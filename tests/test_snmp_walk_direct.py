# test_snmp_walk_direct.py
import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

async def test_walk():
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create(('192.168.151.114', 161), timeout=5, retries=1)
    
    # Test with bulk_cmd
    error_indication, error_status, error_index, var_bind_table = await bulk_cmd(
        engine,
        CommunityData('public', mpModel=1),
        transport,
        ContextData(),
        0, 25,
        ObjectType(ObjectIdentity('1.3.6.1.2.1.1')),
        lexicographicMode=False
    )
    
    if error_indication:
        print(f"Error: {error_indication}")
    elif error_status:
        print(f"Error: {error_status}")
    else:
        print(f"Success! Got {len(var_bind_table)} rows")
        
        # ✅ FIX: var_bind_table is a list of ObjectType objects
        for var_bind in var_bind_table:
            # Each var_bind is an ObjectType with [0]=OID, [1]=value
            oid = var_bind[0]
            val = var_bind[1]
            print(f"  {oid} = {val}")

asyncio.run(test_walk())
