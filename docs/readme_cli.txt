================================================================================
                            MIB TOOL V3 - README
================================================================================

COMPREHENSIVE MIB PARSING AND MANAGEMENT TOOL
Version: 3.0.0
Python: 3.8+
License: MIT

================================================================================
TABLE OF CONTENTS
================================================================================

1. OVERVIEW
2. KEY FEATURES
3. INSTALLATION
4. QUICK START
5. ARCHITECTURE
6. COMMAND REFERENCE
7. USAGE EXAMPLES
8. CONFIGURATION
9. API DOCUMENTATION
10. TROUBLESHOOTING
11. PERFORMANCE OPTIMIZATION
12. CONTRIBUTING
13. SUPPORT

================================================================================
1. OVERVIEW
================================================================================

MIB Tool V3 is a powerful, enterprise-grade Management Information Base (MIB) 
parser and management system designed to handle complex MIB processing tasks. 
It provides comprehensive parsing, filtering, deduplication, and analysis 
capabilities for SNMP MIB files.

Primary Use Cases:
- Parse and extract SNMP notifications/traps from MIB files
- Build comprehensive alarm databases from vendor MIBs
- Manage multi-vendor MIB collections
- Analyze MIB data quality and coverage
- Generate reports for network management systems

================================================================================
2. KEY FEATURES
================================================================================

CORE CAPABILITIES:
- Advanced MIB parsing with dependency resolution
- Intelligent deduplication with multiple strategies
- MySQL database integration for large-scale data management
- Support for compressed files (gz, zip, bz2, xz)
- Batch processing for automation
- Comprehensive data analysis and reporting

PARSING FEATURES:
- Automatic dependency resolution
- Textual Convention (TC) resolution with full chain tracking
- Support for SNMPv1, SNMPv2c, and SNMPv3 MIBs
- Parallel processing for large MIB collections
- Smart caching for improved performance
- Handles complex IMPORTS and cross-references

DATA FORMATS SUPPORTED:
- Input: MIB files (.mib, .txt, .my), CSV, JSON, YAML, Excel, Parquet
- Output: CSV, JSON, YAML, Excel, Parquet, HTML
- Compression: gzip, zip, bz2, xz (both input and output)

FILTERING CAPABILITIES:
- Filter by alarm/notification names
- Filter by modules
- Filter by status (current, deprecated, obsolete)
- Filter by node types
- Filter by OID patterns
- Custom regex filtering
- Date range filtering

DEDUPLICATION STRATEGIES:
- Smart (quality-based selection)
- Keep first occurrence
- Keep last occurrence
- Keep one per module (multi-vendor support)
- Merge (combine information from duplicates)

================================================================================
3. INSTALLATION
================================================================================

SYSTEM REQUIREMENTS:
- Python 3.8 or higher
- MySQL 5.7+ or MariaDB 10.2+ (optional, for database features)
- 2GB RAM minimum (4GB+ recommended for large MIB collections)
- 500MB disk space for application and cache

STEP 1: Clone or Download
--------------------------
git clone https://github.com/yourusername/mib-tool-v3.git
cd mib-tool-v3

OR

Download and extract the archive:
tar -xzf mib-tool-v3.tar.gz
cd mib-tool-v3

STEP 2: Install Dependencies
-----------------------------
pip install -r requirements.txt

Required packages:
- pysnmp>=4.4.12
- pysmi>=0.3.4
- pandas>=1.3.0
- sqlalchemy>=1.4.0
- pymysql>=1.0.0
- pyyaml>=5.4
- openpyxl>=3.0.0 (for Excel support)
- pyarrow>=5.0.0 (for Parquet support)

STEP 3: Configure Database (Optional)
--------------------------------------
Edit config/config.yaml:

database:
  host: localhost
  port: 3306
  user: your_username
  password: your_password
  database: mib_tool_db

Or use environment variables:
export MIB_DB_HOST=localhost
export MIB_DB_USER=your_username
export MIB_DB_PASSWORD=your_password

STEP 4: Verify Installation
----------------------------
python mib_tool.py --version
python mib_tool.py --help

STEP 5: Run Tests (Optional)
-----------------------------
python -m pytest tests/

================================================================================
4. QUICK START
================================================================================

BASIC USAGE EXAMPLES:

1. Parse a single MIB file:
   python mib_tool.py parse IF-MIB.mib -o output.csv

2. Parse directory of MIBs:
   python mib_tool.py parse ./mibs --recursive -o all_mibs.csv

3. Import to database:
   python mib_tool.py import ./mibs --table mib_data

4. Filter specific alarms:
   python mib_tool.py filter mib_data -o filtered.csv --alarms "linkDown,linkUp"

5. Export from database:
   python mib_tool.py export mib_data -o export.xlsx --format excel

6. Search for terms:
   python mib_tool.py search "interface" --all-tables

7. Analyze data:
   python mib_tool.py analyze mib_data --report analysis.html --format html

================================================================================
5. ARCHITECTURE
================================================================================

PROJECT STRUCTURE:
mib_tool/
├── mib_tool.py           # Main entry point
├── config/
│   ├── __init__.py
│   └── config.yaml       # Configuration file
├── core/
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── parser.py         # MIB parser with dependency resolution
│   ├── db_manager.py     # Database operations
│   └── exporter.py       # File import/export
├── services/
│   ├── __init__.py
│   ├── filter.py         # Filtering service
│   ├── analyzer.py       # Analysis service
│   ├── resolver.py       # Resolver service
│   └── deduplicator.py   # Deduplication service
├── utils/
│   ├── __init__.py
│   ├── logger.py         # Centralized logging
│   ├── validators.py     # Validation service
│   └── cache.py          # Cache management
├── cli/
│   ├── __init__.py
│   ├── main.py           # CLI interface
│   └── commands.py       # Command handlers
├── tests/
│   └── ...               # Unit tests
├── api/                  # Future Use Case for API
├── docs/                 # Documnetation
├── exports/              # Default export directory
└── requirements.txt

DATA FLOW:
1. MIB Files → Parser → DataFrame
2. DataFrame → Filters/Dedup → Clean DataFrame
3. Clean DataFrame → Database/Export → Output

DATABASE SCHEMA:
The system uses a denormalized schema optimized for query performance:

mib_data_expanded:
- Notification fields (name, OID, status, description)
- Object fields (name, OID, syntax, access, status)
- TC resolution fields (name, base_type, constraints)
- Metadata (module, file, timestamps)
- Indexes on key fields for performance

================================================================================
6. COMMAND REFERENCE
================================================================================

GLOBAL OPTIONS:
--version            Show version
-v, --verbose        Increase verbosity (-v, -vv, -vvv)
--config FILE        Use custom config file
--no-cache           Disable caching
--no-db              Run without database

COMMANDS:

parse - Parse MIB files
------------------------
Usage: mib_tool.py parse SOURCE [OPTIONS]

Arguments:
  SOURCE              MIB file or directory

Options:
  -o, --output FILE   Output file path
  --format FORMAT     Output format (csv, json, excel, etc.)
  -r, --recursive     Process subdirectories
  --pattern PATTERN   File pattern (default: *.mib)
  --force             Force recompilation
  --to-db TABLE       Store in database table
  --no-deps           Skip dependency resolution

import - Import data to database
---------------------------------
Usage: mib_tool.py import SOURCE --table TABLE [OPTIONS]

Arguments:
  SOURCE              Source file/directory

Options:
  --table TABLE       Target database table (required)
  --mode MODE         Import mode (replace, append, fail)
  --format FORMAT     Source format (auto-detect)
  --filter-file FILE  CSV file with alarm names
  --filter ALARMS     Comma-separated alarm names

export - Export from database
------------------------------
Usage: mib_tool.py export TABLE -o OUTPUT [OPTIONS]

Arguments:
  TABLE               Source database table

Options:
  -o, --output FILE   Output file (required)
  --format FORMAT     Output format
  --filter EXPR       SQL WHERE clause
  --columns COLS      Columns to export
  --limit N           Maximum rows
  --compress TYPE     Compression (gzip, zip)

search - Search in database
----------------------------
Usage: mib_tool.py search TERMS [OPTIONS]

Arguments:
  TERMS               Search terms (comma-separated)

Options:
  --table TABLE       Specific table to search
  --all-tables        Search all tables
  --limit N           Maximum results (default: 100)
  -o, --output FILE   Export results

filter - Filter MIB data
-------------------------
Usage: mib_tool.py filter SOURCE -o OUTPUT [OPTIONS]

Arguments:
  SOURCE              Source table or file

Options:
  -o, --output FILE   Output file (required)
  --alarms NAMES      Alarm names to filter
  --alarm-file FILE   CSV with alarm names
  --modules MODULES   Module names
  --status STATUS     Status filter
  --node-type TYPE    Node type filter
  --deduplicate STRAT Deduplication strategy

analyze - Analyze MIB data
---------------------------
Usage: mib_tool.py analyze SOURCE [OPTIONS]

Arguments:
  SOURCE              Table or file to analyze

Options:
  --report FILE       Save report to file
  --format FORMAT     Report format (text, html, json)
  --metrics METRICS   Metrics to analyze (coverage, quality, etc.)

db - Database operations
-------------------------
Usage: mib_tool.py db COMMAND [OPTIONS]

Subcommands:
  list                List tables
  info TABLE          Show table information
  delete TABLE        Delete table
  query SQL           Execute SQL query

cache - Cache management
-------------------------
Usage: mib_tool.py cache COMMAND [OPTIONS]

Subcommands:
  stats               Show cache statistics
  clear               Clear cache
  optimize            Optimize cache

validate - Validate data
-------------------------
Usage: mib_tool.py validate SOURCE [OPTIONS]

Arguments:
  SOURCE              File or table to validate

Options:
  --strict            Strict validation mode
  --report FILE       Save validation report

batch - Batch processing
-------------------------
Usage: mib_tool.py batch BATCH_FILE [OPTIONS]

Arguments:
  BATCH_FILE          YAML/JSON batch configuration

Options:
  --dry-run           Show what would be executed
  --continue-on-error Continue on errors

================================================================================
7. USAGE EXAMPLES
================================================================================

EXAMPLE 1: Complete Workflow
-----------------------------
# Step 1: Parse all vendor MIBs
python mib_tool.py parse ./vendor_mibs --recursive --to-db raw_data

# Step 2: Analyze for duplicates
python mib_tool.py analyze raw_data --metrics duplicates

# Step 3: Deduplicate intelligently
python mib_tool.py filter raw_data -o clean_data.csv --deduplicate smart

# Step 4: Import clean data to final table
python mib_tool.py import clean_data.csv --table production_data

# Step 5: Generate report
python mib_tool.py analyze production_data --report report.html --format html

EXAMPLE 2: Multi-Vendor MIB Management
---------------------------------------
# Parse Cisco MIBs
python mib_tool.py parse ./cisco_mibs --recursive --to-db cisco_data

# Parse Juniper MIBs
python mib_tool.py parse ./juniper_mibs --recursive --to-db juniper_data

# Combine with deduplication (keep one per vendor)
python mib_tool.py db query "SELECT * FROM cisco_data UNION SELECT * FROM juniper_data" \
  -o combined.csv

python mib_tool.py filter combined.csv -o final.csv --deduplicate keep_all_modules

EXAMPLE 3: Alarm Filtering
---------------------------
# Create alarm list file
cat > critical_alarms.csv << EOF
linkDown
linkUp
bgpEstablished
bgpBackwardTransition
ospfNbrStateChange
EOF

# Filter for specific alarms only
python mib_tool.py filter all_mibs.csv -o critical_only.csv \
  --alarm-file critical_alarms.csv

EXAMPLE 4: Batch Processing
----------------------------
# Create batch configuration
cat > nightly_process.yaml << EOF
commands:
  - name: "Parse new MIBs"
    command: parse
    source: "./incoming/mibs"
    to_db: "staging"
    
  - name: "Deduplicate"
    command: filter
    source: "staging"
    output: "cleaned.csv"
    deduplicate: "smart"
    
  - name: "Import to production"
    command: import
    source: "cleaned.csv"
    table: "production"
    mode: "replace"
    
  - name: "Generate report"
    command: analyze
    source: "production"
    report: "daily_report.html"
    format: "html"
EOF

# Execute batch
python mib_tool.py batch nightly_process.yaml

EXAMPLE 5: Working with Compressed Files
-----------------------------------------
# Import compressed data
python mib_tool.py import mib_data.csv.gz --table compressed_import

# Export with compression
python mib_tool.py export production_data -o export.csv --compress gzip

# Process ZIP archive
python mib_tool.py import mib_archive.zip --table archived_data

================================================================================
8. CONFIGURATION
================================================================================

CONFIGURATION FILE (config/config.yaml):

# Database Configuration
database:
  host: localhost
  port: 3306
  user: mib_user
  password: secure_password
  database: mib_tool_db
  pool_size: 5
  max_overflow: 10
  echo: false

# Parser Configuration
parser:
  cache_dir: ./cache
  cache_enabled: true
  resolve_dependencies: true
  parallel: true
  max_workers: 4
  mib_sources:
    - http://mibs.snmplabs.com/asn1/
    - ./local_mibs
  search_paths:
    - /usr/share/snmp/mibs
    - ./vendor_mibs

# Export Configuration
export:
  chunk_size: 10000
  compression: null
  include_metadata: true
  timestamp_format: "%Y-%m-%d %H:%M:%S"

# Processing Configuration
processing:
  deduplicate: true
  dedup_strategy: smart
  validate_oids: true
  resolve_textual_conventions: true
  max_tc_depth: 10

# Logging Configuration
logging:
  level: INFO
  file: ./logs/mib_tool.log
  console: true
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  rotate_size: 10485760  # 10MB
  backup_count: 5

ENVIRONMENT VARIABLES:
Override config file settings:

MIB_DB_HOST=localhost
MIB_DB_USER=username
MIB_DB_PASSWORD=password
MIB_DB_NAME=database
MIB_CACHE_DIR=/tmp/mib_cache
MIB_LOG_LEVEL=DEBUG

================================================================================
9. API DOCUMENTATION
================================================================================

PYTHON API USAGE:

from core.config import Config
from core.parser import MibParser
from core.db_manager import DatabaseManager
from core.exporter import FileExporter
from services.filter import FilterService
from services.analyzer import AnalyzerService
from services.deduplicator import DeduplicationService

# Initialize components
config = Config('./config/config.yaml')
parser = MibParser(config)
db = DatabaseManager(config)
exporter = FileExporter(config)
filter_svc = FilterService()
analyzer = AnalyzerService()
dedup_svc = DeduplicationService()

# Parse MIB file
df = parser.parse_file('IF-MIB.mib')

# Parse directory
df = parser.parse_directory('./mibs', recursive=True)

# Filter data
filtered = filter_svc.filter_by_alarms(df, ['linkDown', 'linkUp'])
filtered = filter_svc.filter_by_modules(filtered, ['IF-MIB'])

# Deduplicate
clean_df = dedup_svc.deduplicate(filtered, strategy='smart')

# Analyze
coverage = analyzer.analyze_coverage(clean_df)
quality = analyzer.analyze_quality(clean_df)

# Database operations
db.df_to_db(clean_df, 'my_table', mode='replace')
retrieved = db.db_to_df('my_table', limit=1000)

# Export
exporter.df_to_file(clean_df, 'output.xlsx', format='excel')

# Search
results = db.search(['linkDown'], table='my_table')

KEY CLASSES:

MibParser:
  - parse_file(path, force_compile=False)
  - parse_directory(path, pattern='*.mib', recursive=False)
  - get_statistics()

DatabaseManager:
  - df_to_db(df, table, mode='replace')
  - db_to_df(table, filters=None, limit=None)
  - search(terms, table=None, limit=100)
  - table_exists(table)
  - list_tables()

FileExporter:
  - df_to_file(df, path, format=None, compression=None)
  - file_to_df(path, format=None)
  - validate_dataframe(df)

FilterService:
  - filter_by_alarms(df, alarm_list)
  - filter_by_modules(df, modules)
  - filter_by_status(df, status)
  - filter_by_node_type(df, node_type)
  - apply_complex_filter(df, filters)

AnalyzerService:
  - analyze_coverage(df)
  - analyze_quality(df)
  - analyze_statistics(df)
  - analyze_duplicates(df)
  - generate_html_report(results)

DeduplicationService:
  - find_duplicates(df, key_columns=None)
  - deduplicate(df, strategy='smart')
  - get_duplicate_report(df)
  - compare_strategies(df)

================================================================================
10. TROUBLESHOOTING
================================================================================

COMMON ISSUES AND SOLUTIONS:

ISSUE: ImportError: No module named 'pysnmp'
SOLUTION:
  pip install pysnmp pysmi
  pip install --upgrade pip

ISSUE: MySQL connection error
SOLUTION:
  1. Verify MySQL is running:
     systemctl status mysql
  2. Check credentials:
     mysql -u username -p
  3. Grant permissions:
     GRANT ALL ON mib_tool_db.* TO 'user'@'localhost';
  4. Use --no-db flag to skip database

ISSUE: MIB compilation failed
SOLUTION:
  1. Check MIB syntax:
     python mib_tool.py validate MIB_FILE.mib
  2. Ensure dependencies available:
     - Place imported MIBs in same directory
     - Add search paths in config.yaml
  3. Use verbose mode for details:
     python mib_tool.py parse MIB_FILE.mib -vvv
  4. Clear cache and retry:
     python mib_tool.py cache clear --all

ISSUE: Out of memory with large files
SOLUTION:
  1. Process in smaller batches
  2. Use database instead of memory:
     python mib_tool.py import large_file.csv --table temp_data
  3. Enable chunking in config:
     export:
       chunk_size: 5000
  4. Increase system memory or use swap

ISSUE: Duplicate data in output
SOLUTION:
  1. Analyze duplicates:
     python mib_tool.py analyze data --metrics duplicates
  2. Apply deduplication:
     python mib_tool.py filter data -o clean.csv --deduplicate smart
  3. For multi-vendor:
     --deduplicate keep_all_modules

ISSUE: Slow parsing performance
SOLUTION:
  1. Enable caching (default)
  2. Use parallel processing:
     parser:
       parallel: true
       max_workers: 4
  3. Parse directory instead of individual files
  4. Pre-compile MIBs if possible

ISSUE: Cannot find specific alarms
SOLUTION:
  1. Search across all tables:
     python mib_tool.py search "alarm_name" --all-tables
  2. Check exact name match:
     python mib_tool.py db query "SELECT * FROM table WHERE notification_name LIKE '%alarm%'"
  3. Verify MIB was parsed successfully

================================================================================
11. PERFORMANCE OPTIMIZATION
================================================================================

OPTIMIZATION TIPS:

1. DATABASE OPTIMIZATION:
   - Create indexes on frequently searched columns:
     CREATE INDEX idx_notification ON mib_data(notification_name);
     CREATE INDEX idx_oid ON mib_data(object_oid);
   - Use connection pooling (configured in config.yaml)
   - Optimize MySQL settings for large datasets

2. PARSING OPTIMIZATION:
   - Enable parallel processing for multiple files
   - Use caching to avoid re-parsing
   - Process entire directories instead of individual files
   - Pre-download MIB dependencies

3. MEMORY OPTIMIZATION:
   - Use chunking for large files
   - Process data in batches
   - Use database for intermediate storage
   - Clear cache periodically

4. QUERY OPTIMIZATION:
   - Use specific columns instead of SELECT *
   - Add filters to reduce data transfer
   - Use LIMIT for large result sets
   - Create composite indexes for complex queries

5. EXPORT OPTIMIZATION:
   - Use compression for large exports
   - Export in chunks for very large datasets
   - Use binary formats (Parquet) for better performance
   - Avoid unnecessary format conversions

BENCHMARK RESULTS:
- Single MIB file: ~0.5-2 seconds
- Directory (100 MIBs): ~30-60 seconds (parallel)
- Deduplication (100K records): ~5-10 seconds
- Database import (1M records): ~30-60 seconds
- Export to CSV (1M records): ~10-20 seconds

================================================================================
12. CONTRIBUTING
================================================================================

DEVELOPMENT SETUP:

1. Fork the repository
2. Create virtual environment:
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows

3. Install development dependencies:
   pip install -r requirements-dev.txt

4. Run tests:
   pytest tests/ -v
   pytest tests/ --cov=core --cov=services

5. Check code style:
   flake8 core/ services/ cli/
   black --check core/ services/ cli/

CONTRIBUTION GUIDELINES:

1. Follow PEP 8 style guide
2. Add unit tests for new features
3. Update documentation
4. Create descriptive commit messages
5. Submit pull request with description

TESTING:
- Unit tests: tests/unit/
- Integration tests: tests/integration/
- Performance tests: tests/performance/

Run specific test:
  pytest tests/unit/test_parser.py::test_parse_file

================================================================================
13. SUPPORT
================================================================================

GETTING HELP:

1. Check this README first
2. Review the troubleshooting section
3. Search existing issues on GitHub
4. Check the FAQ (docs/FAQ.txt)
5. Contact support

REPORTING ISSUES:

Include the following information:
1. MIB Tool version (mib_tool.py --version)
2. Python version (python --version)
3. Operating system
4. Error messages (use -vvv for verbose output)
5. Sample MIB file (if applicable)
6. Configuration file (remove passwords)

RESOURCES:

- Documentation: docs/
- Examples: examples/
- MIB samples: test_data/
- Configuration templates: config/templates/

LICENSE:

MIT License - See LICENSE file for details

ACKNOWLEDGMENTS:

- pysnmp library for SNMP/MIB support
- pysmi for MIB compilation
- pandas for data manipulation
- SQLAlchemy for database abstraction

================================================================================
END OF README
================================================================================

Version: 3.0.0
Last Updated: 2024
Author: MIB Tool Development Team
================================================================================
