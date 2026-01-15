"""
API Router aggregation
"""

from fastapi import APIRouter

from backend.api.v1.endpoints import (
    analyzer, database, export, jobs, parser, upload, settings, 
    traps, trap_sync, trap_builder, protobuf, snmp_walk, metrics
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(parser.router, prefix="/parser", tags=["parser"])
api_router.include_router(database.router, prefix="/database", tags=["database"])
api_router.include_router(analyzer.router, prefix="/analyzer", tags=["analyzer"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(traps.router, prefix="/traps", tags=["traps"])
api_router.include_router(trap_sync.router, prefix="/trap-sync", tags=["trap-sync"])
api_router.include_router(trap_builder.router, prefix="/trap-builder", tags=["trap-builder"])
api_router.include_router(snmp_walk.router, prefix="/snmp-walk", tags=["snmp-walk"])
api_router.include_router(protobuf.router, prefix="/protobuf", tags=["protobuf"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])