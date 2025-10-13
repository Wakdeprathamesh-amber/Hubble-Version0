# Bi-Directional Thread Synchronization

## Overview
This feature enables seamless communication between main channels and internal channels through thread synchronization. Team members can reply in either channel, and their responses will automatically appear in both threads.

## Complete Flow

### 1. Ticket Creation
```
User posts in #support
  ↓
Bot creates ticket in Google Sheets
  ↓
Bot posts confirmation in #support thread with buttons
  ↓
Bot mirrors ticket to #support-internal
  ↓
Bot stores internal_message_ts in Google Sheets
```

### 2. Internal Team Replies (NEW)
```
Team member views ticket in #support-internal
  ↓
Team member replies in thread
  ↓
Bot detects reply in internal channel thread
  ↓
Bot matches thread_ts to internal_message_ts
  ↓
Bot forwards reply to #support thread
  ↓
Original requester sees the response
```

### 3. Main Channel Replies (NEW)
```
User or admin replies in #support thread
  ↓
Bot detects reply in main channel thread
  ↓
Bot looks up internal_channel_id and internal_message_ts
  ↓
Bot forwards reply to #support-internal thread
  ↓
Internal team sees the response
```

## Technical Implementation

### Key Files Modified
- `slack_handler.py`: Lines 192-250 (Internal → Main), Lines 438-465 (Main → Internal)

### Data Flow
1. **Ticket Storage**: `internal_message_ts` stored in Google Sheets (Column N)
2. **Thread Matching**: Uses `internal_message_ts` == `thread_ts` for matching
3. **User Attribution**: Fetches user's real name for clear identification
4. **Message Format**: 
   - `💬 **User Name** (from internal team): [message]`
   - `💬 **User Name** (from main channel): [message]`

### Edge Cases Handled
- ✅ Bot messages ignored (prevents loops)
- ✅ Message subtypes ignored (edits, joins, etc.)
- ✅ Missing thread_ts handled gracefully
- ✅ Channel config lookup failures handled
- ✅ User name lookup failures default to "Unknown"

## Testing Checklist

### Before Testing
- [ ] Bot is added to both main channel and internal channel
- [ ] Config sheet has internal_channel_id set correctly
- [ ] Admin user IDs configured

### Test Scenarios

#### Scenario 1: Internal Team Reply
1. Create ticket in main channel
2. Verify ticket appears in internal channel
3. Reply in internal channel thread
4. **Expected**: Reply appears in main channel thread with "(from internal team)" label

#### Scenario 2: Main Channel Reply  
1. Create ticket in main channel
2. Reply in main channel thread (as admin or requester)
3. **Expected**: Reply appears in internal channel thread with "(from main channel)" label

#### Scenario 3: Multiple Replies
1. Create ticket
2. Internal team member replies
3. User replies in main channel
4. Another internal team member replies
5. **Expected**: All messages flow correctly to both channels

#### Scenario 4: Button Actions Still Work
1. Create ticket
2. Test "View & Edit" button in both channels
3. Test "Assign to Me" in internal channel
4. Test "Change Status" in internal channel
5. Test "Close Ticket" in main channel
6. **Expected**: All buttons work, updates reflected in both channels

## Benefits

1. **Seamless Communication**: Internal team can respond without switching channels
2. **Complete Context**: All replies visible in both threads
3. **User Experience**: Customers see responses immediately
4. **Team Efficiency**: Internal discussions kept separate while responses flow through

## Configuration

No additional configuration needed! If an internal channel is configured in the Config sheet, thread sync automatically works.

## Logging

Minimal logging for production:
- ✅ Thread reply detected
- ✅ Ticket matched
- ✅ Reply forwarded successfully
- ❌ Errors only when something fails

