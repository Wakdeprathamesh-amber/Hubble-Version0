#!/usr/bin/env python3
"""
Comprehensive Test Script for Fix Kar Slack Bot
Tests all functionality including edge cases and regular scenarios
"""

import os
import sys
import json
import time
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️  python-dotenv not available, using system environment variables")

from ticket_service import TicketService
from sheets_service import SheetsService

class ComprehensiveTester:
    def __init__(self):
        """Initialize the comprehensive tester"""
        self.ticket_service = TicketService()
        self.sheets_service = self.ticket_service.sheets_service
        
        # Initialize Slack client
        self.slack_client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))
        self.channel_id = os.environ.get('TARGET_CHANNEL_ID')
        
        # Test results
        self.test_results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }
        
        print("🧪 COMPREHENSIVE TEST SCRIPT FOR FIX KAR SLACK BOT")
        print("=" * 60)
        
    def log_test(self, test_name, status, message=""):
        """Log test results"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        if status == 'PASS':
            print(f"✅ [{timestamp}] {test_name}: PASS")
            self.test_results['passed'].append(test_name)
        elif status == 'FAIL':
            print(f"❌ [{timestamp}] {test_name}: FAIL - {message}")
            self.test_results['failed'].append(f"{test_name}: {message}")
        elif status == 'WARN':
            print(f"⚠️  [{timestamp}] {test_name}: WARNING - {message}")
            self.test_results['warnings'].append(f"{test_name}: {message}")
    
    def test_environment_setup(self):
        """Test 1: Environment Variables and Setup"""
        print("\n🔧 TEST 1: Environment Setup")
        print("-" * 40)
        
        required_vars = [
            'SLACK_BOT_TOKEN',
            'SLACK_SIGNING_SECRET', 
            'TARGET_CHANNEL_ID',
            'GOOGLE_CREDENTIALS_PATH',
            'GOOGLE_SPREADSHEET_ID'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_test("Environment Variables", "FAIL", f"Missing: {', '.join(missing_vars)}")
        else:
            self.log_test("Environment Variables", "PASS")
        
        # Test Slack API connection
        try:
            auth_test = self.slack_client.auth_test()
            if auth_test['ok']:
                self.log_test("Slack API Connection", "PASS")
            else:
                self.log_test("Slack API Connection", "FAIL", "Auth test failed")
        except Exception as e:
            self.log_test("Slack API Connection", "FAIL", str(e))
        
        # Test Google Sheets connection
        try:
            tickets = self.sheets_service.get_tickets()
            self.log_test("Google Sheets Connection", "PASS")
        except Exception as e:
            self.log_test("Google Sheets Connection", "FAIL", str(e))
    
    def test_ticket_creation(self):
        """Test 2: Ticket Creation Functionality"""
        print("\n🎫 TEST 2: Ticket Creation")
        print("-" * 40)
        
        # Test basic ticket creation
        try:
            test_message = f"Test ticket creation - {datetime.now().strftime('%H:%M:%S')}"
            ticket_id = self.ticket_service.create_ticket(
                message_text=test_message,
                requester_id="U08S2KRG2F9",  # Test user ID
                timestamp="1754300000.000000",
                thread_ts="1754300000.000000",
                channel_id=self.channel_id,
                priority="High"
            )
            
            if ticket_id:
                self.log_test("Basic Ticket Creation", "PASS", f"Created ticket #{ticket_id}")
                self.test_ticket_id = ticket_id
            else:
                self.log_test("Basic Ticket Creation", "FAIL", "No ticket ID returned")
        except Exception as e:
            self.log_test("Basic Ticket Creation", "FAIL", str(e))
        
        # Test ticket retrieval
        try:
            ticket = self.ticket_service.get_ticket(self.test_ticket_id)
            if ticket:
                self.log_test("Ticket Retrieval", "PASS")
                # Verify ticket data
                if ticket.get('status') == 'Open':
                    self.log_test("Ticket Status Default", "PASS")
                else:
                    self.log_test("Ticket Status Default", "FAIL", f"Expected 'Open', got '{ticket.get('status')}'")
                
                if ticket.get('priority') == 'High':
                    self.log_test("Ticket Priority Setting", "PASS")
                else:
                    self.log_test("Ticket Priority Setting", "FAIL", f"Expected 'High', got '{ticket.get('priority')}'")
            else:
                self.log_test("Ticket Retrieval", "FAIL", "Ticket not found")
        except Exception as e:
            self.log_test("Ticket Retrieval", "FAIL", str(e))
    
    def test_ticket_status_updates(self):
        """Test 3: Ticket Status Update Functionality"""
        print("\n🔄 TEST 3: Status Updates")
        print("-" * 40)
        
        if not hasattr(self, 'test_ticket_id'):
            self.log_test("Status Update Tests", "FAIL", "No test ticket available")
            return
        
        # Test status update to Closed
        try:
            success = self.ticket_service.update_ticket_status(self.test_ticket_id, "Closed")
            if success:
                self.log_test("Status Update to Closed", "PASS")
                
                # Verify the update
                ticket = self.ticket_service.get_ticket(self.test_ticket_id)
                if ticket.get('status') == 'Closed':
                    self.log_test("Status Verification", "PASS")
                else:
                    self.log_test("Status Verification", "FAIL", f"Expected 'Closed', got '{ticket.get('status')}'")
                
                # Check if resolved_at is set
                if ticket.get('resolved_at'):
                    self.log_test("Resolved At Timestamp", "PASS")
                else:
                    self.log_test("Resolved At Timestamp", "FAIL", "resolved_at not set")
                
                # Check if other fields are preserved
                if ticket.get('priority') == 'High':
                    self.log_test("Field Preservation", "PASS")
                else:
                    self.log_test("Field Preservation", "FAIL", "Priority field was cleared")
            else:
                self.log_test("Status Update to Closed", "FAIL", "Update failed")
        except Exception as e:
            self.log_test("Status Update to Closed", "FAIL", str(e))
        
        # Test status update back to Open
        try:
            success = self.ticket_service.update_ticket_status(self.test_ticket_id, "Open")
            if success:
                self.log_test("Status Update to Open", "PASS")
                
                # Verify the update
                ticket = self.ticket_service.get_ticket(self.test_ticket_id)
                if ticket.get('status') == 'Open':
                    self.log_test("Open Status Verification", "PASS")
                else:
                    self.log_test("Open Status Verification", "FAIL", f"Expected 'Open', got '{ticket.get('status')}'")
            else:
                self.log_test("Status Update to Open", "FAIL", "Update failed")
        except Exception as e:
            self.log_test("Status Update to Open", "FAIL", str(e))
    
    def test_modal_updates(self):
        """Test 4: Modal Update Functionality"""
        print("\n📝 TEST 4: Modal Updates")
        print("-" * 40)
        
        if not hasattr(self, 'test_ticket_id'):
            self.log_test("Modal Update Tests", "FAIL", "No test ticket available")
            return
        
        # Test modal update
        try:
            success = self.ticket_service.update_ticket_from_modal(
                ticket_id=self.test_ticket_id,
                requester="U08S2KRG2F9",
                status="Closed",
                assignee="U08S2KRG2F9",
                priority="Critical",
                description="Updated via modal test"
            )
            
            if success:
                self.log_test("Modal Update", "PASS")
                
                # Verify the updates
                ticket = self.ticket_service.get_ticket(self.test_ticket_id)
                if ticket.get('status') == 'Closed':
                    self.log_test("Modal Status Update", "PASS")
                else:
                    self.log_test("Modal Status Update", "FAIL", f"Expected 'Closed', got '{ticket.get('status')}'")
                
                if ticket.get('priority') == 'Critical':
                    self.log_test("Modal Priority Update", "PASS")
                else:
                    self.log_test("Modal Priority Update", "FAIL", f"Expected 'Critical', got '{ticket.get('priority')}'")
                
                if "Updated via modal test" in ticket.get('message', ''):
                    self.log_test("Modal Description Update", "PASS")
                else:
                    self.log_test("Modal Description Update", "FAIL", "Description not updated")
            else:
                self.log_test("Modal Update", "FAIL", "Modal update failed")
        except Exception as e:
            self.log_test("Modal Update", "FAIL", str(e))
    
    def test_edge_cases(self):
        """Test 5: Edge Cases"""
        print("\n⚠️  TEST 5: Edge Cases")
        print("-" * 40)
        
        # Test invalid ticket ID
        try:
            ticket = self.ticket_service.get_ticket("999999")
            if ticket is None:
                self.log_test("Invalid Ticket ID", "PASS")
            else:
                self.log_test("Invalid Ticket ID", "FAIL", "Should return None")
        except Exception as e:
            self.log_test("Invalid Ticket ID", "FAIL", str(e))
        
        # Test invalid status
        try:
            success = self.ticket_service.update_ticket_status(self.test_ticket_id, "InvalidStatus")
            if not success:
                self.log_test("Invalid Status Validation", "PASS")
            else:
                self.log_test("Invalid Status Validation", "FAIL", "Should reject invalid status")
        except Exception as e:
            self.log_test("Invalid Status Validation", "FAIL", str(e))
        
        # Test empty message
        try:
            ticket_id = self.ticket_service.create_ticket(
                message_text="",
                requester_id="U08S2KRG2F9",
                timestamp="1754300000.000000"
            )
            if ticket_id:
                self.log_test("Empty Message Handling", "PASS")
            else:
                self.log_test("Empty Message Handling", "FAIL", "Should handle empty messages")
        except Exception as e:
            self.log_test("Empty Message Handling", "FAIL", str(e))
        
        # Test very long message
        try:
            long_message = "A" * 1000  # Very long message
            ticket_id = self.ticket_service.create_ticket(
                message_text=long_message,
                requester_id="U08S2KRG2F9",
                timestamp="1754300000.000000"
            )
            if ticket_id:
                self.log_test("Long Message Handling", "PASS")
            else:
                self.log_test("Long Message Handling", "FAIL", "Should handle long messages")
        except Exception as e:
            self.log_test("Long Message Handling", "FAIL", str(e))
    
    def test_slack_integration(self):
        """Test 6: Slack Integration"""
        print("\n💬 TEST 6: Slack Integration")
        print("-" * 40)
        
        # Test channel access
        try:
            channel_info = self.slack_client.conversations_info(channel=self.channel_id)
            if channel_info['ok']:
                self.log_test("Channel Access", "PASS")
            else:
                self.log_test("Channel Access", "FAIL", "Cannot access channel")
        except Exception as e:
            self.log_test("Channel Access", "FAIL", str(e))
        
        # Test user info retrieval
        try:
            user_info = self.slack_client.users_info(user="U08S2KRG2F9")
            if user_info['ok']:
                self.log_test("User Info Retrieval", "PASS")
            else:
                self.log_test("User Info Retrieval", "FAIL", "Cannot get user info")
        except Exception as e:
            self.log_test("User Info Retrieval", "FAIL", str(e))
        
        # Test message posting (optional - might spam the channel)
        # Uncomment if you want to test actual message posting
        """
        try:
            response = self.slack_client.chat_postMessage(
                channel=self.channel_id,
                text="🧪 Test message from comprehensive test script"
            )
            if response['ok']:
                self.log_test("Message Posting", "PASS")
            else:
                self.log_test("Message Posting", "FAIL", "Cannot post message")
        except Exception as e:
            self.log_test("Message Posting", "FAIL", str(e))
        """
    
    def test_data_integrity(self):
        """Test 7: Data Integrity"""
        print("\n🔒 TEST 7: Data Integrity")
        print("-" * 40)
        
        # Test all tickets retrieval
        try:
            all_tickets = self.ticket_service.get_all_tickets()
            if isinstance(all_tickets, list):
                self.log_test("All Tickets Retrieval", "PASS", f"Found {len(all_tickets)} tickets")
            else:
                self.log_test("All Tickets Retrieval", "FAIL", "Should return list")
        except Exception as e:
            self.log_test("All Tickets Retrieval", "FAIL", str(e))
        
        # Test ticket data structure
        if hasattr(self, 'test_ticket_id'):
            try:
                ticket = self.ticket_service.get_ticket(self.test_ticket_id)
                required_fields = ['ticket_id', 'status', 'created_by', 'created_at']
                missing_fields = []
                
                for field in required_fields:
                    if field not in ticket:
                        missing_fields.append(field)
                
                if not missing_fields:
                    self.log_test("Ticket Data Structure", "PASS")
                else:
                    self.log_test("Ticket Data Structure", "FAIL", f"Missing fields: {missing_fields}")
            except Exception as e:
                self.log_test("Ticket Data Structure", "FAIL", str(e))
    
    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("🚀 Starting Comprehensive Test Suite...")
        
        # Run all test categories
        self.test_environment_setup()
        self.test_ticket_creation()
        self.test_ticket_status_updates()
        self.test_modal_updates()
        self.test_edge_cases()
        self.test_slack_integration()
        self.test_data_integrity()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results['passed']) + len(self.test_results['failed'])
        
        print(f"✅ PASSED: {len(self.test_results['passed'])}")
        print(f"❌ FAILED: {len(self.test_results['failed'])}")
        print(f"⚠️  WARNINGS: {len(self.test_results['warnings'])}")
        print(f"📈 SUCCESS RATE: {(len(self.test_results['passed']) / total_tests * 100):.1f}%" if total_tests > 0 else "📈 SUCCESS RATE: 0%")
        
        if self.test_results['failed']:
            print("\n❌ FAILED TESTS:")
            for failure in self.test_results['failed']:
                print(f"   • {failure}")
        
        if self.test_results['warnings']:
            print("\n⚠️  WARNINGS:")
            for warning in self.test_results['warnings']:
                print(f"   • {warning}")
        
        print("\n🎯 RECOMMENDATIONS:")
        if len(self.test_results['failed']) == 0:
            print("   • All tests passed! System is working correctly.")
        else:
            print("   • Fix the failed tests above before deploying.")
            print("   • Check environment variables and API connections.")
        
        print("=" * 60)

if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists('app.py'):
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Run the comprehensive test suite
    tester = ComprehensiveTester()
    tester.run_all_tests() 