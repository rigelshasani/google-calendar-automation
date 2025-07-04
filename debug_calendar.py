# Create debug_calendar.py
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Load service account
with open('service-account-key.json', 'r') as f:
    service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=credentials)

# Check calendar list
print("=== Checking Calendars ===")
try:
    # Get calendar list
    calendar_list = service.calendarList().list().execute()
    
    if not calendar_list.get('items'):
        # No calendars in list, but we can still access primary
        print("No calendars in calendarList, but 'primary' is accessible")
        
        # Get primary calendar directly
        primary = service.calendars().get(calendarId='primary').execute()
        print(f"\nPrimary calendar:")
        print(f"  ID: {primary.get('id', 'N/A')}")
        print(f"  Summary: {primary.get('summary', 'N/A')}")
        print(f"  Time Zone: {primary.get('timeZone', 'N/A')}")
    else:
        for cal in calendar_list['items']:
            print(f"\nCalendar: {cal['summary']}")
            print(f"  ID: {cal['id']}")
            print(f"  Access Role: {cal['accessRole']}")
            
except Exception as e:
    print(f"Error: {e}")

# Test event creation to trigger webhook
print("\n=== Testing Event Creation ===")
try:
    from datetime import datetime, timedelta
    
    # Create a test event
    now = datetime.utcnow()
    event = {
        'summary': 'Webhook Test Event - Delete Me',
        'start': {
            'dateTime': '2025-07-07T14:00:00Z',
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': '2025-07-07T15:00:00Z',
            'timeZone': 'UTC',
        },
        'description': f'Created at {now.isoformat()} to test webhook'
    }
    
    created_event = service.events().insert(
        calendarId='primary',
        body=event
    ).execute()
    
    print(f"✓ Created test event: {created_event.get('htmlLink')}")
    print(f"Event ID: {created_event['id']}")
    print("\n⚠️  CHECK VERCEL LOGS NOW - This should trigger a webhook!")
    
except Exception as e:
    print(f"Error creating event: {e}")