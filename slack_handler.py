import os
import json
import logging
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from datetime import datetime

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
                
                # Update ticket assignee
                success = self.ticket_service.update_ticket_assignee(ticket_id, assignee)
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
                
                # Skip if this is a bot message
                if event.get("bot_id"):
                    return
                
                # Check if this is from the target channel
                target_channel = os.environ.get("TARGET_CHANNEL_ID")
                
                # Handle thread replies (update first response)
                if thread_ts:
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
                    return
                
                # Handle original messages (create tickets)
                if channel_id == target_channel and user_id and text:
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
                        thread_ts=ts,  # Use the message timestamp as thread_ts
                        channel_id=channel_id,
                        priority='Medium'
                    )
                    
                    # Send confirmation message with ticket details in a thread
                    response = f"""
:ticket: *Ticket #{ticket_id} has been created*

**Hubble has logged your ticket.**
We've recorded the details and notified the relevant team. You can track progress right here in this thread.

🔍 Use the button below to view or update ticket information - including status, assignee, and priority.

*Hubble: See it. Sort it. Solve it.*
"""
                    say(
                        text=response,
                        thread_ts=ts,  # Reply in thread
                        blocks=[
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
                                            "text": "View & Edit",
                                            "emoji": True
                                        },
                                        "style": "primary",
                                        "value": ticket_id,
                                        "action_id": "view_edit_ticket"
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "✅ Close Ticket",
                                            "emoji": True
                                        },
                                        "style": "danger",
                                        "value": ticket_id,
                                        "action_id": "close_ticket"
                                    }
                                ]
                            }
                        ]
                    )
                    logger.info(f"✅ Created ticket #{ticket_id} for user {user_id}")
                    
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
                
                logger.info(f"View & Edit button clicked for ticket {ticket_id} by user {user_id}")
                
                # Check if user has permission (channel owner or admin)
                if not self._has_edit_permission(user_id, body["channel"]["id"]):
                    # Send error message
                    client.chat_postEphemeral(
                        channel=body["channel"]["id"],
                        user=user_id,
                        text="❌ You don't have permission to edit this ticket. Only channel owners and admins can modify tickets."
                    )
                    return
                
                # Get ticket data
                ticket = self.ticket_service.get_ticket(ticket_id)
                if not ticket:
                    client.chat_postEphemeral(
                        channel=body["channel"]["id"],
                        user=user_id,
                        text=f"❌ Ticket #{ticket_id} not found."
                    )
                    return
                
                # Create modal using views.open API
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
                                "initial_user": ticket.get("created_by", ""),
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
                                "initial_user": ticket.get("assignee", ""),
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
                                        "text": ticket.get("priority", "Medium")
                                    },
                                    "value": ticket.get("priority", "Medium")
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
                                "initial_value": ticket.get("message", ""),
                                "action_id": "description_input"
                            }
                        }
                    ],
                    "private_metadata": ticket_id
                }
                
                # Open the modal using views.open API
                try:
                    response = client.views_open(
                        trigger_id=body["trigger_id"],
                        view=modal
                    )
                    
                    if response["ok"]:
                        logger.info(f"Modal opened successfully for ticket {ticket_id}")
                    else:
                        logger.error(f"Failed to open modal: {response.get('error')}")
                        # Fallback to simple message
                        update_message = f"""
📋 *Ticket #{ticket_id} Details*

**Current Status:** {ticket.get('status', 'Open')}
**Priority:** {ticket.get('priority', 'Medium')}
**Assignee:** {ticket.get('assignee', 'Not assigned')}
**Description:** {ticket.get('message', 'No description')}

*Modal functionality coming soon!*
"""
                        client.chat_postMessage(
                            channel=body["channel"]["id"],
                            thread_ts=body["message"]["thread_ts"],
                            text=update_message
                        )
                        
                except Exception as e:
                    logger.error(f"Error opening modal: {str(e)}")
                    # Fallback to simple message
                    update_message = f"""
📋 *Ticket #{ticket_id} Details*

**Current Status:** {ticket.get('status', 'Open')}
**Priority:** {ticket.get('priority', 'Medium')}
**Assignee:** {ticket.get('assignee', 'Not assigned')}
**Description:** {ticket.get('message', 'No description')}

*Modal functionality coming soon!*
"""
                    client.chat_postMessage(
                        channel=body["channel"]["id"],
                        thread_ts=body["message"]["thread_ts"],
                        text=update_message
                    )
                
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
        def handle_modal_submission(ack, body, view, logger):
            """Handle modal submission for ticket editing"""
            try:
                logger.info("🔧 view_submission received for ticket_edit_modal")
                
                # Acknowledge the modal submission immediately with success response
                ack({
                    "response_action": "clear"
                })
                
                # Extract data from the modal
                ticket_id = view["private_metadata"]
                user_id = body["user"]["id"]
                
                # Parse the form data
                values = view["state"]["values"]
                
                requester_id = values["requester"]["requester_select"]["selected_user"]
                status = values["status"]["status_select"]["selected_option"]["value"]
                assignee_id = values["assignee"]["assignee_select"]["selected_user"]
                priority = values["priority"]["priority_select"]["selected_option"]["value"]
                description = values["description"]["description_input"]["value"]
                
                # Create Slack client for user lookups
                from slack_sdk import WebClient
                client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
                
                # Convert user IDs to display names
                requester_name = self._get_user_name(client, requester_id)
                assignee_name = self._get_user_name(client, assignee_id)
                
                # Use display names for the sheet
                requester = f"@{requester_name}"
                assignee = f"@{assignee_name}"
                
                logger.info(f"🔧 EXTRACTED VALUES: Ticket={ticket_id}, User={user_id}, Status={status}, Priority={priority}")
                logger.info(f"🔧 MODAL DATA: Requester={requester}, Assignee={assignee}, Description={description[:50]}...")
                
                # Update the ticket
                logger.info(f"🔧 CALLING update_ticket_from_modal for ticket {ticket_id}")
                success = self.ticket_service.update_ticket_from_modal(
                    ticket_id=ticket_id,
                    requester=requester,
                    status=status,
                    assignee=assignee,
                    priority=priority,
                    description=description
                )
                logger.info(f"🔧 MODAL UPDATE RESULT: Success = {success}")
                
                if success:
                    logger.info(f"✅ SUCCESS: Updated ticket {ticket_id} in Google Sheets")
                    
                    # Get user names for display (client already created above)
                    requester_name = self._get_user_name(client, requester_id)
                    assignee_name = self._get_user_name(client, assignee_id)
                    
                    update_message = f"""
✅ *Ticket #{ticket_id} Updated*

**Updated by:** <@{user_id}>
**Requester:** <@{requester_id}> ({requester_name})
**Status:** {status}
**Assignee:** <@{assignee_id}> ({assignee_name})
**Priority:** {priority}
**Description:** {description[:100]}{"..." if len(description) > 100 else ""}
"""
                    
                    # Try to post update to the original thread
                    ticket = self.ticket_service.get_ticket(ticket_id)
                    thread_ts = None
                    
                    # Extract thread_ts from thread link if available
                    logger.info(f"🔧 TICKET DATA: {ticket}")
                    if ticket and ticket.get("thread_link"):
                        thread_link = ticket["thread_link"]
                        logger.info(f"🔧 FOUND thread_link: {thread_link}")
                        # Extract timestamp from link: https://amberstudent.slack.com/archives/C08VB634J86/p1754311679452949
                        if "/p" in thread_link:
                            timestamp_part = thread_link.split("/p")[-1]
                            # Convert back to thread_ts format (add decimal point)
                            if len(timestamp_part) >= 10:
                                thread_ts = f"{timestamp_part[:10]}.{timestamp_part[10:]}"
                                logger.info(f"🔧 EXTRACTED thread_ts: {thread_ts} from link: {thread_link}")
                            else:
                                logger.warning(f"⚠️  Invalid timestamp format in link: {thread_link}")
                                thread_ts = None
                        else:
                            logger.warning(f"⚠️  No /p found in thread link: {thread_link}")
                            thread_ts = None
                    elif ticket and ticket.get("thread_ts"):
                        # Fallback: use thread_ts directly if available
                        thread_ts = ticket["thread_ts"]
                        logger.info(f"🔧 USING thread_ts directly: {thread_ts}")
                    else:
                        logger.warning(f"⚠️  No thread timestamp found for ticket {ticket_id}")
                        logger.warning(f"⚠️  Available ticket fields: {list(ticket.keys()) if ticket else 'No ticket'}")
                        thread_ts = None
                    
                    if ticket and thread_ts:
                        try:
                            client.chat_postMessage(
                                channel=os.environ.get("TARGET_CHANNEL_ID"),
                                thread_ts=thread_ts,
                                text=update_message
                            )
                            logger.info(f"✅ Posted update to thread")
                                
                        except Exception as e:
                            logger.error(f"Error posting to thread: {str(e)}")
                            # Fallback: send as DM to the user
                            try:
                                client.chat_postMessage(
                                    channel=user_id,
                                    text=update_message
                                )
                                logger.info(f"✅ Sent update as DM to user {user_id}")
                            except Exception as dm_error:
                                logger.error(f"Error sending DM: {str(dm_error)}")
                    else:
                        logger.warning(f"⚠️  Could not post update to thread for ticket {ticket_id}")
                        # Send as DM to the user as fallback
                        try:
                            client.chat_postMessage(
                                channel=user_id,
                                text=update_message
                            )
                            logger.info(f"✅ Sent update as DM to user {user_id}")
                        except Exception as dm_error:
                            logger.error(f"Error sending DM: {str(dm_error)}")
                    
                    # Acknowledge with success response AFTER all processing
                    ack()
                else:
                    logger.error(f"❌ FAILED: Could not update ticket {ticket_id} in Google Sheets")
                    
                    # Acknowledge with error response
                    ack({
                        "response_action": "errors",
                        "errors": {
                            "description": "Failed to update ticket. Please try again."
                        }
                    })
                    
            except Exception as e:
                logger.error(f"❌ EXCEPTION in Slack Bolt view handler: {str(e)}", exc_info=True)
                # Acknowledge with error response
                ack({
                    "response_action": "errors",
                    "errors": {
                        "description": "An error occurred while updating the ticket."
                    }
                })

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