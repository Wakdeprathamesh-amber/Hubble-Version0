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
                
                # Handle main channel buttons directly (for performance)
                if action_id == 'view_edit_ticket':
                    return handle_view_edit_ticket_direct(payload)
                elif action_id == 'close_ticket':
                    return handle_close_ticket_direct(payload)
                # For all other actions (including internal channel buttons),
                # fall through to Slack Bolt handler below
                else:
                    logger.info(f"🔄 Delegating action '{action_id}' to Slack Bolt handler")
                    # Don't return 400, let it fall through to Slack Bolt handler
        elif payload.get('type') == 'view_submission':
            # Delegate to Slack Bolt handler which uses dynamic modal system
            logger.info(f"🔧 MODAL SUBMISSION: Delegating to Slack Bolt handler")
            # Let Slack Bolt handler process it
            pass
        
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