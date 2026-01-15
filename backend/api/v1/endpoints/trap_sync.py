"""
Trap Sync API Endpoints

Handles MIB data synchronization to trap_master_data table.
"""

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Request, WebSocket, WebSocketDisconnect

from backend.services.trap_sync_service import TrapSyncService
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# SYNC ENDPOINTS
# ============================================

@router.post("/sync/table")
async def sync_table(
    request: Request,
    table_name: str = Body(..., description="User table name to sync"),
    strategy: Optional[str] = Body(None, description="Deduplication strategy"),
    force_full: bool = Body(False, description="Ignored (kept for compatibility)")
):
    """
    Sync user table to trap_master_data.
    
    Body Parameters:
        table_name: User table name (required)
        strategy: Dedup strategy (append, newest, replace, skip)
        force_full: Ignored (kept for backward compatibility)
    
    Returns:
        Sync result with statistics
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        ws_manager = request.app.state.ws_manager  # Get WebSocket manager
        
        # ✅ Use strategy from config, allow override
        if not strategy:
            strategy = config.traps.sync_strategy
        
        logger.info(f"Sync table request: {table_name}, strategy: {strategy}")
        
        # Create sync service with WebSocket support
        sync_service = TrapSyncService(db, config, ws_manager)
        
        # Sync table
        result = await sync_service.sync_table(
            table_name=table_name,
            strategy=strategy,
            force_full=force_full
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(500, f"Sync failed: {str(e)}")


@router.post("/sync/all")
async def sync_all_tables(
    request: Request,
    body: dict = Body(default={})  # ✅ Accept JSON object
):
    """
    Sync all user tables to trap_master_data.
    
    Body Parameters:
        strategy: Dedup strategy (optional, uses 'append' if not specified)
    
    Example:
        {
            "strategy": "append"
        }
    
    Returns:
        Overall sync results
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        ws_manager = request.app.state.ws_manager
        
        # ✅ Use config values, allow override
        strategy = body.get('strategy', config.traps.sync_strategy)
        skip_synced = body.get('skip_synced', config.traps.skip_synced)
        
        logger.info(f"Sync all tables request: strategy={strategy}, skip_synced={skip_synced}")
        
        # Create sync service
        sync_service = TrapSyncService(db, config, ws_manager)
        
        # Sync all tables
        result = await sync_service.sync_all_tables(
            strategy=strategy,
            skip_synced=skip_synced
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Sync all failed: {e}", exc_info=True)
        raise HTTPException(500, f"Sync all failed: {str(e)}")


@router.get("/sync/status")
async def get_sync_status(
    request: Request,
    table_name: Optional[str] = None
):
    """
    Get sync status for table(s).
    
    Query Parameters:
        table_name: Specific table (optional, returns all if not specified)
    
    Returns:
        List of sync status records
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # Create sync service (no WebSocket needed for status)
        sync_service = TrapSyncService(db, config)
        
        # Get status
        status = sync_service.get_sync_status(table_name)
        
        return {
            'success': True,
            'status': status,
            'count': len(status)
        }
    
    except Exception as e:
        logger.error(f"Get sync status failed: {e}", exc_info=True)
        raise HTTPException(500, f"Get sync status failed: {str(e)}")


@router.get("/sync/tables")
async def list_user_tables(request: Request):
    """
    Get list of user tables available for sync.
    
    Returns:
        List of user table names with sync status
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # Create sync service
        sync_service = TrapSyncService(db, config)
        
        # Get user tables
        tables = sync_service._get_user_tables()
        
        # Get sync status for each
        status_list = sync_service.get_sync_status()
        status_map = {s['table_name']: s for s in status_list}
        
        # Combine
        result = []
        for table in tables:
            status = status_map.get(table, {})
            result.append({
                'table_name': table,
                'sync_status': status.get('sync_status', 'never'),
                'last_sync_at': status.get('last_sync_at'),
                'rows_synced': status.get('rows_synced', 0),
                'notifications_count': status.get('notifications_count', 0)
            })
        
        return {
            'success': True,
            'tables': result,
            'count': len(result)
        }
    
    except Exception as e:
        logger.error(f"List user tables failed: {e}", exc_info=True)
        raise HTTPException(500, f"List user tables failed: {str(e)}")


@router.get("/master/stats")
async def get_master_table_stats(request: Request):
    """
    Get statistics about trap_master_data table.
    
    Returns:
        Master table statistics
    """
    try:
        db = request.app.state.db_manager
        
        # Check if table exists
        if not db.table_exists('trap_master_data', database='data'):
            return {
                'success': True,
                'exists': False,
                'message': 'trap_master_data table does not exist yet'
            }
        
        # Get table info
        info = db.get_table_info('trap_master_data', database='data')
        
        if info.empty:
            return {
                'success': True,
                'exists': True,
                'total_rows': 0
            }
        
        # Get counts by type
        counts_query = """
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT notification_oid) as total_notifications,
                COUNT(DISTINCT object_oid) as total_objects,
                COUNT(DISTINCT source_table) as source_tables,
                COUNT(DISTINCT module_name) as modules
            FROM trap_master_data
        """
        
        counts = db.db_to_df(
            table=None,
            database='data',
            query=counts_query
        )
        
        row = info.iloc[0]
        counts_row = counts.iloc[0] if not counts.empty else {}
        
        return {
            'success': True,
            'exists': True,
            'total_rows': int(counts_row.get('total_rows', 0)),
            'total_notifications': int(counts_row.get('total_notifications', 0)),
            'total_objects': int(counts_row.get('total_objects', 0)),
            'source_tables': int(counts_row.get('source_tables', 0)),
            'modules': int(counts_row.get('modules', 0)),
            'size_mb': float(row['size_mb']),
            'created': row.get('created'),
            'updated': row.get('last_updated')
        }
    
    except Exception as e:
        logger.error(f"Get master stats failed: {e}", exc_info=True)
        raise HTTPException(500, f"Get master stats failed: {str(e)}")

# Web Socket
@router.websocket("/ws/{table_name}")
async def sync_websocket(websocket: WebSocket, table_name: str):
    """
    WebSocket endpoint for sync progress updates.
    
    Path Parameters:
        table_name: Table being synced
    
    Example:
        ws://localhost:8000/api/v1/trap-sync/ws/cisco_mibs
    """
    # ✅ Get ws_manager from app state via websocket
    ws_manager = websocket.app.state.ws_manager
    
    await ws_manager.connect(websocket)
    
    # Subscribe to sync topic
    topic = f'sync:{table_name}'
    ws_manager.subscribe(topic, websocket)
    
    logger.info(f"🔌 WebSocket connected for sync: {table_name}")
    
    try:
        while True:
            # Keep connection alive with ping/pong
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_text('pong')
    
    except WebSocketDisconnect:
        ws_manager.unsubscribe(topic, websocket)
        ws_manager.disconnect(websocket)
        logger.info(f"🔌 WebSocket disconnected for sync: {table_name}")

@router.websocket("/ws/all")
async def sync_all_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for sync all progress updates.
    
    Example:
        ws://localhost:8000/api/v1/trap-sync/ws/all
    """
    # ✅ Get ws_manager from app state via websocket
    ws_manager = websocket.app.state.ws_manager
    
    await ws_manager.connect(websocket)
    
    # Subscribe to sync all topic
    topic = 'sync:all'
    ws_manager.subscribe(topic, websocket)
    
    logger.info(f"🔌 WebSocket connected for sync all")
    
    try:
        while True:
            # Keep connection alive with ping/pong
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_text('pong')
    
    except WebSocketDisconnect:
        ws_manager.unsubscribe(topic, websocket)
        ws_manager.disconnect(websocket)
        logger.info(f"🔌 WebSocket disconnected for sync all")