"""
Upload API endpoints
"""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from backend.models.schemas import (
    ExtractArchiveResponse,
    SessionInfoResponse,
    UploadFilesResponse,
    UploadSessionResponse,
)
from backend.services.upload_service import UploadService
from services.config_service import Config
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize upload service
upload_service = UploadService()


@router.post("/session/create", response_model=UploadSessionResponse)
async def create_upload_session():
    """
    Create a new upload session

    Returns:
        Session ID and directory path
    """
    try:
        session_id = upload_service.create_session()
        session_dir = upload_service.get_session_dir(session_id)

        return UploadSessionResponse(
            success=True,
            session_id=session_id,
            session_path=str(session_dir),
            message="Upload session created",
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/upload", response_model=UploadFilesResponse)
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    """
    Upload files to session directory

    Args:
        session_id: Upload session ID
        files: List of files to upload

    Returns:
        Upload results for each file
    """
    try:
        # Verify session exists
        upload_service.get_session_dir(session_id)

        # Upload files
        results = await upload_service.upload_files(session_id, files)

        # Count successes and failures
        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count

        # Calculate total size
        total_size = sum(r.get("size", 0) for r in results if r["status"] == "success")

        return UploadFilesResponse(
            success=True,
            session_id=session_id,
            files_uploaded=success_count,
            files_failed=failed_count,
            total_size=total_size,
            files=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/extract", response_model=ExtractArchiveResponse)
async def extract_archive(session_id: str, archive_filename: str):
    """
    Extract archive in session directory

    Args:
        session_id: Upload session ID
        archive_filename: Name of archive file to extract

    Returns:
        Extraction results
    """
    try:
        session_dir = upload_service.get_session_dir(session_id)
        archive_path = session_dir / archive_filename

        if not archive_path.exists():
            raise HTTPException(status_code=404, detail=f"Archive not found: {archive_filename}")

        # Extract archive
        result = upload_service.extract_archive(session_id, archive_path)

        return ExtractArchiveResponse(
            success=result["success"],
            session_id=session_id,
            archive_filename=archive_filename,
            total_files=result["total_files"],
            supported_files=result["supported_files"],
            ignored_files=result["ignored_files"],
            extract_dir=result["extract_dir"],
            total_size=result["total_size"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Archive extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/files")
async def list_session_files(session_id: str):
    """
    List all supported files in session directory

    Args:
        session_id: Upload session ID

    Returns:
        List of supported files
    """
    try:
        files = upload_service.filter_supported_files(session_id)

        return {"success": True, "session_id": session_id, "file_count": len(files), "files": files}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List files failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/info", response_model=SessionInfoResponse)
async def get_session_info(session_id: str):
    """
    Get session information

    Args:
        session_id: Upload session ID

    Returns:
        Session information
    """
    try:
        info = upload_service.get_session_info(session_id)

        return SessionInfoResponse(success=True, **info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def cleanup_session(session_id: str, background_tasks: BackgroundTasks):
    """
    Cleanup session directory

    Args:
        session_id: Upload session ID
        background_tasks: FastAPI background tasks

    Returns:
        Cleanup status
    """
    try:
        # Schedule cleanup in background
        background_tasks.add_task(upload_service.cleanup_session, session_id)

        return {"success": True, "session_id": session_id, "message": "Session cleanup scheduled"}

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup/old-sessions")
async def cleanup_old_sessions(max_age_hours: Optional[int] = None, background_tasks: BackgroundTasks = None):
    """
    Cleanup old sessions (admin endpoint)

    Args:
        max_age_hours: Maximum age in hours
        background_tasks: FastAPI background tasks

    Returns:
        Number of sessions cleaned
    """
    try:
        if background_tasks:
            # Run in background
            background_tasks.add_task(upload_service.cleanup_old_sessions, max_age_hours)
            return {"success": True, "message": "Cleanup scheduled"}
        else:
            # Run immediately
            cleaned = upload_service.cleanup_old_sessions(max_age_hours)
            return {"success": True, "sessions_cleaned": cleaned}

    except Exception as e:
        logger.error(f"Cleanup old sessions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
