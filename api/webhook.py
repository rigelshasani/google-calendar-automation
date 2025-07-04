from http.server import BaseHTTPRequestHandler
import json
import os
import subprocess
import tempfile

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Webhook is working!')
        
    def do_POST(self):
        # Get headers
        token = self.headers.get('X-Goog-Channel-Token')
        resource_state = self.headers.get('X-Goog-Resource-State')
        
        # Verify token
        expected_token = os.environ.get('WEBHOOK_TOKEN', '')
        if expected_token and token != expected_token:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return
        
        # Log the webhook call
        print(f"Webhook received: {resource_state}")
        
        # Handle sync message (sent when watch is created)
        if resource_state == 'sync':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Sync acknowledged')
            return
        
        # Handle actual calendar changes
        if resource_state == 'exists':
            try:
                # Option 1: Trigger GitHub Action
                if os.environ.get('GITHUB_TOKEN'):
                    import urllib.request
                    import urllib.error
                    
                    github_token = os.environ.get('GITHUB_TOKEN')
                    url = 'https://api.github.com/repos/rigelshasani/google-calendar-automation/dispatches'
                    
                    data = json.dumps({
                        'event_type': 'calendar-sync'
                    }).encode('utf-8')
                    
                    req = urllib.request.Request(
                        url,
                        data=data,
                        headers={
                            'Authorization': f'token {github_token}',
                            'Accept': 'application/vnd.github.v3+json',
                            'Content-Type': 'application/json'
                        }
                    )
                    
                    try:
                        response = urllib.request.urlopen(req)
                        print(f"GitHub Action triggered: {response.status}")
                    except urllib.error.HTTPError as e:
                        print(f"Failed to trigger GitHub Action: {e.code}")
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'status': 'processed',
                    'resource_state': resource_state,
                    'action': 'github_action_triggered' if os.environ.get('GITHUB_TOKEN') else 'logged_only'
                }
                
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                print(f"Error processing webhook: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            # Unknown state
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'received',
                'resource_state': resource_state
            }
            
            self.wfile.write(json.dumps(response).encode())