import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ticket_service import TicketService
from slack_handler import SlackHandler
from modal_builder import build_modal_blocks
from modal_submission_handler import handle_dynamic_modal_submission
import logging
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Debug: Print environment variables (excluding sensitive values)
print("Environment Variables Loaded:")
print(f"TARGET_CHANNEL_ID: {os.environ.get('TARGET_CHANNEL_ID')}")
print(f"SLACK_BOT_TOKEN exists: {'Yes' if os.environ.get('SLACK_BOT_TOKEN') else 'No'}")
print(f"SLACK_SIGNING_SECRET exists: {'Yes' if os.environ.get('SLACK_SIGNING_SECRET') else 'No'}")
print(f"GOOGLE_CREDENTIALS_PATH exists: {'Yes' if os.environ.get('GOOGLE_CREDENTIALS_PATH') else 'No'}")
print(f"GOOGLE_SPREADSHEET_ID exists: {'Yes' if os.environ.get('GOOGLE_SPREADSHEET_ID') else 'No'}")

# Initialize Flask app
app = Flask(__name__)

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

# Initialize services
ticket_service = TicketService()  # TicketService creates its own SheetsService
slack_handler = SlackHandler(ticket_service)

@app.after_request
def after_request(response):
    # Add CORS headers
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    # Add ngrok header
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

@app.route("/slack/events", methods=["GET", "POST", "OPTIONS"])
def slack_events():
    """Handle Slack events"""
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        # Log basic request info
        logger.info(f"📨 SLACK EVENT: {request.method} {request.path}")
        
        # Handle different content types
        if request.content_type == "application/json":
            data = request.get_json()
        elif request.content_type == "application/x-www-form-urlencoded":
            # Parse form data for interactive components
            form_data = request.form
            if 'payload' in form_data:
                data = json.loads(form_data['payload'])
            else:
                data = {}
        else:
            logger.warning(f"Unknown content type: {request.content_type}")
            return jsonify({"error": "Unsupported content type"}), 400
        
        # Process the event
        response = slack_handler.handler.handle(request)
        return response
        
    except Exception as e:
        logger.error(f"❌ Error processing Slack event: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/slack/interactive", methods=["POST"])
def slack_interactive():
    """Handle Slack interactive components (buttons, modals, etc.)"""
    try:
        logger.info(f"🔘 INTERACTIVE: {request.method} {request.path}")
        
        # Parse the payload to check action type
        if request.content_type == "application/x-www-form-urlencoded":
            form_data = request.form
            if 'payload' in form_data:
                payload = json.loads(form_data['payload'])
            else:
                logger.error("No payload found in form data")
                return jsonify({"error": "No payload found"}), 400
        else:
            logger.error(f"Unexpected content type: {request.content_type}")
            return jsonify({"error": "Expected application/x-www-form-urlencoded"}), 400
        
        # Handle different types of interactive components
        if payload.get('type') == 'block_actions':
            # Handle button clicks
            actions = payload.get('actions', [])
            if actions:
                action = actions[0]
                action_id = action.get('action_id')
                
                logger.info(f"🔘 ACTION: {action_id}")
                
                # Handle main channel buttons directly
                if action_id == 'view_edit_ticket':
                    return handle_view_edit_ticket_direct(payload)
                elif action_id == 'close_ticket':
                    return handle_close_ticket_direct(payload)
                # Handle internal channel buttons directly
                elif action_id == 'internal_view_edit':
                    return handle_internal_view_edit_direct(payload)
                elif action_id == 'internal_assign_me':
                    return handle_internal_assign_me_direct(payload)
                elif action_id == 'internal_change_status':
                    return handle_internal_change_status_direct(payload)
        
        elif payload.get('type') == 'view_submission':
            # Handle modal submissions directly
            logger.info(f"🔧 MODAL SUBMISSION")
            callback_id = payload.get('view', {}).get('callback_id')
            
            if callback_id == 'ticket_edit_modal':
                return handle_modal_submission_direct(payload)
        
        # For any other unknown types, log and return error
        logger.warning(f"⚠️ Unknown interaction type: {payload.get('type')}")
        return jsonify({"error": "Unknown interaction type"}), 400
            
    except Exception as e:
        logger.error(f"❌ Error processing interactive request: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def handle_view_edit_ticket_direct(payload):
    """Handle View & Edit button click with dynamic modal"""
    try:
        # Extract data from payload
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']
        
        logger.info(f"🔧 Direct handling: View & Edit for ticket {ticket_id} by user {user_id} in channel {channel_id}")

        # Admin enforcement
        try:
            cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            admin_ids_csv = cfg.get('admin_user_ids', '')
            if admin_ids_csv:
                admin_ids = [u.strip() for u in admin_ids_csv.split(',') if u.strip()]
            else:
                admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
        except Exception:
            admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
        
        if user_id not in admin_ids:
            from slack_sdk import WebClient
            client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
            try:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="❌ Only channel admins can view or edit tickets."
                )
            except Exception:
                pass
            return jsonify({"ok": False, "error": "not_admin"})
        
        # Get ticket data
        ticket = slack_handler.ticket_service.get_ticket(ticket_id)
        if not ticket:
            logger.error(f"❌ Ticket {ticket_id} not found")
            return jsonify({"error": "Ticket not found"}), 404
        
        # Get modal template for this channel
        cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
        cfg = cfg_map.get(ticket.get('channel_id', channel_id), {})
        template_key = cfg.get('modal_template_key', 'tech_default')
        
        # Load field definitions
        fields = slack_handler.ticket_service.sheets_service.get_modal_template(template_key)
        if not fields:
            logger.error(f"No fields found for template '{template_key}'")
            return jsonify({"error": "Modal template not found"}), 500
        
        # Build dynamic modal blocks
        modal_blocks = build_modal_blocks(fields, ticket)
        
        # Store metadata
        metadata = json.dumps({
            'ticket_id': ticket_id,
            'template_key': template_key,
            'channel_id': ticket.get('channel_id', channel_id)
        })
        
        # Create modal payload
        modal_payload = {
            "trigger_id": payload['trigger_id'],
            "view": {
                "type": "modal",
                "callback_id": "ticket_edit_modal",
                "title": {
                    "type": "plain_text",
                    "text": f"Edit Ticket #{ticket_id}",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Update",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": modal_blocks,
                "private_metadata": metadata
            }
        }
        
        # Open modal
        from slack_sdk import WebClient
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        
        try:
            response = client.views_open(**modal_payload)
            if response['ok']:
                logger.info(f"Dynamic modal opened successfully for ticket {ticket_id}")
                return jsonify({"ok": True})
            else:
                logger.error(f"Failed to open modal: {response}")
                return jsonify({"error": "Failed to open modal"}), 500
        except Exception as e:
            logger.error(f"Error opening modal: {str(e)}")
            return jsonify({"error": str(e)}), 500
            
    except Exception as e:
        logger.error(f"Error handling View & Edit: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_close_ticket_direct(payload):
    """Handle close ticket action directly"""
    try:
        # Extract data from payload
        user_id = payload['user']['id']
        channel_id = payload['channel']['id']
        ticket_id = payload['actions'][0]['value']
        thread_ts = payload['message']['thread_ts']
        
        logger.info(f"Direct handling: Close ticket {ticket_id} by user {user_id} in channel {channel_id}")

        # Admin enforcement using Config sheet per-channel admins
        try:
            cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            admin_ids_csv = cfg.get('admin_user_ids', '')
            if admin_ids_csv:
                admin_ids = [u.strip() for u in admin_ids_csv.split(',') if u.strip()]
            else:
                # Fallback to global env
                admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
        except Exception:
            admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
        
        if user_id not in admin_ids:
            from slack_sdk import WebClient
            client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
            try:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="❌ Only channel admins can close tickets."
                )
            except Exception:
                pass
            return jsonify({"ok": False, "error": "not_admin"})
        
        # Update ticket status
        success = slack_handler.ticket_service.update_ticket_status(ticket_id, "Closed")
        
        if success:
            # Send confirmation
            from slack_sdk import WebClient
            from internal_channel_handler import update_internal_channel_message
            
            client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
            
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"✅ Ticket #{ticket_id} has been closed by <@{user_id}>"
            )
            
            # Update internal channel if configured
            try:
                cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(channel_id, {})
                internal_channel_id = cfg.get('internal_channel_id', '').strip()
                
                if internal_channel_id:
                    # Get updated ticket
                    ticket = slack_handler.ticket_service.get_ticket(ticket_id)
                    if ticket:
                        internal_message_ts = ticket.get('internal_message_ts', '').strip()
                        
                        if internal_message_ts:
                            template_key = cfg.get('modal_template_key', 'tech_default')
                            fields = slack_handler.ticket_service.sheets_service.get_modal_template(template_key)
                            
                            update_internal_channel_message(
                                client=client,
                                internal_channel_id=internal_channel_id,
                                message_ts=internal_message_ts,
                                ticket=ticket,
                                fields=fields or []
                            )
                            logger.info(f"✅ Updated ticket #{ticket_id} in internal channel after close")
            except Exception as e:
                logger.error(f"Error updating internal channel after close: {str(e)}", exc_info=True)
            
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Failed to close ticket"}), 500
                
    except Exception as e:
        logger.error(f"Error in direct close handler: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_internal_view_edit_direct(payload):
    """Handle View & Edit button from internal channel"""
    try:
        from slack_sdk import WebClient
        from modal_builder import build_modal_blocks
        
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']  # Internal channel
        
        logger.info(f"📊 Internal: View/Edit ticket {ticket_id}")
        
        # Get ticket
        ticket = ticket_service.get_ticket(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404
        
        # Get modal template
        original_channel_id = ticket.get('channel_id', '')
        cfg_map = ticket_service.sheets_service.get_channel_config_map()
        cfg = cfg_map.get(original_channel_id, {})
        template_key = cfg.get('modal_template_key', 'tech_default')
        
        fields = ticket_service.sheets_service.get_modal_template(template_key)
        if not fields:
            return jsonify({"error": "Modal template not found"}), 500
        
        # Build modal
        modal_blocks = build_modal_blocks(fields, ticket)
        metadata = json.dumps({
            'ticket_id': ticket_id,
            'template_key': template_key,
            'channel_id': original_channel_id
        })
        
        modal_payload = {
            "trigger_id": payload['trigger_id'],
            "view": {
                "type": "modal",
                "callback_id": "ticket_edit_modal",
                "title": {"type": "plain_text", "text": f"Edit Ticket #{ticket_id}", "emoji": True},
                "submit": {"type": "plain_text", "text": "Update", "emoji": True},
                "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
                "blocks": modal_blocks,
                "private_metadata": metadata
            }
        }
        
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        response = client.views_open(**modal_payload)
        
        if response['ok']:
            logger.info(f"✅ Opened modal for ticket {ticket_id}")
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Failed to open modal"}), 500
            
    except Exception as e:
        logger.error(f"Error in internal view/edit: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def handle_internal_assign_me_direct(payload):
    """Handle Assign to Me button from internal channel"""
    try:
        from slack_sdk import WebClient
        from internal_channel_handler import update_internal_channel_message
        
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']  # Internal channel
        
        logger.info(f"📊 Internal: Assign to Me ticket {ticket_id}")
        
        # Get user's name
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        try:
            user_info = client.users_info(user=user_id)
            if user_info["ok"]:
                user_name = user_info["user"].get("real_name", user_info["user"].get("name", "Unknown"))
            else:
                user_name = "Unknown"
        except:
            user_name = "Unknown"
        
        assignee_display = f"@{user_name}"
        
        # Update ticket (also store user_id for modal pre-fill)
        success = ticket_service.sheets_service.update_ticket_assignee(
            ticket_id=ticket_id,
            assignee_id=assignee_display,
            user_id=user_id
        )
        
        if success:
            # Get updated ticket
            ticket = ticket_service.get_ticket(ticket_id)
            if ticket:
                # Update internal channel card
                internal_message_ts = ticket.get('internal_message_ts', '').strip()
                original_channel_id = ticket.get('channel_id', '')
                
                cfg_map = ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(original_channel_id, {})
                template_key = cfg.get('modal_template_key', 'tech_default')
                fields = ticket_service.sheets_service.get_modal_template(template_key)
                
                if internal_message_ts:
                    update_internal_channel_message(
                        client=client,
                        internal_channel_id=channel_id,
                        message_ts=internal_message_ts,
                        ticket=ticket,
                        fields=fields or []
                    )
                
                # Post to original thread
                thread_link = ticket.get("thread_link", "")
                if thread_link and "/p" in thread_link:
                    timestamp_part = thread_link.split("/p")[-1]
                    if len(timestamp_part) >= 10:
                        thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        try:
                            client.chat_postMessage(
                                channel=original_channel_id,
                                thread_ts=thread_ts,
                                text=f"👤 Ticket #{ticket_id} assigned to <@{user_id}> ({user_name})"
                            )
                        except Exception as e:
                            logger.error(f"Error posting to thread: {str(e)}")
            
            logger.info(f"✅ Assigned ticket {ticket_id} to {user_name}")
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Failed to assign ticket"}), 500
            
    except Exception as e:
        logger.error(f"Error in internal assign me: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def handle_internal_change_status_direct(payload):
    """Handle Change Status button from internal channel"""
    try:
        from slack_sdk import WebClient
        from internal_channel_handler import update_internal_channel_message
        
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']  # Internal channel
        
        logger.info(f"📊 Internal: Change Status ticket {ticket_id}")
        
        # Get current ticket
        ticket = ticket_service.get_ticket(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404
        
        current_status = ticket.get('status', 'Open')
        new_status = "Closed" if current_status == "Open" else "Open"
        
        # Update status
        success = ticket_service.update_ticket_status(ticket_id, new_status)
        
        if success:
            # Get updated ticket
            updated_ticket = ticket_service.get_ticket(ticket_id)
            if updated_ticket:
                client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
                
                # Update internal channel card
                internal_message_ts = updated_ticket.get('internal_message_ts', '').strip()
                original_channel_id = updated_ticket.get('channel_id', '')
                
                cfg_map = ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(original_channel_id, {})
                template_key = cfg.get('modal_template_key', 'tech_default')
                fields = ticket_service.sheets_service.get_modal_template(template_key)
                
                if internal_message_ts:
                    update_internal_channel_message(
                        client=client,
                        internal_channel_id=channel_id,
                        message_ts=internal_message_ts,
                        ticket=updated_ticket,
                        fields=fields or []
                    )
                
                # Post to original thread
                thread_link = updated_ticket.get("thread_link", "")
                if thread_link and "/p" in thread_link:
                    timestamp_part = thread_link.split("/p")[-1]
                    if len(timestamp_part) >= 10:
                        thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        try:
                            status_emoji = "✅" if new_status == "Closed" else "🔵"
                            client.chat_postMessage(
                                channel=original_channel_id,
                                thread_ts=thread_ts,
                                text=f"{status_emoji} Ticket #{ticket_id} status changed to *{new_status}* by <@{user_id}>"
                            )
                        except Exception as e:
                            logger.error(f"Error posting to thread: {str(e)}")
            
            logger.info(f"✅ Changed ticket {ticket_id} status to {new_status}")
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Failed to change status"}), 500
            
    except Exception as e:
        logger.error(f"Error in internal change status: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def handle_modal_submission_direct(payload):
    """Handle modal submission directly without Slack Bolt"""
    try:
        from slack_sdk import WebClient
        from modal_builder import extract_modal_values
        from internal_channel_handler import update_internal_channel_message
        
        logger.info("🔧 Direct modal submission handler")
        
        view = payload['view']
        user_id = payload['user']['id']
        
        # Parse metadata
        try:
            metadata = json.loads(view["private_metadata"])
            ticket_id = metadata['ticket_id']
            template_key = metadata['template_key']
            channel_id = metadata['channel_id']
        except Exception as e:
            logger.error(f"Failed to parse metadata: {str(e)}")
            return jsonify({
                "response_action": "errors",
                "errors": {
                    "description": "Invalid ticket data. Please try again."
                }
            })
        
        logger.info(f"🔧 Submitting ticket #{ticket_id}")
        
        # Get template fields
        fields = ticket_service.sheets_service.get_modal_template(template_key)
        
        # Extract submitted values
        values = view["state"]["values"]
        submitted_data = extract_modal_values(values, fields)
        
        logger.info(f"🔧 Extracted {len(submitted_data)} fields")
        
        # Separate core fields from custom fields
        core_field_ids = {'requester', 'status', 'assignee', 'priority', 'description'}
        core_data = {}
        custom_data = {}
        
        for field_id, value in submitted_data.items():
            if field_id in core_field_ids:
                core_data[field_id] = value
            else:
                custom_data[field_id] = value
        
        # Create Slack client
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        
        # Convert user IDs to display names
        requester_id = core_data.get('requester', '')
        assignee_id = core_data.get('assignee', '')
        
        def get_user_name(uid):
            try:
                user_info = client.users_info(user=uid)
                if user_info["ok"]:
                    return user_info["user"].get("real_name", user_info["user"].get("name", "Unknown"))
            except:
                pass
            return "Unknown"
        
        requester_name = get_user_name(requester_id) if requester_id else ''
        assignee_name = get_user_name(assignee_id) if assignee_id else ''
        
        requester = f"@{requester_name}" if requester_name else ''
        assignee = f"@{assignee_name}" if assignee_name else ''
        
        status = core_data.get('status', 'Open')
        priority = core_data.get('priority', 'MEDIUM')
        description = core_data.get('description', '')
        
        # Store user IDs in custom_data
        if requester_id:
            custom_data['requester_id'] = requester_id
        if assignee_id:
            custom_data['assignee_id'] = assignee_id
        
        logger.info(f"🔧 Updating: Status={status}, Assignee={assignee}, Priority={priority}")
        
        # Update ticket in Sheets
        success = ticket_service.update_ticket_from_modal(
            ticket_id=ticket_id,
            requester=requester,
            status=status,
            assignee=assignee,
            priority=priority,
            description=description,
            custom_fields=custom_data
        )
        
        if success:
            logger.info(f"✅ Updated ticket {ticket_id}")
            
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
            
            update_message = "\n".join(update_lines)
            
            # Post to original thread
            ticket = ticket_service.get_ticket(ticket_id)
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
            
            # Update internal channel
            try:
                cfg_map = ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(channel_id, {})
                internal_channel_id = cfg.get('internal_channel_id', '').strip()
                
                if internal_channel_id and ticket:
                    internal_message_ts = ticket.get('internal_message_ts', '').strip()
                    
                    if internal_message_ts:
                        logger.info(f"📊 Updating internal channel")
                        
                        updated_ticket = ticket_service.get_ticket(ticket_id)
                        if updated_ticket:
                            fields_for_display = ticket_service.sheets_service.get_modal_template(template_key)
                            
                            update_internal_channel_message(
                                client=client,
                                internal_channel_id=internal_channel_id,
                                message_ts=internal_message_ts,
                                ticket=updated_ticket,
                                fields=fields_for_display or []
                            )
                            logger.info(f"✅ Updated internal channel")
            except Exception as e:
                logger.error(f"Error updating internal channel: {str(e)}", exc_info=True)
            
            # Return success response (close modal)
            return jsonify({"response_action": "clear"})
        else:
            logger.error(f"❌ Failed to update ticket {ticket_id}")
            return jsonify({
                "response_action": "errors",
                "errors": {
                    "description": "Failed to update ticket. Please try again."
                }
            })
            
    except Exception as e:
        logger.error(f"❌ Error in modal submission: {str(e)}", exc_info=True)
        return jsonify({
            "response_action": "errors",
            "errors": {
                "description": "An error occurred. Please try again."
            }
        })

@app.route("/tickets", methods=["GET"])
def get_tickets():
    """API endpoint to get all tickets"""
    return jsonify(ticket_service.get_all_tickets())

@app.route("/test", methods=["GET"])
def test():
    return jsonify({"status": "ok"})

@app.route("/test/message", methods=["POST"])
def test_message():
    """Test endpoint for message events"""
    try:
        data = request.get_json()
        logger.debug(f"Test message data: {data}")
        
        # Extract event data
        event = data.get("event", {})
        channel_id = event.get("channel")
        user_id = event.get("user")
        text = event.get("text")
        ts = event.get("ts")
        
        # Create a ticket
        ticket_id = ticket_service.create_ticket(
            message_text=text,
            requester_id=user_id,
            timestamp=ts
        )
        
        return jsonify({
            "status": "ok",
            "message": f"Ticket #{ticket_id} created",
            "ticket_id": ticket_id
        })
    except Exception as e:
        logger.error(f"Error in test message endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    """Simple home endpoint to verify the server is running"""
    return jsonify({"status": "ok", "message": "Fix Kar Slack Bot is running!"})

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Basic health checks
        env_vars = {
            "SLACK_BOT_TOKEN": bool(os.environ.get('SLACK_BOT_TOKEN')),
            "SLACK_SIGNING_SECRET": bool(os.environ.get('SLACK_SIGNING_SECRET')),
            "GOOGLE_CREDENTIALS_PATH": bool(os.environ.get('GOOGLE_CREDENTIALS_PATH')),
            "GOOGLE_SPREADSHEET_ID": bool(os.environ.get('GOOGLE_SPREADSHEET_ID')),
            "TARGET_CHANNEL_ID": bool(os.environ.get('TARGET_CHANNEL_ID'))
        }
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment_variables": env_vars
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route("/slack/commands", methods=["POST"])
def slack_commands():
    """Handle Slack slash commands"""
    return slack_handler.handler.handle(request)

if __name__ == "__main__":
    # Get port from environment variable or use 3000 as default
    port = int(os.environ.get("PORT", 3000))
    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=True)