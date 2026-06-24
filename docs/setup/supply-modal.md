# Supply Channel Modal Template Setup

## Instructions

Add the following rows to your **Modal Templates** sheet in Google Sheets for the `supply` template key.

## Sheet Structure
- **Column A**: Template Key
- **Column B**: Field ID
- **Column C**: Field Label
- **Column D**: Field Type (user_select, select, text, textarea, date)
- **Column E**: Required (Yes/No)
- **Column F**: Options (CSV for select fields, empty for others)
- **Column G**: Order (1, 2, 3, etc.)

## Rows to Add

| Template Key | Field ID | Field Label | Field Type | Required | Options | Order |
|-------------|----------|-------------|------------|----------|---------|-------|
| supply | requester | Requester | user_select | Yes | | 1 |
| supply | assignee | Assignee | user_select | No | | 2 |
| supply | priority | Priority | select | No | CRITICAL,HIGH,MEDIUM,LOW | 3 |
| supply | status | Status | select | Yes | Open,Closed | 4 |
| supply | supply_country | Supply Country | text | No | | 5 |
| supply | supply_city | Supply City | text | No | | 6 |
| supply | description | Description | textarea | Yes | | 7 |
| supply | category | Category (Supply) | text | No | | 8 |
| supply | pmg | PMG | text | No | | 9 |

## Field Details

1. **Requester** (user_select, Required, Order 1)
   - Field ID: `requester`
   - Pre-filled with ticket creator

2. **Assignee** (user_select, Optional, Order 2)
   - Field ID: `assignee`
   - Shows "Unassigned" if not set

3. **Priority** (select, Optional, Order 3)
   - Field ID: `priority`
   - Options: CRITICAL, HIGH, MEDIUM, LOW

4. **Status** (select, Required, Order 4)
   - Field ID: `status`
   - Options: Open, Closed
   - Default: Open

5. **Supply Country** (text, Optional, Order 5)
   - Field ID: `supply_country`

6. **Supply City** (text, Optional, Order 6)
   - Field ID: `supply_city`

7. **Description** (textarea, Required, Order 7)
   - Field ID: `description`

8. **Category (Supply)** (text, Optional, Order 8)
   - Field ID: `category`

9. **PMG** (text, Optional, Order 9)
   - Field ID: `pmg`

## Notes

- **Modal Title**: The code has been updated to show "Form: Supply Team - Edit #XX" or "Form: Supply Team - View #XX" in the modal title for supply template.
- **Channel Display**: A context block showing "Channel: supply" will appear at the top of the modal.
- **Config Sheet**: Make sure the Config sheet has `modal_template_key` set to `supply` for the supply channel.
- After adding these rows to the Modal Templates sheet, the modal will automatically use this template when viewing/editing tickets from the supply channel.

## Quick Setup Steps

1. Open your Google Sheet
2. Go to the **Modal Templates** sheet
3. Add the 9 rows from the CSV file (or copy from the table above)
4. Make sure your **Config** sheet has the supply channel configured with `modal_template_key = supply`
5. The modal will now show:
   - Title: "Form: Supply Team - Edit #XX"
   - Context: "Channel: supply"
   - Fields in the order specified above

