# 🚀 Deployment Guide for Fix Kar Slack Bot

## 📋 Pre-Deployment Checklist

### ✅ Local Testing
- [ ] Bot creates tickets correctly
- [ ] Modal opens and closes without errors
- [ ] Google Sheets integration works
- [ ] Thread replies are working
- [ ] All environment variables are set

### ✅ Code Changes Made
- [ ] `wsgi.py` - Production entry point
- [ ] `Procfile` - Heroku deployment
- [ ] `runtime.txt` - Python version
- [ ] Health check endpoint added
- [ ] Global error handling added

## 🌐 Deployment Options

### Option 1: Heroku (Recommended)

#### Step 1: Install Heroku CLI
```bash
# macOS
brew install heroku/brew/heroku

# Windows
# Download from https://devcenter.heroku.com/articles/heroku-cli
```

#### Step 2: Login to Heroku
```bash
heroku login
```

#### Step 3: Create Heroku App
```bash
heroku create your-app-name
```

#### Step 4: Set Environment Variables
```bash
heroku config:set SLACK_BOT_TOKEN=xoxb-your-token
heroku config:set SLACK_SIGNING_SECRET=your-signing-secret
heroku config:set GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
heroku config:set GOOGLE_SPREADSHEET_ID=your-sheet-id
heroku config:set TARGET_CHANNEL_ID=your-channel-id
```

#### Step 5: Upload Google Credentials
```bash
# Create a temporary file with your credentials
echo '{"type": "service_account", ...}' > credentials.json
heroku config:set GOOGLE_CREDENTIALS="$(cat credentials.json)"
rm credentials.json
```

#### Step 6: Deploy
```bash
git add .
git commit -m "Ready for production deployment"
git push heroku main
```

#### Step 7: Check Logs
```bash
heroku logs --tail
```

### Option 2: Render

#### Step 1: Connect GitHub
1. Go to [render.com](https://render.com)
2. Connect your GitHub account
3. Select this repository

#### Step 2: Create Web Service
1. Click "New Web Service"
2. Select your repository
3. Configure:
   - **Name**: `fix-kar-slack-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`

#### Step 3: Set Environment Variables
Add these in Render dashboard:
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `GOOGLE_CREDENTIALS_PATH`
- `GOOGLE_SPREADSHEET_ID`
- `TARGET_CHANNEL_ID`

#### Step 4: Deploy
Click "Create Web Service" and wait for deployment.

## 🔧 Post-Deployment Steps

### 1. Update Slack App URLs
Go to your Slack App settings and update:
- **Event Subscriptions**: `https://your-app.herokuapp.com/slack/events`
- **Interactive Components**: `https://your-app.herokuapp.com/slack/interactive`
- **Slash Commands**: `https://your-app.herokuapp.com/slack/commands`

### 2. Test the Deployment
1. Visit `https://your-app.herokuapp.com/health`
2. Send a message in your Slack channel
3. Test modal functionality
4. Check Google Sheets for updates

### 3. Monitor the App
```bash
# Heroku
heroku logs --tail

# Render
# Check logs in dashboard
```

## 🔄 Local Development

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SLACK_BOT_TOKEN=xoxb-your-token
export SLACK_SIGNING_SECRET=your-secret
export GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
export GOOGLE_SPREADSHEET_ID=your-sheet-id
export TARGET_CHANNEL_ID=your-channel-id

# Run locally
python app.py
```

### Using ngrok for Local Development
```bash
# Install ngrok
brew install ngrok

# Start ngrok
ngrok http 3000

# Update Slack webhook URLs to ngrok URL
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Environment Variables Not Set
```bash
# Check Heroku config
heroku config

# Set missing variables
heroku config:set VARIABLE_NAME=value
```

#### 2. Google Sheets Access
- Ensure service account has access to the spreadsheet
- Check if credentials are properly uploaded

#### 3. Slack Webhook Errors
- Verify webhook URLs are correct
- Check if app has required permissions
- Ensure signing secret is correct

#### 4. App Not Starting
```bash
# Check logs
heroku logs --tail

# Common fixes:
# - Ensure gunicorn is in requirements.txt
# - Check Procfile syntax
# - Verify Python version in runtime.txt
```

## 📊 Monitoring

### Health Check Endpoint
- **URL**: `https://your-app.herokuapp.com/health`
- **Purpose**: Monitor app status and environment variables

### Logs
```bash
# Heroku
heroku logs --tail

# Render
# Available in dashboard
```

## 🔒 Security Notes

1. **Never commit sensitive data** to Git
2. **Use environment variables** for all secrets
3. **Enable HTTPS** in production
4. **Monitor logs** for suspicious activity
5. **Regularly rotate** Slack tokens if needed

## 💰 Cost Considerations

- **Heroku**: Free tier available, $7/month for custom domain
- **Render**: Free tier available, $7/month for custom domain
- **AWS**: ~$10-20/month for small instance
- **Google Cloud**: Pay per use, usually $5-15/month

## 🎯 Success Criteria

After deployment, verify:
- [ ] Health check returns 200
- [ ] Bot responds to messages
- [ ] Modals open and close correctly
- [ ] Google Sheets are updated
- [ ] Thread replies work
- [ ] No errors in logs 