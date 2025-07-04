# ─────────────────── LIBS ───────────────────
from __future__ import print_function
from datetime import datetime, timedelta
from dateutil import tz
import os.path
import pickle
import argparse
import sys
import json
from typing import List, Tuple, Set, Dict, Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# ─────────────────── CONFIG ───────────────────
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CONFIG_FILE = "calendar_config.json"

# Default configuration
DEFAULT_CONFIG = {
    "timezone": "Europe/Tirane",
    "color_scheme": {
        "Spanish video": "10",      # Basil (green)
        "Spanish writing": "10",    # Basil (green)
        "Spanish podcast": "10",    # Basil (green)
        "Deep Work 1": "9",         # Blueberry (blue)
        "Deep Work 2": "9",         # Blueberry (blue)
        "Deep Work 1 (deload)": "1", # Lavender (light blue)
        "Guitar practice": "6",      # Tangerine (orange)
        "Guitar free play": "6",     # Tangerine (orange)
        "Light analytics": "7",      # Peacock (teal)
        "Gym": "11",                # Tomato (red)
        "Gym (deload)": "4",        # Flamingo (light red)
        "Reflection": "5",          # Banana (yellow)
        "Family walk / light analytics": "8", # Graphite (gray)
        "default": "1"              # Lavender for unknown events
    },
    "batch_size": 50,
    "add_completion_prefix": True,  # Add ✓ prefix when marking done
    "completion_strategies": {
        "enabled": True,
        "method": "title_prefix"    # or "color_change" or "description"
    }
}

# Google Calendar Color IDs:
# 1: Lavender, 2: Sage, 3: Grape, 4: Flamingo
# 5: Banana, 6: Tangerine, 7: Peacock, 8: Graphite
# 9: Blueberry, 10: Basil, 11: Tomato

# Format: ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min)
try:
    from my_schedule import schedule
    print("✓ Loaded personal schedule from my_schedule.py")
except ImportError:
    try:
        from schedule_data import schedule
        print("✓ Loaded schedule from schedule_data.py")
    except ImportError:
        print("⚠️  No schedule file found. Using default schedule.")
        schedule = [
            # Add your events here or create my_schedule.py
        ]

# ─────────────────── HELPERS───────────────────
def load_config() -> Dict:
    """Load configuration from file or create default"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"⚠️  Error loading config: {e}. Using defaults.")
    
    # Create default config file
    with open(CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"✓ Created {CONFIG_FILE} with default settings")
    return DEFAULT_CONFIG

def get_event_color(title: str, config: Dict) -> str:
    """Get color ID for an event based on its title"""
    color_scheme = config.get("color_scheme", {})
    
    # Check for exact match first
    if title in color_scheme:
        return color_scheme[title]
    
    # Check for partial match
    for pattern, color in color_scheme.items():
        if pattern != "default" and pattern.lower() in title.lower():
            return color
    
    return color_scheme.get("default", "1")

def get_calendar_service():
    """Get authenticated Google Calendar service with token refresh"""
    creds = None
    token_file = "token.pickle"
    
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)
        
        # Save the credentials for the next run
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)
    
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def iso(dt: datetime) -> str:
    """Convert datetime to ISO format string"""
    return dt.isoformat()

def get_existing_events(service, start_time: datetime, end_time: datetime) -> Set[Tuple[str, str, str]]:
    """Fetch existing events in the given time range"""
    existing = set()
    page_token = None
    
    while True:
        try:
            events_result = service.events().list(
                calendarId="primary",
                timeMin=iso(start_time),
                timeMax=iso(end_time),
                maxResults=2500,
                singleEvents=True,
                pageToken=page_token
            ).execute()
            
            events = events_result.get("items", [])
            for event in events:
                if "summary" in event and "start" in event and "end" in event:
                    existing.add((
                        event["summary"],
                        event["start"].get("dateTime", "")[:16],
                        event["end"].get("dateTime", "")[:16]
                    ))
            
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break
                
        except HttpError as e:
            print(f"Error fetching events: {e}")
            break
    
    return existing

def create_event_batches(events: list, batch_size: int = 50) -> List[list]:
    """Split events into batches to avoid API limits"""
    return [events[i:i + batch_size] for i in range(0, len(events), batch_size)]

def mark_event_complete(service, event_id: str, event: dict, config: Dict) -> bool:
    """Mark an event as complete using configured strategy"""
    if not config.get("completion_strategies", {}).get("enabled", True):
        return False
    
    method = config.get("completion_strategies", {}).get("method", "title_prefix")
    
    try:
        if method == "title_prefix":
            # Add checkmark to title
            if not event["summary"].startswith("✓ "):
                event["summary"] = "✓ " + event["summary"]
        
        elif method == "color_change":
            # Change to gray color
            event["colorId"] = "8"  # Graphite
        
        elif method == "description":
            # Add completion timestamp to description
            desc = event.get("description", "")
            completion_text = f"\n\n✅ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            event["description"] = desc + completion_text
        
        # Update the event
        service.events().update(
            calendarId="primary",
            eventId=event_id,
            body=event
        ).execute()
        return True
        
    except Exception as e:
        print(f"Error marking event complete: {e}")
        return False

# ─────────────────── MAIN ───────────────────
def main(dry_run: bool = False, clear_mode: bool = False, mark_done: Optional[str] = None):
    # Load configuration
    config = load_config()
    timezone = config.get("timezone", "Europe/Tirane")
    
    # 1. Build Calendar service
    try:
        svc = get_calendar_service()
        print("✓ Service ready")
        print(f"🌍 Timezone: {timezone}")
    except Exception as e:
        print(f"✗ Failed to initialize service: {e}")
        return 1
    
    # Handle mark-done mode
    if mark_done:
        print(f"✅ Marking events as done: '{mark_done}'")
        # Search for events today
        today = datetime.now(tz=tz.gettz(timezone))
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end = today.replace(hour=23, minute=59, second=59)
        
        events = svc.events().list(
            calendarId="primary",
            timeMin=iso(start),
            timeMax=iso(end),
            q=mark_done,
            singleEvents=True
        ).execute().get("items", [])
        
        marked = 0
        for event in events:
            if mark_event_complete(svc, event["id"], event, config):
                marked += 1
                print(f"  ✓ Marked: {event['summary']}")
        
        print(f"✓ Marked {marked} event(s) as complete")
        return 0
    
    # 2. Check if schedule has events
    if not schedule:
        print("No events in schedule. Add events to the 'schedule' list.")
        return 0
    
    # 3. Find date range from schedule
    dates = [(s[1], s[2], s[3]) for s in schedule]
    min_date = min(dates)
    max_date = max(dates)
    
    start_time = datetime(min_date[0], min_date[1], min_date[2], 0, 0, tzinfo=tz.gettz(timezone))
    end_time = datetime(max_date[0], max_date[1], max_date[2], 23, 59, 59, tzinfo=tz.gettz(timezone))
    
    print(f"📅 Schedule range: {start_time.date()} to {end_time.date()}")
    
    # 4. Clear mode - delete events in range
    if clear_mode:
        print("🗑️  Clear mode: Removing events in schedule range...")
        existing_events = svc.events().list(
            calendarId="primary",
            timeMin=iso(start_time),
            timeMax=iso(end_time),
            maxResults=2500,
            singleEvents=True
        ).execute().get("items", [])
        
        # Filter events that match our schedule (excluding completed ones)
        schedule_titles = {s[0] for s in schedule}
        events_to_delete = []
        for e in existing_events:
            summary = e.get("summary", "")
            # Remove completion prefix for matching
            clean_summary = summary.replace("✓ ", "")
            if clean_summary in schedule_titles:
                events_to_delete.append(e)
        
        if events_to_delete:
            print(f"Found {len(events_to_delete)} matching events to delete")
            if not dry_run:
                batch = svc.new_batch_http_request()
                for event in events_to_delete:
                    batch.add(svc.events().delete(calendarId="primary", eventId=event["id"]))
                batch.execute()
                print("✓ Events deleted")
            else:
                print("(Dry run - no events deleted)")
        else:
            print("No matching events to delete")
        return 0
    
    # 5. Get existing events
    existing = get_existing_events(svc, start_time, end_time)
    print(f"✓ {len(existing)} events already on calendar")
    
    # 6. Prepare new events with colors
    new_events = []
    skipped = 0
    
    for title, y, m, d, sh, sm, eh, em in schedule:
        start = datetime(y, m, d, sh, sm, tzinfo=tz.gettz(timezone))
        end = datetime(y, m, d, eh, em, tzinfo=tz.gettz(timezone))
        fingerprint = (title, iso(start)[:16], iso(end)[:16])
        
        if fingerprint in existing:
            skipped += 1
            continue
        
        event = {
            "summary": title,
            "start": {"dateTime": iso(start), "timeZone": timezone},
            "end": {"dateTime": iso(end), "timeZone": timezone},
            "colorId": get_event_color(title, config),
            "description": f"Created by calendar automation\nCategory: {title}"
        }
        
        new_events.append(event)
    
    print(f"📊 Summary: {len(new_events)} new, {skipped} skipped (duplicates)")
    
    # Show color mapping
    if new_events and not dry_run:
        print("\n🎨 Color assignments:")
        color_counts = {}
        for event in new_events:
            color = event.get("colorId", "1")
            title_type = event["summary"].split(" ")[0]
            if title_type not in color_counts:
                color_counts[title_type] = color
        
        color_names = {
            "1": "Lavender", "2": "Sage", "3": "Grape", "4": "Flamingo",
            "5": "Banana", "6": "Tangerine", "7": "Peacock", "8": "Graphite",
            "9": "Blueberry", "10": "Basil", "11": "Tomato"
        }
        
        for title_type, color_id in sorted(color_counts.items()):
            print(f"  • {title_type}: {color_names.get(color_id, 'Unknown')}")
    
    # 7. Insert new events in batches
    if new_events:
        if dry_run:
            print(f"\n🔍 Dry run mode - would add {len(new_events)} events:")
            for event in new_events[:5]:  # Show first 5
                color_name = {"1": "Lavender", "2": "Sage", "3": "Grape", "4": "Flamingo",
                             "5": "Banana", "6": "Tangerine", "7": "Peacock", "8": "Graphite",
                             "9": "Blueberry", "10": "Basil", "11": "Tomato"}.get(event.get("colorId", "1"), "Unknown")
                print(f"   • {event['summary']} on {event['start']['dateTime'][:10]} [{color_name}]")
            if len(new_events) > 5:
                print(f"   ... and {len(new_events) - 5} more")
        else:
            print(f"\n↻ Uploading {len(new_events)} new events...")
            
            # Process in batches
            batch_size = config.get("batch_size", 50)
            batches = create_event_batches(new_events, batch_size)
            total_uploaded = 0
            
            for i, batch_events in enumerate(batches, 1):
                print(f"  Batch {i}/{len(batches)} ({len(batch_events)} events)...", end='', flush=True)
                
                batch = svc.new_batch_http_request()
                success_count = 0
                
                def callback(req_id, resp, exc):
                    nonlocal success_count
                    if not exc:
                        success_count += 1
                
                for event in batch_events:
                    batch.add(svc.events().insert(calendarId="primary", body=event), callback=callback)
                
                try:
                    batch.execute()
                    total_uploaded += success_count
                    print(f" ✓ {success_count}/{len(batch_events)} added")
                except Exception as e:
                    print(f" ✗ Error: {e}")
            
            print(f"\n✓ Successfully uploaded {total_uploaded}/{len(new_events)} events")
    else:
        print("✓ No new events to add")
    
    print("\n💡 Tip: Use --mark-done 'Event Name' to mark events as complete")
    print("✓ Done!")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push schedule to Google Calendar with colors")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--clear", action="store_true", help="Clear matching events in date range before adding")
    parser.add_argument("--mark-done", type=str, help="Mark events matching this name as complete")
    
    args = parser.parse_args()
    
    sys.exit(main(dry_run=args.dry_run, clear_mode=args.clear, mark_done=args.mark_done))