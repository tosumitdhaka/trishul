#!/usr/bin/env python3
"""
Simple File-Based Metrics Service with Resource Tracking

For single-pod deployment with ~20 metrics.
Writes to JSON file on PVC, tracks CPU/Memory usage.
"""

import json
import os
import psutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from utils.logger import get_logger
from services.config_service import Config


class SimpleFileMetrics:
    """
    Lightweight file-based metrics for single pod.
    
    Features:
    - In-memory counters/gauges
    - Periodic flush to JSON file (every 60s)
    - Load from file on startup
    - CPU/Memory tracking
    - Thread-safe operations
    """
    
    def __init__(self, config):
        """
        Initialize metrics service.
        
        Args:
            metrics_file: Path to metrics JSON file
        """

        config = config

        metrics_path = f"{config.metrics.directory}/metrics.json"
        self.metrics_file = Path(metrics_path)

        self.logger = get_logger(self.__class__.__name__)
        
        # Create directory
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

        # Retention
        self.retention_days = config.metrics.retention_days
        
        # In-memory metrics
        self._metrics = {}
        self._lock = threading.RLock()
        
        # Resource tracking
        self._process = psutil.Process(os.getpid())
        self._max_memory_mb = 0.0
        self._max_cpu_percent = 0.0
        
        # Background flush
        self._flush_interval = config.metrics.flush_interval_sec
        self._flush_thread = None
        self._stop_flush = threading.Event()
        
        # Resource monitoring
        self._monitor_interval = config.metrics.monitor_interval
        self._monitor_thread = None
        self._stop_monitor = threading.Event()
        
        # Load existing metrics
        self._load()
        
        # Start background threads
        self._start_flush_thread()
        self._start_monitor_thread()
        
        self.logger.info(f"Metrics service initialized: {self.metrics_file}")
    
    def _load(self):
        """Load latest metrics file."""
        # Find latest metrics file
        files = sorted(self.metrics_file.parent.glob("metrics_*.json"))
        
        if not files:
            self.logger.info("No existing metrics, starting fresh")
            return
        
        latest_file = files[-1]
        
        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
                with self._lock:
                    self._metrics = data.get('metrics', {})
                    self._max_memory_mb = data.get('max_memory_mb', 0.0)
                    self._max_cpu_percent = data.get('max_cpu_percent', 0.0)
                self.logger.info(f"Loaded {len(self._metrics)} metrics from {latest_file.name}")
        except Exception as e:
            self.logger.warning(f"Failed to load metrics: {e}")
    
    def _start_flush_thread(self):
        """Start background flush thread."""
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _start_monitor_thread(self):
        """Start background resource monitoring thread."""
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _flush_loop(self):
        """Background loop to flush metrics."""
        while not self._stop_flush.wait(self._flush_interval):
            try:
                self._flush()
            except Exception as e:
                self.logger.error(f"Flush failed: {e}")
    
    def _monitor_loop(self):
        """Background loop to monitor resource usage."""
        while not self._stop_monitor.wait(self._monitor_interval):
            try:
                self._update_resource_metrics()
            except Exception as e:
                self.logger.error(f"Resource monitoring failed: {e}")
    
    def _update_resource_metrics(self):
        """Update CPU and memory metrics."""
        try:
            # Get current memory usage
            memory_info = self._process.memory_info()
            current_memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
            
            # Get current CPU usage (average over interval)
            current_cpu_percent = self._process.cpu_percent(interval=1)
            
            with self._lock:
                # Update max values
                if current_memory_mb > self._max_memory_mb:
                    self._max_memory_mb = current_memory_mb
                    self.logger.debug(f"New max memory: {self._max_memory_mb:.2f} MB")
                
                if current_cpu_percent > self._max_cpu_percent:
                    self._max_cpu_percent = current_cpu_percent
                    self.logger.debug(f"New max CPU: {self._max_cpu_percent:.2f}%")
                
                # Update current gauges
                self.gauge_set('app_resource_memory_current_mb', round(current_memory_mb, 2))
                self.gauge_set('app_resource_memory_max_mb', round(self._max_memory_mb, 2))
                self.gauge_set('app_resource_cpu_current_percent', round(current_cpu_percent, 2))
                self.gauge_set('app_resource_cpu_max_percent', round(self._max_cpu_percent, 2))
        
        except Exception as e:
            self.logger.debug(f"Failed to update resource metrics: {e}")
    
    def _flush(self):
        """Flush metrics to file with daily rotation."""
        with self._lock:
            snapshot = dict(self._metrics)
            max_memory = self._max_memory_mb
            max_cpu = self._max_cpu_percent
        
        try:
            # Daily rotation
            date_suffix = datetime.now().strftime("%Y-%m-%d")
            metrics_file = self.metrics_file.parent / f"metrics_{date_suffix}.json"
            temp_file = metrics_file.with_suffix('.tmp')
            
            data = {
                'updated_at': datetime.now().isoformat(),
                'max_memory_mb': max_memory,
                'max_cpu_percent': max_cpu,
                'metrics': snapshot
            }
            
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_file.replace(metrics_file)
            
            # Cleanup old files (keep last 7 days)
            self._cleanup_old_files(self.retention_days)
            
            self.logger.debug(f"Flushed to {metrics_file.name}")
        
        except Exception as e:
            self.logger.error(f"Flush failed: {e}")

    def _cleanup_old_files(self, days: int = 7):
        """Delete metrics files older than N days."""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            
            for file in self.metrics_file.parent.glob("metrics_*.json"):
                if file.stat().st_mtime < cutoff.timestamp():
                    file.unlink()
                    self.logger.info(f"Deleted old metrics: {file.name}")
        except Exception as e:
            self.logger.debug(f"Cleanup failed: {e}")
    
    def counter(self, name: str, labels: Optional[Dict] = None) -> int:
        """Increment counter by 1."""
        return self.counter_add(name, 1, labels)
    
    def counter_add(self, name: str, value: int, labels: Optional[Dict] = None) -> int:
        """Add value to counter."""
        key = self._make_key(name, labels)

        # ✅ ADD DEBUG LOG
        # self.logger.info(f"📊 counter_add: {name} += {value} (labels={labels})")
        
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = {
                    'name': name,
                    'type': 'counter',
                    'value': 0,
                    'labels': labels or {}
                }
            
            self._metrics[key]['value'] += value

            # ✅ ADD DEBUG LOG
            # self.logger.info(f"📊 {name} = {self._metrics[key]['value']}")

            return self._metrics[key]['value']
    
    def gauge_set(self, name: str, value: float, labels: Optional[Dict] = None):
        """Set gauge value."""
        key = self._make_key(name, labels)
        
        with self._lock:
            self._metrics[key] = {
                'name': name,
                'type': 'gauge',
                'value': value,
                'labels': labels or {}
            }
    
    def _make_key(self, name: str, labels: Optional[Dict] = None) -> str:
        """Create unique key for metric."""
        if labels:
            labels_str = json.dumps(labels, sort_keys=True)
            return f"{name}:{labels_str}"
        return name
    
    def get_all(self) -> Dict[str, Any]:
        """Get all metrics grouped by name."""
        with self._lock:
            snapshot = dict(self._metrics)
        
        # Group by metric name
        grouped = {}
        for key, metric in snapshot.items():
            name = metric['name']
            if name not in grouped:
                grouped[name] = []
            
            grouped[name].append({
                'value': metric['value'],
                'labels': metric['labels'],
                'type': metric['type']
            })
        
        return grouped
    
    def get_metric(self, name: str, labels: Optional[Dict] = None) -> Optional[float]:
        """Get specific metric value."""
        key = self._make_key(name, labels)
        
        with self._lock:
            if key in self._metrics:
                return self._metrics[key]['value']
        
        return None
    
    def get_resource_stats(self) -> Dict[str, float]:
        """Get current resource statistics."""
        with self._lock:
            return {
                'max_memory_mb': round(self._max_memory_mb, 2),
                'max_cpu_percent': round(self._max_cpu_percent, 2),
                'current_memory_mb': round(self.get_metric('app_resource_memory_current_mb') or 0, 2),
                'current_cpu_percent': round(self.get_metric('app_resource_cpu_current_percent') or 0, 2),
            }
    
    def reset_max_resources(self):
        """Reset max resource tracking (useful for testing)."""
        with self._lock:
            self._max_memory_mb = 0.0
            self._max_cpu_percent = 0.0
            self.logger.info("Reset max resource tracking")
    
    def shutdown(self):
        """Shutdown and flush."""
        self.logger.info("Shutting down metrics service...")
        
        # Stop threads
        self._stop_flush.set()
        self._stop_monitor.set()
        
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        # Final flush
        self._flush()
        self.logger.info("Metrics service shutdown complete")


# Global instance
_metrics_service = None


def get_metrics_service():
    """Get global metrics service instance."""
    return _metrics_service


def init_metrics_service(config):
    """Initialize global metrics service."""
    global _metrics_service

    if not config:
        config = Config()

    _metrics_service = SimpleFileMetrics(config)
    return _metrics_service
