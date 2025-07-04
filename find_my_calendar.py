import pickle
from googleapiclient.discovery import build

# Use YOUR credentials (not service account)
with open('token.pickle', 'rb') as token:
    creds = pickle.load(token)

service = build('calendar', 'v3', credentials=creds)

print("=== YOUR Calendars ===")
calendar_list = service.calendarList().list().execute()

your_calendar_id = None
for cal in calendar_list.get('items', []):
    print(f"\nCalendar: {cal['summary']}")
    print(f"  ID: {cal['id']}")
    print(f"  Primary: {cal.get('primary', False)}")
    
    if cal.get('primary'):
        your_calendar_id = cal['id']
        print("  ^^ THIS IS YOUR MAIN CALENDAR!")

if your_calendar_id:
    print(f"\n✅ Your calendar ID is: {your_calendar_id}")
    print("\nNOTE: If this is your Gmail address, you can use it instead of 'primary' in the watch!")