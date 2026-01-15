#!/usr/bin/env python3
"""
SNMP Walk Service

Handles SNMP walk operations on devices using SNMPv2c
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.services.oid_resolver_service import OIDResolverService
from backend.services.metrics_service import get_metrics_service
from utils.logger import get_logger

logger = get_logger(__name__)


class SNMPWalkService:
    """
    Service for SNMP walk operations.
    
    Features:
    - Device management (CRUD)
    - Walk configuration management (CRUD)
    - Execute SNMP walks
    - Resolve OIDs using trap_master_data
    - Store results in database
    - Query historical results
    """
    
    def __init__(self, db_manager, ws_manager=None):
        """
        Initialize SNMP walk service.
        
        Args:
            db_manager: Database manager instance
            ws_manager: WebSocket manager for broadcasting (optional)
        """
        self.db = db_manager
        self.ws_manager = ws_manager
        self.logger = logger

        # ✅ Import SnmpEngine
        from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
        self.engine = SnmpEngine()
        
        # Initialize OID resolver
        self.oid_resolver = OIDResolverService(db_manager)

        self.metrics = get_metrics_service()
        
        self.logger.info("✅ SNMPWalkService initialized")
    
    # ============================================
    # DEVICE MANAGEMENT
    # ============================================
    
    def create_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new SNMP device."""
        try:
            from sqlalchemy import text
            
            query = text("""
                INSERT INTO snmp_devices (
                    name, ip_address, snmp_community, snmp_port, enabled,
                    description, location, contact, device_type, vendor
                ) VALUES (
                    :name, :ip_address, :snmp_community, :snmp_port, :enabled,
                    :description, :location, :contact, :device_type, :vendor
                )
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, device_data)
                conn.commit()
                device_id = result.lastrowid
            
            self.logger.info(f"✅ Created device: {device_data['name']} (ID: {device_id})")
            
            return {
                'success': True,
                'device_id': device_id,
                'message': f"Device '{device_data['name']}' created successfully"
            }
        
        except Exception as e:
            self.logger.error(f"Failed to create device: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Get device by ID."""
        try:
            query = f"""
                SELECT * FROM snmp_devices WHERE id = {device_id}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            if df.empty:
                return None
            
            return df.iloc[0].to_dict()
        
        except Exception as e:
            self.logger.error(f"Failed to get device: {e}")
            return None
    
    def list_devices(
        self,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all devices."""
        try:
            where_clause = "WHERE enabled = TRUE" if enabled_only else ""
            
            query = f"""
                SELECT * FROM snmp_devices
                {where_clause}
                ORDER BY name
                LIMIT {limit} OFFSET {offset}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            return df.to_dict('records') if not df.empty else []
        
        except Exception as e:
            self.logger.error(f"Failed to list devices: {e}")
            return []
    
    def update_device(self, device_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update device."""
        try:
            from sqlalchemy import text
            
            # Build dynamic UPDATE query
            update_fields = []
            params = {'device_id': device_id}
            
            for field, value in update_data.items():
                if value is not None:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = value
            
            if not update_fields:
                return {'success': False, 'error': 'No fields to update'}
            
            query = text(f"""
                UPDATE snmp_devices
                SET {', '.join(update_fields)}
                WHERE id = :device_id
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, params)
                conn.commit()
            
            if result.rowcount > 0:
                self.logger.info(f"✅ Updated device ID: {device_id}")
                return {'success': True, 'message': 'Device updated successfully'}
            else:
                return {'success': False, 'error': 'Device not found'}
        
        except Exception as e:
            self.logger.error(f"Failed to update device: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def delete_device(self, device_id: int) -> Dict[str, Any]:
        """Delete device (cascades to walk results)."""
        try:
            from sqlalchemy import text
            
            query = text("DELETE FROM snmp_devices WHERE id = :device_id")
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, {'device_id': device_id})
                conn.commit()
            
            if result.rowcount > 0:
                self.logger.info(f"✅ Deleted device ID: {device_id}")
                return {'success': True, 'message': 'Device deleted successfully'}
            else:
                return {'success': False, 'error': 'Device not found'}
        
        except Exception as e:
            self.logger.error(f"Failed to delete device: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    # ============================================
    # WALK CONFIG MANAGEMENT
    # ============================================
    
    def create_walk_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new walk configuration."""
        try:
            from sqlalchemy import text
            
            query = text("""
                INSERT INTO snmp_walk_configs (
                    name, description, base_oid, walk_type, enabled
                ) VALUES (
                    :name, :description, :base_oid, :walk_type, :enabled
                )
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, config_data)
                conn.commit()
                config_id = result.lastrowid
            
            self.logger.info(f"✅ Created walk config: {config_data['name']} (ID: {config_id})")
            
            return {
                'success': True,
                'config_id': config_id,
                'message': f"Walk config '{config_data['name']}' created successfully"
            }
        
        except Exception as e:
            self.logger.error(f"Failed to create walk config: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def get_walk_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """Get walk config by ID."""
        try:
            query = f"""
                SELECT * FROM snmp_walk_configs WHERE id = {config_id}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            if df.empty:
                return None
            
            return df.iloc[0].to_dict()
        
        except Exception as e:
            self.logger.error(f"Failed to get walk config: {e}")
            return None
    
    def list_walk_configs(
        self,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all walk configurations."""
        try:
            where_clause = "WHERE enabled = TRUE" if enabled_only else ""
            
            query = f"""
                SELECT * FROM snmp_walk_configs
                {where_clause}
                ORDER BY name
                LIMIT {limit} OFFSET {offset}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            return df.to_dict('records') if not df.empty else []
        
        except Exception as e:
            self.logger.error(f"Failed to list walk configs: {e}")
            return []
    
    def update_walk_config(self, config_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update walk configuration."""
        try:
            from sqlalchemy import text
            
            # Build dynamic UPDATE query
            update_fields = []
            params = {'config_id': config_id}
            
            for field, value in update_data.items():
                if value is not None:
                    update_fields.append(f"{field} = :{field}")
                    params[field] = value
            
            if not update_fields:
                return {'success': False, 'error': 'No fields to update'}
            
            query = text(f"""
                UPDATE snmp_walk_configs
                SET {', '.join(update_fields)}
                WHERE id = :config_id
            """)
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, params)
                conn.commit()
            
            if result.rowcount > 0:
                self.logger.info(f"✅ Updated walk config ID: {config_id}")
                return {'success': True, 'message': 'Walk config updated successfully'}
            else:
                return {'success': False, 'error': 'Walk config not found'}
        
        except Exception as e:
            self.logger.error(f"Failed to update walk config: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def delete_walk_config(self, config_id: int) -> Dict[str, Any]:
        """Delete walk configuration."""
        try:
            from sqlalchemy import text
            
            query = text("DELETE FROM snmp_walk_configs WHERE id = :config_id")
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, {'config_id': config_id})
                conn.commit()
            
            if result.rowcount > 0:
                self.logger.info(f"✅ Deleted walk config ID: {config_id}")
                return {'success': True, 'message': 'Walk config deleted successfully'}
            else:
                return {'success': False, 'error': 'Walk config not found'}
        
        except Exception as e:
            self.logger.error(f"Failed to delete walk config: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    # ============================================
    # SNMP WALK EXECUTION
    # ============================================
    
    async def execute_walk(
        self,
        device_id: int,
        base_oid: str,
        config_id: Optional[int] = None,
        config_name: Optional[str] = None,
        walk_type: str = "custom",
        resolve_oids: bool = True,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute SNMP walk on device.
        
        Args:
            device_id: Device ID to walk
            base_oid: Base OID to walk
            config_id: Optional walk config ID
            config_name: Optional walk config name
            walk_type: Walk type label
            resolve_oids: Whether to resolve OIDs using trap_master_data
            job_id: Optional job ID for tracking
        
        Returns:
            Dict with walk results
        """
        start_time = time.time()
        
        try:
            # Get device info
            device = self.get_device(device_id)
            if not device:
                return {
                    'success': False,
                    'error': f"Device ID {device_id} not found"
                }
            
            if not device['enabled']:
                return {
                    'success': False,
                    'error': f"Device '{device['name']}' is disabled"
                }
            
            self.logger.info(
                f"🚶 Starting SNMP walk on {device['name']} ({device['ip_address']}) "
                f"for OID: {base_oid}"
            )
            
            # Perform SNMP walk
            walk_results = await self._snmp_walk(
                host=device['ip_address'],
                port=device['snmp_port'],
                community=device['snmp_community'],
                base_oid=base_oid,
                timeout=10,
                retries=2
            )
            
            if not walk_results['success']:
                if self.metrics:
                    self.metrics.counter('snmp_walk_total', {'status': 'failed'})
                return walk_results
            
            raw_results = walk_results['results']

            if self.metrics:
                self.metrics.counter_add('snmp_walk_oids_collected_total', len(raw_results))
            
            # Resolve OIDs if requested
            resolved_results = []
            if resolve_oids and raw_results:
                resolved_results = await self._resolve_walk_results(raw_results)
            else:
                resolved_results = raw_results
            
            # Store results in database
            stored_count = self._store_walk_results(
                device_id=device_id,
                device_name=device['name'],
                device_ip=device['ip_address'],
                config_id=config_id,
                config_name=config_name,
                base_oid=base_oid,
                walk_type=walk_type,
                results=resolved_results,
                job_id=job_id
            )
            
            duration = time.time() - start_time
            resolved_count = sum(1 for r in resolved_results if r.get('resolved'))

            if self.metrics:
                self.metrics.counter('snmp_walk_total', {'status': 'success'})
                self.metrics.gauge_set('snmp_walk_duration_seconds', round(duration, 2))

                if len(resolved_results) > 0:
                    resolution_pct = (resolved_count / len(resolved_results)) * 100
                    self.metrics.gauge_set('snmp_walk_resolution_percentage', round(resolution_pct, 1))
            
            self.logger.info(
                f"✅ Walk completed: {len(resolved_results)} results, "
                f"{resolved_count} resolved ({duration:.2f}s)"
            )
            
            # Broadcast via WebSocket if available
            if self.ws_manager and job_id:
                await self._broadcast_walk_progress(job_id, {
                    'status': 'completed',
                    'results_count': len(resolved_results),
                    'resolved_count': resolved_count,
                    'duration': duration
                })
            
            return {
                'success': True,
                'message': f"Walk completed successfully",
                'device_name': device['name'],
                'device_ip': device['ip_address'],
                'base_oid': base_oid,
                'results_count': len(resolved_results),
                'resolved_count': resolved_count,
                'stored_count': stored_count,
                'duration': duration,
                'job_id': job_id,
                'results': resolved_results[:100]  # Return first 100 for preview
            }
        
        except Exception as e:
            if self.metrics:
                self.metrics.counter('snmp_walk_total', {'status': 'failed'})

            self.logger.error(f"Walk execution failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    async def _snmp_walk(
        self,
        host: str,
        port: int,
        community: str,
        base_oid: str,
        timeout: int = 10,
        retries: int = 2
    ) -> Dict[str, Any]:
        """
        Perform SNMP walk using pysnmp 7.1.22 async API.
        
        Args:
            host: Target device IP/hostname
            port: SNMP port (default 161)
            community: SNMP community string
            base_oid: Base OID to walk
            timeout: Timeout in seconds
            retries: Number of retries
        
        Returns:
            Dict with success status and results
        """
        from pysnmp.hlapi.v3arch.asyncio import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            bulk_cmd,
        )
        
        try:
            results = []
            
            self.logger.info(f"Starting SNMP walk on {host}:{port} for OID {base_oid}")
            
            # Create transport
            transport = await UdpTransportTarget.create(
                (host, port),
                timeout=timeout,
                retries=retries
            )
            
            # Perform bulk walk
            error_indication, error_status, error_index, var_bind_table = await bulk_cmd(
                self.engine,
                CommunityData(community, mpModel=1),  # SNMPv2c
                transport,
                ContextData(),
                0,  # non-repeaters
                25,  # max-repetitions (fetch 25 OIDs at a time)
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            )
            
            # Check for errors
            if error_indication:
                error_msg = str(error_indication)

                if self.metrics:
                    if 'timeout' in error_msg.lower():
                        self.metrics.counter('snmp_walk_total', {'status': 'timeout'})
                    else:
                        self.metrics.counter('snmp_walk_total', {'status': 'failed'})

                self.logger.error(f"SNMP walk error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'results': []
                }
            
            if error_status:
                error_msg = f"{error_status.prettyPrint()} at {error_index}"
                self.logger.error(f"SNMP walk error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'results': []
                }
            
            # ✅ FIX: Process varbinds correctly
            # var_bind_table is a list of ObjectType objects
            for var_bind in var_bind_table:
                # Each var_bind is ObjectType with [0]=OID, [1]=value
                oid = var_bind[0]
                val = var_bind[1]
                
                oid_str = str(oid)
                value_str = str(val)
                value_type = type(val).__name__
                
                # Extract OID index (part after base OID)
                oid_index = None
                if oid_str.startswith(base_oid):
                    oid_index = oid_str[len(base_oid):].lstrip('.')
                
                results.append({
                    'oid': oid_str,
                    'oid_index': oid_index,
                    'value': value_str,
                    'value_type': value_type,
                    'resolved': False
                })
            
            self.logger.info(f"✅ SNMP walk completed: {len(results)} OIDs retrieved")
            
            return {
                'success': True,
                'results': results
            }
        
        except Exception as e:
            if self.metrics:
                self.metrics.counter('snmp_walk_total', {'status': 'failed'})

            self.logger.error(f"SNMP walk exception: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    
    async def _resolve_walk_results(self, results: List[Dict]) -> List[Dict]:
        """Resolve OIDs in walk results using trap_master_data."""
        try:
            # Collect unique OIDs
            oids_to_resolve = list(set(r['oid'] for r in results))
            
            self.logger.info(f"Resolving {len(oids_to_resolve)} unique OIDs...")
            
            # Batch resolve
            resolved = self.oid_resolver.resolve_batch(oids_to_resolve)
            
            # Add resolved names to results
            for result in results:
                oid = result['oid']
                if oid in resolved:
                    resolved_info = resolved[oid]
                    
                    result['oid_name'] = resolved_info['name']
                    result['oid_description'] = resolved_info['description']
                    result['oid_syntax'] = resolved_info['syntax']
                    result['oid_module'] = resolved_info['module']
                    result['resolved'] = True
                    
                    # ✅ Extract OID index from instance suffix
                    if 'instance' in resolved_info and resolved_info['instance']:
                        # Remove leading dot from instance (e.g., ".3" -> "3")
                        instance = resolved_info['instance'].lstrip('.')
                        result['oid_index'] = instance if instance else None
                    else:
                        # ✅ Fallback: Extract index from OID directly
                        result['oid_index'] = self._extract_oid_index(
                            oid, 
                            resolved_info.get('base_oid')
                        )
                else:
                    result['oid_name'] = None
                    result['oid_description'] = None
                    result['oid_syntax'] = None
                    result['oid_module'] = None
                    result['resolved'] = False
                    result['oid_index'] = None
            
            resolved_count = sum(1 for r in results if r['resolved'])
            self.logger.info(
                f"Resolved {resolved_count}/{len(results)} OIDs "
                f"({resolved_count/len(results)*100:.1f}%)"
            )
            
            return results
        
        except Exception as e:
            self.logger.error(f"OID resolution failed: {e}")
            return results
    
    
    def _extract_oid_index(self, full_oid: str, base_oid: Optional[str]) -> Optional[str]:
        """
        Extract index from OID.
        
        Args:
            full_oid: Full OID (e.g., "1.3.6.1.2.1.2.2.1.5.3")
            base_oid: Base OID (e.g., "1.3.6.1.2.1.2.2.1.5")
        
        Returns:
            Index string (e.g., "3") or None
        
        Examples:
            full_oid="1.3.6.1.2.1.2.2.1.5.3", base_oid="1.3.6.1.2.1.2.2.1.5"
            -> "3"
            
            full_oid="1.3.6.1.2.1.4.20.1.1.192.168.1.1", base_oid="1.3.6.1.2.1.4.20.1.1"
            -> "192.168.1.1"
        """
        if not base_oid:
            return None
        
        try:
            # Remove base OID from full OID
            if full_oid.startswith(base_oid):
                index = full_oid[len(base_oid):]
                # Remove leading dot
                index = index.lstrip('.')
                return index if index else None
            
            return None
        
        except Exception as e:
            self.logger.warning(f"Failed to extract index from {full_oid}: {e}")
            return None
    
    def _store_walk_results(
        self,
        device_id: int,
        device_name: str,
        device_ip: str,
        config_id: Optional[int],
        config_name: Optional[str],
        base_oid: str,
        walk_type: str,
        results: List[Dict],
        job_id: Optional[str]
    ) -> int:
        """Store walk results in database."""
        try:
            from sqlalchemy import text
            
            if not results:
                return 0
            
            # Prepare batch insert
            insert_query = text("""
                INSERT INTO snmp_walk_results (
                    device_id, device_name, device_ip,
                    config_id, config_name, base_oid, walk_type,
                    oid, oid_index, value, value_type,
                    oid_name, oid_description, oid_syntax, oid_module, resolved,
                    job_id
                ) VALUES (
                    :device_id, :device_name, :device_ip,
                    :config_id, :config_name, :base_oid, :walk_type,
                    :oid, :oid_index, :value, :value_type,
                    :oid_name, :oid_description, :oid_syntax, :oid_module, :resolved,
                    :job_id
                )
            """)
            
            with self.db._get_connection("traps") as conn:
                for result in results:
                    conn.execute(insert_query, {
                        'device_id': device_id,
                        'device_name': device_name,
                        'device_ip': device_ip,
                        'config_id': config_id,
                        'config_name': config_name,
                        'base_oid': base_oid,
                        'walk_type': walk_type,
                        'oid': result['oid'],
                        'oid_index': result.get('oid_index'),
                        'value': result['value'],
                        'value_type': result['value_type'],
                        'oid_name': result.get('oid_name'),
                        'oid_description': result.get('oid_description'),
                        'oid_syntax': result.get('oid_syntax'),
                        'oid_module': result.get('oid_module'),
                        'resolved': result.get('resolved', False),
                        'job_id': job_id
                    })
                conn.commit()
            
            self.logger.info(f"✅ Stored {len(results)} walk results")
            return len(results)
        
        except Exception as e:
            self.logger.error(f"Failed to store walk results: {e}", exc_info=True)
            return 0
    
    async def _broadcast_walk_progress(self, job_id: str, data: Dict):
        """Broadcast walk progress via WebSocket."""
        try:
            if self.ws_manager:
                import json
                message = {
                    'type': 'walk_progress',
                    'job_id': job_id,
                    'data': data
                }
                await self.ws_manager.broadcast(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Failed to broadcast progress: {e}")
    
    # ============================================
    # QUERY WALK RESULTS
    # ============================================
    
    def query_walk_results(
        self,
        device_id: Optional[int] = None,
        device_name: Optional[str] = None,
        config_id: Optional[int] = None,
        base_oid: Optional[str] = None,
        walk_type: Optional[str] = None,
        oid_filter: Optional[str] = None,
        resolved_only: bool = False,
        limit: int = 1000,
        offset: int = 0,
        sort_by: str = "collected_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Query walk results with filters."""
        try:
            # Build WHERE clause
            where_clauses = []
            
            if device_id:
                where_clauses.append(f"device_id = {device_id}")
            if device_name:
                where_clauses.append(f"device_name LIKE '%{device_name}%'")
            if config_id:
                where_clauses.append(f"config_id = {config_id}")
            if base_oid:
                where_clauses.append(f"base_oid = '{base_oid}'")
            if walk_type:
                where_clauses.append(f"walk_type = '{walk_type}'")
            if oid_filter:
                where_clauses.append(f"(oid LIKE '%{oid_filter}%' OR oid_name LIKE '%{oid_filter}%')")
            if resolved_only:
                where_clauses.append("resolved = TRUE")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Count total
            count_query = f"""
                SELECT COUNT(*) as total
                FROM snmp_walk_results
                WHERE {where_sql}
            """
            
            count_df = self.db.db_to_df(
                table=None,
                database="traps",
                query=count_query
            )
            
            total = int(count_df.iloc[0]['total']) if not count_df.empty else 0
            
            # Get results
            query = f"""
                SELECT *
                FROM snmp_walk_results
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order.upper()}
                LIMIT {limit} OFFSET {offset}
            """
            
            df = self.db.db_to_df(
                table=None,
                database="traps",
                query=query
            )
            
            results = df.to_dict('records') if not df.empty else []
            
            return {
                'success': True,
                'total': total,
                'limit': limit,
                'offset': offset,
                'results': results
            }
        
        except Exception as e:
            self.logger.error(f"Failed to query walk results: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total': 0,
                'results': []
            }

    def get_walk_statistics(self) -> Dict[str, Any]:
        """Get walk statistics."""
        try:
            stats = {}
            
            # Device stats
            device_query = """
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN enabled = TRUE THEN 1 ELSE 0 END), 0) as enabled
                FROM snmp_devices
            """
            device_df = self.db.db_to_df(table=None, database="traps", query=device_query)
            if not device_df.empty and device_df.iloc[0]['total'] is not None:
                stats['total_devices'] = int(device_df.iloc[0]['total'])
                stats['enabled_devices'] = int(device_df.iloc[0]['enabled'])
            else:
                stats['total_devices'] = 0
                stats['enabled_devices'] = 0
            
            # Config stats
            config_query = """
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN enabled = TRUE THEN 1 ELSE 0 END), 0) as enabled
                FROM snmp_walk_configs
            """
            config_df = self.db.db_to_df(table=None, database="traps", query=config_query)
            if not config_df.empty and config_df.iloc[0]['total'] is not None:
                stats['total_configs'] = int(config_df.iloc[0]['total'])
                stats['enabled_configs'] = int(config_df.iloc[0]['enabled'])
            else:
                stats['total_configs'] = 0
                stats['enabled_configs'] = 0
            
            # Results stats
            results_query = """
                SELECT 
                    COUNT(*) as total,
                    COALESCE(SUM(CASE WHEN resolved = TRUE THEN 1 ELSE 0 END), 0) as resolved,
                    MAX(collected_at) as last_walk
                FROM snmp_walk_results
            """
            results_df = self.db.db_to_df(table=None, database="traps", query=results_query)
            if not results_df.empty and results_df.iloc[0]['total'] is not None:
                row = results_df.iloc[0]
                total = int(row['total'])
                resolved = int(row['resolved'])
                stats['total_results'] = total
                stats['resolved_results'] = resolved
                stats['resolution_percentage'] = (resolved / total * 100) if total > 0 else 0.0
                stats['last_walk_time'] = row['last_walk'] if row['last_walk'] is not None else None
            else:
                stats['total_results'] = 0
                stats['resolved_results'] = 0
                stats['resolution_percentage'] = 0.0
                stats['last_walk_time'] = None
            
            return {
                'success': True,
                'stats': stats
            }
        
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    
    def clear_walk_results(
        self,
        device_id: Optional[int] = None,
        older_than_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Clear walk results with optional filters."""
        try:
            from sqlalchemy import text
            
            where_clauses = []
            params = {}
            
            if device_id:
                where_clauses.append("device_id = :device_id")
                params['device_id'] = device_id
            
            if older_than_days:
                where_clauses.append("collected_at < DATE_SUB(NOW(), INTERVAL :days DAY)")
                params['days'] = older_than_days
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            query = text(f"DELETE FROM snmp_walk_results WHERE {where_sql}")
            
            with self.db._get_connection("traps") as conn:
                result = conn.execute(query, params)
                conn.commit()
                deleted_count = result.rowcount
            
            self.logger.info(f"✅ Cleared {deleted_count} walk results")
            
            return {
                'success': True,
                'deleted_count': deleted_count
            }
        
        except Exception as e:
            self.logger.error(f"Failed to clear walk results: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
