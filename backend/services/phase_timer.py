"""
Phase Timer - Track execution time per phase
"""

from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PhaseTimer:
    """Track time spent in each phase for ETA calculation"""
    
    def __init__(self):
        self.phase_timings: Dict[str, float] = {}
        self.current_phase: Optional[str] = None
        self.phase_start_time: Optional[datetime] = None
        self.job_start_time: datetime = datetime.now()
    
    def start_phase(self, phase_name: str):
        """Start timing a phase"""
        # End previous phase if exists
        if self.current_phase and self.phase_start_time:
            self.end_phase()
        
        self.current_phase = phase_name
        self.phase_start_time = datetime.now()
        logger.debug(f"Phase '{phase_name}' started")
    
    def end_phase(self):
        """End current phase and record time"""
        if self.current_phase and self.phase_start_time:
            duration = (datetime.now() - self.phase_start_time).total_seconds()
            self.phase_timings[self.current_phase] = duration
            logger.debug(f"Phase '{self.current_phase}' completed in {duration:.2f}s")
            self.current_phase = None
            self.phase_start_time = None
    
    def get_timings(self) -> Dict[str, float]:
        """Get all phase timings"""
        # End current phase if still running
        if self.current_phase:
            self.end_phase()
        return self.phase_timings
    
    def get_total_time(self) -> float:
        """Get total elapsed time since job start"""
        return (datetime.now() - self.job_start_time).total_seconds()
    
    def calculate_eta(self, current_phase: str, current_progress: float) -> Optional[float]:
        """
        Calculate ETA - uses simplified approach for better accuracy.
        """
        # ✅ Use simplified calculation (more accurate with variable phase times)
        return self.calculate_eta_simple(current_progress)
    
    def calculate_eta_simple(self, current_progress: float) -> Optional[float]:
        """
        Simplified ETA: Use actual elapsed time and current progress.
        
        More accurate than phase-based estimation when phase times vary wildly.
        """
        if current_progress <= 0 or current_progress >= 90:
            return None
        
        # Get total elapsed time
        elapsed = (datetime.now() - self.job_start_time).total_seconds()
        
        if elapsed < 5:  # Need at least 5 seconds of data
            return None
        
        # Calculate rate (progress per second)
        rate = current_progress / elapsed
        
        if rate <= 0:
            return None
        
        # Estimate remaining progress (90% is when backend takes over)
        remaining_progress = 90 - current_progress
        
        # Calculate remaining time
        remaining_time = remaining_progress / rate
        
        # Add buffer for backend phases (saving + cleanup ≈ 40% of total)
        # If we're at 90%, backend phases will take ~40% of elapsed time
        backend_buffer = elapsed * 0.5
        
        total_eta = remaining_time + backend_buffer
        
        # Clamp to reasonable range
        total_eta = max(1, min(7200, total_eta))
        
        return total_eta

