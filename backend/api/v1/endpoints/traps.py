"""
SNMP Trap API Endpoints
Handles trap sending, receiving, and management
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, HTTPException, Request

from backend.services.trap_sender import TrapSenderService
from backend.services.trap_builder_service import TrapBuilderService  # ✅ NEW

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# TRAP SENDER ENDPOINTS
# ============================================

@router.get("/available")
async def get_available_traps(
    request: Request,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get available traps from trap_master_data.
    
    Query Parameters:
        search: Search term for filtering (optional)
        limit: Maximum records to return (default 100)
        offset: Offset for pagination (default 0)
    
    Returns:
        List of available traps with their details
    """
    try:
        db = request.app.state.db_manager
        
        # ✅ UPDATED: Use TrapBuilderService
        builder = TrapBuilderService(db)
        
        # Get notifications
        traps = builder.list_notifications(
            search=search,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "traps": traps,
            "total": len(traps),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get available traps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get traps: {str(e)}")


# ✅ NEW: Get notification details
@router.get("/notifications/{notification_name}")
async def get_notification_details(
    request: Request,
    notification_name: str
):
    """
    Get notification details including objects.
    
    Path Parameters:
        notification_name: Notification name (e.g., 'linkDown')
    
    Returns:
        Notification details with objects
    """
    try:
        db = request.app.state.db_manager
        builder = TrapBuilderService(db)
        
        # Get notification
        notification = builder.get_notification(notification_name)
        if not notification:
            raise HTTPException(404, f"Notification '{notification_name}' not found")
        
        # Get objects
        objects = builder.get_notification_objects(notification_name)
        
        return {
            "success": True,
            "notification": notification,
            "objects": objects
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get notification: {str(e)}")


# ✅ NEW: Send trap by notification name
@router.post("/send-by-name")
async def send_trap_by_name(
    request: Request,
    notification_name: str = Body(..., description="Notification name"),
    target_host: str = Body(..., description="Target IP/hostname"),
    target_port: int = Body(1162, description="Target UDP port"),
    varbind_values: Dict[str, Any] = Body({}, description="Varbind values (name -> value)"),
    snmp_version: str = Body("v2c", description="SNMP version"),
    community: str = Body("public", description="SNMP community string")
):
    """
    Send trap by notification name (simplified).
    
    Body Parameters:
        notification_name: Notification name (e.g., 'linkDown')
        target_host: Target IP address or hostname
        target_port: Target UDP port (default 1162)
        varbind_values: Dict mapping object name to value
                       e.g., {"ifIndex": 5, "ifAdminStatus": 2}
        snmp_version: SNMP version (v2c)
        community: SNMP community string (default "public")
    
    Returns:
        Send result with status and details
    """
    try:
        db = request.app.state.db_manager
        
        # Initialize services
        sender = TrapSenderService(db)
        builder = TrapBuilderService(db)
        
        # Get notification details
        notification = builder.get_notification(notification_name)
        if not notification:
            raise HTTPException(404, f"Notification '{notification_name}' not found")
        
        # Get notification objects
        objects = builder.get_notification_objects(notification_name)
        
        # ✅ NEW: Build two versions of varbinds
        # 1. varbinds_for_sending: with OIDs (for SNMP protocol)
        # 2. varbinds_for_storage: with names (for database)
        
        varbinds_for_sending = []
        varbinds_for_storage = []
        
        for obj in objects:
            obj_name = obj['name']
            obj_oid = obj['oid']
            
            # Get value from user input
            if obj_name in varbind_values:
                value = varbind_values[obj_name]
            else:
                # Use empty string if not provided
                value = ""
            
            # Determine type from syntax
            syntax = obj.get('syntax', 'OctetString')
            data_type = _map_syntax_to_type(syntax)
            
            # For sending (with OID)
            varbinds_for_sending.append({
                'oid': obj_oid,
                'type': data_type,
                'value': value
            })
            
            # ✅ For storage (with name)
            varbinds_for_storage.append({
                'name': obj_name,
                'oid': obj_oid,
                'type': data_type,
                'syntax': syntax,
                'value': value,
                'description': obj.get('description', '')
            })
        
        # Send trap
        result = await sender.send_trap(
            trap_oid=notification['oid'],
            target_host=target_host,
            target_port=target_port,
            varbinds=varbinds_for_sending,  # ✅ Send with OIDs
            snmp_version=snmp_version,
            community=community,
            trap_name=notification_name,  # ✅ Pass trap name
            original_varbinds=varbinds_for_storage  # ✅ Store with names
        )
        
        if not result['success']:
            raise HTTPException(500, result.get('error', 'Send failed'))
        
        return {
            "success": True,
            "message": f"Trap '{notification_name}' sent to {target_host}:{target_port}",
            "notification_name": notification_name,
            "trap_oid": notification['oid'],
            "trap_id": result.get('trap_id'),
            "duration": result.get('duration'),
            "varbinds_sent": result.get('varbinds_sent', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send trap: {e}", exc_info=True)
        raise HTTPException(500, f"Send failed: {str(e)}")


@router.post("/send")
async def send_trap(
    request: Request,
    trap_oid: str = Body(..., description="Trap notification OID"),
    target_host: str = Body(..., description="Target IP/hostname"),
    target_port: int = Body(1162, description="Target UDP port"),
    varbinds: List[Dict[str, Any]] = Body([], description="List of varbinds"),
    snmp_version: str = Body("v2c", description="SNMP version"),
    community: str = Body("public", description="SNMP community string"),
    template_id: Optional[int] = Body(None, description="Template ID for logging")
):
    """
    Send SNMP trap to target device (advanced).
    
    Body Parameters:
        trap_oid: Trap notification OID (required)
        target_host: Target IP address or hostname (required)
        target_port: Target UDP port (default 1162)
        varbinds: List of varbinds [{"oid": "...", "type": "...", "value": "..."}]
        snmp_version: SNMP version (v2c)
        community: SNMP community string (default "public")
        template_id: Optional template ID for logging
    
    Returns:
        Send result with status and details
    """
    try:
        db = request.app.state.db_manager
        
        # Initialize trap sender
        sender = TrapSenderService(db)
        
        # Validate varbinds
        if varbinds:
            is_valid, error = sender.validate_varbinds(varbinds)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid varbinds: {error}")
        
        # Send trap
        result = await sender.send_trap(
            trap_oid=trap_oid,
            target_host=target_host,
            target_port=target_port,
            varbinds=varbinds,
            snmp_version=snmp_version,
            community=community,
            template_id=template_id
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Send failed'))
        
        return {
            "success": True,
            "message": f"Trap sent to {target_host}:{target_port}",
            "trap_id": result.get('trap_id'),
            "duration": result.get('duration'),
            "varbinds_sent": result.get('varbinds_sent', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send trap: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Send failed: {str(e)}")


@router.get("/sent")
async def get_sent_history(
    request: Request,
    limit: int = 100,
    offset: int = 0
):
    """
    Get sent trap history.
    
    Query Parameters:
        limit: Maximum records to return (default 100)
        offset: Offset for pagination (default 0)
    
    Returns:
        List of sent trap records
    """
    try:
        db = request.app.state.db_manager
        sender = TrapSenderService(db)
        
        history = sender.get_sent_history(limit=limit, offset=offset)
        
        return {
            "success": True,
            "traps": history,
            "total": len(history),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get sent history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/data-types")
async def get_data_types(request: Request):
    """
    Get supported SNMP data types.
    
    Returns:
        List of supported data types
    """
    try:
        db = request.app.state.db_manager
        sender = TrapSenderService(db)
        
        types = sender.get_data_types()
        
        return {
            "success": True,
            "data_types": types
        }
        
    except Exception as e:
        logger.error(f"Failed to get data types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get data types: {str(e)}")


# ============================================
# TRAP TEMPLATE ENDPOINTS
# ============================================

@router.post("/templates")
async def create_template(
    request: Request,
    name: str = Body(..., description="Template name"),
    description: Optional[str] = Body(None, description="Template description"),
    trap_oid: str = Body(..., description="Trap OID"),
    enterprise_oid: Optional[str] = Body(None, description="Enterprise OID"),
    varbinds: List[Dict[str, Any]] = Body([], description="Varbinds"),
    snmp_version: str = Body("v2c", description="SNMP version"),
    community: str = Body("public", description="Community string")
):
    """Create trap template."""
    try:
        db = request.app.state.db_manager
        
        # Validate varbinds
        if varbinds:
            sender = TrapSenderService(db)
            is_valid, error = sender.validate_varbinds(varbinds)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid varbinds: {error}")
        
        # Insert template
        from sqlalchemy import text
        
        query = text("""
            INSERT INTO trap_templates (
                name, description, trap_oid, enterprise_oid,
                varbinds, snmp_version, community
            ) VALUES (:name, :description, :trap_oid, :enterprise_oid, :varbinds, :snmp_version, :community)
        """)
        
        varbinds_json = json.dumps(varbinds) if varbinds else None
        
        with db._get_connection("traps") as conn:
            result = conn.execute(query, {
                'name': name,
                'description': description,
                'trap_oid': trap_oid,
                'enterprise_oid': enterprise_oid,
                'varbinds': varbinds_json,
                'snmp_version': snmp_version,
                'community': community
            })
            conn.commit()
            template_id = result.lastrowid
        
        logger.info(f"✅ Created trap template: {name} (ID: {template_id})")
        
        return {
            "success": True,
            "message": f"Template '{name}' created",
            "template_id": template_id
        }
        
    except Exception as e:
        logger.error(f"Failed to create template: {e}", exc_info=True)
        
        if "Duplicate entry" in str(e):
            raise HTTPException(status_code=400, detail=f"Template '{name}' already exists")
        
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("/templates")
async def get_templates(
    request: Request,
    limit: int = 100,
    offset: int = 0
):
    """Get trap templates."""
    try:
        db = request.app.state.db_manager
        
        query = f"""
            SELECT 
                id, name, description, trap_oid, enterprise_oid,
                varbinds, snmp_version, community, created_at, updated_at
            FROM trap_templates
            ORDER BY name
            LIMIT {limit} OFFSET {offset}
        """
        
        df = db.db_to_df(table=None, database="traps", query=query)
        
        if df.empty:
            return {
                "success": True,
                "templates": [],
                "total": 0
            }
        
        # Convert to list of dicts
        templates = df.to_dict('records')
        
        # Parse varbinds JSON
        for template in templates:
            if template.get('varbinds'):
                try:
                    template['varbinds'] = json.loads(template['varbinds'])
                except:
                    template['varbinds'] = []
        
        return {
            "success": True,
            "templates": templates,
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Failed to get templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")


@router.delete("/templates/{template_id}")
async def delete_template(
    request: Request,
    template_id: int
):
    """Delete trap template."""
    try:
        db = request.app.state.db_manager
        from sqlalchemy import text
        
        # Check if template exists
        check_query = f"SELECT name FROM trap_templates WHERE id = {template_id}"
        df = db.db_to_df(table=None, database="traps", query=check_query)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
        
        template_name = df.iloc[0]['name']
        
        # Delete template
        delete_query = text("DELETE FROM trap_templates WHERE id = :template_id")
        
        with db._get_connection("traps") as conn:
            conn.execute(delete_query, {'template_id': template_id})
            conn.commit()
        
        logger.info(f"✅ Deleted trap template: {template_name} (ID: {template_id})")
        
        return {
            "success": True,
            "message": f"Template '{template_name}' deleted"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


# ============================================
# TRAP RECEIVER ENDPOINTS
# ============================================

@router.post("/receiver/start")
async def start_receiver(
    request: Request,
    port: int = Body(1162, description="UDP port to listen on"),
    bind_address: str = Body("0.0.0.0", description="IP address to bind to"),
    community: str = Body("public", description="SNMP community string")
):
    """Start trap receiver."""
    try:
        # Get or create receiver instance
        if not hasattr(request.app.state, 'trap_receiver'):
            from backend.services.trap_receiver import TrapReceiverService
            db = request.app.state.db_manager
            ws_manager = getattr(request.app.state, 'ws_manager', None)
            request.app.state.trap_receiver = TrapReceiverService(db, ws_manager)
        
        receiver = request.app.state.trap_receiver
        
        result = await receiver.start(
            port=port,
            bind_address=bind_address,
            community=community
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to start receiver: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start receiver: {str(e)}")


@router.post("/receiver/stop")
async def stop_receiver(request: Request):
    """Stop trap receiver."""
    try:
        if not hasattr(request.app.state, 'trap_receiver'):
            raise HTTPException(status_code=400, detail="Receiver not initialized")
        
        receiver = request.app.state.trap_receiver
        result = await receiver.stop()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop receiver: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop receiver: {str(e)}")


@router.get("/receiver/status")
async def get_receiver_status(request: Request):
    """Get trap receiver status."""
    try:
        if not hasattr(request.app.state, 'trap_receiver'):
            return {
                'success': True,
                'running': False,
                'message': 'Receiver not initialized'
            }
        
        receiver = request.app.state.trap_receiver
        status = receiver.get_status()
        
        return {
            'success': True,
            **status
        }
        
    except Exception as e:
        logger.error(f"Failed to get receiver status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/received")
async def get_received_traps(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    source_ip: Optional[str] = None,
    trap_oid: Optional[str] = None
):
    """
    Get received traps.
    
    ✅ UPDATED: Now includes resolved OID names
    
    Query Parameters:
        limit: Maximum records to return (default 100)
        offset: Offset for pagination (default 0)
        source_ip: Filter by source IP (optional)
        trap_oid: Filter by trap OID (optional)
    
    Returns:
        List of received traps with resolved OID names
    """
    try:
        if not hasattr(request.app.state, 'trap_receiver'):
            from backend.services.trap_receiver import TrapReceiverService
            db = request.app.state.db_manager
            request.app.state.trap_receiver = TrapReceiverService(db)
        
        receiver = request.app.state.trap_receiver
        
        traps = receiver.get_received_traps(
            limit=limit,
            offset=offset,
            source_ip=source_ip,
            trap_oid=trap_oid
        )
        
        return {
            'success': True,
            'traps': traps,
            'total': len(traps),
            'limit': limit,
            'offset': offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get received traps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get traps: {str(e)}")


@router.delete("/received")
async def clear_received_traps(request: Request):
    """Clear all received traps."""
    try:
        if not hasattr(request.app.state, 'trap_receiver'):
            from backend.services.trap_receiver import TrapReceiverService
            db = request.app.state.db_manager
            request.app.state.trap_receiver = TrapReceiverService(db)
        
        receiver = request.app.state.trap_receiver
        result = receiver.clear_received_traps()
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to clear traps: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear traps: {str(e)}")


# ============================================
# HELPER FUNCTIONS
# ============================================

def _map_syntax_to_type(syntax: str) -> str:
    """
    Map MIB syntax to SNMP data type.
    
    Args:
        syntax: MIB syntax (e.g., 'Integer32', 'OCTET STRING')
    
    Returns:
        SNMP data type
    """
    syntax_map = {
        'Integer32': 'Integer32',
        'INTEGER': 'Integer',
        'Unsigned32': 'Unsigned32',
        'Counter32': 'Counter32',
        'Counter64': 'Counter64',
        'Gauge32': 'Gauge32',
        'TimeTicks': 'TimeTicks',
        'IpAddress': 'IpAddress',
        'OCTET STRING': 'OctetString',
        'DisplayString': 'OctetString',
        'InterfaceIndex': 'Integer32',
        'RowPointer': 'OctetString',
        'ResourceId': 'OctetString',
    }
    
    return syntax_map.get(syntax, 'OctetString')
