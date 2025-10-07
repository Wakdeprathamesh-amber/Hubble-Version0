# 📊 Internal Channels Setup Guide

## 🎯 What Are Internal Channels?

Internal channels are **backend visualization channels** where team members can see all tickets from a main channel in one place, with beautiful formatted cards and quick action buttons.

### **Purpose:**
- **Visualization** - See all tickets at a glance
- **Quick Actions** - View/Edit, Assign, Change Status without going to threads
- **Team Workspace** - Dedicated channel for ticket management

---

## 🏗️ Architecture

```
#product-tech-suggestions (Main Channel)
├── User posts message → Creates ticket
└── Bot replies in thread with ticket details

#product-tech-suggestions-internal (Internal Channel)
└── Bot posts formatted ticket card with:
    ✅/🔵 Status | Priority | Requester | Assignee
    Created & Updated timestamps
    Full description
    All custom fields
    [View/Edit] [Assign to Me] [Change Status] buttons
```

---

## 📋 Setup Instructions

### **Step 1: Create Internal Channel in Slack**

1. Create a new Slack channel (private recommended)
   ```
   Example: #product-tech-suggestions-internal
   ```

2. Invite your bot to the internal channel
   ```
   /invite @your-bot-name
   ```

3. Invite team members who should see/manage tickets

4. Copy the **Channel ID**:
   - Right-click on channel name → View channel details
   - Scroll down, copy the Channel ID (e.g., `C09INTERNAL123`)

---

### **Step 2: Update Google Sheets Config Tab**

Open your Google Sheets and go to the **Config** tab:

#### **Add Column G: Internal Channel ID**

| A: Channel ID | B: Channel Name | C: Admin User IDs | D: Default Assignee | E: Priorities | F: Modal Template Key | **G: Internal Channel ID** |
|---|---|---|---|---|---|---|
| C08VB634J86 | product-tech-suggestions | U123,U456 | @Shreyas | CRITICAL,HIGH,MEDIUM,LOW | tech_default | **C09INTERNAL123** |

**Example:**
```
Main Channel: C08VB634J86 → Internal Channel: C09INTERNAL123
Main Channel: C06RCHXHQ5V → Internal Channel: C09INTERNAL456
```

---

### **Step 3: Update Main Tickets Sheet**

The sheet will automatically add a new column: **Column N: Internal Message TS**

This column stores the message timestamp for updating messages later.

**Expected Headers (14 columns):**
```
A: Ticket ID
B: Thread Link
C: Requester
D: Status
E: Priority
F: Assignee
G: Thread Created At TS
H: First Response Time
I: Resolved At
J: Message
K: Channel ID
L: Channel Name
M: Custom Fields (JSON)
N: Internal Message TS  ← NEW!
```

---

### **Step 4: Deploy & Test**

1. **Restart your bot** (if running locally):
   ```bash
   python app.py
   ```

2. **Or redeploy** (if on Heroku):
   ```bash
   git add .
   git commit -m "Add internal channel feature"
   git push heroku main
   ```

3. **Create a test ticket**:
   - Post a message in your main channel
   - Bot should:
     ✅ Reply in thread (as before)
     ✅ Post formatted card to internal channel (NEW!)

---

## 🎨 Ticket Card Format

Each ticket appears in the internal channel as a rich message card:

```
┌─────────────────────────────────────┐
│  Ticket #123                        │
├─────────────────────────────────────┤
│ Status: 🔵 Open | Priority: HIGH 🔸│
│                                     │
│ Requested by: @User in #channel     │
│ (view - link to original thread)   │
│                                     │
│ Assignee: @TeamMember               │
│                                     │
│ Created: September 25th 1:40 PM     │
│ Changed: Today 12:23 PM             │
│                                     │
│ Description:                        │
│ [Full ticket description...]        │
│                                     │
│ Custom Field 1: Value               │
│ Custom Field 2: Value               │
├─────────────────────────────────────┤
│ [🔍 View/Edit] [👤 Assign to Me]   │
│ [🔄 Change Status]                  │
└─────────────────────────────────────┘
```

---

## 🔘 Button Actions

### **1. 🔍 View/Edit**
- Opens the same modal as in main channel
- Shows all fields with current values
- Anyone in internal channel can use this

### **2. 👤 Assign to Me**
- Quick self-assignment
- Updates ticket assignee to the user who clicked
- Updates internal channel card AND posts to original thread
- No modal needed!

### **3. 🔄 Change Status**
- Toggles between Open ↔ Closed
- Updates status instantly
- Updates internal channel card AND posts to original thread
- No modal needed!

---

## 🔄 Update Behavior

### **When Ticket is Updated:**
- Via modal (View/Edit) from main OR internal channel
- Via "Assign to Me" button
- Via "Change Status" button
- Via "Close Ticket" button in main channel

**What Happens:**
1. ✅ Google Sheet updated
2. ✅ Original thread receives update message
3. ✅ Internal channel card updated IN-PLACE (same message)

**Note:** Messages are updated, not reposted. The internal channel always shows the current state of all tickets.

---

## 📊 Key Features

### **✅ What Works:**

1. **Automatic Posting** - New tickets automatically appear in internal channel
2. **Real-time Updates** - Changes reflected immediately in internal channel
3. **All Ticket Types** - Shows both Open and Closed tickets
4. **Chronological Order** - Newest tickets at bottom (natural chat order)
5. **Rich Formatting** - Status emojis, priority colors, clickable links
6. **Custom Fields** - All modal fields displayed
7. **Quick Actions** - Three action buttons for fast ticket management
8. **Bidirectional Updates** - Actions in internal channel update main thread
9. **No Permissions Needed** - Anyone in internal channel can use buttons
10. **Forward-Only** - Only new tickets (after deployment) are posted

### **❌ What Doesn't Happen:**

1. **No ticket creation** from internal channel messages
2. **No historical tickets** - Only tickets created after setup
3. **No deletion** - Closed tickets stay visible (just show as ✅ Closed)

---

## 🧪 Testing Checklist

- [ ] Create internal channel
- [ ] Add bot to internal channel
- [ ] Update Config sheet with internal channel ID
- [ ] Restart/redeploy bot
- [ ] Create test ticket in main channel
- [ ] Verify ticket appears in internal channel
- [ ] Click "View/Edit" - modal should open
- [ ] Click "Assign to Me" - should assign and update
- [ ] Click "Change Status" - should toggle Open/Closed
- [ ] Edit ticket via modal - internal channel should update
- [ ] Close ticket from main channel - internal channel should update

---

## 🎉 Example Configuration

### **For Multiple Channels:**

**Config Sheet:**
| Channel ID | Channel Name | Admin User IDs | Default Assignee | Priorities | Modal Template Key | Internal Channel ID |
|---|---|---|---|---|---|---|
| C08VB634J86 | product-tech-suggestions | U123,U456 | @Shreyas | CRITICAL,HIGH,MEDIUM,LOW | tech_default | C09INTERNAL001 |
| C06RCHXHQ5V | customer-support | U789,U012 | @Support | URGENT,HIGH,MEDIUM,LOW | support_template | C09INTERNAL002 |
| C07ABC12345 | design-requests | U345,U678 | @Designer | HIGH,MEDIUM,LOW | design_template | C09INTERNAL003 |

**Slack Channels:**
```
#product-tech-suggestions      → #product-tech-suggestions-internal
#customer-support              → #customer-support-internal
#design-requests               → #design-requests-internal
```

---

## 🆘 Troubleshooting

### **Ticket not appearing in internal channel?**
- Check Config sheet has correct internal channel ID in column G
- Verify bot is invited to internal channel
- Check logs for errors: `📊 Posting ticket #X to internal channel`

### **Buttons not working?**
- Make sure bot has permissions in internal channel
- Check logs for action handler errors
- Verify internal_message_ts is stored in sheet (Column N)

### **Updates not reflecting?**
- Check that internal_message_ts exists for the ticket
- Verify Config sheet has correct channel mapping
- Check logs for update errors

### **Historical tickets not showing?**
- This is expected! Only tickets created AFTER setup appear
- To backfill, you'd need to manually re-create them (not recommended)

---

## 📝 Notes

- **Privacy**: Internal channels are typically private - only invite team members
- **Performance**: No impact on main channel users - they don't see internal channel
- **Scalability**: Works with unlimited tickets - Slack handles pagination
- **Maintenance**: No ongoing maintenance needed once set up

---

## 🚀 You're Done!

Your internal channel is now set up! Team members can:
- See all tickets at a glance
- Take quick actions with buttons
- No need to scroll through threads
- Perfect for ticket triage and management

**Enjoy your new ticket visualization system!** 🎉

