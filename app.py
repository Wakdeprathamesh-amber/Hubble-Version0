import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ticket_service import TicketService
from slack_handler import SlackHandler
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
        
        # Parse the payload
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
                
                if action_id == 'view_edit_ticket':
                    return handle_view_edit_ticket_direct(payload)
                elif action_id == 'close_ticket':
                    return handle_close_ticket_direct(payload)
                else:
                    logger.warning(f"Unknown action_id: {action_id}")
                    return jsonify({"error": "Unknown action"}), 400
        elif payload.get('type') == 'view_submission':
            # Handle modal submission directly
            logger.info(f"🔧 MODAL SUBMISSION: Handling directly")
            logger.info(f"🔧 PAYLOAD TYPE: {payload.get('type')}")
            logger.info(f"🔧 CALLBACK ID: {payload.get('view', {}).get('callback_id')}")
            logger.info(f"🔧 FULL PAYLOAD KEYS: {list(payload.keys())}")
            logger.info(f"🔧 VIEW KEYS: {list(payload.get('view', {}).keys())}")
            logger.info(f"🔧 USER INFO: {payload.get('user', {})}")
            logger.info(f"🔧 TEAM INFO: {payload.get('team', {})}")
            
            # Handle the modal submission directly
            try:
                view = payload.get('view', {})
                callback_id = view.get('callback_id')
                
                if callback_id == 'ticket_edit_modal':
                    # Extract data from the modal
                    ticket_id = view.get('private_metadata')
                    user_id = payload.get('user', {}).get('id')
                    values = view.get('state', {}).get('values', {})
                    
                    # Parse form data
                    requester_id = values.get('requester', {}).get('requester_select', {}).get('selected_user', '')
                    status = values.get('status', {}).get('status_select', {}).get('selected_option', {}).get('value', '')
                    assignee_id = values.get('assignee', {}).get('assignee_select', {}).get('selected_user', '')
                    priority = values.get('priority', {}).get('priority_select', {}).get('selected_option', {}).get('value', '')
                    description = values.get('description', {}).get('description_input', {}).get('value', '')
                    
                    logger.info(f"🔧 EXTRACTED VALUES: Ticket={ticket_id}, User={user_id}, Status={status}, Priority={priority}")
                    logger.info(f"🔧 RAW FORM DATA: Requester={requester_id}, Assignee={assignee_id}")
                    logger.info(f"🔧 VALUES STRUCTURE: {values}")
                    
                    # Return immediate acknowledgment first
                    logger.info(f"🔧 RETURNING IMMEDIATE ACKNOWLEDGMENT")
                    response_data = {
                        "response_action": "clear"
                    }
                    response = jsonify(response_data)
                    logger.info(f"🔧 IMMEDIATE RESPONSE: {response_data}")
                    
                    # Process the update in background
                    def process_update():
                        try:
                            logger.info(f"🔧 BACKGROUND: Processing ticket {ticket_id} update")
                            
                            # Get user names from Slack
                            requester_name = ""
                            assignee_name = ""
                            
                            if requester_id:
                                try:
                                    logger.info(f"🔧 CALLING SLACK API for requester: {requester_id}")
                                    user_info = slack_handler.slack_app.client.users_info(user=requester_id)
                                    logger.info(f"🔧 SLACK API RESPONSE: {user_info}")
                                    if user_info["ok"]:
                                        user = user_info["user"]
                                        real_name = user.get("real_name", user.get("name", f"@{requester_id}"))
                                        requester_name = f"@{real_name}"  # Add @ symbol
                                        logger.info(f"🔧 EXTRACTED NAME: {requester_name}")
                                    else:
                                        requester_name = f"@{requester_id}"
                                        logger.error(f"❌ Slack API failed for requester: {user_info}")
                                except Exception as e:
                                    logger.error(f"❌ Error getting requester name: {str(e)}")
                                    requester_name = f"@{requester_id}"
                            
                            if assignee_id:
                                try:
                                    logger.info(f"🔧 CALLING SLACK API for assignee: {assignee_id}")
                                    user_info = slack_handler.slack_app.client.users_info(user=assignee_id)
                                    logger.info(f"🔧 SLACK API RESPONSE: {user_info}")
                                    if user_info["ok"]:
                                        user = user_info["user"]
                                        real_name = user.get("real_name", user.get("name", f"@{assignee_id}"))
                                        assignee_name = f"@{real_name}"  # Add @ symbol
                                        logger.info(f"🔧 EXTRACTED NAME: {assignee_name}")
                                    else:
                                        assignee_name = f"@{assignee_id}"
                                        logger.error(f"❌ Slack API failed for assignee: {user_info}")
                                except Exception as e:
                                    logger.error(f"❌ Error getting assignee name: {str(e)}")
                                    assignee_name = f"@{assignee_id}"
                            
                            logger.info(f"🔧 USER NAMES: Requester={requester_name}, Assignee={assignee_name}")
                            logger.info(f"🔧 ORIGINAL IDs: Requester={requester_id}, Assignee={assignee_id}")
                            logger.info(f"🔧 SLACK API RESPONSES: Requester={user_info if 'user_info' in locals() else 'Not called'}")
                            
                            success = slack_handler.ticket_service.update_ticket_from_modal(
                                ticket_id=ticket_id,
                                requester=requester_name,
                                status=status,
                                assignee=assignee_name,
                                priority=priority,
                                description=description
                            )
                            
                            if success:
                                logger.info(f"✅ BACKGROUND: Successfully updated ticket {ticket_id}")
                            else:
                                logger.error(f"❌ BACKGROUND: Failed to update ticket {ticket_id}")
                        except Exception as e:
                            logger.error(f"❌ BACKGROUND ERROR: {str(e)}")
                    
                    # Start background processing
                    thread = threading.Thread(target=process_update)
                    thread.daemon = True
                    thread.start()
                    
                    return response, 200
                else:
                    logger.warning(f"Unknown callback_id: {callback_id}")
                    return jsonify({"response_action": "clear"})
                    
            except Exception as e:
                logger.error(f"❌ MODAL HANDLER ERROR: {str(e)}", exc_info=True)
                return jsonify({
                    "response_action": "errors",
                    "errors": {
                        "description": "An error occurred while updating the ticket."
                    }
                })
        
        # Try Slack Bolt handler as fallback
        try:
            response = slack_handler.handler.handle(request)
            return response
        except Exception as e:
            logger.error(f"❌ Error processing interactive request: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 500
            
    except Exception as e:
        logger.error(f"❌ Error processing interactive request: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def handle_view_edit_ticket_direct(payload):
    """Handle View & Edit button click"""
    try:
        # Extract data from payload
        user_id = payload['user']['id']
        ticket_id = payload['actions'][0]['value']
        channel_id = payload['channel']['id']
        
        logger.info(f"🔧 Direct handling: View & Edit for ticket {ticket_id} by user {user_id} in channel {channel_id}")

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
                    text="❌ Only channel admins can view or edit tickets."
                )
            except Exception:
                pass
            return jsonify({"ok": False, "error": "not_admin"})
        
        # Get ticket data from sheet
        tickets = slack_handler.ticket_service.get_all_tickets()
        ticket = None
        for t in tickets:
            if str(t.get('ticket_id')) == str(ticket_id):
                ticket = t
                break
        
        if not ticket:
            logger.error(f"❌ Ticket {ticket_id} not found")
            return jsonify({"error": "Ticket not found"}), 404
        
        # Get assignee user ID (default to creator if not set)
        # For now, we'll use the current user as default since we don't have user IDs stored
        assignee_user_id = user_id
        
        # Convert priority to modal format
        priority_mapping = {
            "Critical": "CRITICAL",
            "High": "HIGH", 
            "Medium": "MEDIUM",
            "Low": "LOW"
        }
        modal_priority = priority_mapping.get(ticket.get('priority', 'Medium'), 'MEDIUM')
        
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
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "requester",
                        "label": {
                            "type": "plain_text",
                            "text": "Requester",
                            "emoji": True
                        },
                        "element": {
                            "type": "users_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select requester",
                                "emoji": True
                            },
                            "initial_user": user_id,  # Use current user as default since we don't have stored user IDs
                            "action_id": "requester_select"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "status",
                        "label": {
                            "type": "plain_text",
                            "text": "Status",
                            "emoji": True
                        },
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select status",
                                "emoji": True
                            },
                            "initial_option": {
                                "text": {
                                    "type": "plain_text",
                                    "text": ticket.get("status", "Open")
                                },
                                "value": ticket.get("status", "Open")
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Open"
                                    },
                                    "value": "Open"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Closed"
                                    },
                                    "value": "Closed"
                                }
                            ],
                            "action_id": "status_select"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "assignee",
                        "label": {
                            "type": "plain_text",
                            "text": "Assignee",
                            "emoji": True
                        },
                        "element": {
                            "type": "users_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select assignee",
                                "emoji": True
                            },
                            "initial_user": assignee_user_id,
                            "action_id": "assignee_select"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "priority",
                        "label": {
                            "type": "plain_text",
                            "text": "Priority",
                            "emoji": True
                        },
                        "element": {
                            "type": "static_select",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select priority",
                                "emoji": True
                            },
                            "initial_option": {
                                "text": {
                                    "type": "plain_text",
                                    "text": modal_priority
                                },
                                "value": modal_priority
                            },
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "CRITICAL"
                                    },
                                    "value": "CRITICAL"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "HIGH"
                                    },
                                    "value": "HIGH"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "MEDIUM"
                                    },
                                    "value": "MEDIUM"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "LOW"
                                    },
                                    "value": "LOW"
                                }
                            ],
                            "action_id": "priority_select"
                        }
                    },
                    {
                        "type": "input",
                        "block_id": "description",
                        "label": {
                            "type": "plain_text",
                            "text": "Description",
                            "emoji": True
                        },
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "initial_value": ticket.get("description", ""),
                            "action_id": "description_input"
                        }
                    }
                ],
                "private_metadata": str(ticket_id)
            }
        }
        
        # Open modal using Slack API
        from slack_sdk import WebClient
        client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        
        try:
            response = client.views_open(**modal_payload)
            if response['ok']:
                logger.info(f"Modal opened successfully for ticket {ticket_id}")
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
            client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
            
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"✅ Ticket #{ticket_id} has been closed by <@{user_id}>"
            )
            
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Failed to close ticket"}), 500
                
    except Exception as e:
        logger.error(f"Error in direct close handler: {str(e)}")
        return jsonify({"error": str(e)}), 500

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