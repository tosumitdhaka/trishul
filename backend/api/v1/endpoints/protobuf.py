"""
Protobuf Decoder API Endpoints V2

Session-based workflow:
1. Upload .proto files to session (via upload service)
2. Compile schema: POST /compile-schema (session_id)
3. Upload .protobuf files to session (via upload service)
4. Decode: POST /decode (session_id, message_type)
5. Download: GET /download/{session_id}/{filename} or /download-batch/{session_id}
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Form
from fastapi.responses import FileResponse

from core.protobuf_decoder import ProtobufDecoderV2

from backend.models.schemas import (
    ProtobufDecodeResponse,
    ProtobufFileResult,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# HELPER: Get Upload Service
# ============================================

def get_upload_service(request: Request):
    """Get upload service from app state."""
    if hasattr(request.app.state, 'upload_service'):
        return request.app.state.upload_service
    
    # Fallback: create new instance
    from backend.services.upload_service import UploadService
    upload_service = UploadService()
    request.app.state.upload_service = upload_service
    return upload_service


# ============================================
# PHASE 1: COMPILE SCHEMA
# ============================================

@router.post("/compile-schema")
async def compile_schema(
    request: Request,
    session_id: str = Form(..., description="Upload session ID containing .proto files"),
):
    """
    Compile .proto schema files in session directory.
    
    Workflow:
    1. User uploads .proto files to session (via /upload endpoints)
    2. Call this endpoint to compile schema
    3. Returns available message types and auto-detected root
    
    Args:
        session_id: Upload session ID containing .proto files
    
    Returns:
        Compilation result with message types and dependency scores
    """
    try:
        upload_service = get_upload_service(request)
        
        # Get session directory
        try:
            session_dir = upload_service.get_session_dir(session_id)
        except HTTPException:
            raise HTTPException(404, f"Session not found: {session_id}")
        
        logger.info(f"📦 Compiling schema for session: {session_id}")
        
        # Check if .proto files exist
        proto_files = list(session_dir.glob("*.proto"))
        if not proto_files:
            raise HTTPException(400, "No .proto files found in session. Please upload .proto files first.")
        
        # Initialize decoder
        decoder = ProtobufDecoderV2(session_dir, verbose=False)
        
        # Compile schema
        result = decoder.compile_schema()
        
        if not result["success"]:
            logger.error(f"❌ Compilation failed: {result.get('error')}")
            raise HTTPException(400, result.get("error", "Compilation failed"))
        
        logger.info(f"✅ Compiled {len(result['message_types'])} message type(s)")
        
        return {
            "success": True,
            "session_id": session_id,
            "message": f"Compiled {len(result['proto_files'])} .proto file(s) successfully",
            "proto_files": result["proto_files"],
            "package": result.get("package", ""),
            "message_types": result["message_types"],
            "auto_detected_root": result["auto_detected_root"],
            "dependency_scores": result.get("dependency_scores", {}),
            "total_messages": len(result["message_types"]),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Compilation error: {e}", exc_info=True)
        raise HTTPException(500, f"Compilation failed: {str(e)}")


# ============================================
# PHASE 2: DECODE FILES
# ============================================

@router.post("/decode", response_model=ProtobufDecodeResponse)
async def decode_protobuf(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(..., description="Upload session ID"),
    message_type: str = Form(..., description="Root message type for decoding"),
    indent: int = Form(2, ge=0, le=8, description="JSON indentation"),
):
    """
    Decode binary protobuf files using compiled schema.
    
    Workflow:
    1. User uploads .protobuf files to session (via /upload endpoints)
    2. User compiles schema (via /compile-schema)
    3. Call this endpoint to decode binary files
    4. Download JSON results
    
    Args:
        session_id: Upload session ID
        message_type: Root message type (from compile-schema response)
        indent: JSON indentation
    
    Returns:
        Decode results with download URLs
    """
    try:
        config = request.app.state.config
        upload_service = get_upload_service(request)
        
        # Get session directory
        try:
            session_dir = upload_service.get_session_dir(session_id)
        except HTTPException:
            raise HTTPException(404, f"Session not found: {session_id}")
        
        logger.info(f"📦 Decoding protobuf files for session: {session_id}")
        
        # Initialize decoder
        decoder = ProtobufDecoderV2(session_dir, verbose=False)
        
        # Check if schema is compiled
        if not decoder.message_classes:
            # Try to compile
            compile_result = decoder.compile_schema()
            if not compile_result["success"]:
                raise HTTPException(
                    400,
                    "Schema not compiled. Please call /compile-schema first."
                )
        
        # Find binary files to decode
        binary_extensions = ['.protobuf', '.pb', '.bin', '.dat']
        files_to_decode = []
        
        for ext in binary_extensions:
            files_to_decode.extend([f.name for f in session_dir.glob(f"*{ext}")])
        
        # Also check files without extension
        for file_path in session_dir.iterdir():
            if file_path.is_file() and not file_path.suffix and file_path.name not in files_to_decode:
                # Check if it's not a .proto or _pb2.py file
                if not file_path.name.endswith('.proto') and not file_path.name.endswith('_pb2.py'):
                    files_to_decode.append(file_path.name)
        
        if not files_to_decode:
            raise HTTPException(404, "No binary protobuf files found in session. Please upload .protobuf files first.")
        
        logger.info(f"📄 Decoding {len(files_to_decode)} file(s) with message type: {message_type}")
        
        # Decode files
        decode_results = decoder.decode_files(
            binary_files=files_to_decode,
            message_type=message_type,
            output_dir=session_dir,
            indent=indent
        )
        
        # Build response
        results = []
        success_count = 0
        json_files = []
        
        for result in decode_results:
            if result["status"] == "success":
                success_count += 1
                json_files.append(result["output_filename"])
                
                # Generate download URL
                file_url = f"/api/v1/protobuf/download/{session_id}/{result['output_filename']}"
                
                results.append(ProtobufFileResult(
                    filename=result["filename"],
                    output_filename=result["output_filename"],
                    file_url=file_url,
                    file_size=result["file_size"],
                    status="success",
                    fields_decoded=result["fields_decoded"],
                ))
            else:
                results.append(ProtobufFileResult(
                    filename=result["filename"],
                    status="failed",
                    error=result.get("error"),
                ))
        
        failed_count = len(decode_results) - success_count
        
        logger.info(f"✅ Decoded {success_count}/{len(decode_results)} file(s)")
        
        # Create batch ZIP if multiple files
        batch_zip_url = None
        if success_count > 1:
            zip_path = decoder.create_batch_zip(json_files, "decoded_batch.zip")
            if zip_path:
                batch_zip_url = f"/api/v1/protobuf/download-batch/{session_id}"
        
        return ProtobufDecodeResponse(
            success=True,
            message=f"Decoded {success_count}/{len(decode_results)} file(s) successfully",
            proto_schema=f"{len(decoder.message_classes)} message type(s)",
            message_type=message_type,
            files_processed=len(decode_results),
            files_success=success_count,
            files_failed=failed_count,
            results=results,
            note=f"Session will be cleaned up after {config.upload.session_timeout_hours} hours. Batch download: {batch_zip_url or 'N/A'}",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Decode failed: {e}", exc_info=True)
        raise HTTPException(500, f"Decode failed: {str(e)}")


# ============================================
# DOWNLOAD ENDPOINTS
# ============================================

@router.get("/download/{session_id}/{filename}")
async def download_decoded_file(
    request: Request,
    session_id: str,
    filename: str,
):
    """
    Download decoded JSON file from session.
    
    Args:
        session_id: Upload session ID
        filename: JSON filename to download
    
    Returns:
        File download response
    """
    try:
        upload_service = get_upload_service(request)
        
        # Get session directory
        try:
            session_dir = upload_service.get_session_dir(session_id)
        except HTTPException:
            raise HTTPException(404, f"Session not found: {session_id}")
        
        file_path = session_dir / filename
        
        if not file_path.exists():
            raise HTTPException(404, f"File not found: {filename}")
        
        # Security: Ensure file is in session directory
        if not file_path.resolve().is_relative_to(session_dir.resolve()):
            raise HTTPException(403, "Access denied")
        
        logger.info(f"📥 Downloading: {filename} from session {session_id}")
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/json"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download failed: {e}", exc_info=True)
        raise HTTPException(500, f"Download failed: {str(e)}")


@router.get("/download-batch/{session_id}")
async def download_batch_zip(
    request: Request,
    session_id: str,
):
    """
    Download all decoded JSON files as a ZIP archive.
    
    Args:
        session_id: Upload session ID
    
    Returns:
        ZIP file download response
    """
    try:
        upload_service = get_upload_service(request)
        
        # Get session directory
        try:
            session_dir = upload_service.get_session_dir(session_id)
        except HTTPException:
            raise HTTPException(404, f"Session not found: {session_id}")
        
        zip_path = session_dir / "decoded_batch.zip"
        
        if not zip_path.exists():
            # Create ZIP on-the-fly
            json_files = [f.name for f in session_dir.glob("*.json")]
            
            if not json_files:
                raise HTTPException(404, "No decoded JSON files found in session")
            
            decoder = ProtobufDecoderV2(session_dir, verbose=False)
            zip_path = decoder.create_batch_zip(json_files, "decoded_batch.zip")
            
            if not zip_path:
                raise HTTPException(500, "Failed to create batch ZIP")
        
        logger.info(f"📥 Downloading batch ZIP from session {session_id}")
        
        return FileResponse(
            path=str(zip_path),
            filename=f"protobuf_decoded_{session_id[:8]}.zip",
            media_type="application/zip"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Batch download failed: {e}", exc_info=True)
        raise HTTPException(500, f"Batch download failed: {str(e)}")


# ============================================
# INFO & VALIDATION ENDPOINTS
# ============================================

@router.get("/schema-info/{session_id}")
async def get_schema_info(
    request: Request,
    session_id: str,
):
    """
    Get detailed schema information for compiled session.
    
    Args:
        session_id: Upload session ID
    
    Returns:
        Detailed schema information
    """
    try:
        upload_service = get_upload_service(request)
        
        # Get session directory
        try:
            session_dir = upload_service.get_session_dir(session_id)
        except HTTPException:
            raise HTTPException(404, f"Session not found: {session_id}")
        
        # Initialize decoder
        decoder = ProtobufDecoderV2(session_dir, verbose=False)
        
        # Get schema info
        info = decoder.get_schema_info()
        
        if not info.get("compiled"):
            raise HTTPException(400, "Schema not compiled for this session. Please call /compile-schema first.")
        
        return {
            "success": True,
            "session_id": session_id,
            **info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get schema info: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get schema info: {str(e)}")


@router.post("/validate-schema")
async def validate_schema(
    request: Request,
    session_id: str = Form(..., description="Upload session ID containing .proto files"),
):
    """
    Validate .proto schema files in session (alias for compile-schema).
    
    Args:
        session_id: Upload session ID containing .proto files
    
    Returns:
        Validation result (same as compile-schema)
    """
    # Validation is the same as compilation
    return await compile_schema(request, session_id)
