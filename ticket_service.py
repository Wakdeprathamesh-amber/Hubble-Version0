import os
import logging
from datetime import datetime
from sheets_service import SheetsService

logger = logging.getLogger(__name__)

class TicketService:
    def __init__(self):
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SPREADSHEET_ID environment variable is required")
            
        self.sheets_service = SheetsService(credentials_path, spreadsheet_id)
        self.next_ticket_id = self._get_next_ticket_id()
    
    def _get_next_ticket_id(self) -> int:
        """Get the next ticket ID by finding the highest existing ID and adding 1"""
        tickets = self.sheets_service.get_tickets()
        if not tickets:
            return 1
        
        max_id = max(int(ticket['ticket_id']) for ticket in tickets if ticket['ticket_id'].isdigit())
        return max_id + 1
    
    def create_ticket(self, message_text, requester_id, requester_name=None, timestamp=None, thread_ts=None, channel_id=None, priority='Medium'):
        """Create a new ticket with default values"""
        try:
            ticket_id = str(self.next_ticket_id)
            self.next_ticket_id += 1
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ticket_data = {
                'ticket_id': ticket_id,
                'thread_ts': thread_ts,
                'channel_id': channel_id,
                'created_by': requester_id,
                'requester_name': requester_name or f"@{requester_id}",  # Use real name if provided
                'status': 'Open',  # Default status is Open
                'priority': priority,
                'assignee': '',
                'created_at': current_time,
                'updated_at': current_time,
                'resolved_at': '',
                'description': message_text
            }
            
            success = self.sheets_service.append_ticket(ticket_data)
            if success:
                logger.info(f"Created ticket {ticket_id}")
                return ticket_id
            else:
                logger.error(f"Failed to create ticket {ticket_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}")
            raise
    
    def get_ticket(self, ticket_id):
        """Get a specific ticket by ID"""
        tickets = self.sheets_service.get_tickets()
        for ticket in tickets:
            if ticket['ticket_id'] == ticket_id:
                return ticket
        return None
    
    def get_all_tickets(self):
        """Get all tickets"""
        return self.sheets_service.get_tickets()
    
    def update_ticket_status(self, ticket_id, new_status):
        """Update ticket status and timestamps"""
        try:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return False
            
            # Validate status
            valid_statuses = ['Open', 'Closed']
            if new_status not in valid_statuses:
                logger.error(f"Invalid status: {new_status}. Must be one of {valid_statuses}")
                return False
            
            # Update timestamps based on status
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if new_status == 'Closed':
                resolved_at = current_time
            else:
                resolved_at = ticket.get('resolved_at', '')
            
            # Update the ticket
            success = self.sheets_service.update_ticket_status(
                ticket_id=ticket_id,
                new_status=new_status,
                updated_at=current_time,
                resolved_at=resolved_at
            )
            
            if success:
                logger.info(f"Updated ticket {ticket_id} status to {new_status}")
                return True
            else:
                logger.error(f"Failed to update ticket {ticket_id} status")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket status: {str(e)}")
            return False
    
    def update_ticket_assignee(self, ticket_id, assignee_id):
        """Update ticket assignee"""
        try:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return False
            
            # Update the ticket
            success = self.sheets_service.update_ticket_assignee(
                ticket_id=ticket_id,
                assignee_id=assignee_id
            )
            
            if success:
                logger.info(f"Updated ticket {ticket_id} assignee to {assignee_id}")
                return True
            else:
                logger.error(f"Failed to update ticket {ticket_id} assignee")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket assignee: {str(e)}")
            return False
    
    def update_ticket_priority(self, ticket_id, priority):
        """Update ticket priority"""
        try:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return False
            
            # Validate priority
            valid_priorities = ['Low', 'Medium', 'High', 'Urgent']
            if priority not in valid_priorities:
                logger.error(f"Invalid priority: {priority}")
                return False
            
            # Update the ticket
            success = self.sheets_service.update_ticket_priority(
                ticket_id=ticket_id,
                priority=priority
            )
            
            if success:
                logger.info(f"Updated ticket {ticket_id} priority to {priority}")
                return True
            else:
                logger.error(f"Failed to update ticket {ticket_id} priority")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket priority: {str(e)}")
            return False
    
    def update_ticket_first_response(self, ticket_id, response_text, responder_id):
        """Update ticket with first response information"""
        try:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return False
            
            # Update the ticket with first response
            success = self.sheets_service.update_ticket_first_response(
                ticket_id=ticket_id,
                response_text=response_text,
                responder_id=responder_id
            )
            
            if success:
                logger.info(f"Updated ticket {ticket_id} with first response from {responder_id}")
                return True
            else:
                logger.error(f"Failed to update ticket {ticket_id} with first response")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket first response: {str(e)}")
            return False

    def update_ticket_from_modal(self, ticket_id, requester, status, assignee, priority, description, custom_fields=None):
        """Update ticket from modal form data"""
        try:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return False
            
            # Update the ticket with all fields
            success = self.sheets_service.update_ticket_from_modal(
                ticket_id=ticket_id,
                requester=requester,
                status=status,
                assignee=assignee,
                priority=priority,
                description=description,
                custom_fields=custom_fields
            )
            
            if success:
                logger.info(f"Updated ticket {ticket_id} from modal")
                return True
            else:
                logger.error(f"Failed to update ticket {ticket_id} from modal")
                return False
                
        except Exception as e:
            logger.error(f"Error updating ticket from modal: {str(e)}")
            return False

    def clear_all_tickets(self):
        """Clear all tickets from the sheet"""
        try:
            success = self.sheets_service.clear_all_data()
            if success:
                logger.info("All tickets cleared from sheet")
                return True
            else:
                logger.error("Failed to clear tickets from sheet")
                return False
        except Exception as e:
            logger.error(f"Error clearing tickets: {str(e)}")
            return False