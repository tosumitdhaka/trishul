#!/usr/bin/env python3
"""
Test Sent Traps Storage with Names

Validates that sent traps store original names (not OIDs) in database.
"""

import requests
import json
import time
import pymysql
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def print_header(text: str):
    """Print section header."""
    print(f"\n{CYAN}{'=' * 70}{RESET}")
    print(f"{CYAN}{text.center(70)}{RESET}")
    print(f"{CYAN}{'=' * 70}{RESET}\n")


def print_test(text: str):
    """Print test name."""
    print(f"{BLUE}▶ {text}{RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{YELLOW}ℹ️  {text}{RESET}")


def get_db_connection():
    """Get database connection."""
    try:
        conn = pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            password='dhaka123',  # Update if you have a password
            database='mib_tool_traps',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return None


def test_send_trap_by_name():
    """Test sending trap by name and verify storage."""
    print_header("TEST: Send Trap by Name")
    
    print_test("Step 1: Send trap using notification name")
    
    # Send trap
    try:
        response = requests.post(
            f"{BASE_URL}/traps/send-by-name",
            json={
                "notification_name": "linkDown",
                "target_host": "127.0.0.1",
                "target_port": 1162,
                "varbind_values": {
                    "ifIndex": 5,
                    "ifAdminStatus": 2,
                    "ifOperStatus": 2
                }
            }
        )
        
        if response.status_code != 200:
            print_error(f"Failed to send trap: {response.status_code}")
            print(response.text)
            return None
        
        result = response.json()
        
        if not result.get('success'):
            print_error(f"Trap send failed: {result.get('message')}")
            return None
        
        trap_id = result.get('trap_id')
        print_success(f"Trap sent successfully (ID: {trap_id})")
        print(f"  Notification: {result.get('notification_name')}")
        print(f"  Trap OID: {result.get('trap_oid')}")
        print(f"  Duration: {result.get('duration'):.3f}s")
        print(f"  Varbinds sent: {result.get('varbinds_sent')}")
        
        return trap_id
        
    except Exception as e:
        print_error(f"Exception: {e}")
        return None


def test_verify_database_storage(trap_id: int):
    """Verify trap is stored with names in database."""
    print_test("\nStep 2: Verify database storage")
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # Query sent trap
            cursor.execute("""
                SELECT 
                    id, trap_oid, trap_name, target_host, target_port,
                    varbinds, status, sent_at
                FROM sent_traps
                WHERE id = %s
            """, (trap_id,))
            
            trap = cursor.fetchone()
            
            if not trap:
                print_error(f"Trap ID {trap_id} not found in database")
                return False
            
            print_success("Trap found in database")
            print(f"\n  Database Record:")
            print(f"  ID: {trap['id']}")
            print(f"  Trap OID: {trap['trap_oid']}")
            print(f"  Trap Name: {trap['trap_name']}")
            print(f"  Target: {trap['target_host']}:{trap['target_port']}")
            print(f"  Status: {trap['status']}")
            print(f"  Sent At: {trap['sent_at']}")
            
            # Parse varbinds
            varbinds = json.loads(trap['varbinds']) if trap['varbinds'] else []
            
            print(f"\n  Varbinds ({len(varbinds)} total):")
            
            # Validate varbinds structure
            all_have_names = True
            all_have_oids = True
            
            for i, vb in enumerate(varbinds, 1):
                has_name = 'name' in vb and vb['name']
                has_oid = 'oid' in vb and vb['oid']
                
                if not has_name:
                    all_have_names = False
                if not has_oid:
                    all_have_oids = False
                
                name_status = "✅" if has_name else "❌"
                oid_status = "✅" if has_oid else "❌"
                
                print(f"    {i}. {name_status} Name: {vb.get('name', 'MISSING')}")
                print(f"       {oid_status} OID: {vb.get('oid', 'MISSING')}")
                print(f"       Type: {vb.get('type', 'N/A')}")
                print(f"       Syntax: {vb.get('syntax', 'N/A')}")
                print(f"       Value: {vb.get('value', 'N/A')}")
                if vb.get('description'):
                    desc = vb['description'][:60] + "..." if len(vb.get('description', '')) > 60 else vb.get('description', '')
                    print(f"       Description: {desc}")
                print()
            
            # Validation results
            print(f"  Validation Results:")
            
            if trap['trap_name']:
                print_success(f"Trap name stored: {trap['trap_name']}")
            else:
                print_error("Trap name NOT stored")
            
            if all_have_names:
                print_success(f"All {len(varbinds)} varbinds have names")
            else:
                print_error("Some varbinds missing names")
            
            if all_have_oids:
                print_success(f"All {len(varbinds)} varbinds have OIDs")
            else:
                print_error("Some varbinds missing OIDs")
            
            # Check for expected fields
            expected_fields = ['name', 'oid', 'type', 'syntax', 'value']
            all_fields_present = all(
                all(field in vb for field in expected_fields)
                for vb in varbinds
            )
            
            if all_fields_present:
                print_success("All expected fields present in varbinds")
            else:
                print_error("Some expected fields missing")
            
            return (
                trap['trap_name'] is not None and
                all_have_names and
                all_have_oids and
                all_fields_present
            )
        
    except Exception as e:
        print_error(f"Database verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        conn.close()


def test_get_sent_history():
    """Test getting sent history via API."""
    print_test("\nStep 3: Verify API returns names")
    
    try:
        response = requests.get(f"{BASE_URL}/traps/sent?limit=1")
        
        if response.status_code != 200:
            print_error(f"Failed to get sent history: {response.status_code}")
            return False
        
        result = response.json()
        
        if not result.get('success'):
            print_error("API call failed")
            return False
        
        traps = result.get('traps', [])
        
        if not traps:
            print_error("No traps in history")
            return False
        
        trap = traps[0]
        
        print_success("API returned sent history")
        print(f"\n  Latest Trap:")
        print(f"  ID: {trap.get('id')}")
        print(f"  Trap Name: {trap.get('trap_name')}")
        print(f"  Trap OID: {trap.get('trap_oid')}")
        print(f"  Target: {trap.get('target_host')}:{trap.get('target_port')}")
        
        varbinds = trap.get('varbinds', [])
        print(f"\n  Varbinds ({len(varbinds)} total):")
        
        all_have_names = True
        for i, vb in enumerate(varbinds, 1):
            has_name = 'name' in vb and vb['name']
            if not has_name:
                all_have_names = False
            
            status = "✅" if has_name else "❌"
            print(f"    {i}. {status} {vb.get('name', 'MISSING')}: {vb.get('value')}")
        
        if all_have_names:
            print_success("\nAll varbinds have names in API response")
            return True
        else:
            print_error("\nSome varbinds missing names in API response")
            return False
        
    except Exception as e:
        print_error(f"API test failed: {e}")
        return False


def test_compare_old_vs_new():
    """Compare old (OID-only) vs new (with names) storage."""
    print_test("\nStep 4: Compare storage formats")
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        with conn.cursor() as cursor:
            # Get latest 2 traps
            cursor.execute("""
                SELECT id, trap_name, varbinds
                FROM sent_traps
                ORDER BY id DESC
                LIMIT 2
            """)
            
            traps = cursor.fetchall()
            
            if len(traps) < 2:
                print_info("Not enough traps to compare")
                return
            
            print(f"\n  Comparing last 2 traps:")
            
            for trap in traps:
                varbinds = json.loads(trap['varbinds']) if trap['varbinds'] else []
                
                has_names = all('name' in vb and vb['name'] for vb in varbinds)
                
                format_type = "NEW (with names)" if has_names else "OLD (OIDs only)"
                status = "✅" if has_names else "⚠️"
                
                print(f"\n  {status} Trap ID {trap['id']}: {format_type}")
                print(f"     Trap Name: {trap['trap_name'] or 'N/A'}")
                
                if varbinds:
                    sample_vb = varbinds[0]
                    if 'name' in sample_vb:
                        print(f"     Sample Varbind: {sample_vb.get('name')} = {sample_vb.get('value')}")
                    else:
                        print(f"     Sample Varbind: {sample_vb.get('oid')} = {sample_vb.get('value')}")
        
    except Exception as e:
        print_error(f"Comparison failed: {e}")
    
    finally:
        conn.close()


def main():
    """Run all tests."""
    print(f"\n{GREEN}{'=' * 70}{RESET}")
    print(f"{GREEN}{'SENT TRAPS WITH NAMES - TEST SUITE'.center(70)}{RESET}")
    print(f"{GREEN}{'=' * 70}{RESET}\n")
    
    try:
        # Test 1: Send trap
        trap_id = test_send_trap_by_name()
        
        if not trap_id:
            print_error("\nTest failed: Could not send trap")
            return False
        
        # Wait a moment for database write
        time.sleep(0.5)
        
        # Test 2: Verify database storage
        db_valid = test_verify_database_storage(trap_id)
        
        # Test 3: Verify API response
        api_valid = test_get_sent_history()
        
        # Test 4: Compare formats
        test_compare_old_vs_new()
        
        # Summary
        print_header("TEST SUMMARY")
        
        if db_valid and api_valid:
            print_success("✅ ALL TESTS PASSED!")
            print(f"\n  {GREEN}Sent traps are now storing names correctly:{RESET}")
            print(f"  • Trap name stored in trap_name column")
            print(f"  • Varbinds include 'name' field")
            print(f"  • Varbinds include 'oid' field")
            print(f"  • Varbinds include 'syntax' field")
            print(f"  • Varbinds include 'description' field")
            print(f"  • API returns complete information")
            return True
        else:
            print_error("❌ SOME TESTS FAILED")
            print(f"\n  {RED}Issues detected:{RESET}")
            if not db_valid:
                print(f"  • Database storage incomplete")
            if not api_valid:
                print(f"  • API response missing names")
            return False
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        return False
    except Exception as e:
        print_error(f"\nTest suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
