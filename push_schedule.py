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
from httplib2 import Http

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
        "method": "color_change"    # or "title_prefix" or "description"
    },
    "conflict_resolution": {
        "enabled": True,
        "buffer_minutes": 30,
        "max_end_time": "23:59",
        "gym_preferences": {
            "morning_end": "17:30",
            "evening_start": "19:30"
        }
    }
}

# Google Calendar Color IDs:
# 1: Lavender, 2: Sage, 3: Grape, 4: Flamingo
# 5: Banana, 6: Tangerine, 7: Peacock, 8: Graphite
# 9: Blueberry, 10: Basil, 11: Tomato

# Format: ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min)
try:
    from my_schedule import schedule  # type: ignore
    print("✓ Loaded personal schedule from my_schedule.py")
except ImportError:
    try:
        from schedule_data import schedule  # type: ignore
        print("✓ Loaded schedule from schedule_data.py")
    except ImportError:
        print("⚠️  No schedule file found. Using default schedule.")
        schedule = [
            # Add your events here or create my_schedule.py
        ]

def validate_schedule(schedule):
    """Validate schedule format and data types"""
    for i, event in enumerate(schedule):
        if len(event) != 8:
            raise ValueError(f"Event {i} has {len(event)} fields, expected 8")
        
        title, y, m, d, sh, sm, eh, em = event
        if not isinstance(title, str):
            raise ValueError(f"Event {i}: title must be string")
        
        # Validate date/time values
        try:
            datetime(y, m, d, sh, sm)
            datetime(y, m, d, eh, em)
        except ValueError as e:
            raise ValueError(f"Event {i} '{title}': {e}")
        
        if (sh, sm) >= (eh, em):
            raise ValueError(f"Event {i} '{title}': end time before start time")


# Validate the schedule immediately after loading
try:
    validate_schedule(schedule)
    print(f"✓ Validated {len(schedule)} schedule entries")
except ValueError as e:
    print(f"❌ Schedule validation failed: {e}")
    print("Please fix your schedule file and try again.")
    sys.exit(1)

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
    
        # Add timeout to all API calls
    http = Http(timeout=30)
    return build("calendar", "v3", credentials=creds, 
                 http=http, cache_discovery=False)

def iso(dt: datetime) -> str:
    """Convert datetime to ISO format string"""
    return dt.isoformat()

def get_existing_events(service, start_time: datetime, end_time: datetime) -> Set[Tuple[str, str, str]]:
    """Fetch existing events in the given time range"""
    existing = set()
    page_token = None
    
    while True:
        try:
            events_result = api_call_with_retry(
                lambda: service.events().list(
                    calendarId="primary",
                    timeMin=iso(start_time),
                    timeMax=iso(end_time),
                    maxResults=2500,
                    singleEvents=True,
                    pageToken=page_token
                ).execute()
)
            
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

def get_all_calendar_events(service, start_time: datetime, end_time: datetime) -> List[Dict]:
    """Fetch all calendar events with full details"""
    all_events = []
    page_token = None
    
    while True:
        try:
            events_result = api_call_with_retry(
                lambda: service.events().list(
                    calendarId="primary",
                    timeMin=iso(start_time),
                    timeMax=iso(end_time),
                    maxResults=2500,
                    singleEvents=True,
                    pageToken=page_token,
                    orderBy="startTime"
                ).execute()
            )
            
            all_events.extend(events_result.get("items", []))
            
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break
                
        except HttpError as e:
            print(f"Error fetching events: {e}")
            break
    
    return all_events

def parse_datetime(dt_string: str, timezone_str: str) -> datetime:
    """Parse datetime string to timezone-aware datetime object"""
    from dateutil.parser import isoparse
    
    # Use dateutil's robust parser
    dt = isoparse(dt_string)
    
    # If naive, assume it's in the config timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.gettz(timezone_str))
    else:
        # Convert to config timezone
        dt = dt.astimezone(tz.gettz(timezone_str))
    
    return dt
def events_overlap(event1_start: datetime, event1_end: datetime, 
                  event2_start: datetime, event2_end: datetime) -> bool:
    """Check if two events overlap"""
    return event1_start < event2_end and event2_start < event1_end

def is_scheduled_event(calendar_event: Dict, schedule_events: List) -> bool:
    """Check if a calendar event matches any scheduled event"""
    if "summary" not in calendar_event or "start" not in calendar_event:
        return False
    
    cal_summary = calendar_event["summary"].replace("✓ ", "")  # Remove completion marker
    
    for sched_event in schedule_events:
        if cal_summary == sched_event[0]:
            return True
    
    return False

def detect_conflicts(calendar_events: List[Dict], schedule_events: List, 
                    date: datetime, timezone_str: str) -> List[Dict]:
    """Detect conflicts between manual calendar events and scheduled events"""
    conflicts = []
    
    # Convert schedule events for this date to datetime objects
    scheduled_for_date = []
    for s in schedule_events:
        title, y, m, d, sh, sm, eh, em = s
        if y == date.year and m == date.month and d == date.day:
            start = datetime(y, m, d, sh, sm, tzinfo=tz.gettz(timezone_str))
            end = datetime(y, m, d, eh, em, tzinfo=tz.gettz(timezone_str))
            scheduled_for_date.append({
                'title': title,
                'start': start,
                'end': end,
                'original': s
            })
    
    # Check each calendar event
    for cal_event in calendar_events:
        # Skip if it's one of our scheduled events
        if is_scheduled_event(cal_event, schedule_events):
            continue
        
        # Parse calendar event times
        cal_start = parse_datetime(cal_event["start"]["dateTime"], timezone_str)
        cal_end = parse_datetime(cal_event["end"]["dateTime"], timezone_str)
        
        # Check against each scheduled event
        for sched_event in scheduled_for_date:
            if events_overlap(cal_start, cal_end, sched_event['start'], sched_event['end']):
                conflicts.append({
                    'manual_event': cal_event,
                    'scheduled_event': sched_event,
                    'manual_start': cal_start,
                    'manual_end': cal_end
                })
    
    return conflicts

def calculate_rescheduled_time(event: Dict, conflicts: List[Dict], 
                             all_events: List[Dict], config: Dict, 
                             timezone_str: str) -> Optional[Tuple[datetime, datetime]]:
    """Calculate new time for an event considering conflicts and preferences"""
    
    buffer = config.get("conflict_resolution", {}).get("buffer_minutes", 30)
    max_end = config.get("conflict_resolution", {}).get("max_end_time", "23:59")
    
    # Original event times
    orig_start = event['start']
    orig_end = event['end']
    duration = orig_end - orig_start
    
    # Find the latest conflict end time
    latest_conflict_end = max(c['manual_end'] for c in conflicts 
                             if c['scheduled_event']['title'] == event['title'])
    
    # Proposed new start time (conflict end + buffer)
    new_start = latest_conflict_end + timedelta(minutes=buffer)
    new_end = new_start + duration
    
    # Special handling for Gym events
    if "gym" in event['title'].lower():
        gym_prefs = config.get("conflict_resolution", {}).get("gym_preferences", {})
        try:
            morning_end = datetime.strptime(gym_prefs.get("morning_end", "17:30"), "%H:%M").time()
            evening_start = datetime.strptime(gym_prefs.get("evening_start", "19:30"), "%H:%M").time()
        except ValueError:
            # Handle invalid time format
            morning_end = datetime.strptime("17:30", "%H:%M").time()
            evening_start = datetime.strptime("19:30", "%H:%M").time()
        
        # If pushed past morning window, move to evening
        if new_start.time() > morning_end and new_start.time() < evening_start:
            new_start = new_start.replace(hour=evening_start.hour, minute=evening_start.minute)
            new_end = new_start + duration
    
    # Fix: Parse max_end_time properly
    max_end_dt = datetime.strptime(max_end, "%H:%M")
    
    # Check if we're crossing midnight
    if new_end.date() > new_start.date():
        # Event spans midnight - check if end time is before max
        if new_end.time() > max_end_dt.time():
            return None  # Too late (goes past max time on next day)
    else:
        # Same day - normal check
        if new_end.time() > max_end_dt.time():
            return None  # Too late
    
    # Check for conflicts with other events at the new time
    for cal_event in all_events:
        if "start" not in cal_event or "dateTime" not in cal_event["start"]:
            continue
            
        other_start = parse_datetime(cal_event["start"]["dateTime"], timezone_str)
        other_end = parse_datetime(cal_event["end"]["dateTime"], timezone_str)
        
        # Add buffer to avoid back-to-back scheduling
        if events_overlap(new_start - timedelta(minutes=5), 
                         new_end + timedelta(minutes=5), 
                         other_start, other_end):
            # Try to push further
            new_start = other_end + timedelta(minutes=buffer)
            new_end = new_start + duration
            
            # Recheck gym preferences
            if "gym" in event['title'].lower() and new_start.time() > morning_end and new_start.time() < evening_start:
                new_start = new_start.replace(hour=evening_start.hour, minute=evening_start.minute)
                new_end = new_start + duration
            
            # Recheck max end time with midnight crossing logic
            if new_end.date() > new_start.date():
                if new_end.time() > max_end_dt.time():
                    return None
            else:
                if new_end.time() > max_end_dt.time():
                    return None
    
    return (new_start, new_end)

def create_event_batches(events: list, batch_size: int = 50) -> List[list]:
    """Split events into batches to avoid API limits"""
    return [events[i:i + batch_size] for i in range(0, len(events), batch_size)]

def api_call_with_retry(func, max_retries=3):
    """Simple retry wrapper for API calls"""
    import time
    from googleapiclient.errors import HttpError
    
    for attempt in range(max_retries):
        try:
            return func()
        except HttpError as e:
            if e.resp.status in [403, 429, 500, 503] and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                print(f"  ⚠️  API error {e.resp.status}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception(f"Failed after {max_retries} attempts")

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
        api_call_with_retry(
            lambda: service.events().update(
                calendarId="primary",
                eventId=event_id,
                body=event
            ).execute()
        )
        return True
        
    except Exception as e:
        print(f"Error marking event complete: {e}")
        return False

def handle_conflicts(service, conflicts: List[Dict], all_events: List[Dict], 
                    schedule_events: List, config: Dict, timezone_str: str, 
                    dry_run: bool = True) -> List[Dict]:
    """Handle conflicts by rescheduling events"""
    
    if not conflicts:
        return []
    
    print(f"\n⚠️  Found {len(conflicts)} conflicts:")
    
    # Group conflicts by scheduled event
    conflicts_by_event = {}
    for conflict in conflicts:
        event_title = conflict['scheduled_event']['title']
        if event_title not in conflicts_by_event:
            conflicts_by_event[event_title] = []
        conflicts_by_event[event_title].append(conflict)
    
    rescheduled = []
    
    for event_title, event_conflicts in conflicts_by_event.items():
        scheduled_event = event_conflicts[0]['scheduled_event']
        manual_event = event_conflicts[0]['manual_event']
        
        print(f"  - '{manual_event['summary']}' conflicts with '{event_title}'")
        
        # Calculate new time
        new_times = calculate_rescheduled_time(scheduled_event, event_conflicts, 
                                             all_events, config, timezone_str)
        
        if new_times:
            new_start, new_end = new_times
            print(f"    → Rescheduling '{event_title}' to {new_start.strftime('%H:%M')} - {new_end.strftime('%H:%M')}")
            
            if not dry_run:
                # Find the existing calendar event to update
                for cal_event in all_events:
                    if (cal_event.get("summary", "").replace("✓ ", "") == event_title and
                        "dateTime" in cal_event.get("start", {})):
                        
                        cal_start = parse_datetime(cal_event["start"]["dateTime"], timezone_str)
                        if (cal_start.date() == scheduled_event['start'].date() and
                            cal_start.hour == scheduled_event['start'].hour and
                            cal_start.minute == scheduled_event['start'].minute):
                            
                            # Update the event
                            cal_event["start"]["dateTime"] = iso(new_start)
                            cal_event["end"]["dateTime"] = iso(new_end)
                            
                            try:
                                api_call_with_retry(
                                    lambda: service.events().update(
                                        calendarId="primary",
                                        eventId=cal_event["id"],
                                        body=cal_event
                                    ).execute()
                                )
                                
                                rescheduled.append({
                                    'title': event_title,
                                    'old_start': scheduled_event['start'],
                                    'new_start': new_start,
                                    'new_end': new_end
                                })
                                print(f"    ✓ Rescheduled successfully")
                            except Exception as e:
                                print(f"    ✗ Error rescheduling: {e}")
                            break
        else:
            print(f"    ✗ Cannot reschedule '{event_title}' within constraints")
    
    return rescheduled

# ─────────────────── MAIN ───────────────────
def main(dry_run: bool = False, clear_mode: bool = False, mark_done: Optional[str] = None, 
         sync_mode: bool = False, auto_reschedule: bool = False):
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
    
    # Handle sync mode
    if sync_mode:
        print("\n🔄 Checking for conflicts...")
        
        # Get today's date
        today = datetime.now(tz=tz.gettz(timezone))
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Fetch all calendar events for today
        all_events = get_all_calendar_events(svc, start, end)
        
        # Detect conflicts
        conflicts = detect_conflicts(all_events, schedule, today, timezone)
        
        if conflicts:
            if auto_reschedule or (not dry_run and input("\nReschedule conflicts? (y/n): ").lower() == 'y'):
                handle_conflicts(svc, conflicts, all_events, schedule, config, 
                               timezone, dry_run=dry_run)
            else:
                print("\nNo changes made. Use --auto-reschedule to automatically handle conflicts.")
        else:
            print("✓ No conflicts found!")
        
        return 0
    
    # Handle mark-done mode
    if mark_done:
        print(f"✅ Marking events as done: '{mark_done}'")
        # Search for events today
        today = datetime.now(tz=tz.gettz(timezone))
        start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end = today.replace(hour=23, minute=59, second=59)
        
        events = api_call_with_retry(
            lambda: svc.events().list(
                calendarId="primary",
                timeMin=iso(start),
                timeMax=iso(end),
                q=mark_done,
                singleEvents=True
            ).execute()
        ).get("items", [])
        
        marked = 0
        for event in events:
            if mark_event_complete(svc, event["id"], event, config):
                marked += 1
                print(f"  ✓ Marked: {event['summary']}")
        
        print(f"✓ Marked {marked} event(s) as complete")
        return 0
    
    # 2. Check if schedule has events
    if not schedule:
        print("No events in schedule. Create my_schedule.py with format:")
        print("schedule = [")
        print("    ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min),")
        print("    ('Deep Work', 2025, 7, 7, 9, 0, 11, 0),")
        print("]")
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
        existing_events = api_call_with_retry(
            lambda: svc.events().list(
                calendarId="primary",
                timeMin=iso(start_time),
                timeMax=iso(end_time),
                maxResults=2500,
                singleEvents=True
            ).execute()
        ).get("items", [])
        
        # Only delete events with exact fingerprint match (title + time)
        schedule_fingerprints = set()
        for s in schedule:
            title, y, m, d, sh, sm, eh, em = s
            start = datetime(y, m, d, sh, sm, tzinfo=tz.gettz(timezone))
            end = datetime(y, m, d, eh, em, tzinfo=tz.gettz(timezone))
            fingerprint = (title, iso(start), iso(end))
            schedule_fingerprints.add(fingerprint)
        
        events_to_delete = []
        for e in existing_events:
            if "summary" in e and "start" in e and "end" in e:
                event_fingerprint = (
                    e["summary"].replace("✓ ", ""),
                    e["start"]["dateTime"],
                    e["end"]["dateTime"]
                )
                if event_fingerprint in schedule_fingerprints:
                    events_to_delete.append(e)
    
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
                # Visual progress bar
                progress = "█" * i + "░" * (len(batches) - i)
                print(f"\r  Progress: [{progress}] {i}/{len(batches)} ({len(batch_events)} events)...", end='', flush=True)
                
                batch = svc.new_batch_http_request()
                success_count = 0
                failed_count = 0
                
                def callback(req_id, resp, exc):
                    nonlocal success_count, failed_count
                    if not exc:
                        success_count += 1
                    else:
                        failed_count += 1
                        # Only print errors on new line to not break progress bar
                        if hasattr(exc, 'resp') and exc.resp.status == 403:
                            print(f"\n    ⚠️  Quota exceeded - stopping batch")
                            raise  # Stop the batch
                
                for event in batch_events:
                    batch.add(svc.events().insert(calendarId="primary", body=event), callback=callback)
                
                try:
                    batch.execute()
                    total_uploaded += success_count
                except Exception as e:
                    print(f"\n    ✗ Error in batch {i}: {e}")
                    break  # Stop processing more batches on error
            
            # Clear the progress bar line and show final result
            print(f"\r  Progress: [{'█' * len(batches)}] Complete!                    ")
            print(f"\n✓ Successfully uploaded {total_uploaded}/{len(new_events)} events")
    else:
        print("✓ No new events to add")
    
    print("\n💡 Tips:")
    print("  - Use --sync to check for conflicts with manual calendar entries")
    print("  - Use --mark-done 'Event Name' to mark events as complete")
    print("✓ Done!")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push schedule to Google Calendar with colors")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--clear", action="store_true", help="Clear matching events in date range before adding")
    parser.add_argument("--mark-done", type=str, help="Mark events matching this name as complete")
    parser.add_argument("--sync", action="store_true", help="Check for conflicts and suggest rescheduling")
    parser.add_argument("--auto-reschedule", action="store_true", help="Automatically reschedule on conflicts (use with --sync)")
    
    args = parser.parse_args()
    
    sys.exit(main(dry_run=args.dry_run, clear_mode=args.clear, mark_done=args.mark_done,
                  sync_mode=args.sync, auto_reschedule=args.auto_reschedule))