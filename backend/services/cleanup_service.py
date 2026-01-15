"""
Cleanup Service - Automatic job cleanup
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.logger import get_logger

logger = get_logger(__name__)


class CleanupService:
    """
    Service for automatic cleanup of old jobs.

    Features:
    - Scheduled cleanup (daily at configured time)
    - Manual cleanup trigger
    - Configurable retention period
    - Selective cleanup (only completed/failed/cancelled)
    - Optional data table deletion
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.config = None
        self.db_manager = None
        self.is_running = False

    def start(self, config, db_manager):
        """
        Start the cleanup service.

        Args:
            config: Application configuration
            db_manager: Database manager instance
        """
        config = config
        self.db_manager = db_manager

        if not config.cleanup.enabled:
            logger.info("Cleanup service is disabled in configuration")
            return

        try:
            # Schedule cleanup job
            trigger = CronTrigger(
                hour=config.cleanup.schedule_hour, minute=config.cleanup.schedule_minute
            )

            self.scheduler.add_job(
                self.cleanup_old_jobs,
                trigger=trigger,
                id="cleanup_old_jobs",
                name="Cleanup Old Jobs",
                replace_existing=True,
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(
                f"✅ Cleanup service started - "
                f"runs daily at {config.cleanup.schedule_hour:02d}:{config.cleanup.schedule_minute:02d}, "
                f"retention: {config.cleanup.retention_days} days"
            )

        except Exception as e:
            logger.error(f"Failed to start cleanup service: {e}", exc_info=True)

    def stop(self):
        """Stop the cleanup service"""
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Cleanup service stopped")

    async def cleanup_old_jobs(self, dry_run: bool = False) -> dict:
        """
        Clean up old jobs based on retention policy.

        Args:
            dry_run: If True, only report what would be deleted without actually deleting

        Returns:
            Dictionary with cleanup statistics
        """
        try:
            from services import Config as config

            retention_days = config.cleanup.retention_days
            cutoff_date = datetime.now() - timedelta(days=retention_days)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else ''}Starting cleanup: "
                f"deleting jobs older than {retention_days} days (before {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})"
            )

            # Get all jobs
            jobs = self.db_manager.list_jobs(limit=100000)

            stats = {
                "total_jobs": len(jobs),
                "eligible_for_deletion": 0,
                "deleted": 0,
                "failed": 0,
                "skipped": 0,
                "errors": [],
            }

            for job in jobs:
                try:
                    # Check if job should be kept
                    if self._should_keep_job(job, cutoff_date):
                        stats["skipped"] += 1
                        continue

                    stats["eligible_for_deletion"] += 1

                    if not dry_run:
                        # Delete job
                        success = await asyncio.to_thread(
                            self.db_manager.delete_job_complete,
                            job["job_id"],
                            delete_data=self.config.cleanup.delete_data,
                        )

                        if success:
                            stats["deleted"] += 1
                            logger.debug(
                                f"Deleted job {job['job_id']} ({job['status']}, {job.get('completed_at', 'N/A')})"
                            )
                        else:
                            stats["failed"] += 1
                            stats["errors"].append(f"Failed to delete job {job['job_id']}")

                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"Error processing job {job.get('job_id', 'unknown')}: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.error(error_msg)

            # Log summary
            if dry_run:
                logger.info(
                    f"[DRY RUN] Cleanup summary: "
                    f"{stats['eligible_for_deletion']} jobs would be deleted, "
                    f"{stats['skipped']} would be kept"
                )
            else:
                logger.info(
                    f"✅ Cleanup complete: "
                    f"deleted {stats['deleted']} jobs, "
                    f"failed {stats['failed']}, "
                    f"skipped {stats['skipped']}"
                )

            return stats

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            return {
                "total_jobs": 0,
                "eligible_for_deletion": 0,
                "deleted": 0,
                "failed": 0,
                "skipped": 0,
                "errors": [str(e)],
            }

    def _should_keep_job(self, job: dict, cutoff_date: datetime) -> bool:
        """
        Determine if a job should be kept.

        Args:
            job: Job metadata
            cutoff_date: Jobs older than this date are eligible for deletion

        Returns:
            True if job should be kept, False if it can be deleted
        """
        # Never delete running or queued jobs
        if job["status"] in ["running", "queued"]:
            return True

        # Keep jobs with specific statuses if configured
        if job["status"] in self.config.cleanup.keep_statuses:
            return True

        # Check if job is old enough to delete
        completed_at = job.get("completed_at")
        if not completed_at:
            # Job never completed, check created_at
            created_at = job.get("created_at")
            if not created_at:
                # No timestamp, keep it to be safe
                return True

            # Use created_at for comparison
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

            return created_at >= cutoff_date

        # Use completed_at for comparison
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

        return completed_at >= cutoff_date

    async def get_cleanup_preview(self) -> dict:
        """
        Get a preview of what would be deleted without actually deleting.

        Returns:
            Dictionary with preview statistics
        """
        return await self.cleanup_old_jobs(dry_run=True)


# Global instance
cleanup_service = CleanupService()
