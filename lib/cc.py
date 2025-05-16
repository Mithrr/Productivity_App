import os
import io
import json
import requests
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import datetime
from googleapiclient.http import MediaFileUpload

# Google Drive, Calendar, and Tasks API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/calendar',
          'https://www.googleapis.com/auth/tasks']

# Set up your Google Maps API key
GOOGLE_MAPS_API_KEY = 'YOUR_API_KEY_HERE'

def authenticate_google_services():
    """Authenticate and return Google Drive, Calendar, and Tasks services."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

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
    note = {
        'event': event_name,
        'location': location,
        'location_details': location_details,
        'date_time': date_time.isoformat(),
        'related_notes': related_notes or []
    }
    return note

def save_note_to_drive(service, note):
    """Save a note to Google Drive."""
    file_metadata = {
        'name': f"{note['event']}_note.json",
        'mimeType': 'application/json'
    }
    media = MediaFileUpload(io.BytesIO(json.dumps(note).encode('utf-8')), mimetype='application/json')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
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
    task = {
        'title': event_note['event'],
        'notes': f"Location: {event_note['location_details']['address']}" if event_note['location_details'] else f"Location: {event_note['location']}",
        'due': event_note['date_time']
    }
    task_result = tasks_service.tasks().insert(tasklist='@default', body=task).execute()
    return task_result

# Example usage: creating, syncing, and threading notes
if __name__ == "__main__":
    drive_service, calendar_service, tasks_service = authenticate_google_services()

    # Create first note
    event_note_1 = create_event_note('Meeting', 'New York', datetime.datetime.now())
    note_id_1 = save_note_to_drive(drive_service, event_note_1)
    print(f"Note 1 saved with ID: {note_id_1}")

    # Sync the first event with Google Calendar
    calendar_event_1 = sync_event_to_calendar(calendar_service, event_note_1)
    print(f"Event 1 synced with Calendar: {calendar_event_1['id']}")

    # Sync the first event as a task with Google Tasks
    task_1 = sync_note_to_tasks(tasks_service, event_note_1)
    print(f"Task 1 synced with Google Tasks: {task_1['id']}")

    # Create second note and thread it to the first one
    event_note_2 = create_event_note('Conference', 'San Francisco', datetime.datetime.now(), related_notes=[note_id_1])
    note_id_2 = save_note_to_drive(drive_service, event_note_2)
    print(f"Note 2 saved with ID: {note_id_2}")

    # Sync the second event with Google Calendar
    calendar_event_2 = sync_event_to_calendar(calendar_service, event_note_2)
    print(f"Event 2 synced with Calendar: {calendar_event_2['id']}")

    # Sync the second event as a task with Google Tasks
    task_2 = sync_note_to_tasks(tasks_service, event_note_2)
    print(f"Task 2 synced with Google Tasks: {task_2['id']}")