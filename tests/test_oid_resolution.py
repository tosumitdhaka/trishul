#!/usr/bin/env python3
"""
OID Resolution Test Script

Tests OID resolver service with various OIDs to check resolution accuracy.
"""

import requests
import json
from typing import List, Dict

# Configuration
BASE_URL = "http://localhost:8000/api/v1/snmp-walk"
HEADERS = {"Content-Type": "application/json"}

# Test OIDs (common SNMP OIDs)
TEST_OIDS = [
    # System MIB (1.3.6.1.2.1.1.x)
    {
        "oid": "1.3.6.1.2.1.1.1",
        "expected_name": "sysDescr",
        "category": "System"
    },
    {
        "oid": "1.3.6.1.2.1.1.3",
        "expected_name": "sysUpTime",
        "category": "System"
    },
    {
        "oid": "1.3.6.1.2.1.1.4",
        "expected_name": "sysContact",
        "category": "System"
    },
    {
        "oid": "1.3.6.1.2.1.1.5.0",
        "expected_name": "sysName",
        "category": "System"
    },
    {
        "oid": "1.3.6.1.2.1.1.6.0",
        "expected_name": "sysLocation",
        "category": "System"
    },
    
    # Interface MIB (1.3.6.1.2.1.2.x)
    {
        "oid": "1.3.6.1.2.1.2.1.0",
        "expected_name": "ifNumber",
        "category": "Interface"
    },
    {
        "oid": "1.3.6.1.2.1.2.2.1.1",
        "expected_name": "ifIndex",
        "category": "Interface"
    },
    {
        "oid": "1.3.6.1.2.1.2.2.1.2",
        "expected_name": "ifDescr",
        "category": "Interface"
    },
    {
        "oid": "1.3.6.1.2.1.2.2.1.5",
        "expected_name": "ifSpeed",
        "category": "Interface"
    },
    {
        "oid": "1.3.6.1.2.1.2.2.1.8",
        "expected_name": "ifOperStatus",
        "category": "Interface"
    },
    
    # IP MIB (1.3.6.1.2.1.4.x)
    {
        "oid": "1.3.6.1.2.1.4.1.0",
        "expected_name": "ipForwarding",
        "category": "IP"
    },
    {
        "oid": "1.3.6.1.2.1.4.3.0",
        "expected_name": "ipInReceives",
        "category": "IP"
    },
    
    # TCP MIB (1.3.6.1.2.1.6.x)
    {
        "oid": "1.3.6.1.2.1.6.5.0",
        "expected_name": "tcpActiveOpens",
        "category": "TCP"
    },
    {
        "oid": "1.3.6.1.2.1.6.9.0",
        "expected_name": "tcpCurrEstab",
        "category": "TCP"
    },
    
    # UDP MIB (1.3.6.1.2.1.7.x)
    {
        "oid": "1.3.6.1.2.1.7.1.0",
        "expected_name": "udpInDatagrams",
        "category": "UDP"
    },
    
    # BGP MIB (1.3.6.1.2.1.15.x)
    {
        "oid": "1.3.6.1.2.1.15.3.1.2",
        "expected_name": "bgpPeerState",
        "category": "BGP"
    },
    {
        "oid": "1.3.6.1.2.1.15.3.1.7",
        "expected_name": "bgpPeerRemoteAs",
        "category": "BGP"
    },
    
    # Host Resources MIB (1.3.6.1.2.1.25.x)
    {
        "oid": "1.3.6.1.2.1.25.1.1.0",
        "expected_name": "hrSystemUptime",
        "category": "Host Resources"
    },
    {
        "oid": "1.3.6.1.2.1.25.2.3.1.5",
        "expected_name": "hrStorageUsed",
        "category": "Host Resources"
    },
    {
        "oid": "1.3.6.1.2.1.25.3.3.1.2",
        "expected_name": "hrProcessorLoad",
        "category": "Host Resources"
    },
]


def print_header(title: str):
    """Print section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_single_oid(oid: str, expected_name: str = None, category: str = None) -> Dict:
    """Test resolution of a single OID."""
    try:
        response = requests.get(f"{BASE_URL}/oid-resolver/resolve/{oid}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                result = data.get('result', {})
                resolved_name = result.get('name')
                
                # Check if name matches expected
                name_match = False
                if expected_name and resolved_name:
                    name_match = expected_name.lower() in resolved_name.lower()
                
                return {
                    'oid': oid,
                    'category': category,
                    'expected_name': expected_name,
                    'resolved': True,
                    'resolved_name': resolved_name,
                    'description': result.get('description', '')[:80],
                    'module': result.get('module'),
                    'syntax': result.get('syntax'),
                    'name_match': name_match,
                    'status': 'PASS' if name_match or not expected_name else 'PARTIAL'
                }
            else:
                return {
                    'oid': oid,
                    'category': category,
                    'expected_name': expected_name,
                    'resolved': False,
                    'resolved_name': None,
                    'description': None,
                    'module': None,
                    'syntax': None,
                    'name_match': False,
                    'status': 'NOT_FOUND'
                }
        else:
            return {
                'oid': oid,
                'category': category,
                'expected_name': expected_name,
                'resolved': False,
                'status': 'ERROR',
                'error': f"HTTP {response.status_code}"
            }
    
    except Exception as e:
        return {
            'oid': oid,
            'category': category,
            'expected_name': expected_name,
            'resolved': False,
            'status': 'ERROR',
            'error': str(e)
        }


def test_batch_resolution():
    """Test batch OID resolution."""
    print_header("OID RESOLUTION TEST")
    print(f"\nBase URL: {BASE_URL}")
    print(f"Testing {len(TEST_OIDS)} OIDs...\n")
    
    results = []
    categories = {}
    
    # Test each OID
    for test_case in TEST_OIDS:
        result = test_single_oid(
            test_case['oid'],
            test_case.get('expected_name'),
            test_case.get('category')
        )
        results.append(result)
        
        # Group by category
        category = result.get('category', 'Unknown')
        if category not in categories:
            categories[category] = {'total': 0, 'resolved': 0, 'matched': 0}
        
        categories[category]['total'] += 1
        if result['resolved']:
            categories[category]['resolved'] += 1
        if result.get('name_match'):
            categories[category]['matched'] += 1
    
    # Print results by category
    for category in sorted(categories.keys()):
        print_header(f"{category} MIB")
        
        category_results = [r for r in results if r.get('category') == category]
        
        for result in category_results:
            status_icon = {
                'PASS': '✅',
                'PARTIAL': '⚠️',
                'NOT_FOUND': '❌',
                'ERROR': '🔴'
            }.get(result['status'], '❓')
            
            print(f"\n{status_icon} OID: {result['oid']}")
            print(f"   Expected: {result.get('expected_name', 'N/A')}")
            
            if result['resolved']:
                print(f"   Resolved: {result['resolved_name']}")
                print(f"   Module:   {result.get('module', 'N/A')}")
                print(f"   Syntax:   {result.get('syntax', 'N/A')}")
                if result.get('description'):
                    print(f"   Desc:     {result['description']}...")
            else:
                print(f"   Status:   Not found in trap_master_data")
                if result.get('error'):
                    print(f"   Error:    {result['error']}")
    
    # Print summary
    print_header("SUMMARY")
    
    total_oids = len(results)
    total_resolved = sum(1 for r in results if r['resolved'])
    total_matched = sum(1 for r in results if r.get('name_match'))
    total_not_found = sum(1 for r in results if r['status'] == 'NOT_FOUND')
    total_errors = sum(1 for r in results if r['status'] == 'ERROR')
    
    resolution_rate = (total_resolved / total_oids * 100) if total_oids > 0 else 0
    match_rate = (total_matched / total_oids * 100) if total_oids > 0 else 0
    
    print(f"\nTotal OIDs Tested:     {total_oids}")
    print(f"✅ Resolved:           {total_resolved} ({resolution_rate:.1f}%)")
    print(f"✅ Name Matched:       {total_matched} ({match_rate:.1f}%)")
    print(f"❌ Not Found:          {total_not_found}")
    print(f"🔴 Errors:             {total_errors}")
    
    print("\n" + "-" * 80)
    print("Resolution by Category:")
    print("-" * 80)
    
    for category in sorted(categories.keys()):
        stats = categories[category]
        cat_rate = (stats['resolved'] / stats['total'] * 100) if stats['total'] > 0 else 0
        match_rate = (stats['matched'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        print(f"{category:20s} {stats['resolved']:2d}/{stats['total']:2d} resolved ({cat_rate:5.1f}%)  "
              f"{stats['matched']:2d}/{stats['total']:2d} matched ({match_rate:5.1f}%)")
    
    print("\n" + "=" * 80)
    
    # Recommendations
    if resolution_rate < 50:
        print("\n⚠️  LOW RESOLUTION RATE!")
        print("\nRecommendations:")
        print("1. Import standard MIBs:")
        print("   - SNMPv2-MIB (System)")
        print("   - IF-MIB (Interfaces)")
        print("   - IP-MIB, TCP-MIB, UDP-MIB")
        print("   - HOST-RESOURCES-MIB")
        print("   - BGP4-MIB (if monitoring BGP)")
        print("\n2. Parse and sync to trap_master_data:")
        print("   python -m core.parser --source standard_mibs --mode directory")
        print("   Then use trap-sync API to import to trap_master_data")
    elif resolution_rate < 80:
        print("\n⚠️  MODERATE RESOLUTION RATE")
        print("\nSome OIDs not found. Consider importing additional MIBs.")
    else:
        print("\n✅ EXCELLENT RESOLUTION RATE!")
        print("\nYour MIB database is well-populated.")
    
    print("\n" + "=" * 80)
    
    return {
        'total': total_oids,
        'resolved': total_resolved,
        'matched': total_matched,
        'resolution_rate': resolution_rate,
        'match_rate': match_rate,
        'categories': categories
    }


def test_search_functionality():
    """Test OID search functionality."""
    print_header("OID SEARCH TEST")
    
    search_terms = [
        "system",
        "interface",
        "bgp",
        "memory",
        "cpu"
    ]
    
    for term in search_terms:
        try:
            response = requests.get(
                f"{BASE_URL}/oid-resolver/search",
                params={"search": term, "limit": 5}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    count = data.get('count', 0)
                    results = data.get('results', [])
                    
                    print(f"\n🔍 Search: '{term}' - Found {count} results")
                    
                    for i, result in enumerate(results[:3], 1):
                        print(f"   {i}. {result.get('name')} ({result.get('oid')})")
                        print(f"      Module: {result.get('module')}")
                else:
                    print(f"\n❌ Search '{term}' failed")
            else:
                print(f"\n🔴 Search '{term}' - HTTP {response.status_code}")
        
        except Exception as e:
            print(f"\n🔴 Search '{term}' - Error: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        # Test batch resolution
        summary = test_batch_resolution()
        
        # Test search functionality
        test_search_functionality()
        
        # Exit code based on resolution rate
        if summary['resolution_rate'] >= 80:
            exit(0)  # Success
        elif summary['resolution_rate'] >= 50:
            exit(1)  # Warning
        else:
            exit(2)  # Critical
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n\n🔴 Test failed with error: {e}")
        exit(1)
