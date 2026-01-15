#!/usr/bin/env python3
"""
Trap Sync Service - Optimized Version

Syncs user MIB tables to consolidated trap_master_data table.
Uses bulk SQL operations with WebSocket progress updates.

Features:
- Bulk INSERT ... ON DUPLICATE KEY UPDATE
- Batch processing (10K rows per batch)
- Memory efficient (no full table loads)
- WebSocket progress updates
- Multiple sync strategies
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from utils.logger import get_logger

from backend.services.metrics_service import get_metrics_service

logger = get_logger(__name__)


class TrapSyncService:
    """
    Optimized sync service using bulk SQL operations.
    
    Strategies:
    - 'append': Insert new only, skip duplicates (default)
    - 'newest': Insert new, update if source is newer
    - 'replace': Insert new, always overwrite duplicates
    - 'skip': Insert new only (alias for append)
    
    Example:
        sync_service = TrapSyncService(db_manager, config, ws_manager)
        result = await sync_service.sync_table('cisco_mibs', strategy='newest')
    """
    
    # Batch size for processing
    BATCH_SIZE = 10000
    
    # Lock to prevent concurrent syncs
    _sync_lock = asyncio.Lock()
    
    def __init__(self, db_manager, config, ws_manager=None):
        """
        Initialize sync service.
        
        Args:
            db_manager: DatabaseManager instance
            config: Application config
            ws_manager: WebSocket ConnectionManager (optional)
        """
        self.db = db_manager
        self.config = config
        self.ws_manager = ws_manager
        self.logger = get_logger(self.__class__.__name__)
    
    async def sync_table(
        self,
        table_name: str,
        strategy: Optional[str] = None,
        force_full: bool = False  # Kept for API compatibility, not used
    ) -> Dict[str, Any]:
        """
        Sync user table to trap_master_data.
        
        Args:
            table_name: User table name to sync
            strategy: Dedup strategy (append, newest, replace, skip)
            force_full: Ignored (kept for backward compatibility)
        
        Returns:
            Sync result with statistics
        """
        async with self._sync_lock:
            return await self._sync_table_internal(table_name, strategy)
    
    async def _sync_table_internal(
        self,
        table_name: str,
        strategy: Optional[str]
    ) -> Dict[str, Any]:
        """Internal sync method (called with lock held)."""

        start_time = time.time()
        metrics = get_metrics_service()
        
        try:
            # Validate strategy
            valid_strategies = ['append', 'newest', 'replace', 'skip']
            if strategy is None:
                strategy = 'append'
            elif strategy not in valid_strategies:
                self.logger.warning(f"Unknown strategy '{strategy}', using 'append'")
                strategy = 'append'
            
            self.logger.info(f"🔄 Starting optimized sync for table: {table_name} (strategy: {strategy})")
            
            # Send WebSocket update: started
            await self._send_progress(table_name, 'started', 0, f"Starting sync for {table_name}")
            
            # Validate table exists
            if not self.db.table_exists(table_name, database='data'):
                raise ValueError(f"Table '{table_name}' does not exist")
            
            # Ensure master table has proper schema
            await self._ensure_master_table_schema()
            
            # Update sync status to 'syncing'
            self._update_sync_status(table_name, 'syncing')
            
            # Get total row count
            total_rows = self._get_table_row_count(table_name)
            self.logger.info(f"📊 Total rows to sync: {total_rows}")
            
            if total_rows == 0:
                self.logger.warning(f"Table {table_name} is empty, nothing to sync")
                self._update_sync_status(table_name, 'completed', rows_synced=0)
                await self._send_progress(table_name, 'completed', 100, "Table is empty")
                return {
                    'success': True,
                    'table_name': table_name,
                    'rows_processed': 0,
                    'rows_inserted': 0,
                    'rows_updated': 0,
                    'rows_skipped': 0,
                    'duration': time.time() - start_time
                }
            
            # Process in batches
            offset = 0
            stats = {
                'rows_processed': 0,
                'rows_inserted': 0,
                'rows_updated': 0,
                'rows_skipped': 0
            }
            
            while offset < total_rows:
                # Read batch from source
                batch_df = await self._read_batch(table_name, offset, self.BATCH_SIZE)
                
                if batch_df.empty:
                    break
                
                # Add metadata columns
                batch_df['source_table'] = table_name
                batch_df['synced_at'] = datetime.now()
                
                # Sync batch using bulk upsert
                batch_stats = await self._sync_batch_bulk(batch_df, strategy)
                
                # Update stats
                stats['rows_processed'] += len(batch_df)
                stats['rows_inserted'] += batch_stats['inserted']
                stats['rows_updated'] += batch_stats['updated']
                stats['rows_skipped'] += batch_stats['skipped']
                
                offset += self.BATCH_SIZE
                
                # Calculate progress
                progress = min(100, int((offset / total_rows) * 100))
                
                # Send WebSocket update: progress
                await self._send_progress(
                    table_name,
                    'syncing',
                    progress,
                    f"Processed {stats['rows_processed']}/{total_rows} rows"
                )
                
                self.logger.info(
                    f"Progress: {progress}% ({stats['rows_processed']}/{total_rows}) - "
                    f"Inserted: {stats['rows_inserted']}, Updated: {stats['rows_updated']}, Skipped: {stats['rows_skipped']}"
                )
            
            duration = time.time() - start_time

            if metrics:
                metrics.counter('app_db_sync_operations_total', {'table': table_name, 'status': 'success'})
                metrics.counter_add('app_db_sync_rows_total', stats['rows_inserted'], {'table': table_name, 'operation': 'inserted'})
                metrics.counter_add('app_db_sync_rows_total', stats['rows_updated'], {'table': table_name, 'operation': 'updated'})
                metrics.counter_add('app_db_sync_rows_total', stats['rows_skipped'], {'table': table_name, 'operation': 'skipped'})
                metrics.gauge_set('app_db_sync_duration_seconds', round(duration, 2), {'table': table_name})
                metrics.counter_add('app_db_sync_duration_total_seconds', round(duration, 2))
            
            # Update sync status to 'completed'
            self._update_sync_status(
                table_name,
                'completed',
                rows_synced=stats['rows_inserted'] + stats['rows_updated'],
                rows_inserted=stats['rows_inserted'],
                rows_updated=stats['rows_updated'],
                rows_skipped=stats['rows_skipped'],
                sync_method='bulk_sql',
                dedup_strategy=strategy
            )
            
            # Send WebSocket update: completed
            await self._send_progress(
                table_name,
                'completed',
                100,
                f"✅ Sync of {table_name} completed ({duration:.2f}s): {stats['rows_inserted']} inserted, {stats['rows_updated']} updated, {stats['rows_skipped']} skipped"
            )
            
            self.logger.info(
                f"✅ Sync completed for {table_name} in {duration:.2f}s: "
                f"{stats['rows_inserted']} inserted, "
                f"{stats['rows_updated']} updated, "
                f"{stats['rows_skipped']} skipped"
            )
            
            return {
                'success': True,
                'table_name': table_name,
                'sync_method': 'bulk_sql',
                'dedup_strategy': strategy,
                'duration': duration,
                'stats': stats
            }
        
        except Exception as e:
            if metrics:
                metrics.counter('app_db_sync_operations_total', {'table': table_name, 'status': 'failed'})

            self.logger.error(f"❌ Sync failed for {table_name}: {e}", exc_info=True)
            
            # Update sync status to 'failed'
            self._update_sync_status(
                table_name,
                'failed',
                error_message=str(e)
            )
            
            # Send WebSocket update: failed
            await self._send_progress(table_name, 'failed', 0, f"Sync failed: {str(e)}")
            
            return {
                'success': False,
                'table_name': table_name,
                'error': str(e)
            }
    
    async def _sync_batch_bulk(
        self,
        batch_df: pd.DataFrame,
        strategy: str
    ) -> Dict[str, int]:
        """
        Sync batch using bulk INSERT.
        
        Uses unique key: (notification_name, object_name, module_name)
        """
        if batch_df.empty:
            return {'inserted': 0, 'updated': 0, 'skipped': 0}
        
        # Ensure notification_name and object_name are not NULL
        batch_df['notification_name'] = batch_df['notification_name'].fillna('')
        batch_df['object_name'] = batch_df['object_name'].fillna('')
        
        # Ensure node_type exists
        if 'node_type' not in batch_df.columns:
            self.logger.warning("node_type column not found in source data, will be NULL")
            batch_df['node_type'] = None
        
        # Build column list (exclude 'id' if exists)
        columns = [col for col in batch_df.columns if col != 'id']
        
        # Build INSERT query
        placeholders = ', '.join([f':{col}' for col in columns])
        columns_str = ', '.join([f'`{col}`' for col in columns])
        
        # Use INSERT IGNORE for append/skip strategies
        if strategy in ['append', 'skip']:
            query = text(f"""
                INSERT IGNORE INTO trap_master_data ({columns_str})
                VALUES ({placeholders})
            """)
        else:
            # Build ON DUPLICATE KEY UPDATE clause for other strategies
            update_clause = self._build_update_clause(strategy, columns)
            
            query = text(f"""
                INSERT INTO trap_master_data ({columns_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """)
        
        # Execute batch insert with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                with self.db._get_connection('data') as conn:
                    # Convert DataFrame to list of dicts
                    records = batch_df.to_dict('records')
                    
                    # Execute batch
                    result = conn.execute(query, records)
                    conn.commit()
                    
                    # Calculate stats from result
                    rows_affected = result.rowcount
                    
                    # Calculate stats
                    if strategy in ['append', 'skip']:
                        # INSERT IGNORE: rows_affected = number of rows inserted
                        inserted = rows_affected
                        updated = 0
                        skipped = len(records) - inserted
                    else:
                        # ON DUPLICATE KEY UPDATE: rows_affected = inserted + (2 * updated)
                        if rows_affected >= len(records):
                            # Some rows were updated
                            updated = rows_affected - len(records)
                            inserted = len(records) - updated
                            skipped = 0
                        else:
                            # All rows were inserted
                            inserted = rows_affected
                            updated = 0
                            skipped = len(records) - inserted
                    
                    return {
                        'inserted': max(0, inserted),
                        'updated': max(0, updated),
                        'skipped': max(0, skipped)
                    }
            
            except Exception as e:
                if "Deadlock" in str(e) and attempt < max_retries - 1:
                    self.logger.warning(f"Deadlock detected on attempt {attempt + 1}, retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    raise
        
        raise Exception("Failed to sync batch after all retries")
        
        
    def _build_update_clause(self, strategy: str, columns: List[str]) -> str:
        """
        Build ON DUPLICATE KEY UPDATE clause based on strategy.
        
        Only used for 'newest' and 'replace' strategies.
        """
        if strategy == 'newest':
            # Update only if source is newer (based on imported_at)
            update_parts = []
            for col in columns:
                if col not in ['id', 'source_table', 'synced_at']:
                    update_parts.append(
                        f"`{col}` = IF(VALUES(imported_at) > imported_at, VALUES(`{col}`), `{col}`)"
                    )
            # Always update these
            update_parts.append("`source_table` = VALUES(`source_table`)")
            update_parts.append("`synced_at` = VALUES(`synced_at`)")
            return ', '.join(update_parts)
        
        elif strategy == 'replace':
            # Always update with new values (exclude id)
            update_parts = [f"`{col}` = VALUES(`{col}`)" for col in columns if col != 'id']
            return ', '.join(update_parts)
    
    async def _ensure_master_table_schema(self):
        """Ensure master table exists with proper indexes."""
        
        # Check if table exists
        if not self.db.table_exists('trap_master_data', database='data'):
            self.logger.info("Master table doesn't exist yet, will be created on first insert")
            return
        
        # Check if composite index exists
        check_index_query = """
            SELECT COUNT(*) as count
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'trap_master_data'
            AND INDEX_NAME = 'idx_composite_key'
        """
        
        result = self.db.db_to_df(
            table=None,
            database='data',
            query=check_index_query
        )
        
        if result.empty or result.iloc[0]['count'] == 0:
            self.logger.info("Adding composite unique index to master table...")
            
            try:
                create_index_query = """
                    ALTER TABLE trap_master_data
                    ADD UNIQUE INDEX idx_composite_key (
                        notification_oid(255),
                        object_oid(255),
                        module_name(255)
                    )
                """
                
                with self.db._get_connection('data') as conn:
                    conn.execute(text(create_index_query))
                    conn.commit()
                
                self.logger.info("✅ Composite unique index created")
            except Exception as e:
                if "Duplicate key name" in str(e):
                    self.logger.info("Index already exists (race condition)")
                else:
                    raise
        
        # Check for other indexes
        self._ensure_additional_indexes()
    
    def _ensure_additional_indexes(self):
        """Ensure additional performance indexes exist."""
        
        indexes = [
            ('idx_source_table', 'source_table(255)'),
            ('idx_imported_at', 'imported_at'),
            ('idx_notification_oid', 'notification_oid(255)'),
            ('idx_object_oid', 'object_oid(255)')
        ]
        
        for index_name, index_column in indexes:
            check_query = f"""
                SELECT COUNT(*) as count
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'trap_master_data'
                AND INDEX_NAME = '{index_name}'
            """
            
            result = self.db.db_to_df(
                table=None,
                database='data',
                query=check_query
            )
            
            if result.empty or result.iloc[0]['count'] == 0:
                try:
                    create_query = f"""
                        ALTER TABLE trap_master_data
                        ADD INDEX {index_name} ({index_column})
                    """
                    
                    with self.db._get_connection('data') as conn:
                        conn.execute(text(create_query))
                        conn.commit()
                    
                    self.logger.info(f"✅ Index {index_name} created")
                except Exception as e:
                    if "Duplicate key name" in str(e):
                        pass  # Already exists
                    else:
                        self.logger.warning(f"Failed to create index {index_name}: {e}")
    
    async def _read_batch(
        self,
        table_name: str,
        offset: int,
        limit: int
    ) -> pd.DataFrame:
        """Read batch from source table."""
        
        query = f"""
            SELECT * FROM `{table_name}`
            LIMIT {limit} OFFSET {offset}
        """
        
        return await asyncio.to_thread(
            self.db.db_to_df,
            table=None,
            database='data',
            query=query
        )
    
    def _get_table_row_count(self, table_name: str) -> int:
        """Get total row count for table."""
        
        query = f"SELECT COUNT(*) as count FROM `{table_name}`"
        
        result = self.db.db_to_df(
            table=None,
            database='data',
            query=query
        )
        
        if result.empty:
            return 0
        
        return int(result.iloc[0]['count'])
    
    def _update_sync_status(
        self,
        table_name: str,
        status: str,
        rows_synced: int = 0,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        sync_method: Optional[str] = None,
        dedup_strategy: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Update sync status in system database using UPSERT."""
        
        upsert_query = text("""
            INSERT INTO trap_sync_status (
                table_name, sync_status, last_sync_at,
                rows_synced, rows_inserted, rows_updated, rows_skipped,
                sync_method, dedup_strategy, error_message, updated_at
            ) VALUES (
                :table_name, :status, :last_sync_at,
                :rows_synced, :rows_inserted, :rows_updated, :rows_skipped,
                :sync_method, :dedup_strategy, :error_message, NOW()
            )
            ON DUPLICATE KEY UPDATE
                sync_status = VALUES(sync_status),
                last_sync_at = VALUES(last_sync_at),
                rows_synced = VALUES(rows_synced),
                rows_inserted = VALUES(rows_inserted),
                rows_updated = VALUES(rows_updated),
                rows_skipped = VALUES(rows_skipped),
                sync_method = VALUES(sync_method),
                dedup_strategy = VALUES(dedup_strategy),
                error_message = VALUES(error_message),
                updated_at = NOW()
        """)
        
        with self.db._get_connection('system') as conn:
            conn.execute(upsert_query, {
                'table_name': table_name,
                'status': status,
                'last_sync_at': datetime.now() if status == 'completed' else None,
                'rows_synced': rows_synced,
                'rows_inserted': rows_inserted,
                'rows_updated': rows_updated,
                'rows_skipped': rows_skipped,
                'sync_method': sync_method,
                'dedup_strategy': dedup_strategy,
                'error_message': error_message
            })
            conn.commit()
    
    async def _send_progress(
        self,
        table_name: str,
        status: str,
        progress: int,
        message: str
    ):
        """Send progress update via WebSocket."""
        
        if self.ws_manager is None:
            return
        
        try:
            await self.ws_manager.publish(
                topic=f'sync:{table_name}',
                message={
                    'table_name': table_name,
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to send WebSocket progress: {e}")
    
    def get_sync_status(self, table_name: Optional[str] = None) -> List[Dict]:
        """
        Get sync status for table(s).
        
        Args:
            table_name: Specific table (None for all)
        
        Returns:
            List of sync status records
        """
        if table_name:
            query = f"""
                SELECT * FROM trap_sync_status
                WHERE table_name = '{table_name}'
            """
        else:
            query = """
                SELECT * FROM trap_sync_status
                ORDER BY last_sync_at DESC
            """
        
        df = self.db.db_to_df(
            table=None,
            database='system',
            query=query
        )
        
        if df.empty:
            return []
        
        return df.to_dict('records')
    

    async def sync_all_tables(
        self, 
        strategy: Optional[str] = None,
        skip_synced: bool = False
    ) -> Dict[str, Any]:
        """
        Sync all user tables to trap_master_data.
        
        Args:
            strategy: Dedup strategy (uses config default if None)
            skip_synced: Skip tables that are already synced successfully
        """
        start_time = time.time()
        
        # Use config strategy if not provided
        if strategy is None:
            strategy = self.config.traps.sync_strategy
        
        # Use config skip_synced if not provided
        if skip_synced is None:
            skip_synced = self.config.traps.skip_synced
        
        self.logger.info(f"🔄 Starting sync for all user tables (strategy={strategy}, skip_synced={skip_synced})")
        
        # Get all user tables
        tables = self._get_user_tables()
        
        if not tables:
            self.logger.warning("No user tables found to sync")
            return {
                'success': True,
                'tables_synced': 0,
                'tables_failed': 0,
                'tables_skipped': 0,
                'results': []
            }
        
        self.logger.info(f"Found {len(tables)} user tables to sync")
        
        # Send initial WebSocket update
        await self._send_sync_all_progress('started', 0, f"Starting sync for {len(tables)} tables", None)
        
        results = []
        success_count = 0
        failed_count = 0
        skipped_count = 0
        total_stats = {
            'total_rows_synced': 0,
            'total_rows_inserted': 0,
            'total_rows_updated': 0,
            'total_rows_skipped': 0
        }
        
        # ✅ Track actual table index for progress (excluding skipped)
        processed_idx = 0
        
        for idx, table in enumerate(tables):
            # ✅ Check if table should be skipped
            if skip_synced:
                sync_status = self._get_table_sync_status(table)
                
                # ✅ Skip if table has been successfully synced
                if sync_status and sync_status.get('sync_status') in ['success', 'completed']:
                    self.logger.info(f"⏭️  Skipping {table} (already synced at {sync_status.get('last_sync_at')})")
                    skipped_count += 1
                    
                    # Add to results as skipped
                    results.append({
                        'success': True,
                        'table_name': table,
                        'skipped': True,
                        'reason': 'Already synced',
                        'duration': 0,
                        'rows_inserted': 0,
                        'rows_updated': 0,
                        'rows_skipped': 0,
                        'rows_processed': 0
                    })
                    
                    # ✅ Send progress update for skipped table
                    overall_progress = int(((idx + 1) / len(tables)) * 100)
                    await self._send_sync_all_progress(
                        'syncing',
                        overall_progress,
                        f"Skipped table {idx + 1}/{len(tables)}: {table} (already synced)",
                        table
                    )
                    
                    continue  # ✅ CRITICAL: Skip to next table
            
            # Send progress update for table being synced
            processed_idx += 1
            overall_progress = int(((idx + 1) / len(tables)) * 100)
            await self._send_sync_all_progress(
                'syncing',
                overall_progress,
                f"Syncing table {processed_idx}/{len(tables) - skipped_count}: {table}",
                table
            )
            
            # Sync table
            result = await self.sync_table(table, strategy=strategy)
            
            # Flatten stats structure for frontend
            if result['success'] and 'stats' in result:
                stats = result['stats']
                result['rows_inserted'] = stats.get('rows_inserted', 0)
                result['rows_updated'] = stats.get('rows_updated', 0)
                result['rows_skipped'] = stats.get('rows_skipped', 0)
                result['rows_processed'] = stats.get('rows_processed', 0)
            
            results.append(result)
            
            if result['success']:
                success_count += 1
                # Use flattened stats
                total_stats['total_rows_inserted'] += result.get('rows_inserted', 0)
                total_stats['total_rows_updated'] += result.get('rows_updated', 0)
                total_stats['total_rows_skipped'] += result.get('rows_skipped', 0)
                total_stats['total_rows_synced'] += result.get('rows_inserted', 0) + result.get('rows_updated', 0)
            else:
                failed_count += 1
        
        # Calculate total duration
        total_duration = time.time() - start_time
        
        # Send completion update
        completion_msg = f"✅ Sync all completed ({total_duration:.2f}s): {success_count} synced, {failed_count} failed"
        if skipped_count > 0:
            completion_msg += f", {skipped_count} skipped"
        
        await self._send_sync_all_progress(
            'completed',
            100,
            completion_msg,
            None
        )
        
        self.logger.info(
            f"✅ Sync all completed: {success_count} synced, {failed_count} failed, {skipped_count} skipped"
        )
        
        return {
            'success': True,
            'tables_synced': success_count,
            'tables_failed': failed_count,
            'tables_skipped': skipped_count,
            'total_tables': len(tables),
            'total_duration': total_duration,
            'overall_stats': total_stats,
            'results': results
        }
    
    
    def _get_table_sync_status(self, table_name: str) -> Optional[dict]:
        """
        Get sync status for a specific table.
        
        Returns:
            Sync status dict or None if not found
        """
        try:
            query = """
                SELECT 
                    table_name,
                    sync_status,
                    last_sync_at,
                    rows_synced,
                    rows_inserted,
                    rows_updated,
                    rows_skipped
                FROM trap_sync_status
                WHERE table_name = :table_name
                ORDER BY last_sync_at DESC
                LIMIT 1
            """
            
            with self.db._get_connection('system') as conn:
                result = conn.execute(text(query), {'table_name': table_name})
                row = result.fetchone()
                
                if row:
                    return {
                        'table_name': row[0],
                        'sync_status': row[1],
                        'last_sync_at': row[2],
                        'rows_synced': row[3],
                        'rows_inserted': row[4],
                        'rows_updated': row[5],
                        'rows_skipped': row[6]
                    }
                
                return None
        
        except Exception as e:
            self.logger.warning(f"Failed to get sync status for {table_name}: {e}")
            return None
    
    
    async def _send_sync_all_progress(
        self,
        status: str,
        progress: int,
        message: str,
        current_table: Optional[str] = None  # ✅ Add current table parameter
    ):
        """
        Send progress update for sync all operation via WebSocket.
        
        Uses topic 'sync:all' for sync all operations.
        """
        if self.ws_manager is None:
            return
        
        try:
            await self.ws_manager.publish(
                topic='sync:all',
                message={
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'current_table': current_table,  # ✅ Include current table
                    'timestamp': datetime.now().isoformat()
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to send sync all progress: {e}")
    
    
    def _get_user_tables(self) -> List[str]:
        """Get list of user tables (exclude system tables)."""
        
        database_name = self.config.database.parser_db
        query = f"""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = '{database_name}'
            AND TABLE_TYPE = 'BASE TABLE'
            AND TABLE_NAME NOT IN ('trap_master_data', 'trap_sync_status')
            ORDER BY TABLE_NAME
        """
        
        df = self.db.db_to_df(
            table=None,
            database='data',
            query=query
        )
        
        if df.empty:
            return []
        
        return df['TABLE_NAME'].tolist()
