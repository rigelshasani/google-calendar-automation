import json
import uuid
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Your webhook URL from Vercel
WEBHOOK_URL = 'https://google-calendar-automation.vercel.app/api/webhook'
WEBHOOK_TOKEN = 'your-secret-token-0000032123394ffkd'

# Load service account from your local file
with open('service-account-key.json', 'r') as f:
    service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=credentials)

# First, stop any existing watches
try:
    with open('watch_info.json', 'r') as f:
        old_watch = json.load(f)
    
    print("Stopping old watch...")
    service.channels().stop(body={
        'id': old_watch['channel_id'],
        'resourceId': old_watch['resource_id']
    }).execute()
    print("✓ Old watch stopped")
except:
    print("No existing watch to stop")

# Create new watch
channel_id = str(uuid.uuid4())
expiration = int((time.time() + 604800) * 1000)  # 7 days

request_body = {
    'id': channel_id,
    'type': 'web_hook',
    'address': WEBHOOK_URL,
    'token': WEBHOOK_TOKEN,
    'expiration': expiration
}

print(f"\nCreating new watch...")
print(f"Webhook URL: {WEBHOOK_URL}")
print(f"Channel ID: {channel_id}")

try:
    response = service.events().watch(
        calendarId='rigels1304@gmail.com',
        body=request_body
    ).execute()
    
    print(f"\n✅ Watch created successfully!")
    print(f"Resource ID: {response['resourceId']}")
    print(f"Expiration: {response['expiration']}")
    
    # Save for later reference
    with open('watch_info.json', 'w') as f:
        json.dump({
            'channel_id': response['id'],
            'resource_id': response['resourceId'],
            'expiration': response['expiration'],
            'created_at': time.time()
        }, f, indent=2)
    
    print(f"\n📝 Watch info saved")
    print(f"\n⚠️  IMPORTANT: Check Vercel logs NOW - you should see a 'sync' message!")
        
except Exception as e:
    print(f"\n❌ Error creating watch: {e}")