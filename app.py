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
        from modal_view_builder import build_view_only_blocks
        
        # Extract data from payload
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']
        
        logger.info(f"🔧 Direct handling: View & Edit for ticket {ticket_id} by user {user_id} in channel {channel_id}")

        # Get ticket data first
        ticket = slack_handler.ticket_service.get_ticket(ticket_id)
        if not ticket:
            logger.error(f"❌ Ticket {ticket_id} not found")
            return jsonify({"error": "Ticket not found"}), 404
        
        # Check if user is admin or ticket creator
        is_admin = False
        is_creator = False
        
        try:
            cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            admin_ids_csv = cfg.get('admin_user_ids', '')
            if admin_ids_csv:
                admin_ids = [u.strip() for u in admin_ids_csv.split(',') if u.strip()]
            else:
                admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
            
            is_admin = user_id in admin_ids
            
            # Check if user is the ticket creator
            ticket_creator_id = ticket.get('created_by', '')
            logger.info(f"🔍 Creator check: user_id={user_id}, ticket_creator_id='{ticket_creator_id}', ticket keys={list(ticket.keys())[:10]}")
            is_creator = (user_id == ticket_creator_id)
        except Exception:
            admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
            is_admin = user_id in admin_ids
            ticket_creator_id = ticket.get('created_by', '')
            logger.info(f"🔍 Creator check (exception path): user_id={user_id}, ticket_creator_id='{ticket_creator_id}'")
            is_creator = (user_id == ticket_creator_id)
        
        logger.info(f"🔍 User {user_id} is_admin: {is_admin}, is_creator: {is_creator}")
        
        # Get modal template for this channel
        cfg_map = slack_handler.ticket_service.sheets_service.get_channel_config_map()
        cfg = cfg_map.get(ticket.get('channel_id', channel_id), {})
        template_key = cfg.get('modal_template_key', 'tech_default')
        
        # Load field definitions
        fields = slack_handler.ticket_service.sheets_service.get_modal_template(template_key)
        if not fields:
            logger.error(f"No fields found for template '{template_key}'")
            return jsonify({"error": "Modal template not found"}), 500
        
        # Build modal blocks based on permissions
        if is_admin:
            # Admins get fully editable modal
            modal_blocks = build_modal_blocks(fields, ticket)
        elif is_creator:
            # Creators get editable modal but with status field locked
            modal_blocks = build_modal_blocks(fields, ticket, lock_status=True)
        else:
            # Others get view-only modal
            modal_blocks = build_view_only_blocks(fields, ticket)
        
        # Add channel context block for supply template
        if template_key == 'supply':
            channel_context = {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Channel:* {cfg.get('channel_name', 'supply')}"
                    }
                ]
            }
            modal_blocks.insert(0, channel_context)
        
        # Store metadata
        metadata = json.dumps({
            'ticket_id': ticket_id,
            'template_key': template_key,
            'channel_id': ticket.get('channel_id', channel_id)
        })
        
        # Get custom modal title based on template
        def get_modal_title(template_key, ticket_id, is_editable):
            template_titles = {
                'supply': 'Form: Supply Team',
                'tech_default': 'Ticket',
                # Add more template titles as needed
            }
            base_title = template_titles.get(template_key, 'Ticket')
            action = "Edit" if is_editable else "View"
            return f"{base_title} - {action} #{ticket_id}"
        
        modal_title = get_modal_title(template_key, ticket_id, (is_admin or is_creator))
        
        # Create modal payload
        modal_view = {
            "type": "modal",
            "callback_id": "ticket_edit_modal",
            "title": {
                "type": "plain_text",
                "text": modal_title,
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel" if (is_admin or is_creator) else "Close",
                "emoji": True
            },
            "blocks": modal_blocks,
            "private_metadata": metadata
        }
        
        # Add submit button for admins and creators (makes it editable)
        if is_admin or is_creator:
            modal_view["submit"] = {
                "type": "plain_text",
                "text": "Update",
                "emoji": True
            }
        
        modal_payload = {
            "trigger_id": payload['trigger_id'],
            "view": modal_view
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
            from slack_sdk import WebClient
            from internal_channel_handler import update_internal_channel_message
            
            client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
            
            # Post status change notification to thread
            try:
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"🔴 *Ticket #{ticket_id}* status changed to *Closed* by <@{user_id}>"
                )
                logger.info(f"✅ Posted status change notification to thread")
            except Exception as e:
                logger.error(f"Error posting status change to thread: {str(e)}")
            
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
        from modal_view_builder import build_view_only_blocks
        
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
        
        # Check if user is admin or ticket creator
        is_admin = False
        is_creator = False
        
        try:
            admin_ids_csv = cfg.get('admin_user_ids', '')
            if admin_ids_csv:
                admin_ids = [u.strip() for u in admin_ids_csv.split(',') if u.strip()]
            else:
                admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
            
            is_admin = user_id in admin_ids
            
            # Check if user is the ticket creator
            ticket_creator_id = ticket.get('created_by', '')
            logger.info(f"🔍 Internal creator check: user_id={user_id}, ticket_creator_id='{ticket_creator_id}'")
            is_creator = (user_id == ticket_creator_id)
        except Exception:
            is_admin = False
            ticket_creator_id = ticket.get('created_by', '')
            logger.info(f"🔍 Internal creator check (exception): user_id={user_id}, ticket_creator_id='{ticket_creator_id}'")
            is_creator = (user_id == ticket_creator_id)
        
        logger.info(f"🔍 User {user_id} is_admin: {is_admin}, is_creator: {is_creator}")
        
        fields = ticket_service.sheets_service.get_modal_template(template_key)
        if not fields:
            return jsonify({"error": "Modal template not found"}), 500
        
        # Build modal blocks based on permissions
        if is_admin:
            # Admins get fully editable modal
            modal_blocks = build_modal_blocks(fields, ticket)
        elif is_creator:
            # Creators get editable modal but with status field locked
            modal_blocks = build_modal_blocks(fields, ticket, lock_status=True)
        else:
            # Others get view-only modal
            modal_blocks = build_view_only_blocks(fields, ticket)
        metadata = json.dumps({
            'ticket_id': ticket_id,
            'template_key': template_key,
            'channel_id': original_channel_id
        })
        
        # Build modal view (with or without submit button)
        modal_view = {
            "type": "modal",
            "callback_id": "ticket_edit_modal",
            "title": {
                "type": "plain_text",
                "text": f"Edit Ticket #{ticket_id}" if (is_admin or is_creator) else f"View Ticket #{ticket_id}",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel" if (is_admin or is_creator) else "Close",
                "emoji": True
            },
            "blocks": modal_blocks,
            "private_metadata": metadata
        }
        
        # Add submit button for admins and creators
        if is_admin or is_creator:
            modal_view["submit"] = {
                "type": "plain_text",
                "text": "Update",
                "emoji": True
            }
        
        modal_payload = {
            "trigger_id": payload['trigger_id'],
            "view": modal_view
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
                    
                    # Post assignee change notification to internal channel thread
                    try:
                        client.chat_postMessage(
                            channel=channel_id,
                            thread_ts=internal_message_ts,
                            text=f"👤 *Ticket #{ticket_id}* assigned to <@{user_id}> ({user_name})"
                        )
                        logger.info(f"✅ Posted assignee change notification to internal channel thread")
                    except Exception as e:
                        logger.error(f"Error posting assignee change to internal thread: {str(e)}")
                
                # Also post to main channel thread
                thread_link = ticket.get('thread_link', '')
                if thread_link and '/p' in thread_link:
                    timestamp_part = thread_link.split('/p')[-1]
                    if len(timestamp_part) >= 10:
                        main_thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        try:
                            client.chat_postMessage(
                                channel=original_channel_id,
                                thread_ts=main_thread_ts,
                                text=f"👤 *Ticket #{ticket_id}* assigned to <@{user_id}> ({user_name})"
                            )
                            logger.info(f"✅ Posted assignee change notification to main channel thread")
                        except Exception as e:
                            logger.error(f"Error posting assignee change to main thread: {str(e)}")
            
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
                    
                    # Post status change notification to internal channel thread
                    try:
                        status_emoji = "🔴" if new_status == "Closed" else "🟢"
                        # Get user's name for display
                        user_name = "Unknown"
                        try:
                            user_info = client.users_info(user=user_id)
                            if user_info["ok"]:
                                user_name = user_info["user"].get("real_name", user_info["user"].get("name", "Unknown"))
                        except Exception as e:
                            logger.error(f"Error getting user name: {str(e)}")
                        
                        client.chat_postMessage(
                            channel=channel_id,
                            thread_ts=internal_message_ts,
                            text=f"{status_emoji} *Ticket #{ticket_id}* status changed to *{new_status}* by <@{user_id}> ({user_name})"
                        )
                        logger.info(f"✅ Posted status change notification to internal channel thread")
                    except Exception as e:
                        logger.error(f"Error posting status change to internal thread: {str(e)}")
                
                # Post status change notification to main channel thread
                thread_link = updated_ticket.get('thread_link', '')
                if thread_link and '/p' in thread_link:
                    timestamp_part = thread_link.split('/p')[-1]
                    if len(timestamp_part) >= 10:
                        main_thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        try:
                            status_emoji = "🔴" if new_status == "Closed" else "🟢"
                            client.chat_postMessage(
                                channel=original_channel_id,
                                thread_ts=main_thread_ts,
                                text=f"{status_emoji} *Ticket #{ticket_id}* status changed to *{new_status}* by <@{user_id}>"
                            )
                            logger.info(f"✅ Posted status change notification to main channel thread")
                        except Exception as e:
                            logger.error(f"Error posting status change to main thread: {str(e)}")
            
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
        
        # Get the ticket to check creator
        ticket = ticket_service.get_ticket(ticket_id)
        if not ticket:
            return jsonify({
                "response_action": "errors",
                "errors": {
                    "description": "Ticket not found. Please try again."
                }
            })
        
        # Permission check - admins and ticket creators can submit
        is_admin = False
        is_creator = False
        
        try:
            cfg_map = ticket_service.sheets_service.get_channel_config_map()
            cfg = cfg_map.get(channel_id, {})
            admin_ids_csv = cfg.get('admin_user_ids', '')
            if admin_ids_csv:
                admin_ids = [u.strip() for u in admin_ids_csv.split(',') if u.strip()]
            else:
                admin_ids = [u.strip() for u in os.environ.get('ADMIN_USER_IDS', '').split(',') if u.strip()]
            
            is_admin = user_id in admin_ids
            
            # Check if user is the ticket creator
            ticket_creator_id = ticket.get('created_by', '')
            is_creator = (user_id == ticket_creator_id)
            
            logger.info(f"🔧 Submission permission: user_id={user_id}, is_admin={is_admin}, is_creator={is_creator}")
            
            if not is_admin and not is_creator:
                logger.warning(f"⚠️ User {user_id} (not admin or creator) tried to submit modal")
                return jsonify({
                    "response_action": "errors",
                    "errors": {
                        "description": "Only admins and ticket creators can update tickets."
                    }
                })
        except Exception as e:
            logger.error(f"Error checking permissions: {str(e)}")
            # If check fails, continue (fail open)
        
        # Get template fields
        fields = ticket_service.sheets_service.get_modal_template(template_key)
        
        # Extract submitted values
        values = view["state"]["values"]
        logger.info(f"🔧 Raw modal values keys: {list(values.keys())}")
        
        submitted_data = extract_modal_values(values, fields)
        logger.info(f"🔧 Extracted {len(submitted_data)} fields: {list(submitted_data.keys())}")
        logger.info(f"🔧 Extracted description value: '{submitted_data.get('description', 'NOT FOUND')}'")
        
        # Separate core fields from custom fields
        core_field_ids = {'requester', 'status', 'assignee', 'priority', 'description'}
        core_data = {}
        custom_data = {}
        
        for field_id, value in submitted_data.items():
            if field_id in core_field_ids:
                core_data[field_id] = value
            else:
                custom_data[field_id] = value
        
        # Ensure description is in core_data even if empty (for textarea fields)
        if 'description' not in core_data and 'description' in [f['field_id'] for f in fields]:
            core_data['description'] = ''
            logger.info(f"🔧 Added empty description to core_data")
        
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
        
        # For creators, preserve existing status (they can't change it)
        # For admins, use submitted status
        if is_creator and not is_admin:
            status = ticket.get('status', 'Open')  # Keep current status
            logger.info(f"🔧 Creator submission - preserving status: {status}")
        else:
            status = core_data.get('status', ticket.get('status', 'Open'))
        
        priority = core_data.get('priority', 'MEDIUM')
        description = core_data.get('description', '') or ''  # Ensure it's always a string, not None
        logger.info(f"🔧 Description value: '{description}' (type: {type(description).__name__}, length: {len(description)})")
        
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
            
            # Silent update - no message to thread
            logger.info(f"✅ Ticket updated silently (no thread message)")
            
            # Get the updated ticket data
            ticket = ticket_service.get_ticket(ticket_id)
            
            # Update internal channel
            try:
                cfg_map = ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(channel_id, {})
                internal_channel_id = cfg.get('internal_channel_id', '').strip()
                
                logger.info(f"🔍 Config check: channel_id={channel_id}, internal_channel_id={internal_channel_id}")
                
                if internal_channel_id and ticket:
                    internal_message_ts = ticket.get('internal_message_ts', '').strip()
                    
                    logger.info(f"🔍 Internal message check: ts={internal_message_ts}")
                    
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
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        
        # Use a field-specific error if description field exists, otherwise use a generic error
        error_field = "description"
        error_message = f"An error occurred: {str(e)}. Please try again."
        
        # Check if description field exists in the form
        try:
            metadata = json.loads(payload['view']["private_metadata"])
            template_key = metadata.get('template_key', '')
            fields = ticket_service.sheets_service.get_modal_template(template_key)
            if not any(f.get('field_id') == 'description' for f in fields):
                # If description field doesn't exist, use first field as error target
                if fields:
                    error_field = fields[0].get('field_id', 'description')
        except:
            pass
        
        return jsonify({
            "response_action": "errors",
            "errors": {
                error_field: error_message
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