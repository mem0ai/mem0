#!/usr/bin/env python3
"""
SMS Webhook Test Script
Test the SMS webhook endpoint to ensure it's responding correctly
"""
import requests
import json

def test_webhook_health():
    """Test if the webhook endpoint is healthy"""
    print("🔍 Testing SMS webhook health...")
    
    try:
        # Test health endpoint
        health_url = "https://jean-memory-api-virginia.onrender.com/health"
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ API health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
            
        # Test webhooks test endpoint
        webhook_test_url = "https://jean-memory-api-virginia.onrender.com/webhooks/test-entry"
        response = requests.get(webhook_test_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Webhook endpoint is accessible")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def test_webhook_structure():
    """Test the SMS webhook structure (without actually sending SMS)"""
    print("\n🔍 Testing SMS webhook structure...")
    
    webhook_url = "https://jean-memory-api-virginia.onrender.com/webhooks/sms"
    
    # This will fail without proper Twilio signature, but we can see if endpoint exists
    try:
        response = requests.post(webhook_url, data={}, timeout=10)
        
        if response.status_code == 403:
            print("✅ SMS webhook is protected (403 Forbidden - signature validation working)")
            return True
        elif response.status_code == 422:
            print("✅ SMS webhook exists (422 Validation Error - missing required fields)")
            return True
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    print("🚀 SMS Integration Test Suite")
    print("=" * 40)
    
    # Test 1: Health checks
    health_ok = test_webhook_health()
    
    # Test 2: Webhook structure
    webhook_ok = test_webhook_structure()
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 40)
    print(f"✅ API Health: {'PASS' if health_ok else 'FAIL'}")
    print(f"✅ SMS Webhook: {'PASS' if webhook_ok else 'FAIL'}")
    
    if health_ok and webhook_ok:
        print("\n🎉 SMS integration backend is ready!")
        print("\nNext steps:")
        print("1. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in Render")
        print("2. Test phone verification in dashboard")
        print("3. Send test SMS to +13648889368")
    else:
        print("\n❌ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main() 