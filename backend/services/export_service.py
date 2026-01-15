
#!/usr/bin/env python3
"""
Export Service - Unified export operations

Thin wrapper around FileManager - delegates all operations.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

from core.file_manager import FileManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ExportService:
    """
    Unified export service - delegates to FileManager
    
    Responsibilities:
    - Provide simple API for exports
    - Delegate all operations to FileManager
    - Return standardized results
    
    Example:
        ```python
        export_service = ExportService(config)
        
        result = await export_service.export_dataframe(
            df=my_dataframe,
            base_name="my_export",
            format="csv",
            compress=True
        )
        ```
    """
    
    def __init__(self, config):
        """
        Initialize export service
        
        Args:
            config: Application config
        """
        self.config = config
        self.file_manager = FileManager(config)
        self.logger = get_logger(self.__class__.__name__)
    
    async def export_dataframe(
        self,
        df: pd.DataFrame,
        base_name: str,
        format: str,
        compress: bool = False,
        compression: str = None
    ) -> Dict[str, Any]:
        """
        Export DataFrame to file - delegates to FileManager
        
        Args:
            df: DataFrame to export
            base_name: Base name for file (e.g., 'table_name' or 'job_id')
            format: Export format (csv, json, excel, yaml, parquet)
            compress: Whether to compress as ZIP
            custom_filename: Optional custom filename (without extension)
        
        Returns:
            Dict with:
                - output_path: Path object
                - filename: Final filename
                - file_size: File size in bytes
        
        Raises:
            Exception: If export fails
        """
        try:

            # ✅ Determine compression type
            compression_type = None
            if compress:
                if compression:
                    # Use specified compression
                    compression_type = compression
                else:
                    # Use default from config
                    compression_type = self.config.export.compression or 'zip'
            
            result_path = await self.file_manager.df_to_file_async(
                df=df,
                base_name=base_name,  # ✅ Just filename, FileManager adds export_dir
                format=format,
                compression=compression_type
            )
            
            # ✅ FileManager returns final path after all operations
            file_size = result_path.stat().st_size
            
            self.logger.info(f"✅ Export complete: {result_path.name} ({file_size:,} bytes)")
            
            return {
                "output_path": result_path,
                "filename": result_path.name,
                "file_size": file_size,
            }
        
        except Exception as e:
            self.logger.error(f"❌ Export failed: {e}", exc_info=True)
            raise
    
    def get_mime_type(self, format: str) -> str:
        """
        Get MIME type for format - delegates to FileManager
        
        Args:
            format: Export format
        
        Returns:
            MIME type string
        """
        return self.file_manager.get_mime_type(format)
    
    
    @staticmethod
    def get_supported_formats() -> list:
        """
        Get supported export formats - delegates to FileManager
        
        Returns:
            List of format strings
        """
        return FileManager.SUPPORTED_FORMATS
    
    @staticmethod
    def get_supported_compressions() -> list:
        """
        Get supported compression types - delegates to FileManager
        
        Returns:
            List of compression type strings
        """
        return FileManager.get_supported_compressions()