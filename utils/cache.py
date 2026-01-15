#!/usr/bin/env python3
"""
Cache Manager - Handles caching of parsed MIB data (THREAD-SAFE)
Improves performance by caching parsed DataFrames
"""

import hashlib
import json
import pickle
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.logger import get_logger


class CacheManager:
    """Thread-safe cache manager for parsed MIB data."""

    CACHE_VERSION = "3.0.0"  # Increment when data structure changes

    # ✅ Class-level lock for initialization
    _init_lock = threading.Lock()

    def __init__(self, cache_dir: str = "./cache", enabled: bool = True, config=None):
        """
        Initialize cache manager (thread-safe).

        Args:
            cache_dir: Directory for cache files
            enabled: Whether caching is enabled
            config: Cache config object with ttl_hours, max_size_mb, cleanup_on_startup
        """
        # ✅ Use lock during initialization to prevent race conditions
        with self._init_lock:
            self.cache_dir = Path(cache_dir)
            self.enabled = enabled
            self.logger = get_logger(self.__class__.__name__)

            # ✅ Store config values
            self.config = config
            if config:
                self.ttl_hours = getattr(config, 'ttl_hours', 168)
                self.max_size_mb = getattr(config, 'max_size_mb', 500)
                self.cleanup_on_startup = getattr(config, 'cleanup_on_startup', False)
            else:
                self.ttl_hours = 168  # 7 days default
                self.max_size_mb = 500  # 500 MB default
                self.cleanup_on_startup = False

            # ✅ Instance-level lock for all operations
            self._lock = threading.RLock()  # Reentrant lock

            # ✅ Initialize stats with lock protection
            with self._lock:
                self.cache_stats = {"hits": 0, "misses": 0, "saves": 0, "errors": 0}

            if self.enabled:
                # Create cache directory if it doesn't exist
                self.cache_dir.mkdir(parents=True, exist_ok=True)

                # Check and update cache version
                self._check_cache_version()

                # ✅ Initialize metadata file path BEFORE loading
                self.metadata_file = self.cache_dir / "cache_metadata.json"

                # Initialize metadata
                self.metadata = self._load_metadata()

                # ✅ NEW: Cleanup on startup if configured
                if self.cleanup_on_startup:
                    self.logger.info("🧹 Cleanup on startup enabled, clearing cache...")
                    cleared = self.clear_cache()
                    self.logger.info(f"✅ Cleared {cleared} cache files on startup")
                else:
                    # ✅ NEW: Auto-cleanup expired files based on TTL
                    self._cleanup_expired_cache()

        # Import metrics service
        try:
            from backend.services.metrics_service import get_metrics_service
            self.metrics = get_metrics_service()
        except ImportError:
            self.metrics = None

    def _cleanup_expired_cache(self):
        """Remove cache files older than TTL (thread-safe)."""
        if not self.enabled or not self.ttl_hours:
            return

        try:
            with self._lock:
                ttl_days = self.ttl_hours / 24
                cutoff_time = datetime.now() - timedelta(hours=self.ttl_hours)
                
                removed = 0
                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            cache_file.unlink()
                            removed += 1
                    except Exception as e:
                        self.logger.debug(f"Error removing expired cache file {cache_file}: {e}")
                
                if removed > 0:
                    self.logger.info(f"🧹 Removed {removed} expired cache files (TTL: {self.ttl_hours}h / {ttl_days:.1f} days)")
                    # Update metadata
                    self._save_metadata()
        except Exception as e:
            self.logger.debug(f"Error during expired cache cleanup: {e}")

    def _check_cache_version(self):
        """Check cache version and clear if outdated (thread-safe)."""
        with self._lock:
            version_file = self.cache_dir / ".version"

            if version_file.exists():
                try:
                    current_version = version_file.read_text().strip()
                    if current_version != self.CACHE_VERSION:
                        self.logger.info(
                            f"Cache version mismatch ({current_version} != {self.CACHE_VERSION}), clearing cache"
                        )
                        self._clear_cache_internal()
                except Exception as e:
                    self.logger.debug(f"Error reading cache version: {e}")
                    self._clear_cache_internal()

            # Write current version
            try:
                version_file.write_text(self.CACHE_VERSION)
            except Exception as e:
                self.logger.debug(f"Error writing cache version: {e}")

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata (thread-safe)."""
        with self._lock:
            if self.metadata_file.exists():
                try:
                    with open(self.metadata_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    self.logger.debug(f"Error loading cache metadata: {e}")

            return {
                "created": datetime.now().isoformat(),
                "version": self.CACHE_VERSION,
                "files": {},
                "stats": {"total_hits": 0, "total_misses": 0, "total_saves": 0},
            }

    def _save_metadata(self):
        """Save cache metadata (thread-safe)."""
        with self._lock:
            try:
                # Update stats
                self.metadata["stats"]["total_hits"] += self.cache_stats["hits"]
                self.metadata["stats"]["total_misses"] += self.cache_stats["misses"]
                self.metadata["stats"]["total_saves"] += self.cache_stats["saves"]
                self.metadata["last_updated"] = datetime.now().isoformat()

                with open(self.metadata_file, "w", encoding="utf-8") as f:
                    json.dump(self.metadata, f, indent=2)
            except Exception as e:
                self.logger.debug(f"Error saving cache metadata: {e}")

    def _get_cache_key(self, file_path: str) -> str:
        """Generate stable cache key for a file (thread-safe)."""
        file_path = Path(file_path)

        if not file_path.exists():
            return None

        # Only use file path and modification time
        file_stat = file_path.stat()
        key_string = f"{file_path.absolute()}:{file_stat.st_mtime}:{file_stat.st_size}"

        # Create MD5 hash
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_filename(self, cache_key: str) -> Path:
        """Get cache filename for a cache key."""
        return self.cache_dir / f"{cache_key}.cache"

    def get(self, file_path: str) -> Optional[pd.DataFrame]:
        """Simple get method (alias for get_cached) - thread-safe."""
        return self.get_cached(file_path)

    def is_cached(self, file_path: str) -> bool:
        """Check if file is cached without loading (thread-safe)."""
        if not self.enabled:
            return False

        with self._lock:
            cache_key = self._get_cache_key(file_path)
            if not cache_key:
                return False

            cache_file = self._get_cache_filename(cache_key)

            if cache_file.exists():
                # Check if cache is still valid
                source_mtime = Path(file_path).stat().st_mtime
                cache_mtime = cache_file.stat().st_mtime
                return cache_mtime > source_mtime

            return False

    def get_cache_info(self, file_path: str) -> Optional[Dict]:
        """Get information about cached file without loading data (thread-safe)."""
        with self._lock:
            cache_key = self._get_cache_key(file_path)
            if not cache_key:
                return None

            cache_file = self._get_cache_filename(cache_key)
            if cache_file.exists():
                return {
                    "exists": True,
                    "size": cache_file.stat().st_size,
                    "modified": datetime.fromtimestamp(cache_file.stat().st_mtime),
                    "key": cache_key,
                }
            return None

    def get_cached(self, file_path: str) -> Optional[pd.DataFrame]:
        """Get cached DataFrame for a MIB file (thread-safe)."""
        if not self.enabled:
            return None

        with self._lock:
            cache_key = self._get_cache_key(file_path)

            if not cache_key:
                self.cache_stats["misses"] += 1
                return None

            cache_file = self._get_cache_filename(cache_key)

            if not cache_file.exists():
                self.cache_stats["misses"] += 1
                if self.metrics:
                    self.metrics.counter('app_cache_operations', labels={'operation': 'hit'})
                self.logger.debug(f"Cache miss for {Path(file_path).name} - file not found")
                return None

            try:
                # Check if source file is newer than cache
                source_mtime = Path(file_path).stat().st_mtime
                cache_mtime = cache_file.stat().st_mtime

                if source_mtime > cache_mtime:
                    self.logger.debug(f"Cache outdated for {Path(file_path).name}")
                    cache_file.unlink()  # Remove outdated cache
                    self.cache_stats["misses"] += 1
                    return None

                # Load cached data
                with open(cache_file, "rb") as f:
                    data = pickle.load(f)

                # Quick validation
                if isinstance(data, dict) and "df" in data:
                    df = data["df"]
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        self.cache_stats["hits"] += 1
                        if self.metrics:
                            self.metrics.counter('app_cache_operations', labels={'operation': 'hit'})
                        self.logger.debug(
                            f"✓ Cache hit for {Path(file_path).name} ({len(df)} records)"
                        )
                        return df

                # Invalid cache
                self.logger.debug(f"Invalid cache structure for {Path(file_path).name}")
                cache_file.unlink()
                self.cache_stats["misses"] += 1
                return None

            except Exception as e:
                self.logger.debug(f"Error loading cache: {e}")
                self.cache_stats["errors"] += 1
                try:
                    cache_file.unlink()  # Remove corrupted cache
                except:
                    pass
                return None

    def cache(self, file_path: str, df: pd.DataFrame, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache a DataFrame for a MIB file (thread-safe).

        Args:
            file_path: Path to the MIB file
            df: DataFrame to cache
            metadata: Optional metadata to store with cache

        Returns:
            True if successfully cached, False otherwise
        """
        if not self.enabled or df is None or df.empty:
            return False

        with self._lock:
            cache_key = self._get_cache_key(file_path)
            if not cache_key:
                return False

            cache_file = self._get_cache_filename(cache_key)

            try:
                # Prepare cache data
                cache_data = {
                    "version": self.CACHE_VERSION,
                    "df": df,
                    "metadata": metadata or {},
                    "cached_at": datetime.now().isoformat(),
                    "file_path": str(file_path),
                    "file_size": Path(file_path).stat().st_size,
                    "record_count": len(df),
                }

                # Save to cache
                with open(cache_file, "wb") as f:
                    pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

                self.cache_stats["saves"] += 1
                self.logger.debug(f"Cached data for {Path(file_path).name} ({len(df)} records)")

                if self.metrics:
                    self.metrics.counter('app_cache_operations', labels={'operation': 'save'})
                    # Update cache size gauge
                    total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.cache"))
                    self.metrics.gauge_set('app_cache_size_bytes', total_size)
                    self.metrics.gauge_set('app_cache_files_total', len(list(self.cache_dir.glob("*.cache"))))

                # Update metadata
                file_name = Path(file_path).name
                self.metadata["files"][file_name] = {
                    "cache_key": cache_key,
                    "cache_file": cache_file.name,
                    "source_file": str(file_path),
                    "cached_at": datetime.now().isoformat(),
                    "size": cache_file.stat().st_size,
                    "record_count": len(df),
                    "hits": 0,
                }

                # Save metadata periodically
                if self.cache_stats["saves"] % 10 == 0:
                    self._save_metadata()

                return True

            except Exception as e:
                self.logger.debug(f"Error caching data for {Path(file_path).name}: {e}")
                self.cache_stats["errors"] += 1
                return False

    def warm_cache(self, mib_files: List[Path], parser=None) -> int:
        """Pre-populate cache for a list of MIB files (thread-safe)."""
        if not self.enabled or not parser:
            return 0

        warmed = 0
        for mib_file in mib_files:
            with self._lock:
                cache_key = self._get_cache_key(str(mib_file))
                if cache_key:
                    cache_file = self._get_cache_filename(cache_key)
                    if not cache_file.exists():
                        pass

            # Parse outside lock to avoid holding lock during slow operation
            try:
                df = parser.parse_file(str(mib_file))
                if not df.empty:
                    self.cache(str(mib_file), df)
                    warmed += 1
            except:
                pass

        self.logger.info(f"Warmed cache with {warmed} files")
        return warmed

    def _clear_cache_internal(self) -> int:
        """Internal cache clearing (assumes lock is held)."""
        cleared = 0

        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
                cleared += 1
            except Exception as e:
                self.logger.debug(f"Error removing cache file {cache_file}: {e}")

        # Reset metadata
        self.metadata = {
            "created": datetime.now().isoformat(),
            "version": self.CACHE_VERSION,
            "files": {},
            "stats": {"total_hits": 0, "total_misses": 0, "total_saves": 0},
        }

        return cleared

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cache files (thread-safe).

        Args:
            older_than_days: Only clear files older than this many days

        Returns:
            Number of files cleared
        """
        if not self.enabled:
            return 0

        with self._lock:
            cleared = 0

            if older_than_days is not None:
                # Clear only old files
                cutoff_time = datetime.now() - timedelta(days=older_than_days)

                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            cache_file.unlink()
                            cleared += 1
                    except Exception as e:
                        self.logger.debug(f"Error removing cache file {cache_file}: {e}")
            else:
                # Clear all cache files
                cleared = self._clear_cache_internal()
                self._save_metadata()

            if cleared > 0:
                self.logger.info(f"Cleared {cleared} cache files")
            return cleared

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (thread-safe)."""
        with self._lock:
            stats = {
                "enabled": self.enabled,
                "cache_dir": str(self.cache_dir),
                "ttl_hours": self.ttl_hours,
                "max_size_mb": self.max_size_mb,
                "cleanup_on_startup": self.cleanup_on_startup,
                "total_files": 0,
                "total_size_mb": 0,
                "oldest_file": None,
                "newest_file": None,
                "session_stats": self.cache_stats.copy(),
            }

            if not self.enabled:
                return stats

            # Calculate cache directory stats
            cache_files = list(self.cache_dir.glob("*.cache"))

            if cache_files:
                stats["total_files"] = len(cache_files)
                stats["total_size_mb"] = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)

                # Find oldest and newest
                cache_files.sort(key=lambda f: f.stat().st_mtime)
                stats["oldest_file"] = cache_files[0].name
                stats["newest_file"] = cache_files[-1].name

            # Calculate hit rate
            total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
            if total_requests > 0:
                stats["hit_rate"] = round((self.cache_stats["hits"] / total_requests) * 100, 2)
            else:
                stats["hit_rate"] = 0

            # Add metadata stats
            if self.metadata:
                stats["metadata"] = {
                    "created": self.metadata.get("created"),
                    "last_updated": self.metadata.get("last_updated"),
                    "total_cached_files": len(self.metadata.get("files", {})),
                }

            return stats

    def optimize_cache(self, max_size_mb: float = None, max_age_days: int = None) -> Dict[str, int]:
        """
        Optimize cache by removing old or large files (thread-safe).

        Args:
            max_size_mb: Maximum cache size in MB (uses config if not provided)
            max_age_days: Maximum age of cache files in days (uses config TTL if not provided)

        Returns:
            Dictionary with optimization results
        """
        if not self.enabled:
            return {"removed": 0}

        # ✅ Use config values if not provided
        if max_size_mb is None:
            max_size_mb = self.max_size_mb

        if max_age_days is None:
            max_age_days = self.ttl_hours / 24 if self.ttl_hours else 30

        with self._lock:
            results = {"removed_old": 0, "removed_size": 0, "removed_unused": 0}

            # Remove old files
            results["removed_old"] = self.clear_cache(older_than_days=max_age_days)

            # Check total size and remove least recently used if needed
            cache_files = []
            total_size = 0

            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    stat = cache_file.stat()
                    cache_files.append(
                        {"path": cache_file, "size": stat.st_size, "atime": stat.st_atime}
                    )
                    total_size += stat.st_size
                except:
                    pass

            # Convert to MB
            total_size_mb = total_size / (1024 * 1024)

            if total_size_mb > max_size_mb:
                # Sort by access time (least recently used first)
                cache_files.sort(key=lambda x: x["atime"])

                # Remove files until under size limit
                for file_info in cache_files:
                    if total_size_mb <= max_size_mb:
                        break

                    try:
                        file_info["path"].unlink()
                        total_size_mb -= file_info["size"] / (1024 * 1024)
                        results["removed_size"] += 1
                    except:
                        pass

            # Remove files that haven't been accessed
            if self.metadata and "files" in self.metadata:
                for file_name, file_info in list(self.metadata["files"].items()):
                    if file_info.get("hits", 0) == 0:
                        cache_key = file_info.get("cache_key")
                        if cache_key:
                            cache_file = self._get_cache_filename(cache_key)
                            if cache_file.exists():
                                try:
                                    cache_file.unlink()
                                    results["removed_unused"] += 1
                                    del self.metadata["files"][file_name]
                                except:
                                    pass

            # Save updated metadata
            self._save_metadata()

            total_removed = sum(results.values())
            if total_removed > 0:
                self.logger.info(f"Cache optimization complete: {results}")
            return results

    def __del__(self):
        """Cleanup on deletion (thread-safe)."""
        if hasattr(self, "_lock") and hasattr(self, "metadata") and hasattr(self, "cache_stats"):
            try:
                with self._lock:
                    self._save_metadata()
            except:
                pass
