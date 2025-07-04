from datetime import datetime
import json

def handler(event, context):
    """
    Vercel Python handler
    event contains: body, headers, path, httpMethod
    """
    
    # Get HTTP method
    method = event.get('httpMethod', 'GET')
    
    if method == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/plain'
            },
            'body': 'Webhook is working!'
        }
    
    elif method == 'POST':
        # Get headers (lowercase in event)
        headers = event.get('headers', {})
        webhook_token = headers.get('x-goog-channel-token', '')
        resource_state = headers.get('x-goog-resource-state', '')
        
        # Log for debugging
        print(f"Received webhook: {resource_state}")
        print(f"Headers: {json.dumps(headers)}")
        
        # Handle sync message
        if resource_state == 'sync':
            return {
                'statusCode': 200,
                'body': 'Sync acknowledged'
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'status': 'received',
                'method': method,
                'resource_state': resource_state
            })
        }
    
    return {
        'statusCode': 405,
        'body': 'Method not allowed'
    }