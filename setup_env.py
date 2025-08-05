#!/usr/bin/env python3
"""
Environment Setup Script for Fix Kar Slack Bot
Helps set up environment variables for both local and production deployment
"""

import os
import json
from pathlib import Path

def create_env_template():
    """Create a .env.template file"""
    template = """# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
TARGET_CHANNEL_ID=your-channel-id-here

# Google Sheets Configuration
GOOGLE_CREDENTIALS_PATH=path/to/your/credentials.json
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id-here

# Server Configuration
PORT=3000
FLASK_ENV=development
"""
    
    with open('.env.template', 'w') as f:
        f.write(template)
    print("✅ Created .env.template file")

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'SLACK_BOT_TOKEN',
        'SLACK_SIGNING_SECRET', 
        'GOOGLE_CREDENTIALS_PATH',
        'GOOGLE_SPREADSHEET_ID',
        'TARGET_CHANNEL_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def validate_google_credentials():
    """Validate Google credentials file exists and is valid JSON"""
    creds_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
    if not creds_path:
        print("❌ GOOGLE_CREDENTIALS_PATH not set")
        return False
    
    if not os.path.exists(creds_path):
        print(f"❌ Google credentials file not found: {creds_path}")
        return False
    
    try:
        with open(creds_path, 'r') as f:
            json.load(f)
        print("✅ Google credentials file is valid JSON")
        return True
    except json.JSONDecodeError:
        print("❌ Google credentials file is not valid JSON")
        return False

def main():
    """Main setup function"""
    print("🚀 Fix Kar Slack Bot - Environment Setup")
    print("=" * 50)
    
    # Create template if it doesn't exist
    if not os.path.exists('.env.template'):
        create_env_template()
        print("\n📝 Please copy .env.template to .env and fill in your values")
        return
    
    # Check environment
    print("\n🔍 Checking environment variables...")
    env_ok = check_environment()
    
    if env_ok:
        print("\n🔍 Validating Google credentials...")
        creds_ok = validate_google_credentials()
        
        if creds_ok:
            print("\n✅ Environment is ready for deployment!")
            print("\n📋 Next steps:")
            print("1. Push to GitHub: git push origin main")
            print("2. Deploy to Heroku/Render (see DEPLOYMENT.md)")
            print("3. Update Slack webhook URLs")
            print("4. Test the deployment")
        else:
            print("\n❌ Please fix Google credentials before deploying")
    else:
        print("\n❌ Please set all required environment variables before deploying")

if __name__ == "__main__":
    main() 