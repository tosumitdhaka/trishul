#!/usr/bin/env python3
"""
Shared Pydantic Validators

Reusable field validators for Pydantic models to avoid duplication.
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def validate_datetime_field(v) -> Optional[datetime]:
    """
    Shared datetime validator for Pydantic models.
    
    Handles:
    - None values
    - pandas NaT (Not a Time)
    - ISO format strings
    - datetime objects
    
    Args:
        v: Value to validate
    
    Returns:
        datetime object or None
    
    Example:
        ```python
        from pydantic import BaseModel, field_validator
        from utils.pydantic_validators import validate_datetime_field
        
        class MyModel(BaseModel):
            created_at: Optional[datetime]
            
            @field_validator("created_at", mode="before")
            @classmethod
            def validate_created_at(cls, v):
                return validate_datetime_field(v)
        ```
    """
    # Handle None
    if v is None:
        return None
    
    # Handle pandas NaT (Not a Time)
    if isinstance(v, float) and pd.isna(v):
        return None
    
    if pd.isna(v):
        return None
    
    # Handle ISO format strings
    if isinstance(v, str):
        try:
            # Handle ISO format with timezone
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    
    # Return as-is if already datetime
    if isinstance(v, datetime):
        return v
    
    # Unknown type
    return None


def validate_optional_int(v) -> Optional[int]:
    """
    Validate optional integer field.
    
    Handles:
    - None values
    - pandas NaN
    - String integers
    - Float to int conversion
    
    Args:
        v: Value to validate
    
    Returns:
        int or None
    """
    if v is None:
        return None
    
    if pd.isna(v):
        return None
    
    if isinstance(v, str):
        try:
            return int(v)
        except (ValueError, TypeError):
            return None
    
    if isinstance(v, float):
        if pd.isna(v):
            return None
        return int(v)
    
    if isinstance(v, int):
        return v
    
    return None


def validate_optional_float(v) -> Optional[float]:
    """
    Validate optional float field.
    
    Handles:
    - None values
    - pandas NaN
    - String floats
    
    Args:
        v: Value to validate
    
    Returns:
        float or None
    """
    if v is None:
        return None
    
    if pd.isna(v):
        return None
    
    if isinstance(v, str):
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    
    if isinstance(v, (int, float)):
        if pd.isna(v):
            return None
        return float(v)
    
    return None