
"""
SNMP Walk API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query

from backend.models.snmp_walk_schemas import (
    SNMPDevice,
    SNMPDeviceCreate,
    SNMPDeviceUpdate,
    SNMPWalkConfig,
    SNMPWalkConfigCreate,
    SNMPWalkConfigUpdate,
    SNMPWalkExecuteRequest,
    SNMPWalkExecuteResponse,
    SNMPWalkQueryRequest,
    SNMPWalkQueryResponse,
    SNMPWalkStats,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================
# DEVICE ENDPOINTS
# ============================================

@router.post("/devices", response_model=dict)
async def create_device(device: SNMPDeviceCreate, request: Request):
    """
    Create new SNMP device.
    
    Example:
    ```json
    {
        "name": "core-router-1",
        "ip_address": "192.168.1.1",
        "snmp_community": "public",
        "snmp_port": 161,
        "enabled": true,
        "description": "Core router",
        "location": "Data Center 1",
        "device_type": "Router",
        "vendor": "Cisco"
    }
    ```
    """
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.create_device(device.dict())
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to create device'))
    
    except Exception as e:
        logger.error(f"Create device failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices", response_model=List[SNMPDevice])
async def list_devices(
    request: Request,
    enabled_only: bool = Query(False, description="Show only enabled devices"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List all SNMP devices."""
    try:
        walk_service = request.app.state.walk_service
        devices = walk_service.list_devices(
            enabled_only=enabled_only,
            limit=limit,
            offset=offset
        )
        return devices
    
    except Exception as e:
        logger.error(f"List devices failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}", response_model=SNMPDevice)
async def get_device(device_id: int, request: Request):
    """Get device by ID."""
    try:
        walk_service = request.app.state.walk_service
        device = walk_service.get_device(device_id)
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
        
        return device
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get device failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/devices/{device_id}", response_model=dict)
async def update_device(device_id: int, device: SNMPDeviceUpdate, request: Request):
    """
    Update device.
    
    All fields are optional - only provided fields will be updated.
    """
    try:
        walk_service = request.app.state.walk_service
        
        # Filter out None values
        update_data = {k: v for k, v in device.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        result = walk_service.update_device(device_id, update_data)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to update device'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update device failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/devices/{device_id}", response_model=dict)
async def delete_device(device_id: int, request: Request):
    """
    Delete device.
    
    ⚠️ Warning: This will also delete all walk results for this device (CASCADE).
    """
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.delete_device(device_id)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to delete device'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete device failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# WALK CONFIG ENDPOINTS
# ============================================

@router.post("/configs", response_model=dict)
async def create_walk_config(config: SNMPWalkConfigCreate, request: Request):
    """
    Create new walk configuration.
    
    Example:
    ```json
    {
        "name": "BGP Peers",
        "description": "Walk BGP peer table",
        "base_oid": "1.3.6.1.2.1.15.3",
        "walk_type": "bgp_peers",
        "enabled": true
    }
    ```
    """
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.create_walk_config(config.dict())
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to create config'))
    
    except Exception as e:
        logger.error(f"Create walk config failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs", response_model=List[SNMPWalkConfig])
async def list_walk_configs(
    request: Request,
    enabled_only: bool = Query(False, description="Show only enabled configs"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List all walk configurations."""
    try:
        walk_service = request.app.state.walk_service
        configs = walk_service.list_walk_configs(
            enabled_only=enabled_only,
            limit=limit,
            offset=offset
        )
        return configs
    
    except Exception as e:
        logger.error(f"List walk configs failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs/{config_id}", response_model=SNMPWalkConfig)
async def get_walk_config(config_id: int, request: Request):
    """Get walk configuration by ID."""
    try:
        walk_service = request.app.state.walk_service
        config = walk_service.get_walk_config(config_id)
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Config {config_id} not found")
        
        return config
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get walk config failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configs/{config_id}", response_model=dict)
async def update_walk_config(config_id: int, config: SNMPWalkConfigUpdate, request: Request):
    """
    Update walk configuration.
    
    All fields are optional - only provided fields will be updated.
    """
    try:
        walk_service = request.app.state.walk_service
        
        # Filter out None values
        update_data = {k: v for k, v in config.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        result = walk_service.update_walk_config(config_id, update_data)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to update config'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update walk config failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configs/{config_id}", response_model=dict)
async def delete_walk_config(config_id: int, request: Request):
    """Delete walk configuration."""
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.delete_walk_config(config_id)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to delete config'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete walk config failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# WALK EXECUTION ENDPOINTS
# ============================================

@router.post("/execute", response_model=SNMPWalkExecuteResponse)
async def execute_walk(walk_request: SNMPWalkExecuteRequest, request: Request):
    """
    Execute SNMP walk on a device.
    
    You can either:
    1. Use a predefined config: `{"device_id": 1, "config_id": 2}`
    2. Use custom OID: `{"device_id": 1, "base_oid": "1.3.6.1.2.1.2.2"}`
    
    Example:
    ```json
    {
        "device_id": 1,
        "config_id": 2,
        "resolve_oids": true
    }
    ```
    
    Or:
    ```json
    {
        "device_id": 1,
        "base_oid": "1.3.6.1.2.1.2.2",
        "walk_type": "interfaces",
        "resolve_oids": true
    }
    ```
    """
    try:
        walk_service = request.app.state.walk_service
        
        # Determine base_oid and config details
        base_oid = walk_request.base_oid
        config_id = walk_request.config_id
        config_name = None
        walk_type = walk_request.walk_type
        
        # If config_id provided, get config details
        if config_id:
            config = walk_service.get_walk_config(config_id)
            if not config:
                raise HTTPException(status_code=404, detail=f"Config {config_id} not found")
            
            if not config['enabled']:
                raise HTTPException(status_code=400, detail=f"Config '{config['name']}' is disabled")
            
            base_oid = config['base_oid']
            config_name = config['name']
            walk_type = config['walk_type']
        
        # Validate base_oid
        if not base_oid:
            raise HTTPException(
                status_code=400,
                detail="Either config_id or base_oid must be provided"
            )
        
        # Generate job_id for tracking
        import uuid
        job_id = str(uuid.uuid4())
        
        # Execute walk
        result = await walk_service.execute_walk(
            device_id=walk_request.device_id,
            base_oid=base_oid,
            config_id=config_id,
            config_name=config_name,
            walk_type=walk_type,
            resolve_oids=walk_request.resolve_oids,
            job_id=job_id
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Walk execution failed'))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute walk failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# QUERY RESULTS ENDPOINTS
# ============================================

@router.post("/results/query", response_model=SNMPWalkQueryResponse)
async def query_walk_results(query_request: SNMPWalkQueryRequest, request: Request):
    """
    Query walk results with filters.
    
    Example:
    ```json
    {
        "device_id": 1,
        "resolved_only": true,
        "limit": 100,
        "offset": 0,
        "sort_by": "collected_at",
        "sort_order": "desc"
    }
    ```
    """
    try:
        walk_service = request.app.state.walk_service
        
        result = walk_service.query_walk_results(
            device_id=query_request.device_id,
            device_name=query_request.device_name,
            config_id=query_request.config_id,
            base_oid=query_request.base_oid,
            walk_type=query_request.walk_type,
            oid_filter=query_request.oid_filter,
            resolved_only=query_request.resolved_only,
            limit=query_request.limit,
            offset=query_request.offset,
            sort_by=query_request.sort_by,
            sort_order=query_request.sort_order
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Query failed'))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query walk results failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/latest")
async def get_latest_results(
    request: Request,
    device_id: Optional[int] = Query(None, description="Filter by device ID"),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get latest walk results (shortcut endpoint)."""
    try:
        walk_service = request.app.state.walk_service
        
        result = walk_service.query_walk_results(
            device_id=device_id,
            limit=limit,
            offset=0,
            sort_by="collected_at",
            sort_order="desc"
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Query failed'))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get latest results failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/results/clear", response_model=dict)
async def clear_walk_results(
    request: Request,
    device_id: Optional[int] = Query(None, description="Clear results for specific device"),
    older_than_days: Optional[int] = Query(None, description="Clear results older than N days")
):
    """
    Clear walk results.
    
    Examples:
    - Clear all results: `DELETE /results/clear`
    - Clear for device: `DELETE /results/clear?device_id=1`
    - Clear old results: `DELETE /results/clear?older_than_days=30`
    """
    try:
        walk_service = request.app.state.walk_service
        
        result = walk_service.clear_walk_results(
            device_id=device_id,
            older_than_days=older_than_days
        )
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to clear results'))
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear walk results failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@router.get("/stats", response_model=SNMPWalkStats)
async def get_walk_statistics(request: Request):
    """
    Get walk statistics.
    
    Returns:
    - Total devices (enabled/disabled)
    - Total walk configs (enabled/disabled)
    - Total walk results
    - OID resolution statistics
    - Last walk time
    """
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.get_walk_statistics()
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to get statistics'))
        
        return result['stats']
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get statistics failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UTILITY ENDPOINTS
# ============================================

@router.get("/oid-resolver/search")
async def search_oids(
    request: Request,
    search: str = Query(..., min_length=2, description="Search term"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Search OIDs in trap_master_data.
    
    Useful for finding OIDs to walk.
    
    Example: `/oid-resolver/search?search=bgp&limit=20`
    """
    try:
        walk_service = request.app.state.walk_service
        results = walk_service.oid_resolver.search_objects(
            search=search,
            limit=limit
        )
        
        return {
            'success': True,
            'search': search,
            'count': len(results),
            'results': results
        }
    
    except Exception as e:
        logger.error(f"OID search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oid-resolver/resolve/{oid:path}")
async def resolve_oid(oid: str, request: Request):
    """
    Resolve single OID to name/description.
    
    Example: `/oid-resolver/resolve/1.3.6.1.2.1.1.3.0`
    """
    try:
        walk_service = request.app.state.walk_service
        result = walk_service.oid_resolver.resolve_oid(oid)
        
        if result:
            return {
                'success': True,
                'result': result
            }
        else:
            return {
                'success': False,
                'message': f"OID '{oid}' not found in trap_master_data"
            }
    
    except Exception as e:
        logger.error(f"OID resolution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))