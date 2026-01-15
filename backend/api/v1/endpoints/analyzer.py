"""
Analyzer API endpoints - FIXED
"""

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Body, HTTPException, Request

from backend.models.schemas import AnalysisResult, AnalyzeRequest, AnalyzeResponse
from core.analyzer import AnalyzerService
from core.file_manager import FileManager
from services.db_service import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ✅ Helper function for numpy conversion
def convert_numpy_types(obj: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj


@router.post("/analyze", response_model=AnalyzeResponse)  # ✅ Changed to AnalyzeResponse
async def analyze_data(
    request: Request, body: AnalyzeRequest = None, data: Optional[List[dict]] = Body(None)
):
    """
    Analyze MIB data for quality and statistics
    """
    config = request.app.state.config

    try:
        # Handle direct data input
        if data is not None:
            logger.info(f"Analyzing {len(data)} records from direct data")
            df = pd.DataFrame(data)
            metrics = body.metrics if body else ["all"]

        # Handle source-based input
        elif body and body.source:
            source_path = Path(body.source)

            if source_path.exists() and source_path.is_file():
                exporter = FileManager(config)
                df = exporter.file_to_df(str(source_path))
            else:
                db = DatabaseManager(config)
                if db.table_exists(body.source):
                    df = db.db_to_df(table=body.source)
                else:
                    raise HTTPException(status_code=404, detail=f"Source not found: {body.source}")

            metrics = body.metrics
        else:
            raise HTTPException(
                status_code=400, detail="Either 'source' or 'data' must be provided"
            )

        if df.empty:
            raise HTTPException(status_code=400, detail="No data to analyze")

        logger.info(f"DataFrame shape: {df.shape}, columns: {list(df.columns)[:5]}...")

        # Initialize analyzer
        analyzer = AnalyzerService()

        # Determine metrics to analyze
        if "all" in metrics:
            metrics = ["quality", "coverage", "statistics", "duplicates"]

        results = []

        # Perform analysis for each metric
        for metric in metrics:
            try:
                logger.info(f"Analyzing metric: {metric}")

                if metric == "quality":
                    result = analyzer.analyze_quality(df)
                elif metric == "coverage":
                    result = analyzer.analyze_coverage(df)
                elif metric == "statistics":
                    result = analyzer.analyze_statistics(df)
                elif metric == "duplicates":
                    result = analyzer.analyze_duplicates(df)
                else:
                    logger.warning(f"Unknown metric: {metric}")
                    continue

                # Convert numpy types
                result = convert_numpy_types(result)

                logger.info(f"✅ {metric} analysis complete")

                # ✅ Create AnalysisResult object
                results.append(AnalysisResult(metric=metric, result=result))

            except Exception as metric_error:
                logger.error(f"❌ Failed to analyze {metric}: {metric_error}", exc_info=True)
                results.append(AnalysisResult(metric=metric, result={"error": str(metric_error)}))

        logger.info(f"✅ Analysis complete: {len(results)} metrics")

        # ✅ RETURN AnalyzeResponse object
        return AnalyzeResponse(
            success=True,
            metrics=results,
            records_analyzed=len(df),
            timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/table", response_model=AnalyzeResponse)  # ✅ Changed to AnalyzeResponse
async def analyze_table(
    request: Request,
    table: str = Body(..., embed=True, description="Table name to analyze"),
    database: str = Body("data", description="Database: 'data' or 'jobs'"),
    metrics: List[str] = Body(default=["all"], description="Metrics to calculate"),
    limit: Optional[int] = Body(None, description="Limit rows to analyze"),
):
    """
    Analyze a database table directly.
    """
    try:
        db = request.app.state.db_manager

        if not db.table_exists(table, database=database):
            raise HTTPException(
                status_code=404, detail=f"Table '{table}' not found in '{database}' database"
            )

        logger.info(f"📊 Analyzing table: {database}.{table}")

        # Load data
        df = db.db_to_df(table=table, database=database, limit=limit)

        if df.empty:
            raise HTTPException(status_code=404, detail="Table is empty")

        # Convert to records
        data = df.to_dict("records")

        # Use the existing analyze_data logic
        class MockBody:
            def __init__(self, metrics):
                self.metrics = metrics

        return await analyze_data(request, body=MockBody(metrics), data=data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Table analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Table analysis failed: {str(e)}")


@router.get("/metrics")
async def get_available_metrics():
    """Get available analysis metrics"""
    return {
        "metrics": [
            {"name": "all", "description": "Run all analysis metrics"},
            {"name": "quality", "description": "Analyze data quality and completeness"},
            {"name": "coverage", "description": "Analyze field and notification coverage"},
            {"name": "statistics", "description": "Generate statistical analysis"},
            {"name": "duplicates", "description": "Find and analyze duplicate entries"},
        ]
    }
