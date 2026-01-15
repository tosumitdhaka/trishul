"""
Additional response models
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# from utils.pydantic_validators import validate_datetime_field


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorDetail(BaseModel):
    """Error detail"""

    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response"""

    success: bool = False
    errors: List[ErrorDetail]


class PaginatedResponse(BaseModel):
    """Paginated response"""

    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[Dict[str, Any]]
