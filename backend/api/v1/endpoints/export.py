
"""
Export API Endpoints - Refactored with ExportService
Handles data export from database tables to various formats
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request
from fastapi.responses import FileResponse

# ✅ NEW: Import ExportService
from backend.services.export_service import ExportService
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# EXPORT ENDPOINTS
# ============================================

@router.post("/table")
async def export_table(
    request: Request,
    background_tasks: BackgroundTasks,
    table: str = Body(..., description="Table name to export"),
    database: str = Body("data", description="Database: 'data' or 'jobs'"),
    format: str = Body("json", description="Export format"),
    filename: Optional[str] = Body(None, description="Custom filename (without extension)"),
    columns: Optional[List[str]] = Body(None, description="Columns to export"),
    limit: Optional[int] = Body(None, description="Maximum records to export"),
    compress: bool = Body(False, description="Compress as ZIP"),
    compression: Optional[str] = Body(None),
):
    """
    Export table data with database parameter.
    
    Supports exporting from:
    - 'data' database (user tables)
    - 'jobs' database (job result tables)
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # ✅ NEW: Initialize ExportService
        export_service = ExportService(config)
        
        logger.info(f"📊 Exporting table '{table}' from '{database}' to {format}")
        
        # Validate database parameter
        if database not in ["data", "jobs"]:
            raise HTTPException(400, f"Invalid database: {database}. Must be 'data' or 'jobs'")
        
        # Check if table exists
        if not db.table_exists(table, database=database):
            raise HTTPException(404, f"Table '{table}' not found in '{database}' database")
        
        # Load data from specified database
        df = db.db_to_df(
            table=table,
            database=database,
            columns=columns,
            limit=limit,
        )
        
        if df.empty:
            raise HTTPException(404, "No data to export")
        
        logger.info(f"✅ Loaded {len(df)} rows from {database}.{table}")
        
        # ✅ NEW: Export using ExportService
        result = await export_service.export_dataframe(
            df=df,
            base_name=filename,
            format=format,
            compress=compress,
            compression=compression
        )
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_export_file, str(result["output_path"]), delay=3600)
        
        return {
            "success": True,
            "table": table,
            "database": database,
            "records_exported": len(df),
            "format": format,
            "file_url": f"/api/v1/export/download/{result['filename']}",
            "filename": result["filename"],
            "file_size": result["file_size"],
            "compressed": compress,
            "compression": compression,
            "message": "File will be automatically deleted after 1 hour",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Export failed: {e}", exc_info=True)
        raise HTTPException(500, f"Export failed: {str(e)}")


@router.post("/job/{job_id}")
async def export_job_result(
    request: Request,
    background_tasks: BackgroundTasks,
    job_id: str,
    format: str = Body("csv", description="Export format"),
    filename: Optional[str] = Body(None, description="Custom filename (without extension)"),
    columns: Optional[List[str]] = Body(None, description="Columns to export"),
    limit: Optional[int] = Body(None, description="Maximum records to export"),
    compress: bool = Body(False, description="Compress as ZIP"),
    compression: Optional[str] = Body(None),
):
    """
    Export job result data from jobs database.
    
    Reads table name from job metadata - no conversion needed.
    Handles job ID with hyphens correctly.
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # ✅ NEW: Initialize ExportService
        export_service = ExportService(config)
        
        logger.info(f"📊 Exporting job '{job_id}'")
        
        # Get job metadata
        job_metadata = db.get_job_metadata(job_id, include_data=False)
        
        if not job_metadata:
            logger.error(f"❌ Job not found: {job_id}")
            raise HTTPException(404, f"Job not found: {job_id}")
        
        # Get table name from metadata
        result_data = job_metadata.get("result", {})
        table_name = result_data.get("table_name")
        
        if not table_name:
            # Fallback: construct table name from job_id
            logger.warning(f"⚠️ No table_name in job metadata for {job_id}")
            table_job_id = job_id.replace("-", "_")
            table_name = f"job_{table_job_id}_data"
            logger.info(f"Constructed table name: {table_name}")
        else:
            logger.info(f"📋 Using table name from metadata: {table_name}")
        
        # Verify table exists in jobs database
        if not db.table_exists(table_name, database="jobs"):
            logger.error(f"❌ Table not found in jobs database: {table_name}")
            raise HTTPException(404, f"Job data table not found: {table_name}")
        
        logger.info(f"✅ Table exists: {table_name}")
        
        # Load data from jobs database
        df = db.db_to_df(table=table_name, database="jobs", columns=columns, limit=limit)
        
        if df.empty:
            raise HTTPException(404, "No data in job result")
        
        logger.info(f"✅ Loaded {len(df)} rows from job result")
        
        if filename:
            base_name = filename
        else:
            base_name = f"job_{job_id}"

        # ✅ NEW: Export using ExportService
        result = await export_service.export_dataframe(
            df=df,
            base_name=base_name,
            format=format,
            compress=compress,
            compression=compression,
        )
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_export_file, str(result["output_path"]), delay=3600)
        
        logger.info(f"✅ Job export complete: {result['filename']}")
        
        return {
            "success": True,
            "job_id": job_id,
            "table_name": table_name,
            "records_exported": len(df),
            "format": format,
            "file_url": f"/api/v1/export/download/{result['filename']}",
            "filename": result["filename"],
            "file_size": result["file_size"],
            "compressed": compress,
            "compression": compression,
            "message": "File will be automatically deleted after 1 hour",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Job export failed: {e}", exc_info=True)
        raise HTTPException(500, f"Export failed: {str(e)}")

@router.post("/query")
async def export_query_results(
    request: Request,
    background_tasks: BackgroundTasks,
    data: List[Dict[str, Any]] = Body(..., description="Query result data"),
    format: str = Body("csv", description="Export format"),
    filename: Optional[str] = Body(None, description="Custom filename"),
    compress: bool = Body(False, description="Compress as ZIP"),
    compression: Optional[str] = Body(None),
):
    """
    Export query results directly from data array.
    """
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # ✅ NEW: Initialize ExportService
        export_service = ExportService(config)

        logger.info(f"📊 Exporting query results: {len(data)} rows to {format}")

        if not data or len(data) == 0:
            raise HTTPException(status_code=400, detail="No data to export")

        # Convert to DataFrame
        df = pd.DataFrame(data)

        if df.empty:
            raise HTTPException(404, "No data to export")
        
        logger.info(f"✅ Loaded {len(df)} rows")

        result = await export_service.export_dataframe(
            df=df,
            base_name=filename,
            format=format,
            compress=compress,
            compression=compression
        )

        # Schedule cleanup
        background_tasks.add_task(cleanup_export_file, str(result["output_path"]), delay=3600)

        return {
            "success": True,
            "records_exported": len(df),
            "format": format,
            "file_url": f"/api/v1/export/download/{result['filename']}",
            "filename": result["filename"],
            "file_size": result["file_size"],
            "compressed": compress,
            "compression": compression,
            "message": "File will be automatically deleted after 1 hour",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Query export failed: {e}", exc_info=True)
        raise HTTPException(500, f"Export failed: {str(e)}")

@router.get("/formats")
async def get_export_formats(request: Request):
    """Get supported export formats from FileManager."""
    
    # ✅ Get formats from FileManager
    from core.file_manager import FileManager
    supported_formats = FileManager.SUPPORTED_FORMATS
    
    # Format metadata
    format_info = {
        "csv": {
            "id": "csv",
            "name": "CSV",
            "icon": "📊",
            "description": "Comma-Separated Values",
            "extension": ".csv",
            "mime_type": "text/csv",
        },
        "tsv": {
            "id": "tsv",
            "name": "TSV",
            "icon": "📊",
            "description": "Tab-Separated Values",
            "extension": ".tsv",
            "mime_type": "text/tab-separated-values",
        },
        "json": {
            "id": "json",
            "name": "JSON",
            "icon": "📄",
            "description": "JavaScript Object Notation",
            "extension": ".json",
            "mime_type": "application/json",
        },
        "jsonl": {
            "id": "jsonl",
            "name": "JSON Lines",
            "icon": "📄",
            "description": "Newline-delimited JSON",
            "extension": ".jsonl",
            "mime_type": "application/x-ndjson",
        },
        "yaml": {
            "id": "yaml",
            "name": "YAML",
            "icon": "📝",
            "description": "YAML Ain't Markup Language",
            "extension": ".yaml",
            "mime_type": "text/yaml",
        },
        "excel": {
            "id": "excel",
            "name": "Excel",
            "icon": "📋",
            "description": "Microsoft Excel Spreadsheet",
            "extension": ".xlsx",
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        "parquet": {
            "id": "parquet",
            "name": "Parquet",
            "icon": "🗄️",
            "description": "Apache Parquet (Columnar)",
            "extension": ".parquet",
            "mime_type": "application/octet-stream",
        },
        "html": {
            "id": "html",
            "name": "HTML",
            "icon": "🌐",
            "description": "HTML Report",
            "extension": ".html",
            "mime_type": "text/html",
        },
        "xml": {
            "id": "xml",
            "name": "XML",
            "icon": "📋",
            "description": "Extensible Markup Language",
            "extension": ".xml",
            "mime_type": "application/xml",
        },
    }
    
    # ✅ Return only supported formats
    return {
        "success": True,
        "formats": [format_info[fmt] for fmt in supported_formats if fmt in format_info]
    }

@router.get("/compressions")
async def get_export_compressions():
    """Get supported compression types."""
    from core.file_manager import FileManager
    
    compressions = FileManager.get_supported_compressions()
    
    compression_info = {
        "gzip": {
            "id": "gzip",
            "name": "GZIP",
            "icon": "⚡",
            "extension": ".gz",
            "description": "GNU Zip compression"
        },
        "zip": {
            "id": "zip",
            "name": "ZIP",
            "icon": "📦",
            "extension": ".zip",
            "description": "ZIP archive"
        },
        "bz2": {
            "id": "bz2",
            "name": "BZ2",
            "icon": "📚",
            "extension": ".bz2",
            "description": "Bzip2 compression"
        },
        "xz": {
            "id": "xz",
            "name": "XZ",
            "icon": "🔒",
            "extension": ".xz",
            "description": "XZ compression"
        },
    }
    
    return {
        "success": True,
        "compressions": [compression_info[c] for c in compressions if c in compression_info]
    }


@router.get("/download/{filename}")
async def download_file(request: Request, filename: str, background_tasks: BackgroundTasks):
    """
    Download exported file with auto-cleanup after download.
    """
    try:
        config = request.app.state.config
        file_path = Path(config.export.export_dir).resolve() / filename
        
        if not file_path.exists():
            raise HTTPException(404, "File not found or already deleted")
        
        # Security: Ensure file is in export directory
        export_dir = Path(config.export.export_dir).resolve()
        if not file_path.resolve().is_relative_to(export_dir):
            raise HTTPException(403, "Access denied")
        
        # Schedule cleanup after download (60 seconds)
        background_tasks.add_task(cleanup_export_file, str(file_path), delay=60)
        
        logger.info(f"📥 Downloading: {filename}")
        
        return FileResponse(
            path=str(file_path), filename=filename, media_type="application/octet-stream"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download failed: {e}", exc_info=True)
        raise HTTPException(500, f"Download failed: {str(e)}")


# ============================================
# HELPER FUNCTIONS
# ============================================

async def cleanup_export_file(filepath: str, delay: int = 0):
    """
    Cleanup export file after delay.
    """
    if delay > 0:
        await asyncio.sleep(delay)
    
    try:
        file_path = Path(filepath)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"🧹 Cleaned up export file: {file_path.name}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to cleanup file {filepath}: {str(e)}")