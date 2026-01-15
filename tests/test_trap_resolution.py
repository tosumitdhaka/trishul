#!/usr/bin/env python3
"""
Test Trap OID Resolution

Sends a trap and verifies OIDs are resolved correctly.
"""

import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_trap_resolution():
    """Test that sent traps are resolved when received."""
    
    print("=" * 70)
    print("Testing Trap OID Resolution")
    print("=" * 70)
    
    # 1. Make sure receiver is running
    print("\n1. Checking receiver status...")
    response = requests.get(f"{BASE_URL}/traps/receiver/status")
    status = response.json()
    
    if not status.get('running'):
        print("   Starting receiver...")
        requests.post(f"{BASE_URL}/traps/receiver/start", json={
            "port": 1162,
            "bind_address": "0.0.0.0",
            "community": "public"
        })
        time.sleep(2)
    else:
        print("   ✅ Receiver already running")
    
    # 2. Send a trap
    print("\n2. Sending linkDown trap...")
    send_body = {
        "notification_name": "linkDown",
        "target_host": "127.0.0.1",
        "target_port": 1162,
        "varbind_values": {
            "ifIndex": 5,
            "ifAdminStatus": 2,
            "ifOperStatus": 2
        }
    }
    
    send_response = requests.post(
        f"{BASE_URL}/traps/send-by-name",
        json=send_body
    )
    send_result = send_response.json()
    
    if send_result['success']:
        print(f"   ✅ Trap sent (ID: {send_result['trap_id']})")
    else:
        print(f"   ❌ Failed to send trap")
        return
    
    # 3. Wait for trap to be received
    print("\n3. Waiting for trap to be received...")
    time.sleep(2)
    
    # 4. Get received traps
    print("\n4. Checking received traps...")
    received_response = requests.get(f"{BASE_URL}/traps/received?limit=1")
    received_result = received_response.json()
    
    if received_result['success'] and received_result['traps']:
        trap = received_result['traps'][0]
        
        print(f"\n   Received Trap ID: {trap['id']}")
        print(f"   Trap OID: {trap.get('trap_oid', 'Unknown')}")
        print(f"   Trap Name: {trap.get('trap_name', 'Not resolved')}")
        print(f"   Source: {trap['source_ip']}")
        print(f"\n   Varbinds:")
        
        resolved_count = 0
        total_count = len(trap.get('varbinds', []))
        
        for vb in trap.get('varbinds', []):
            resolved = vb.get('resolved', False)
            name = vb.get('name', 'Unknown')
            value = vb.get('value', '')
            oid = vb.get('oid', '')
            
            status = "✅" if resolved else "❌"
            print(f"   {status} {name} ({oid}): {value}")
            
            if resolved:
                resolved_count += 1
        
        # Resolution statistics
        if 'resolution_stats' in trap:
            stats = trap['resolution_stats']
            print(f"\n   Resolution Stats:")
            print(f"   - Resolved: {stats['resolved']}/{stats['total']}")
            print(f"   - Percentage: {stats['percentage']:.1f}%")
        else:
            print(f"\n   Resolution: {resolved_count}/{total_count} varbinds")
        
        if resolved_count == total_count:
            print("\n   ✅ All varbinds resolved successfully!")
        elif resolved_count > 0:
            print(f"\n   ⚠️  Partial resolution: {resolved_count}/{total_count}")
        else:
            print("\n   ❌ No varbinds resolved")
    else:
        print("   ❌ No traps received")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    test_trap_resolution()
