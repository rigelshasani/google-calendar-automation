from http.server import BaseHTTPRequestHandler

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
        
        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'received',
            'resource_state': resource_state
        }
        
        import json
        self.wfile.write(json.dumps(response).encode())