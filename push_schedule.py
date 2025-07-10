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
CONFIG_FILE = "config.json"


# Default configuration (fallback)
DEFAULT_CONFIG = {
    "timezone": "Europe/Tirane",
    "color_scheme": {
        "Spanish video": "10",
        "Spanish writing": "10",
        "Spanish podcast": "10",
        "Deep Work 1": "9",
        "Deep Work 2": "9",
        "Deep Work 1 (deload)": "1",
        "Guitar practice": "6",
        "Guitar free play": "6",
        "Light analytics": "7",
        "Gym": "11",
        "Gym (deload)": "4",
        "Reflection": "5",
        "Family walk / light analytics": "8",
        "default": "1"
    },
    "batch_size": 50,
    "add_completion_prefix": True,
    "completion_strategies": {
        "enabled": True,
        "method": "color_change"
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

# Load configuration from file or fallback
try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    print(f"✓ Loaded configuration from {CONFIG_FILE}")
except Exception as e:
    print(f"⚠️  Failed to load {CONFIG_FILE}, using DEFAULT_CONFIG. Reason: {e}")
    config = DEFAULT_CONFIG

    # pull the calendar ID
    CALENDAR_ID = config.get("calendar_id", "primary")

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
            events_result = api_call_with_retry(
                lambda: service.events().list(
                    calendarId=CALENDAR_ID,
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
                    calendarId=CALENDAR_ID,
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

def events_overlap(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
    *,
    min_minutes: int = 0,            # treat overlaps shorter than this as “no conflict”
) -> bool:
    """
    Return True if the two intervals overlap for at least `min_minutes`.

    Example:
        # 15-minute clash, but we only care about ≥30-minute overlaps
        events_overlap(a_start, a_end, b_start, b_end, min_minutes=30)  -> False
    """
    latest_start  = max(start1, start2)
    earliest_end  = min(end1, end2)
    overlap       = (earliest_end - latest_start).total_seconds() / 60
    return overlap >= min_minutes

def is_scheduled_event(calendar_event: Dict, schedule_events: List) -> bool:
    """Check if a calendar event matches any scheduled event"""
    if "summary" not in calendar_event or "start" not in calendar_event:
        return False
    
    cal_summary = calendar_event["summary"].replace("✓ ", "")  # Remove completion marker
    
    for sched_event in schedule_events:
        if cal_summary == sched_event[0]:
            return True
    
    return False

# ──────────────────────────────────────────────────────────────────────
# Replace the whole detect_conflicts definition with this one
# ──────────────────────────────────────────────────────────────────────
def detect_conflicts(
    calendar_events: List[Dict],
    schedule_events: List,
    date: datetime,
    timezone_str: str,
) -> List[Dict]:
    """
    Return overlaps between *manual* calendar events and the fixed schedule
    on `date`.  Ignores events that the script itself created.
    """

    # ---- 1. build fingerprints of every scheduled block ----------------
    schedule_fps: Set[Tuple[str, str, str]] = set()
    for title, y, m, d, sh, sm, eh, em in schedule_events:
        st = datetime(y, m, d, sh, sm, tzinfo=tz.gettz(timezone_str))
        en = datetime(y, m, d, eh, em, tzinfo=tz.gettz(timezone_str))
        schedule_fps.add((title, iso(st), iso(en)))

    # ---- 2. keep only that day’s schedule as datetime objects ----------
    sched_today = []
    for title, y, m, d, sh, sm, eh, em in schedule_events:
        if (y, m, d) != (date.year, date.month, date.day):
            continue
        st = datetime(y, m, d, sh, sm, tzinfo=tz.gettz(timezone_str))
        en = datetime(y, m, d, eh, em, tzinfo=tz.gettz(timezone_str))
        sched_today.append({"title": title, "start": st, "end": en})

    # ---- 3. compare each calendar item --------------------------------
    conflicts = []
    for cal in calendar_events:
        # we only need start/end; title can be empty
        if "start" not in cal or "end" not in cal:
            continue

        cal_title = cal.get("summary", "").replace("✓ ", "")   # default = ""
        cal_start = parse_datetime(cal["start"]["dateTime"], timezone_str)
        cal_end   = parse_datetime(cal["end"]["dateTime"],   timezone_str)

        # skip our own scheduled items (exact fingerprint match)
        if (cal_title, iso(cal_start), iso(cal_end)) in schedule_fps:
            continue

        # test against each fixed block
        for sched in sched_today:
            if events_overlap(
                cal_start,
                cal_end,
                sched["start"],
                sched["end"],
                min_minutes=1,      # ignore <1-minute noise
            ):
                conflicts.append(
                    {
                        "manual_event": cal,
                        "scheduled_event": sched,
                        "manual_start": cal_start,
                        "manual_end":   cal_end,
                    }
                )
    return conflicts


from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

def calculate_rescheduled_time(
    event: Dict,
    conflicts: List[Dict],
    all_events: List[Dict],
    config: Dict,
    timezone_str: str,
    blocked: List[Tuple[datetime, datetime]],      # from handle_conflicts
    schedule_titles: set,                          # ← pass {s[0] for s in schedule}
) -> Optional[Tuple[datetime, datetime]]:
    """
    Find first legal slot for `event` after its conflicts.
    Returns (new_start, new_end) or None if no slot fits.
    """

    buffer  = config.get("conflict_resolution", {}).get("buffer_minutes", 30)
    max_end = config.get("conflict_resolution", {}).get("max_end_time", "23:59")
    duration = event["end"] - event["start"]

    latest_end = max(c["manual_end"] for c in conflicts)
    start = latest_end + timedelta(minutes=buffer)
    end   = start + duration

    # ----- helpers ----------------------------------------------------
    max_end_t = datetime.strptime(max_end, "%H:%M").time()

    def fixed_clashes(s: datetime, e: datetime) -> List[Tuple[datetime, datetime]]:
        """Return (start,end) of calendar items that block this slot."""
        blocking = []
        for ev in all_events:
            title = ev.get("summary", "").replace("✓ ", "")
            # ignore every schedule block (they are flexible)
            if title in schedule_titles:
                continue
            st = parse_datetime(ev["start"]["dateTime"], timezone_str)
            en = parse_datetime(ev["end"]["dateTime"],   timezone_str)
            if events_overlap(s, e, st, en, min_minutes=1):
                blocking.append((st, en))
        return blocking

    # ----- search loop ------------------------------------------------
    while True:
        # midnight / max_end guard
        if (end.date() == start.date() and end.time() > max_end_t) or (
            end.date() > start.date() and end.time() > max_end_t
        ):
            return None

        # clash with already-accepted moves?
        if any(events_overlap(start, end, st, en, min_minutes=1) for st, en in blocked):
            bump = max(en for st, en in blocked if events_overlap(start, end, st, en))
            start = bump + timedelta(minutes=buffer)
            end   = start + duration
            continue

        # clash with fixed (non-schedule) calendar items?
        blockers = fixed_clashes(start, end)
        if blockers:
            bump = min(en for st, en in blockers if en >= end)  # nearest gap
            start = bump + timedelta(minutes=buffer)
            end   = start + duration
            continue

        # slot is clear
        return start, end


    # advance until the slot becomes valid
    while slot_invalid(new_start, new_end):
        # push just past the nearest conflicting end
        candidates = [new_end]

        for ev in all_events:
            if ev.get("summary", "").replace("✓ ", "") == event["title"]:
                continue
            st = parse_datetime(ev["start"]["dateTime"], timezone_str)
            en = parse_datetime(ev["end"]["dateTime"],   timezone_str)
            if events_overlap(new_start, new_end, st, en, min_minutes=1):
                candidates.append(en)

        for st, en in blocked:
            if events_overlap(new_start, new_end, st, en, min_minutes=1):
                candidates.append(en)

        bump_point = min(c for c in candidates if c >= new_end)
        new_start  = bump_point + timedelta(minutes=buffer)
        new_end    = new_start + duration

        # give up if we’re forced past max_end
        if new_end.time() > max_end_t and new_end.date() == new_start.date():
            return None

    return new_start, new_end


    # helper to test “legal” slot quickly
    def slot_valid(start: datetime, end: datetime) -> bool:
        # stay before max_end even if we spill past midnight
        if end.date() > start.date() and end.time() > max_end_dt:
            return False
        if end.date() == start.date() and end.time() > max_end_dt:
            return False
        # clash with fixed calendar items?
        for cal in all_events:
            st = parse_datetime(cal["start"]["dateTime"], timezone_str)
            en = parse_datetime(cal["end"]["dateTime"],   timezone_str)
            if events_overlap(start, end, st, en, min_minutes=1):
                return False
        # clash with moves we have already accepted?
        for st, en in blocked:
            if events_overlap(start, end, st, en, min_minutes=1):
                return False
        return True

    # advance until we find a valid gap
    while not slot_valid(new_start, new_end):
        # push to the later of: next conflicting item’s end OR current end
        bump_to = max(
            [new_end]
            + [parse_datetime(cal["end"]["dateTime"], timezone_str) for cal in all_events
               if events_overlap(new_start, new_end,
                                 parse_datetime(cal["start"]["dateTime"], timezone_str),
                                 parse_datetime(cal["end"]["dateTime"],   timezone_str),
                                 min_minutes=1)]
            + [en for st, en in blocked
               if events_overlap(new_start, new_end, st, en, min_minutes=1)]
        )
        new_start = bump_to + timedelta(minutes=buffer)
        new_end   = new_start + duration
        # give up if we run past max_end
        if not slot_valid(new_start, new_end):
            if new_end.time() > max_end_dt:
                return None

    return new_start, new_end


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
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=event
            ).execute()
        )
        return True
        
    except Exception as e:
        print(f"Error marking event complete: {e}")
        return False

def handle_conflicts(
    service,
    conflicts: List[Dict],
    all_events: List[Dict],
    schedule_events: List,
    config: Dict,
    timezone_str: str,
    dry_run: bool = True,
) -> List[Dict]:
    """Reschedule each fixed-schedule block so it no longer overlaps manual items."""
    if not conflicts:
        return []

    print(f"\n⚠️  Found {len(conflicts)} conflicts:")

    # ── 1. debug print ───────────────────────────────────────────────
    for c in conflicts:
        m  = c["manual_event"]
        se = c["scheduled_event"]
        ms = c["manual_start"].strftime("%H:%M")
        me = c["manual_end"].strftime("%H:%M")
        print(
            f"\nDEBUG: Manual '{m.get('summary', 'No title')}' {ms}-{me}\n"
            f"       Scheduled '{se['title']}' "
            f"{se['start'].strftime('%H:%M')}-{se['end'].strftime('%H:%M')}"
        )

    # ── 2. group conflicts by schedule block ────────────────────────
    by_title: Dict[str, List[Dict]] = {}
    for c in conflicts:
        by_title.setdefault(c["scheduled_event"]["title"], []).append(c)

    # titles of every fixed schedule item (used to ignore them as blockers)
    schedule_titles = {s[0] for s in schedule_events}

    rescheduled: List[Dict] = []
    accepted:   List[Tuple[datetime, datetime]] = []   # slots already placed

    # ── 3. process blocks in chronological order ────────────────────
    for title, ev_conflicts in sorted(
        by_title.items(),
        key=lambda item: item[1][0]["scheduled_event"]["start"],  # earliest first
    ):
        # ignore “self-conflicts”
        real_conflicts = [
            c for c in ev_conflicts
            if c["manual_event"].get("summary", "").replace("✓ ", "") != title
        ]
        if not real_conflicts:
            continue

        scheduled_event = real_conflicts[0]["scheduled_event"]

        new_times = calculate_rescheduled_time(
            scheduled_event,
            real_conflicts,
            all_events,
            config,
            timezone_str,
            blocked=accepted,           # already accepted moves
            schedule_titles=schedule_titles,   # ignore flexible blocks
        )

        if not new_times:
            print(f"    ✗ No free slot for '{title}'")
            continue

        new_start, new_end = new_times
        accepted.append((new_start, new_end))
        print(f"    → Moving '{title}' to {new_start.strftime('%H:%M')}–{new_end.strftime('%H:%M')}")

        if dry_run:
            rescheduled.append(
                {"title": title, "old_start": scheduled_event["start"],
                 "new_start": new_start, "new_end": new_end}
            )
            continue  # skip API updates

        # ── 4. update Google Calendar entry ──────────────────────────
        for cal_event in all_events:
            if (
                cal_event.get("summary", "").replace("✓ ", "") == title
                and "dateTime" in cal_event.get("start", {})
            ):
                cal_start = parse_datetime(cal_event["start"]["dateTime"], timezone_str)
                if cal_start == scheduled_event["start"]:
                    cal_event["start"]["dateTime"] = iso(new_start)
                    cal_event["end"]["dateTime"]   = iso(new_end)
                    try:
                        api_call_with_retry(
                            lambda: service.events()
                            .update(calendarId=CALENDAR_ID, eventId=cal_event["id"], body=cal_event)
                            .execute()
                        )
                        rescheduled.append(
                            {"title": title,
                             "old_start": scheduled_event["start"],
                             "new_start": new_start,
                             "new_end": new_end}
                        )
                        print("    ✓ Rescheduled successfully")
                    except Exception as exc:
                        print(f"    ✗ API error: {exc}")
                    break

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
        # Check July 7 instead of today
        today = datetime(2025, 7, 7, tzinfo=tz.gettz(timezone))
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
                calendarId=CALENDAR_ID,
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
                calendarId=CALENDAR_ID,
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
                    batch.add(svc.events().insert(calendarId=CALENDAR_ID, body=event), callback=callback)
                
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