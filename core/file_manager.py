#!/usr/bin/env python3
"""
File Exporter - Optimized for Web/API Integration
Handles file import/export operations with streaming support
Supports: CSV, JSON, YAML, Excel, Parquet, HTML, XML
"""

import io
import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Generator, Optional

import pandas as pd
import yaml

from utils.logger import get_logger


class FileManager:
    """Optimized file import/export handler for Web/API integration."""

    SUPPORTED_FORMATS = ["csv", "tsv", "json", "jsonl", "yaml", "excel", "parquet", "html", "xml"]
    COMPRESSION_TYPES = ["gzip", "zip", "bz2", "xz"]
    DEFAULT_CHUNK_SIZE = 10000

    def __init__(self, config):
        """Initialize file exporter with web optimizations."""
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

        # Export settings
        self.export_dir = Path(config.export.export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

        self.chunk_size = getattr(config.export, "chunk_size", self.DEFAULT_CHUNK_SIZE)
        self.include_timestamp = getattr(config.export, "include_timestamp", False)
        self.timestamp_format = getattr(config.export, "timestamp_format", "%Y%m%d_%H%M%S")
        self.compression = getattr(config.export, "compression", None)

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Statistics
        self.stats = {
            "files_exported": 0,
            "files_imported": 0,
            "bytes_exported": 0,
            "bytes_imported": 0,
            "errors": 0,
        }

    # ============= CORE EXPORT METHODS =============

    def df_to_file(
        self,
        df: pd.DataFrame,
        base_name: str,
        format: Optional[str] = None,
        compression: Optional[str] = None,
        **kwargs,
    ) -> Path:
        """
        Export DataFrame to file with auto-detection.
        
        Args:
            df: DataFrame to export
            path: Output file path (relative or absolute)
            format: Export format (auto-detected if None or 'auto')
            compression: Compression type (optional)
            **kwargs: Format-specific options
        
        Returns:
            Path: Final output file path (after timestamp/compression)
        """
        if df is None or df.empty:
            self.logger.warning("Empty DataFrame, nothing to export")
            raise ValueError("Cannot export empty DataFrame")
        
        try:

            # ✅ Step 1: Validate format
            format = format.lower()
            if format not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {format}")
            
            # ✅ Step 2: Add timestamp if configured
            timestamp = datetime.now().strftime(self.timestamp_format)
            if self.include_timestamp:
                base_name = f"{base_name}_{timestamp}"

            # ✅ Step 3: Add extension to filename
            extension = self.get_file_extension(format)
            filename = f"{base_name}{extension}"
            
            # ✅ Step 4: Resolve output path (handles relative paths)
            output_path = self._resolve_output_path(filename)
            
            # ✅ Step 5: Export based on format
            self.logger.info(f"Exporting {len(df)} rows to {output_path.name} ({format})")
            
            export_method = getattr(self, f"_export_{format}", None)
            if export_method:
                export_method(df, output_path, **kwargs)
            else:
                raise ValueError(f"No export method for format: {format}")
            
            # ✅ Step 6: Validate file exists
            if not output_path.exists():
                raise FileNotFoundError(f"Export failed: File not created at {output_path}")
            
            # ✅ Step 7: Apply compression if requested
            compression = compression or self.compression
            if compression:
                output_path = self._compress_file(output_path, compression)
            
            # ✅ Step 8: Final validation
            if not output_path.exists():
                raise FileNotFoundError(f"Final file not found: {output_path}")
            
            # ✅ Step 9: Update statistics
            file_size = output_path.stat().st_size
            self.stats["files_exported"] += 1
            self.stats["bytes_exported"] += file_size
            
            self._log_export_success(output_path, len(df), file_size)
            
            # ✅ Return final path
            return output_path
        
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            self.stats["errors"] += 1
            raise


    async def df_to_file_async(
        self, 
        df: pd.DataFrame, 
        base_name: str, 
        format: Optional[str] = None, 
        compression: Optional[str] = None, 
        **kwargs
    ) -> Path:
        """
        Async version for web integration.
        
        Returns:
            Path: Final output file path
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, 
            self.df_to_file, 
            df, 
            base_name, 
            format, 
            compression,
            **kwargs
        )


    def df_to_buffer(self, df: pd.DataFrame, format: str = "csv", **kwargs) -> io.BytesIO:
        """
        Export DataFrame to in-memory buffer for streaming.
        Used for web downloads without creating files.

        Returns:
            BytesIO buffer with exported data
        """
        buffer = io.BytesIO()

        try:
            if format == "csv":
                text_buffer = io.StringIO()
                df.to_csv(text_buffer, index=False, **kwargs)
                buffer.write(text_buffer.getvalue().encode("utf-8"))

            elif format == "json":
                df.to_json(buffer, orient="records", indent=2)

            elif format == "excel":
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, **kwargs)

            elif format == "parquet":
                df.to_parquet(buffer, index=False, **kwargs)

            else:
                raise ValueError(f"Buffer export not supported for format: {format}")

            buffer.seek(0)
            return buffer

        except Exception as e:
            self.logger.error(f"Buffer export failed: {e}")
            raise

    def stream_csv(self, df: pd.DataFrame, chunk_size: int = 1000) -> Generator[str, None, None]:
        """
        Stream CSV data in chunks for large datasets.
        Used for streaming responses in web APIs.

        Yields:
            CSV string chunks
        """
        # Yield header
        yield ",".join(df.columns) + "\n"

        # Yield data in chunks
        for start in range(0, len(df), chunk_size):
            chunk = df.iloc[start : start + chunk_size]
            yield chunk.to_csv(index=False, header=False)

    # ============= CORE IMPORT METHODS =============

    def file_to_df(self, path: str, format: Optional[str] = None, **kwargs) -> pd.DataFrame:
        """
        Import file to DataFrame with auto-detection.

        Args:
            path: Input file path
            format: File format (auto-detected if None)
            **kwargs: Format-specific options

        Returns:
            DataFrame with imported data
        """
        try:
            input_path = Path(path)

            if not input_path.exists():
                self.logger.error(f"File not found: {input_path}")
                return pd.DataFrame()

            # Handle compressed files
            original_path = input_path
            if input_path.suffix in [".gz", ".zip", ".bz2", ".xz"]:
                input_path = self._decompress_file(input_path)

            # Auto-detect format
            if not format:
                format = self._detect_format(input_path)

            format = format.lower()

            if format not in self.SUPPORTED_FORMATS:
                self.logger.error(f"Unsupported format: {format}")
                return pd.DataFrame()

            # Import based on format
            import_method = getattr(self, f"_import_{format}", None)
            if import_method:
                df = import_method(input_path, **kwargs)
            else:
                raise ValueError(f"No import method for format: {format}")

            # Update statistics
            file_size = original_path.stat().st_size
            self.stats["files_imported"] += 1
            self.stats["bytes_imported"] += file_size

            self.logger.info(f"Imported {len(df)} rows from {original_path.name}")

            return df

        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            self.stats["errors"] += 1
            return pd.DataFrame()

    async def file_to_df_async(
        self, path: str, format: Optional[str] = None, **kwargs
    ) -> pd.DataFrame:
        """Async version for web integration."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.file_to_df, path, format, **kwargs)

    # ============= FORMAT-SPECIFIC EXPORT METHODS =============

    def _export_csv(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to CSV format."""
        df.to_csv(
            path,
            index=False,
            encoding="utf-8",
            sep=kwargs.get("sep", ","),
            na_rep=kwargs.get("na_rep", ""),
            chunksize=kwargs.get("chunksize", None),
        )

    def _export_tsv(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to TSV format."""
        kwargs["sep"] = "\t"
        self._export_csv(df, path, **kwargs)

    def _export_json(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to JSON format."""
        # Clean data for JSON
        df_clean = self._prepare_for_json(df)

        df_clean.to_json(
            path,
            orient=kwargs.get("orient", "records"),
            indent=kwargs.get("indent", 2),
            date_format="iso",
            default_handler=str,
        )

    def _export_jsonl(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to JSON Lines format."""
        df_clean = self._prepare_for_json(df)
        df_clean.to_json(path, orient="records", lines=True)

    def _export_yaml(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to YAML format."""
        df_clean = self._prepare_for_json(df)
        data = df_clean.to_dict("records")

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def _export_excel(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to Excel format."""
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            # Main sheet
            sheet_name = kwargs.get("sheet_name", "Data")
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Optional summary sheet
            if kwargs.get("include_summary", False):
                summary = self._create_summary(df)
                summary.to_excel(writer, sheet_name="Summary", index=False)

            # Auto-adjust columns
            if kwargs.get("auto_adjust", True):
                self._adjust_excel_columns(writer)

    def _export_parquet(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to Parquet format."""
        df.to_parquet(
            path,
            index=False,
            compression=kwargs.get("compression", "snappy"),
            engine=kwargs.get("engine", "auto"),
        )

    def _export_html(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to HTML format."""
        html = self._create_html_report(df, **kwargs)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _export_xml(self, df: pd.DataFrame, path: Path, **kwargs):
        """Export to XML format."""
        df.to_xml(
            path,
            root_name=kwargs.get("root_name", "data"),
            row_name=kwargs.get("row_name", "record"),
            index=False,
        )

    # ============= FORMAT-SPECIFIC IMPORT METHODS =============

    def _import_csv(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from CSV format."""
        return pd.read_csv(
            path,
            encoding=kwargs.get("encoding", "utf-8"),
            sep=kwargs.get("sep", ","),
            chunksize=kwargs.get("chunksize", None),
        )

    def _import_tsv(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from TSV format."""
        kwargs["sep"] = "\t"
        return self._import_csv(path, **kwargs)

    def _import_json(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from JSON format."""
        return pd.read_json(path, orient=kwargs.get("orient", "records"), encoding="utf-8")

    def _import_jsonl(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from JSON Lines format."""
        return pd.read_json(path, lines=True)

    def _import_yaml(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from YAML format."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return pd.DataFrame(data)

    def _import_excel(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from Excel format."""
        sheet_name = kwargs.get("sheet_name", 0)
        return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")

    def _import_parquet(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from Parquet format."""
        return pd.read_parquet(path, engine=kwargs.get("engine", "auto"))

    def _import_xml(self, path: Path, **kwargs) -> pd.DataFrame:
        """Import from XML format."""
        return pd.read_xml(path, xpath=kwargs.get("xpath", ".//record"))

    # ============= HELPER METHODS =============

    def _detect_format(self, path: Path) -> str:
        """Auto-detect file format from extension."""
        suffix = path.suffix.lower().lstrip(".")

        format_map = {
            "csv": "csv",
            "tsv": "tsv",
            "txt": "csv",  # Assume CSV for .txt
            "json": "json",
            "jsonl": "jsonl",
            "yaml": "yaml",
            "yml": "yaml",
            "xlsx": "excel",
            "xls": "excel",
            "parquet": "parquet",
            "pq": "parquet",
            "html": "html",
            "htm": "html",
            "xml": "xml",
        }

        return format_map.get(suffix, "csv")

    def _prepare_for_json(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare DataFrame for JSON/YAML export."""
        df_copy = df.copy()

        # Convert datetime to ISO format
        for col in df_copy.select_dtypes(include=["datetime64"]).columns:
            df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Replace NaN with None
        df_copy = df_copy.where(pd.notna(df_copy), None)

        return df_copy

    def _create_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create summary statistics."""
        summary = []

        summary.append({"Metric": "Total Records", "Value": len(df)})
        summary.append({"Metric": "Columns", "Value": len(df.columns)})

        if "node_type" in df.columns:
            for node_type, count in df["node_type"].value_counts().head(10).items():
                summary.append({"Metric": f"Type: {node_type}", "Value": count})

        summary.append({"Metric": "Export Time", "Value": datetime.now().isoformat()})

        return pd.DataFrame(summary)

    def _create_html_report(self, df: pd.DataFrame, **kwargs) -> str:
        """Create HTML report with styling."""
        title = kwargs.get("title", "Data Export")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        .info {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #3498db; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="info">
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Records: {len(df):,}</p>
    </div>
    {df.to_html(index=False, classes='data-table', table_id='export-table')}
</body>
</html>
"""

    def _adjust_excel_columns(self, writer):
        """Auto-adjust Excel column widths."""
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]

            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter

                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass

                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    def _resolve_output_path(self, path: str) -> Path:
        """Resolve output path."""
        output_path = Path(path)

        if not output_path.is_absolute():
            output_path = self.export_dir / output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        return output_path

    def _compress_file(self, path: Path, compression: str) -> Path:
        """Compress file."""
        if compression not in self.COMPRESSION_TYPES:
            self.logger.warning(f"Unknown compression: {compression}")
            return path

        try:
            if compression == "gzip":
                import gzip

                compressed = path.with_suffix(path.suffix + ".gz")
                with open(path, "rb") as f_in:
                    with gzip.open(compressed, "wb") as f_out:
                        f_out.write(f_in.read())

            elif compression == "zip":
                import zipfile

                compressed = path.with_suffix(".zip")
                with zipfile.ZipFile(compressed, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(path, path.name)

            elif compression == "bz2":
                import bz2

                compressed = path.with_suffix(path.suffix + ".bz2")
                with open(path, "rb") as f_in:
                    with bz2.open(compressed, "wb") as f_out:
                        f_out.write(f_in.read())

            elif compression == "xz":
                import lzma

                compressed = path.with_suffix(path.suffix + ".xz")
                with open(path, "rb") as f_in:
                    with lzma.open(compressed, "wb") as f_out:
                        f_out.write(f_in.read())

            path.unlink()  # Remove original
            return compressed

        except Exception as e:
            self.logger.error(f"Compression failed: {e}")
            return path

    def _decompress_file(self, path: Path) -> Path:
        """Decompress file."""
        try:
            if path.suffix == ".gz":
                import gzip

                decompressed = path.with_suffix("")
                with gzip.open(path, "rb") as f_in:
                    with open(decompressed, "wb") as f_out:
                        f_out.write(f_in.read())
                return decompressed

            elif path.suffix == ".zip":
                import zipfile

                with zipfile.ZipFile(path, "r") as zf:
                    names = zf.namelist()
                    if names:
                        zf.extract(names[0], path.parent)
                        return path.parent / names[0]

            elif path.suffix == ".bz2":
                import bz2

                decompressed = path.with_suffix("")
                with bz2.open(path, "rb") as f_in:
                    with open(decompressed, "wb") as f_out:
                        f_out.write(f_in.read())
                return decompressed

            elif path.suffix == ".xz":
                import lzma

                decompressed = path.with_suffix("")
                with lzma.open(path, "rb") as f_in:
                    with open(decompressed, "wb") as f_out:
                        f_out.write(f_in.read())
                return decompressed

            return path

        except Exception as e:
            self.logger.error(f"Decompression failed: {e}")
            return path

    def _log_export_success(self, path: Path, rows: int, size: int):
        """Log export success."""
        size_str = (
            f"{size / (1024*1024):.2f} MB" if size > 1024 * 1024 else f"{size / 1024:.2f} KB"
        )
        self.logger.info(f"✅ Export complete: {rows:,} records to {path.name} ({size_str})")

    # ============= WEB/API SPECIFIC METHODS =============

    def get_mime_type(self, format: str) -> str:
        """Get MIME type for format (for web downloads)."""
        mime_types = {
            "csv": "text/csv",
            "tsv": "text/tab-separated-values",
            "json": "application/json",
            "jsonl": "application/x-ndjson",
            "yaml": "text/yaml",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "parquet": "application/octet-stream",
            "html": "text/html",
            "xml": "application/xml",
        }
        return mime_types.get(format, "application/octet-stream")

    def get_file_extension(self, format: str) -> str:
        """Get file extension for format."""
        extensions = {
            "csv": ".csv",
            "tsv": ".tsv",
            "json": ".json",
            "jsonl": ".jsonl",
            "yaml": ".yaml",
            "excel": ".xlsx",
            "parquet": ".parquet",
            "html": ".html",
            "xml": ".xml",
        }
        return extensions.get(format, ".dat")
    
    @classmethod
    def get_supported_compressions(cls) -> list:
        """
        Get list of supported compression types.
        
        Returns:
            List of compression type strings
        """
        return cls.COMPRESSION_TYPES


    def validate_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Validate DataFrame structure."""
        return {
            "valid": not df.empty,
            "rows": len(df),
            "columns": len(df.columns),
            "memory_mb": df.memory_usage(deep=True).sum() / (1024 * 1024),
            "dtypes": df.dtypes.value_counts().to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get exporter statistics."""
        return {
            **self.stats,
            "supported_formats": self.SUPPORTED_FORMATS,
            "compression_types": self.COMPRESSION_TYPES,
        }

    def close(self):
        """Cleanup resources."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=True)
