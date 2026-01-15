#!/usr/bin/env python3
"""
SNMP Trap Sender Service
Handles sending SNMP traps to target devices
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# ✅ CORRECT IMPORTS for pysnmp
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    send_notification,
)
from pysnmp.proto.rfc1902 import (
    Counter32,
    Counter64,
    Gauge32,
    Integer,
    Integer32,
    IpAddress,
    OctetString,
    TimeTicks,
    Unsigned32,
)

from backend.services.trap_builder_service import TrapBuilderService
from backend.services.metrics_service import get_metrics_service
from utils.logger import get_logger

logger = get_logger(__name__)


class TrapSenderService:
    """
    Service for sending SNMP traps.
    
    Features:
    - Build SNMP v2c traps
    - Send to target device
    - Validate varbinds
    - Log sent traps
    - Use TrapBuilderService for notification lookup
    """
    
    # Supported data types
    DATA_TYPES = {
        'Integer': Integer,
        'Integer32': Integer32,
        'Unsigned32': Unsigned32,
        'Counter32': Counter32,
        'Counter64': Counter64,
        'Gauge32': Gauge32,
        'TimeTicks': TimeTicks,
        'OctetString': OctetString,
        'IpAddress': IpAddress,
        'String': OctetString,  # Alias
    }
    
    def __init__(self, db_manager):
        """Initialize trap sender service."""
        self.db = db_manager
        self.logger = logger
        self.engine = SnmpEngine()
        
        # ✅ NEW: Initialize TrapBuilderService
        self.trap_builder = TrapBuilderService(db_manager)
        
        self.logger.info("✅ TrapSenderService initialized")
    
    # ✅ NEW: Method to get notification from trap_master_data
    def get_notification_by_name(self, notification_name: str) -> Optional[Dict]:
        """
        Get notification details by name.
        
        Args:
            notification_name: Notification name (e.g., 'linkDown')
        
        Returns:
            Notification details or None
        """
        return self.trap_builder.get_notification(notification_name)
    
    # ✅ NEW: Method to get notification objects
    def get_notification_objects(self, notification_name: str) -> List[Dict]:
        """
        Get objects for a notification.
        
        Args:
            notification_name: Notification name
        
        Returns:
            List of notification objects
        """
        return self.trap_builder.get_notification_objects(notification_name)
    
    # ✅ NEW: Method to build trap from notification name
    async def build_trap_from_notification(
        self,
        notification_name: str,
        varbind_values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build trap from notification name and varbind values.
        
        Args:
            notification_name: Notification name (e.g., 'linkDown')
            varbind_values: Dict mapping object name -> value
                           e.g., {'ifIndex': 5, 'ifAdminStatus': 2}
        
        Returns:
            Trap structure ready to send
        """
        # Get trap structure
        trap = self.trap_builder.build_trap_structure(notification_name)
        
        # Fill in values
        for varbind in trap['varbinds']:
            obj_name = varbind['name']
            if obj_name in varbind_values:
                varbind['value'] = varbind_values[obj_name]
        
        return trap
    
    async def send_trap(
        self,
        trap_oid: str,
        target_host: str,
        target_port: int = 1162,
        varbinds: Optional[List[Dict]] = None,
        snmp_version: str = 'v2c',
        community: str = 'public',
        template_id: Optional[int] = None,
        trap_name: Optional[str] = None,  # ✅ NEW: Accept trap name
        original_varbinds: Optional[List[Dict]] = None  # ✅ NEW: Accept original varbinds with names
    ) -> Dict[str, Any]:
        """
        Send SNMP trap to target device.
        
        Args:
            trap_oid: Trap notification OID
            target_host: Target IP/hostname
            target_port: Target UDP port (default 1162)
            varbinds: List of varbinds with OIDs [{"oid": "...", "type": "...", "value": "..."}]
            snmp_version: SNMP version (v2c)
            community: SNMP community string
            template_id: Optional template ID for logging
            trap_name: Optional trap name (if known)
            original_varbinds: Optional varbinds with names for storage
            
        Returns:
            Dict with status and details
        """
        start_time = time.time()
        metrics = get_metrics_service()
        
        try:
            self.logger.info(f"📤 Sending trap {trap_oid} to {target_host}:{target_port}")
            
            # Validate inputs
            if not trap_oid:
                raise ValueError("Trap OID is required")
            
            if not target_host:
                raise ValueError("Target host is required")
            
            # Build varbinds for sending (uses OIDs)
            var_binds = await self._build_varbinds(varbinds or [])
            
            # Create snmpTrapOID.0 varbind
            trap_oid_varbind = ObjectType(
                ObjectIdentity('1.3.6.1.6.3.1.1.4.1.0'),  # snmpTrapOID.0
                OctetString(trap_oid)
            )
            
            # Combine: snmpTrapOID.0 + user varbinds
            all_varbinds = [trap_oid_varbind] + var_binds
            
            # Create transport
            transport = await UdpTransportTarget.create((target_host, target_port))
            
            # Send notification
            error_indication, error_status, error_index, var_bind_table = await send_notification(
                self.engine,
                CommunityData(community, mpModel=1),  # v2c
                transport,
                ContextData(),
                'trap',
                *all_varbinds
            )
            
            # Check for errors
            if error_indication:
                error_msg = str(error_indication)

                if metrics:
                    # Check if timeout
                    if 'timeout' in error_msg.lower():
                        metrics.counter('snmp_traps_sent_total', {'status': 'timeout'})
                    else:
                        metrics.counter('snmp_traps_sent_total', {'status': 'failed'})

                self.logger.error(f"❌ Trap send failed: {error_msg}")
                
                # Log failed trap
                self._log_sent_trap(
                    template_id=template_id,
                    trap_oid=trap_oid,
                    trap_name=trap_name,
                    target_host=target_host,
                    target_port=target_port,
                    snmp_version=snmp_version,
                    community=community,
                    varbinds=original_varbinds or varbinds,  # ✅ Store original names
                    status='failed',
                    error_message=error_msg
                )
                
                return {
                    'success': False,
                    'error': error_msg,
                    'duration': time.time() - start_time
                }
            
            elif error_status:
                error_msg = f"{error_status.prettyPrint()} at {error_index}"

                if metrics:
                    metrics.counter('snmp_traps_sent_total', {'status': 'failed'})

                self.logger.error(f"❌ Trap send failed: {error_msg}")
                
                # Log failed trap
                self._log_sent_trap(
                    template_id=template_id,
                    trap_oid=trap_oid,
                    trap_name=trap_name,
                    target_host=target_host,
                    target_port=target_port,
                    snmp_version=snmp_version,
                    community=community,
                    varbinds=original_varbinds or varbinds,  # ✅ Store original names
                    status='failed',
                    error_message=error_msg
                )
                
                return {
                    'success': False,
                    'error': error_msg,
                    'duration': time.time() - start_time
                }
            
            # Success
            duration = time.time() - start_time

            if metrics:
                metrics.counter('snmp_traps_sent_total', {'status': 'success'})
                metrics.gauge_set('snmp_trap_send_duration_seconds', round(duration, 3))
                metrics.counter_add('snmp_trap_send_duration_total_seconds', round(duration, 3))

            self.logger.info(f"✅ Trap sent successfully in {duration:.2f}s")
            
            # Log successful trap
            trap_id = self._log_sent_trap(
                template_id=template_id,
                trap_oid=trap_oid,
                trap_name=trap_name,
                target_host=target_host,
                target_port=target_port,
                snmp_version=snmp_version,
                community=community,
                varbinds=original_varbinds or varbinds,  # ✅ Store original names
                status='success',
                error_message=None
            )
            
            return {
                'success': True,
                'trap_id': trap_id,
                'trap_name': trap_name,
                'duration': duration,
                'varbinds_sent': len(varbinds or [])
            }
            
        except Exception as e:
            error_msg = str(e)

            if metrics:
                metrics.counter('snmp_traps_sent_total', {'status': 'failed'})

            self.logger.error(f"❌ Trap send exception: {error_msg}", exc_info=True)
            
            # Log failed trap
            self._log_sent_trap(
                template_id=template_id,
                trap_oid=trap_oid,
                trap_name=trap_name,
                target_host=target_host,
                target_port=target_port,
                snmp_version=snmp_version,
                community=community,
                varbinds=original_varbinds or varbinds,  # ✅ Store original names
                status='failed',
                error_message=error_msg
            )
            
            return {
                'success': False,
                'error': error_msg,
                'duration': time.time() - start_time
            }

    async def _build_varbinds(self, varbinds: List[Dict]) -> List[ObjectType]:
        """Build pysnmp varbinds from dict list."""
        from pysnmp.proto import rfc1902
        
        result = []
        
        for vb in varbinds:
            try:
                oid = vb.get('oid')
                data_type = vb.get('type', 'OctetString')
                value = vb.get('value')
                
                if not oid:
                    self.logger.warning(f"Skipping varbind without OID: {vb}")
                    continue
                
                # Get data type class
                type_class = self.DATA_TYPES.get(data_type, OctetString)
                
                # Convert value to appropriate type
                if type_class in [Integer, Integer32, Unsigned32, Counter32, Counter64, Gauge32, TimeTicks]:
                    typed_value = type_class(int(value))
                elif type_class == IpAddress:
                    typed_value = type_class(value)
                else:
                    typed_value = type_class(str(value))
                
                # Convert OID string to tuple
                oid_clean = oid.strip('.')
                oid_tuple = tuple(int(x) for x in oid_clean.split('.'))
                
                # Create ObjectName (OID) directly
                oid_obj = rfc1902.ObjectName(oid_tuple)
                
                # Create ObjectType with OID and value
                obj = ObjectType(ObjectIdentity(oid_obj), typed_value)
                
                result.append(obj)
                
            except Exception as e:
                self.logger.warning(f"Failed to build varbind {vb}: {e}")
                continue
        
        return result
    
    def validate_varbinds(self, varbinds: List[Dict]) -> tuple[bool, Optional[str]]:
        """Validate varbind structure."""
        if not isinstance(varbinds, list):
            return False, "Varbinds must be a list"
        
        for i, vb in enumerate(varbinds):
            if not isinstance(vb, dict):
                return False, f"Varbind {i} must be a dict"
            
            if 'oid' not in vb:
                return False, f"Varbind {i} missing 'oid'"
            
            if 'value' not in vb:
                return False, f"Varbind {i} missing 'value'"
            
            # Validate OID format
            oid = vb['oid']
            if not isinstance(oid, str) or not oid.startswith('1.'):
                return False, f"Varbind {i} has invalid OID format: {oid}"
            
            # Validate data type
            data_type = vb.get('type', 'OctetString')
            if data_type not in self.DATA_TYPES:
                return False, f"Varbind {i} has unsupported type: {data_type}"
        
        return True, None
    
    def _log_sent_trap(
        self,
        template_id: Optional[int],
        trap_oid: str,
        trap_name: Optional[str],
        target_host: str,
        target_port: int,
        snmp_version: str,
        community: str,
        varbinds: Optional[List[Dict]],
        status: str,
        error_message: Optional[str]
    ) -> int:
        """Log sent trap to database with original names."""
        try:
            from sqlalchemy import text
            
            varbinds_json = json.dumps(varbinds) if varbinds else None
            
            # ✅ UPDATED: Include trap_name
            query = text("""
                INSERT INTO sent_traps (
                    template_id, trap_oid, trap_name,
                    target_host, target_port, snmp_version, community,
                    varbinds, status, error_message
                ) VALUES (
                    :template_id, :trap_oid, :trap_name,
                    :target_host, :target_port, :snmp_version, :community,
                    :varbinds, :status, :error_message
                )
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, {
                    'template_id': template_id,
                    'trap_oid': trap_oid,
                    'trap_name': trap_name,
                    'target_host': target_host,
                    'target_port': target_port,
                    'snmp_version': snmp_version,
                    'community': community,
                    'varbinds': varbinds_json,
                    'status': status,
                    'error_message': error_message
                })
                conn.commit()
                
                trap_id = result.lastrowid
                self.logger.info(f"✅ Logged trap with ID: {trap_id}")
                return trap_id
            
        except Exception as e:
            self.logger.error(f"Failed to log sent trap: {e}", exc_info=True)
            return -1
    
    def get_sent_history(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get sent trap history with names."""
        try:
            # ✅ UPDATED: Include trap_name
            query = f"""
                SELECT 
                    id, template_id, trap_oid, trap_name,
                    target_host, target_port, snmp_version, community,
                    varbinds, status, error_message, sent_at
                FROM sent_traps
                ORDER BY sent_at DESC
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
            self.logger.error(f"Failed to get sent history: {e}", exc_info=True)
            return []
    
    def get_data_types(self) -> List[str]:
        """Get list of supported data types."""
        return list(self.DATA_TYPES.keys())
