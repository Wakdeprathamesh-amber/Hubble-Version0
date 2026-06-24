# 🔧 Bot Troubleshooting Guide

## 🚨 **Issue: Bot is in channel but not responding**

### **✅ Current Status Check:**
- ✅ Bot authentication working
- ✅ Flask app running on port 3000
- ✅ Ngrok URL: `https://fdee3b53d981.ngrok-free.app` (ALREADY RUNNING)

### **🔧 Step-by-Step Fix:**

#### **1. Update Slack App Event Subscriptions**

Go to your Slack App settings and update the Event Subscriptions:

1. **Visit**: https://api.slack.com/apps
2. **Select your app**: "Hubble" (or your app name)
3. **Go to**: Event Subscriptions
4. **Update Request URL** (if not already set):
   ```
   https://fdee3b53d981.ngrok-free.app/slack/events
   ```
5. **Subscribe to bot events**:
   - ✅ `message.channels`
   - ✅ `message.groups` 
   - ✅ `message.im`
   - ✅ `message.mpim`

#### **2. Verify Bot Permissions**

In your Slack App settings, go to "OAuth & Permissions":

**Required Bot Token Scopes:**
- ✅ `channels:read`
- ✅ `channels:history`
- ✅ `chat:write`
- ✅ `users:read`
- ✅ `commands`
- ✅ `groups:history`
- ✅ `im:history`
- ✅ `mpim:history`
- ✅ `reactions:read`
- ✅ `reactions:write`
- ✅ `users:read.email`
- ✅ `groups:read`

#### **3. Reinstall App to Workspace**

1. Go to your Slack App settings
2. Click "Install App" or "Reinstall App"
3. Grant all permissions
4. The bot should now have proper permissions

#### **4. Test Bot Commands**

Try these slash commands in any channel:
```
/ticket-status
/update-ticket
/assign-ticket
```

#### **5. Test Message Events**

Send a message in any channel where the bot is present:
```
Hello, this is a test message
```

The bot should respond with a ticket creation message.

### **🔍 Debug Steps:**

#### **Check App Logs:**
```bash
# Look for these log messages when you send a message:
🎫 CREATING TICKET: Channel=C08VB634J86, User=U08S2KRG2F9
✅ Ticket #123 created successfully in channel C08VB634J86
```

#### **Check Slack App Activity:**
1. Go to your Slack App settings
2. Click "Event Subscriptions"
3. Look for "Recent activity" section
4. Check if events are being received

#### **Test Event URL:**
```bash
curl -X POST https://fdee3b53d981.ngrok-free.app/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'
```

### **🚨 Common Issues:**

#### **Issue 1: "Request URL verification failed"**
- **Fix**: Make sure ngrok URL is correct and app is running
- **Check**: `https://fdee3b53d981.ngrok-free.app/slack/events`

#### **Issue 2: "Bot not responding to messages"**
- **Fix**: Check Event Subscriptions are enabled
- **Check**: `message.channels` is subscribed

#### **Issue 3: "Bot can't post messages"**
- **Fix**: Add `chat:write` permission
- **Check**: Reinstall app to workspace

#### **Issue 4: "Bot not in channel"**
- **Fix**: Invite bot to channel: `/invite @fix_kar`
- **Check**: Bot appears in channel member list

### **✅ Verification Checklist:**

- [ ] Ngrok running: `https://fdee3b53d981.ngrok-free.app`
- [ ] Flask app running on port 3000
- [ ] Event Subscriptions URL updated
- [ ] Bot events subscribed
- [ ] App reinstalled to workspace
- [ ] Bot invited to channel
- [ ] Bot permissions granted
- [ ] Test message sent in channel

### **🎯 Quick Test:**

1. **Send this message** in any channel where bot is present:
   ```
   Test ticket creation
   ```

2. **Expected response**:
   ```
   🎫 Ticket #123 has been created
   
   Hubble has logged your ticket.
   We've recorded the details and notified the relevant team.
   ```

3. **If no response**, check the troubleshooting steps above.

### **📞 Still Not Working?**

If the bot still doesn't respond after following all steps:

1. **Check app logs** for error messages
2. **Verify ngrok URL** is accessible
3. **Test with a simple message** first
4. **Try in a different channel**
5. **Restart the Flask app**

**Current ngrok URL**: `https://fdee3b53d981.ngrok-free.app` ✅ (ALREADY RUNNING)
**Event Subscriptions URL**: `https://fdee3b53d981.ngrok-free.app/slack/events` 