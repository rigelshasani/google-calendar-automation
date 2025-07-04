# stop_old_watch.py
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load the old watch info
with open('watch_info.json', 'r') as f:
    old_watch = json.load(f)

# Setup service
with open('service-account-key.json', 'r') as f:
    service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=credentials)

# Stop the old watch
try:
    service.channels().stop(body={
        'id': old_watch['channel_id'],
        'resourceId': old_watch['resource_id']
    }).execute()
    print("Old watch stopped")
except:
    print("Old watch already expired or stopped")