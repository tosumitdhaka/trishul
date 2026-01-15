"""
Test trap receiver
"""

import sys
import asyncio
sys.path.insert(0, '.')

from backend.services.trap_receiver import TrapReceiverService
from backend.services.trap_sender import TrapSenderService
from services.db_service import DatabaseManager
from services.config_service import Config

async def test_receiver():
    print("=" * 60)
    print("SNMP Trap Receiver Test")
    print("=" * 60)
    
    # Initialize
    config = Config()
    db = DatabaseManager(config)
    
    # Create receiver
    receiver = TrapReceiverService(db)
    
    # Test 1: Start receiver
    print("\n1. Starting trap receiver...")
    result = await receiver.start(port=1162, bind_address='0.0.0.0')
    print(f"   Result: {result}")
    
    if not result['success']:
        print("   ❌ Failed to start receiver")
        return
    
    # Test 2: Check status
    print("\n2. Checking receiver status...")
    status = receiver.get_status()
    print(f"   Running: {status['running']}")
    print(f"   Port: {status['port']}")
    print(f"   Traps received: {status['traps_received']}")
    
    # Test 3: Send a trap to ourselves
    print("\n3. Sending test trap to receiver...")
    sender = TrapSenderService(db)
    
    send_result = await sender.send_trap(
        trap_oid="1.3.6.1.6.3.1.1.5.3",
        target_host="127.0.0.1",
        target_port=1162,
        varbinds=[
            {"oid": "1.3.6.1.2.1.1.1.0", "type": "OctetString", "value": "Test System"},
            {"oid": "1.3.6.1.2.1.1.3.0", "type": "TimeTicks", "value": "12345"}
        ]
    )
    
    print(f"   Send result: {send_result}")
    
    # Wait for trap to be received
    print("\n4. Waiting for trap to be received...")
    await asyncio.sleep(2)
    
    # Test 4: Check received traps
    print("\n5. Checking received traps...")
    traps = receiver.get_received_traps(limit=5)
    print(f"   Found {len(traps)} received traps")
    
    if traps:
        print("\n   Recent traps:")
        for trap in traps[:3]:
            print(f"   - From: {trap['source_ip']}:{trap['source_port']}")
            print(f"     Trap OID: {trap['trap_oid']}")
            print(f"     Varbinds: {len(trap['varbinds'])}")
            print(f"     Received: {trap['received_at']}")
    
    # Test 5: Stop receiver
    print("\n6. Stopping receiver...")
    stop_result = await receiver.stop()
    print(f"   Result: {stop_result}")
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_receiver())
