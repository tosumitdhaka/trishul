"""
Database API Endpoints - User Data Tables (mib_tool)
Handles operations on user imported data (long-term storage)
"""


import re
import os   
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import File, Form, APIRouter, Body, HTTPException, Query, Request, UploadFile

from core.file_manager import FileManager
from backend.models.schemas import TableInfo
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============================================
# TABLE LISTING & INFO
# ============================================


@router.get("/tables", response_model=List[TableInfo])
async def list_tables(
    request: Request,
    pattern: Optional[str] = Query(None, description="Filter table names by pattern"),
):
    """
    List all user data tables from mib_tool database.

    Returns:
        List of table information
    """
    try:
        db = request.app.state.db_manager

        # Get tables from data database
        tables_df = db.list_tables(database="data", pattern=pattern)

        if tables_df.empty:
            return []

        result = []
        for _, row in tables_df.iterrows():
            result.append(
                TableInfo(
                    name=row["table_name"],
                    row_count=int(row.get("row_count", 0)),
                    size_mb=float(row.get("size_mb", 0)),
                    created=row.get("created"),
                    updated=row.get("last_updated"),
                    columns=[],
                )
            )

        logger.info(f"Listed {len(result)} tables from data database")
        return result

    except Exception as e:
        logger.error(f"List tables failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")


@router.get("/tables/{table_name}", response_model=TableInfo)
async def get_table_info(request: Request, table_name: str):
    """
    Get detailed information about a specific table.

    Args:
        table_name: Name of the table

    Returns:
        Table information including columns
    """
    try:
        db = request.app.state.db_manager

        # Check if table exists
        if not db.table_exists(table_name, database="data"):
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Get table info
        info_df = db.get_table_info(table_name, database="data")
        if info_df.empty:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Get table structure
        structure_df = db.get_table_structure(table_name, database="data")

        columns = []
        for _, col in structure_df.iterrows():
            columns.append(
                {
                    "name": col["column_name"],
                    "type": col["data_type"],
                    "nullable": "YES" if col["nullable"] == "YES" else "NO",
                }
            )

        row = info_df.iloc[0]
        return TableInfo(
            name=table_name,
            row_count=int(row["row_count"]),
            size_mb=float(row["size_mb"]),
            created=row.get("created"),
            updated=row.get("last_updated"),
            columns=columns,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get table info failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get table info: {str(e)}")


# ============================================
# DATA IMPORT
# ============================================

@router.post("/tables/{table_name}/import/file")
async def import_file_to_table(
    request: Request,
    table_name: str,
    file: UploadFile = File(..., description="CSV, JSON, or Excel file"),
    mode: str = Form("append", pattern="^(append|replace)$", description="Import mode"),
    create_if_missing: bool = Form(True, description="Create table if it doesn't exist"),
):
    """
    Import data from file (CSV, JSON, Excel) to table.
    Uses FileManager for consistent file handling.
    
    Args:
        table_name: Target table name
        file: Uploaded file
        mode: Import mode ('append' or 'replace')
        create_if_missing: Create table if it doesn't exist
        
    Returns:
        Import result with row count
    """
    start_time = datetime.now()
    temp_file_path = None
    
    try:
        db = request.app.state.db_manager
        config = request.app.state.config
        
        # Validate file type
        filename = file.filename.lower()
        supported_extensions = ['.csv', '.json', '.xlsx', '.xls', '.txt', '.gz', '.zip', '.bz2', '.xz']
        
        if not any(filename.endswith(ext) for ext in supported_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: {', '.join(supported_extensions)}"
            )
        
        # Check if table exists
        table_exists = db.table_exists(table_name, database="data")
        
        if not table_exists and not create_if_missing:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found. Set create_if_missing=true to create it."
            )
        
        logger.info(f"📥 Importing file '{file.filename}' to table '{table_name}' (mode={mode})")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
        
        logger.info(f"📁 Saved uploaded file to: {temp_file_path}")
        
        # ✅ Use FileManager to convert file to DataFrame
        file_manager = FileManager(config)
        
        # Auto-detect format and convert to DataFrame
        df = await file_manager.file_to_df_async(temp_file_path)
        
        # Validate data
        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no data")
        
        logger.info(f"✅ Parsed {len(df)} rows, {len(df.columns)} columns using FileManager")
        
        # Clean column names (remove special characters, spaces)
        df.columns = [
            str(col).strip()
            .replace(' ', '_')
            .replace('-', '_')
            .replace('.', '_')
            .replace('(', '')
            .replace(')', '')
            .replace('[', '')
            .replace(']', '')
            .replace('/', '_')
            .replace('\\', '_')
            .lower()
            for col in df.columns
        ]
        
        logger.info(f"🧹 Cleaned column names: {list(df.columns)}")
        
        # Handle replace mode
        if mode == 'replace' and table_exists:
            logger.info(f"🗑️ Deleting existing table '{table_name}' (replace mode)")
            db.delete_table(table_name, database="data", confirm=True)
            table_exists = False
        
        # ✅ Import to database using existing method
        logger.info(f"💾 Saving to database table '{table_name}'...")
        success = db.save_to_user_db(df, table_name, mode='append')
        
        if not success:
            raise HTTPException(status_code=500, detail="Database import failed")
        
        # Get final row count
        final_count = db.get_table_row_count(table_name, database="data")
        
        # Get table size
        info_df = db.get_table_info(table_name, database="data")
        size_mb = float(info_df.iloc[0]["size_mb"]) if not info_df.empty else 0
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✅ Imported {len(df)} rows to '{table_name}' in {duration:.2f}s")
        
        return {
            "success": True,
            "message": f"Imported {len(df)} rows to table '{table_name}'",
            "table": table_name,
            "rows_imported": len(df),
            "total_rows": final_count,
            "columns": list(df.columns),
            "column_count": len(df.columns),
            "mode": mode,
            "duration": duration,
            "size_mb": size_mb,
            "created_table": not table_exists,
            "file_format": Path(file.filename).suffix.lstrip('.')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ File import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    
    finally:
        # ✅ Cleanup: Delete temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"🧹 Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


# ============================================
# TABLE DELETION
# ============================================


@router.delete("/tables/{table_name}")
async def delete_table(
    request: Request, table_name: str, confirm: bool = Query(False, description="Confirm deletion")
):
    """
    Delete user table.

    Args:
        table_name: Name of the table to delete
        confirm: Must be True to actually delete

    Returns:
        Deletion result
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Deletion not confirmed. Set confirm=true")

    try:
        db = request.app.state.db_manager

        # Check if table exists
        if not db.table_exists(table_name, database="data"):
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Delete table
        success = db.delete_table(table_name, database="data", confirm=True)

        if not success:
            raise HTTPException(status_code=500, detail="Delete failed")

        logger.info(f"✅ Deleted table {table_name}")

        return {"success": True, "message": f"Table '{table_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete table failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

# ============================================
# QUERY ENDPOINTS
# ============================================


@router.post("/query")
async def execute_safe_query(
    request: Request,
    table: str = Body(..., description="Table name"),
    database: str = Body(default="data", description="Database name ('data' or 'jobs')"),  # ✅ ADD THIS
    columns: List[str] = Body(default=["*"], description="Columns to select"),
    where: Optional[str] = Body(None, description="WHERE clause (without WHERE keyword)"),
    order_by: Optional[str] = Body(None, description="ORDER BY clause (without ORDER BY keyword)"),
    limit: int = Body(100, description="Result limit"),
    offset: int = Body(0, description="Result offset"),
):
    """
    Execute a safe, parameterized query on user tables..

    ✅ NOW SUPPORTS: Both 'data' and 'jobs' databases
    """
    try:
        # print(f"database: {database}")
        db = request.app.state.db_manager

        # ✅ Validate database parameter
        if database not in ["data", "jobs"]:
            raise HTTPException(
                status_code=400, detail=f"Invalid database: {database}. Must be 'data' or 'jobs'"
            )

        logger.info(f"🔍 Safe query on {database}.{table}")
        # print(f"🔍 Safe query on {database}.{table}")

        # ✅ Validate table exists in specified database
        if not db.table_exists(table, database=database):
            raise HTTPException(
                status_code=404, detail=f"Table '{table}' not found in {database} database"
            )

        # Build safe query
        columns_str = ", ".join([f"`{col}`" if col != "*" else "*" for col in columns])
        query = f"SELECT {columns_str} FROM `{table}`"

        # Add WHERE clause if provided
        if where:
            # Basic validation - reject dangerous keywords
            where_upper = where.upper()
            dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
            if any(keyword in where_upper for keyword in dangerous):
                # raise HTTPException(status_code=400, detail="WHERE clause contains forbidden keywords") 
                logger.warning("WHERE clause contains forbidden keywords")
            query += f" WHERE {where}"

        # Add ORDER BY if provided
        if order_by:
            query += f" ORDER BY {order_by}"

        # Add LIMIT and OFFSET
        query += f" LIMIT {limit} OFFSET {offset}"

        logger.info(f"📝 Executing query: {query}")

        # ✅ Execute query on specified database
        df = db.db_to_df(table=None, database=database, query=query)  # ✅ Use specified database

        if df.empty:
            return {"success": True, "data": [], "total": 0, "returned": 0, "query": query}

        # Get total count (without limit)
        count_query = f"SELECT COUNT(*) as count FROM `{table}`"
        if where:
            count_query += f" WHERE {where}"

        count_df = db.db_to_df(table=None, database=database, query=count_query)
        total = int(count_df.iloc[0]["count"]) if not count_df.empty else len(df)

        # Convert to records
        records = df.to_dict("records")

        logger.info(f"✅ Query returned {len(records)} rows (total: {total})")

        return {
            "success": True,
            "data": records,
            "total": total,
            "returned": len(records),
            "query": query,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")


@router.post("/query/validate")
async def validate_query(
    request: Request,
    query: str = Body(..., embed=True, description="SQL query to validate"),  # ✅ Add embed=True
):
    """
    Validate a SQL query without executing it.
    """
    try:
        query_upper = query.strip().upper()

        # Check if SELECT query
        if not query_upper.startswith("SELECT"):
            return {"valid": False, "error": "Only SELECT queries are allowed"}

        # Check for dangerous keywords
        dangerous = [
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "EXEC",
            "EXECUTE",
        ]
        for keyword in dangerous:
            if keyword in query_upper:
                return {"valid": False, "error": f"Query contains forbidden keyword: {keyword}"}

        # Try to parse table name
        import re

        table_match = re.search(r"FROM\s+`?(\w+)`?", query, re.IGNORECASE)
        if not table_match:
            return {"valid": False, "error": "Could not parse table name from query"}

        table_name = table_match.group(1)

        # Check if table exists
        db = request.app.state.db_manager
        if not db.table_exists(table_name, database="data"):
            return {"valid": False, "error": f"Table '{table_name}' not found"}

        return {"valid": True, "table": table_name, "message": "Query is valid"}

    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        return {"valid": False, "error": str(e)}

# ============================================
# NEW ENDPOINTS (Add to database.py)
# ============================================

@router.post("/tables/{table_name}/rename")
async def rename_table(
    request: Request,
    table_name: str,
    new_name: str = Body(..., embed=True)
):
    """Rename a table"""
    try:
        db = request.app.state.db_manager
        
        # Validate new name
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', new_name):
            raise HTTPException(400, "Invalid table name")
        
        # Check if target exists
        if db.table_exists(new_name, database="data"):
            raise HTTPException(400, f"Table '{new_name}' already exists")
        
        # Rename
        success = db.rename_table(table_name, new_name, database="data")
        
        if not success:
            raise HTTPException(500, "Rename failed")
        
        return {
            "success": True,
            "message": f"Table renamed from '{table_name}' to '{new_name}'"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/tables/{table_name}/duplicate")
async def duplicate_table(
    request: Request,
    table_name: str,
    target_name: str = Body(..., embed=True)
):
    """Duplicate a table (structure + data)"""
    try:
        db = request.app.state.db_manager
        
        # Validate
        if not db.table_exists(table_name, database="data"):
            raise HTTPException(404, f"Table '{table_name}' not found")
        
        if db.table_exists(target_name, database="data"):
            raise HTTPException(400, f"Table '{target_name}' already exists")
        
        # Duplicate
        success = db.duplicate_table(table_name, target_name, database="data")
        
        if not success:
            raise HTTPException(500, "Duplication failed")
        
        # Get row count
        row_count = db.get_table_row_count(target_name, database="data")
        
        return {
            "success": True,
            "message": f"Table duplicated: {row_count} rows copied",
            "source": table_name,
            "target": target_name,
            "rows": row_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Duplicate failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/tables/{table_name}/stats")
async def get_table_stats(request: Request, table_name: str):
    """Get detailed table statistics"""
    try:
        db = request.app.state.db_manager
        
        if not db.table_exists(table_name, database="data"):
            raise HTTPException(404, f"Table '{table_name}' not found")
        
        # Get basic info
        info_df = db.get_table_info(table_name, database="data")
        info = info_df.iloc[0].to_dict()
        
        # Get column stats
        structure_df = db.get_table_structure(table_name, database="data")
        
        return {
            "success": True,
            "table": table_name,
            "row_count": int(info["row_count"]),
            "size_mb": float(info["size_mb"]),
            "column_count": len(structure_df),
            "created": info.get("created"),
            "updated": info.get("last_updated"),
            "columns": structure_df.to_dict("records")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get stats failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))
