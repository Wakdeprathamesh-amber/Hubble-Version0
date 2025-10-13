import os
import json
import logging
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from datetime import datetime
from modal_builder import build_modal_blocks, extract_modal_values
from modal_submission_handler import handle_dynamic_modal_submission
from internal_channel_handler import post_to_internal_channel, update_internal_channel_message

logger = logging.getLogger(__name__)

class SlackHandler:
    def __init__(self, ticket_service):
        self.ticket_service = ticket_service
        
        # Initialize the Slack app with environment variables
        self.slack_app = App(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
            process_before_response=True,
            request_verification_enabled=False  # Disable request verification since we handle it in Flask
        )
        
        # Create request handler for Flask
        self.handler = SlackRequestHandler(self.slack_app)
        
        # Register event listeners and commands
        self._register_listeners()
        self._register_commands()
        
        # Log initialization
        logger.info("SlackHandler initialized with:")
        logger.info(f"Bot Token: {os.environ.get('SLACK_BOT_TOKEN')[:10]}...")
        logger.info(f"Signing Secret: {os.environ.get('SLACK_SIGNING_SECRET')[:10]}...")
        logger.info(f"Target Channel: {os.environ.get('TARGET_CHANNEL_ID')}")
    
    def _is_admin(self, user_id: str) -> bool:
        """
        Check if a user is an admin based on ADMIN_USER_IDS env (comma-separated Slack user IDs).
        """
        try:
            admin_ids = os.environ.get("ADMIN_USER_IDS", "")
            admin_list = [uid.strip() for uid in admin_ids.split(",") if uid.strip()]
            return user_id in admin_list
        except Exception:
            return False

    def _is_channel_admin(self, user_id: str, channel_id: str) -> bool:
        """
        Check if user is an admin for the given channel using Config tab if available; fallback to global env.
        """
        try:
            config_map = self.ticket_service.sheets_service.get_channel_config_map()
            channel_cfg = config_map.get(channel_id)
            if channel_cfg and channel_cfg.get('admin_user_ids'):
                ids = [u.strip() for u in channel_cfg['admin_user_ids'].split(',') if u.strip()]
                return user_id in ids
        except Exception:
            pass
        return self._is_admin(user_id)

    def _register_commands(self):
        @self.slack_app.command("/ticket-status")
        def handle_ticket_status(ack, body, say):
            """Handle /ticket-status command"""
            # Acknowledge the command request
            ack()
            
            try:
                # Parse command text
                text = body.get("text", "").strip()
                if not text:
                    say("Please provide a ticket ID. Usage: /ticket-status TICKET_ID")
                    return
                
                # Get ticket status
                ticket = self.ticket_service.get_ticket(text)
                if not ticket:
                    say(f"❌ Ticket {text} not found")
                    return
                
                # Format response
                response = f"""
:ticket: *Ticket #{ticket['ticket_id']}*
• Status: {ticket['status']}
• Created by: <@{ticket['created_by']}>
• Created at: {ticket['created_at']}
• Priority: {ticket.get('priority', 'Not set')}
• Assignee: {f"<@{ticket['assignee']}>" if ticket.get('assignee') else "Not assigned"}
• Message: {ticket['message']}
"""
                say(response)
            except Exception as e:
                logger.error(f"Error handling ticket status command: {str(e)}", exc_info=True)
                say("❌ An error occurred while fetching the ticket status")
        
        @self.slack_app.command("/update-ticket")
        def handle_update_ticket(ack, body, say):
            """Handle /update-ticket command"""
            # Acknowledge the command request
            ack()
            
            try:
                # Parse command text
                text = body.get("text", "").strip()
                parts = text.split()
                if len(parts) < 2:
                    say("Please provide ticket ID and new status. Usage: /update-ticket TICKET_ID STATUS")
                    return
                
                ticket_id = parts[0]
                new_status = " ".join(parts[1:])
                
                # Update ticket status
                success = self.ticket_service.update_ticket_status(ticket_id, new_status)
                if success:
                    say(f"✅ Ticket #{ticket_id} status updated to: {new_status}")
                else:
                    say(f"❌ Failed to update ticket #{ticket_id}")
            except Exception as e:
                logger.error(f"Error handling update ticket command: {str(e)}", exc_info=True)
                say("❌ An error occurred while updating the ticket")
        
        @self.slack_app.command("/assign-ticket")
        def handle_assign_ticket(ack, body, say):
            """Handle /assign-ticket command"""
            # Acknowledge the command request
            ack()
            
            try:
                # Parse command text
                text = body.get("text", "").strip()
                parts = text.split()
                if len(parts) < 2:
                    say("Please provide ticket ID and assignee. Usage: /assign-ticket TICKET_ID @USER")
                    return
                
                ticket_id = parts[0]
                assignee = parts[1].strip("<@>")
                
                # Update ticket assignee (pass assignee as both display and user_id)
                success = self.ticket_service.update_ticket_assignee(
                    ticket_id=ticket_id,
                    assignee_id=assignee,
                    user_id=assignee if assignee.startswith('U') else None
                )
                if success:
                    say(f"✅ Ticket #{ticket_id} assigned to <@{assignee}>")
                else:
                    say(f"❌ Failed to assign ticket #{ticket_id}")
            except Exception as e:
                logger.error(f"Error handling assign ticket command: {str(e)}", exc_info=True)
                say("❌ An error occurred while assigning the ticket")
    
    def _register_listeners(self):
        @self.slack_app.event("message")
        def handle_message_events(body, say, logger):
            try:
                # Extract event data
                event = body.get("event", {})
                channel_id = event.get("channel")
                user_id = event.get("user")
                text = event.get("text", "")
                ts = event.get("ts")
                thread_ts = event.get("thread_ts")  # Check if this is a thread reply
                subtype = event.get("subtype")
                
                # Skip if this is a bot message
                if event.get("bot_id"):
                    return
                
                # Ignore message subtypes like edits or joins to avoid false ticket creation
                if subtype:
                    logger.debug(f"Ignoring message with subtype={subtype}")
                    return
                
                # Check if this channel is an internal visualization channel
                # Internal channels should NOT create tickets
                is_internal_channel = False
                try:
                    cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                    for main_channel_id, config in cfg_map.items():
                        internal_ch_id = config.get('internal_channel_id', '').strip()
                        if internal_ch_id == channel_id:
                            is_internal_channel = True
                            logger.info(f"📊 Message in internal channel {channel_id} - skipping ticket creation")
                            break
                except Exception as e:
                    logger.error(f"Error checking if internal channel: {str(e)}")
                
                # Handle thread replies in internal channels - forward to main channel
                if is_internal_channel and thread_ts:
                    logger.info(f"🧵 INTERNAL THREAD REPLY: Channel={channel_id}, User={user_id}, Thread={thread_ts}")
                    
                    # Find ticket by internal_message_ts matching the thread_ts
                    tickets = self.ticket_service.get_all_tickets()
                    matching_ticket = None
                    
                    for ticket in tickets:
                        internal_msg_ts = ticket.get('internal_message_ts', '').strip()
                        if internal_msg_ts == thread_ts:
                            matching_ticket = ticket
                            logger.info(f"✅ Found matching ticket #{ticket['ticket_id']} for internal thread {thread_ts}")
                            break
                    
                    if matching_ticket:
                        # Get user's name for display
                        user_name = "Unknown"
                        try:
                            user_info = self.slack_app.client.users_info(user=user_id)
                            if user_info["ok"]:
                                user_name = user_info["user"].get("real_name", user_info["user"].get("name", "Unknown"))
                        except Exception as e:
                            logger.error(f"Error getting user name: {str(e)}")
                        
                        # Get the main channel thread_ts from the ticket
                        main_channel_id = matching_ticket.get('channel_id', '')
                        thread_link = matching_ticket.get('thread_link', '')
                        
                        # Extract thread_ts from thread_link
                        main_thread_ts = None
                        if thread_link and "/p" in thread_link:
                            timestamp_part = thread_link.split("/p")[-1]
                            if len(timestamp_part) >= 10:
                                main_thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                        
                        # If we couldn't get from thread_link, try thread_ts field
                        if not main_thread_ts:
                            main_thread_ts = matching_ticket.get('thread_ts', '')
                        
                        if main_channel_id and main_thread_ts:
                            # Forward the reply to main channel thread
                            try:
                                forward_text = f"💬 *{user_name}* (from internal team):\n{text}"
                                self.slack_app.client.chat_postMessage(
                                    channel=main_channel_id,
                                    thread_ts=main_thread_ts,
                                    text=forward_text
                                )
                                logger.info(f"✅ Forwarded internal reply to main channel thread")
                            except Exception as e:
                                logger.error(f"❌ Error forwarding reply to main channel: {str(e)}", exc_info=True)
                        else:
                            logger.warning(f"⚠️ Could not determine main channel thread (channel={main_channel_id}, thread_ts={main_thread_ts})")
                    else:
                        logger.warning(f"⚠️ No ticket found for internal thread {thread_ts}")
                    
                    # Don't create a ticket - just return after handling the reply
                    return
                
                # Check if this is a channel message (not DM, not group DM, not internal channel)
                # The bot will work in any channel it's invited to
                # Only create tickets for top-level messages (not thread replies)
                if (
                    not channel_id.startswith('D')
                    and not channel_id.startswith('G')
                    and not is_internal_channel  # NEW: Don't create tickets in internal channels
                    and user_id
                    and text
                    and not thread_ts  # ensure this is not a reply in a thread
                ):
                    logger.info(f"🎫 CREATING TICKET: Channel={channel_id}, User={user_id}")
                    
                    # Get user's real name from Slack
                    user_name = f"@{user_id}"  # Default fallback
                    try:
                        user_info = self.slack_app.client.users_info(user=user_id)
                        if user_info["ok"]:
                            user = user_info["user"]
                            real_name = user.get("real_name", user.get("name", f"@{user_id}"))
                            user_name = f"@{real_name}"  # Add @ symbol
                        logger.info(f"🎫 USER NAME: {user_name}")
                    except Exception as e:
                        logger.error(f"❌ Error getting user name: {str(e)}")
                    
                    # Create a ticket
                    ticket_id = self.ticket_service.create_ticket(
                        message_text=text,
                        requester_id=user_id,
                        requester_name=user_name,  # Pass the real name
                        timestamp=ts,
                        thread_ts=ts,  # Use the message timestamp as thread_ts for the new thread root
                        channel_id=channel_id,
                        priority='Medium'
                    )
                    
                    # Send confirmation message with ticket details in a thread
                    response = f"""
:ticket: *Ticket #{ticket_id} has been created*

**Hubble has logged your ticket.**
We've recorded the details and notified the relevant team. You can track progress right here in this thread.

🔍 Use the button below to view or update ticket information - including status, assignee, and priority.
"""
                    
                    # Load channel-specific priorities if configured
                    try:
                        cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                        cfg = cfg_map.get(channel_id, {})
                        priorities_csv = cfg.get('priorities', '')
                        if priorities_csv:
                            priorities = [p.strip() for p in priorities_csv.split(',') if p.strip()]
                        else:
                            priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                    except Exception:
                        priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

                    # Create buttons for ticket actions
                    blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": response
                            }
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "View & Edit Ticket"
                                    },
                                    "style": "primary",
                                    "action_id": "view_edit_ticket",
                                    "value": ticket_id
                                },
                                {
                                    "type": "button",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "Close Ticket"
                                    },
                                    "style": "danger",
                                    "action_id": "close_ticket",
                                    "value": ticket_id
                                }
                            ]
                        }
                    ]
                    
                    # Send the response in a thread
                    say(
                        text=response,
                        blocks=blocks,
                        thread_ts=ts
                    )
                    
                    logger.info(f"✅ Ticket #{ticket_id} created successfully in channel {channel_id}")
                    
                    # Post to internal channel if configured
                    try:
                        cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                        cfg = cfg_map.get(channel_id, {})
                        internal_channel_id = cfg.get('internal_channel_id', '').strip()
                        
                        if internal_channel_id:
                            logger.info(f"📊 Posting ticket #{ticket_id} to internal channel {internal_channel_id}")
                            
                            # Get the ticket data
                            ticket = self.ticket_service.get_ticket(ticket_id)
                            if ticket:
                                # Get modal template fields
                                template_key = cfg.get('modal_template_key', 'tech_default')
                                fields = self.ticket_service.sheets_service.get_modal_template(template_key)
                                
                                # Post to internal channel
                                internal_message_ts = post_to_internal_channel(
                                    client=self.slack_app.client,
                                    internal_channel_id=internal_channel_id,
                                    ticket=ticket,
                                    fields=fields or []
                                )
                                
                                if internal_message_ts:
                                    # Store the internal message timestamp
                                    self.ticket_service.sheets_service.update_internal_message_ts(
                                        ticket_id=ticket_id,
                                        internal_message_ts=internal_message_ts
                                    )
                                    logger.info(f"✅ Posted ticket #{ticket_id} to internal channel")
                                else:
                                    logger.warning(f"⚠️ Failed to post ticket #{ticket_id} to internal channel")
                        else:
                            logger.debug(f"No internal channel configured for channel {channel_id}")
                    except Exception as e:
                        logger.error(f"❌ Error posting to internal channel: {str(e)}", exc_info=True)
                
                # Handle thread replies (update first response + forward to internal channel)
                elif thread_ts:
                    logger.info(f"🧵 THREAD REPLY: Channel={channel_id}, User={user_id}")
                    
                    # Get the ticket for this thread
                    tickets = self.ticket_service.get_all_tickets()
                    ticket = None
                    for t in tickets:
                        # Check if this thread matches the ticket's thread_ts
                        # The thread_ts in the sheet might be stored differently
                        ticket_thread_ts = t.get("thread_ts", "")
                        if ticket_thread_ts == thread_ts or ticket_thread_ts == thread_ts.replace('.', ''):
                            ticket = t
                            break
                    
                    # If still not found, try to find by thread link
                    if not ticket:
                        for t in tickets:
                            thread_link = t.get("thread_link", "")
                            if thread_link and thread_ts.replace('.', '') in thread_link:
                                ticket = t
                                break
                    
                    if ticket and not ticket.get("first_response"):
                        logger.info(f"🎯 FIRST RESPONSE: Updating ticket {ticket['ticket_id']} with first response")
                        # Update the ticket with the first response
                        success = self.ticket_service.update_ticket_first_response(
                            ticket_id=ticket["ticket_id"],
                            response_text=event.get("text", ""),
                            responder_id=event.get("user")
                        )
                        
                        if success:
                            # Notify in thread
                            say(
                                text=f"✅ First response recorded for Ticket #{ticket['ticket_id']}",
                                thread_ts=thread_ts
                            )
                        else:
                            logger.error(f"❌ Failed to update first response for ticket {ticket['ticket_id']}")
                    elif ticket and ticket.get("first_response"):
                        logger.info(f"ℹ️ Ticket {ticket['ticket_id']} already has first response")
                    else:
                        logger.warning(f"⚠️ No ticket found for thread_ts: {thread_ts}")
                    
                    # Forward main channel thread reply to internal channel (if configured)
                    if ticket:
                        try:
                            cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                            cfg = cfg_map.get(channel_id, {})
                            internal_channel_id = cfg.get('internal_channel_id', '').strip()
                            internal_message_ts = ticket.get('internal_message_ts', '').strip()
                            
                            if internal_channel_id and internal_message_ts:
                                # Get user's name for display
                                user_name = "Unknown"
                                try:
                                    user_info = self.slack_app.client.users_info(user=user_id)
                                    if user_info["ok"]:
                                        user_name = user_info["user"].get("real_name", user_info["user"].get("name", "Unknown"))
                                except Exception as e:
                                    logger.error(f"Error getting user name: {str(e)}")
                                
                                # Forward to internal channel thread
                                forward_text = f"💬 *{user_name}* (from main channel):\n{text}"
                                self.slack_app.client.chat_postMessage(
                                    channel=internal_channel_id,
                                    thread_ts=internal_message_ts,
                                    text=forward_text
                                )
                                logger.info(f"✅ Forwarded main channel reply to internal channel thread")
                        except Exception as e:
                            logger.error(f"❌ Error forwarding reply to internal channel: {str(e)}", exc_info=True)
                    
            except Exception as e:
                logger.error(f"❌ Error handling message event: {str(e)}", exc_info=True)
                raise

        # Add action handler for the Close Ticket button
        @self.slack_app.action("close_ticket")
        def handle_close_ticket(ack, body, say):
            try:
                # Acknowledge the action
                ack()
                
                # Get ticket ID from button value
                ticket_id = body["actions"][0]["value"]
                user_id = body["user"]["id"]
                
                # Permission check: only admins can close
                if not self._is_channel_admin(user_id, body.get("channel", {}).get("id")):
                    try:
                        say(
                            text="❌ Only admins can close tickets.",
                            channel=body.get("channel", {}).get("id"),
                            user=user_id,
                            thread_ts=body.get("message", {}).get("thread_ts") or body.get("message", {}).get("ts")
                        )
                    except Exception:
                        pass
                    return

                logger.info(f"🔧 CLOSE TICKET: Ticket {ticket_id} by user {user_id}")
                
                # Get thread_ts from the message
                thread_ts = body.get("message", {}).get("thread_ts")
                if not thread_ts:
                    # If no thread_ts in message, try to get it from the message timestamp
                    thread_ts = body.get("message", {}).get("ts")
                
                # Update ticket status and set resolved_at timestamp
                logger.info(f"🔧 UPDATING STATUS: Calling update_ticket_status for ticket {ticket_id}")
                success = self.ticket_service.update_ticket_status(ticket_id, "Closed")
                logger.info(f"🔧 UPDATE RESULT: Success = {success}")
                
                if success:
                    # Update the message to show ticket is closed
                    if thread_ts:
                        say(
                            text=f"✅ Ticket #{ticket_id} has been closed by <@{user_id}>",
                            thread_ts=thread_ts
                        )
                    else:
                        say(
                            text=f"✅ Ticket #{ticket_id} has been closed by <@{user_id}>"
                        )
                else:
                    if thread_ts:
                        say(
                            text=f"❌ Failed to close ticket #{ticket_id}",
                            thread_ts=thread_ts
                        )
                    else:
                        say(
                            text=f"❌ Failed to close ticket #{ticket_id}"
                        )
            except Exception as e:
                logger.error(f"Error handling close ticket action: {str(e)}", exc_info=True)
                # Try to send error message
                try:
                    thread_ts = body.get("message", {}).get("thread_ts")
                    if thread_ts:
                        say(
                            text="❌ An error occurred while closing the ticket",
                            thread_ts=thread_ts
                        )
                    else:
                        say(
                            text="❌ An error occurred while closing the ticket"
                        )
                except:
                    pass  # If we can't send error message, just log it

        # Add action handler for the View & Edit button
        @self.slack_app.action("view_edit_ticket")
        def handle_view_edit_ticket(ack, body, client):
            try:
                # Acknowledge the action
                ack()
                
                # Get ticket ID from button value
                ticket_id = body["actions"][0]["value"]
                user_id = body["user"]["id"]
                channel_id = body["channel"]["id"]
                
                logger.info(f"View & Edit button clicked for ticket {ticket_id} by user {user_id}")
                
                # Check if user has permission (admin only)
                if not self._is_channel_admin(user_id, channel_id):
                    try:
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text="❌ Only admins can view or edit tickets."
                        )
                    except Exception:
                        pass
                    return
                
                # Get ticket data
                ticket = self.ticket_service.get_ticket(ticket_id)
                if not ticket:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"❌ Ticket #{ticket_id} not found."
                    )
                    return
                
                # Get modal template for this channel
                cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(ticket.get('channel_id', channel_id), {})
                template_key = cfg.get('modal_template_key', 'tech_default')
                
                logger.info(f"Loading modal template: {template_key} for ticket {ticket_id}")
                
                # Load field definitions from Modal Templates sheet
                fields = self.ticket_service.sheets_service.get_modal_template(template_key)
                
                if not fields:
                    logger.error(f"No fields found for template '{template_key}'")
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"❌ Modal template '{template_key}' not found. Please check Modal Templates sheet."
                    )
                    return
                
                # Build modal blocks dynamically
                modal_blocks = build_modal_blocks(fields, ticket)
                
                # Store template_key and channel_id in metadata
                metadata = json.dumps({
                    'ticket_id': ticket_id,
                    'template_key': template_key,
                    'channel_id': ticket.get('channel_id', channel_id)
                })
                
                modal = {
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
                
                # Open the modal
                try:
                    response = client.views_open(
                        trigger_id=body["trigger_id"],
                        view=modal
                    )
                    
                    if response["ok"]:
                        logger.info(f"Dynamic modal opened successfully for ticket {ticket_id}")
                    else:
                        logger.error(f"Failed to open modal: {response.get('error')}")
                        
                except Exception as e:
                    logger.error(f"Error opening modal: {str(e)}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error handling view edit ticket action: {str(e)}", exc_info=True)
                try:
                    client.chat_postEphemeral(
                        channel=body["channel"]["id"],
                        user=user_id,
                        text="❌ An error occurred while processing the request."
                    )
                except:
                    pass

        # Add modal submission handler
        @self.slack_app.view("ticket_edit_modal")
        def handle_modal_submission_wrapper(ack, body, view, logger):
            """Handle modal submission for ticket editing - delegates to dynamic handler"""
            handle_dynamic_modal_submission(ack, body, view, self)
        
        # ========== INTERNAL CHANNEL BUTTON HANDLERS ==========
        
        @self.slack_app.action("internal_view_edit")
        def handle_internal_view_edit(ack, body, client):
            """Handle View/Edit button from internal channel"""
            try:
                ack()
                
                ticket_id = body["actions"][0]["value"]
                user_id = body["user"]["id"]
                channel_id = body["channel"]["id"]  # This is the internal channel
                
                logger.info(f"📊 Internal channel: View/Edit for ticket {ticket_id}")
                
                # Get ticket data
                ticket = self.ticket_service.get_ticket(ticket_id)
                if not ticket:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"❌ Ticket #{ticket_id} not found."
                    )
                    return
                
                # Get modal template
                original_channel_id = ticket.get('channel_id', '')
                cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                cfg = cfg_map.get(original_channel_id, {})
                template_key = cfg.get('modal_template_key', 'tech_default')
                
                fields = self.ticket_service.sheets_service.get_modal_template(template_key)
                if not fields:
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"❌ Modal template not found."
                    )
                    return
                
                # Build modal
                modal_blocks = build_modal_blocks(fields, ticket)
                metadata = json.dumps({
                    'ticket_id': ticket_id,
                    'template_key': template_key,
                    'channel_id': original_channel_id
                })
                
                modal = {
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
                
                client.views_open(trigger_id=body["trigger_id"], view=modal)
                logger.info(f"✅ Opened edit modal from internal channel")
                
            except Exception as e:
                logger.error(f"❌ Error handling internal view/edit: {str(e)}", exc_info=True)
        
        @self.slack_app.action("internal_assign_me")
        def handle_internal_assign_me(ack, body, client):
            """Handle Assign to Me button from internal channel"""
            try:
                ack()
                
                ticket_id = body["actions"][0]["value"]
                user_id = body["user"]["id"]
                channel_id = body["channel"]["id"]
                
                logger.info(f"📊 Internal channel: Assign to Me for ticket {ticket_id}")
                
                # Get user's name
                user_name = self._get_user_name(client, user_id)
                assignee_display = f"@{user_name}"
                
                # Update ticket assignee (also store user_id for modal pre-fill)
                success = self.ticket_service.sheets_service.update_ticket_assignee(
                    ticket_id=ticket_id,
                    assignee_id=assignee_display,
                    user_id=user_id
                )
                
                if success:
                    # Get updated ticket
                    ticket = self.ticket_service.get_ticket(ticket_id)
                    if ticket:
                        # Update internal channel message
                        internal_message_ts = ticket.get('internal_message_ts', '').strip()
                        original_channel_id = ticket.get('channel_id', '')
                        
                        cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                        cfg = cfg_map.get(original_channel_id, {})
                        template_key = cfg.get('modal_template_key', 'tech_default')
                        fields = self.ticket_service.sheets_service.get_modal_template(template_key)
                        
                        if internal_message_ts:
                            update_internal_channel_message(
                                client=client,
                                internal_channel_id=channel_id,
                                message_ts=internal_message_ts,
                                ticket=ticket,
                                fields=fields or []
                            )
                        
                        # Also post to original thread
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
                else:
                    logger.error(f"❌ Failed to assign ticket {ticket_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error handling internal assign me: {str(e)}", exc_info=True)
        
        @self.slack_app.action("internal_change_status")
        def handle_internal_change_status(ack, body, client):
            """Handle Change Status button from internal channel"""
            try:
                ack()
                
                ticket_id = body["actions"][0]["value"]
                user_id = body["user"]["id"]
                channel_id = body["channel"]["id"]
                
                logger.info(f"📊 Internal channel: Change Status for ticket {ticket_id}")
                
                # Get current ticket
                ticket = self.ticket_service.get_ticket(ticket_id)
                if not ticket:
                    return
                
                current_status = ticket.get('status', 'Open')
                new_status = "Closed" if current_status == "Open" else "Open"
                
                # Update status
                success = self.ticket_service.update_ticket_status(ticket_id, new_status)
                
                if success:
                    # Get updated ticket
                    updated_ticket = self.ticket_service.get_ticket(ticket_id)
                    if updated_ticket:
                        # Update internal channel message
                        internal_message_ts = updated_ticket.get('internal_message_ts', '').strip()
                        original_channel_id = updated_ticket.get('channel_id', '')
                        
                        cfg_map = self.ticket_service.sheets_service.get_channel_config_map()
                        cfg = cfg_map.get(original_channel_id, {})
                        template_key = cfg.get('modal_template_key', 'tech_default')
                        fields = self.ticket_service.sheets_service.get_modal_template(template_key)
                        
                        if internal_message_ts:
                            update_internal_channel_message(
                                client=client,
                                internal_channel_id=channel_id,
                                message_ts=internal_message_ts,
                                ticket=updated_ticket,
                                fields=fields or []
                            )
                        
                        # Also post to original thread
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
                else:
                    logger.error(f"❌ Failed to change status for ticket {ticket_id}")
                    
            except Exception as e:
                logger.error(f"❌ Error handling internal change status: {str(e)}", exc_info=True)

    def _has_edit_permission(self, user_id: str, channel_id: str) -> bool:
        """
        Check if user has permission to edit tickets (channel owner or admin).
        
        Args:
            user_id (str): The user ID to check
            channel_id (str): The channel ID
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        try:
            # Get channel info
            channel_info = self.slack_app.client.conversations_info(channel=channel_id)
            channel = channel_info["channel"]
            
            # Check if user is channel owner
            if channel.get("creator") == user_id:
                return True
            
            # Check if user is workspace admin (you might want to add more specific checks)
            # For now, we'll allow channel members to edit (you can make this more restrictive)
            return True
            
        except Exception as e:
            logger.error(f"Error checking edit permission: {str(e)}")
            return False

    def _get_user_name(self, client, user_id: str) -> str:
        """
        Get user's real name from Slack.
        
        Args:
            client: Slack client
            user_id (str): The user ID
            
        Returns:
            str: User's real name or display name
        """
        try:
            user_info = client.users_info(user=user_id)
            user = user_info["user"]
            return user.get("real_name", user.get("display_name", user.get("name", "Unknown")))
        except Exception as e:
            logger.error(f"Error getting user name: {str(e)}")
            return "Unknown"
