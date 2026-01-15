"""
Trap Builder API Endpoints

Handles trap building operations:
- List notifications
- Get notification details
- Get notification objects
- Search varbinds
- Build trap structure
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from backend.services.trap_builder_service import TrapBuilderService
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# NOTIFICATION ENDPOINTS
# ============================================

@router.get("/notifications")
async def list_notifications(
    request: Request,
    search: Optional[str] = Query(None, description="Search term"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    List available notifications.
    
    Query Parameters:
        search: Search term (optional)
        limit: Maximum results (default 100)
        offset: Offset for pagination (default 0)
    
    Returns:
        List of notifications with details
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # List notifications
        notifications = builder.list_notifications(
            search=search,
            limit=limit,
            offset=offset
        )
        
        return {
            'success': True,
            'notifications': notifications,
            'count': len(notifications),
            'limit': limit,
            'offset': offset
        }
    
    except Exception as e:
        logger.error(f"List notifications failed: {e}", exc_info=True)
        raise HTTPException(500, f"List notifications failed: {str(e)}")


@router.get("/notifications/{notification_name}")
async def get_notification(
    request: Request,
    notification_name: str
):
    """
    Get notification details.
    
    Path Parameters:
        notification_name: Notification name (e.g., 'linkDown')
    
    Returns:
        Notification details
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Get notification
        notification = builder.get_notification(notification_name)
        
        if not notification:
            raise HTTPException(404, f"Notification '{notification_name}' not found")
        
        return {
            'success': True,
            'notification': notification
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notification failed: {e}", exc_info=True)
        raise HTTPException(500, f"Get notification failed: {str(e)}")


@router.get("/notifications/{notification_name}/objects")
async def get_notification_objects(
    request: Request,
    notification_name: str
):
    """
    Get objects (varbinds) for a notification.
    
    Path Parameters:
        notification_name: Notification name
    
    Returns:
        List of notification objects with details
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Get objects
        objects = builder.get_notification_objects(notification_name)
        
        if not objects:
            raise HTTPException(404, f"No objects found for notification '{notification_name}'")
        
        return {
            'success': True,
            'notification_name': notification_name,
            'objects': objects,
            'count': len(objects)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notification objects failed: {e}", exc_info=True)
        raise HTTPException(500, f"Get notification objects failed: {str(e)}")


@router.get("/notifications/{notification_name}/build")
async def build_trap_structure(
    request: Request,
    notification_name: str
):
    """
    Build complete trap structure for a notification.
    
    Path Parameters:
        notification_name: Notification name
    
    Returns:
        Complete trap structure ready to send
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Build trap structure
        trap = builder.build_trap_structure(notification_name)
        
        return {
            'success': True,
            'trap': trap
        }
    
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"Build trap structure failed: {e}", exc_info=True)
        raise HTTPException(500, f"Build trap structure failed: {str(e)}")


# ============================================
# VARBIND SEARCH ENDPOINTS
# ============================================

@router.get("/varbinds/search")
async def search_varbinds(
    request: Request,
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results")
):
    """
    Search for varbinds (objects) to add to trap.
    
    Query Parameters:
        q: Search query (required)
        limit: Maximum results (default 50)
    
    Returns:
        List of matching objects
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Search varbinds
        varbinds = builder.search_varbinds(q, limit)
        
        return {
            'success': True,
            'query': q,
            'varbinds': varbinds,
            'count': len(varbinds)
        }
    
    except Exception as e:
        logger.error(f"Search varbinds failed: {e}", exc_info=True)
        raise HTTPException(500, f"Search varbinds failed: {str(e)}")


# ============================================
# OID RESOLVER ENDPOINTS
# ============================================

@router.get("/oid/resolve")
async def resolve_oid(
    request: Request,
    oid: str = Query(..., description="OID to resolve")
):
    """
    Resolve OID to name and description.
    
    Query Parameters:
        oid: OID string (e.g., '1.3.6.1.2.1.1.3.0')
    
    Returns:
        Resolved OID details
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service (includes OID resolver)
        builder = TrapBuilderService(db)
        
        # Resolve OID
        result = builder.oid_resolver.resolve_oid(oid)
        
        if not result:
            raise HTTPException(404, f"OID '{oid}' not found")
        
        return {
            'success': True,
            'oid': result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve OID failed: {e}", exc_info=True)
        raise HTTPException(500, f"Resolve OID failed: {str(e)}")


@router.post("/oid/resolve-batch")
async def resolve_oids_batch(
    request: Request,
    oids: list[str]
):
    """
    Resolve multiple OIDs at once.
    
    Body:
        oids: List of OID strings
    
    Returns:
        Dict mapping OID -> resolved data
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Resolve batch
        results = builder.oid_resolver.resolve_batch(oids)
        
        return {
            'success': True,
            'results': results,
            'resolved_count': len(results),
            'total_count': len(oids)
        }
    
    except Exception as e:
        logger.error(f"Resolve batch failed: {e}", exc_info=True)
        raise HTTPException(500, f"Resolve batch failed: {str(e)}")


@router.get("/oid/cache/stats")
async def get_cache_stats(request: Request):
    """
    Get OID cache statistics.
    
    Returns:
        Cache statistics
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Get cache stats
        stats = builder.oid_resolver.get_cache_stats()
        
        return {
            'success': True,
            'cache_stats': stats
        }
    
    except Exception as e:
        logger.error(f"Get cache stats failed: {e}", exc_info=True)
        raise HTTPException(500, f"Get cache stats failed: {str(e)}")


@router.post("/oid/cache/clear")
async def clear_cache(request: Request):
    """
    Clear OID cache.
    
    Returns:
        Success status
    """
    try:
        db = request.app.state.db_manager
        
        # Create builder service
        builder = TrapBuilderService(db)
        
        # Clear cache
        builder.oid_resolver.clear_cache()
        
        return {
            'success': True,
            'message': 'Cache cleared'
        }
    
    except Exception as e:
        logger.error(f"Clear cache failed: {e}", exc_info=True)
        raise HTTPException(500, f"Clear cache failed: {str(e)}")
