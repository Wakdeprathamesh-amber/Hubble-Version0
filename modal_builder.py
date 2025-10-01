"""
Modal builder for dynamic Slack modals based on field templates.
"""
from typing import List, Dict, Optional


def build_modal_blocks(fields: List[Dict], ticket_data: Optional[Dict] = None) -> List[Dict]:
    """
    Build Slack modal blocks from field definitions.
    
    Args:
        fields: List of field definitions from Modal Templates sheet
        ticket_data: Optional existing ticket data for pre-filling fields
        
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
            initial_val = ticket_data.get(field_id) or ticket_data.get(f"{field_id}_id", "")
            if initial_val and initial_val.startswith('U'):
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
            if ticket_data.get(field_id) and ticket_data[field_id] in option_list:
                element["initial_option"] = {
                    "text": {"type": "plain_text", "text": ticket_data[field_id]},
                    "value": ticket_data[field_id]
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
            if ticket_data.get(field_id):
                element["initial_value"] = ticket_data[field_id]
                
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
            if ticket_data.get(field_id):
                element["initial_value"] = ticket_data[field_id]
        
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

