#!/usr/bin/env python3
"""
Trap Builder Service

Builds SNMP traps from parsed MIB data.
Fetches notification details and related objects.
"""

import json
from typing import Dict, List, Optional

from backend.services.oid_resolver_service import OIDResolverService
from utils.logger import get_logger

logger = get_logger(__name__)


class TrapBuilderService:
    """
    Build SNMP traps using trap_master_data.
    
    Features:
    - Get notification details
    - Get notification objects (varbinds)
    - Search for additional varbinds
    - Build complete trap structure
    
    Example:
        builder = TrapBuilderService(db_manager)
        
        # Get notification
        notif = builder.get_notification('linkDown')
        
        # Get notification objects
        objects = builder.get_notification_objects('linkDown')
        
        # Build trap structure
        trap = builder.build_trap_structure('linkDown')
    """
    
    def __init__(self, db_manager):
        """
        Initialize trap builder.
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db = db_manager
        self.oid_resolver = OIDResolverService(db_manager)
        self.logger = get_logger(self.__class__.__name__)
        
        self.logger.info("✅ TrapBuilderService initialized")
    
    def get_notification(self, notification_name: str) -> Optional[Dict]:
        """
        Get notification details.
        
        Args:
            notification_name: Notification name (e.g., 'linkDown')
        
        Returns:
            {
                'name': 'linkDown',
                'oid': '1.3.6.1.6.3.1.1.5.3',
                'description': 'A linkDown trap signifies...',
                'module': 'IF-MIB',
                'status': 'current',
                'objects_count': 3
            }
        """
        query = f"""
            SELECT 
                notification_name,
                notification_oid,
                notification_description,
                notification_status,
                module_name,
                COUNT(*) as objects_count
            FROM trap_master_data
            WHERE notification_name = '{notification_name}'
            AND notification_name IS NOT NULL
            AND notification_name != ''
            GROUP BY notification_name, notification_oid, notification_description,
                     notification_status, module_name
            LIMIT 1
        """
        
        df = self.db.db_to_df(
            table=None,
            database='data',
            query=query
        )
        
        if df.empty:
            self.logger.warning(f"Notification not found: {notification_name}")
            return None
        
        row = df.iloc[0]
        
        return {
            'name': row['notification_name'],
            'oid': row['notification_oid'],
            'description': row['notification_description'],
            'module': row['module_name'],
            'status': row['notification_status'],
            'objects_count': int(row['objects_count'])
        }
    
    def get_notification_objects(
        self,
        notification_name: str
    ) -> List[Dict]:
        """
        Get objects (varbinds) for a notification.
        
        Args:
            notification_name: Notification name
        
        Returns:
            List of objects with details
            [
                {
                    'sequence': 1,
                    'name': 'ifIndex',
                    'oid': '1.3.6.1.2.1.2.2.1.1',
                    'description': 'A unique value...',
                    'syntax': 'InterfaceIndex',
                    'type': 'MibTableColumn',
                    'value': '',  # User will fill this
                    'required': True
                },
                ...
            ]
        """
        query = f"""
            SELECT 
                object_sequence,
                object_name,
                object_oid,
                object_description,
                object_syntax,
                object_node_type,
                tc_enumerations
            FROM trap_master_data
            WHERE notification_name = '{notification_name}'
            AND object_name IS NOT NULL
            AND object_name != ''
            ORDER BY object_sequence
        """
        
        df = self.db.db_to_df(
            table=None,
            database='data',
            query=query
        )
        
        if df.empty:
            self.logger.warning(f"No objects found for notification: {notification_name}")
            return []
        
        results = []
        for _, row in df.iterrows():
            # Parse enumerations if available
            enumerations = None
            if row['tc_enumerations']:
                try:
                    enumerations = json.loads(row['tc_enumerations'])
                except:
                    pass
            
            results.append({
                'sequence': int(row['object_sequence']) if row['object_sequence'] else 0,
                'name': row['object_name'],
                'oid': row['object_oid'],
                'description': row['object_description'],
                'syntax': row['object_syntax'],
                'type': row['object_node_type'],
                'enumerations': enumerations,
                'value': '',  # User will fill this
                'required': True  # From notification
            })
        
        return results
    
    def search_varbinds(
        self,
        search: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search for additional varbinds to add.
        
        Args:
            search: Search term
            limit: Maximum results
        
        Returns:
            List of matching objects
        """
        return self.oid_resolver.search_objects(search, limit)
    
    def build_trap_structure(
        self,
        notification_name: str,
        custom_varbinds: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Build complete trap structure.
        
        Args:
            notification_name: Notification name
            custom_varbinds: Additional varbinds to include
        
        Returns:
            Complete trap structure ready to send
            {
                'trap_oid': '1.3.6.1.6.3.1.1.5.3',
                'trap_name': 'linkDown',
                'description': '...',
                'module': 'IF-MIB',
                'varbinds': [
                    {'oid': '...', 'name': 'ifIndex', 'value': '', ...},
                    {'oid': '...', 'name': 'ifAdminStatus', 'value': '', ...},
                    ...
                ]
            }
        """
        # Get notification
        notification = self.get_notification(notification_name)
        
        if not notification:
            raise ValueError(f"Notification '{notification_name}' not found")
        
        # Get required objects
        required_objects = self.get_notification_objects(notification_name)
        
        # Combine with custom varbinds
        all_varbinds = required_objects.copy()
        
        if custom_varbinds:
            all_varbinds.extend(custom_varbinds)
        
        return {
            'trap_oid': notification['oid'],
            'trap_name': notification['name'],
            'description': notification['description'],
            'module': notification['module'],
            'status': notification['status'],
            'varbinds': all_varbinds
        }
    
    def list_notifications(
        self,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        List available notifications.
        
        Args:
            search: Search term (optional)
            limit: Maximum results
            offset: Offset for pagination
        
        Returns:
            List of notifications
        """
        where_clause = ""
        if search:
            where_clause = f"AND (notification_name LIKE '%{search}%' OR notification_description LIKE '%{search}%')"
        
        query = f"""
            SELECT 
                notification_name,
                notification_oid,
                notification_description,
                notification_status,
                module_name,
                COUNT(*) as objects_count
            FROM trap_master_data
            WHERE notification_name IS NOT NULL
            AND notification_name != ''
            {where_clause}
            GROUP BY notification_name, notification_oid, notification_description,
                     notification_status, module_name
            ORDER BY notification_name
            LIMIT {limit} OFFSET {offset}
        """
        
        df = self.db.db_to_df(
            table=None,
            database='data',
            query=query
        )
        
        if df.empty:
            return []
        
        results = []
        for _, row in df.iterrows():
            results.append({
                'name': row['notification_name'],
                'oid': row['notification_oid'],
                'description': row['notification_description'],
                'module': row['module_name'],
                'status': row['notification_status'],
                'objects_count': int(row['objects_count'])
            })
        
        return results
