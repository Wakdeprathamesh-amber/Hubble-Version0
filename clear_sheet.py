#!/usr/bin/env python3
"""
Script to clear all data from the Google Sheet and reset with new headers.
"""

import os
from dotenv import load_dotenv
from ticket_service import TicketService

def main():
    # Load environment variables
    load_dotenv()
    
    print("🧹 Clearing Google Sheet Data")
    print("=" * 50)
    
    try:
        # Initialize ticket service
        ticket_service = TicketService()
        
        # Clear all tickets
        success = ticket_service.clear_all_tickets()
        
        if success:
            print("✅ Sheet cleared successfully!")
            print("📋 New headers have been set up:")
            print("   A: Ticket ID")
            print("   B: Thread Link")
            print("   C: Requester")
            print("   D: Status")
            print("   E: Priority")
            print("   F: Assignee")
            print("   G: Thread Created At TS")
            print("   H: First Response Time")
            print("   I: Resolved At")
            print("   J: Message")
            print("\n🚀 Ready for fresh testing!")
        else:
            print("❌ Failed to clear sheet data")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main() 