#!/usr/bin/env python3
"""
Test Helius API key with getAsset call
Verifies credentials are working and no 403 errors
"""

import json
import os
import sys
import requests

def load_helius_key() -> str:
    """Load Helius API key from env or credentials file"""
    # Try environment variable first
    env_key = os.getenv("HELIUS_API_KEY", "")
    if env_key:
        print(f"✓ Loaded key from environment variable")
        return env_key
    
    # Try credentials file
    creds_paths = [
        os.path.expanduser("~/.config/helius/credentials.json"),
        "/Users/pterion2910/.config/helius/credentials.json",
    ]
    for creds_file in creds_paths:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                    key = creds.get("api_key", "")
                    if key:
                        print(f"✓ Loaded key from {creds_file}")
                        return key
            except Exception as e:
                print(f"✗ Failed to read {creds_file}: {e}")
                continue
    
    return ""

def test_helius_api(api_key: str):
    """Test Helius API with getAsset call on USDC"""
    
    # USDC mint address on Solana
    usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    print(f"\n{'='*60}")
    print("Testing Helius API Connection")
    print(f"{'='*60}")
    print(f"API Key (first 8 chars): {api_key[:8]}...")
    print(f"Testing with USDC: {usdc_mint[:16]}...")
    
    # Test RPC endpoint
    rpc_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAsset",
        "params": [usdc_mint]
    }
    
    try:
        print(f"\n→ Calling getAsset via RPC...")
        response = requests.post(rpc_url, json=payload, timeout=30)
        
        print(f"← Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                result = data["result"]
                print(f"\n✅ SUCCESS! API key is working")
                print(f"   Token: {result.get('symbol', 'N/A')} ({result.get('name', 'N/A')})")
                print(f"   Decimals: {result.get('decimals', 'N/A')}")
                print(f"   Supply: {result.get('supply', 'N/A')}")
                return True
            elif "error" in data:
                print(f"\n⚠️ RPC Error: {data['error']}")
                return False
        elif response.status_code == 403:
            print(f"\n❌ 403 FORBIDDEN - API key is invalid or expired")
            print(f"   Response: {response.text[:200]}")
            return False
        else:
            print(f"\n❌ Unexpected status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timed out")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def test_helius_rest(api_key: str):
    """Test Helius REST API (addresses endpoint)"""
    
    # Test wallet (Solana Foundation)
    test_wallet = "So11111111111111111111111111111111111111112"
    
    print(f"\n{'='*60}")
    print("Testing Helius REST API (v0)")
    print(f"{'='*60}")
    
    rest_url = f"https://api.helius.xyz/v0/addresses/{test_wallet}/transactions"
    
    try:
        print(f"\n→ Calling addresses/transactions...")
        response = requests.get(
            rest_url,
            params={"api-key": api_key, "limit": 1},
            timeout=30
        )
        
        print(f"← Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ REST API working!")
            print(f"   Transactions returned: {len(data) if isinstance(data, list) else 'N/A'}")
            return True
        elif response.status_code == 403:
            print(f"\n❌ 403 FORBIDDEN - API key rejected")
            return False
        else:
            print(f"\n⚠️ Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

def main():
    print("Helius API Key Test")
    print(f"{'='*60}\n")
    
    # Load key
    api_key = load_helius_key()
    
    if not api_key:
        print("\n❌ No Helius API key found!")
        print("   Checked:")
        print("   - HELIUS_API_KEY environment variable")
        print("   - ~/.config/helius/credentials.json")
        sys.exit(1)
    
    # Run tests
    rpc_ok = test_helius_api(api_key)
    rest_ok = test_helius_rest(api_key)
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    print(f"RPC API (getAsset):     {'✅ PASS' if rpc_ok else '❌ FAIL'}")
    print(f"REST API (addresses):   {'✅ PASS' if rest_ok else '❌ FAIL'}")
    
    if rpc_ok and rest_ok:
        print(f"\n🎉 All tests passed! Helius API key is working correctly.")
        sys.exit(0)
    else:
        print(f"\n⚠️  Some tests failed. Check the key and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
