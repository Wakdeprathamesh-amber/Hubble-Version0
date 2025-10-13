"""
Modal builder for dynamic Slack modals based on field templates.
"""
from typing import List, Dict, Optional


def build_modal_blocks(fields: List[Dict], ticket_data: Optional[Dict] = None, lock_status: bool = False) -> List[Dict]:
    """
    Build Slack modal blocks from field definitions.
    
    Args:
        fields: List of field definitions from Modal Templates sheet
        ticket_data: Optional existing ticket data for pre-filling fields
        lock_status: If True, status field will be view-only (for ticket creators)
        
    Returns:
        List of Slack Block Kit blocks
    """
    blocks = []
    ticket_data = ticket_data or {}
    
    for field in fields:
        field_id = field['field_id']
        field_label = field['field_label']
        field_type = field['field_type']
        required = field['required']
        options = field['options']
        
        # If this is the status field and we need to lock it, make it view-only
        if field_id == 'status' and lock_status:
            current_status = ticket_data.get('status', 'Open')
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{field_label}:* {current_status}\n_Status can only be changed by admins_"
                }
            })
            continue  # Skip creating an editable input for status
        
        block = {
            "type": "input",
            "block_id": field_id,
            "label": {
                "type": "plain_text",
                "text": field_label,
                "emoji": True
            },
            "optional": not required
        }
        
        # Build element based on field type
        if field_type == "user_select":
            element = {
                "type": "users_select",
                "action_id": f"{field_id}_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Select {field_label.lower()}",
                    "emoji": True
                }
            }
            # Pre-fill if data exists and looks like a user ID (starts with U)
            initial_val = ""
            
            # For requester field, check multiple sources
            if field_id == "requester":
                # 1. Check requester_id from custom_fields
                initial_val = ticket_data.get("requester_id", "")
                # 2. Fall back to created_by if it's a user ID
                if not initial_val or not initial_val.startswith('U'):
                    created_by = ticket_data.get("created_by", "")
                    if created_by and created_by.startswith('U'):
                        initial_val = created_by
            
            # For assignee field, check multiple sources
            elif field_id == "assignee":
                # 1. Check assignee_id from custom_fields
                initial_val = ticket_data.get("assignee_id", "")
                # 2. Fall back to assignee if it's a user ID
                if not initial_val or not initial_val.startswith('U'):
                    assignee = ticket_data.get("assignee", "")
                    if assignee and assignee.startswith('U'):
                        initial_val = assignee
            
            # For any other user_select field
            else:
                # Check field_id from custom_fields, then field_id_id variant
                initial_val = ticket_data.get(f"{field_id}_id", "") or ticket_data.get(field_id, "")
            
            # Only set initial_user if we have a valid Slack user ID
            if initial_val and isinstance(initial_val, str) and initial_val.startswith('U'):
                element["initial_user"] = initial_val
                
        elif field_type == "select":
            # Build options from CSV
            option_list = [opt.strip() for opt in options.split(',') if opt.strip()]
            element = {
                "type": "static_select",
                "action_id": f"{field_id}_select",
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Select {field_label.lower()}",
                    "emoji": True
                },
                "options": [
                    {
                        "text": {"type": "plain_text", "text": opt},
                        "value": opt
                    } for opt in option_list
                ]
            }
            # Pre-fill if data exists
            current_value = ticket_data.get(field_id, "")
            
            # Case-insensitive matching for status and priority
            matched_option = None
            if current_value:
                for opt in option_list:
                    if opt.upper() == current_value.upper():
                        matched_option = opt
                        break
            
            if matched_option:
                element["initial_option"] = {
                    "text": {"type": "plain_text", "text": matched_option},
                    "value": matched_option
                }
                
        elif field_type == "textarea":
            element = {
                "type": "plain_text_input",
                "action_id": f"{field_id}_input",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Enter {field_label.lower()}",
                    "emoji": True
                }
            }
            # Pre-fill if data exists
            # Special case: 'description' field maps to 'message' in ticket data
            value = ticket_data.get(field_id, "")
            if not value and field_id == "description":
                value = ticket_data.get("message", "")
            
            if value:
                element["initial_value"] = str(value)
                
        elif field_type == "date":
            element = {
                "type": "datepicker",
                "action_id": f"{field_id}_date",
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Select {field_label.lower()}",
                    "emoji": True
                }
            }
            # Pre-fill if data exists (format: YYYY-MM-DD)
            if ticket_data.get(field_id):
                element["initial_date"] = ticket_data[field_id]
                
        else:  # text
            element = {
                "type": "plain_text_input",
                "action_id": f"{field_id}_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Enter {field_label.lower()}",
                    "emoji": True
                }
            }
            # Pre-fill if data exists
            value = ticket_data.get(field_id, "")
            if value:
                element["initial_value"] = str(value)
        
        block["element"] = element
        blocks.append(block)
    
    return blocks


def extract_modal_values(values: Dict, fields: List[Dict]) -> Dict[str, str]:
    """
    Extract submitted values from Slack modal state.
    
    Args:
        values: The view["state"]["values"] dict from modal submission
        fields: List of field definitions to know what to extract
        
    Returns:
        Dict mapping field_id to submitted value
    """
    extracted = {}
    
    for field in fields:
        field_id = field['field_id']
        field_type = field['field_type']
        
        if field_id not in values:
            continue
            
        block_values = values[field_id]
        
        # Extract based on field type
        if field_type == "user_select":
            action_id = f"{field_id}_select"
            if action_id in block_values:
                extracted[field_id] = block_values[action_id].get("selected_user", "")
                
        elif field_type == "select":
            action_id = f"{field_id}_select"
            if action_id in block_values:
                selected = block_values[action_id].get("selected_option", {})
                extracted[field_id] = selected.get("value", "")
                
        elif field_type == "date":
            action_id = f"{field_id}_date"
            if action_id in block_values:
                extracted[field_id] = block_values[action_id].get("selected_date", "")
                
        else:  # text or textarea
            action_id = f"{field_id}_input"
            if action_id in block_values:
                extracted[field_id] = block_values[action_id].get("value", "")
    
    return extracted

