import os
import json
import datetime
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
import requests

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.appdata',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/tasks.readonly'
]
def get_location_details(location):
    """Get location details using Google Maps Geocoding API."""
    api_key = 'AIzaSyBYr7iPTU-Zeq096_m_IfU5uhaln8HneY8'  # Replace with your actual API key
    geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={api_key}"
    
    response = requests.get(geocode_url)
    logger.debug(f"Geocoding API response: {response.text}")  # Log the full response for debugging
    
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            # Extract latitude and longitude from the response
            latitude = data['results'][0]['geometry']['location']['lat']
            longitude = data['results'][0]['geometry']['location']['lng']
            return {
                "address": data['results'][0]['formatted_address'],
                "latitude": latitude,
                "longitude": longitude
            }
        else:
            logger.error("No results found for the given location.")
            return {
                "address": location,
                "latitude": 0.0,
                "longitude": 0.0
            }
    else:
        logger.error(f"Error fetching location details: {response.status_code} - {response.text}")
        return {
            "address": location,
            "latitude": 0.0,
            "longitude": 0.0
        }
def authenticate_google_services():
    """Authenticate and create service objects for Google APIs."""
    creds = None
    
    # Check if credentials.json exists
    if not os.path.exists('credentials.json'):
        logger.error("credentials.json file not found!")
        raise FileNotFoundError("Please download credentials.json from Google Cloud Console")

    # Load existing credentials if available
    if os.path.exists('token.pickle'):
        logger.info("Loading existing credentials from token.pickle")
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If credentials are invalid or don't exist, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            logger.info("Getting new credentials")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open('token.pickle', 'wb') as token:
            logger.info("Saving credentials to token.pickle")
            pickle.dump(creds, token)

    # Build services
    logger.info("Building Google services")
    drive_service = build('drive', 'v3', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)

    return drive_service, calendar_service, tasks_service

def get_location_details(location):
    """Mock function to get location details. Replace with actual geocoding service if needed."""
    return {
        "address": location,
        "latitude": 0.0,
        "longitude": 0.0
    }
def create_event_note(event_name, location, date_time, related_notes=None):
    """Create a new event note with location details."""
    logger.info(f"Creating event note for: {event_name}")
    
    location_details = get_location_details(location)  # This will now fetch real location data
    
    if isinstance(date_time, datetime.datetime):
        date_time_str = date_time.isoformat()
    else:
        date_time_str = date_time

    note = {
        'event': event_name,
        'location': location,
        'location_details': location_details,  # This will now contain real data
        'date_time': date_time_str,
        'related_notes': related_notes or []
    }
    return note
def save_note_to_drive(service, note):
    """Save a note to Google Drive."""
    logger.info(f"Saving note to Drive: {note['event']}")
    
    # Create temporary file name
    temp_file_path = f"{note['event'].replace(' ', '_')}_note.json"
    with open(temp_file_path, 'w') as temp_file:
        json.dump(note, temp_file)

    file_metadata = {
        'name': f"{note['event']}_note.json",
        'mimeType': 'application/json'
    }

    media = MediaFileUpload(temp_file_path, mimetype='application/json')

    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logger.info(f"File saved to Drive with ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logger.error(f"Error saving to Drive: {str(e)}")
        raise
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def sync_note_to_calendar(service, note):
    """Sync the event note with Google Calendar."""
    logger.info(f"Syncing note to Calendar: {note['event']}")
    
    # Parse the datetime
    start_time = datetime.datetime.fromisoformat(note ['date_time'])
    end_time = start_time + datetime.timedelta(hours=1)  # Default 1-hour duration

    event = {
        'summary': note['event'],
        'location': note['location_details']['address'],
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
    }

    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Calendar event created: {event.get('id')}")
        return event
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        raise

def sync_note_to_tasks(service, note):
    """Sync the event note as a task with Google Tasks."""
    logger.info(f"Syncing note to Tasks: {note['event']}")
    
    due_date = datetime.datetime.fromisoformat(note['date_time']).isoformat() + 'Z'
    
    task = {
        'title': note['event'],
        'notes': f"Location: {note['location_details']['address']}",
        'due': due_date
    }

    try:
        # Get the default task list
        tasklists = service.tasklists().list().execute()
        if not tasklists.get('items'):
            tasklist = service.tasklists().insert(body={'title': 'My Tasks'}).execute()
            tasklist_id = tasklist['id']
        else:
            tasklist_id = tasklists['items'][0]['id']

        task_result = service.tasks().insert(tasklist=tasklist_id, body=task).execute()
        logger.info(f"Task created: {task_result.get('id')}")
        return task_result
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise

def test_services():
    """Test connection to Google services."""
    try:
        logger.info("Testing Google services connection...")
        
        # Load credentials
        creds = None
        if os.path.exists('token.pickle'):
            logger.info("Loading existing credentials from token.pickle")
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.info("Getting new credentials")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            with open('token.pickle', 'wb') as token:
                logger.info("Saving new credentials to token.pickle")
                pickle.dump(creds, token)
        
        logger.info("Building Google services")
        drive_service = build('drive', 'v3', credentials=creds)
        calendar_service = build('calendar', 'v3', credentials=creds)
        tasks_service = build('tasks', 'v1', credentials=creds)
        
        # Test Drive API
        drive_about = drive_service.about().get(fields='user').execute()
        logger.info(f"Drive API connected for user: {drive_about['user']['emailAddress']}")
        
        # Test Calendar API
        calendar_list = calendar_service.calendarList().list().execute()
        logger.info("Calendar API connected successfully")
        
        # Test Tasks API
        tasks_lists = tasks_service.tasklists().list().execute()
        logger.info("Tasks API connected successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Service test failed: {str(e)}")
        return False

def main():
    """Main function to run the sync process."""
    try:
        logger.info("Starting Google services sync application")
        
        # Test services first
        if not test_services():
            logger.error("Service test failed")
            return

        # Initialize services
        drive_service, calendar_service, tasks_service = authenticate_google_services()
        
        # Create a sample event note with a specific location
        current_time = datetime.datetime.now()
        test_note = create_event_note(
            event_name="Test Meeting",
            location="1600 Amphitheatre Parkway, Mountain View, CA",  # Use a valid address
            date_time=current_time
        )
        
        # Save note to Drive
        logger.info("Saving note to Drive...")
        file_id = save_note_to_drive(drive_service, test_note)
        logger.info(f"Note saved to Drive with ID: {file_id}")
        
        # Sync to Calendar
        logger.info("Syncing to Calendar...")
        calendar_event = sync_note_to_calendar(calendar_service, test_note)
        logger.info(f"Calendar event created with ID: {calendar_event['id']}")
        
        # Sync to Tasks
        logger.info("Syncing to Tasks...")
        task = sync_note_to_tasks(tasks_service, test_note)
        logger.info(f"Task created with ID: {task['id']}")
        
        logger.info("Sync process completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
if __name__ == "__main__":
    main()