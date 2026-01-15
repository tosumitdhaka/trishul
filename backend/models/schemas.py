"""
Pydantic models for request/response validation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from utils.pydantic_validators import validate_datetime_field


class ParseMode(str, Enum):
    """Parse modes"""

    FILE = "file"
    DIRECTORY = "directory"
    TEXT = "text"


class DeduplicationStrategy(str, Enum):
    """Deduplication strategies"""

    NONE = "none"
    EXACT = "exact"
    SMART = "smart"


class ImportMode(str, Enum):
    """Database import modes"""

    REPLACE = "replace"
    APPEND = "append"
    FAIL = "fail"


# Request Models
class ParseRequest(BaseModel):
    """Parse request model"""

    source: str = Field(..., description="File path or directory")
    mode: ParseMode = ParseMode.FILE
    recursive: bool = False
    pattern: str = "*.mib"
    no_deps: bool = False
    force_compile: bool = False
    deduplicate: bool = True
    dedup_strategy: DeduplicationStrategy = DeduplicationStrategy.SMART


class ParseTextRequest(BaseModel):
    """Parse text request"""

    content: str = Field(..., description="MIB text content")
    filename: Optional[str] = "inline.mib"
    deduplicate: bool = True


class ImportRequest(BaseModel):
    """Import to database request"""

    source: str
    table: str
    mode: ImportMode = ImportMode.REPLACE
    parse_options: Optional[ParseRequest] = None


class ExportRequest(BaseModel):
    """Export request"""

    table: str
    format: str = "json"
    columns: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None


class AnalyzeRequest(BaseModel):
    """Analyze request"""

    source: str  # Table name or file path
    metrics: List[str] = ["all"]


# Response Models
class ParseResponse(BaseModel):
    """Parse response"""

    success: bool
    records_parsed: int
    files_processed: Optional[int] = None
    files_failed: Optional[int] = None
    duplicates_removed: Optional[int] = None
    duration: float
    errors: List[str] = []
    data: Optional[List[Dict]] = None  # First few records


class ImportResponse(BaseModel):
    """Import response"""

    success: bool
    records_imported: int
    table: str
    mode: str
    duration: float
    errors: List[str] = []


class ExportResponse(BaseModel):
    """Export response"""

    success: bool
    records_exported: int
    format: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None


class TableInfo(BaseModel):
    """Database table information"""

    name: str
    row_count: int
    size_mb: float
    created: Optional[datetime]
    updated: Optional[datetime]
    columns: List[Dict[str, str]]

    # ✅ Critical fix for NaT values
    @field_validator("created", "updated", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        """Handle pandas NaT and None values"""
        return validate_datetime_field(v)


class AnalysisResult(BaseModel):
    """Analysis result"""

    metric: str
    result: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str
    error_code: Optional[str] = None


class AnalyzeResponse(BaseModel):
    success: bool
    metrics: List[AnalysisResult]
    records_analyzed: int
    timestamp: str


# ============================================
# Upload Service Schemas
# ============================================


class UploadSessionResponse(BaseModel):
    """Upload session creation response"""

    success: bool
    session_id: str
    session_path: str
    message: str


class UploadFileResult(BaseModel):
    """Single file upload result"""

    filename: str
    path: Optional[str] = None
    size: Optional[int] = None
    status: str
    error: Optional[str] = None


class UploadFilesResponse(BaseModel):
    """Multiple files upload response"""

    success: bool
    session_id: str
    files_uploaded: int
    files_failed: int
    total_size: int
    files: List[Dict[str, Any]]


class SupportedFile(BaseModel):
    """Supported file info"""

    filename: str
    path: str
    size: int


class IgnoredFile(BaseModel):
    """Ignored file info"""

    filename: str
    reason: str


class ExtractArchiveResponse(BaseModel):
    """Archive extraction response"""

    success: bool
    session_id: str
    archive_filename: str
    total_files: int
    supported_files: List[str]
    ignored_files: List[str]
    extract_dir: str
    total_size: int
    message: Optional[str] = None


class SessionInfoResponse(BaseModel):
    """Session information response"""

    success: bool
    session_id: str
    path: str
    file_count: int
    supported_count: int
    total_size: int
    created: str


# ============================================
# Updated Parser Schemas
# ============================================


class ParseDirectoryRequest(BaseModel):
    """Parse directory request (new)"""

    session_id: str
    deduplicate: bool = True
    dedup_strategy: str = "smart"
    force_compile: bool = False
    job_name: Optional[str] = None


class ParseDirectoryResponse(BaseModel):
    """Parse directory response (enhanced)"""

    success: bool
    session_id: str
    records_parsed: int
    files_processed: int
    files_failed: int
    duplicates_removed: int
    duration: float
    errors: List[str] = []
    data: Optional[List[Dict]] = None
    job_id: Optional[str] = None  # For job creation case
    message: Optional[str] = None  # For status messages
    failed_files: List[Dict[str, str]] = []  # List of {filename, error}
    missing_dependencies: List[str] = []  # List of missing MIB names


# ============================================
# Job Queue Schemas
# ============================================


class JobStatus(str, Enum):
    """Job status enum"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class JobType(str, Enum):
    """Job type enum"""

    PARSE_FILE = "parse_file"
    PARSE_DIRECTORY = "parse_directory"
    PARSE_ARCHIVE = "parse_archive"
    PARSE_TEXT = "parse_text"
    PARSE_SESSION = "parse_session"


class JobMetrics(BaseModel):
    """Job metrics"""

    files_total: int = 0
    files_processed: int = 0
    files_failed: int = 0
    records_parsed: int = 0
    duplicates_removed: int = 0
    bytes_processed: int = 0


class JobCreateRequest(BaseModel):
    """Job creation request"""

    job_type: JobType
    session_id: Optional[str] = None
    params: Dict[str, Any] = {}


# ============================================
# Job Response Schemas (NEW - for database storage)
# ============================================


class JobBase(BaseModel):
    """Base job schema"""

    job_id: str
    job_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("created_at", "started_at", "completed_at", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        """Handle pandas NaT and convert to datetime"""
        return validate_datetime_field(v)


class JobResponse(JobBase):
    """Job response without full data (for list views)"""

    records_count: Optional[int] = None
    errors: Optional[List[str]] = None


class JobDetailResponse(BaseModel):
    """Job detail response with full data"""

    success: bool
    job: Dict[str, Any]


class JobListResponse(BaseModel):
    """Job list response"""

    success: bool
    jobs: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class JobUpdateRequest(BaseModel):
    """Job update request"""

    status: Optional[str] = None
    progress: Optional[int] = None
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class JobStatsResponse(BaseModel):
    """Job statistics response"""

    success: bool
    stats: Dict[str, Any]

# ============================================
# Protobuf Decoder V2 Schemas
# ============================================

class CompileSchemaResponse(BaseModel):
    """Schema compilation response"""
    success: bool
    session_id: str
    message: str
    proto_files: List[str]
    package: Optional[str] = None
    message_types: List[str]
    auto_detected_root: Optional[str] = None
    dependency_scores: Optional[Dict[str, int]] = None
    total_messages: int


# Update existing ProtobufDecodeRequest (if it exists, otherwise add it)
class ProtobufDecodeRequest(BaseModel):
    """Protobuf decode request"""
    session_id: str = Field(..., description="Upload session ID")
    message_type: str = Field(..., description="Root message type for decoding")
    indent: int = Field(2, ge=0, le=8, description="JSON indentation")


# Keep existing ProtobufFileResult (no changes needed)
class ProtobufFileResult(BaseModel):
    """Single protobuf file decode result"""
    filename: str
    output_filename: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    status: str
    fields_decoded: Optional[int] = None
    error: Optional[str] = None


# Keep existing ProtobufDecodeResponse (no changes needed)
class ProtobufDecodeResponse(BaseModel):
    """Protobuf decode response"""
    success: bool
    message: str
    proto_schema: str
    message_type: str
    files_processed: int
    files_success: int
    files_failed: int
    results: List[ProtobufFileResult]
    note: Optional[str] = None


# Keep existing ProtoSchemaValidationResponse (no changes needed)
class ProtoSchemaValidationResponse(BaseModel):
    """Proto schema validation response"""
    success: bool
    valid: bool
    filename: str
    package: Optional[str] = None
    messages: Optional[List[str]] = None
    total_messages: Optional[int] = None
    error: Optional[str] = None
    message: str
