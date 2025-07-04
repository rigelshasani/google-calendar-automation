from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from dateutil import tz
import subprocess
import tempfile

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Get headers
        content_length = int(self.headers.get('Content-Length', 0))
        webhook_token = self.headers.get('X-Goog-Channel-Token', '')
        resource_state = self.headers.get('X-Goog-Resource-State', '')
        
        # Verify token
        if webhook_token != os.environ.get('WEBHOOK_TOKEN', ''):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return
        
        # Handle sync message
        if resource_state == 'sync':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            return
        
        # Handle calendar changes
        if resource_state == 'exists':
            try:
                # Create temp directory for our script
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Write credentials
                    creds_path = os.path.join(tmpdir, 'credentials.json')
                    with open(creds_path, 'w') as f:
                        f.write(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
                    
                    # Write schedule
                    schedule_path = os.path.join(tmpdir, 'my_schedule.py')
                    with open(schedule_path, 'w') as f:
                        f.write(f"schedule = {os.environ.get('SCHEDULE_DATA', '[]')}")
                    
                    # Write config
                    config_path = os.path.join(tmpdir, 'calendar_config.json')
                    with open(config_path, 'w') as f:
                        f.write(os.environ.get('CALENDAR_CONFIG', '{}'))
                    
                    # Copy main script
                    script_content = '''
# Simplified version of push_schedule.py for webhook
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Your existing imports and functions here
from push_schedule import main

if __name__ == "__main__":
    # Run sync with auto-reschedule
    main(sync_mode=True, auto_reschedule=True)
'''
                    
                    script_path = os.path.join(tmpdir, 'sync_calendar.py')
                    with open(script_path, 'w') as f:
                        f.write(script_content)
                    
                    # Also copy your actual push_schedule.py
                    with open('push_schedule.py', 'r') as source:
                        content = source.read()
                        push_script_path = os.path.join(tmpdir, 'push_schedule.py')
                        with open(push_script_path, 'w') as dest:
                            dest.write(content)
                    
                    # Run the sync
                    result = subprocess.run(
                        ['python', script_path],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True
                    )
                    
                    response_data = {
                        'status': 'completed',
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'returncode': result.returncode
                    }
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode())
                    
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')