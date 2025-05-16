# app.py (Backend)
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import datetime
import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import logging

# Initialize Flask app and CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})  # Update CORS to allow frontend origin

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define your Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

def authenticate_google_services():
    """Authenticate and create service objects for Google APIs."""
    creds = None
    if not os.path.exists('credentials.json'):
        raise FileNotFoundError("Please download credentials.json from Google Cloud Console")

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
    return drive_service

def create_event_note(event_name, location, date_time, related_notes):
    """Create a formatted event note."""
    note_content = f"Event: {event_name}\nLocation: {location}\nDate and Time: {date_time}\nNotes: {related_notes}"
    return note_content

def save_note_to_drive(service, note):
    """Save the note to Google Drive."""
    file_metadata = {
        'name': 'Event Note - ' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'mimeType': 'application/vnd.google-apps.document'
    }

    with open('note.txt', 'w') as f:
        f.write(note)
    
    media = MediaFileUpload('note.txt', mimetype='text/plain')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    os.remove('note.txt')
    
    return file.get('id')

@app.route('/add-note', methods=['POST'])
def add_note():
    """Endpoint to add a new event note."""
    data = request.json
    logger.debug("Received data: %s", data)  # Log the received data
    event_name = data.get('eventName')
    location = data.get('location')
    date_time = data.get('dateTime')  # Should be in ISO format now
    notes = data.get('notes')

    try:
        drive_service = authenticate_google_services()
        note = create_event_note(event_name, location, date_time, related_notes=[notes])
        file_id = save_note_to_drive(drive_service, note)
        return jsonify({'fileId': file_id}), 200
    except Exception as e:
        logger.error("Error adding note: %s", str(e))  # Log the error
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True) 
