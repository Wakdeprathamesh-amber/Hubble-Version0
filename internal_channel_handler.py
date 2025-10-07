"""
Internal Channel Handler - Posts and updates ticket cards in internal visualization channels.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


def format_ticket_card(ticket: Dict, fields: List[Dict], include_buttons: bool = True) -> Dict:
    """
    Format a ticket as a rich Slack message card.
    
    Args:
        ticket: Ticket data dictionary
        fields: Modal template fields to display
        include_buttons: Whether to include action buttons
        
    Returns:
        Dict with 'text' and 'blocks' for Slack message
    """
    ticket_id = ticket.get('ticket_id', 'Unknown')
    status = ticket.get('status', 'Open')
    priority = ticket.get('priority', 'Medium')
    requester = ticket.get('created_by', 'Unknown')
    assignee = ticket.get('assignee', 'Unassigned')
    channel_name = ticket.get('channel_name', 'Unknown Channel')
    channel_id = ticket.get('channel_id', '')
    thread_link = ticket.get('thread_link', '')
    created_at = ticket.get('created_at', '')
    resolved_at = ticket.get('resolved_at', '')
    description = ticket.get('message', '')
    
    # Status emoji
    status_emoji = "✅" if status == "Closed" else "🔵"
    
    # Priority emoji
    priority_emoji_map = {
        'CRITICAL': '🔴',
        'HIGH': '🔸',
        'MEDIUM': '🟡',
        'LOW': '🟢'
    }
    priority_emoji = priority_emoji_map.get(priority.upper(), '')
    
    # Format timestamps nicely
    def format_timestamp(ts_str):
        if not ts_str:
            return "N/A"
        try:
            # Parse the timestamp
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            # Format as "Month Day Time"
            return dt.strftime('%B %d %I:%M %p')
        except:
            return ts_str
    
    created_formatted = format_timestamp(created_at)
    changed_formatted = format_timestamp(resolved_at) if resolved_at else format_timestamp(created_at)
    
    # Build header text
    header_text = f"{status_emoji} *{status}*  #{ticket_id}"
    if priority:
        header_text += f" | {priority} {priority_emoji}"
    
    # Build the message blocks
    blocks = []
    
    # Header block
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Ticket #{ticket_id}",
            "emoji": True
        }
    })
    
    # Status and priority section
    status_fields = [
        {
            "type": "mrkdwn",
            "text": f"*Status:* {status_emoji} {status}"
        },
        {
            "type": "mrkdwn",
            "text": f"*Priority:* {priority} {priority_emoji}"
        }
    ]
    
    blocks.append({
        "type": "section",
        "fields": status_fields
    })
    
    # Requester and channel info
    view_link_text = f"<{thread_link}|view>" if thread_link else "no link"
    requester_text = f"*Requested by:* {requester} in <#{channel_id}|{channel_name}> ({view_link_text})"
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": requester_text
        }
    })
    
    # Assignee
    if assignee:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Assignee:* {assignee}"
            }
        })
    
    # Timestamps
    timestamp_fields = [
        {
            "type": "mrkdwn",
            "text": f"*Created:* {created_formatted}"
        },
        {
            "type": "mrkdwn",
            "text": f"*Changed:* {changed_formatted}"
        }
    ]
    
    blocks.append({
        "type": "section",
        "fields": timestamp_fields
    })
    
    # Description
    if description:
        # Truncate if too long
        desc_preview = description if len(description) <= 500 else description[:500] + "..."
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{desc_preview}"
            }
        })
    
    # Custom fields (from modal template)
    custom_field_lines = []
    for field in fields:
        field_id = field['field_id']
        # Skip core fields
        if field_id in ['requester', 'status', 'assignee', 'priority', 'description']:
            continue
        
        field_label = field['field_label']
        field_value = ticket.get(field_id, '')
        
        if field_value:
            custom_field_lines.append(f"*{field_label}:* {field_value}")
    
    if custom_field_lines:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(custom_field_lines)
            }
        })
    
    # Divider
    blocks.append({"type": "divider"})
    
    # Action buttons (if enabled)
    if include_buttons:
        buttons = [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🔍 View/Edit",
                    "emoji": True
                },
                "style": "primary",
                "action_id": "internal_view_edit",
                "value": ticket_id
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "👤 Assign to Me",
                    "emoji": True
                },
                "action_id": "internal_assign_me",
                "value": ticket_id
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🔄 Change Status",
                    "emoji": True
                },
                "style": "danger" if status == "Open" else "default",
                "action_id": "internal_change_status",
                "value": ticket_id
            }
        ]
        
        blocks.append({
            "type": "actions",
            "elements": buttons
        })
    
    # Fallback text for notifications
    fallback_text = f"{status_emoji} {status} #{ticket_id} | {priority} - {requester} in {channel_name}"
    
    return {
        "text": fallback_text,
        "blocks": blocks
    }


def post_to_internal_channel(client: WebClient, internal_channel_id: str, ticket: Dict, fields: List[Dict]) -> Optional[str]:
    """
    Post a new ticket card to the internal channel.
    
    Args:
        client: Slack WebClient
        internal_channel_id: ID of the internal channel
        ticket: Ticket data
        fields: Modal template fields
        
    Returns:
        Message timestamp (ts) if successful, None otherwise
    """
    try:
        if not internal_channel_id:
            logger.warning("No internal channel ID provided")
            return None
        
        # Format the ticket card
        message = format_ticket_card(ticket, fields, include_buttons=True)
        
        # Post to channel
        response = client.chat_postMessage(
            channel=internal_channel_id,
            text=message['text'],
            blocks=message['blocks'],
            unfurl_links=False,
            unfurl_media=False
        )
        
        if response['ok']:
            message_ts = response['ts']
            logger.info(f"✅ Posted ticket #{ticket['ticket_id']} to internal channel {internal_channel_id}")
            return message_ts
        else:
            logger.error(f"❌ Failed to post to internal channel: {response.get('error')}")
            return None
            
    except SlackApiError as e:
        logger.error(f"❌ Slack API error posting to internal channel: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Error posting to internal channel: {str(e)}", exc_info=True)
        return None


def update_internal_channel_message(client: WebClient, internal_channel_id: str, message_ts: str, ticket: Dict, fields: List[Dict]) -> bool:
    """
    Update an existing ticket card in the internal channel.
    
    Args:
        client: Slack WebClient
        internal_channel_id: ID of the internal channel
        message_ts: Timestamp of the message to update
        ticket: Updated ticket data
        fields: Modal template fields
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not internal_channel_id or not message_ts:
            logger.warning("No internal channel ID or message timestamp provided")
            return False
        
        # Format the updated ticket card
        message = format_ticket_card(ticket, fields, include_buttons=True)
        
        # Update the message
        response = client.chat_update(
            channel=internal_channel_id,
            ts=message_ts,
            text=message['text'],
            blocks=message['blocks'],
            unfurl_links=False,
            unfurl_media=False
        )
        
        if response['ok']:
            logger.info(f"✅ Updated ticket #{ticket['ticket_id']} in internal channel")
            return True
        else:
            logger.error(f"❌ Failed to update internal channel message: {response.get('error')}")
            return False
            
    except SlackApiError as e:
        logger.error(f"❌ Slack API error updating internal channel: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error updating internal channel: {str(e)}", exc_info=True)
        return False

