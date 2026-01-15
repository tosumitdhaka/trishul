#!/usr/bin/env python3
"""
SNMP Trap Receiver Service
Handles receiving and parsing SNMP traps
"""

import asyncio
import json
import time
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto import rfc1905

from backend.services.oid_resolver_service import OIDResolverService
from backend.services.metrics_service import get_metrics_service
from utils.logger import get_logger

logger = get_logger(__name__)


class TrapReceiverService:
    """
    Service for receiving SNMP traps.
    
    Features:
    - Listen on UDP port for incoming traps
    - Parse trap data
    - Resolve OIDs using trap_master_data
    - Store in database
    - Broadcast via WebSocket
    """
    
    def __init__(self, db_manager, ws_manager=None):
        """
        Initialize trap receiver service.
        
        Args:
            db_manager: Database manager instance
            ws_manager: WebSocket manager for broadcasting (optional)
        """
        self.db = db_manager
        self.ws_manager = ws_manager
        self.logger = logger
        
        # ✅ NEW: Initialize OID resolver
        self.oid_resolver = OIDResolverService(db_manager)
        
        # Receiver state
        self.running = False
        self.engine = None
        self.transport = None
        self.listener_task = None
        
        # Configuration
        self.listen_port = 1162
        self.bind_address = '0.0.0.0'
        self.community = 'public'
        
        # Statistics
        self.stats = {
            'traps_received': 0,
            'start_time': None,
            'last_trap_time': None
        }
        
        self.metrics = get_metrics_service()

        self.logger.info("✅ TrapReceiverService initialized")
    
    async def start(
        self,
        port: int = 1162,
        bind_address: str = '0.0.0.0',
        community: str = 'public'
    ) -> Dict[str, Any]:
        """Start trap receiver."""
        if self.running:
            return {
                'success': False,
                'error': 'Receiver already running'
            }
        
        try:
            self.listen_port = port
            self.bind_address = bind_address
            self.community = community
            
            self.logger.info(f"🎧 Starting trap receiver on {bind_address}:{port}")
            
            # Create SNMP engine
            self.engine = engine.SnmpEngine()
            
            # Configure transport
            config.addTransport(
                self.engine,
                udp.domainName,
                udp.UdpTransport().openServerMode((bind_address, port))
            )
            
            # Configure community
            config.addV1System(self.engine, 'my-area', community)
            
            # Register callback
            ntfrcv.NotificationReceiver(self.engine, self._trap_callback_simple)
            
            # Start listener in background
            self.running = True
            self.stats['start_time'] = datetime.now()
            self.listener_task = asyncio.create_task(self._run_dispatcher())
            
            self.logger.info(f"✅ Trap receiver started on {bind_address}:{port}")
            
            return {
                'success': True,
                'message': f'Receiver started on {bind_address}:{port}',
                'port': port,
                'bind_address': bind_address
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start receiver: {e}", exc_info=True)
            self.running = False
            return {
                'success': False,
                'error': str(e)
            }
    
    async def stop(self) -> Dict[str, Any]:
        """Stop trap receiver."""
        if not self.running:
            return {
                'success': False,
                'error': 'Receiver not running'
            }
        
        try:
            self.logger.info("🛑 Stopping trap receiver...")
            
            self.running = False
            
            # Cancel listener task
            if self.listener_task:
                self.listener_task.cancel()
                try:
                    await self.listener_task
                except asyncio.CancelledError:
                    pass
            
            # Close transport
            if self.engine:
                self.engine.transportDispatcher.closeDispatcher()
            
            self.logger.info("✅ Trap receiver stopped")
            
            return {
                'success': True,
                'message': 'Receiver stopped',
                'traps_received': self.stats['traps_received']
            }
            
        except Exception as e:
            self.logger.error(f"❌ Failed to stop receiver: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _run_dispatcher(self):
        """Run SNMP dispatcher loop."""
        try:
            self.logger.info("🔄 Dispatcher loop started")
            
            while self.running:
                self.engine.transportDispatcher.runDispatcher(timeout=0.5)
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            self.logger.info("Dispatcher loop cancelled")
        except Exception as e:
            self.logger.error(f"Dispatcher error: {e}", exc_info=True)
    
    def _trap_callback_simple(
        self,
        snmpEngine,
        stateReference,
        contextEngineId,
        contextName,
        varBinds,
        cbCtx
    ):
        """Callback for received traps."""

        processing_start = time.time()

        try:
            source_ip = "127.0.0.1"
            source_port = 0
            
            self.logger.info(f"📨 Received trap from {source_ip}:{source_port}")
            
            # Parse trap data
            trap_data = self._parse_trap(varBinds, source_ip, source_port)
            
            # ✅ NEW: Resolve OIDs
            trap_data = self._resolve_trap_oids(trap_data)
            
            # Store in database
            trap_id = self._store_trap(trap_data)
            trap_data['id'] = trap_id
            
            # Update statistics
            self.stats['traps_received'] += 1
            self.stats['last_trap_time'] = datetime.now()

            processing_duration = time.time() - processing_start
            if self.metrics:
                self.metrics.counter('snmp_traps_received_total')
                self.metrics.gauge_set('snmp_trap_receive_duration_seconds', round(processing_duration, 3))
                self.metrics.counter_add('snmp_trap_receive_duration_total_seconds', round(processing_duration, 3))
            
            # Broadcast via WebSocket
            if self.ws_manager:
                asyncio.create_task(self._broadcast_trap(trap_data))
            
            self.logger.info(f"✅ Trap processed: ID={trap_id}, Varbinds={len(trap_data['varbinds'])}")
            
        except Exception as e:
            self.logger.error(f"❌ Trap callback error: {e}", exc_info=True)
    
    def _parse_trap(
        self,
        varBinds,
        source_ip: str,
        source_port: int
    ) -> Dict[str, Any]:
        """Parse trap varbinds."""
        trap_data = {
            'source_ip': source_ip,
            'source_port': source_port,
            'trap_oid': None,
            'enterprise_oid': None,
            'timestamp': None,
            'varbinds': [],
            'snmp_version': 'v2c',
            'community': self.community,
            'raw_data': None
        }
        
        varbind_list = []
        
        for oid, val in varBinds:
            oid_str = str(oid)
            val_str = str(val)
            
            # Check for standard trap OIDs
            if oid_str == '1.3.6.1.6.3.1.1.4.1.0':  # snmpTrapOID.0
                trap_data['trap_oid'] = val_str
            elif oid_str == '1.3.6.1.2.1.1.3.0':  # sysUpTime.0
                trap_data['timestamp'] = val_str
            elif oid_str == '1.3.6.1.6.3.1.1.4.3.0':  # snmpTrapEnterprise.0
                trap_data['enterprise_oid'] = val_str
            
            # Add to varbinds list
            varbind_list.append({
                'oid': oid_str,
                'value': val_str,
                'type': type(val).__name__
            })
        
        trap_data['varbinds'] = varbind_list
        trap_data['raw_data'] = json.dumps(varbind_list)
        
        return trap_data
    
    def _resolve_trap_oids(self, trap_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve OIDs in trap using trap_master_data.
        
        Args:
            trap_data: Parsed trap data
        
        Returns:
            Trap data with resolved OID names
        """
        try:
            # ✅ FIX 1: Resolve trap OID separately (from notification_oid column)
            if trap_data['trap_oid']:
                trap_oid = trap_data['trap_oid']
                
                # Query notification_oid column specifically
                query = f"""
                    SELECT 
                        notification_name,
                        notification_description,
                        module_name
                    FROM trap_master_data
                    WHERE notification_oid = '{trap_oid}'
                    LIMIT 1
                """
                
                df = self.db.db_to_df(
                    table=None,
                    database='data',
                    query=query
                )
                
                if not df.empty:
                    row = df.iloc[0]
                    trap_data['trap_name'] = row['notification_name']
                    trap_data['trap_description'] = row['notification_description']
                    trap_data['trap_module'] = row['module_name']
                    self.logger.info(f"✅ Resolved trap: {trap_data['trap_name']}")
                else:
                    self.logger.warning(f"⚠️  Trap OID not found: {trap_oid}")
            
            # ✅ FIX 2: Collect varbind OIDs (excluding standard SNMP OIDs)
            oids_to_resolve = []
            standard_oids = [
                '1.3.6.1.2.1.1.3.0',        # sysUpTime.0
                '1.3.6.1.6.3.1.1.4.1.0',    # snmpTrapOID.0
                '1.3.6.1.6.3.1.1.4.3.0',    # snmpTrapEnterprise.0
            ]
            
            for vb in trap_data['varbinds']:
                oid = vb['oid']
                
                # Skip standard SNMP OIDs (they won't be in MIB data)
                if oid in standard_oids:
                    # Add standard names manually
                    if oid == '1.3.6.1.2.1.1.3.0':
                        vb['name'] = 'sysUpTime'
                        vb['description'] = 'System uptime'
                        vb['resolved'] = True
                    elif oid == '1.3.6.1.6.3.1.1.4.1.0':
                        vb['name'] = 'snmpTrapOID'
                        vb['description'] = 'The authoritative identification of the notification'
                        vb['resolved'] = True
                    elif oid == '1.3.6.1.6.3.1.1.4.3.0':
                        vb['name'] = 'snmpTrapEnterprise'
                        vb['description'] = 'The enterprise OID'
                        vb['resolved'] = True
                else:
                    oids_to_resolve.append(oid)
            
            # Batch resolve remaining OIDs
            if oids_to_resolve:
                resolved = self.oid_resolver.resolve_batch(oids_to_resolve)
                
                # Add resolved names to varbinds
                for vb in trap_data['varbinds']:
                    if vb['oid'] in resolved:
                        vb['name'] = resolved[vb['oid']]['name']
                        vb['description'] = resolved[vb['oid']]['description']
                        vb['syntax'] = resolved[vb['oid']]['syntax']
                        vb['resolved'] = True
                    elif vb['oid'] not in standard_oids:
                        # Not resolved and not a standard OID
                        vb['name'] = None
                        vb['description'] = None
                        vb['resolved'] = False
            
            # Calculate resolution statistics
            resolved_count = sum(1 for vb in trap_data['varbinds'] if vb.get('resolved'))
            total_count = len(trap_data['varbinds'])
            trap_data['resolution_stats'] = {
                'resolved': resolved_count,
                'total': total_count,
                'percentage': (resolved_count / total_count * 100) if total_count > 0 else 0
            }
            
            self.logger.info(
                f"Resolved {resolved_count}/{total_count} varbinds "
                f"({trap_data['resolution_stats']['percentage']:.1f}%)"
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to resolve OIDs: {e}")
        
        return trap_data
    
    def _store_trap(self, trap_data: Dict[str, Any]) -> int:
        """Store received trap in database."""
        try:
            from sqlalchemy import text
            
            varbinds_json = json.dumps(trap_data['varbinds'])
            
            # ✅ UPDATED: Include trap_name and trap_description
            query = text("""
                INSERT INTO received_traps (
                    source_ip, source_port, trap_oid, enterprise_oid,
                    timestamp, varbinds, snmp_version, community, raw_data,
                    trap_name, trap_description
                ) VALUES (
                    :source_ip, :source_port, :trap_oid, :enterprise_oid,
                    :timestamp, :varbinds, :snmp_version, :community, :raw_data,
                    :trap_name, :trap_description
                )
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, {
                    'source_ip': trap_data['source_ip'],
                    'source_port': trap_data['source_port'],
                    'trap_oid': trap_data['trap_oid'],
                    'enterprise_oid': trap_data['enterprise_oid'],
                    'timestamp': trap_data['timestamp'],
                    'varbinds': varbinds_json,
                    'snmp_version': trap_data['snmp_version'],
                    'community': trap_data['community'],
                    'raw_data': trap_data['raw_data'],
                    'trap_name': trap_data.get('trap_name'),  # ✅ NEW
                    'trap_description': trap_data.get('trap_description')  # ✅ NEW
                })
                conn.commit()
                
                trap_id = result.lastrowid
                return trap_id
                
        except Exception as e:
            self.logger.error(f"Failed to store trap: {e}", exc_info=True)
            return -1

    
    async def _broadcast_trap(self, trap_data: Dict[str, Any]):
        """Broadcast trap via WebSocket."""
        try:
            if self.ws_manager:
                message = {
                    'type': 'trap_received',
                    'data': trap_data
                }
                await self.ws_manager.broadcast(json.dumps(message))
                self.logger.debug(f"📡 Broadcasted trap via WebSocket")
        except Exception as e:
            self.logger.error(f"Failed to broadcast trap: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get receiver status."""
        uptime = None
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            'running': self.running,
            'port': self.listen_port,
            'bind_address': self.bind_address,
            'community': self.community,
            'traps_received': self.stats['traps_received'],
            'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'last_trap_time': self.stats['last_trap_time'].isoformat() if self.stats['last_trap_time'] else None,
            'uptime_seconds': uptime
        }
    
    def get_received_traps(
        self,
        limit: int = 100,
        offset: int = 0,
        source_ip: Optional[str] = None,
        trap_oid: Optional[str] = None
    ) -> List[Dict]:
        """Get received traps from database."""
        try:
            # Build WHERE clause
            where_clauses = []
            if source_ip:
                where_clauses.append(f"source_ip = '{source_ip}'")
            if trap_oid:
                where_clauses.append(f"trap_oid = '{trap_oid}'")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # ✅ UPDATED: Include trap_name and trap_description
            query = f"""
                SELECT 
                    id, source_ip, source_port, trap_oid, trap_name, trap_description,
                    enterprise_oid, timestamp, varbinds, snmp_version, community, 
                    raw_data, received_at
                FROM received_traps
                WHERE {where_sql}
                ORDER BY received_at DESC
                LIMIT {limit} OFFSET {offset}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            if df.empty:
                return []
            
            records = df.to_dict('records')
            
            # Parse varbinds JSON
            for record in records:
                if record.get('varbinds'):
                    try:
                        record['varbinds'] = json.loads(record['varbinds'])
                    except:
                        record['varbinds'] = []
                else:
                    record['varbinds'] = []
            
            return records
            
        except Exception as e:
            self.logger.error(f"Failed to get received traps: {e}", exc_info=True)
            return []
    
    def clear_received_traps(self) -> Dict[str, Any]:
        """Clear all received traps from database."""
        try:
            from sqlalchemy import text
            
            query = text("DELETE FROM received_traps")
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query)
                conn.commit()
                
                deleted_count = result.rowcount
            
            self.logger.info(f"✅ Cleared {deleted_count} received traps")
            
            return {
                'success': True,
                'deleted_count': deleted_count
            }
            
        except Exception as e:
            self.logger.error(f"Failed to clear traps: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
