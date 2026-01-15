"""
Quick test for trap sending
"""

import sys
import asyncio
sys.path.insert(0, '.')

from backend.services.trap_sender import TrapSenderService
from services.db_service import DatabaseManager
from services.config_service import Config

async def test_trap():
    # Initialize
    config = Config()
    db = DatabaseManager(config)
    sender = TrapSenderService(db)
    
    print("=" * 60)
    print("SNMP Trap Sender Test")
    print("=" * 60)
    
    # Test 1: Validate varbinds
    print("\n1. Testing varbind validation...")
    varbinds = [
        {"oid": "1.3.6.1.2.1.1.1.0", "type": "OctetString", "value": "Test System"},
        {"oid": "1.3.6.1.2.1.1.3.0", "type": "TimeTicks", "value": "12345"}
    ]
    
    is_valid, error = sender.validate_varbinds(varbinds)
    print(f"   Valid: {is_valid}")
    if error:
        print(f"   Error: {error}")
    
    # Test 2: Get data types
    print("\n2. Getting supported data types...")
    types = sender.get_data_types()
    print(f"   Supported types: {', '.join(types)}")
    
    # Test 3: Send trap to localhost (ASYNC)
    print("\n3. Sending test trap to localhost:1162...")
    print("   (This will fail if no receiver is running, but tests the sending logic)")
    
    result = await sender.send_trap(  # ✅ Added await
        trap_oid="1.3.6.1.6.3.1.1.5.3",  # linkDown
        target_host="127.0.0.1",
        target_port=1162,
        varbinds=varbinds,
        community="public"
    )
    
    print(f"\n   Result:")
    print(f"   - Success: {result['success']}")
    print(f"   - Duration: {result['duration']:.3f}s")
    if result['success']:
        print(f"   - Trap ID: {result.get('trap_id')}")
        print(f"   - Varbinds sent: {result.get('varbinds_sent')}")
    else:
        print(f"   - Error: {result.get('error')}")
    
    # Test 4: Get sent history
    print("\n4. Getting sent trap history...")
    history = sender.get_sent_history(limit=5)
    print(f"   Found {len(history)} sent traps")
    
    if history:
        print("\n   Recent traps:")
        for trap in history[:3]:
            print(f"   - {trap['trap_oid']} to {trap['target_host']}:{trap['target_port']}")
            print(f"     Status: {trap['status']}, Sent: {trap['sent_at']}")
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_trap())
