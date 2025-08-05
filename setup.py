#!/usr/bin/env python3
"""
Setup script for Fix Kar Slack Bot
This script helps configure environment variables and test the application
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create a .env file with placeholder values"""
    env_content = """# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
TARGET_CHANNEL_ID=C1234567890

# Google Sheets Configuration
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id-here

# Server Configuration (optional)
PORT=3000
"""
    
    env_path = Path('.env')
    if env_path.exists():
        print("⚠️  .env file already exists")
        return False
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file with placeholder values")
    print("📝 Please edit .env file with your actual credentials:")
    print("   - SLACK_BOT_TOKEN: Get from https://api.slack.com/apps")
    print("   - SLACK_SIGNING_SECRET: Get from your Slack app settings")
    print("   - TARGET_CHANNEL_ID: Right-click channel → Copy link → extract ID")
    print("   - GOOGLE_CREDENTIALS_PATH: Path to your service account JSON file")
    print("   - GOOGLE_SPREADSHEET_ID: From your Google Sheets URL")
    return True

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = [
        'flask',
        'slack-bolt',
        'python-dotenv',
        'requests',
        'google-auth',
        'google-api-python-client'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print("✅ All dependencies are installed")
        return True

def check_env_vars():
    """Check if environment variables are set"""
    required_vars = [
        'SLACK_BOT_TOKEN',
        'SLACK_SIGNING_SECRET',
        'TARGET_CHANNEL_ID',
        'GOOGLE_CREDENTIALS_PATH',
        'GOOGLE_SPREADSHEET_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment")
        return False
    else:
        print("✅ All environment variables are set")
        return True

def main():
    """Main setup function"""
    print("🔧 Fix Kar Slack Bot Setup")
    print("=" * 40)
    
    # Check dependencies
    print("\n1. Checking dependencies...")
    deps_ok = check_dependencies()
    
    # Create .env file if it doesn't exist
    print("\n2. Checking environment configuration...")
    if not Path('.env').exists():
        create_env_file()
    else:
        print("✅ .env file exists")
    
    # Check environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        env_ok = check_env_vars()
    except ImportError:
        print("⚠️  python-dotenv not available, checking system environment")
        env_ok = check_env_vars()
    
    print("\n3. Setup Summary:")
    if deps_ok and env_ok:
        print("✅ Setup complete! You can now run the application.")
        print("\nTo start the application:")
        print("   python app.py")
        print("\nTo test with ngrok:")
        print("   ngrok http 3000")
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Configure .env file with your credentials")
        print("3. Run the application: python app.py")

if __name__ == "__main__":
    main() 