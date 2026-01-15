#!/usr/bin/env python3
"""
Complete SNMP Trap System Test Suite

Tests all endpoints:
- Trap Sync
- Trap Builder
- Trap Sender
- Trap Receiver
"""

import requests
import json
import time
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


def print_result(result: Dict[Any, Any]):
    """Print formatted result."""
    print(json.dumps(result, indent=2))


# ============================================
# TRAP SYNC TESTS
# ============================================

def test_trap_sync():
    """Test trap sync endpoints."""
    print_header("TRAP SYNC TESTS")
    
    # 1. List user tables
    print_test("Test 1: List User Tables")
    try:
        response = requests.get(f"{BASE_URL}/trap-sync/sync/tables")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} user tables")
            if result['tables']:
                for table in result['tables'][:3]:
                    print(f"  - {table['table_name']} (status: {table['sync_status']})")
        else:
            print_error("Failed to list tables")
        
        return result
    except Exception as e:
        print_error(f"Error: {e}")
        return None
    
    # 2. Get sync status
    print_test("\nTest 2: Get Sync Status")
    try:
        response = requests.get(f"{BASE_URL}/trap-sync/sync/status")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} sync records")
            if result['status']:
                for status in result['status'][:3]:
                    print(f"  - {status['table_name']}: {status['sync_status']}")
        else:
            print_error("Failed to get sync status")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 3. Get master table stats
    print_test("\nTest 3: Get Master Table Stats")
    try:
        response = requests.get(f"{BASE_URL}/trap-sync/master/stats")
        result = response.json()
        
        if result['success'] and result['exists']:
            print_success("Master table exists")
            print(f"  Total rows: {result['total_rows']}")
            print(f"  Notifications: {result['total_notifications']}")
            print(f"  Objects: {result['total_objects']}")
            print(f"  Source tables: {result['source_tables']}")
            print(f"  Size: {result['size_mb']} MB")
        else:
            print_info("Master table doesn't exist yet")
    except Exception as e:
        print_error(f"Error: {e}")


# ============================================
# TRAP BUILDER TESTS
# ============================================

def test_trap_builder():
    """Test trap builder endpoints."""
    print_header("TRAP BUILDER TESTS")
    
    # 1. List notifications
    print_test("Test 1: List Notifications")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/notifications?limit=10")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} notifications")
            notifications = result['notifications']
            
            if notifications:
                for notif in notifications[:5]:
                    print(f"  - {notif['name']} ({notif['oid']})")
                
                # Return first notification for further tests
                return notifications[0]['name']
        else:
            print_error("Failed to list notifications")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return None
    
    # 2. Search notifications
    print_test("\nTest 2: Search Notifications")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/notifications?search=link&limit=5")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} notifications matching 'link'")
            for notif in result['notifications']:
                print(f"  - {notif['name']}")
        else:
            print_error("Failed to search notifications")
    except Exception as e:
        print_error(f"Error: {e}")


def test_notification_details(notification_name: str):
    """Test notification detail endpoints."""
    print_header(f"NOTIFICATION DETAILS: {notification_name}")
    
    # 1. Get notification details
    print_test("Test 1: Get Notification Details")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/notifications/{notification_name}")
        result = response.json()
        
        if result['success']:
            notif = result['notification']
            print_success(f"Got notification: {notif['name']}")
            print(f"  OID: {notif['oid']}")
            print(f"  Module: {notif['module']}")
            print(f"  Objects: {notif['objects_count']}")
            print(f"  Status: {notif['status']}")
        else:
            print_error("Failed to get notification")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 2. Get notification objects
    print_test("\nTest 2: Get Notification Objects")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/notifications/{notification_name}/objects")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} objects")
            for obj in result['objects']:
                enums = f" (enums: {list(obj['enumerations'].keys())})" if obj['enumerations'] else ""
                print(f"  {obj['sequence']}. {obj['name']} - {obj['syntax']}{enums}")
            
            return result['objects']
        else:
            print_error("Failed to get objects")
            return []
    except Exception as e:
        print_error(f"Error: {e}")
        return []
    
    # 3. Build trap structure
    print_test("\nTest 3: Build Trap Structure")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/notifications/{notification_name}/build")
        result = response.json()
        
        if result['success']:
            trap = result['trap']
            print_success("Built trap structure")
            print(f"  Trap OID: {trap['trap_oid']}")
            print(f"  Trap Name: {trap['trap_name']}")
            print(f"  Varbinds: {len(trap['varbinds'])}")
        else:
            print_error("Failed to build trap")
    except Exception as e:
        print_error(f"Error: {e}")


def test_varbind_search():
    """Test varbind search."""
    print_header("VARBIND SEARCH TESTS")
    
    print_test("Test: Search Varbinds")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/varbinds/search?q=interface&limit=5")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['count']} varbinds matching 'interface'")
            for vb in result['varbinds']:
                print(f"  - {vb['name']} ({vb['oid']}) - {vb['type']}")
        else:
            print_error("Failed to search varbinds")
    except Exception as e:
        print_error(f"Error: {e}")


def test_oid_resolver():
    """Test OID resolver."""
    print_header("OID RESOLVER TESTS")
    
    # 1. Resolve single OID
    print_test("Test 1: Resolve Single OID")
    try:
        oid = "1.3.6.1.2.1.1.3.0"
        response = requests.get(f"{BASE_URL}/trap-builder/oid/resolve?oid={oid}")
        result = response.json()
        
        if result['success']:
            resolved = result['oid']
            print_success(f"Resolved OID: {oid}")
            print(f"  Name: {resolved['name']}")
            print(f"  Type: {resolved['type']}")
            print(f"  Syntax: {resolved['syntax']}")
            print(f"  Module: {resolved['module']}")
        else:
            print_error("Failed to resolve OID")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 2. Resolve batch OIDs
    print_test("\nTest 2: Resolve Batch OIDs")
    try:
        oids = [
            "1.3.6.1.2.1.1.3.0",
            "1.3.6.1.2.1.2.2.1.1",
            "1.3.6.1.2.1.2.2.1.8"
        ]
        response = requests.post(
            f"{BASE_URL}/trap-builder/oid/resolve-batch",
            json=oids
        )
        result = response.json()
        
        if result['success']:
            print_success(f"Resolved {result['resolved_count']}/{result['total_count']} OIDs")
            for oid, data in result['results'].items():
                print(f"  {oid} → {data['name']}")
        else:
            print_error("Failed to resolve batch")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 3. Get cache stats
    print_test("\nTest 3: Get Cache Stats")
    try:
        response = requests.get(f"{BASE_URL}/trap-builder/oid/cache/stats")
        result = response.json()
        
        if result['success']:
            stats = result['cache_stats']
            print_success("Cache stats retrieved")
            print(f"  Size: {stats['size']}/{stats['max_size']}")
            print(f"  Hits: {stats['hits']}")
            print(f"  Misses: {stats['misses']}")
            print(f"  Hit rate: {stats['hit_rate']}")
        else:
            print_error("Failed to get cache stats")
    except Exception as e:
        print_error(f"Error: {e}")


# ============================================
# TRAP SENDER TESTS
# ============================================

def test_trap_sender(notification_name: str, objects: list):
    """Test trap sender endpoints."""
    print_header("TRAP SENDER TESTS")
    
    # 1. Get available traps
    print_test("Test 1: Get Available Traps")
    try:
        response = requests.get(f"{BASE_URL}/traps/available?limit=5")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['total']} available traps")
            for trap in result['traps'][:3]:
                print(f"  - {trap['name']} ({trap['oid']})")
        else:
            print_error("Failed to get available traps")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 2. Get notification details (from traps endpoint)
    print_test("\nTest 2: Get Notification Details (Traps Endpoint)")
    try:
        response = requests.get(f"{BASE_URL}/traps/notifications/{notification_name}")
        result = response.json()
        
        if result['success']:
            print_success(f"Got notification: {result['notification']['name']}")
            print(f"  Objects: {len(result['objects'])}")
        else:
            print_error("Failed to get notification")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 3. Send trap by name (simplified method)
    print_test("\nTest 3: Send Trap by Name")
    try:
        # Build varbind values from objects
        varbind_values = {}
        for obj in objects:
            # Use sample values based on syntax
            if obj['enumerations']:
                # Use first enum value
                varbind_values[obj['name']] = list(obj['enumerations'].values())[0]
            elif 'Index' in obj['syntax']:
                varbind_values[obj['name']] = 1
            else:
                varbind_values[obj['name']] = 1
        
        body = {
            "notification_name": notification_name,
            "target_host": "127.0.0.1",
            "target_port": 1162,
            "varbind_values": varbind_values
        }
        
        response = requests.post(
            f"{BASE_URL}/traps/send-by-name",
            json=body
        )
        result = response.json()
        
        if result['success']:
            print_success(f"Trap sent successfully!")
            print(f"  Trap ID: {result['trap_id']}")
            print(f"  Duration: {result['duration']:.3f}s")
            print(f"  Varbinds sent: {result['varbinds_sent']}")
        else:
            print_error(f"Failed to send trap: {result.get('detail', 'Unknown error')}")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 4. Get sent history
    print_test("\nTest 4: Get Sent History")
    try:
        response = requests.get(f"{BASE_URL}/traps/sent?limit=5")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['total']} sent traps")
            for trap in result['traps'][:3]:
                print(f"  - ID {trap['id']}: {trap['trap_oid']} → {trap['target_host']} ({trap['status']})")
        else:
            print_error("Failed to get sent history")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 5. Get data types
    print_test("\nTest 5: Get Data Types")
    try:
        response = requests.get(f"{BASE_URL}/traps/data-types")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {len(result['data_types'])} data types")
            print(f"  Types: {', '.join(result['data_types'][:5])}...")
        else:
            print_error("Failed to get data types")
    except Exception as e:
        print_error(f"Error: {e}")


# ============================================
# TRAP RECEIVER TESTS
# ============================================

def test_trap_receiver():
    """Test trap receiver endpoints."""
    print_header("TRAP RECEIVER TESTS")
    
    # 1. Get receiver status
    print_test("Test 1: Get Receiver Status")
    try:
        response = requests.get(f"{BASE_URL}/traps/receiver/status")
        result = response.json()
        
        if result['success']:
            if result['running']:
                print_success("Receiver is running")
                print(f"  Port: {result['port']}")
                print(f"  Traps received: {result['traps_received']}")
                print(f"  Uptime: {result.get('uptime_seconds', 0):.1f}s")
            else:
                print_info("Receiver is not running")
        else:
            print_error("Failed to get status")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 2. Start receiver
    print_test("\nTest 2: Start Receiver")
    try:
        body = {
            "port": 1162,
            "bind_address": "0.0.0.0",
            "community": "public"
        }
        response = requests.post(
            f"{BASE_URL}/traps/receiver/start",
            json=body
        )
        result = response.json()
        
        if result['success']:
            print_success("Receiver started successfully")
            print(f"  Listening on: {result.get('bind_address', '0.0.0.0')}:{result.get('port', 1162)}")
        else:
            print_info(f"Receiver start: {result.get('error', 'Already running')}")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # Wait a bit for receiver to be ready
    time.sleep(1)
    
    # 3. Get received traps
    print_test("\nTest 3: Get Received Traps")
    try:
        response = requests.get(f"{BASE_URL}/traps/received?limit=5")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['total']} received traps")
            for trap in result['traps'][:3]:
                trap_oid = trap.get('trap_oid', 'Unknown')
                source = trap.get('source_ip', 'Unknown')
                varbinds = len(trap.get('varbinds', []))
                print(f"  - ID {trap['id']}: {trap_oid} from {source} ({varbinds} varbinds)")
                
                # Show resolved varbinds
                for vb in trap.get('varbinds', [])[:2]:
                    name = vb.get('name', 'Unknown')
                    resolved = "✓" if vb.get('resolved') else "✗"
                    print(f"    {resolved} {name}: {vb.get('value', '')}")
        else:
            print_error("Failed to get received traps")
    except Exception as e:
        print_error(f"Error: {e}")


# ============================================
# TEMPLATE TESTS
# ============================================

def test_templates():
    """Test template endpoints."""
    print_header("TEMPLATE TESTS")
    
    # 1. Get templates
    print_test("Test 1: Get Templates")
    try:
        response = requests.get(f"{BASE_URL}/traps/templates")
        result = response.json()
        
        if result['success']:
            print_success(f"Found {result['total']} templates")
            for template in result['templates'][:3]:
                print(f"  - {template['name']}: {template['trap_oid']}")
        else:
            print_error("Failed to get templates")
    except Exception as e:
        print_error(f"Error: {e}")
    
    # 2. Create template
    print_test("\nTest 2: Create Template")
    try:
        body = {
            "name": f"test_template_{int(time.time())}",
            "description": "Test template created by test script",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.2.2.1.1", "type": "Integer32", "value": "1"}
            ],
            "snmp_version": "v2c",
            "community": "public"
        }
        
        response = requests.post(
            f"{BASE_URL}/traps/templates",
            json=body
        )
        result = response.json()
        
        if result['success']:
            print_success(f"Template created: {result['template_id']}")
            return result['template_id']
        else:
            print_error(f"Failed to create template: {result.get('detail', 'Unknown error')}")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return None


# ============================================
# MAIN TEST RUNNER
# ============================================

def main():
    """Run all tests."""
    print(f"\n{GREEN}{'=' * 70}{RESET}")
    print(f"{GREEN}{'SNMP TRAP SYSTEM - COMPLETE TEST SUITE'.center(70)}{RESET}")
    print(f"{GREEN}{'=' * 70}{RESET}\n")
    
    try:
        # Phase 1: Trap Sync
        test_trap_sync()
        
        # Phase 2: Trap Builder
        notification_name = test_trap_builder()
        
        if notification_name:
            # Phase 3: Notification Details
            objects = test_notification_details(notification_name)
            
            # Phase 4: Varbind Search
            test_varbind_search()
            
            # Phase 5: OID Resolver
            test_oid_resolver()
            
            # Phase 6: Trap Sender
            if objects:
                test_trap_sender(notification_name, objects)
            
            # Phase 7: Trap Receiver
            test_trap_receiver()
            
            # Phase 8: Templates
            test_templates()
        else:
            print_error("No notifications found - skipping sender/receiver tests")
            print_info("Please sync MIB data first using: POST /trap-sync/sync/table")
        
        # Summary
        print(f"\n{GREEN}{'=' * 70}{RESET}")
        print(f"{GREEN}{'✅ ALL TESTS COMPLETED!'.center(70)}{RESET}")
        print(f"{GREEN}{'=' * 70}{RESET}\n")
    
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
    except Exception as e:
        print(f"\n{RED}Test suite failed: {e}{RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
