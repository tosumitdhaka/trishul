"""
Jobs API Endpoints - Job Management
Handles job metadata (system DB) and job data (jobs DB)
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

# ✅ NEW: Import WebSocket manager
from backend.config.websocket import manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# JOB LISTING & INFO
# ============================================


@router.get("/")
async def list_jobs(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List all jobs with optional filtering.

    Args:
        status: Filter by status ('queued', 'running', 'completed', 'failed')
        job_type: Filter by job type ('parse', 'export', etc.)
        limit: Maximum jobs to return
        offset: Offset for pagination

    Returns:
        List of jobs with metadata
    """
    try:
        db = request.app.state.db_manager

        jobs = db.list_jobs(limit=limit, offset=offset, status=status, job_type=job_type)

        logger.info(f"Listed {len(jobs)} jobs (status={status}, type={job_type})")

        return {"success": True, "jobs": jobs, "total": len(jobs), "limit": limit, "offset": offset}

    except Exception as e:
        logger.error(f"List jobs failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/{job_id}")
async def get_job(
    request: Request,
    job_id: str,
    include_data: bool = Query(False, description="Include result data"),
):
    """
    Get job metadata by ID.

    Args:
        job_id: Job ID
        include_data: Whether to include result_data field

    Returns:
        Job metadata
    """
    try:
        db = request.app.state.db_manager

        job = db.get_job_metadata(job_id, include_data=include_data)

        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        logger.debug(f"Retrieved job {job_id}")

        return {"success": True, "job": job}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")


# ============================================
# JOB DATA RETRIEVAL
# ============================================


@router.get("/{job_id}/data")
async def get_job_data(
    request: Request,
    job_id: str,
    limit: int = Query(1000, ge=1, le=10000, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Get job result data.

    Args:
        job_id: Job ID
        limit: Maximum records to return
        offset: Offset for pagination

    Returns:
        Job result data
    """
    try:
        db = request.app.state.db_manager

        # Check if job exists
        job = db.get_job_metadata(job_id, include_data=True)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Check if job has data
        result = job.get("result", {})
        if not result.get("has_data", False):
            return {
                "success": True,
                "data": [],
                "total": 0,
                "returned": 0,
                "message": "Job has no data",
            }

        # Get data from jobs database
        df = db.get_job_result(job_id, limit=limit, offset=offset)

        # Get total count
        table_name = f"job_{job_id}_data"
        total_count = db.get_table_row_count(table_name, database="jobs")

        logger.info(f"Retrieved {len(df)} records from job {job_id}")

        return {
            "success": True,
            "data": df.to_dict("records"),
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "returned": len(df),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get job data failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job data: {str(e)}")


# ============================================
# JOB DATA OPERATIONS
# ============================================


@router.post("/{job_id}/save-to-database")
async def save_job_to_database(
    request: Request, job_id: str, table_name: str = Body(..., embed=True)
):
    """
    Save job result data to user database (mib_tool).

    This copies data from temporary jobs database to permanent user database.

    Args:
        job_id: Job ID
        table_name: Target table name in user database

    Returns:
        Save result
    """
    try:
        db = request.app.state.db_manager

        # Check if job exists
        job = db.get_job_metadata(job_id, include_data=True)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Check if job has data
        result = job.get("result", {})
        if not result.get("has_data", False):
            raise HTTPException(status_code=400, detail="Job has no data to save")

        logger.info(f"Saving job {job_id} data to user database table '{table_name}'")

        # Copy data from jobs DB to user DB
        success = db.copy_job_to_user_db(job_id, table_name)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save data to database")

        logger.info(f"✅ Saved job {job_id} data to {table_name}")

        return {
            "success": True,
            "message": f"Job data saved to table '{table_name}'",
            "table_name": table_name,
            "records": result.get("records_parsed", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save job to database failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


# ============================================
# JOB DELETION
# ============================================


@router.delete("/{job_id}")
async def delete_job(
    request: Request,
    job_id: str,
    delete_data: bool = Query(True, description="Also delete job data table"),
):
    """
    Delete job (metadata and optionally data).

    Args:
        job_id: Job ID
        delete_data: Whether to also delete the data table

    Returns:
        Deletion result
    """
    try:
        db = request.app.state.db_manager

        # Check if job exists
        job = db.get_job_metadata(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        logger.info(f"Deleting job {job_id} (delete_data={delete_data})")

        # Delete job (metadata + data)
        success = db.delete_job_complete(job_id, delete_data=delete_data)

        if not success:
            raise HTTPException(status_code=500, detail="Delete failed")

        logger.info(f"✅ Deleted job {job_id}")

        return {"success": True, "message": f"Job '{job_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete job failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


# ============================================
# WEBSOCKET ENDPOINT (NEW)
# ============================================


@router.websocket("/ws/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job progress updates.

    Client connects to: ws://localhost:8000/api/v1/jobs/ws/{job_id}

    Protocol:
    - Client → Server: "ping" (keepalive)
    - Server → Client: "pong" (keepalive response)
    - Server → Client: JSON progress updates

    Progress message format:
    {
        "topic": "job:{job_id}",
        "data": {
            "job_id": "...",
            "phase": "parsing",
            "current": 5,
            "total": 10,
            "percentage": 50.0,
            "message": "Parsing file 5 of 10...",
            "metadata": {...}
        }
    }

    Args:
        websocket: WebSocket connection
        job_id: Job ID to subscribe to
    """
    await manager.connect(websocket)
    manager.subscribe(f"job:{job_id}", websocket)

    logger.info(f"WebSocket connected for job {job_id}")

    try:
        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_text()

            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
                logger.debug(f"WebSocket ping/pong for job {job_id}")

            # Handle other commands (future: cancel, pause, etc.)
            elif data.startswith("cancel"):
                logger.info(f"Cancel requested for job {job_id}")
                # TODO: Implement cancellation
                await websocket.send_text('{"status": "cancel_not_implemented"}')

            else:
                logger.debug(f"Unknown WebSocket message for job {job_id}: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
        manager.disconnect(websocket)


# ============================================
# JOB CLEANUP (NEW)
# ============================================


@router.post("/cleanup")
async def cleanup_jobs(request: Request, dry_run: bool = False):
    """
    Manually trigger job cleanup.

    Args:
        dry_run: If true, only preview what would be deleted

    Returns:
        Cleanup statistics
    """
    try:
        from backend.services.cleanup_service import cleanup_service

        logger.info(f"Manual cleanup triggered (dry_run={dry_run})")

        stats = await cleanup_service.cleanup_old_jobs(dry_run=dry_run)

        return {
            "success": True,
            "dry_run": dry_run,
            "statistics": stats,
            "message": f"{'Preview: ' if dry_run else ''}{stats['deleted']} jobs {'would be' if dry_run else ''} deleted",
        }

    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/cleanup/preview")
async def preview_cleanup(request: Request):
    """
    Preview what would be deleted by cleanup without actually deleting.

    Returns:
        Preview statistics
    """
    try:
        from backend.services.cleanup_service import cleanup_service

        stats = await cleanup_service.get_cleanup_preview()

        return {
            "success": True,
            "statistics": stats,
            "message": f"{stats['eligible_for_deletion']} jobs would be deleted",
        }

    except Exception as e:
        logger.error(f"Cleanup preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


# ============================================
# JOB CANCELLATION (NEW)
# ============================================


@router.post("/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str):
    """
    Cancel a queued job.
    
    Only queued jobs can be cancelled. Running jobs cannot be cancelled.
    Cancellation will:
    - Delete the session directory (uploaded files)
    - Delete the job record from database
    
    Args:
        job_id: Job ID to cancel
    
    Returns:
        Cancellation confirmation
    """
    try:
        db = request.app.state.db_manager
        
        # Check if job exists
        job = db.get_job_metadata(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        status = job["status"]
        
        # Only allow cancellation of queued jobs
        if status != "queued":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status '{status}'. Only queued jobs can be cancelled."
            )
        
        logger.info(f"🚫 Cancelling queued job {job_id}")
        
        # Get session info
        session_id = job.get("session_id")
        
        # 1. Delete session directory (uploaded files)
        if session_id:
            from pathlib import Path
            import shutil
            
            session_dir = Path(f"uploads/{session_id}")
            if session_dir.exists():
                try:
                    shutil.rmtree(session_dir)
                    logger.info(f"🗑️ Deleted session directory: {session_dir}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete session directory: {e}")
        
        # 2. Delete job record from database
        try:
            success = db.delete_job_complete(job_id=job_id, delete_data=False)
        
            if success:
                logger.info(f"🗑️ Deleted job record: {job_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to delete job record: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete job record")
        
        logger.info(f"✅ Queued job {job_id} cancelled successfully")
        
        return {
            "success": success,
            "message": "Queued job cancelled and removed",
            "job_id": job_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel job failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


# ============================================
# JOB RETRY (NEW)
# ============================================


@router.post("/{job_id}/retry")
async def retry_job(request: Request, job_id: str):
    """
    Retry a failed or cancelled job with the same parameters.

    Args:
        job_id: Job ID to retry

    Returns:
        New job information
    """
    try:
        db = request.app.state.db_manager

        # Get original job
        job = db.get_job_metadata(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Check if job can be retried
        if job["status"] not in ["failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry job with status '{job['status']}'. Only failed or cancelled jobs can be retried.",
            )

        logger.info(f"Retry requested for job {job_id}")

        # Get original parameters from metadata
        metadata = job.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        session_id = metadata.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=400, detail="Cannot retry: original session information not found"
            )

        # Check if session files still exist
        from backend.services.upload_service import UploadService

        upload_service = UploadService()
        session_dir = upload_service.get_session_dir(session_id)

        if not session_dir or not session_dir.exists():
            raise HTTPException(
                status_code=400,
                detail="Cannot retry: original files are no longer available. Please re-upload the files.",
            )

        # Check if session has files
        mib_files = list(session_dir.glob("*.mib"))
        if not mib_files:
            raise HTTPException(
                status_code=400, detail="Cannot retry: no MIB files found in original session"
            )

        logger.info(f"Retrying job {job_id} with session {session_id} ({len(mib_files)} files)")

        # Get original settings
        deduplicate = metadata.get("deduplicate", True)
        dedup_strategy = metadata.get("dedup_strategy", "smart")
        original_job_name = job.get("job_name", "")

        # Create new job name
        retry_count = metadata.get("retry_count", 0) + 1
        new_job_name = (
            f"{original_job_name} (Retry #{retry_count})"
            if original_job_name
            else f"Retry of {job_id[:8]}"
        )

        # Create new job
        new_job_id = str(uuid.uuid4())

        # Save new job metadata
        new_metadata = {
            "session_id": session_id,
            "deduplicate": deduplicate,
            "dedup_strategy": dedup_strategy,
            "retry_count": retry_count,
            "original_job_id": job_id,
            "retried_at": datetime.now().isoformat(),
        }

        success = db.save_job_metadata(
            {
                "job_id": new_job_id,
                "job_type": "parse_session",
                "job_name": new_job_name,
                "status": "queued",
                "created_at": datetime.now(),
                "progress": 0,
                "message": "Job queued for retry...",
                "metadata": new_metadata,
            }
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to create retry job")

        # Start background task
        from backend.api.v1.endpoints.parser import parse_session_job_async

        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            parse_session_job_async,
            new_job_id,
            str(session_dir),
            deduplicate,
            dedup_strategy,
            request.app.state.config,
            db,
            request.app.state.ws_manager,
            asyncio.get_event_loop(),
        )

        # Execute background task
        await background_tasks()

        logger.info(f"✅ Retry job {new_job_id} started for original job {job_id}")

        return {
            "success": True,
            "job_id": new_job_id,
            "original_job_id": job_id,
            "message": f"Job retry started: {new_job_name}",
            "retry_count": retry_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry job failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")
