import os
from dotenv import load_dotenv
from sheets_service import SheetsService
import time

def test_sheets_integration():
    # Load environment variables
    load_dotenv()
    
    # Get credentials path and spreadsheet ID from environment variables
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    
    if not credentials_path or not spreadsheet_id:
        print("Error: Missing environment variables")
        print("Please ensure GOOGLE_CREDENTIALS_PATH and GOOGLE_SPREADSHEET_ID are set")
        return
    
    print("Initializing Sheets Service...")
    sheets_service = SheetsService(credentials_path, spreadsheet_id)
    
    # Clean up any existing test data
    print("\nCleaning up existing test data...")
    sheets_service.cleanup_test_data()
    
    # First, let's get the sheet metadata to find the correct sheet ID
    print("\nGetting sheet metadata...")
    try:
        spreadsheet = sheets_service.service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        
        print("\nAvailable sheets:")
        for sheet in spreadsheet.get('sheets', []):
            sheet_props = sheet.get('properties', {})
            print(f"Sheet Name: {sheet_props.get('title')}")
            print(f"Sheet ID: {sheet_props.get('sheetId')}")
            print("---")
    except Exception as e:
        print(f"❌ Failed to get sheet metadata: {str(e)}")
        return
    
    # Test 1: Create a test ticket
    print("\nTest 1: Creating a test ticket...")
    test_ticket = {
        'ticket_id': 'TEST-001',
        'thread_ts': '1234567890.123456',
        'created_by': 'test_user',
        'status': 'New',
        'description': 'This is a test ticket created by the integration test script'
    }
    
    try:
        success = sheets_service.append_ticket(test_ticket)
        if success:
            print("✅ Test ticket created successfully")
        else:
            print("⚠️ Test ticket already exists or creation failed")
    except Exception as e:
        print(f"❌ Failed to create test ticket: {str(e)}")
        return
    
    # Wait a moment for the sheet to update
    print("Waiting for sheet to update...")
    time.sleep(5)
    
    # Test 2: Get all tickets and verify our test ticket
    print("\nTest 2: Retrieving tickets...")
    try:
        # Get raw data first
        result = sheets_service.sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A2:J'
        ).execute()
        
        values = result.get('values', [])
        print("\nRaw data from sheet:")
        for row in values:
            print(f"Row: {row}")
        
        tickets = sheets_service.get_tickets()
        print(f"\nFound {len(tickets)} tickets in the sheet")
        
        test_ticket_found = False
        for ticket in tickets:
            print(f"Checking ticket: {ticket['ticket_id']}")
            if ticket['ticket_id'] == 'TEST-001':
                test_ticket_found = True
                print("✅ Test ticket found in sheet")
                print(f"Ticket details:")
                print(f"  - Status: {ticket['status']}")
                print(f"  - Created by: {ticket['created_by']}")
                print(f"  - Message: {ticket['message']}")
                break
        
        if not test_ticket_found:
            print("❌ Test ticket not found in sheet")
            return
    except Exception as e:
        print(f"❌ Failed to retrieve tickets: {str(e)}")
        return
    
    # Test 3: Update ticket status
    print("\nTest 3: Updating ticket status...")
    try:
        success = sheets_service.update_ticket_status('TEST-001', 'In Progress')
        if success:
            print("✅ Ticket status updated successfully")
        else:
            print("❌ Failed to update ticket status")
            return
    except Exception as e:
        print(f"❌ Error updating ticket status: {str(e)}")
        return
    
    # Wait a moment for the sheet to update
    print("Waiting for sheet to update...")
    time.sleep(5)
    
    # Test 4: Verify status update
    print("\nTest 4: Verifying status update...")
    try:
        # Get raw data to verify
        result = sheets_service.sheet.values().get(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A2:J'
        ).execute()
        
        values = result.get('values', [])
        print("\nRaw data after update:")
        for row in values:
            print(f"Row: {row}")
        
        tickets = sheets_service.get_tickets()
        for ticket in tickets:
            if ticket['ticket_id'] == 'TEST-001':
                if ticket['status'] == 'In Progress':
                    print("✅ Status update verified")
                else:
                    print(f"❌ Status update failed. Current status: {ticket['status']}")
                break
    except Exception as e:
        print(f"❌ Failed to verify status update: {str(e)}")
        return
    
    # Clean up test data after successful test run
    print("\nCleaning up test data...")
    sheets_service.cleanup_test_data()
    
    print("\n🎉 All tests completed successfully!")

if __name__ == "__main__":
    test_sheets_integration() 