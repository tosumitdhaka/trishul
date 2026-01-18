#!/usr/bin/env python3
"""
Configuration Management for Trishul Tool
Centralized configuration handling with validation
"""

import base64
import json
import os
from dataclasses import asdict, dataclass, field
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from utils.logger import get_logger


def init_dataclass_from_dict(dataclass_type, config_dict: Dict[str, Any]):
    """
    Initialize a dataclass from a config dictionary.
    Only uses fields that exist in the dataclass definition.
    
    Args:
        dataclass_type: The dataclass type to initialize
        config_dict: Dictionary with configuration values
        
    Returns:
        Initialized dataclass instance
    """
    from dataclasses import fields
    
    # Get valid field names for this dataclass
    valid_fields = {f.name for f in fields(dataclass_type)}
    
    # Filter config_dict to only include valid fields
    filtered_config = {
        key: value 
        for key, value in config_dict.items() 
        if key in valid_fields
    }
    
    # Initialize dataclass with filtered config
    return dataclass_type(**filtered_config)


@dataclass
class ProjectConfig:
    """Project configuration."""
    name: str = "Trishul"
    version: str = "2.1.0"

@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = "trishul-mysql"
    port: int = 3306
    user: str = "root"
    password: str = ""
    password_base64: str = ""
    
    # Database names
    parser_db: str = "trishu_parser"  # User imported data
    jobs_db: str = "trishul_jobs"  # Job results data (temporary)
    system_db: str = "trishul_system"  # Jobs, settings, sessions
    traps_db: str = "trishul_traps"  # Traps data
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo: bool = False
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Batch settings
    batch_insert: bool = True
    import_mode: str = "replace"
    batch_size: int = 1000

@dataclass
class ParserConfig:
    """Parser configuration."""
    compiled_dir: str = "./data/compiled_mibs"
    mib_search_dirs: List[str] = field(default_factory=list)
    mib_patterns: List[str] = field(default_factory=lambda: ["", ".mib", ".txt", ".my"])
    force_compile: bool = False

    deduplication_enabled: bool = True
    deduplication_strategy: str = "smart"

@dataclass
class CacheConfig:
    """Cache configuration."""
    enabled: bool = True
    directory: str = "./data/cache"
    ttl_hours: int = 168  # 7 days
    max_size_mb: int = 500
    cleanup_on_startup: bool = False

@dataclass
class JobsConfig:
    """Jobs configuration."""
    concurrency: int = 4
    auto_refresh_interval: int = 15

@dataclass
class CleanupConfig:
    """Cleanup configuration."""
    enabled: bool = True
    retention_days: int = 30
    schedule_hour: int = 2
    schedule_minute: int = 0
    delete_data: bool = True
    keep_statuses: List[str] = field(default_factory=list)

@dataclass
class ExportConfig:
    """Export configuration."""
    export_dir: str = "./data/exports"

    chunk_size: int = 10000
    include_timestamp: bool = False
    timestamp_format: str = "%Y%m%d_%H%M%S"
    compression: Optional[str] = None  # 'gzip', 'zip', 'bz2', 'xz'

@dataclass
class UploadConfig:
    """Upload configuration."""
    upload_dir: str = "./data/uploads"
    temp_dir: str = "./data/temp"
    max_size_mb: int = 100
    max_archive_size_mb: int = 500
    max_archive_entries: int = 10000
    supported_extensions: List[str] = field(default_factory=lambda: [".mib", ".txt", ".my", ""])
    session_timeout_hours: int = 24

@dataclass
class MetricsConfig:
    """Metrics configuration."""
    directory: str = "./data/metrics"
    retention_days: int = 7
    flush_interval_sec: int = 60
    monitor_interval: int = 5

@dataclass
class TrapsConfig:
    """Traps configuration."""
    sync_strategy: str = "append" #'append', 'replace', 'newest'
    skip_synced: bool = True
    batch_size: int = 1000

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    console: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_file_size_mb: int = 10
    backup_count: int = 5

@dataclass
class WebConfig:
    """Web/API configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    api_v1_prefix: str = "/api/v1"

@dataclass
class UIConfig:
    """UI configuration."""
    data_table: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExternalLinksConfig:
    """External links configuration."""
    data_table: Dict[str, Any] = field(default_factory=dict)


class Config:
    """Centralized configuration management."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from file or defaults."""

        self.config_path = config_path or self._find_config_file()
        self.raw_config = self._load_config()

        # Initialize logger after basic setup
        self.logger = get_logger(self.__class__.__name__)

        # Initialize sub-configurations
        self.project = self._init_project_config()
        self.database = self._init_database_config()
        self.parser = self._init_parser_config()
        self.cache = self._init_cache_config()
        self.jobs = self._init_jobs_config()
        self.cleanup = self._init_cleanup_config()
        self.export = self._init_export_config()
        self.upload = self._init_upload_config()
        self.metrics = self._init_metrics_config()
        self.traps = self._init_traps_config()
        self.logging = self._init_logging_config()
        self.web = self._init_web_config()
        self.ui = self._init_ui_config()
        self.externallinks = self._init_externallinks_config()

        # Version
        self.version = self.project.version

        # Create required directories
        self._create_directories()

        self.monitoring_enabled = os.getenv('MONITORING_ENABLED', 'false').lower() == 'true'

    def reload(self):
        """
        Reload configuration from file.
        
        This reloads the config file and re-initializes all sub-configurations.
        Useful for hot-reloading config without restarting the server.
        
        Returns:
            self (for chaining)
        """
        try:
            self.logger.info(f"Reloading configuration from {self.config_path}")
            
            # Reload raw config
            self.raw_config = self._load_config()
            
            # Re-initialize all sub-configurations
            self.project = self._init_project_config()
            self.database = self._init_database_config()
            self.parser = self._init_parser_config()
            self.cache = self._init_cache_config()
            self.jobs = self._init_jobs_config()
            self.cleanup = self._init_cleanup_config()
            self.export = self._init_export_config()
            self.upload = self._init_upload_config()
            self.metrics = self._init_metrics_config()
            self.traps = self._init_traps_config()
            self.logging = self._init_logging_config()
            self.web = self._init_web_config()
            self.ui = self._init_ui_config()
            self.externallinks = self._init_externallinks_config()
            
            # Update version
            self.version = self.project.version
            
            # Re-create directories if needed
            self._create_directories()
            
            self.logger.info("✅ Configuration reloaded successfully")
            
            return self
            
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}", exc_info=True)
            raise

    def _find_config_file(self) -> str:
        """Find configuration file in standard locations."""
        search_paths = [
            Path("./config/config.yaml"),
            Path("app/config/config.yaml"),
            Path("./config.yaml"),
            Path("../config/config.yaml")
        ]

        for path in search_paths:
            if path.exists():
                return str(path)

        # Return default path
        return "./config/config.yaml"

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not os.path.exists(self.config_path):
            # Use logger if available, otherwise print
            if hasattr(self, 'logger'):
                self.logger.warning(f"Config file not found: {self.config_path}, using defaults")
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                if self.config_path.endswith((".yaml", ".yml")):
                    config = yaml.safe_load(f) or {}
                elif self.config_path.endswith(".json"):
                    config = json.load(f)
                else:
                    config = {}

                return config

        except Exception as e:
            # Use logger if available, otherwise print
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to load config: {e}", exc_info=True)
            return {}

    def _init_project_config(self) -> ProjectConfig:
        """Initialize project configuration."""
        return init_dataclass_from_dict(ProjectConfig, self.raw_config.get("project", {}))

    def _init_parser_config(self) -> ParserConfig:
        """Initialize parser configuration."""
        config = init_dataclass_from_dict(ParserConfig, self.raw_config.get("parser", {}))
        
        # Special handling: expand and filter paths
        config.mib_search_dirs = [
            os.path.abspath(os.path.expanduser(d))
            for d in config.mib_search_dirs
            if os.path.exists(os.path.expanduser(d))
        ]
        
        # Validate deduplication strategy
        valid_strategies = ["smart", "keep_first", "keep_last", "keep_all_modules", "merge", "none"]
        if config.deduplication_strategy not in valid_strategies:
            self.logger.warning(f"Invalid deduplication strategy: {config.deduplication_strategy}, using 'none'")
            config.deduplication_strategy = "none"
        
        return config

    def _init_database_config(self) -> DatabaseConfig:
        """Initialize database configuration."""
        cfg = self.raw_config.get("database", {})
        
        # Auto-initialize most fields
        config = init_dataclass_from_dict(DatabaseConfig, cfg)
        
        # Special handling: password decoding (priority order)
        if not config.password:
            # 1. Environment variable
            if os.environ.get("DB_PASSWORD"):
                config.password = os.environ["DB_PASSWORD"]
                self.logger.debug("Using database password from environment variable")
            # 2. Base64 encoded in config
            elif cfg.get("password_base64"):
                try:
                    config.password = base64.b64decode(cfg["password_base64"]).decode("utf-8")
                    self.logger.debug("Using database password from config (base64)")
                except Exception as e:
                    self.logger.warning(f"Failed to decode password: {e}")
            # 3. Password file
            elif cfg.get("password_file"):
                password_file = Path(cfg["password_file"])
                if password_file.exists():
                    config.password = password_file.read_text().strip()
        
        return config

    def _init_export_config(self) -> ExportConfig:
        """Initialize export configuration."""
        return init_dataclass_from_dict(ExportConfig, self.raw_config.get("export", {}))

    def _init_cache_config(self) -> CacheConfig:
        """Initialize cache configuration."""
        return init_dataclass_from_dict(CacheConfig, self.raw_config.get("cache", {}))

    def _init_logging_config(self) -> LoggingConfig:
        """Initialize logging configuration."""
        return init_dataclass_from_dict(LoggingConfig, self.raw_config.get("logging", {}))

    def _init_web_config(self) -> WebConfig:
        """Initialize web/API configuration."""
        return init_dataclass_from_dict(WebConfig, self.raw_config.get("web", {}))

    def _init_upload_config(self) -> UploadConfig:
        """Initialize upload configuration."""
        return init_dataclass_from_dict(UploadConfig, self.raw_config.get("upload", {}))
    
    def _init_metrics_config(self) -> MetricsConfig:
        """Initialize export configuration."""
        return init_dataclass_from_dict(MetricsConfig, self.raw_config.get("metrics", {}))
    
    def _init_traps_config(self) -> TrapsConfig:
        """Initialize traps configuration."""
        return init_dataclass_from_dict(TrapsConfig, self.raw_config.get("traps", {}))

    def _init_jobs_config(self) -> JobsConfig:
        """Initialize jobs configuration."""
        return init_dataclass_from_dict(JobsConfig, self.raw_config.get("jobs", {}))

    def _init_cleanup_config(self) -> CleanupConfig:
        """Initialize cleanup configuration."""
        return init_dataclass_from_dict(CleanupConfig, self.raw_config.get("cleanup", {}))

    def _init_ui_config(self) -> UIConfig:
        """Initialize UI configuration."""
        return init_dataclass_from_dict(UIConfig, self.raw_config.get("ui", {}))

    def _init_externallinks_config(self) -> ExternalLinksConfig:
        """Initialize external links configuration."""
        return init_dataclass_from_dict(ExternalLinksConfig, self.raw_config.get("external_links", {}))

    def _create_directories(self):
        """Create required directories if they don't exist."""
        directories = [
            self.parser.compiled_dir,
            self.cache.directory,
            self.export.export_dir,
            self.upload.upload_dir,
            self.metrics.directory,
            self.upload.temp_dir,
        ]

        if self.logging.file:
            directories.append(os.path.dirname(self.logging.file))

        for directory in directories:
            if directory:
                try:
                    Path(directory).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.logger.warning(f"Failed to create directory {directory}: {e}")

    def get_database_password(self, prompt: bool = True) -> str:
        """
        Get database password, prompting if necessary.

        Args:
            prompt: Whether to prompt for password if not configured

        Returns:
            Database password
        """
        if self.database.password:
            return self.database.password

        if prompt:
            password = getpass(f"Enter password for {self.database.user}@{self.database.host}: ")
            self.database.password = password
            return password

        return ""

    def get_all_mib_search_paths(self) -> List[str]:
        """Get all MIB search paths."""
        paths = []

        # Add configured paths
        paths.extend(self.parser.mib_search_dirs)

        # Add compiled directory
        paths.append(os.path.abspath(self.parser.compiled_dir))

        # Add current directory
        paths.append(os.path.abspath("."))

        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            if p not in seen and os.path.exists(p):
                unique_paths.append(p)
                seen.add(p)

        return unique_paths

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "version": self.version,
            "project": asdict(self.project),
            "database": {
                **asdict(self.database),
                "password": "***" if self.database.password else "",
            },
            "parser": asdict(self.parser),
            "cache": asdict(self.cache),
            "jobs": asdict(self.jobs),
            "cleanup": asdict(self.cleanup),
            "export": asdict(self.export),
            "upload": asdict(self.upload),
            "logging": asdict(self.logging),
            "web": asdict(self.web),
            "ui": asdict(self.ui),
        }

    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        save_path = path or self.config_path

        # Convert to dict for saving
        config_dict = self.to_dict()

        # Encode password if present
        if self.database.password:
            config_dict["database"]["password_base64"] = base64.b64encode(
                self.database.password.encode()
            ).decode("utf-8")
            del config_dict["database"]["password"]

        # Save to file
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

        self.logger.info(f"Configuration saved to {save_path}")

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of issues.

        Returns:
            List of validation issues (empty if valid)
        """
        issues = []

        # Check database configuration
        if self.database.host and not self.database.system_db:
            issues.append("Database name not specified")

        # Check if at least one search path exists
        if not self.get_all_mib_search_paths():
            issues.append("No valid MIB search paths found")

        # Check export directory is writable
        try:
            Path(self.export.export_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create export directory: {e}")

        # Check cache directory is writable
        try:
            Path(self.cache.directory).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create cache directory: {e}")

        # Validate chunk sizes
        if self.export.chunk_size < 100:
            issues.append("Export chunk size too small (minimum 100)")

        return issues

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"Config(version={self.project.version})"

    def __repr__(self) -> str:
        """Detailed representation of configuration."""
        return (
            f"Config(\n"
            f"  project={self.project.name},\n"
            f"  version={self.project.version},\n"
            f"  log_level={self.logging.level},\n"
            f"  database={self.database.host}:{self.database.port},\n"
            f"  cache={'enabled' if self.cache.enabled else 'disabled'},\n"
            f")"
        )
