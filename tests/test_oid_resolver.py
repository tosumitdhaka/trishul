#!/usr/bin/env python3
"""
Test script for OID Resolver Service
Tests both exact match and prefix match functionality
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.config_service import Config
from services.db_service import DatabaseManager
from backend.services.oid_resolver_service import OIDResolverService


def test_oid_resolver():
    """Test OID resolver with various scenarios"""
    
    print("=" * 80)
    print("OID Resolver Test Script")
    print("=" * 80)
    
    # Initialize services
    print("\n1. Initializing services...")
    try:
        config = Config()
        db_manager = DatabaseManager(config)
        resolver = OIDResolverService(db_manager)
        print("✅ Services initialized")
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        return
    
    # Test cases
    test_cases = [
        {
            'name': 'Exact Match - sysDescr',
            'oid': '1.3.6.1.2.1.1.1.0',
            'expected_name': 'sysDescr',
            'expected_type': 'exact'
        },
        {
            'name': 'Prefix Match - ifDescr.1',
            'oid': '1.3.6.1.2.1.2.2.1.2.1',
            'expected_name': 'ifDescr.1',
            'expected_type': 'prefix'
        },
        {
            'name': 'Prefix Match - ifDescr.2',
            'oid': '1.3.6.1.2.1.2.2.1.2.2',
            'expected_name': 'ifDescr.2',
            'expected_type': 'prefix'
        },
        {
            'name': 'Prefix Match - ifType.1',
            'oid': '1.3.6.1.2.1.2.2.1.3.1',
            'expected_name': 'ifType.1',
            'expected_type': 'prefix'
        },
        {
            'name': 'Prefix Match - ifAdminStatus.1',
            'oid': '1.3.6.1.2.1.2.2.1.7.1',
            'expected_name': 'ifAdminStatus.1',
            'expected_type': 'prefix'
        },
        {
            'name': 'Not Found',
            'oid': '9.9.9.9.9.9',
            'expected_name': None,
            'expected_type': 'not_found'
        }
    ]
    
    print("\n2. Running test cases...")
    print("-" * 80)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"  OID: {test['oid']}")
        
        try:
            result = resolver.resolve_oid(test['oid'])
            
            if result is None:
                if test['expected_type'] == 'not_found':
                    print(f"  ✅ PASS - OID not found (as expected)")
                    passed += 1
                else:
                    print(f"  ❌ FAIL - Expected to find OID but got None")
                    failed += 1
            else:
                print(f"  Result:")
                print(f"    Name: {result.get('name')}")
                print(f"    Module: {result.get('module')}")
                print(f"    Syntax: {result.get('syntax')}")
                print(f"    Type: {result.get('type')}")
                
                if 'base_oid' in result:
                    print(f"    Base OID: {result.get('base_oid')}")
                    print(f"    Instance: {result.get('instance')}")
                
                # Check if name matches expected
                if test['expected_name'] and result.get('name') == test['expected_name']:
                    print(f"  ✅ PASS - Name matches expected: {test['expected_name']}")
                    passed += 1
                elif test['expected_name']:
                    print(f"  ❌ FAIL - Expected name: {test['expected_name']}, got: {result.get('name')}")
                    failed += 1
                else:
                    print(f"  ✅ PASS - OID resolved")
                    passed += 1
                    
        except Exception as e:
            print(f"  ❌ ERROR - {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"Test Summary: {passed} passed, {failed} failed")
    print("=" * 80)
    
    # Additional diagnostics
    print("\n3. Database diagnostics...")
    print("-" * 80)
    
    # Check if IF-MIB objects exist
    query = """
        SELECT 
            object_name,
            object_oid,
            module_name,
            source_table
        FROM trap_master_data
        WHERE module_name = 'IF-MIB'
        AND object_oid IN (
            '1.3.6.1.2.1.2.2.1.2',
            '1.3.6.1.2.1.2.2.1.3',
            '1.3.6.1.2.1.2.2.1.7',
            '1.3.6.1.2.1.2.2.1.8'
        )
        ORDER BY object_oid
    """
    
    df = db_manager.db_to_df(table=None, database='data', query=query)
    
    if df.empty:
        print("❌ No IF-MIB objects found in trap_master_data")
        print("   Please sync if_mib table first!")
    else:
        print(f"✅ Found {len(df)} IF-MIB objects:")
        for _, row in df.iterrows():
            print(f"   {row['object_name']}: {row['object_oid']}")
    
    # Test the SQL query directly
    print("\n4. Testing SQL prefix match query...")
    print("-" * 80)
    
    test_oid = '1.3.6.1.2.1.2.2.1.2.1'
    query_prefix = f"""
        SELECT 
            object_oid,
            object_name,
            module_name,
            LENGTH(object_oid) as oid_length
        FROM trap_master_data
        WHERE '{test_oid}' LIKE CONCAT(object_oid, '%')
        ORDER BY oid_length DESC
        LIMIT 5
    """
    
    df_prefix = db_manager.db_to_df(table=None, database='data', query=query_prefix)
    
    if df_prefix.empty:
        print(f"❌ No prefix matches found for {test_oid}")
    else:
        print(f"✅ Found {len(df_prefix)} prefix matches for {test_oid}:")
        for _, row in df_prefix.iterrows():
            print(f"   {row['object_name']}: {row['object_oid']} (length: {row['oid_length']})")
    
    # Check database connection
    print("\n5. Database connection check...")
    print("-" * 80)
    
    query_count = "SELECT COUNT(*) as count FROM trap_master_data"
    df_count = db_manager.db_to_df(table=None, database='data', query=query_count)
    
    if not df_count.empty:
        total_rows = df_count.iloc[0]['count']
        print(f"✅ trap_master_data has {total_rows} rows")
    else:
        print("❌ Could not query trap_master_data")
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == '__main__':
    test_oid_resolver()
