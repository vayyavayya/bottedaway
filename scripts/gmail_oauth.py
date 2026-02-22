#!/usr/bin/env python3
"""
Gmail OAuth Flow - Get refresh token for Himalaya
"""
import json
import os
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

CREDENTIALS_PATH = os.path.expanduser("~/.config/openclaw/google/gmail/credentials.json")
TOKEN_PATH = os.path.expanduser("~/.config/openclaw/google/gmail/token.json")
REDIRECT_PORT = 8085

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            self.server.auth_code = params['code'][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed.")

def get_refresh_token():
    # Load credentials
    with open(CREDENTIALS_PATH) as f:
        creds = json.load(f)['installed']
    
    client_id = creds['client_id']
    client_secret = creds['client_secret']
    redirect_uri = f"http://localhost:{REDIRECT_PORT}"
    
    # Build auth URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        "scope=https://mail.google.com/+https://www.googleapis.com/auth/gmail.modify&"
        "response_type=code&"
        "access_type=offline&"
        "prompt=consent"
    )
    
    print("Opening browser for Gmail authorization...")
    print(f"If browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)
    
    # Start local server to receive callback
    server = HTTPServer(('localhost', REDIRECT_PORT), OAuthHandler)
    server.auth_code = None
    server.handle_request()
    
    if not server.auth_code:
        print("❌ Failed to get authorization code")
        return False
    
    # Exchange code for tokens
    token_data = {
        'code': server.auth_code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=urllib.parse.urlencode(token_data).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            tokens = json.loads(response.read().decode())
            
            with open(TOKEN_PATH, 'w') as f:
                json.dump(tokens, f, indent=2)
            
            print("✅ Tokens saved successfully!")
            print(f"Refresh token: {tokens.get('refresh_token', 'N/A')[:20]}...")
            return True
    except Exception as e:
        print(f"❌ Token exchange failed: {e}")
        return False

if __name__ == "__main__":
    if get_refresh_token():
        print(f"\nTokens stored in: {TOKEN_PATH}")
    else:
        exit(1)
