#!/usr/bin/env python3
"""
Simple test to verify bot connection and event handling
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_bot_connection():
    """Test if bot can connect to Slack and receive events"""
    
    print("🧪 Testing Bot Connection")
    print("=" * 40)
    
    # Check environment variables
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
    
    print(f"Bot Token: {'✅ Set' if bot_token else '❌ Missing'}")
    print(f"Signing Secret: {'✅ Set' if signing_secret else '❌ Missing'}")
    
    if not bot_token:
        print("❌ SLACK_BOT_TOKEN not found in environment variables")
        return False
    
    # Test bot authentication
    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {bot_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"✅ Bot authenticated successfully")
                print(f"   Bot User ID: {data.get('user_id')}")
                print(f"   Team: {data.get('team')}")
                print(f"   Team ID: {data.get('team_id')}")
                return True
            else:
                print(f"❌ Bot authentication failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing bot connection: {str(e)}")
        return False

def test_app_endpoint():
    """Test if the Flask app is responding"""
    
    print("\n🌐 Testing App Endpoint")
    print("=" * 40)
    
    try:
        response = requests.get("http://127.0.0.1:3000/")
        
        if response.status_code == 200:
            print("✅ Flask app is responding")
            return True
        else:
            print(f"❌ Flask app returned status: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Flask app is not running on port 3000")
        print("   Make sure to run: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error testing app endpoint: {str(e)}")
        return False

def check_slack_app_config():
    """Provide guidance on Slack app configuration"""
    
    print("\n🔧 Slack App Configuration Check")
    print("=" * 40)
    print("Please verify these settings in your Slack App:")
    print()
    print("1. **Event Subscriptions**:")
    print("   - Request URL: https://your-ngrok-url.ngrok-free.app/slack/events")
    print("   - Subscribe to bot events:")
    print("     ✅ message.channels")
    print("     ✅ message.groups")
    print("     ✅ message.im")
    print("     ✅ message.mpim")
    print()
    print("2. **OAuth & Permissions**:")
    print("   - Bot Token Scopes:")
    print("     ✅ channels:read")
    print("     ✅ channels:history")
    print("     ✅ chat:write")
    print("     ✅ users:read")
    print("     ✅ commands")
    print()
    print("3. **App Installation**:")
    print("   - App should be installed to workspace")
    print("   - Bot should be invited to channels")
    print()
    print("4. **Test Commands**:")
    print("   - Try: /ticket-status")
    print("   - Try: /update-ticket")
    print("   - Try: /assign-ticket")

if __name__ == "__main__":
    print("Starting bot connection tests...\n")
    
    # Test bot connection
    bot_ok = test_bot_connection()
    
    # Test app endpoint
    app_ok = test_app_endpoint()
    
    # Provide configuration guidance
    check_slack_app_config()
    
    print("\n🎯 Summary:")
    if bot_ok and app_ok:
        print("✅ Bot connection and app are working")
        print("✅ If bot still doesn't respond, check Slack app configuration above")
    else:
        print("❌ Some tests failed - check the issues above")
    
    print("\n💡 Next Steps:")
    print("1. Verify Slack app configuration")
    print("2. Check ngrok URL is correct in Event Subscriptions")
    print("3. Try sending a message in a channel where bot is present")
    print("4. Check app logs for any error messages") 