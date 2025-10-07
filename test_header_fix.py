#!/usr/bin/env python3
"""
Test script to verify the header setup fix doesn't delete data.
"""

import os
from dotenv import load_dotenv
from sheets_service import SheetsService

def main():
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing Header Setup Fix")
    print("=" * 60)
    
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    
    if not spreadsheet_id:
        print("❌ Error: GOOGLE_SPREADSHEET_ID not set")
        return
    
    try:
        print("\n1️⃣ Initializing SheetsService...")
        sheets_service = SheetsService(credentials_path, spreadsheet_id)
        print("✅ SheetsService initialized")
        
        print("\n2️⃣ Checking existing tickets...")
        tickets = sheets_service.get_tickets()
        print(f"✅ Found {len(tickets)} tickets in the sheet")
        
        if len(tickets) > 0:
            print("\n📋 Sample tickets:")
            for i, ticket in enumerate(tickets[:3]):  # Show first 3
                print(f"   Ticket #{ticket['ticket_id']}: {ticket.get('status', 'N/A')} - {ticket.get('message', '')[:50]}...")
        
        print("\n3️⃣ Re-initializing SheetsService (simulating app restart)...")
        sheets_service2 = SheetsService(credentials_path, spreadsheet_id)
        print("✅ SheetsService re-initialized")
        
        print("\n4️⃣ Checking tickets again...")
        tickets_after = sheets_service2.get_tickets()
        print(f"✅ Found {len(tickets_after)} tickets in the sheet")
        
        if len(tickets) == len(tickets_after):
            print("\n✅ SUCCESS! No data was lost during re-initialization")
            print(f"   Before: {len(tickets)} tickets")
            print(f"   After:  {len(tickets_after)} tickets")
        else:
            print(f"\n⚠️ WARNING! Ticket count changed!")
            print(f"   Before: {len(tickets)} tickets")
            print(f"   After:  {len(tickets_after)} tickets")
            print(f"   Difference: {len(tickets) - len(tickets_after)} tickets")
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

