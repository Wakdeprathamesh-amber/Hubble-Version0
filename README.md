# Fix Kar Slack Bot

A Slack bot that creates tickets from messages in a specific channel.

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- A Slack workspace with permission to add apps
- Slack app with appropriate permissions

### Slack App Configuration

1. Create a new Slack app at https://api.slack.com/apps
2. Add the following Bot Token Scopes under "OAuth & Permissions":
   - `chat:write`
   - `channels:history` (or `groups:history` for private channels)
   - `app_mentions:read`

3. Enable Event Subscriptions and subscribe to the `message.channels` event
4. Install the app to your workspace

### Environment Setup

1. Clone this repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file in the root directory with the following variables:

```bash
# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
TARGET_CHANNEL_ID=C1234567890

# Google Sheets Configuration
GOOGLE_CREDENTIALS_PATH=credentials.json
GOOGLE_SPREADSHEET_ID=your-spreadsheet-id-here

# Server Configuration (optional)
PORT=3000
```

**Required Environment Variables:**
- `SLACK_BOT_TOKEN`: Your Slack bot token (starts with `xoxb-`)
- `SLACK_SIGNING_SECRET`: Your Slack app signing secret
- `TARGET_CHANNEL_ID`: The channel ID where tickets should be created from
- `GOOGLE_CREDENTIALS_PATH`: Path to your Google service account credentials JSON file
- `GOOGLE_SPREADSHEET_ID`: The ID of your Google Spreadsheet for ticket tracking

### Running the Application

```bash
python app.py
```

## 🚀 Deployment

### Environment Setup Helper
Run the setup script to check your environment:
```bash
python setup_env.py
```

### Quick Deployment Options

#### Option 1: Heroku
```bash
# Install Heroku CLI
brew install heroku/brew/heroku

# Login and create app
heroku login
heroku create your-app-name

# Set environment variables
heroku config:set SLACK_BOT_TOKEN=xoxb-your-token
heroku config:set SLACK_SIGNING_SECRET=your-secret
heroku config:set GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
heroku config:set GOOGLE_SPREADSHEET_ID=your-sheet-id
heroku config:set TARGET_CHANNEL_ID=your-channel-id

# Deploy
git push heroku main
```

#### Option 2: Render
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set environment variables in the dashboard
4. Deploy automatically

### Monitoring
- **Health Check**: `https://your-app.herokuapp.com/health`
- **Home Page**: `https://your-app.herokuapp.com/`
- **Logs**: `heroku logs --tail`

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).