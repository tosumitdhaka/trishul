"""
Database Initialization Module - Optimized
Handles creation and initialization of all databases at application startup
"""

from typing import Any, Dict

import pymysql

from services.config_service import Config
from services.db_service import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseInitializer:
    """
    Handles initialization of all application databases
    
    Responsibilities:
    1. Create databases if they don't exist
    2. Create system tables (jobs, settings, sessions, audit_logs, trap_sync_status)
    3. Create trap tables (templates, sent, received)
    4. Create trap_master_data table in user database
    5. Initialize DatabaseManager
    6. Verify connections
    """
    
    def __init__(self, config: Config):
        """
        Initialize database initializer
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.db_manager = None
        self.connection = None
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize all databases and return status
        
        Returns:
            Dict with initialization status and db_manager instance
        """
        # logger.info("=" * 70)
        logger.info("Database Initialization")
        # logger.info("=" * 70)
        
        try:
            # Get database credentials
            password = self.config.database.password
            if not password:
                logger.warning("No database password configured")
                password = ""
            
            # Connect to MySQL server
            logger.info(
                f"Connecting to MySQL at {self.config.database.host}:{self.config.database.port}"
            )
            
            self.connection = pymysql.connect(
                host=self.config.database.host,
                port=self.config.database.port,
                user=self.config.database.user,
                password=password,
                charset="utf8mb4",
                connect_timeout=10,
            )
            
            cursor = self.connection.cursor()
            
            # Initialize databases
            results = {
                "data_db": self._init_data_database(cursor),
                "system_db": self._init_system_database(cursor),
                "jobs_db": self._init_jobs_database(cursor),
                "traps_db": self._init_traps_database(cursor),

            }
            
            # Commit changes
            self.connection.commit()
            
            # Close MySQL connection
            cursor.close()
            self.connection.close()
            self.connection = None
            
            # Initialize DatabaseManager
            logger.info("Initializing database manager...")
            self.db_manager = DatabaseManager(self.config)
            
            # Health check
            health = self._health_check()
            
            # Summary
            # logger.info("=" * 70)
            all_success = all(results.values())
            
            if all_success:
                logger.info("✅ All databases initialized successfully")
            else:
                logger.warning("⚠️  Some databases failed to initialize")
                for db_name, success in results.items():
                    status = "✅" if success else "❌"
                    logger.info(f"  {status} {db_name}")
            
            # logger.info("=" * 70)
            
            return {
                "success": all_success,
                "results": results,
                "db_manager": self.db_manager,
                "health": health,
            }
        
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
            
            # Cleanup on failure
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            
            return {
                "success": False,
                "error": str(e),
                "db_manager": None,
                "health": {}
            }
    
    def _init_data_database(self, cursor) -> bool:
        """
        Initialize data database (user imported data)
        
        Args:
            cursor: MySQL cursor
        
        Returns:
            True if successful
        """
        data_db = self.config.database.parser_db
        logger.info(f"Initializing data database: {data_db}")
        
        try:
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{data_db}`
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
            )
            
            logger.info(f"  ✅ {data_db} ready")
            
            # Use database
            cursor.execute(f"USE `{data_db}`")

            # Create trap_master_data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trap_master_data (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    
                    -- ✅ NEW: Top-level node type
                    node_type VARCHAR(50),

                    notification_name VARCHAR(255) NOT NULL DEFAULT '',
                    notification_oid VARCHAR(512),
                    notification_status VARCHAR(50),
                    notification_description TEXT,
                    notification_module VARCHAR(255),
                    notification_enterprise VARCHAR(255),
                    notification_type VARCHAR(50),
                    
                    object_sequence INT,
                    
                    object_name VARCHAR(255) NOT NULL DEFAULT '',
                    object_oid VARCHAR(512),
                    object_node_type VARCHAR(50),
                    object_syntax VARCHAR(100),
                    object_access VARCHAR(50),
                    object_status VARCHAR(50),
                    object_description TEXT,
                    object_units VARCHAR(100),
                    object_reference TEXT,
                    
                    tc_name VARCHAR(255),
                    tc_base_type VARCHAR(100),
                    tc_display_hint VARCHAR(100),
                    tc_status VARCHAR(50),
                    tc_description TEXT,
                    tc_enumerations JSON,
                    tc_constraints VARCHAR(255),
                    tc_resolution_chain TEXT,
                    
                    table_indexes TEXT,
                    augments_table VARCHAR(255),
                    parent_name VARCHAR(255),
                    parent_oid VARCHAR(512),
                    parent_type VARCHAR(50),
                    
                    source_table VARCHAR(255) NOT NULL,
                    module_name VARCHAR(255) NOT NULL,
                    module_revision VARCHAR(50),
                    source_file VARCHAR(255),
                    mib_imports TEXT,
                    
                    processed_at TIMESTAMP NULL,
                    parser_version VARCHAR(20),
                    imported_at TIMESTAMP NULL,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- ✅ Unique constraint on (notification_name, object_name, module_name)
                    UNIQUE KEY idx_unique_key (
                        notification_name,
                        object_name,
                        module_name
                    ),
                    
                    KEY idx_node_type (node_type),
                    KEY idx_notification_oid (notification_oid),
                    KEY idx_notification_name (notification_name),
                    KEY idx_object_oid (object_oid(255)),
                    KEY idx_object_name (object_name),
                    KEY idx_object_node_type (object_node_type),
                    KEY idx_module_name (module_name),
                    KEY idx_source_table (source_table),
                    KEY idx_imported_at (imported_at),
                    KEY idx_sequence (notification_oid, object_sequence),
                    
                    FULLTEXT KEY idx_fulltext_notif (notification_name, notification_description),
                    FULLTEXT KEY idx_fulltext_obj (object_name, object_description)
                    
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            logger.info(f"  ✅ trap_master_data table ready in {data_db}")
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Failed to initialize {data_db}: {e}")
            return False
    
    def _init_system_database(self, cursor) -> bool:
        """
        Initialize system database (jobs metadata, settings, sessions, trap_sync_status)
        
        Args:
            cursor: MySQL cursor
        
        Returns:
            True if successful
        """
        system_db = self.config.database.system_db
        logger.info(f"Initializing system database: {system_db}")
        
        try:
            # Create database
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{system_db}`
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
            )
            
            # Use database
            cursor.execute(f"USE `{system_db}`")
            
            # Create jobs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id VARCHAR(36) PRIMARY KEY,
                    job_type VARCHAR(50) NOT NULL,
                    job_name VARCHAR(255),
                    status VARCHAR(20) NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    progress INT DEFAULT 0,
                    message TEXT,
                    result_data JSON,
                    errors JSON,
                    metadata JSON,
                    INDEX idx_created_at (created_at),
                    INDEX idx_status (status),
                    INDEX idx_job_type (job_type),
                    INDEX idx_completed_at (completed_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            )
            
            # Create settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_value JSON NOT NULL,
                    category VARCHAR(50),
                    description TEXT,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_category (category)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            )
            
            # Create upload_sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_sessions (
                    session_id VARCHAR(36) PRIMARY KEY,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    files_count INT DEFAULT 0,
                    total_size BIGINT DEFAULT 0,
                    metadata JSON,
                    INDEX idx_created_at (created_at),
                    INDEX idx_expires_at (expires_at),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            )
            
            # Create audit_logs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    action VARCHAR(50) NOT NULL,
                    user_id VARCHAR(50),
                    details JSON,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_action (action),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            )
            
            # ✅ NEW: Create trap_sync_status table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trap_sync_status (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    
                    table_name VARCHAR(255) NOT NULL UNIQUE,
                    
                    last_sync_at TIMESTAMP NULL,
                    rows_synced INT DEFAULT 0,
                    rows_inserted INT DEFAULT 0,
                    rows_updated INT DEFAULT 0,
                    rows_skipped INT DEFAULT 0,
                    notifications_count INT DEFAULT 0,
                    objects_count INT DEFAULT 0,
                    
                    duplicates_skipped INT DEFAULT 0,
                    duplicates_replaced INT DEFAULT 0,
                    
                    sync_method VARCHAR(50),
                    dedup_strategy VARCHAR(50),
                    
                    sync_status VARCHAR(50) DEFAULT 'pending',
                    error_message TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    INDEX idx_sync_status (sync_status),
                    INDEX idx_last_sync (last_sync_at)
                    
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            )
            
            logger.info(f"  ✅ {system_db} ready (5 tables created)")
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Failed to initialize {system_db}: {e}")
            return False
    
    def _init_jobs_database(self, cursor) -> bool:
        """
        Initialize jobs database (job result tables)
        
        Args:
            cursor: MySQL cursor
        
        Returns:
            True if successful
        """
        jobs_db = self.config.database.jobs_db
        logger.info(f"Initializing jobs database: {jobs_db}")
        
        try:
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{jobs_db}`
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
            )
            
            logger.info(f"  ✅ {jobs_db} ready")
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Failed to create {jobs_db}: {e}")
            return False
    
    def _init_traps_database(self, cursor) -> bool:
        """
        Initialize traps database (trap templates, sent, received)
        
        Args:
            cursor: MySQL cursor
        
        Returns:
            True if successful
        """
        traps_db = self.config.database.traps_db
        logger.info(f"Initializing traps database: {traps_db}")
        
        try:
            # Create database
            cursor.execute(
                f"""
                CREATE DATABASE IF NOT EXISTS `{traps_db}`
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
            )
            
            # Use database
            cursor.execute(f"USE `{traps_db}`")
            
            # Table 1: Trap Templates
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trap_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    trap_oid VARCHAR(255) NOT NULL,
                    trap_name VARCHAR(255),
                    trap_description TEXT,
                    enterprise_oid VARCHAR(255),
                    varbinds JSON,
                    snmp_version VARCHAR(10) DEFAULT 'v2c',
                    community VARCHAR(100) DEFAULT 'public',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_trap_oid (trap_oid),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Table 2: Sent Traps History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sent_traps (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    template_id INT,
                    trap_oid VARCHAR(255) NOT NULL,
                    trap_name VARCHAR(255),
                    trap_description TEXT,
                    target_host VARCHAR(255) NOT NULL,
                    target_port INT DEFAULT 1162,
                    snmp_version VARCHAR(10) DEFAULT 'v2c',
                    community VARCHAR(100),
                    varbinds JSON,
                    status VARCHAR(20),
                    error_message TEXT,
                    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_sent_at (sent_at),
                    INDEX idx_status (status),
                    INDEX idx_target_host (target_host),
                    INDEX idx_trap_oid (trap_oid),
                    INDEX idx_trap_name (trap_name),
                    FOREIGN KEY (template_id) REFERENCES trap_templates(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Table 3: Received Traps
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS received_traps (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_ip VARCHAR(45) NOT NULL,
                    source_port INT,
                    trap_oid VARCHAR(255) NOT NULL,
                    trap_name VARCHAR(255),
                    trap_description TEXT,
                    enterprise_oid VARCHAR(255),
                    timestamp VARCHAR(50),
                    varbinds JSON,
                    snmp_version VARCHAR(10),
                    community VARCHAR(100),
                    raw_data TEXT,
                    received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_received_at (received_at),
                    INDEX idx_source_ip (source_ip),
                    INDEX idx_trap_oid (trap_oid),
                    INDEX idx_trap_name (trap_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Table 4: SNMP Devices (inventory)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snmp_devices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    ip_address VARCHAR(45) NOT NULL,
                    snmp_community VARCHAR(100) DEFAULT 'public',
                    snmp_port INT DEFAULT 161,
                    enabled BOOLEAN DEFAULT TRUE,
                    description TEXT,
                    location VARCHAR(255),
                    contact VARCHAR(255),
                    device_type VARCHAR(100),
                    vendor VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_ip (ip_address),
                    INDEX idx_enabled (enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Table 5: SNMP Walk Configurations (reusable)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snmp_walk_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    base_oid VARCHAR(512) NOT NULL,
                    walk_type VARCHAR(50) DEFAULT 'custom',
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_name (name),
                    INDEX idx_walk_type (walk_type),
                    INDEX idx_enabled (enabled)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Table 6: SNMP Walk Results (collected data)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snmp_walk_results (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    
                    device_id INT NOT NULL,
                    device_name VARCHAR(255) NOT NULL,
                    device_ip VARCHAR(45) NOT NULL,
                    
                    config_id INT,
                    config_name VARCHAR(255),
                    base_oid VARCHAR(512) NOT NULL,
                    walk_type VARCHAR(50),
                    
                    oid VARCHAR(512) NOT NULL,
                    oid_index VARCHAR(255),
                    value TEXT,
                    value_type VARCHAR(50),
                    
                    oid_name VARCHAR(255),
                    oid_description TEXT,
                    oid_syntax VARCHAR(100),
                    oid_module VARCHAR(255),
                    resolved BOOLEAN DEFAULT FALSE,
                    
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    job_id VARCHAR(36),
                    
                    INDEX idx_device (device_id, device_name),
                    INDEX idx_device_ip (device_ip),
                    INDEX idx_config (config_id),
                    INDEX idx_base_oid (base_oid(255)),
                    INDEX idx_oid (oid(255)),
                    INDEX idx_collected (collected_at),
                    INDEX idx_job (job_id),
                    INDEX idx_resolved (resolved),
                    
                    FOREIGN KEY (device_id) REFERENCES snmp_devices(id) ON DELETE CASCADE,
                    FOREIGN KEY (config_id) REFERENCES snmp_walk_configs(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            logger.info(f"  ✅ {traps_db} ready (6 tables created)")  # Update count

            return True
        
        except Exception as e:
            logger.error(f"  ❌ Failed to initialize {traps_db}: {e}")
            return False

    def _health_check(self) -> Dict[str, Any]:
        """
        Check health of all databases
        
        Returns:
            Health status for each database
        """
        if not self.db_manager:
            return {}
        
        try:
            return self.db_manager.health_check()
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return {}
    
    async def cleanup(self):
        """Cleanup database connections"""
        logger.info("Cleaning up database connections...")
        
        try:
            # Close MySQL connection if still open
            if self.connection:
                self.connection.close()
                logger.info("  ✅ MySQL connection closed")
            
            # Close database manager
            if self.db_manager:
                self.db_manager.close()
                logger.info("  ✅ Database manager closed")
        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# ============================================
# Convenience functions for use in main.py
# ============================================

async def initialize_databases(config: Config) -> Dict[str, Any]:
    """
    Initialize all databases
    
    Args:
        config: Application configuration
    
    Returns:
        Dict with initialization status and db_manager instance
    
    Example:
        >>> result = await initialize_databases(config)
        >>> if result['success']:
        >>>     db_manager = result['db_manager']
    """
    initializer = DatabaseInitializer(config)
    return await initializer.initialize()


async def cleanup_databases(db_manager):
    """
    Cleanup database connections
    
    Args:
        db_manager: Database manager instance
    
    Example:
        >>> await cleanup_databases(db_manager)
    """
    if db_manager:
        try:
            db_manager.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
