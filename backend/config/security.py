"""
Security utilities for authentication and authorization
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create JWT access token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject), "iat": datetime.utcnow(), "type": "access"}

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT refresh token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # 7 days for refresh token

    to_encode = {"exp": expire, "sub": str(subject), "iat": datetime.utcnow(), "type": "refresh"}

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify JWT token
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"Token decode error: {e}")
        return None


def generate_api_key() -> str:
    """
    Generate a secure API key
    """
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash
    """
    return hash_api_key(api_key) == hashed_key


class PermissionChecker:
    """
    Check user permissions
    """

    def __init__(self, required_permissions: list):
        self.required_permissions = required_permissions

    def __call__(self, user: dict) -> bool:
        """
        Check if user has required permissions
        """
        if not user:
            return False

        user_permissions = user.get("permissions", [])

        # Check if user has all required permissions
        for permission in self.required_permissions:
            if permission not in user_permissions:
                return False

        return True


# Permission constants
class Permissions:
    """
    Permission constants
    """

    # Parser permissions
    PARSE_FILE = "parse:file"
    PARSE_DIRECTORY = "parse:directory"

    # Database permissions
    DB_READ = "db:read"
    DB_WRITE = "db:write"
    DB_DELETE = "db:delete"

    # Export permissions
    EXPORT_DATA = "export:data"

    # Admin permissions
    ADMIN_ALL = "admin:all"


# Role definitions
ROLES = {
    "viewer": [
        Permissions.DB_READ,
    ],
    "user": [
        Permissions.PARSE_FILE,
        Permissions.DB_READ,
        Permissions.EXPORT_DATA,
    ],
    "power_user": [
        Permissions.PARSE_FILE,
        Permissions.PARSE_DIRECTORY,
        Permissions.DB_READ,
        Permissions.DB_WRITE,
        Permissions.EXPORT_DATA,
    ],
    "admin": [
        Permissions.ADMIN_ALL,
    ],
}


def get_role_permissions(role: str) -> list:
    """
    Get permissions for a role
    """
    return ROLES.get(role, [])


def has_permission(user: dict, permission: str) -> bool:
    """
    Check if user has a specific permission
    """
    if not user:
        return False

    # Admin has all permissions
    if Permissions.ADMIN_ALL in user.get("permissions", []):
        return True

    return permission in user.get("permissions", [])


# Security headers middleware
def get_security_headers() -> dict:
    """
    Get security headers for responses
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }


# Input sanitization
def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input
    """
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Remove control characters
    import re

    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    # Remove potential SQL injection patterns (basic)
    dangerous_patterns = [
        r";\s*DROP\s+",
        r";\s*DELETE\s+",
        r";\s*UPDATE\s+",
        r";\s*INSERT\s+",
        r"--",
        r"/\*.*\*/",
    ]

    for pattern in dangerous_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


# Session management
class SessionManager:
    """
    Simple session manager (use Redis in production)
    """

    def __init__(self):
        self.sessions = {}

    def create_session(self, user_id: str, data: dict) -> str:
        """
        Create a new session
        """
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            "user_id": user_id,
            "data": data,
            "created_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """
        Get session data
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session["last_accessed"] = datetime.utcnow()

            # Check if session expired (24 hours)
            if (datetime.utcnow() - session["created_at"]).days >= 1:
                del self.sessions[session_id]
                return None

            return session
        return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self):
        """
        Remove expired sessions
        """
        now = datetime.utcnow()
        expired = []

        for session_id, session in self.sessions.items():
            if (now - session["created_at"]).days >= 1:
                expired.append(session_id)

        for session_id in expired:
            del self.sessions[session_id]

        return len(expired)


# Global session manager instance
session_manager = SessionManager()
