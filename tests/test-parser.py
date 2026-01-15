#!/usr/bin/env python3
"""
Comprehensive MIB Parser Test Suite
Tests: Field enrichment, Progress callbacks, Concurrent parsing
"""

import sys
import threading
import time
import shutil
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
mib_p_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from core.parser import MibParser
from services.config_service import Config

# ============================================
# CONFIGURATION
# ============================================

MIB_DIR = mib_p_dir / 'mib_files' / 'mibs'
MIB_FILE = mib_p_dir / 'mib_files' / 'mibs' / 'IF-MIB.mib'
COMP_DIR = parent_dir / 'compiled_mibs'
CACHE_DIR = parent_dir / 'cache'

# Test configuration
TEST_LIST = [
    'field_enrichment_test'
    #'progress_callback_test',
    #'concurrent_file_test',
    #'concurrent_directory_test'
]

# ============================================
# UTILITIES
# ============================================

def clear_cache():
    """Clear compiled MIBs and cache directories."""
    cleared = []
    
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        cleared.append("cache")
    
    if COMP_DIR.exists():
        shutil.rmtree(COMP_DIR)
        cleared.append("compiled_mibs")
    
    if cleared:
        print(f"  ✓ Cleared: {', '.join(cleared)}")
    else:
        print("  ✓ Already clean")

def print_header(title: str):
    """Print formatted test header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_subheader(title: str):
    """Print formatted subheader."""
    print(f"\n  {title}")
    print("  " + "-" * 60)

def print_result(passed: bool, message: str):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {message}")

def validate_field(df, field_name: str, expected_non_empty: bool = True) -> bool:
    """Validate that a field exists and optionally has non-empty values."""
    if field_name not in df.columns:
        print_result(False, f"Field '{field_name}' missing from DataFrame")
        return False
    
    if expected_non_empty:
        non_empty = df[field_name].notna().sum()
        if non_empty == 0:
            print_result(False, f"Field '{field_name}' has no non-empty values")
            return False
        print_result(True, f"Field '{field_name}' exists with {non_empty} non-empty values")
    else:
        print_result(True, f"Field '{field_name}' exists")
    
    return True

# ============================================
# TEST 1: FIELD ENRICHMENT
# ============================================

def field_enrichment_test():
    """Test that all enrichment fields are properly populated."""
    print_header("TEST 1: FIELD ENRICHMENT")
    
    if not MIB_FILE.exists():
        print_result(False, f"MIB file not found: {MIB_FILE}")
        return
    
    try:
        config = Config()
        parser = MibParser(config)
        
        print_subheader("Parsing IF-MIB.mib")
        df = parser.parse_file(str(MIB_FILE))
        
        if df.empty:
            print_result(False, "DataFrame is empty")
            return
        
        print_result(True, f"Parsed {len(df)} records")
        
        # Test 1.1: Notification fields
        print_subheader("1.1: Notification Fields")
        linkdown = df[df['notification_name'] == 'linkDown']
        
        # In your test, print the actual notification_description:
        print(f"Notification description length: {len(linkdown.iloc[0]['notification_description'])}")
        print(f"First 200 chars: {linkdown.iloc[0]['notification_description'][:200]}")
        
        if linkdown.empty:
            print_result(False, "linkDown notification not found")
        else:
            print_result(True, f"Found linkDown notification with {len(linkdown)} objects")
            
            # Check notification description
            notif_desc = linkdown.iloc[0]['notification_description']
            if notif_desc and len(notif_desc) > 50:
                print_result(True, f"Notification description populated ({len(notif_desc)} chars)")
            else:
                print_result(False, f"Notification description empty or too short")
            
            # Check object descriptions
            for idx, row in linkdown.iterrows():
                obj_name = row['object_name']
                obj_desc = row['object_description']
                if obj_desc and len(obj_desc) > 20:
                    print_result(True, f"Object '{obj_name}' description populated ({len(obj_desc)} chars)")
                else:
                    print_result(False, f"Object '{obj_name}' description empty or too short")
        
        # Test 1.2: Enumeration fields
        print_subheader("1.2: Enumeration Fields")
        enum_objects = linkdown[linkdown['tc_enumerations'].notna()]
        
        if not enum_objects.empty:
            for idx, row in enum_objects.iterrows():
                obj_name = row['object_name']
                enums = row['tc_enumerations']
                print_result(True, f"Object '{obj_name}' has enumerations: {enums[:50]}...")
        else:
            print_result(False, "No objects with enumerations found")
        
        # Test 1.3: TC resolution fields
        print_subheader("1.3: TC Resolution Fields")
        tc_objects = df[df['tc_name'].notna() & (df['tc_name'] != '')]
        
        if not tc_objects.empty:
            print_result(True, f"Found {len(tc_objects)} objects with TC resolution")
            
            # Check resolution chain
            for idx, row in tc_objects.head(3).iterrows():
                obj_name = row['object_name']
                tc_name = row['tc_name']
                tc_base = row['tc_base_type']
                tc_chain = row['tc_resolution_chain']
                
                if tc_chain and '->' in tc_chain:
                    print_result(True, f"Object '{obj_name}': {tc_chain}")
                else:
                    print_result(False, f"Object '{obj_name}': incomplete TC chain")
        else:
            print_result(False, "No objects with TC resolution found")
        
        # Test 1.4: Table fields
        print_subheader("1.4: Table Fields")
        validate_field(df, 'table_indexes', expected_non_empty=False)
        validate_field(df, 'augments_table', expected_non_empty=False)
        
        table_objects = df[df['table_indexes'].notna() & (df['table_indexes'] != '')]
        if not table_objects.empty:
            print_result(True, f"Found {len(table_objects)} objects with table indexes")
            for idx, row in table_objects.head(3).iterrows():
                print(f"    - {row['object_name']}: indexes={row['table_indexes']}")
        
        # Test 1.5: Parent fields
        print_subheader("1.5: Parent Fields")
        parent_objects = df[df['parent_name'].notna() & (df['parent_name'] != '')]
        if not parent_objects.empty:
            print_result(True, f"Found {len(parent_objects)} objects with parent resolution")
            parent_counts = parent_objects['parent_name'].value_counts().head(5)
            print("    Top parents:")
            for parent, count in parent_counts.items():
                print(f"      - {parent}: {count} children")
        
        # Test 1.6: Notification enterprise
        print_subheader("1.6: Notification Enterprise")
        validate_field(df, 'notification_enterprise', expected_non_empty=False)
        
    except Exception as e:
        print_result(False, f"Exception: {e}")
        import traceback
        traceback.print_exc()

# ============================================
# TEST 2: PROGRESS CALLBACKS
# ============================================

def progress_callback_test():
    """Test progress callback functionality."""
    print_header("TEST 2: PROGRESS CALLBACKS")
    
    if not MIB_DIR.exists():
        print_result(False, f"MIB directory not found: {MIB_DIR}")
        return
    
    # Track callback invocations
    callback_data = {
        'calls': 0,
        'phases': set(),
        'max_percentage': 0,
        'messages': []
    }
    
    def my_callback(current, total, message):
        callback_data['calls'] += 1
        callback_data['messages'].append(message)
        
        # Try to extract phase from message
        for phase in ['Scanning', 'Compiling', 'Parsing', 'Enriching', 'Deduplicating', 'Completed']:
            if phase.lower() in message.lower():
                callback_data['phases'].add(phase)
        
        # Calculate percentage
        if total > 0:
            pct = (current / total) * 100
            callback_data['max_percentage'] = max(callback_data['max_percentage'], pct)
        
        print(f"  [{current}/{total}] {message}")
    
    try:
        config = Config()
        parser = MibParser(config)
        
        print_subheader("Parsing directory with callbacks")
        df = parser.parse_directory(str(MIB_DIR), progress_callback=my_callback)
        
        print_subheader("Callback Statistics")
        print_result(True, f"Total callbacks: {callback_data['calls']}")
        print_result(True, f"Phases detected: {', '.join(sorted(callback_data['phases']))}")
        print_result(True, f"Max percentage: {callback_data['max_percentage']:.1f}%")
        
        # Validate callback behavior
        if callback_data['calls'] < 5:
            print_result(False, "Too few callbacks (expected at least 5)")
        else:
            print_result(True, f"Sufficient callbacks ({callback_data['calls']})")
        
        if callback_data['max_percentage'] < 90:
            print_result(False, f"Progress didn't reach 90% (got {callback_data['max_percentage']:.1f}%)")
        else:
            print_result(True, f"Progress reached {callback_data['max_percentage']:.1f}%")
        
        if not df.empty:
            print_result(True, f"Parsed {len(df)} records")
        else:
            print_result(False, "DataFrame is empty")
        
    except Exception as e:
        print_result(False, f"Exception: {e}")
        import traceback
        traceback.print_exc()

# ============================================
# TEST 3: CONCURRENT FILE PARSING
# ============================================

def concurrent_file_test():
    """Test concurrent file parsing by multiple users."""
    print_header("TEST 3: CONCURRENT FILE PARSING")
    
    if not MIB_FILE.exists():
        print_result(False, f"MIB file not found: {MIB_FILE}")
        return
    
    results = {}
    errors = {}
    
    def parse_job(user_id: int):
        try:
            config = Config()
            parser = MibParser(config)
            
            start_time = time.time()
            df = parser.parse_file(str(MIB_FILE))
            elapsed = time.time() - start_time
            
            results[user_id] = {
                'records': len(df),
                'elapsed': elapsed,
                'success': not df.empty
            }
        except Exception as e:
            errors[user_id] = str(e)
    
    print_subheader("Starting 3 concurrent users")
    threads = [threading.Thread(target=parse_job, args=(i,)) for i in range(3)]
    
    start_time = time.time()
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    total_elapsed = time.time() - start_time
    
    print_subheader("Results")
    
    # Check results
    success_count = sum(1 for r in results.values() if r['success'])
    
    for user_id in range(3):
        if user_id in results:
            r = results[user_id]
            status = "✅" if r['success'] else "❌"
            print(f"  {status} User {user_id}: {r['records']} records in {r['elapsed']:.2f}s")
        elif user_id in errors:
            print(f"  ❌ User {user_id}: ERROR - {errors[user_id]}")
        else:
            print(f"  ❌ User {user_id}: No result")
    
    print(f"\n  Total time: {total_elapsed:.2f}s")
    
    # Validate
    if success_count == 3:
        print_result(True, "All 3 users succeeded")
    else:
        print_result(False, f"Only {success_count}/3 users succeeded")
    
    # Check that all got same record count
    if results:
        record_counts = [r['records'] for r in results.values()]
        if len(set(record_counts)) == 1:
            print_result(True, f"All users got same record count ({record_counts[0]})")
        else:
            print_result(False, f"Users got different record counts: {record_counts}")

# ============================================
# TEST 4: CONCURRENT DIRECTORY PARSING
# ============================================

def concurrent_directory_test():
    """Test concurrent directory parsing by multiple users."""
    print_header("TEST 4: CONCURRENT DIRECTORY PARSING")
    
    if not MIB_DIR.exists():
        print_result(False, f"MIB directory not found: {MIB_DIR}")
        return
    
    results = {}
    errors = {}
    
    def parse_job(user_id: int):
        try:
            config = Config()
            parser = MibParser(config)
            
            start_time = time.time()
            df = parser.parse_directory(str(MIB_DIR))
            elapsed = time.time() - start_time
            
            results[user_id] = {
                'records': len(df),
                'elapsed': elapsed,
                'success': not df.empty
            }
        except Exception as e:
            errors[user_id] = str(e)
    
    print_subheader("Starting 3 concurrent users")
    threads = [threading.Thread(target=parse_job, args=(i,)) for i in range(3)]
    
    start_time = time.time()
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    total_elapsed = time.time() - start_time
    
    print_subheader("Results")
    
    # Check results
    success_count = sum(1 for r in results.values() if r['success'])
    
    for user_id in range(3):
        if user_id in results:
            r = results[user_id]
            status = "✅" if r['success'] else "❌"
            print(f"  {status} User {user_id}: {r['records']} records in {r['elapsed']:.2f}s")
        elif user_id in errors:
            print(f"  ❌ User {user_id}: ERROR - {errors[user_id]}")
        else:
            print(f"  ❌ User {user_id}: No result")
    
    print(f"\n  Total time: {total_elapsed:.2f}s")
    
    # Validate
    if success_count == 3:
        print_result(True, "All 3 users succeeded")
    else:
        print_result(False, f"Only {success_count}/3 users succeeded")
    
    # Check that all got same record count
    if results:
        record_counts = [r['records'] for r in results.values()]
        if len(set(record_counts)) == 1:
            print_result(True, f"All users got same record count ({record_counts[0]})")
        else:
            print_result(False, f"Users got different record counts: {record_counts}")

# ============================================
# MAIN TEST RUNNER
# ============================================

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  MIB PARSER COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    # Map test names to functions
    test_functions = {
        'field_enrichment_test': field_enrichment_test,
        'progress_callback_test': progress_callback_test,
        'concurrent_file_test': concurrent_file_test,
        'concurrent_directory_test': concurrent_directory_test
    }
    
    for test_name in TEST_LIST:
        print_header(f"PREPARING: {test_name}")
        clear_cache()
        
        if test_name in test_functions:
            try:
                test_functions[test_name]()
            except Exception as e:
                print_result(False, f"Test crashed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print_result(False, f"Test '{test_name}' not found")
    
    print("\n" + "=" * 70)
    print("  ALL TESTS COMPLETED")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
