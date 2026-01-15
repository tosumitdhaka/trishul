#!/usr/bin/env python3
"""
Database Manager - Restructured and Unified
Handles all database operations across 3 databases with DataFrame support
"""

import json
import re
import time
import pandas as pd
import warnings
from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

# SQLAlchemy imports
try:
    from sqlalchemy import (
        create_engine,
        inspect,
        text
    )
    from sqlalchemy.exc import OperationalError
except ImportError as e:
    print(f"[ERROR] SQLAlchemy not installed: {e}")
    print("[INFO] Install with: pip install sqlalchemy pymysql")
    raise

from utils.logger import get_logger

from backend.services.metrics_service import get_metrics_service

# Suppress SQLAlchemy warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sqlalchemy")


def retry_on_connection_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry database operations on connection errors."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            f"Connection error (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}"
                        )
                        time.sleep(delay * (attempt + 1))
                        if not self._test_connection():
                            self._reconnect()
                    else:
                        self.logger.error(f"Failed after {max_retries} attempts: {str(e)[:100]}")
                        raise
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class DatabaseManager:
    """
    Unified Database Manager for MIB Tool

    Manages 3 databases:
    - data_db (mib_tool): User imported data (long-term storage)
    - system_db (mib_tool_system): Jobs metadata, settings, sessions
    - jobs_db (mib_tool_jobs): Temporary job results (auto-cleanup)

    DataFrame is the universal data format:
    - Parser outputs DataFrame
    - DatabaseManager works with DataFrames
    - Exporter takes DataFrames
    """

    # Class-level constants
    MAX_IDENTIFIER_LENGTH = 64
    MAX_VARCHAR_LENGTH = 65535
    DEFAULT_CHUNK_SIZE = 10000
    RESERVED_WORDS = {"select", "from", "where", "table", "database", "index", "order", "group"}

    def __init__(self, config):
        """
        Initialize database manager.

        Args:
            config: Configuration object with database settings
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

        self._executor = ThreadPoolExecutor(max_workers=2)

        # Optimized settings
        self.chunk_size = getattr(config.export, "chunk_size", self.DEFAULT_CHUNK_SIZE)
        self.use_batch_insert = True

        # Connection retry settings
        self.max_retries = 3
        self.retry_delay = 1.0

        # Statistics
        self.stats = {
            "tables_created": 0,
            "rows_inserted": 0,
            "rows_retrieved": 0,
            "queries_executed": 0,
            "failed_queries": 0,
            "errors": 0,
            "reconnections": 0,
            "last_error": None,
            "last_operation": None,
        }

        # Performance tracking
        self._operation_times = []

        # ✅ Database configuration mapping
        self.db_configs = {
            'data': {
                'name': getattr(self.config.database, "parser_db", "trishul_parser"),
                'engine_attr': 'data_engine'
            },
            'system': {
                'name': getattr(self.config.database, "system_db", "trishul_system"),
                'engine_attr': 'system_engine'
            },
            'jobs': {
                'name': getattr(self.config.database, "jobs_db", "trishul_jobs"),
                'engine_attr': 'jobs_engine'
            },
            'traps': {
                'name': getattr(self.config.database, "traps_db", "trishul_traps"),
                'engine_attr': 'traps_engine'
            }
        }

        # Database engines
        self.data_engine = None  
        self.system_engine = None  
        self.jobs_engine = None  
        self.traps_engine = None 

        self.connected = False

        # Initialize connections
        if config.database.host:
            self._init_engines()

    # ============================================
    # ENGINE INITIALIZATION
    # ============================================
    
    def _init_engines(self):
        """Initialize all database engines with deduplication."""
        try:
            password = self.config.get_database_password(prompt=True)
            
            # Track unique database names to their engines
            db_name_to_engine = {}
            
            # Create engines only for unique database names
            for db_type, db_config in self.db_configs.items():
                db_name = db_config['name']
                engine_attr = db_config['engine_attr']
                
                # Reuse existing engine if database name already processed
                if db_name in db_name_to_engine:
                    setattr(self, engine_attr, db_name_to_engine[db_name])
                    self.logger.debug(f"Reusing engine for {db_type} DB: {db_name}")
                else:
                    # Create new engine
                    engine = self._create_engine(db_name, password)
                    setattr(self, engine_attr, engine)
                    db_name_to_engine[db_name] = engine
                    self.logger.debug(f"Created new engine for {db_type} DB: {db_name}")
            
            # Test connections
            if self._test_all_connections():
                self.connected = True
                self.logger.info("✅ All database engines initialized successfully")
                for db_type, db_config in self.db_configs.items():
                    self.logger.info(f"   {db_type.capitalize()} DB: {db_config['name']}")
            else:
                raise ConnectionError("Failed to establish database connections")
                
        except Exception as e:
            self.logger.error(f"Engine initialization failed: {str(e)[:200]}")
            self.connected = False
            self.stats["last_error"] = str(e)
            raise

    def _create_engine(self, database: str, password: str):
        """
        Create SQLAlchemy engine for specified database.
        
        Args:
            database: Database name
            password: Database password
        
        Returns:
            SQLAlchemy engine
        """
        connection_string = self._build_connection_string(database, password)
        
        engine = create_engine(
            connection_string,
            pool_size=self.config.database.pool_size,
            max_overflow=self.config.database.max_overflow,
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
            connect_args={"connect_timeout": 10, "charset": "utf8mb4"},
        )
        
        # Test connection and create database if needed
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.debug(f"Connected to database: {database}")
        except Exception as e:
            if "Unknown database" in str(e):
                self.logger.info(f"Database '{database}' not found. Creating...")
                if self._create_database(database, password):
                    # Recreate engine after database creation
                    engine = create_engine(
                        connection_string,
                        pool_size=self.config.database.pool_size,
                        max_overflow=self.config.database.max_overflow,
                        pool_timeout=30,
                        pool_pre_ping=True,
                        pool_recycle=3600,
                        echo=False,
                        connect_args={"connect_timeout": 10, "charset": "utf8mb4"},
                    )
                else:
                    raise
            else:
                raise
        
        return engine

    def _build_connection_string(self, database: str, password: str) -> str:
        """Build SQLAlchemy connection string."""
        driver = self._detect_mysql_driver()
        password_encoded = quote_plus(password)
        
        return (
            f"mysql+{driver}://{self.config.database.user}:{password_encoded}@"
            f"{self.config.database.host}:{self.config.database.port}/"
            f"{database}?charset=utf8mb4"
        )

    def _detect_mysql_driver(self) -> str:
        """Detect available MySQL driver."""
        drivers = [
            ("pymysql", "pymysql"),
            ("MySQLdb", "mysqldb"),
            ("mysql.connector", "mysqlconnector"),
        ]
        
        for module_name, driver_name in drivers:
            try:
                __import__(module_name)
                return driver_name
            except ImportError:
                continue
        
        raise ImportError("No MySQL driver found. Please install: pip install pymysql")

    def _create_database(self, database: str, password: str) -> bool:
        """Create database if it doesn't exist."""
        # Validate database name to prevent SQL injection
        if not re.match(r'^[a-zA-Z0-9_]+$', database):
            self.logger.error(f"Invalid database name: {database}")
            return False
        
        connection = None
        try:
            import pymysql
            
            connection = pymysql.connect(
                host=self.config.database.host,
                port=self.config.database.port,
                user=self.config.database.user,
                password=password,
                charset="utf8mb4",
            )
            
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE DATABASE IF NOT EXISTS `{database}`
                    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                connection.commit()
            
            self.logger.info(f"Database '{database}' created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database creation failed: {str(e)[:200]}")
            return False
        finally:
            if connection:
                connection.close()

    # ============================================
    # UTILITY METHODS
    # ============================================

    def health_check(self) -> Dict[str, Any]:
        """Check health of all databases."""
        health = {}
        
        # ✅ Dynamically check all configured databases
        for db_type, db_config in self.db_configs.items():
            db_key = f"{db_type}_db"
            health[db_key] = {"status": "unknown", "error": None}
            
            try:
                engine = getattr(self, db_config['engine_attr'], None)
                
                if self.connected and engine:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    health[db_key]["status"] = "healthy"
                elif engine:
                    health[db_key]["status"] = "not_connected"
                else:
                    health[db_key]["status"] = "not_initialized"
                    
            except Exception as e:
                health[db_key]["status"] = "unhealthy"
                health[db_key]["error"] = str(e)[:100]
        
        return health

    def get_statistics(self) -> Dict[str, Any]:
        """Get database manager statistics."""
        stats = self.stats.copy()
        
        if self.connected:
            stats["connected"] = True
            
            # ✅ Dynamically build databases dict
            stats["databases"] = {}
            for db_type, db_config in self.db_configs.items():
                stats["databases"][db_type] = db_config['name']
        else:
            stats["connected"] = False
        
        return stats

    def is_healthy(self) -> bool:
        """
        Check if all connections are healthy.
        
        Returns:
            bool: True if all connections are healthy
        """
        if not self.connected:
            return False
        
        try:
            return self._test_all_connections()
        except Exception:
            return False

    def close(self):
        """Close all database connections gracefully."""
        try:
            # ✅ Shutdown thread pool executor
            if hasattr(self, '_executor') and self._executor:
                self._executor.shutdown(wait=True)
                self.logger.debug("Thread pool executor closed")
            
            # ✅ Dispose only unique engines
            disposed_ids = set()
            for db_config in self.db_configs.values():
                engine = getattr(self, db_config['engine_attr'], None)
                if engine and id(engine) not in disposed_ids:
                    engine.dispose()
                    disposed_ids.add(id(engine))
                    self.logger.debug(f"Engine closed for {db_config['name']}")
            
            self.connected = False
            self.logger.info("✅ All database connections closed")
            
        except Exception as e:
            self.logger.error(f"Error closing database connections: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.close()
        except Exception:
            pass


    # ============================================
    # CONNECTION TESTING & MANAGEMENT
    # ============================================
    
    def _test_connection(self, engine=None) -> bool:
        """Test if database connection is alive."""
        if engine is None:
            engine = self.data_engine
        
        if not engine:
            return False
        
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _test_all_connections(self) -> bool:
        """Test all database connections."""
        # Track unique engines to avoid testing the same engine multiple times
        tested_engine_ids = set()
        
        for db_config in self.db_configs.values():
            engine = getattr(self, db_config['engine_attr'], None)
            if engine:
                engine_id = id(engine)
                if engine_id not in tested_engine_ids:
                    if not self._test_connection(engine):
                        return False
                    tested_engine_ids.add(engine_id)
        
        return True

    def _reconnect(self) -> bool:
        """Attempt to reconnect to databases."""
        self.logger.info("Attempting to reconnect...")
        self.stats["reconnections"] += 1
        
        # Store old engines
        old_engines = {}
        for db_config in self.db_configs.values():
            engine_attr = db_config['engine_attr']
            old_engines[engine_attr] = getattr(self, engine_attr, None)
        
        try:
            self._init_engines()
            
            # Dispose old engines (only unique ones)
            disposed_ids = set()
            for engine in old_engines.values():
                if engine and id(engine) not in disposed_ids:
                    engine.dispose()
                    disposed_ids.add(id(engine))
            
            return True
        except Exception as e:
            self.logger.error(f"Reconnection failed: {str(e)[:100]}")
            
            # Restore old engines
            for engine_attr, engine in old_engines.items():
                setattr(self, engine_attr, engine)
            
            return False

    def _get_engine(self, database: str):
        """
        Get SQLAlchemy engine for specified database.
        
        Args:
            database: 'data', 'system', 'jobs', or 'traps'
        
        Returns:
            SQLAlchemy engine or None
        """
        if database in self.db_configs:
            engine_attr = self.db_configs[database]['engine_attr']
            return getattr(self, engine_attr, None)
        
        valid_dbs = ', '.join(self.db_configs.keys())
        self.logger.error(f"Invalid database: {database}. Must be one of: {valid_dbs}")
        return None

    @contextmanager
    def _get_connection(self, database: str = "data"):
        """Context manager for database connections."""
        engine = self._get_engine(database)
        if not engine:
            raise ValueError(f"Invalid database: {database}")
        
        conn = None
        try:
            conn = engine.connect()
            yield conn
        finally:
            if conn:
                conn.close()

    # ============================================
    # CORE DATAFRAME OPERATIONS
    # ============================================

    @retry_on_connection_error(max_retries=3)
    def df_to_db(
        self, df: pd.DataFrame, table: str, database: str = "data", mode: str = "replace"
    ) -> bool:
        """
        Save DataFrame to specified database.

        Args:
            df: DataFrame to save
            table: Table name
            database: Which database ('data', 'system', 'jobs')
            mode: 'replace', 'append', or 'fail'

        Returns:
            True if successful

        Examples:
            # Save to user data database
            db.df_to_db(df, 'my_table', database='data')

            # Save to jobs database
            db.df_to_db(df, 'job_abc123_data', database='jobs')
        """

        if not self.connected:
            self.logger.error("Database not connected")
            return False

        if df is None or df.empty:
            self.logger.warning("Empty DataFrame, nothing to store")
            return False

        # Get engine
        engine = self._get_engine(database)
        if not engine:
            return False

        operation_start = time.time()
        metrics = get_metrics_service()

        try:
            # Validate table name
            table = self._sanitize_table_name(table)
            if not self._validate_table_name(table):
                raise ValueError(f"Invalid table name: {table}")

            table_rows = len(df)

            self.logger.info(f"Preparing {table_rows:,} records for {database}.{table}...")

            # Prepare DataFrame
            df = self._prepare_dataframe(df.copy())

            # Check existing table
            table_exists = self.table_exists(table, database)

            if table_exists and mode == "fail":
                raise ValueError(f"Table '{table}' already exists and mode is 'fail'")

            # Create table structure if needed
            if mode == "replace" or not table_exists:
                self._create_optimized_table(table, df, engine)

            # Insert data
            if self.use_batch_insert and table_rows > self.chunk_size:
                self._batch_insert(df, table, mode if not table_exists else "append", engine)
            else:
                df.to_sql(
                    name=table,
                    con=engine,
                    if_exists="append" if table_exists and mode != "replace" else mode,
                    index=False,
                    method="multi",
                    chunksize=self.chunk_size,
                )

            # Create indexes for new tables
            if mode == "replace" or not table_exists:
                self._create_indexes(table, df, engine)

            # Update statistics
            self.stats["rows_inserted"] += table_rows
            if not table_exists:
                self.stats["tables_created"] += 1

            # Track performance
            operation_time = time.time() - operation_start
            rows_per_sec = table_rows / operation_time if operation_time > 0 else 0
            self._track_operation("df_to_db", operation_time, table_rows)

            if metrics:
                metrics.counter('app_db_queries_total', {'database': database, 'operation': 'insert', 'status': 'success'})
                metrics.gauge_set('app_db_query_duration_seconds', round(operation_time, 3), {'database': database, 'operation': 'insert'})
                metrics.counter_add('app_db_query_duration_total_seconds', round(operation_time, 3), {'database': database, 'operation': 'insert'})

            self.logger.info(
                f"✅ Stored {table_rows:,} rows in {database}.{table} "
                f"({operation_time:.2f}s, {rows_per_sec:.0f} rows/sec)"
            )

            return True

        except Exception as e:
            if metrics:
                metrics.counter('app_db_queries_total', {'database': database, 'operation': 'insert', 'status': 'failed'})

            self.logger.error(f"Failed to store data in {database}.{table}: {str(e)[:200]}")
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return False

    @retry_on_connection_error(max_retries=3)
    def db_to_df(
        self,
        table: str,
        database: str = "data",
        query: str = None,
        filters: Dict = None,
        columns: List[str] = None,
        limit: int = None,
        offset: int = None,
        sort_by: str = None,
        sort_order: str = "asc",
    ) -> pd.DataFrame:
        """
        Retrieve DataFrame from specified database.

        Args:
            table: Table name
            database: Which database ('data', 'system', 'jobs')
            query: Custom SQL query (overrides table)
            filters: Filter conditions
            columns: Columns to select
            limit: Max records
            offset: Offset for pagination
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'

        Returns:
            DataFrame with retrieved data

        Examples:
            # Get from user data database
            df = db.db_to_df('my_table', database='data', limit=100)

            # Get from jobs database
            df = db.db_to_df('job_abc123_data', database='jobs')

            # Get with filters and sorting
            df = db.db_to_df('my_table', database='data',
                            filters={'status': 'current'},
                            sort_by='object_name',
                            limit=50, offset=0)
        """
        if not self.connected:
            self.logger.error("Database not connected")
            return pd.DataFrame()

        # Get engine
        engine = self._get_engine(database)
        if not engine:
            return pd.DataFrame()

        operation_start = time.time()
        metrics = get_metrics_service()

        try:
            if query:
                sql = query
                params = {}
            else:
                sql, params = self._build_select_query(
                    table, filters, columns, limit, offset, sort_by, sort_order
                )

            # Read data
            df = pd.read_sql_query(text(sql), engine, params=params)

            # Update statistics
            self.stats["rows_retrieved"] += len(df)
            self.stats["queries_executed"] += 1

            # Track performance
            operation_time = time.time() - operation_start
            self._track_operation("db_to_df", operation_time, len(df))

            if metrics:
                metrics.counter('app_db_queries_total', {'database': database, 'operation': 'select', 'status': 'success'})
                metrics.gauge_set('app_db_query_duration_seconds', round(operation_time, 3), {'database': database, 'operation': 'select'})
                metrics.counter_add('app_db_query_duration_total_seconds', round(operation_time, 3), {'database': database, 'operation': 'select'})

            if len(df) > 0:
                self.logger.debug(
                    f"Retrieved {len(df):,} rows from {database}.{table} in {operation_time:.2f}s"
                )

            return df

        except Exception as e:
            if metrics:
                metrics.counter('app_db_queries_total', {'database': database, 'operation': 'select', 'status': 'failed'})

            self.logger.error(f"Query failed on {database}.{table}: {str(e)[:200]}")
            self.stats["errors"] += 1
            return pd.DataFrame()

    # ============================================
    # CONVENIENCE METHODS (Clearer Intent)
    # ============================================

    def save_to_user_db(self, df: pd.DataFrame, table: str, mode: str = "replace") -> bool:
        """
        Save DataFrame to user data database (mib_tool).

        Convenience method for: df_to_db(df, table, database='data')
        """
        return self.df_to_db(df, table, database="data", mode=mode)

    def save_to_jobs_db(self, df: pd.DataFrame, table: str, mode: str = "replace") -> bool:
        """
        Save DataFrame to jobs database (mib_tool_jobs).

        Convenience method for: df_to_db(df, table, database='jobs')
        """
        return self.df_to_db(df, table, database="jobs", mode=mode)

    def get_from_user_db(self, table: str, **kwargs) -> pd.DataFrame:
        """
        Get DataFrame from user data database (mib_tool).

        Convenience method for: db_to_df(table, database='data', **kwargs)
        """
        return self.db_to_df(table, database="data", **kwargs)

    def get_from_jobs_db(self, table: str, **kwargs) -> pd.DataFrame:
        """
        Get DataFrame from jobs database (mib_tool_jobs).

        Convenience method for: db_to_df(table, database='jobs', **kwargs)
        """
        return self.db_to_df(table, database="jobs", **kwargs)

    # ============================================
    # HIGH-LEVEL JOB METHODS
    # ============================================

    def save_job_result(self, df: pd.DataFrame, job_id: str) -> bool:
        """
        Save job result DataFrame to jobs database.

        Args:
            df: Parsed data
            job_id: Job ID

        Returns:
            True if successful

        Example:
            # In parser endpoint after parsing
            df = parser.parse_file("IF-MIB.mib")
            db.save_job_result(df, job_id="abc-123")
        """
        table_name = f"job_{job_id.replace('-', '_')}_data"
        return self.save_to_jobs_db(df, table_name, mode="replace")

    def get_job_result(self, job_id: str, limit: int = None, offset: int = None) -> pd.DataFrame:
        """
        Get job result DataFrame from jobs database.

        Args:
            job_id: Job ID
            limit: Max records
            offset: Offset for pagination

        Returns:
            DataFrame with job results

        Example:
            # In jobs endpoint to view data
            df = db.get_job_result(job_id="abc-123", limit=1000)
        """
        table_name = f"job_{job_id.replace('-', '_')}_data"
        return self.get_from_jobs_db(table_name, limit=limit, offset=offset)

    def copy_job_to_user_db(self, job_id: str, target_table: str) -> bool:
        """
        Copy job result from jobs DB to user data DB.
        
        Args:
            job_id: Job ID
            target_table: Target table name in user DB
        
        Returns:
            True if successful
        """
        # Variables
        source_table = f"job_{job_id.replace('-', '_')}_data"
        target_table = target_table
        source_db = self.config.database.jobs_db
        target_db = self.config.database.parser_db
        
        # ✅ ADD: Get metrics service
        metrics = get_metrics_service()
        operation_start = time.time()
        
        # Build Query
        create_table_sql = (
            f"CREATE TABLE {target_db}.{target_table} LIKE {source_db}.{source_table};"
        )
        copy_data_sql = (
            f"INSERT INTO {target_db}.{target_table} SELECT * FROM {source_db}.{source_table};"
        )
        
        # Execute query
        try:
            with self._get_connection("data") as conn:
                # Create table
                conn.execute(text(create_table_sql))
                
                # Track table creation
                if metrics:
                    metrics.counter('app_db_table_operations_total', {
                        'database': 'data',
                        'operation': 'create',
                        'status': 'success'
                    })
                
                # Copy data
                result = conn.execute(text(copy_data_sql))
                rows_copied = result.rowcount
                conn.commit()
                
                # Track insert operation
                operation_time = time.time() - operation_start
                if metrics:
                    metrics.counter('app_db_queries_total', {
                        'database': 'data',
                        'operation': 'insert',
                        'status': 'success'
                    })
                    metrics.gauge_set('app_db_query_duration_seconds', round(operation_time, 3), {
                        'database': 'data',
                        'operation': 'insert'
                    })
                    metrics.counter_add('app_db_query_duration_total_seconds', round(operation_time, 3), {
                        'database': 'data',
                        'operation': 'insert'
                    })
                
                # Update stats
                self.stats["rows_inserted"] += rows_copied
                self.stats["tables_created"] += 1
            
            self.logger.info(
                f"Job table: {source_table} with Job ID: {job_id}, saved to {target_db}.{target_table} "
                f"({rows_copied} rows in {operation_time:.2f}s)"
            )
            return True
            
        except Exception as e:
            # ✅ ADD: Track failure
            if metrics:
                metrics.counter('app_db_table_operations_total', {
                    'database': 'data',
                    'operation': 'create',
                    'status': 'failed'
                })
                metrics.counter('app_db_queries_total', {
                    'database': 'data',
                    'operation': 'insert',
                    'status': 'failed'
                })
            
            self.logger.error(
                f"Failed to copy {source_db}.{source_table} to {target_db}.{target_table}: {str(e)[:100]}"
            )
            return False


    # ============================================
    # TABLE OPERATIONS
    # ============================================

    def list_tables(self, database: str = "data", pattern: str = None) -> pd.DataFrame:
        """
        List all tables in specified database.

        Args:
            database: Which database ('data', 'system', 'jobs')
            pattern: Optional pattern to filter table names

        Returns:
            DataFrame with table information
        """
        if not self.connected:
            return pd.DataFrame()

        engine = self._get_engine(database)
        if not engine:
            return pd.DataFrame()

        try:
            # Get database name
            db_names = {
                "data": self.config.database.parser_db,
                "system": self.config.database.system_db,
                "jobs": self.config.database.jobs_db,
                "traps": self.config.database.traps_db,
            }
            db_name = db_names.get(database)

            sql = """
                SELECT 
                    TABLE_NAME as table_name,
                    ROUND(DATA_LENGTH/1024/1024, 2) as size_mb,
                    CREATE_TIME as created,
                    UPDATE_TIME as last_updated
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = :database
                    AND TABLE_TYPE = 'BASE TABLE'
            """

            params = {"database": db_name}

            if pattern:
                sql += " AND TABLE_NAME LIKE :pattern"
                params["pattern"] = f"%{pattern}%"

            sql += " ORDER BY TABLE_NAME"

            # Get table metadata
            tables_df = pd.read_sql_query(text(sql), engine, params=params)

            if tables_df.empty:
                return tables_df
            
            # ✅ Get accurate row counts for each table
            with self._get_connection(database) as conn:
                row_counts = []
                for table_name in tables_df['table_name']:
                    try:
                        # Get accurate count with COUNT(*)
                        count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
                        count_result = conn.execute(text(count_query))
                        row_count = count_result.scalar()
                        row_counts.append(row_count)
                    except Exception as e:
                        self.logger.warning(f"Failed to count rows for {table_name}: {e}")
                        row_counts.append(0)

            # Add accurate row counts to dataframe
            tables_df['row_count'] = row_counts

            return tables_df

        except Exception as e:
            self.logger.error(f"Failed to list tables from {database}: {str(e)[:100]}")
            return pd.DataFrame()

    def table_exists(self, table: str, database: str = "data") -> bool:
        """
        Check if table exists in specified database.

        Args:
            table: Table name
            database: Which database ('data', 'system', 'jobs')

        Returns:
            True if table exists
        """
        if not self.connected:
            return False

        engine = self._get_engine(database)
        if not engine:
            return False

        try:
            inspector = inspect(engine)
            return table in inspector.get_table_names()
        except Exception:
            return False
        
    # ============================================
    # TABLE OPERATIONS (ADDITIONAL METHODS)
    # ============================================

    @retry_on_connection_error(max_retries=3)
    def rename_table(self, old_name: str, new_name: str, database: str = "data") -> bool:
        """
        Rename a table in specified database.
        
        Args:
            old_name: Current table name
            new_name: New table name
            database: Which database ('data', 'system', 'jobs', 'traps')
        
        Returns:
            True if successful
        """
        if not self.connected:
            self.logger.error("Database not connected")
            return False
        
        try:
            # Validate table names
            if not self._validate_table_name(old_name):
                raise ValueError(f"Invalid old table name: {old_name}")
            
            if not self._validate_table_name(new_name):
                raise ValueError(f"Invalid new table name: {new_name}")
            
            # Check if old table exists
            if not self.table_exists(old_name, database):
                self.logger.error(f"Table '{old_name}' does not exist in {database}")
                return False
            
            # Check if new table already exists
            if self.table_exists(new_name, database):
                self.logger.error(f"Table '{new_name}' already exists in {database}")
                return False
            
            # Rename table
            with self._get_connection(database) as conn:
                conn.execute(text(f"RENAME TABLE `{old_name}` TO `{new_name}`"))
                conn.commit()
            
            self.logger.info(f"✅ Renamed table {database}.{old_name} to {new_name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to rename table: {str(e)[:200]}")
            self.stats["errors"] += 1
            return False


    @retry_on_connection_error(max_retries=3)
    def duplicate_table(
        self, source: str, target: str, database: str = "data", copy_data: bool = True
    ) -> bool:
        """
        Duplicate a table (structure and optionally data).
        
        Args:
            source: Source table name
            target: Target table name
            database: Which database ('data', 'system', 'jobs', 'traps')
            copy_data: Whether to copy data (default: True)
        
        Returns:
            True if successful
        """
        if not self.connected:
            self.logger.error("Database not connected")
            return False
        
        try:
            # Validate table names
            if not self._validate_table_name(source):
                raise ValueError(f"Invalid source table name: {source}")
            
            if not self._validate_table_name(target):
                raise ValueError(f"Invalid target table name: {target}")
            
            # Check if source table exists
            if not self.table_exists(source, database):
                self.logger.error(f"Source table '{source}' does not exist in {database}")
                return False
            
            # Check if target table already exists
            if self.table_exists(target, database):
                self.logger.error(f"Target table '{target}' already exists in {database}")
                return False
            
            with self._get_connection(database) as conn:
                # Create table structure
                conn.execute(text(f"CREATE TABLE `{target}` LIKE `{source}`"))
                
                # Copy data if requested
                if copy_data:
                    conn.execute(text(f"INSERT INTO `{target}` SELECT * FROM `{source}`"))
                
                conn.commit()
            
            action = "with data" if copy_data else "structure only"
            self.logger.info(f"✅ Duplicated table {database}.{source} to {target} ({action})")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to duplicate table: {str(e)[:200]}")
            self.stats["errors"] += 1
            return False


    @retry_on_connection_error(max_retries=3)
    def truncate_table(self, table: str, database: str = "data") -> bool:
        """
        Truncate a table (delete all rows, keep structure).
        
        Args:
            table: Table name
            database: Which database ('data', 'system', 'jobs', 'traps')
        
        Returns:
            True if successful
        """
        if not self.connected:
            self.logger.error("Database not connected")
            return False
        
        try:
            # Check if table exists
            if not self.table_exists(table, database):
                self.logger.error(f"Table '{table}' does not exist in {database}")
                return False
            
            with self._get_connection(database) as conn:
                conn.execute(text(f"TRUNCATE TABLE `{table}`"))
                conn.commit()
            
            self.logger.info(f"✅ Truncated table {database}.{table}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to truncate table: {str(e)[:200]}")
            self.stats["errors"] += 1
            return False

    def delete_table(self, table: str, database: str = "data", confirm: bool = False) -> bool:
        """
        Delete a table from specified database.

        Args:
            table: Table name
            database: Which database ('data', 'system', 'jobs')
            confirm: Must be True to actually delete

        Returns:
            True if successful
        """
        if not self.connected or not confirm:
            return False

        if not self.table_exists(table, database):
            self.logger.warning(f"Table '{table}' does not exist in {database}")
            return False

        try:
            with self._get_connection(database) as conn:
                conn.execute(text(f"DROP TABLE `{table}`"))
                conn.commit()

            metrics = get_metrics_service()
            if metrics:
                metrics.counter('app_db_table_operations_total', {'database': database, 'operation': 'delete', 'status': 'success'})

            self.logger.info(f"Deleted table {database}.{table}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete table {database}.{table}: {str(e)[:100]}")
            return False

    def get_table_info(self, table: str, database: str = "data") -> pd.DataFrame:
        """Get table information."""
        if not self.connected or not self.table_exists(table, database):
            return pd.DataFrame()

        engine = self._get_engine(database)
        if not engine:
            return pd.DataFrame()

        try:
            db_names = {
                "data": self.config.database.parser_db,
                "system": self.config.database.system_db,
                "jobs": self.config.database.jobs_db,
                "traps": self.config.database.traps_db,
            }
            db_name = db_names.get(database)

            sql = """
                SELECT 
                    TABLE_NAME as table_name,
                    TABLE_ROWS as row_count,
                    ROUND(DATA_LENGTH/1024/1024, 2) as size_mb,
                    CREATE_TIME as created,
                    UPDATE_TIME as last_updated
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table
            """

            return pd.read_sql_query(
                text(sql), engine, params={"database": db_name, "table": table}
            )

        except Exception as e:
            self.logger.error(f"Failed to get table info: {str(e)[:100]}")
            return pd.DataFrame()

    def get_table_row_count(self, table: str, database: str = "data") -> int:
        """Get row count for a table."""
        info = self.get_table_info(table, database)
        return int(info["row_count"].iloc[0]) if not info.empty else 0

    def get_table_structure(self, table: str, database: str = "data") -> pd.DataFrame:
        """Get table structure."""
        if not self.connected or not self.table_exists(table, database):
            return pd.DataFrame()

        engine = self._get_engine(database)
        if not engine:
            return pd.DataFrame()

        try:
            db_names = {
                "data": self.config.database.parser_db,
                "system": self.config.database.system_db,
                "jobs": self.config.database.jobs_db,
                "traps": self.config.database.traps_db,
            }
            db_name = db_names.get(database)

            sql = """
                SELECT 
                    COLUMN_NAME as column_name,
                    DATA_TYPE as data_type,
                    CHARACTER_MAXIMUM_LENGTH as max_length,
                    IS_NULLABLE as nullable,
                    COLUMN_KEY as key_type
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :database AND TABLE_NAME = :table
                ORDER BY ORDINAL_POSITION
            """

            return pd.read_sql_query(
                text(sql), engine, params={"database": db_name, "table": table}
            )

        except Exception as e:
            self.logger.error(f"Failed to get structure: {str(e)[:100]}")
            return pd.DataFrame()

    # ============================================
    # JOB METADATA OPERATIONS (System DB)
    # ============================================

    @retry_on_connection_error(max_retries=3)
    def save_job_metadata(self, job: Dict[str, Any]) -> bool:
        """
        Save job metadata to system database.
        Supports both full inserts and partial updates.

        Args:
            job: Job dictionary with metadata
                - job_id (required): Job identifier
                - status (required for new jobs): Job status
                - Other fields are optional

        Returns:
            True if successful
        """
        try:
            metrics = get_metrics_service()

            job_id = job.get("job_id")
            if not job_id:
                self.logger.error("job_id is required")
                return False

            with self._get_connection("system") as conn:
                # Check if job exists
                check_query = text("SELECT status FROM jobs WHERE job_id = :job_id")
                existing = conn.execute(check_query, {"job_id": job_id}).fetchone()

                if existing:
                    # ✅ UPDATE: Build dynamic UPDATE query
                    update_fields = []
                    params = {"job_id": job_id}

                    # Simple fields
                    simple_fields = {
                        "job_name": "job_name",
                        "job_type": "job_type",
                        "status": "status",
                        "started_at": "started_at",
                        "completed_at": "completed_at",
                        "progress": "progress",
                        "message": "message",
                    }

                    for field, db_field in simple_fields.items():
                        if field in job:
                            update_fields.append(f"{db_field} = :{db_field}")
                            params[db_field] = job[field]

                    # JSON fields
                    if "result" in job:
                        update_fields.append("result_data = :result_data")
                        params["result_data"] = (
                            self._json_serialize(job["result"]) if job["result"] else None
                        )

                    if "errors" in job:
                        update_fields.append("errors = :errors")
                        params["errors"] = (
                            self._json_serialize(job["errors"]) if job["errors"] else None
                        )

                    if "metadata" in job:
                        update_fields.append("metadata = :metadata")
                        params["metadata"] = (
                            self._json_serialize(job["metadata"]) if job["metadata"] else None
                        )

                    if not update_fields:
                        self.logger.debug(f"No fields to update for job {job_id}")
                        return True

                    update_query = text(
                        f"""
                        UPDATE jobs 
                        SET {', '.join(update_fields)}
                        WHERE job_id = :job_id
                    """
                    )

                    conn.execute(update_query, params)
                    conn.commit()

                    if metrics:
                        metrics.counter('app_jobs_db_operations_total', {'operation': 'update'})

                    self.logger.debug(f"Updated job {job_id}")
                    return True

                else:
                    # ✅ INSERT: Require status for new jobs
                    if "status" not in job:
                        self.logger.error(f"status is required for new job {job_id}")
                        return False

                    # Serialize JSON fields
                    result_data = (
                        self._json_serialize(job.get("result")) if job.get("result") else None
                    )
                    errors = (
                        self._json_serialize(job.get("errors", [])) if job.get("errors") else None
                    )
                    metadata = (
                        self._json_serialize(job.get("metadata", {}))
                        if job.get("metadata")
                        else None
                    )

                    query = text(
                        """
                        INSERT INTO jobs (
                            job_id, job_type, job_name, status, created_at, started_at, 
                            completed_at, progress, message, result_data, errors, metadata
                        ) VALUES (
                            :job_id, :job_type, :job_name, :status, :created_at, :started_at,
                            :completed_at, :progress, :message, :result_data, :errors, :metadata
                        )
                    """
                    )

                    conn.execute(
                        query,
                        {
                            "job_id": job_id,
                            "job_type": job.get("job_type", "parse"),
                            "job_name": job.get("job_name"),
                            "status": job["status"],
                            "created_at": job.get("created_at", datetime.now()),
                            "started_at": job.get("started_at"),
                            "completed_at": job.get("completed_at"),
                            "progress": job.get("progress", 0),
                            "message": job.get("message"),
                            "result_data": result_data,
                            "errors": errors,
                            "metadata": metadata,
                        },
                    )
                    conn.commit()

                    if metrics:
                        metrics.counter('app_jobs_db_operations_total', {'operation': 'create'})

                    self.logger.debug(f"Inserted new job {job_id}")
                    return True

        except Exception as e:
            self.logger.error(f"Failed to save job metadata: {str(e)[:200]}", exc_info=True)
            return False

    def _json_serialize(self, obj):
        """Helper to serialize objects to JSON"""
        import json
        from datetime import date, datetime

        import numpy as np
        import pandas as pd

        def json_serializer(o):
            if isinstance(o, pd.Timestamp):
                return o.isoformat()
            if isinstance(o, np.datetime64):
                return pd.Timestamp(o).isoformat()
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                return float(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
            if pd.isna(o):
                return None
            raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

        return json.dumps(obj, default=json_serializer)

    @retry_on_connection_error(max_retries=3)
    def get_job_metadata(self, job_id: str, include_data: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get job metadata from system database.

        Args:
            job_id: Job ID
            include_data: Whether to include result_data

        Returns:
            Job dictionary or None if not found
        """
        try:
            metrics = get_metrics_service()

            with self._get_connection("system") as conn:
                if include_data:
                    query = text(
                        """
                        SELECT 
                            job_id, job_type, job_name, status, created_at, started_at,
                            completed_at, progress, message, result_data, errors, metadata
                        FROM jobs 
                        WHERE job_id = :job_id
                    """
                    )
                else:
                    query = text(
                        """
                        SELECT 
                            job_id, job_type, job_name, status, created_at, started_at,
                            completed_at, progress, message, errors, metadata
                        FROM jobs 
                        WHERE job_id = :job_id
                    """
                    )

                result = conn.execute(query, {"job_id": job_id}).fetchone()

                if result:
                    job = dict(result._mapping)

                    # Parse JSON fields
                    if include_data and job.get("result_data"):
                        job["result"] = json.loads(job["result_data"])
                        del job["result_data"]

                    if job.get("errors"):
                        job["errors"] = json.loads(job["errors"]) if job["errors"] else []

                    if job.get("metadata"):
                        job["metadata"] = json.loads(job["metadata"]) if job["metadata"] else {}

                    if metrics:
                        metrics.counter('app_jobs_db_operations_total', {'operation': 'select'})

                    return job

                return None

        except Exception as e:
            self.logger.error(f"Failed to get job metadata: {str(e)[:200]}")
            return None

    @retry_on_connection_error(max_retries=3)
    def list_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List jobs from system database."""
        try:
            with self._get_connection("system") as conn:
                where_clauses = []
                params = {"limit": limit, "offset": offset}

                if status:
                    where_clauses.append("status = :status")
                    params["status"] = status

                if job_type:
                    where_clauses.append("job_type = :job_type")
                    params["job_type"] = job_type

                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

                query = text(
                    f"""
                    SELECT 
                        job_id, job_type, job_name, status, created_at, started_at,
                        completed_at, progress, message, result_data, errors, metadata
                    FROM jobs 
                    WHERE {where_sql}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """
                )

                results = conn.execute(query, params).fetchall()

                jobs = []
                for row in results:
                    job = dict(row._mapping)

                    # Parse JSON fields
                    if job.get("result_data"):
                        try:
                            job["result"] = json.loads(job["result_data"])
                            del job["result_data"]
                        except:
                            pass

                    if job.get("errors"):
                        try:
                            job["errors"] = json.loads(job["errors"]) if job["errors"] else []
                        except:
                            job["errors"] = []

                    if job.get("metadata"):
                        try:
                            job["metadata"] = json.loads(job["metadata"]) if job["metadata"] else {}
                        except:
                            job["metadata"] = {}

                    jobs.append(job)

                return jobs

        except Exception as e:
            self.logger.error(f"Failed to list jobs: {str(e)[:200]}", exc_info=True)
            return []

    @retry_on_connection_error(max_retries=3)
    def delete_job_metadata(self, job_id: str) -> bool:
        """Delete job metadata from system database."""
        try:
            metrics = get_metrics_service()

            with self._get_connection("system") as conn:
                query = text("DELETE FROM jobs WHERE job_id = :job_id")
                result = conn.execute(query, {"job_id": job_id})
                conn.commit()

                if metrics:
                    if result.rowcount > 0:
                        metrics.counter('app_jobs_db_operations_total', {'operation': 'delete'})

                if result.rowcount > 0:
                    self.logger.info(f"Deleted job metadata for {job_id}")
                    return True
                else:
                    self.logger.warning(f"Job {job_id} not found in system database")
                    return False

        except Exception as e:
            self.logger.error(f"Failed to delete job metadata: {str(e)[:200]}")
            return False

    def delete_job_complete(self, job_id: str, delete_data: bool = True) -> bool:
        """
        Delete job completely (metadata + data).

        Args:
            job_id: Job ID
            delete_data: Whether to also delete the data table

        Returns:
            True if successful
        """
        success = True

        # Delete data table if requested
        if delete_data:
            table_name = f"job_{job_id.replace('-', '_')}_data"
            if self.table_exists(table_name, "jobs"):
                if not self.delete_table(table_name, "jobs", confirm=True):
                    success = False

        # Delete metadata
        if not self.delete_job_metadata(job_id):
            success = False

        return success
    
    def count_running_jobs(self) -> int:
        """
        Count currently running jobs.
        
        Returns:
            Number of jobs with status 'running'
        """
        try:
            with self._get_connection("system") as conn:
                
                query = "SELECT COUNT(*) FROM jobs WHERE status = 'running';"
                
                count = conn.execute(text(query)).fetchone()[0]
                
            self.logger.debug(f"Running jobs count: {count}")
            print(f"Running jobs count: {count}")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Failed to count running jobs: {e}")
            return 0  # Return 0 on error to allow job to proceed


    # ============================================
    # HELPER METHODS
    # ============================================

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare DataFrame for database storage."""
        # Add timestamp
        df["imported_at"] = datetime.now()

        # Handle text columns
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].apply(
                lambda x: str(x)[: self.MAX_VARCHAR_LENGTH] if pd.notna(x) else None
            )

        # Handle datetime columns
        for col in df.select_dtypes(include=["datetime64"]).columns:
            df[col] = pd.to_datetime(df[col]).dt.tz_localize(None)

        # Handle boolean columns
        for col in df.select_dtypes(include=["bool"]).columns:
            df[col] = df[col].astype(int)

        # Replace NaN with None
        return df.where(pd.notna(df), None)

    def _batch_insert(self, df: pd.DataFrame, table: str, mode: str, engine):
        """Batch insertion for large datasets."""
        total_rows = len(df)
        chunks = [df[i : i + self.chunk_size] for i in range(0, total_rows, self.chunk_size)]

        self.logger.debug(f"Batch inserting {total_rows:,} rows in {len(chunks)} chunks")

        for i, chunk in enumerate(chunks, 1):
            chunk.to_sql(
                table,
                engine,
                if_exists="replace" if i == 1 and mode == "replace" else "append",
                index=False,
                method="multi",
            )

            if i % 10 == 0 or i == len(chunks):
                self.logger.debug(
                    f"Inserted {min(i * self.chunk_size, total_rows):,}/{total_rows:,} rows"
                )

    def _validate_table_name(self, table: str) -> bool:
        """Validate table name."""
        if len(table) > self.MAX_IDENTIFIER_LENGTH:
            return False
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", table):
            return False
        if table.lower() in self.RESERVED_WORDS:
            return False
        return True

    def _sanitize_table_name(self, table: str) -> str:
        """Sanitize table name."""
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", table)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"tbl_{sanitized}"
        return sanitized[: self.MAX_IDENTIFIER_LENGTH]

    def _build_select_query(
        self,
        table: str,
        filters: Dict = None,
        columns: List[str] = None,
        limit: int = None,
        offset: int = None,
        sort_by: str = None,
        sort_order: str = "asc",
    ) -> Tuple[str, Dict]:
        """
        Build SELECT query with filters.

        Returns:
            Tuple of (sql_query, params_dict)
        """
        # SELECT clause
        if columns:
            cols = ", ".join([f"`{col}`" for col in columns])
        else:
            cols = "*"

        sql = f"SELECT {cols} FROM `{table}`"
        params = {}

        # ✅ WHERE clause - Use direct string interpolation
        if filters:
            where_clauses = []
            for col, value in filters.items():
                if isinstance(value, dict):
                    # Complex filter
                    if "contains" in value:
                        search = value["contains"].replace("'", "''")  # Escape quotes
                        where_clauses.append(f"`{col}` LIKE '%{search}%'")
                    elif "regex" in value:
                        pattern = value["regex"].replace("'", "''")
                        where_clauses.append(f"`{col}` REGEXP '{pattern}'")
                    elif "not_empty" in value and value["not_empty"]:
                        where_clauses.append(f"(`{col}` IS NOT NULL AND `{col}` != '')")
                    elif "empty" in value and value["empty"]:
                        where_clauses.append(f"(`{col}` IS NULL OR `{col}` = '')")
                    elif "not_in" in value:
                        # ✅ FIX: Extract escaping outside f-string
                        escaped_values = []
                        for v in value["not_in"]:
                            if isinstance(v, str):
                                escaped = v.replace("'", "''")
                                escaped_values.append(f"'{escaped}'")
                            else:
                                escaped_values.append(str(v))
                        values_str = ", ".join(escaped_values)
                        where_clauses.append(f"`{col}` NOT IN ({values_str})")
                    elif "gt" in value:
                        where_clauses.append(f"`{col}` > {value['gt']}")
                    elif "lt" in value:
                        where_clauses.append(f"`{col}` < {value['lt']}")
                    elif "gte" in value and "lte" in value:
                        where_clauses.append(f"`{col}` BETWEEN {value['gte']} AND {value['lte']}")
                elif isinstance(value, list):
                    # ✅ FIX: IN clause - Extract escaping outside f-string
                    escaped_values = []
                    for v in value:
                        if isinstance(v, str):
                            escaped = v.replace("'", "''")
                            escaped_values.append(f"'{escaped}'")
                        else:
                            escaped_values.append(str(v))
                    values_str = ", ".join(escaped_values)
                    where_clauses.append(f"`{col}` IN ({values_str})")
                elif isinstance(value, str):
                    # Simple string equality
                    escaped = value.replace("'", "''")
                    where_clauses.append(f"`{col}` = '{escaped}'")
                else:
                    # Numeric equality
                    where_clauses.append(f"`{col}` = {value}")

            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

        # ORDER BY clause
        if sort_by:
            sql += f" ORDER BY `{sort_by}` {sort_order.upper()}"

        # LIMIT clause
        if limit:
            sql += f" LIMIT {limit}"
            if offset:
                sql += f" OFFSET {offset}"

        self.logger.info(f"Built query: {sql}")

        return sql, params  # params will be empty now

    def _create_optimized_table(self, table: str, df: pd.DataFrame, engine):
        """Create optimized table structure."""
        try:
            columns_sql = []

            for col in df.columns:
                dtype = str(df[col].dtype)

                # Determine SQL type
                if col.endswith("_oid"):
                    sql_type = "VARCHAR(512)"
                elif col.endswith("_name"):
                    sql_type = "VARCHAR(256)"
                elif col.endswith("_description"):
                    sql_type = "TEXT"
                elif col in ["tc_enumerations", "notification_objects_detail"]:
                    sql_type = "JSON"
                elif "int" in dtype:
                    sql_type = "INT"
                elif "float" in dtype:
                    sql_type = "FLOAT"
                elif "datetime" in dtype:
                    sql_type = "DATETIME"
                elif "bool" in dtype:
                    sql_type = "BOOLEAN"
                else:
                    max_len = (
                        df[col].astype(str).str.len().max() if not df[col].isna().all() else 255
                    )
                    if pd.isna(max_len) or max_len <= 255:
                        sql_type = "VARCHAR(255)"
                    elif max_len <= 65535:
                        sql_type = "TEXT"
                    else:
                        sql_type = "LONGTEXT"

                columns_sql.append(f"`{col}` {sql_type}")

            create_sql = f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    {', '.join(columns_sql)},
                    KEY idx_imported (imported_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """

            with engine.connect() as conn:
                # Drop existing table if exists
                conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                conn.execute(text(create_sql))
                conn.commit()

            metrics = get_metrics_service()
            if metrics:
                metrics.counter('app_db_table_operations_total', {'database': 'data', 'operation': 'create', 'status': 'success'})

            self.logger.debug(f"Created table '{table}'")

        except Exception as e:
            self.logger.error(f"Table creation failed: {str(e)[:200]}")
            raise

    def _create_indexes(self, table: str, df: pd.DataFrame, engine):
        """Create indexes for better performance."""
        index_columns = [
            "notification_name",
            "object_name",
            "module_name",
            "node_type",
            "notification_oid",
            "object_oid",
        ]

        with engine.connect() as conn:
            for col in index_columns:
                if col in df.columns:
                    try:
                        if df[col].dtype == "object":
                            index_sql = (
                                f"CREATE INDEX idx_{table}_{col} ON `{table}` (`{col}`(100))"
                            )
                        else:
                            index_sql = f"CREATE INDEX idx_{table}_{col} ON `{table}` (`{col}`)"
                        conn.execute(text(index_sql))
                    except Exception:
                        pass

            conn.commit()

    def _track_operation(self, op_type: str, duration: float, rows: int):
        """Track operation performance."""
        self._operation_times.append((op_type, duration, rows))
        if len(self._operation_times) > 100:
            self._operation_times = self._operation_times[-100:]

