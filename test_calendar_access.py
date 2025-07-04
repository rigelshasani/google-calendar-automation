from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from datetime import datetime

# Load service account
with open('service-account-key.json', 'r') as f:
    service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=credentials)

# Try to list events
try:
    # List calendars first
    print("=== Checking Calendar Access ===")
    calendar_list = service.calendarList().list().execute()
    print(f"\nAccessible calendars: {len(calendar_list.get('items', []))}")
    
    for cal in calendar_list.get('items', []):
        print(f"- {cal['summary']} (ID: {cal['id']})")
    
    # Now check events in primary calendar
    print("\n=== Events in Primary Calendar ===")
    events = service.events().list(
        calendarId='rigels1304@gmail.com',
        timeMin='2025-07-07T00:00:00Z',
        timeMax='2025-07-08T00:00:00Z',
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    items = events.get('items', [])
    print(f"Found {len(items)} events on July 7:")
    
    for event in items:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"  - {event.get('summary', 'No title')} at {start}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    if "calendar not found" in str(e).lower():
        print("\n⚠️  The service account doesn't have access to your primary calendar!")
        print("Make sure to share your calendar with: calendar-464910@appspot.gserviceaccount.com")