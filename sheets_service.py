from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import os
from typing import Dict, List, Optional

class SheetsService:
    """
    A service class for interacting with Google Sheets for ticket management.
    
    This class provides methods for:
    - Creating and managing tickets
    - Updating ticket status
    - Retrieving ticket information
    - Cleaning up test data
    
    The sheet structure is:
    - Column A: Ticket ID
    - Column B: Thread Link
    - Column C: Requester
    - Column D: Status
    - Column E: Priority
    - Column F: Assignee
    - Column G: Thread Created At TS
    - Column H: First Response Time
    - Column I: Resolved At
    - Column J: Message
    """
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """
        Initialize the Google Sheets service.
        
        Args:
            credentials_path (str): Path to the service account credentials JSON file or JSON content
            spreadsheet_id (str): ID of the Google Spreadsheet to use
        """
        self.spreadsheet_id = spreadsheet_id
        
        # Handle credentials from file or environment variable
        if os.path.exists(credentials_path):
            # Load from file (local development)
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
        else:
            # Load from environment variable (production)
            import json
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            if not credentials_json:
                raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
            
            credentials_info = json.loads(credentials_json)
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
        self.service = build('sheets', 'v4', credentials=self.credentials)
        self.sheet = self.service.spreadsheets()
        
        # Get the sheet name from the spreadsheet
        try:
            spreadsheet = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = spreadsheet.get('sheets', [])
            if sheets:
                # Use the first sheet's title
                self.sheet_name = sheets[0]['properties']['title']
                print(f"Using sheet: {self.sheet_name}")
            else:
                self.sheet_name = "Sheet1"
                print("No sheets found, defaulting to Sheet1")
        except Exception as e:
            print(f"Error getting sheet name: {str(e)}")
            self.sheet_name = "Sheet1"
        
        # Ensure headers are set up correctly
        self._setup_headers()
    
    def _setup_headers(self):
        """Set up the headers in the sheet if they don't exist."""
        try:
            # Get current headers
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A1:M1'
            ).execute()
            
            values = result.get('values', [])
            
            # Only setup headers if the sheet is COMPLETELY EMPTY (no first column at all)
            # Check if first cell is empty or doesn't say "Ticket ID"
            should_setup = False
            
            if not values:
                # Sheet is completely empty
                should_setup = True
                print("⚠️ Sheet has no headers. Setting up new headers...")
            elif not values[0] or len(values[0]) == 0:
                # First row exists but is empty
                should_setup = True
                print("⚠️ Sheet header row is empty. Setting up new headers...")
            elif values[0][0].strip() != 'Ticket ID':
                # First column doesn't say "Ticket ID"
                print("⚠️ WARNING: First column is not 'Ticket ID', but preserving existing data")
                should_setup = False
            else:
                # Headers exist and first column is correct
                print(f"✅ Headers found: {len(values[0])} columns")
                
                # If we have fewer than 14 columns, ADD missing columns without clearing data
                if len(values[0]) < 14:
                    print(f"⚠️ Adding missing header columns (found {len(values[0])}, need 14)")
                    
                    expected_headers = [
                        'Ticket ID',
                        'Thread Link',
                        'Requester',
                        'Status',
                        'Priority',
                        'Assignee',
                        'Thread Created At TS',
                        'First Response Time',
                        'Resolved At',
                        'Message',
                        'Channel ID',
                        'Channel Name',
                        'Custom Fields (JSON)',
                        'Internal Message TS'
                    ]
                    
                    # Extend existing headers with missing ones
                    current_headers = values[0]
                    missing_headers = expected_headers[len(current_headers):]
                    updated_headers = current_headers + missing_headers
                    
                    body = {'values': [updated_headers]}
                    
                    # Update ONLY the header row, don't touch data
                    self.sheet.values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f'{self.sheet_name}!A1:N1',
                        valueInputOption='RAW',
                        body=body
                    ).execute()
                    print(f"✅ Added {len(missing_headers)} missing header columns")
                
                should_setup = False
            
            if should_setup:
                headers = [
                    'Ticket ID',
                    'Thread Link',
                    'Requester',
                    'Status',
                    'Priority',
                    'Assignee',
                    'Thread Created At TS',
                    'First Response Time',
                    'Resolved At',
                    'Message',
                    'Channel ID',
                    'Channel Name',
                    'Custom Fields (JSON)',
                    'Internal Message TS'
                ]
                
                body = {
                    'values': [headers]
                }
                
                # Only clear the HEADER ROW, not all data
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f'{self.sheet_name}!A1:N1',
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                print("✅ Headers set up successfully")
        except Exception as e:
            print(f"❌ Error setting up headers: {str(e)}")
            # Don't raise - allow app to continue even if header setup fails
            pass

    def append_ticket(self, ticket_data: Dict) -> bool:
        """
        Append a new ticket to the spreadsheet, checking for duplicates first.
        
        Args:
            ticket_data (Dict): Dictionary containing ticket information
            
        Returns:
            bool: True if ticket was created successfully, False if duplicate found
        """
        # Check if ticket already exists
        existing_tickets = self.get_tickets()
        for ticket in existing_tickets:
            if ticket['ticket_id'] == ticket_data['ticket_id']:
                print(f"⚠️ Ticket {ticket_data['ticket_id']} already exists. Skipping creation.")
                return False
        
        # Format the ticket data for the sheet
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create thread link
        workspace_id = "T1K9VHPT7"  # Your workspace ID
        channel_id = ticket_data.get('channel_id', '')
        thread_ts = ticket_data.get('thread_ts', '')
        thread_link = f"https://amberstudent.slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}" if thread_ts else ""
        
        # Get default assignee based on channel
        default_assignee = self._get_default_assignee(channel_id)
        
        # Get channel name from Config or fallback to channel_id
        channel_name = self._get_channel_name(channel_id)
        
        # Get custom fields as JSON
        import json
        custom_fields = ticket_data.get('custom_fields', {})
        custom_fields_json = json.dumps(custom_fields) if custom_fields else ''
        
        row = [
            ticket_data.get('ticket_id', ''),           # Ticket ID
            thread_link,                                 # Thread Link
            ticket_data.get('requester_name', ticket_data.get('created_by', '')),  # Requester (display name)
            ticket_data.get('status', 'Open'),          # Status
            ticket_data.get('priority', 'Medium'),      # Priority
            default_assignee,                           # Assignee (display name)
            current_time,                               # Thread Created At TS
            '',                                         # First Response Time (empty initially)
            '',                                         # Resolved At (empty initially)
            ticket_data.get('description', ''),         # Message
            ticket_data.get('channel_id', ''),          # Channel ID
            channel_name,                               # Channel Name
            custom_fields_json,                         # Custom Fields (JSON)
            ticket_data.get('internal_message_ts', '')  # Internal Message TS
        ]

        body = {
            'values': [row]
        }

        try:
            # Append the row to the sheet
            self.sheet.values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A:N',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            print(f"✅ Successfully added ticket {ticket_data['ticket_id']} to sheet")
            return True
        except Exception as e:
            print(f"Error appending ticket: {str(e)}")
            return False

    def get_channel_config_map(self) -> Dict[str, Dict[str, str]]:
        """
        Read per-channel configuration from a 'Config' sheet tab.
        Expected columns:
        A: Channel ID | B: Channel Name | C: Admin User IDs | D: Default Assignee | E: Priorities | F: Modal Template Key | G: Internal Channel ID

        Returns:
            Dict[channel_id, settings_dict]
        """
        try:
            # Try to read the Config tab; if missing, return empty
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Config!A2:G'
            ).execute()

            values = result.get('values', [])
            config_map: Dict[str, Dict[str, str]] = {}
            for row in values:
                row = row + [''] * (7 - len(row))  # Pad to 7 columns
                channel_id = row[0].strip()
                if not channel_id:
                    continue
                config_map[channel_id] = {
                    'channel_name': row[1].strip(),         # Column B
                    'admin_user_ids': row[2].strip(),       # Column C
                    'default_assignee': row[3].strip(),     # Column D
                    'priorities': row[4].strip(),           # Column E
                    'modal_template_key': row[5].strip(),   # Column F
                    'internal_channel_id': row[6].strip(),  # Column G
                }
            return config_map
        except Exception as e:
            print(f"Error reading Config tab: {str(e)}")
            return {}

    def _get_default_assignee(self, channel_id: str) -> str:
        """
        Get the default assignee based on the channel ID from Config sheet.
        
        Args:
            channel_id (str): The Slack channel ID
            
        Returns:
            str: The default assignee for the channel
        """
        try:
            cfg_map = self.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            assignee = cfg.get('default_assignee', '').strip()
            # Ensure @ prefix
            if assignee and not assignee.startswith('@'):
                assignee = f'@{assignee}'
            return assignee
        except Exception as e:
            print(f"Error getting default assignee from config: {str(e)}")
            return ''

    def _get_channel_name(self, channel_id: str) -> str:
        """
        Get the channel name from Config sheet.
        
        Args:
            channel_id (str): The Slack channel ID
            
        Returns:
            str: The channel name or channel_id if not found
        """
        try:
            cfg_map = self.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            return cfg.get('channel_name', channel_id)
        except Exception as e:
            print(f"Error getting channel name from config: {str(e)}")
            return channel_id

    def get_modal_template(self, template_key: str) -> List[Dict]:
        """
        Read modal field definitions from 'Modal Templates' sheet.
        Expected columns:
        A: Template Key | B: Field ID | C: Field Label | D: Field Type | E: Required | F: Options (CSV) | G: Order
        
        Args:
            template_key (str): The template key to look up
            
        Returns:
            List[Dict]: List of field definitions sorted by order
        """
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='Modal Templates!A2:G'
            ).execute()

            values = result.get('values', [])
            fields = []
            
            for row in values:
                row = row + [''] * (7 - len(row))  # Pad to 7 columns
                if row[0].strip() == template_key:
                    fields.append({
                        'field_id': row[1].strip(),
                        'field_label': row[2].strip(),
                        'field_type': row[3].strip(),
                        'required': row[4].strip().lower() == 'yes',
                        'options': row[5].strip(),
                        'order': int(row[6].strip()) if row[6].strip().isdigit() else 999
                    })
            
            # Sort by order
            fields.sort(key=lambda x: x['order'])
            return fields
        except Exception as e:
            print(f"Error reading modal template '{template_key}': {str(e)}")
            return []

    def get_tickets(self) -> List[Dict]:
        """
        Retrieve all tickets from the spreadsheet, handling duplicates by returning the most recent version.
        
        Returns:
            List[Dict]: List of ticket dictionaries
        """
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A2:N'  # Skip header row, include internal_message_ts column
            ).execute()

            values = result.get('values', [])
            ticket_dict = {}  # Use dict to handle duplicates

            for row in values:
                # Ensure row has all required fields, pad with empty strings if needed
                row = row + [''] * (14 - len(row))  # Pad row to have 14 columns
                
                if row[0]:  # Only process rows that have a ticket ID
                    ticket_id = row[0].strip()
                    
                    # Parse custom fields JSON
                    import json
                    custom_fields = {}
                    if row[12]:  # Column M: Custom Fields
                        try:
                            custom_fields = json.loads(row[12])
                        except Exception:
                            custom_fields = {}
                    
                    # Extract user IDs from custom_fields, fallback to display names for backwards compatibility
                    creator_id = custom_fields.get('requester_id', row[2])  # Use requester_id from custom_fields
                    assignee_id = custom_fields.get('assignee_id', row[5]) if row[5].startswith('U') else row[5]
                    
                    ticket = {
                        'ticket_id': ticket_id,
                        'thread_link': row[1],
                        'created_by': creator_id,  # User ID for permission checks
                        'requester_name': row[2],  # Display name for showing
                        'status': row[3],
                        'priority': row[4],
                        'assignee': row[5],  # Display name for showing
                        'assignee_id': assignee_id,  # User ID for permission checks
                        'created_at': row[6],
                        'first_response': row[7],
                        'resolved_at': row[8],
                        'message': row[9],
                        'channel_id': row[10],           # Channel ID
                        'channel_name': row[11],         # Channel Name
                        'internal_message_ts': row[13],  # Internal Message TS
                        **custom_fields  # Merge custom fields into ticket dict
                    }
                    # Keep the most recent version (last occurrence)
                    ticket_dict[ticket_id] = ticket

            return list(ticket_dict.values())
        except Exception as e:
            print(f"Error retrieving tickets: {str(e)}")
            return []

    def update_ticket_status(self, ticket_id: str, new_status: str, updated_at: str = None, resolved_at: str = None) -> bool:
        """
        Update the status of a specific ticket by finding and modifying the correct row.
        
        Args:
            ticket_id (str): ID of the ticket to update
            new_status (str): New status value (Open/Closed)
            updated_at (str): Timestamp for the update (optional)
            resolved_at (str): Timestamp for resolution (optional)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Validate status
            valid_statuses = ['Open', 'Closed']
            if new_status not in valid_statuses:
                print(f"❌ Invalid status: {new_status}. Must be one of {valid_statuses}")
                return False
            
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:K"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == ticket_id.strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for status update")
                return False

            # Update status and timestamps
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if new_status == 'Closed':
                resolved_at = current_time
            else:
                resolved_at = ''

            # Update only status (column D) and resolved_at (column I) without affecting other fields
            status_update_range = f"{self.sheet_name}!D{row_index}"
            resolved_update_range = f"{self.sheet_name}!I{row_index}"
            
            # Update status
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=status_update_range,
                valueInputOption="RAW",
                body={"values": [[new_status]]}
            ).execute()
            
            # Update resolved_at
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=resolved_update_range,
                valueInputOption="RAW",
                body={"values": [[resolved_at]]}
            ).execute()

            # Verify the update
            verify_result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!D{row_index}:I{row_index}"
            ).execute()

            verify_values = verify_result.get("values", [[]])
            if verify_values and verify_values[0][0] == new_status:
                print(f"✅ Successfully updated ticket {ticket_id} status to {new_status}")
                return True
            else:
                print(f"❌ Failed to verify update for ticket {ticket_id}")
                return False

        except Exception as e:
            print(f"❌ Error updating ticket status: {str(e)}")
            return False

    def update_ticket_assignee(self, ticket_id: str, assignee_id: str, user_id: str = None) -> bool:
        """
        Update the assignee of a specific ticket.
        
        Args:
            ticket_id (str): ID of the ticket to update
            assignee_id (str): Display name of the assignee (e.g., "@Prathamesh")
            user_id (str): Optional Slack user ID (e.g., "U08S2KRG2F9") to store in custom_fields
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:N"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None
            current_row = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == ticket_id.strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    current_row = row + [''] * (14 - len(row))  # Pad to 14 columns
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for assignee update")
                return False

            # Update assignee display name (Column F)
            update_range = f"{self.sheet_name}!F{row_index}"
            update_body = {
                "values": [[assignee_id]]
            }

            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body=update_body
            ).execute()

            # Also update custom_fields to include assignee_id if provided
            if user_id:
                import json
                # Get existing custom fields
                custom_fields_json = current_row[12] if len(current_row) > 12 else ''
                try:
                    custom_fields = json.loads(custom_fields_json) if custom_fields_json else {}
                except:
                    custom_fields = {}
                
                # Add/update assignee_id
                custom_fields['assignee_id'] = user_id
                
                # Save back to sheet
                custom_fields_range = f"{self.sheet_name}!M{row_index}"
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=custom_fields_range,
                    valueInputOption="RAW",
                    body={"values": [[json.dumps(custom_fields)]]}
                ).execute()
                print(f"✅ Stored assignee_id {user_id} in custom_fields")

            # Verify the update
            verify_result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!F{row_index}"
            ).execute()

            verify_values = verify_result.get('values', [])
            if verify_values and verify_values[0][0] == assignee_id:
                print(f"✅ Updated ticket {ticket_id} assignee to {assignee_id} at row {row_index}")
                return True
            else:
                print(f"❌ Assignee update verification failed")
                return False

        except Exception as e:
            print(f"❌ Error updating ticket assignee: {str(e)}")
            return False

    def update_ticket_priority(self, ticket_id: str, priority: str) -> bool:
        """
        Update the priority of a specific ticket.
        
        Args:
            ticket_id (str): ID of the ticket to update
            priority (str): New priority (CRITICAL/HIGH/MEDIUM/LOW)
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Validate priority
            valid_priorities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
            if priority.upper() not in valid_priorities:
                print(f"❌ Invalid priority: {priority}. Must be one of {valid_priorities}")
                return False
            
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:K"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == ticket_id.strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for priority update")
                return False

            # Update priority
            update_range = f"{self.sheet_name}!E{row_index}"
            update_body = {
                "values": [[priority.upper()]]
            }

            # Perform the update
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body=update_body
            ).execute()

            # Verify the update
            verify_result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!E{row_index}"
            ).execute()

            verify_values = verify_result.get('values', [])
            if verify_values and verify_values[0][0] == priority.upper():
                print(f"✅ Updated ticket {ticket_id} priority to {priority.upper()} at row {row_index}")
                return True
            else:
                print(f"❌ Priority update verification failed")
                return False

        except Exception as e:
            print(f"❌ Error updating ticket priority: {str(e)}")
            return False

    def cleanup_test_data(self, test_prefix: str = 'TEST-') -> bool:
        """
        Remove all test data from the sheet that starts with the given prefix.
        
        Args:
            test_prefix (str): The prefix to identify test tickets (default: 'TEST-')
            
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        try:
            # Get all rows
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A2:K'
            ).execute()
            
            values = result.get('values', [])
            rows_to_delete = []
            
            # Find rows with test tickets
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].startswith(test_prefix):
                    rows_to_delete.append(i + 2)  # +2 for header row and 1-based indexing
            
            if not rows_to_delete:
                print("No test data found to clean up")
                return True
            
            # Delete rows in reverse order to maintain correct indices
            for row_index in sorted(rows_to_delete, reverse=True):
                request = {
                    'requests': [{
                        'deleteDimension': {
                            'range': {
                                'sheetId': 0,  # Assuming Sheet1 is the first sheet
                                'dimension': 'ROWS',
                                'startIndex': row_index - 1,  # 0-based index
                                'endIndex': row_index  # exclusive
                            }
                        }
                    }]
                }
                
                self.sheet.batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=request
                ).execute()
            
            print(f"✅ Cleaned up {len(rows_to_delete)} test rows")
            return True
            
        except Exception as e:
            print(f"❌ Error cleaning up test data: {str(e)}")
            return False

    def update_ticket_first_response(self, ticket_id: str, response_text: str, responder_id: str) -> bool:
        """
        Update the first response of a specific ticket.
        
        Args:
            ticket_id (str): ID of the ticket to update
            response_text (str): The text of the first response
            responder_id (str): ID of the user who responded
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:K"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == ticket_id.strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for first response update")
                return False

            # Update first response and timestamp
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_range = f"{self.sheet_name}!H{row_index}"
            update_body = {
                "values": [[f"{current_time} - {responder_id}: {response_text}"]]
            }

            # Perform the update
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body=update_body
            ).execute()

            # Verify the update
            verify_result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!H{row_index}"
            ).execute()

            verify_values = verify_result.get('values', [])
            if verify_values and verify_values[0][0].startswith(current_time):
                print(f"✅ Updated ticket {ticket_id} with first response at row {row_index}")
                return True
            else:
                print(f"❌ First response update verification failed")
                return False

        except Exception as e:
            print(f"❌ Error updating ticket first response: {str(e)}")
            return False 

    def clear_all_data(self) -> bool:
        """
        Clear all data from the sheet and reset with new headers.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("🗑️ Clearing all data from the sheet...")
            
            # Clear all data
            self.sheet.values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A:K'
            ).execute()
            
            # Set up new headers
            headers = [
                'Ticket ID',
                'Thread Link',
                'Requester',
                'Status',
                'Priority',
                'Assignee',
                'Thread Created At TS',
                'First Response Time',
                'Resolved At',
                'Message',
                'Channel ID'
            ]
            
            body = {
                'values': [headers]
            }
            
            # Update with new headers
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f'{self.sheet_name}!A1:K1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print("✅ Sheet cleared and reset with new headers successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error clearing sheet data: {str(e)}")
            return False 

    def update_ticket_from_modal(self, ticket_id: str, requester: str, status: str, assignee: str, priority: str, description: str, custom_fields: Dict = None) -> bool:
        """
        Update ticket data from modal form.
        
        Args:
            ticket_id (str): ID of the ticket to update
            requester (str): New requester name
            status (str): New status
            assignee (str): New assignee name
            priority (str): New priority
            description (str): New description
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Ensure description is a string (not None)
            description = description or ""
            
            print(f"🔄 Updating ticket {ticket_id} from modal...")
            print(f"   Requester: {requester}")
            print(f"   Status: {status}")
            print(f"   Assignee: {assignee}")
            print(f"   Priority: {priority}")
            print(f"   Description: {description[:50] if description else '(empty)'}...")
            
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:K"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == str(ticket_id).strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    print(f"✅ Found ticket {ticket_id} at row {row_index}")
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for modal update")
                return False

            # Get current timestamp
            from datetime import datetime
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update columns separately to avoid discontinuous range issues
            # Column C: Requester (display name)
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!C{row_index}",
                valueInputOption="RAW",
                body={"values": [[requester]]}
            ).execute()
            
            # Column D: Status
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!D{row_index}",
                valueInputOption="RAW",
                body={"values": [[status]]}
            ).execute()
            
            # Column E: Priority
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!E{row_index}",
                valueInputOption="RAW",
                body={"values": [[priority]]}
            ).execute()
            
            # Column F: Assignee (display name)
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!F{row_index}",
                valueInputOption="RAW",
                body={"values": [[assignee]]}
            ).execute()
            
            # Column G: Updated At (always update)
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!G{row_index}",
                valueInputOption="RAW",
                body={"values": [[current_time]]}
            ).execute()
            
            # Column I: Resolved At (only if status is Closed)
            if status == "Closed":
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!I{row_index}",
                    valueInputOption="RAW",
                    body={"values": [[current_time]]}
                ).execute()
                print(f"✅ Updated resolved_at timestamp for closed ticket {ticket_id}")
            
            # Column J: Description
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!J{row_index}",
                valueInputOption="RAW",
                body={"values": [[description]]}
            ).execute()
            
            # Column M: Custom Fields (JSON)
            if custom_fields is not None:
                import json
                custom_fields_json = json.dumps(custom_fields) if custom_fields else ''
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!M{row_index}",
                    valueInputOption="RAW",
                    body={"values": [[custom_fields_json]]}
                ).execute()
                print(f"✅ Updated custom fields for ticket {ticket_id}")

            print(f"✅ Successfully updated ticket {ticket_id} at row {row_index}")
            return True

        except Exception as e:
            print(f"❌ Error updating ticket from modal: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def update_internal_message_ts(self, ticket_id: str, internal_message_ts: str) -> bool:
        """
        Update the internal_message_ts for a ticket.
        
        Args:
            ticket_id (str): ID of the ticket to update
            internal_message_ts (str): Timestamp of the message in internal channel
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # Get all rows to find the ticket
            range_name = f"{self.sheet_name}!A2:N"
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get("values", [])
            row_index = None

            # Find the row with matching ticket_id
            for i, row in enumerate(values):
                if len(row) > 0 and row[0].strip() == str(ticket_id).strip():
                    row_index = i + 2  # +2 because sheet rows are 1-indexed and we skip header
                    break

            if row_index is None:
                print(f"❌ Ticket {ticket_id} not found for internal_message_ts update")
                return False

            # Update internal_message_ts (Column N)
            update_range = f"{self.sheet_name}!N{row_index}"
            update_body = {
                "values": [[internal_message_ts]]
            }

            # Perform the update
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",
                body=update_body
            ).execute()

            print(f"✅ Updated ticket {ticket_id} internal_message_ts to {internal_message_ts}")
            return True

        except Exception as e:
            print(f"❌ Error updating internal_message_ts: {str(e)}")
            return False 