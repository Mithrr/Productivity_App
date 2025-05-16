import os
import json
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
import datetime

# Google Drive, Calendar, and Tasks API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/calendar',
          'https://www.googleapis.com/auth/tasks']

# Set up your Google Maps API key
GOOGLE_MAPS_API_KEY = '_'

def authenticate_google_services():
    """Authenticate and return Google Drive, Calendar, and Tasks services."""
    creds = None
    # Check if token.json exists and load it as Credentials object
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, prompt the user to log in.
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    drive_service = build('drive', 'v3', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)
    return drive_service, calendar_service, tasks_service
def get_location_details(location_name):
    """Fetch location details using Google Maps API."""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location_name}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        if result['results']:
            location_data = result['results'][0]
            formatted_address = location_data['formatted_address']
            coordinates = location_data['geometry']['location']
            return {
                'address': formatted_address,
                'lat': coordinates['lat'],
                'lng': coordinates['lng']
            }
    return None

def create_event_note(event_name, location, date_time, related_notes=None):
    """Create a new event note with location details."""
    location_details = get_location_details(location)
    
    # Ensure date_time is in ISO format
    if isinstance(date_time, datetime.datetime):
        date_time_str = date_time.isoformat()
    else:
        date_time_str = date_time
        
    note = {
        'event': event_name,
        'location': location,
        'location_details': location_details,
        'date_time': date_time_str,
        'related_notes': related_notes or []
    }
    return note

def save_note_to_drive(service, note):
    """Save a note to Google Drive in a dedicated folder."""
    # First, check if notes folder exists, if not create it
    folder_name = "Meeting Notes"
    folder_id = None
    
    # Search for the folder
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    if not results['files']:
        # Create folder if it doesn't exist
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
    else:
        folder_id = results['files'][0]['id']

    # Create a temporary file to store the note
    temp_file_path = f"{note['event']}_note.json"
    with open(temp_file_path, 'w') as temp_file:
        json.dump(note, temp_file)

    file_metadata = {
        'name': f"{note['event']}_note.json",
        'parents': [folder_id],  # Place in the notes folder
        'mimeType': 'application/json',
        'description': f"Meeting note for {note['event']} created on {datetime.now().strftime('%Y-%m-%d')}"
    }

    media = MediaFileUpload(temp_file_path, mimetype='application/json')

    # Upload the file to Google Drive
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webViewLink'  # Also get the web view link
    ).execute()
    
    # Clean up the temporary file
    os.remove(temp_file_path)

    print(f"Note saved to Drive: {file.get('webViewLink')}")  # Print direct link
    return file.get('id')
    """Save a note to Google Drive."""
    # Create a temporary file to store the note
    temp_file_path = f"{note['event']}_note.json"
    with open(temp_file_path, 'w') as temp_file:
        json.dump(note, temp_file)

    file_metadata = {
        'name': f"{note['event']}_note.json",
        'mimeType': 'application/json'
    }

    media = MediaFileUpload(temp_file_path, mimetype='application/json')

    # Upload the file to Google Drive
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    # Clean up the temporary file
    os.remove(temp_file_path)

    return file.get('id')

def sync_event_to_calendar(calendar_service, event_note):
    """Sync the event note with Google Calendar."""
    event = {
        'summary': event_note['event'],
        'location': event_note['location_details']['address'] if event_note['location_details'] else event_note['location'],
        'start': {
            'dateTime': event_note['date_time'],
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (datetime.datetime.fromisoformat(event_note['date_time']) + datetime.timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        }
    }
    event_result = calendar_service.events().insert(calendarId='primary', body=event).execute()
    return event_result

def sync_note_to_tasks(tasks_service, event_note):
    """Sync the event note as a task with Google Tasks."""
    # Convert datetime to RFC 3339 format
    due_date = datetime.datetime.fromisoformat(event_note['date_time']).isoformat('T') + 'Z'
    
    task = {
        'title': event_note['event'],
        'notes': f"Location: {event_note['location_details']['address'] if event_note['location_details'] else event_note['location']}",
        'due': due_date
    }
    
    # First, get the default task list ID
    tasklists = tasks_service.tasklists().list().execute()
    if not tasklists.get('items'):
        # Create a new task list if none exists
        tasklist = tasks_service.tasklists().insert(body={'title': 'My Tasks'}).execute()
        tasklist_id = tasklist['id']
    else:
        # Use the first available task list
        tasklist_id = tasklists['items'][0]['id']
    
    # Insert the task into the specified task list
    task_result = tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
    return task_result