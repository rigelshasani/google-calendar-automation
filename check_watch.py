import json
import time
from datetime import datetime

try:
    with open('watch_info.json', 'r') as f:
        watch = json.load(f)
    
    # Check expiration
    expiry_ms = int(watch['expiration'])
    expiry_time = datetime.fromtimestamp(expiry_ms / 1000)
    now = datetime.now()
    
    print("=" * 50)
    print("GOOGLE CALENDAR WATCH STATUS")
    print("=" * 50)
    print(f"Watch Channel ID: {watch['channel_id']}")
    print(f"Resource ID: {watch['resource_id']}")
    print(f"Created at: {datetime.fromtimestamp(watch['created_at']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Expires at: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Status: {'✅ ACTIVE' if expiry_time > now else '❌ EXPIRED'}")
    
    if expiry_time > now:
        time_remaining = expiry_time - now
        days = time_remaining.days
        hours = time_remaining.seconds // 3600
        print(f"Time remaining: {days} days, {hours} hours")
        print("\n✓ Your watch is active and should be sending webhooks!")
    else:
        print("\n✗ Your watch has expired. Run setup_calendar_watch.py again.")
    
except FileNotFoundError:
    print("❌ No watch_info.json found!")
    print("Have you run setup_calendar_watch.py?")
except Exception as e:
    print(f"Error checking watch: {e}")