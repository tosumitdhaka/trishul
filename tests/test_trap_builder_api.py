#!/usr/bin/env python3
"""
Test Trap Builder API
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1/trap-builder"


def test_list_notifications():
    """Test listing notifications."""
    print("\n=== Test: List Notifications ===")
    response = requests.get(f"{BASE_URL}/notifications?limit=10")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Found {result['count']} notifications")
    if result['notifications']:
        print(f"First notification: {result['notifications'][0]['name']}")
    return result


def test_search_notifications():
    """Test searching notifications."""
    print("\n=== Test: Search Notifications ===")
    response = requests.get(f"{BASE_URL}/notifications?search=link&limit=5")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Found {result['count']} notifications matching 'link'")
    for notif in result['notifications']:
        print(f"  - {notif['name']} ({notif['oid']})")
    return result


def test_get_notification(notification_name: str):
    """Test getting notification details."""
    print(f"\n=== Test: Get Notification '{notification_name}' ===")
    response = requests.get(f"{BASE_URL}/notifications/{notification_name}")
    print(f"Status: {response.status_code}")
    result = response.json()
    if result['success']:
        notif = result['notification']
        print(f"Name: {notif['name']}")
        print(f"OID: {notif['oid']}")
        print(f"Module: {notif['module']}")
        print(f"Objects: {notif['objects_count']}")
    return result


def test_get_notification_objects(notification_name: str):
    """Test getting notification objects."""
    print(f"\n=== Test: Get Notification Objects '{notification_name}' ===")
    response = requests.get(f"{BASE_URL}/notifications/{notification_name}/objects")
    print(f"Status: {response.status_code}")
    result = response.json()
    if result['success']:
        print(f"Found {result['count']} objects:")
        for obj in result['objects']:
            print(f"  {obj['sequence']}. {obj['name']} ({obj['oid']}) - {obj['syntax']}")
    return result


def test_build_trap_structure(notification_name: str):
    """Test building trap structure."""
    print(f"\n=== Test: Build Trap Structure '{notification_name}' ===")
    response = requests.get(f"{BASE_URL}/notifications/{notification_name}/build")
    print(f"Status: {response.status_code}")
    result = response.json()
    if result['success']:
        trap = result['trap']
        print(f"Trap OID: {trap['trap_oid']}")
        print(f"Trap Name: {trap['trap_name']}")
        print(f"Varbinds: {len(trap['varbinds'])}")
    return result


def test_search_varbinds():
    """Test searching varbinds."""
    print("\n=== Test: Search Varbinds ===")
    response = requests.get(f"{BASE_URL}/varbinds/search?q=memory&limit=5")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Found {result['count']} varbinds matching 'memory'")
    for vb in result['varbinds']:
        print(f"  - {vb['name']} ({vb['oid']})")
    return result


def test_resolve_oid():
    """Test resolving OID."""
    print("\n=== Test: Resolve OID ===")
    oid = "1.3.6.1.2.1.1.3.0"
    response = requests.get(f"{BASE_URL}/oid/resolve?oid={oid}")
    print(f"Status: {response.status_code}")
    result = response.json()
    if result['success']:
        resolved = result['oid']
        print(f"OID: {resolved['oid']}")
        print(f"Name: {resolved['name']}")
        print(f"Type: {resolved['type']}")
        print(f"Syntax: {resolved['syntax']}")
    return result


def test_resolve_batch():
    """Test batch OID resolution."""
    print("\n=== Test: Resolve Batch OIDs ===")
    oids = [
        "1.3.6.1.2.1.1.3.0",
        "1.3.6.1.2.1.2.2.1.1",
        "1.3.6.1.2.1.2.2.1.8"
    ]
    response = requests.post(
        f"{BASE_URL}/oid/resolve-batch",
        json=oids
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Resolved {result['resolved_count']}/{result['total_count']} OIDs")
    for oid, data in result['results'].items():
        print(f"  {oid} → {data['name']}")
    return result


def test_cache_stats():
    """Test getting cache stats."""
    print("\n=== Test: Cache Stats ===")
    response = requests.get(f"{BASE_URL}/oid/cache/stats")
    print(f"Status: {response.status_code}")
    result = response.json()
    stats = result['cache_stats']
    print(f"Cache size: {stats['size']}/{stats['max_size']}")
    print(f"Hits: {stats['hits']}")
    print(f"Misses: {stats['misses']}")
    print(f"Hit rate: {stats['hit_rate']}")
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("Trap Builder API Test Suite")
    print("=" * 70)
    
    try:
        # 1. List notifications
        notifications = test_list_notifications()
        
        # 2. Search notifications
        test_search_notifications()
        
        # If notifications exist, test with first one
        if notifications['notifications']:
            first_notif = notifications['notifications'][0]['name']
            
            # 3. Get notification details
            test_get_notification(first_notif)
            
            # 4. Get notification objects
            test_get_notification_objects(first_notif)
            
            # 5. Build trap structure
            test_build_trap_structure(first_notif)
        
        # 6. Search varbinds
        test_search_varbinds()
        
        # 7. Resolve OID
        test_resolve_oid()
        
        # 8. Resolve batch
        test_resolve_batch()
        
        # 9. Cache stats
        test_cache_stats()
        
        print("\n" + "=" * 70)
        print("✅ All tests completed!")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

