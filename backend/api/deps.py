"""
API Dependencies - Reusable dependencies for FastAPI endpoints
"""

from datetime import datetime
from typing import Generator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from services.config_service import Config, settings
from services.db_service import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Optional Bearer token for authentication
security = HTTPBearer(auto_error=False)

