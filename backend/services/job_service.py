
#!/usr/bin/env python3
"""
Job Service - Centralized job management

Handles job lifecycle:
- Create jobs with metadata
- Update progress (DB + WebSocket)
- Complete/fail jobs
- Check cancellation status
"""

import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class JobCancelledException(Exception):
    """Raised when job is cancelled by user"""
    pass


class JobService:
    """
    Centralized job management service
    
    Responsibilities:
    - Create jobs with metadata
    - Update progress (DB + WebSocket)
    - Complete/fail jobs
    - Check cancellation status
    
    Example:
        ```python
        job_service = JobService(db_manager, ws_manager, config)
        
        # Create job
        job_id = job_service.create_job(
            job_type="parse",
            job_name="Parse MIB files",
            metadata={"file_count": 10}
        )
        
        # Update progress
        await job_service.update_progress(job_id, 50, "Processing...")
        
        # Complete job
        await job_service.complete_job(job_id, {"records": 100})
        ```
    """
    
    def __init__(self, db_manager, ws_manager, config):
        """
        Initialize job service
        
        Args:
            db_manager: DatabaseManager instance
            ws_manager: WebSocket ConnectionManager instance
            config: Application config
        """
        self.db = db_manager
        self.ws = ws_manager
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    def generate_job_id(self) -> str:
        """Generate unique job ID"""
        return str(uuid.uuid4())
    
    def create_job(
        self,
        job_type: str,
        job_name: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Create new job in database
        
        Args:
            job_type: Type of job (e.g., 'parse', 'export', 'trap_send')
            job_name: Human-readable job name
            metadata: Job-specific metadata
        
        Returns:
            job_id: Generated job ID
        
        Raises:
            RuntimeError: If job creation fails
        """
        job_id = self.generate_job_id()
        
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "job_name": job_name,
            "status": "queued",
            "created_at": datetime.now(),
            "progress": 0,
            "message": "Job queued...",
            "metadata": metadata,
        }
        
        success = self.db.save_job_metadata(job_data)
        
        if not success:
            raise RuntimeError(f"Failed to create job {job_id}")
        
        self.logger.info(f"✅ Created job {job_id}: {job_name}")
        
        return job_id
    
    async def start_job(self, job_id: str):
        """
        Mark job as started
        
        Args:
            job_id: Job ID
        """
        await asyncio.to_thread(
            self.db.save_job_metadata,
            {
                "job_id": job_id,
                "status": "running",
                "started_at": datetime.now(),
                "progress": 0,
                "message": "Job started...",
            }
        )
        
        self.logger.info(f"▶️ Started job {job_id}")
    
    async def update_progress(
        self,
        job_id: str,
        progress: int,
        message: str,
        phase: Optional[str] = "running",
        eta_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update job progress (DB + WebSocket)
        
        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            message: Status message
            phase: Current phase name (optional)
            eta_seconds: Estimated time remaining (optional)
            metadata: Additional metadata (optional)
        """

        if phase == "queued":
            status = phase
        else:
            status = "running"

        # Update database
        await asyncio.to_thread(
            self.db.save_job_metadata,
            {
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message,
            }
        )
        
        # Push WebSocket update
        if self.ws:
            ws_data = {
                "job_id": job_id,
                "phase": phase or "processing",
                "percentage": progress,
                "message": message,
            }
            
            if eta_seconds is not None:
                ws_data["eta_seconds"] = eta_seconds
            
            if metadata:
                ws_data["metadata"] = metadata
            
            await self.ws.publish(f"job:{job_id}", ws_data)
        
        self.logger.debug(f"Job {job_id}: {progress}% - {message}")
    
    async def complete_job(
        self,
        job_id: str,
        result: Dict[str, Any],
        message: Optional[str] = None
    ):
        """
        Mark job as completed
        
        Args:
            job_id: Job ID
            result: Job result metadata
            message: Completion message (optional)
        """
        completion_message = message or "Job completed successfully"
        
        await asyncio.to_thread(
            self.db.save_job_metadata,
            {
                "job_id": job_id,
                "status": "completed",
                "completed_at": datetime.now(),
                "progress": 100,
                "message": completion_message,
                "result": result,
            }
        )
        
        # Push final WebSocket update
        if self.ws:
            await self.ws.publish(
                f"job:{job_id}",
                {
                    "job_id": job_id,
                    "phase": "complete",
                    "percentage": 100,
                    "message": completion_message,
                    "metadata": result,
                }
            )
        
        self.logger.info(f"✅ Completed job {job_id}")
    
    async def fail_job(
        self,
        job_id: str,
        error: str,
        errors: Optional[list] = None
    ):
        """
        Mark job as failed
        
        Args:
            job_id: Job ID
            error: Error message
            errors: List of error details (optional)
        """
        error_message = f"Job failed: {error}"
        
        await asyncio.to_thread(
            self.db.save_job_metadata,
            {
                "job_id": job_id,
                "status": "failed",
                "completed_at": datetime.now(),
                "progress": 0,
                "message": error_message,
                "errors": errors or [error],
            }
        )
        
        # Push failure WebSocket update
        if self.ws:
            await self.ws.publish(
                f"job:{job_id}",
                {
                    "job_id": job_id,
                    "phase": "failed",
                    "percentage": 0,
                    "message": error_message,
                    "metadata": {"error": error},
                }
            )
        
        self.logger.error(f"❌ Failed job {job_id}: {error}")
    
    async def cancel_job(self, job_id: str):
        """
        Mark job as cancelled
        
        Args:
            job_id: Job ID
        """
        await asyncio.to_thread(
            self.db.save_job_metadata,
            {
                "job_id": job_id,
                "status": "cancelled",
                "completed_at": datetime.now(),
                "progress": 0,
                "message": "Job cancelled by user",
            }
        )
        
        # Push cancellation WebSocket update
        if self.ws:
            await self.ws.publish(
                f"job:{job_id}",
                {
                    "job_id": job_id,
                    "phase": "cancelled",
                    "percentage": 0,
                    "message": "Job cancelled by user",
                }
            )
        
        self.logger.info(f"🚫 Cancelled job {job_id}")
    
    def check_cancellation(self, job_id: str):
        """
        Check if job is cancelled
        
        Args:
            job_id: Job ID
        
        Raises:
            JobCancelledException: If job is cancelled
        """
        try:
            job = self.db.get_job_metadata(job_id)
            if job and job.get("status") == "cancelled":
                self.logger.info(f"Job {job_id}: Cancellation detected")
                raise JobCancelledException(f"Job {job_id} cancelled by user")
        except JobCancelledException:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to check cancellation for {job_id}: {e}")
    