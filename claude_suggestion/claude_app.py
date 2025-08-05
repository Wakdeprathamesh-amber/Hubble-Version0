import os
import sys
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from ticket_service import TicketService
from slack_handler import SlackHandler
import logging
import json
from datetime import datetime

# Configure comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Ensure logs go to stdout
        logging.FileHandler('slack_bot.log')  # Also save to file
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Debug: Print environment variables (excluding sensitive values)
logger.info("=== STARTING SLACK BOT APPLICATION ===")
logger.info("Environment Variables Loaded:")
logger.info(f"TARGET_CHANNEL_ID: {os.environ.get('TARGET_CHANNEL_ID')}")
logger.info(f"SLACK_BOT_TOKEN exists: {'Yes' if os.environ.get('SLACK_BOT_TOKEN') else 'No'}")
logger.info(f"SLACK_SIGNING_SECRET exists: {'Yes' if os.environ.get('SLACK_SIGNING_SECRET') else 'No'}")
logger.info(f"PORT: {os.environ.get('PORT', '3000')}")

# Validate required environment variables
required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "TARGET_CHANNEL_ID"]
missing_vars = [var for var in required_vars if not os.environ.get(var)]

if missing_vars:
    logger.error(f"Missing required environment variables: {missing_vars}")
    logger.error("Please check your .env file and ensure all variables are set")
    sys.exit(1)

# Initialize Flask app
app = Flask(__name__)

# Initialize services
logger.info("Initializing services...")
try:
    ticket_service = TicketService()
    logger.info("✓ TicketService initialized")
    
    slack_handler = SlackHandler(ticket_service)
    logger.info("✓ SlackHandler initialized")
except Exception as e:
    logger.error(f"Failed to initialize services: {str(e)}", exc_info=True)
    sys.exit(1)

@app.before_request
def log_request_info():
    """Log all incoming requests"""
    logger.info(f"=== INCOMING REQUEST ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Path: {request.path}")
    logger.info(f"Headers: {dict(request.headers)}")
    if request.method == "POST":
        try:
            if request.content_type == 'application/json':
                logger.info(f"JSON Body: {request.get_json()}")
            else:
                logger.info(f"Raw Body: {request.get_data()}")
        except Exception as e:
            logger.warning(f"Could not log request body: {str(e)}")

@app.route("/slack/events", methods=["GET", "POST"])
def slack_events():
    """Endpoint for Slack events"""
    logger.info("=== SLACK EVENTS ENDPOINT CALLED ===")
    
    try:
        # Handle GET request (for Slack URL verification)
        if request.method == "GET":
            logger.info("Handling GET request for URL verification")
            return jsonify({"status": "ok", "message": "Slack events endpoint is working"})
            
        # Handle POST request (for Slack events)
        logger.info("Processing POST request")
        
        # Get request data
        try:
            json_data = request.get_json()
            if not json_data:
                logger.error("No JSON data received")
                return jsonify({"error": "No JSON data"}), 400
                
            logger.info(f"Received JSON: {json.dumps(json_data, indent=2)}")
            
        except Exception as e:
            logger.error(f"Error parsing JSON: {str(e)}")
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Handle URL verification challenge
        if json_data.get("type") == "url_verification":
            challenge = json_data.get("challenge")
            logger.info(f"URL verification challenge: {challenge}")
            return jsonify({"challenge": challenge})
        
        # Handle event callbacks
        if json_data.get("type") == "event_callback":
            logger.info("Processing event callback")
            event = json_data.get("event", {})
            logger.info(f"Event type: {event.get('type')}")
            logger.info(f"Event data: {json.dumps(event, indent=2)}")
            
            # Check if it's a message event
            if event.get("type") == "message":
                logger.info("Processing message event")
                
                # Extract message details
                channel_id = event.get("channel")
                user_id = event.get("user")
                text = event.get("text", "")
                ts = event.get("ts")
                
                logger.info(f"Message details:")
                logger.info(f"  Channel: {channel_id}")
                logger.info(f"  User: {user_id}")
                logger.info(f"  Text: {text}")
                logger.info(f"  Timestamp: {ts}")
                
                # Check if message is from target channel
                target_channel = os.environ.get("TARGET_CHANNEL_ID")
                logger.info(f"Target channel: {target_channel}")
                
                if channel_id == target_channel:
                    logger.info("Message is from target channel - processing")
                    
                    # Skip bot messages and messages without user
                    if not user_id:
                        logger.info("Skipping message without user ID")
                        return jsonify({"status": "ok"})
                    
                    if event.get("bot_id"):
                        logger.info("Skipping bot message")
                        return jsonify({"status": "ok"})
                    
                    # Create ticket
                    try:
                        ticket_id = ticket_service.create_ticket(
                            message_text=text,
                            requester_id=user_id,
                            timestamp=ts
                        )
                        logger.info(f"Created ticket #{ticket_id}")
                        
                        # Send response via Slack handler
                        response_text = f":ticket: Ticket #{ticket_id} has been created for <@{user_id}>'s request."
                        logger.info(f"Sending response: {response_text}")
                        
                        # Note: In a real implementation, you'd send this back to Slack
                        # For now, we'll just log it
                        logger.info("Ticket created successfully")
                        
                    except Exception as e:
                        logger.error(f"Error creating ticket: {str(e)}", exc_info=True)
                        return jsonify({"error": "Failed to create ticket"}), 500
                        
                else:
                    logger.info(f"Message not from target channel (got: {channel_id}, expected: {target_channel})")
            else:
                logger.info(f"Non-message event type: {event.get('type')}")
        else:
            logger.info(f"Non-event-callback type: {json_data.get('type')}")
        
        # Use the slack_handler for proper event processing
        try:
            logger.info("Delegating to SlackHandler")
            response = slack_handler.handler.handle(request)
            logger.info(f"SlackHandler response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error in SlackHandler: {str(e)}", exc_info=True)
            return jsonify({"status": "ok"})  # Return ok to prevent retries
                
    except Exception as e:
        logger.error(f"Unexpected error in slack_events: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/tickets", methods=["GET"])
def get_tickets():
    """API endpoint to get all tickets"""
    logger.info("Getting all tickets")
    try:
        tickets = ticket_service.get_all_tickets()
        logger.info(f"Returning {len(tickets)} tickets")
        return jsonify(tickets)
    except Exception as e:
        logger.error(f"Error getting tickets: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/test", methods=["GET"])
def test():
    """Test endpoint"""
    logger.info("Test endpoint called")
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "message": "Flask app is running"
    })

@app.route("/test/message", methods=["POST"])
def test_message():
    """Test endpoint for message events"""
    logger.info("Test message endpoint called")
    try:
        data = request.get_json()
        logger.info(f"Test message data: {json.dumps(data, indent=2)}")
        
        # Extract event data
        event = data.get("event", {})
        channel_id = event.get("channel")
        user_id = event.get("user")
        text = event.get("text", "Test message")
        ts = event.get("ts", str(datetime.now().timestamp()))
        
        # Create a ticket
        ticket_id = ticket_service.create_ticket(
            message_text=text,
            requester_id=user_id or "test_user",
            timestamp=ts
        )
        
        logger.info(f"Test ticket #{ticket_id} created")
        
        return jsonify({
            "status": "ok",
            "message": f"Test ticket #{ticket_id} created",
            "ticket_id": ticket_id,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in test message endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    logger.info("Health check called")
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "ticket_service": "ok",
            "slack_handler": "ok"
        }
    })

@app.route("/", methods=["GET"])
def home():
    """Simple home endpoint to verify the server is running"""
    logger.info("Home endpoint called")
    return jsonify({
        "status": "ok", 
        "message": "Fix Kar Slack Bot is running!",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/slack/events (POST) - Slack event handler",
            "/tickets (GET) - Get all tickets",
            "/test (GET) - Test endpoint",
            "/test/message (POST) - Test message processing",
            "/health (GET) - Health check"
        ]
    })

if __name__ == "__main__":
    # Get port from environment variable or use 3000 as default
    port = int(os.environ.get("PORT", 3000))
    
    logger.info(f"=== STARTING FLASK SERVER ===")
    logger.info(f"Port: {port}")
    logger.info(f"Debug mode: True")
    logger.info(f"Host: 0.0.0.0")
    logger.info("Available endpoints:")
    logger.info("  GET  / - Home")
    logger.info("  GET  /health - Health check")  
    logger.info("  GET  /test - Test")
    logger.info("  POST /test/message - Test message")
    logger.info("  GET  /tickets - Get all tickets")
    logger.info("  GET|POST /slack/events - Slack events")
    logger.info("=" * 50)
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=port, debug=True)