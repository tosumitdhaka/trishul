"""
Parser API endpoints - Optimized
"""

import asyncio  # ✅ NEW: Import asyncio
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile

from backend.models.schemas import (
    ParseDirectoryRequest,
    ParseDirectoryResponse,
    ParseResponse,
    ParseTextRequest,
)
from backend.services.upload_service import UploadService
from backend.services.phase_timer import PhaseTimer
from backend.services.job_service import JobService, JobCancelledException
from core.deduplicator import DeduplicationService
from core.parser import MibParser
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ✅ NEW: Custom exception for job cancellation
class JobCancelledException(Exception):
    """Exception raised when a job is cancelled by user"""

    pass
"""
@router.post("/parse/file", response_model=ParseResponse)
async def parse_file(
    request: Request,
    file: UploadFile = File(...),
    deduplicate: bool = True,
    dedup_strategy: str = "smart",
):
    "Parse uploaded MIB file (inline processing for single file)"

    start_time = datetime.now()
    config = request.app.state.config

    temp_file = None
    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mib") as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_file = tmp.name

        # Parse file
        parser = MibParser(config)
        df = parser.parse_file(temp_file)

        if df.empty:
            raise HTTPException(status_code=400, detail="No data parsed from file")

        duplicates_removed = 0

        # Apply deduplication if requested
        if deduplicate:
            dedup_service = DeduplicationService()
            original_count = len(df)
            df = dedup_service.deduplicate(df, strategy=dedup_strategy)
            duplicates_removed = original_count - len(df)

        duration = (datetime.now() - start_time).total_seconds()

        return ParseResponse(
            success=True,
            records_parsed=len(df),
            duplicates_removed=duplicates_removed,
            duration=duration,
            data=df.to_dict("records"),
        )

    except Exception as e:
        logger.error(f"Parse file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()
"""

@router.post("/parse/text", response_model=ParseResponse)
async def parse_text(request: Request, body: ParseTextRequest):
    """
    Parse MIB text content (inline processing)
    """
    start_time = datetime.now()
    config = request.app.state.config

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".mib") as tmp:
            tmp.write(body.content)
            temp_file = tmp.name

        # Parse file
        parser = MibParser(config)
        df = parser.parse_file(temp_file)

        if df.empty:
            raise HTTPException(status_code=400, detail="No data parsed from text")

        duplicates_removed = 0

        # Apply deduplication if requested
        if body.deduplicate:
            dedup_service = DeduplicationService()
            original_count = len(df)
            df = dedup_service.deduplicate(df)
            duplicates_removed = original_count - len(df)

        duration = (datetime.now() - start_time).total_seconds()

        return ParseResponse(
            success=True,
            records_parsed=len(df),
            duplicates_removed=duplicates_removed,
            duration=duration,
            data=df.to_dict("records"),
        )

    except Exception as e:
        logger.error(f"Parse text failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()


@router.get("/parse/formats")
async def get_supported_formats():
    """Get supported file formats"""
    return {
        "input_formats": ["mib", "txt", "my", ""],
        "output_formats": ["json", "csv", "excel", "parquet", "yaml"],
    }

@router.post("/parse/session", response_model=ParseDirectoryResponse)
async def parse_session_directory(
    request: Request, body: ParseDirectoryRequest, background_tasks: BackgroundTasks
):
    """
    Parse all files in a session directory (always background job)
    """
    config = request.app.state.config
    db_manager = getattr(request.app.state, "db_manager", None)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    upload_service = UploadService()
    
    # ✅ NEW: Initialize JobService
    job_service = JobService(db_manager, ws_manager, config)
    
    try:
        # Get session directory
        session_dir = upload_service.get_session_dir(body.session_id)
        
        if not session_dir.exists():
            raise HTTPException(404, f"Session not found: {body.session_id}")
        
        # Get list of supported files
        files = upload_service.filter_supported_files(body.session_id)
        
        if not files:
            raise HTTPException(400, "No supported MIB files found in session")
        
        # Calculate total size
        total_size = sum(f["size"] for f in files)
        
        logger.info(f"Parsing session {body.session_id}: {len(files)} files, {total_size} bytes")
        
        # Generate job name
        job_name = generate_job_name(files, body.job_name)
        logger.info(f"Generated job name: {job_name}")
        
        # ✅ NEW: Create job using JobService
        job_id = job_service.create_job(
            job_type="parse",
            job_name=job_name,
            metadata={
                "session_id": body.session_id,
                "session_dir": str(session_dir),
                "file_count": len(files),
                "total_size": total_size,
                "deduplicate": body.deduplicate,
                "dedup_strategy": body.dedup_strategy,
                "force_compile": body.force_compile,
            }
        )
        
        logger.info(f"Created job {job_id}: {job_name}")
        
        # Get event loop reference
        loop = asyncio.get_event_loop()
        
        # Add async background task
        background_tasks.add_task(
            parse_session_job_async,
            job_id,
            str(session_dir),
            body.deduplicate,
            body.dedup_strategy,
            body.force_compile,
            config,
            job_service,  # ✅ CHANGED: Pass JobService instead of db_manager + ws_manager
            loop,
        )
        
        return ParseDirectoryResponse(
            success=True,
            session_id=body.session_id,
            records_parsed=0,
            files_processed=0,
            files_failed=0,
            duplicates_removed=0,
            duration=0,
            data=None,
            job_id=job_id,
            message=f"Processing {len(files)} files in background...",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parse session failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ============================================
# ✅ REFACTORED: ASYNC BACKGROUND JOB FUNCTION
# ============================================

async def parse_session_job_async(
    job_id: str,
    session_dir: str,
    deduplicate: bool,
    dedup_strategy: str,
    force_compile: bool,
    config,
    job_service: JobService,
    loop,
):
    """
    Background job for parsing session directory - REFACTORED with JobService
    
    Args:
        job_id: Job ID
        session_dir: Session directory path
        deduplicate: Enable deduplication
        dedup_strategy: Deduplication strategy
        force_compile: Force recompilation
        config: Application config
        job_service: JobService instance (handles DB + WebSocket)
        loop: Event loop reference for WebSocket publishing
    """
    from backend.services.upload_service import UploadService
    from core.parser import MibParser
    

    from backend.services.metrics_service import get_metrics_service
    
    metrics = get_metrics_service()

    # Initialize phase timer
    phase_timer = PhaseTimer()
    
    try:

        # ============================================
        # PHASE 0: Concurrency Check (NEW)
        # ============================================
        
        # Get concurrency limit from config
        max_concurrent = getattr(config.jobs, 'concurrency', 2)
        
        logger.info(f"Job {job_id}: Checking concurrency (limit: {max_concurrent})")
        
        # Wait if at concurrency limit
        wait_count = 0
        while True:
            running_count = job_service.db.count_running_jobs()
            
            if running_count < max_concurrent:
                logger.info(f"Job {job_id}: Concurrency check passed ({running_count}/{max_concurrent})")
                break
            
            # Still at limit, wait
            wait_count += 1
            
            if wait_count == 1:
                # First wait - update job status
                logger.info(f"Job {job_id}: Waiting in queue ({running_count}/{max_concurrent} running)")
                await job_service.update_progress(
                    job_id,
                    0,
                    f"Waiting in queue ({running_count}/{max_concurrent} jobs running)...",
                    phase='queued'
                )
            elif wait_count % 6 == 0:  # Log every 30 seconds (6 * 5s)
                logger.info(f"Job {job_id}: Still waiting ({wait_count * 5}s elapsed, {running_count} jobs running)")
                await job_service.update_progress(
                    job_id,
                    0,
                    f"Waiting in queue ({running_count}/{max_concurrent} jobs running)... ({wait_count * 5}s)",
                    phase='queued'
                )
                
            # ✅ Check if job was cancelled while waiting
            job_service.check_cancellation(job_id)

            # Check every 5 seconds
            await asyncio.sleep(5)
        
        # ============================================
        # PHASE 1: Initializing
        # ============================================
        phase_timer.start_phase('initializing')

        await job_service.update_progress(
            job_id,
            0,
            f"Queue cleared, Starting job...)",
            phase='running'
        )
        
        # ✅ NEW: Use JobService to start job
        await job_service.start_job(job_id)
        
        logger.info(f"Job {job_id}: Starting parse of {session_dir}")
        
        # ============================================
        # Define progress callback (SIMPLIFIED)
        # ============================================
        def on_progress(progress_update):
            """Progress callback from parser with ETA calculation"""
            try:
                # ✅ NEW: Check cancellation using JobService
                job_service.check_cancellation(job_id)
                
                # Skip if somehow > 90% (parser caps at 90%)
                if progress_update.percentage > 90:
                    logger.debug(f"Job {job_id}: Skipping {progress_update.percentage}% from parser (>90%)")
                    return
                
                # Map parser phase to our phase names
                phase_mapping = {
                    'scanning': 'scanning',
                    'compiling': 'compiling',
                    'parsing': 'parsing',
                    'enriching': 'enriching',
                    'deduplicating': 'deduplicating',
                    'complete': 'deduplicating',
                }
                
                current_phase = phase_mapping.get(progress_update.phase, progress_update.phase)
                
                # Update phase timer
                if phase_timer.current_phase != current_phase:
                    phase_timer.start_phase(current_phase)
                
                # Calculate ETA
                eta_seconds = phase_timer.calculate_eta(current_phase, progress_update.percentage)
                
                # ✅ NEW: Update progress using JobService (handles DB + WebSocket)
                asyncio.run_coroutine_threadsafe(
                    job_service.update_progress(
                        job_id,
                        int(progress_update.percentage),
                        progress_update.message,
                        phase=current_phase,
                        eta_seconds=eta_seconds,
                        metadata=progress_update.metadata
                    ),
                    loop
                )
                
                logger.debug(
                    f"Job {job_id}: {progress_update.percentage:.1f}% - {progress_update.message}"
                    + (f" (ETA: {eta_seconds:.0f}s)" if eta_seconds else "")
                )
            
            except JobCancelledException:
                logger.info(f"Job {job_id}: Raising cancellation")
                raise
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        
        # ============================================
        # PHASE 2: Parsing (handled by parser's progress callback)
        # ============================================
        parser = MibParser(config)
        
        # Override deduplication settings
        original_dedup = config.parser.deduplication_enabled
        original_strategy = config.parser.deduplication_strategy
        original_force_compile = config.parser.force_compile
        
        config.parser.deduplication_enabled = deduplicate
        config.parser.deduplication_strategy = dedup_strategy
        config.parser.force_compile = force_compile
        
        parse_start_time = time.time()
        
        try:
            # Run parser in thread pool
            df = await asyncio.to_thread(
                parser.parse_directory,
                session_dir,
                pattern="*.mib",
                recursive=False,
                progress_callback=on_progress,
            )
        finally:
            # Restore original settings
            config.parser.deduplication_enabled = original_dedup
            config.parser.deduplication_strategy = original_strategy
            config.parser.force_compile = original_force_compile

            parser.clear_caches()  # ✅ Always cleanup
        
        parse_time = time.time() - parse_start_time
        logger.info(f"Job {job_id}: Parser completed, finalizing...")
        
        # ============================================
        # PHASE 3: Saving (90% → 95%)
        # ============================================
        phase_timer.start_phase('saving')
        
        # ✅ NEW: Use JobService for progress updates
        await job_service.update_progress(
            job_id, 90, "Saving results to database...", phase="saving"
        )
        
        # Validate results
        files_processed = parser.stats.get("files_processed", 0)
        files_failed = parser.stats.get("files_failed", 0)
        duplicates_removed = parser.stats.get("last_dedup_count", 0)
        records_parsed = len(df)
        
        logger.info(
            f"Job {job_id}: Parsed {records_parsed} records from {files_processed} files "
            f"({files_failed} failed, {duplicates_removed} duplicates removed)"
        )
        
        # Check if parsing succeeded
        if records_parsed == 0:
            total_files_attempted = files_processed + files_failed
            
            if files_failed > 0 and files_processed == 0:
                error_msg = f"All {files_failed} file(s) failed to parse"
            elif total_files_attempted == 0:
                error_msg = "No MIB files were found to parse"
            elif files_processed > 0:
                error_msg = f"No data extracted from {files_processed} file(s)"
            else:
                error_msg = "Parse failed: No data was extracted"
            
            logger.error(f"Job {job_id}: {error_msg}")
            raise Exception(error_msg)
        
        # Update progress
        await job_service.update_progress(
            job_id, 92, "Writing data to database...", phase="saving"
        )
        
        # Save DataFrame to jobs database
        if records_parsed > 0:
            success = await asyncio.to_thread(
                job_service.db.save_job_result, df, job_id
            )
            
            if not success:
                raise Exception("Failed to save job results")
            
            logger.info(f"Job {job_id}: ✅ Results saved to jobs database")
        
        await job_service.update_progress(
            job_id, 95, "Data saved successfully", phase="saving"
        )
        
        # ============================================
        # PHASE 4: Cleanup (96% → 98%)
        # ============================================
        phase_timer.start_phase('cleanup')
        
        logger.info(f"Job {job_id}: Cleaning up session...")
        
        await job_service.update_progress(
            job_id, 96, "Cleaning up temporary files...", phase="cleanup"
        )
        
        upload_service = UploadService()
        session_id = Path(session_dir).name
        
        try:
            upload_service.cleanup_session(session_id)
            logger.info(f"Job {job_id}: Session cleaned up")
        except Exception as cleanup_error:
            logger.warning(f"Job {job_id}: Session cleanup failed: {cleanup_error}")
        
        await job_service.update_progress(
            job_id, 98, "Finalizing...", phase="cleanup"
        )


        # Update parser metrics
        if metrics:
            metrics.counter_add('app_parser_files_compiled', files_processed)
            metrics.counter_add('app_parser_files_failed', files_failed)
            metrics.counter_add('app_parser_records_parsed', records_parsed)
            
            # Throughput metrics
            if parse_time > 0:
                files_per_sec = files_processed / parse_time
                records_per_sec = records_parsed / parse_time
                metrics.gauge_set('app_parser_throughput_files_per_sec', round(files_per_sec, 2))
                metrics.gauge_set('app_parser_throughput_records_per_sec', round(records_per_sec, 2))
        
        # Update job metrics
        if metrics:
            metrics.counter('app_jobs_total', labels={'job_type': 'parse', 'status': 'completed'})
        
        # ============================================
        # Complete job with phase timings
        # ============================================
        
        # Get phase timings
        phase_timings = phase_timer.get_timings()
        total_time = phase_timer.get_total_time()
        
        # Calculate performance metrics
        throughput = records_parsed / parse_time if parse_time > 0 else 0
        files_per_sec = files_processed / parse_time if parse_time > 0 else 0
        avg_file_time = parse_time / files_processed if files_processed > 0 else 0
        
        result_metadata = {
            "success": True,
            "table_name": f"job_{job_id.replace('-', '_')}_data",
            "database": "mib_tool_jobs",
            "records_parsed": records_parsed,
            "files_processed": files_processed,
            "files_failed": files_failed,
            "duplicates_removed": duplicates_removed,
            "has_data": records_parsed > 0,
            "performance": {
                "total_time_seconds": round(total_time, 2),
                "parse_time_seconds": round(parse_time, 2),
                "records_per_second": round(throughput, 2),
                "files_per_second": round(files_per_sec, 3),
                "average_file_time_seconds": round(avg_file_time, 2),
                "total_files": files_processed + files_failed,
                "phase_timings": phase_timings,
            },
            # failed files and missing dependencies
            "failed_files": parser.stats.get("failed_files", []),
            "missing_dependencies": parser.stats.get("missing_dependencies", []),
        }
        
        # Log performance with phase breakdown
        logger.info(
            f"Job {job_id}: Performance - "
            f"Total: {total_time:.2f}s, "
            f"Parse: {parse_time:.2f}s, "
            f"Throughput: {throughput:.2f} rec/s"
        )
        logger.info(f"Job {job_id}: Phase timings: {phase_timings}")
        
        # ✅ NEW: Complete job using JobService
        await job_service.complete_job(
            job_id,
            result_metadata,
            message=f"Successfully parsed {records_parsed} records from {files_processed} files"
        )
    
    except JobCancelledException:
        if metrics:
            metrics.counter('app_jobs_total', labels={'job_type': 'parse', 'status': 'cancelled'})
        # ✅ NEW: Handle cancellation using JobService
        await job_service.cancel_job(job_id)
    
    except Exception as e:
        if metrics:
            metrics.counter('app_jobs_total', labels={'job_type': 'parse', 'status': 'failed'})

        # ✅ NEW: Handle failure using JobService
        logger.error(f"Job {job_id} failed: {e}")
        
        if hasattr(config, "debug") and config.debug:
            logger.debug(f"Job {job_id} traceback:", exc_info=True)
        elif hasattr(config, "verbosity") and config.verbosity >= 3:
            logger.debug(f"Job {job_id} traceback:", exc_info=True)
        
        await job_service.fail_job(job_id, str(e))

def generate_job_name(files: List[Dict], custom_name: str = None) -> str:
    """
    Generate descriptive job name

    Args:
        files: List of file info dicts
        custom_name: User-provided custom name

    Returns:
        Descriptive job name
    """
    if custom_name:
        return custom_name

    if not files:
        return "Parse Job"

    if len(files) == 1:
        filename = Path(files[0]["filename"]).stem
        return f"Parse: {filename}"
    else:
        first_file = Path(files[0]["filename"]).stem
        return f"Parse: {first_file} + {len(files) - 1} more"
