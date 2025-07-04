# Google Calendar Schedule Automation

```
   ___      _                _            
  / __\__ _| | ___ _ __   __| | __ _ _ __ 
 / /  / _` | |/ _ \ '_ \ / _` |/ _` | '__|
/ /__| (_| | |  __/ | | | (_| | (_| | |   
\____/\__,_|_|\___|_| |_|\__,_|\__,_|_|   
     /\        |                    |  _)            
    /  \  _   _| |_ ___  _ __ ___   __ _| |_ _  ___  _ __  
   / /\ \| | | | __/ _ \| '_ ` _ \ / _` | __| |/ _ \| '_ \ 
  / ____ \ |_| | || (_) | | | | | | (_| | |_| | (_) | | | |
 /_/    \_\__,_|\__\___/|_| |_| |_|\__,_|\__|_|\___/|_| |_|
```

A Python script to batch upload recurring schedules to Google Calendar with color coding, timezone support, and completion tracking.

## Features

- **Automatic color coding** by event type
- **Configurable timezone** support
- **Mark events as complete** (changes color to gray)
- **Batch upload** for efficiency
- **Clear mode** to remove old events
- **Dry run** mode for testing
- **Duplicate detection** to avoid re-adding events

## Prerequisites

- Python 3.7+
- Google Calendar API enabled
- Google Cloud credentials

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/calendar-automation.git
   cd calendar-automation
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google Calendar API**

   **Step 1: Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "Select a project" dropdown at the top
   - Click "NEW PROJECT"
   - Enter a project name (e.g., "Calendar Automation")
   - Click "CREATE"
   - Wait for the project to be created (~30 seconds)

   **Step 2: Enable Google Calendar API**
   - Make sure your new project is selected in the dropdown
   - Click the hamburger menu (☰) → "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click on "Google Calendar API" in the results
   - Click "ENABLE" button
   - Wait for the API to be enabled

   **Step 3: Create OAuth 2.0 Credentials**
   - After enabling, click "CREATE CREDENTIALS" button (or go to "APIs & Services" → "Credentials")
   - Click "+ CREATE CREDENTIALS" → "OAuth client ID"
   
   **Step 4: Configure OAuth Consent Screen (first time only)**
   - If prompted, you'll need to configure the consent screen first:
     - Choose "External" user type (unless you have Google Workspace)
     - Click "CREATE"
     - Fill in required fields:
       - App name: "Calendar Automation" (or your choice)
       - User support email: your email
       - Developer contact: your email
     - Click "SAVE AND CONTINUE"
     - On Scopes page: click "SAVE AND CONTINUE" (no changes needed)
     - On Test users page: click "SAVE AND CONTINUE"
     - Click "BACK TO DASHBOARD"

   **Step 5: Create OAuth Client ID**
   - Go back to "Credentials" → "+ CREATE CREDENTIALS" → "OAuth client ID"
   - Application type: Select "Desktop app"
   - Name: "Calendar Automation Client" (or your choice)
   - Click "CREATE"

   **Step 6: Download Credentials**
   - A popup will show your client ID and secret
   - Click "DOWNLOAD JSON" button
   - Rename the downloaded file to `credentials.json`
   - Move it to your project root directory (same folder as `push_schedule.py`)

   **Important Notes:**
   - Keep `credentials.json` private (it's in .gitignore)
   - First run will open a browser for authentication
   - The script will create `token.pickle` for future runs

4. **Configure your schedule**
   
   **Option A: Create manually**
   ```python
   # In push_schedule.py, add your events:
   schedule = [
       ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min),
       ('Deep Work', 2025, 7, 7, 9, 0, 11, 0),
       # ... more events
   ]
   ```

   **Option B: Use AI to generate your schedule**
   
   Copy this prompt to ChatGPT, Claude, or another AI assistant:
   
   > I need help creating a recurring schedule for Google Calendar automation. Please ask me about:
   > 
   > 1. My main priorities and goals for this schedule period
   > 2. Current projects I'm working on and their time requirements  
   > 3. Non-negotiable commitments (work hours, meetings, etc.)
   > 4. Personal activities I want to include (exercise, hobbies, learning)
   > 5. My ideal daily routine and energy levels throughout the day
   > 6. How many weeks I want to schedule
   > 7. Any specific time blocks or patterns I prefer
   > 
   > Based on my answers, generate a Python schedule list in this exact format:
   > ```python
   > schedule = [
   >     ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min),
   >     # ... more events
   > ]
   > ```
   > 
   > Make sure to:
   > - Balance deep work with breaks
   > - Respect my energy patterns
   > - Include buffer time between activities
   > - Create a sustainable routine
   > - Account for weekends differently if needed
   
   The AI will interview you and create a personalized schedule that you can paste directly into the script!

## Usage

### Basic Commands

```bash
# First run - authenticate and create config
python push_schedule.py

# Dry run - see what would be added
python push_schedule.py --dry-run

# Clear old events and add new ones
python push_schedule.py --clear

# Mark an event as complete (turns gray)
python push_schedule.py --mark-done "Deep Work"
```

### Configuration

The script creates `calendar_config.json` on first run:

```json
{
  "timezone": "Europe/Tirane",
  "color_scheme": {
    "Deep Work": "9",     // Blue
    "Meeting": "11",      // Red
    "Exercise": "10",     // Green
    "default": "1"        // Lavender
  },
  "completion_strategies": {
    "enabled": true,
    "method": "color_change"  // or "title_prefix"
  }
}
```

### Color Codes
```
1: Lavender    2: Sage       3: Grape      4: Flamingo
5: Banana      6: Tangerine  7: Peacock    8: Graphite
9: Blueberry  10: Basil     11: Tomato
```

## Project Structure

```
calendar-automation/
├── push_schedule.py          # Main script
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore file
├── README.md                # This file
├── calendar_config.json     # Created on first run
├── credentials.json         # Your Google API credentials (git ignored)
└── token.pickle            # Auth token (created on first run, git ignored)
```

## Security Notes

- Never commit `credentials.json` or `token.pickle`
- Keep your `calendar_config.json` private if it contains sensitive info
- The `.gitignore` file handles this automatically

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Google Calendar API
- Inspired by the need for better calendar automation

---
```
 _____________________
|  _________________  |
| | JAN 01     09:00| |
| |_________________| |
|  ___ ___ ___   ___ |
| |   |   |   | |   ||
| |___|___|___| |___||    Made with love by the 
| |   |   |   | |   ||    open source community
| |___|___|___| |___||         ♥ ♥ ♥
| |   |   |   | |   ||        
| |___|___|___| |___||
|_____________________|
```