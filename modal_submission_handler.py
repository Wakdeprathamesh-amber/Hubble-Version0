"""
New dynamic modal submission handler
"""
import os
import json
import logging
from modal_builder import extract_modal_values

logger = logging.getLogger(__name__)


def handle_dynamic_modal_submission(ack, body, view, slack_handler):
    """
    Handle modal submission with dynamic field extraction.
    
    Args:
        ack: Slack ack function
        body: Slack event body
        view: Modal view data
        slack_handler: SlackHandler instance for accessing services
    """
    try:
        logger.info("🔧 Dynamic modal submission received")
        
        # Parse metadata
        try:
            metadata = json.loads(view["private_metadata"])
            ticket_id = metadata['ticket_id']
            template_key = metadata['template_key']
            channel_id = metadata['channel_id']
        except Exception as e:
            logger.error(f"Failed to parse metadata: {str(e)}")
            ack({
                "response_action": "errors",
                "errors": {
                    "description": "Invalid ticket data. Please try again."
                }
            })
            return
        
        user_id = body["user"]["id"]
        
        # Permission check
        if channel_id and not slack_handler._is_channel_admin(user_id, channel_id):
            ack({
                "response_action": "errors",
                "errors": {
                    "description": "Only channel admins can update tickets."
                }
            })
            return
        
        # Acknowledge immediately
        ack({"response_action": "clear"})
        
        # Get template fields
        fields = slack_handler.ticket_service.sheets_service.get_modal_template(template_key)
        
        # Extract all submitted values
        values = view["state"]["values"]
        submitted_data = extract_modal_values(values, fields)
        
        logger.info(f"🔧 Extracted {len(submitted_data)} fields: {list(submitted_data.keys())}")
        
        # Separate core fields from custom fields
        core_field_ids = {'requester', 'status', 'assignee', 'priority', 'description'}
        core_data = {}
        custom_data = {}
        
        for field_id, value in submitted_data.items():
            if field_id in core_field_ids:
                core_data[field_id] = value
            else:
                custom_data[field_id] = value
        
        # Create Slack client for user lookups
        from slack_sdk import WebClient
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        
        # Convert user IDs to display names for core fields
        requester_id = core_data.get('requester', '')
        assignee_id = core_data.get('assignee', '')
        
        requester_name = slack_handler._get_user_name(client, requester_id) if requester_id else ''
        assignee_name = slack_handler._get_user_name(client, assignee_id) if assignee_id else ''
        
        requester = f"@{requester_name}" if requester_name else ''
        assignee = f"@{assignee_name}" if assignee_name else ''
        
        status = core_data.get('status', 'Open')
        priority = core_data.get('priority', 'MEDIUM')
        description = core_data.get('description', '')
        
        # Store user IDs in custom_data for future reference (helps with modal pre-fill)
        if requester_id:
            custom_data['requester_id'] = requester_id
        if assignee_id:
            custom_data['assignee_id'] = assignee_id
        
        logger.info(f"🔧 Core: Requester={requester}, Status={status}, Assignee={assignee}, Priority={priority}")
        logger.info(f"🔧 Custom: {custom_data}")
        
        # Update ticket in Sheets
        success = slack_handler.ticket_service.update_ticket_from_modal(
            ticket_id=ticket_id,
            requester=requester,
            status=status,
            assignee=assignee,
            priority=priority,
            description=description,
            custom_fields=custom_data
        )
        
        if success:
            logger.info(f"✅ Updated ticket {ticket_id} successfully")
            
            # Build update message
            update_lines = [f"✅ *Ticket #{ticket_id} Updated*", "", f"**Updated by:** <@{user_id}>"]
            
            if requester_id:
                update_lines.append(f"**Requester:** <@{requester_id}> ({requester_name})")
            if status:
                update_lines.append(f"**Status:** {status}")
            if assignee_id:
                update_lines.append(f"**Assignee:** <@{assignee_id}> ({assignee_name})")
            if priority:
                update_lines.append(f"**Priority:** {priority}")
            if description:
                desc_preview = description[:100] + "..." if len(description) > 100 else description
                update_lines.append(f"**Description:** {desc_preview}")
            
            # Add custom fields to message
            for key, val in custom_data.items():
                field_label = key.replace('_', ' ').title()
                update_lines.append(f"**{field_label}:** {val}")
            
            update_message = "\n".join(update_lines)
            
            # Post to thread
            ticket = slack_handler.ticket_service.get_ticket(ticket_id)
            if ticket and ticket.get("thread_link"):
                thread_link = ticket["thread_link"]
                if "/p" in thread_link:
                    timestamp_part = thread_link.split("/p")[-1]
                    if len(timestamp_part) >= 10:
                        thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        post_channel = ticket.get("channel_id") or channel_id
                        try:
                            client.chat_postMessage(
                                channel=post_channel,
                                thread_ts=thread_ts,
                                text=update_message
                            )
                            logger.info(f"✅ Posted update to thread")
                        except Exception as e:
                            logger.error(f"Error posting to thread: {str(e)}")
        else:
            logger.error(f"❌ Failed to update ticket {ticket_id}")
            
    except Exception as e:
        logger.error(f"❌ Exception in modal submission: {str(e)}", exc_info=True)

