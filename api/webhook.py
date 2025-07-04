from datetime import datetime
import json
import os

def handler(request):
    """Vercel Python function handler"""
    
    # Handle GET requests (for testing)
    if request.method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/plain'},
            'body': 'Webhook is working!'
        }
    
    # Handle POST requests (from Google Calendar)
    if request.method == 'POST':
        # Get headers
        headers = request.headers
        webhook_token = headers.get('x-goog-channel-token', '')
        resource_state = headers.get('x-goog-resource-state', '')
        
        # Verify token
        expected_token = os.environ.get('WEBHOOK_TOKEN', '')
        if webhook_token != expected_token:
            return {
                'statusCode': 401,
                'body': 'Unauthorized'
            }
        
        # Handle sync message
        if resource_state == 'sync':
            return {
                'statusCode': 200,
                'body': 'Sync acknowledged'
            }
        
        # Handle calendar changes
        if resource_state == 'exists':
            # For now, just acknowledge
            # TODO: Add your sync logic here
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'received',
                    'resource_state': resource_state,
                    'timestamp': datetime.now().isoformat()
                })
            }
        
        return {
            'statusCode': 200,
            'body': 'OK'
        }
    
    # Method not allowed
    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }