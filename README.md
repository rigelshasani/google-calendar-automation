# 📅 Google Calendar Schedule Automation

A Python script to batch upload recurring schedules to Google Calendar with color coding, timezone support, and completion tracking.

## ✨ Features

- 🎨 **Automatic color coding** by event type
- 🌍 **Configurable timezone** support
- ✅ **Mark events as complete** (changes color to gray)
- 🔄 **Batch upload** for efficiency
- 🧹 **Clear mode** to remove old events
- 🔍 **Dry run** mode for testing
- ⚡ **Duplicate detection** to avoid re-adding events

## 📋 Prerequisites

- Python 3.7+
- Google Calendar API enabled
- Google Cloud credentials

## 🚀 Setup

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
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or select existing)
   - Enable the Google Calendar API
   - Create credentials (OAuth 2.0 Client ID)
   - Download as `credentials.json` and place in project root

4. **Configure your schedule**
   ```python
   # In push_schedule.py, add your events:
   schedule = [
       ('Event Name', year, month, day, start_hour, start_min, end_hour, end_min),
       ('Deep Work', 2025, 7, 7, 9, 0, 11, 0),
       # ... more events
   ]
   ```

## 🎮 Usage

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
- 1: Lavender, 2: Sage, 3: Grape, 4: Flamingo
- 5: Banana, 6: Tangerine, 7: Peacock, 8: Graphite
- 9: Blueberry, 10: Basil, 11: Tomato

## 📁 Project Structure

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

## 🔒 Security Notes

- Never commit `credentials.json` or `token.pickle`
- Keep your `calendar_config.json` private if it contains sensitive info
- The `.gitignore` file handles this automatically

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with Google Calendar API
- Inspired by the need for better calendar automation