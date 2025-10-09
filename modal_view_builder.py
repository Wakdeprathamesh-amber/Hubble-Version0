"""
Build view-only modal blocks (section blocks instead of input blocks)
"""
from typing import List, Dict, Optional


def build_view_only_blocks(fields: List[Dict], ticket_data: Dict) -> List[Dict]:
    """
    Build view-only modal blocks using section blocks (not input blocks).
    Used for non-admin users who should see but not edit ticket data.
    
    Args:
        fields: List of field definitions
        ticket_data: Ticket data to display
        
    Returns:
        List of section blocks for display
    """
    blocks = []
    
    for field in fields:
        field_id = field['field_id']
        field_label = field['field_label']
        field_type = field['field_type']
        
        # Get the value
        value = ""
        
        if field_type == "user_select":
            # For user fields, show as mention
            if field_id == "requester":
                user_id = ticket_data.get("requester_id", "")
                value = f"<@{user_id}>" if user_id and user_id.startswith('U') else ticket_data.get("created_by", "N/A")
            elif field_id == "assignee":
                user_id = ticket_data.get("assignee_id", "")
                if user_id and user_id.startswith('U'):
                    value = f"<@{user_id}>"
                else:
                    assignee_name = ticket_data.get("assignee", "")
                    value = assignee_name if assignee_name else "Not assigned"
            else:
                # Other user fields
                user_id = ticket_data.get(f"{field_id}_id", "")
                value = f"<@{user_id}>" if user_id and user_id.startswith('U') else ticket_data.get(field_id, "N/A")
                
        elif field_type == "select":
            # For dropdowns, show the selected value
            value = ticket_data.get(field_id, "N/A")
            
        elif field_type == "textarea":
            # For text areas, show the text
            if field_id == "description":
                value = ticket_data.get("message", ticket_data.get("description", "N/A"))
            else:
                value = ticket_data.get(field_id, "N/A")
            
        elif field_type == "date":
            # For dates, show the date
            value = ticket_data.get(field_id, "N/A")
            
        else:  # text
            value = ticket_data.get(field_id, "N/A")
        
        # Create section block for display
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{field_label}:*\n{value}"
            }
        })
    
    # Add divider at the end
    blocks.append({"type": "divider"})
    
    # Add info message
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "ℹ️ _View-only mode. Only admins can edit tickets._"
            }
        ]
    })
    
    return blocks

