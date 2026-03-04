#!/usr/bin/env python3
"""Quick test of Helius API key"""
import json
import os
import sys

def load_helius_key():
    """Load Helius API key from credentials"""
    env_key = os.getenv("HELIUS_API_KEY", "")
    if env_key:
        return env_key
    
    creds_file = os.path.expanduser("~/.config/helius/credentials.json")
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                creds = json.load(f)
                return creds.get("api_key", "")
        except Exception as e:
            print(f"Error reading credentials: {e}")
    
    return ""

import requests

helius_key = load_helius_key()
if not helius_key:
    print("❌ No Helius API key found")
    sys.exit(1)

print(f"✅ Loaded Helius key: {helius_key[:8]}...{helius_key[-4:]}")
print()

# Test getAsset call with SOL token mint
test_mint = "So11111111111111111111111111111111111111112"  # Wrapped SOL
url = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getAsset",
    "params": {
        "id": test_mint
    }
}

print(f"Testing getAsset for: {test_mint}")
print(f"URL: {url[:50]}...")
print()

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if "result" in data:
            result = data["result"]
            print("✅ API call successful!")
            print(f"Token: {result.get('content', {}).get('metadata', {}).get('name', 'N/A')}")
            print(f"Symbol: {result.get('content', {}).get('metadata', {}).get('symbol', 'N/A')}")
            print()
            print("Helius API key is working correctly.")
        elif "error" in data:
            print(f"❌ API error: {data['error']}")
            sys.exit(1)
    elif response.status_code == 403:
        print("❌ 403 Forbidden - API key may be invalid or rate limited")
        print(f"Response: {response.text}")
        sys.exit(1)
    else:
        print(f"❌ Unexpected status: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Request failed: {e}")
    sys.exit(1)
