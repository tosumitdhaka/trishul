#!/usr/bin/env python3
"""
OID Resolver Service

Resolves OIDs to names/descriptions using trap_master_data.
Includes in-memory cache for performance.
"""

import time
from collections import OrderedDict
from typing import Dict, List, Optional

from utils.logger import get_logger
from backend.services.metrics_service import get_metrics_service

logger = get_logger(__name__)


class OIDCache:
    """
    LRU cache for OID resolution.
    
    Features:
    - Fast O(1) lookup
    - LRU eviction policy
    - Configurable size
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum cache entries (default 10,000)
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def get(self, oid: str) -> Optional[Dict]:
        """Get from cache (LRU)."""
        metrics = get_metrics_service()

        if oid in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(oid)
            self.hits += 1

            if metrics:
                metrics.counter('app_oid_cache_operations_total', {'operation': 'hit'})

            return self.cache[oid]
        
        self.misses += 1

        if metrics:
            metrics.counter('app_oid_cache_operations_total', {'operation': 'miss'})

        return None
    
    def put(self, oid: str, data: Dict):
        """Put in cache (LRU eviction)."""
        metrics = get_metrics_service()

        if oid in self.cache:
            # Update existing
            self.cache.move_to_end(oid)
        else:
            # Add new
            if len(self.cache) >= self.max_size:
                # Evict least recently used
                self.cache.popitem(last=False)
        
        self.cache[oid] = data

        if metrics:
            metrics.gauge_set('app_oid_cache_size', len(self.cache))
            
    
    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%"
        }


class OIDResolverService:
    """
    Resolve OIDs using trap_master_data.
    
    Features:
    - Single OID resolution
    - Batch OID resolution
    - Object search by name/description
    - In-memory LRU cache
    
    Example:
        resolver = OIDResolverService(db_manager)
        
        # Resolve single OID
        result = resolver.resolve_oid('1.3.6.1.2.1.1.3.0')
        # Returns: {'oid': '...', 'name': 'sysUpTime', 'description': '...'}
        
        # Batch resolve
        results = resolver.resolve_batch(['1.3.6.1.2.1.1.3.0', '1.3.6.1.2.1.2.2.1.1'])
        
        # Search objects
        objects = resolver.search_objects('memory', limit=50)
    """
    
    def __init__(self, db_manager, cache_size: int = 10000):
        """
        Initialize OID resolver.
        
        Args:
            db_manager: DatabaseManager instance
            cache_size: Maximum cache entries (default 10,000)
        """
        self.db = db_manager
        self.cache = OIDCache(max_size=cache_size)
        self.logger = get_logger(self.__class__.__name__)
        
        self.logger.info(f"✅ OIDResolverService initialized (cache_size={cache_size})")
    
    def resolve_oid(self, oid: str) -> Optional[Dict]:
        """
        Resolve single OID to name and description.
        
        Public API for single OID resolution.
        Checks cache → exact match → prefix match.
        
        Args:
            oid: OID string (e.g., "1.3.6.1.2.1.1.3.0")
        
        Returns:
            Resolved OID info or None
        """

        metrics = get_metrics_service()
        
        # Check cache first
        cached = self.cache.get(oid)
        if cached:
            self.logger.debug(f"Cache hit for OID: {oid}")
            
            # ✅ Track resolution from cache
            if metrics:
                metrics.counter('app_oid_resolutions_total', {'status': 'success', 'source': 'cache'})
            
            return cached
        
        # Try exact match
        result = self._resolve_exact(oid)
        if result:
            self.cache.put(oid, result)
            
            # ✅ Track resolution from database
            if metrics:
                metrics.counter('app_oid_resolutions_total', {'status': 'success', 'source': 'database'})
            
            return result
        
        # Try prefix match
        result = self._resolve_prefix(oid)
        if result:
            self.cache.put(oid, result)
            
            # ✅ Track resolution from database
            if metrics:
                metrics.counter('app_oid_resolutions_total', {'status': 'success', 'source': 'database'})
            
            return result
        
        # ✅ Track failed resolution
        if metrics:
            metrics.counter('app_oid_resolutions_total', {'status': 'failed', 'source': 'database'})
        
        self.logger.debug(f"OID not found: {oid}")
        return None
    
    def _resolve_exact(self, oid: str) -> Optional[Dict]:
        """
        Resolve OID with exact match.
        
        Internal method - no metrics tracking (tracked by caller).
        """
        query = f"""
            SELECT 
                object_oid, object_name, object_description,
                object_node_type, object_syntax, module_name, source_table
            FROM trap_master_data
            WHERE object_oid = '{oid}'
            LIMIT 1
        """
        
        df = self.db.db_to_df(table=None, database='data', query=query)
        
        if not df.empty:
            row = df.iloc[0]
            return {
                'oid': oid,
                'name': row['object_name'],
                'description': row['object_description'],
                'type': row['object_node_type'],
                'syntax': row['object_syntax'],
                'module': row['module_name'],
                'source_table': row['source_table']
            }
        
        return None
    
    def _resolve_prefix(self, oid: str) -> Optional[Dict]:
        """
        Resolve OID with prefix match (for instances).
        
        Internal method - no metrics tracking (tracked by caller).
        
        Example:
            Input: "1.3.6.1.2.1.2.2.1.5.3"
            Finds: "1.3.6.1.2.1.2.2.1.5" (ifInOctets)
            Returns: "ifInOctets.3"
        """
        query = f"""
            SELECT 
                object_oid, object_name, object_description,
                object_node_type, object_syntax, module_name, source_table,
                LENGTH(object_oid) as oid_length
            FROM trap_master_data
            WHERE '{oid}' LIKE CONCAT(object_oid, '%')
            ORDER BY oid_length DESC
            LIMIT 1
        """
        
        df = self.db.db_to_df(table=None, database='data', query=query)
        
        if not df.empty:
            row = df.iloc[0]
            base_oid = row['object_oid']
            instance = oid[len(base_oid):] if len(oid) > len(base_oid) else ''
            
            result = {
                'oid': oid,
                'name': f"{row['object_name']}{instance}" if instance else row['object_name'],
                'description': row['object_description'],
                'type': row['object_node_type'],
                'syntax': row['object_syntax'],
                'module': row['module_name'],
                'source_table': row['source_table'],
                'base_oid': base_oid,
                'instance': instance if instance else None
            }
            
            self.logger.debug(f"Prefix match for OID: {oid} -> {base_oid}{instance}")
            return result
        
        return None
    
    def resolve_batch(self, oids: List[str]) -> Dict[str, Dict]:
        """
        Resolve multiple OIDs at once (optimized).
        
        Optimized flow:
        1. Check cache for all OIDs (single pass)
        2. Query DB for exact matches (single query)
        3. Query DB for prefix matches (only for remaining OIDs)
        
        Args:
            oids: List of OID strings
        
        Returns:
            Dict mapping OID -> resolved data
        """
        # ✅ Track batch operation duration
        batch_start = time.time()
        metrics = get_metrics_service()
        
        results = {}
        uncached_oids = []
        
        # ✅ STEP 1: Check cache for all OIDs
        for oid in oids:
            cached = self.cache.get(oid)
            if cached:
                results[oid] = cached
            else:
                uncached_oids.append(oid)
        
        if not uncached_oids:
            self.logger.debug(f"All {len(oids)} OIDs found in cache")
            
            # ✅ Track batch duration
            batch_duration = time.time() - batch_start
            if metrics:
                metrics.gauge_set('app_oid_resolution_batch_duration_seconds', round(batch_duration, 4))
                metrics.counter_add('app_oid_resolution_duration_total_seconds', round(batch_duration, 4))
            
            return results
        
        self.logger.debug(f"Querying {len(uncached_oids)} uncached OIDs")
        
        # ✅ STEP 2: Exact match for all uncached OIDs (single query)
        exact_matched_oids = self._resolve_batch_exact(uncached_oids, results)
        
        # ✅ STEP 3: Prefix match for remaining OIDs
        remaining_oids = [oid for oid in uncached_oids if oid not in exact_matched_oids]
        
        if remaining_oids:
            self.logger.debug(f"Trying prefix match for {len(remaining_oids)} OIDs")
            self._resolve_batch_prefix(remaining_oids, results)
        
        self.logger.debug(f"Resolved {len(results)}/{len(oids)} OIDs")
        
        # ✅ Track batch duration
        batch_duration = time.time() - batch_start
        if metrics:
            metrics.gauge_set('app_oid_resolution_batch_duration_seconds', round(batch_duration, 4))
            metrics.counter_add('app_oid_resolution_duration_total_seconds', round(batch_duration, 4))
        
        return results
    
    def _resolve_batch_exact(self, oids: List[str], results: Dict[str, Dict]) -> set:
        """
        Resolve multiple OIDs with exact match (single query).
        
        Args:
            oids: List of OIDs to resolve
            results: Dict to populate with results
        
        Returns:
            Set of OIDs that were successfully resolved
        """
        metrics = get_metrics_service()
        
        oid_list = "', '".join(oids)
        query = f"""
            SELECT 
                object_oid, object_name, object_description,
                object_node_type, object_syntax, module_name, source_table
            FROM trap_master_data
            WHERE object_oid IN ('{oid_list}')
        """
        
        df = self.db.db_to_df(table=None, database='data', query=query)
        
        exact_matched = set()
        
        for _, row in df.iterrows():
            oid = row['object_oid']
            result = {
                'oid': oid,
                'name': row['object_name'],
                'description': row['object_description'],
                'type': row['object_node_type'],
                'syntax': row['object_syntax'],
                'module': row['module_name'],
                'source_table': row['source_table']
            }
            results[oid] = result
            self.cache.put(oid, result)
            exact_matched.add(oid)
            
            # ✅ Track resolution from database
            if metrics:
                metrics.counter('app_oid_resolutions_total', {'status': 'success', 'source': 'database'})
        
        return exact_matched
    
    def _resolve_batch_prefix(self, oids: List[str], results: Dict[str, Dict]):
        """
        Resolve multiple OIDs with prefix match.
        
        Args:
            oids: List of OIDs to resolve
            results: Dict to populate with results
        """
        metrics = get_metrics_service()
        
        # ✅ Resolve each OID individually with prefix matching
        for oid in oids:
            result = self._resolve_prefix(oid)
            if result:
                results[oid] = result
                self.cache.put(oid, result)
                
                # ✅ Track resolution from database
                if metrics:
                    metrics.counter('app_oid_resolutions_total', {'status': 'success', 'source': 'database'})
            else:
                # ✅ Track failed resolution
                if metrics:
                    metrics.counter('app_oid_resolutions_total', {'status': 'failed', 'source': 'database'})
    
    def search_objects(
        self,
        search: str,
        limit: int = 50,
        object_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search objects by name or description.
        
        Args:
            search: Search term
            limit: Maximum results (default 50)
            object_types: Filter by object types (e.g., ['ObjectType', 'MibScalar'])
        
        Returns:
            List of matching objects
            [
                {
                    'oid': '1.3.6.1.2.1.25.2.3.1.5',
                    'name': 'hrStorageUsed',
                    'description': 'The amount of storage...',
                    'type': 'MibTableColumn',
                    'syntax': 'Integer32',
                    'module': 'HOST-RESOURCES-MIB'
                },
                ...
            ]
        """
        # Build WHERE clause
        where_clauses = [
            f"(object_name LIKE '%{search}%' OR object_description LIKE '%{search}%')"
        ]
        
        if object_types:
            types_str = "', '".join(object_types)
            where_clauses.append(f"object_node_type IN ('{types_str}')")
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                object_oid,
                object_name,
                object_description,
                object_node_type,
                object_syntax,
                module_name,
                source_table
            FROM trap_master_data
            WHERE {where_sql}
            AND object_oid IS NOT NULL
            AND object_oid != ''
            ORDER BY object_name
            LIMIT {limit}
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
                'oid': row['object_oid'],
                'name': row['object_name'],
                'description': row['object_description'],
                'type': row['object_node_type'],
                'syntax': row['object_syntax'],
                'module': row['module_name'],
                'source_table': row['source_table']
            })
        
        return results
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def clear_cache(self):
        """Clear cache."""
        self.cache.clear()
        self.logger.info("Cache cleared")
