"""
Pydantic models for SNMP Walk feature
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


# ============================================
# Device Models
# ============================================

class SNMPDeviceBase(BaseModel):
    """Base SNMP device model"""
    name: str = Field(..., min_length=1, max_length=255)
    ip_address: str = Field(..., description="Device IP address")
    snmp_community: str = Field(default="public", max_length=100)
    snmp_port: int = Field(default=161, ge=1, le=65535)
    enabled: bool = True
    description: Optional[str] = None
    location: Optional[str] = None
    contact: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None


class SNMPDeviceCreate(SNMPDeviceBase):
    """Create SNMP device"""
    pass


class SNMPDeviceUpdate(BaseModel):
    """Update SNMP device (all fields optional)"""
    name: Optional[str] = None
    ip_address: Optional[str] = None
    snmp_community: Optional[str] = None
    snmp_port: Optional[int] = Field(None, ge=1, le=65535)
    enabled: Optional[bool] = None
    description: Optional[str] = None
    location: Optional[str] = None
    contact: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None


class SNMPDevice(SNMPDeviceBase):
    """SNMP device response"""
    id: int
    created_at: datetime
    updated_at: datetime


# ============================================
# Walk Config Models
# ============================================

class SNMPWalkConfigBase(BaseModel):
    """Base walk configuration model"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_oid: str = Field(..., description="Base OID to walk")
    walk_type: str = Field(default="custom", max_length=50)
    enabled: bool = True


class SNMPWalkConfigCreate(SNMPWalkConfigBase):
    """Create walk configuration"""
    pass


class SNMPWalkConfigUpdate(BaseModel):
    """Update walk configuration (all fields optional)"""
    name: Optional[str] = None
    description: Optional[str] = None
    base_oid: Optional[str] = None
    walk_type: Optional[str] = None
    enabled: Optional[bool] = None


class SNMPWalkConfig(SNMPWalkConfigBase):
    """Walk configuration response"""
    id: int
    created_at: datetime
    updated_at: datetime


# ============================================
# Walk Execution Models
# ============================================

class SNMPWalkExecuteRequest(BaseModel):
    """Execute SNMP walk request"""
    device_id: int = Field(..., description="Device ID to walk")
    config_id: Optional[int] = Field(None, description="Walk config ID (optional)")
    base_oid: Optional[str] = Field(None, description="Custom base OID (if config_id not provided)")
    walk_type: str = Field(default="custom", description="Walk type label")
    resolve_oids: bool = Field(default=True, description="Resolve OIDs using trap_master_data")


class SNMPWalkResult(BaseModel):
    """Single walk result"""
    id: int
    device_name: str
    device_ip: str
    config_name: Optional[str]
    base_oid: str
    walk_type: str
    oid: str
    oid_index: Optional[str]
    value: str
    value_type: str
    oid_name: Optional[str]
    oid_description: Optional[str]
    oid_syntax: Optional[str]
    oid_module: Optional[str]
    resolved: bool
    collected_at: datetime
    job_id: Optional[str]


class SNMPWalkExecuteResponse(BaseModel):
    """Walk execution response"""
    success: bool
    message: str
    device_name: str
    device_ip: str
    base_oid: str
    results_count: int
    resolved_count: int
    stored_count: int
    duration: float
    job_id: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Preview of first 100 results (simplified format)"
    )

# ============================================
# Query Models
# ============================================

class SNMPWalkQueryRequest(BaseModel):
    """Query walk results"""
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    config_id: Optional[int] = None
    base_oid: Optional[str] = None
    walk_type: Optional[str] = None
    oid_filter: Optional[str] = Field(None, description="Filter OIDs containing this string")
    resolved_only: bool = Field(default=False, description="Only show resolved OIDs")
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="collected_at", description="Sort column")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class SNMPWalkQueryResponse(BaseModel):
    """Query results response"""
    success: bool
    total: int
    limit: int
    offset: int
    results: List[SNMPWalkResult]


# ============================================
# Statistics Models
# ============================================

class SNMPWalkStats(BaseModel):
    """Walk statistics"""
    total_devices: int
    enabled_devices: int
    total_configs: int
    enabled_configs: int
    total_results: int
    resolved_results: int
    resolution_percentage: float
    last_walk_time: Optional[datetime]
