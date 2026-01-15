"""
FastAPI main application - Optimized
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Add parent directories to Python path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.api.v1.api import api_router
from backend.config.websocket import manager as ws_manager
from backend.database.initialize_database import cleanup_databases, initialize_databases
from backend.services.cleanup_service import cleanup_service
from services.config_service import Config
from backend.services.job_service import JobService
from backend.services.export_service import ExportService
from backend.services.snmp_walk_service import SNMPWalkService
from backend.services.metrics_service import init_metrics_service
from backend.services.upload_service import UploadService
from utils.logger import get_logger

logger = get_logger(__name__)

# Global instances
config = None
db_manager = None
job_service = None
export_service = None

# Initialize config
try:
    config = Config()
    
    # ✅ Setup logging with config
    from utils.logger import setup_logging
    setup_logging(config)
    
    logger = get_logger(__name__)
    logger.info("✅ Configuration loaded")
except Exception as e:
    # Use basic logging if config fails
    import logging
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"❌ Failed to load config: {e}")
    raise



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global db_manager, job_service, export_service
    
    app.state.start_time = datetime.now()

    # ============================================
    # STARTUP
    # ============================================
    print("=" * 70)
    print(f"🚀 {config.project.name} API v{config.project.version}")
    print("=" * 70)
    
    logger.info(f"Starting {config.project.name} API v{config.project.version}")
    
    # Initialize WebSocket manager
    app.state.ws_manager = ws_manager
    logger.info("✅ WebSocket manager initialized")
    # print("🔌 WebSocket manager: Active")
    
    # Initialize databases
    try:
        logger.info("Initializing databases...")
        init_result = await initialize_databases(config)
        
        if init_result["success"]:
            
            # Initialize services, first database then others
            db_manager = init_result["db_manager"]
            metrics_service = init_metrics_service(config)
            job_service = JobService(db_manager, ws_manager, config)
            export_service = ExportService(config)
            walk_service = SNMPWalkService(db_manager, ws_manager)
            upload_service = UploadService()
            
            app.state.db_manager = db_manager
            app.state.metrics_service = metrics_service
            app.state.job_service = job_service
            app.state.export_service = export_service
            app.state.walk_service = walk_service
            app.state.upload_service = upload_service 
            
            logger.info("✅ Databases initialized successfully")
            logger.info("✅ SNMPWalkService initialized")
            logger.info("✅ JobService initialized")
            logger.info("✅ ExportService initialized")
            logger.info("✅ Metrics service initialized")
            logger.info("✅ Upload service initialized")

            #print("⚙️ JobService: Active")
            #print("📤 ExportService: Active")
            #print("🚶 SNMPWalkService: Active")
            
            
            # Show database status
            health = init_result.get("health", {})
            print("=" * 70)
            print("📊 Database Status:")
            
            for db_name, db_health in health.items():
                status = db_health.get("status", "unknown")
                icon = "✅" if status == "healthy" else "⚠️"
                db_display = db_name.replace("_", " ").title()
                print(f"   {icon} {db_display}: {status}")
                
                if db_health.get("error"):
                    print(f"      Error: {db_health['error']}")
            print("=" * 70)
        else:
            print("=" * 70)
            logger.error("❌ Database initialization failed")
            if "error" in init_result:
                logger.error(f"Error: {init_result['error']}")
            print("⚠️  Warning: Database initialization failed, some features may not work")
            print("=" * 70)
    
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}", exc_info=True)
        print("=" * 70)
        print("⚠️  Warning: Database initialization error, some features may not work")
        print("=" * 70)
    
    # Start cleanup service
    try:
        cleanup_service.start(config, db_manager)
        logger.info("✅ Cleanup service started")
        # print("🧹 Cleanup service: Active")
    except ImportError:
        logger.debug("Cleanup service not available")
    except Exception as e:
        logger.warning(f"⚠️ Cleanup service not started: {e}")
    
    # Show server info
    print("=" * 70)
    print("🌐 Server Endpoints:")
    print(f"   • Frontend:  http://{config.web.host}:{config.web.port}")
    print(f"   • API Docs:  http://{config.web.host}:{config.web.port}/docs")
    print(f"   • Health:    http://{config.web.host}:{config.web.port}{config.web.api_v1_prefix}/health")
    # print(f"   • WebSocket: ws://{config.web.host}:{config.web.port}{config.web.api_v1_prefix}/jobs/ws/{{job_id}}")
    print("=" * 70)
    print("✅ Server ready! Press CTRL+C to stop")
    print("=" * 70)
    print()
    
    yield
    
    # ============================================
    # SHUTDOWN
    # ============================================
    print()
    print("=" * 70)
    print(f"🛑 Shutting down {config.project.name} API")
    print("=" * 70)
    
    logger.info(f"Shutting down {config.project.name} API")
    
    # Close WebSocket connections
    try:
        for connection in ws_manager.active_connections:
            try:
                await connection.close()
            except:
                pass
        logger.info("✅ WebSocket connections closed")
        # print("✅ WebSocket connections closed")
    except Exception as e:
        logger.warning(f"⚠️ WebSocket cleanup error: {e}")
    
    # Shutdown metrics service
    try:
        metrics_service.shutdown()
        logger.info("✅ Metrics service shutted down")
    except:
        logger.warning(f"⚠️ Metrics service shutdown error: {e}")

    # Cleanup databases
    try:
        await cleanup_databases(db_manager)
        logger.info("✅ Database connections closed")
        # print("✅ Database connections closed")
    except Exception as e:
        logger.warning(f"⚠️ Database cleanup error: {e}")
    
    # Stop cleanup service
    try:
        cleanup_service.stop()
        logger.info("✅ Cleanup service stopped")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"⚠️ Cleanup service stop error: {e}")
    
    print("=" * 70)
    print("✅ Shutdown complete")
    print("=" * 70)
    print()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    logger.info("Creating FastAPI application...")
    
    app = FastAPI(
        title=f"{config.project.name} API",
        description=f"API for {config.project.name}",
        version=config.project.version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{config.web.api_v1_prefix}/openapi.json",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.web.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("✅ CORS middleware configured")
    
    # Store config in app state
    app.state.config = config
    app.state.db_manager = None  # Will be set during lifespan startup
    app.state.ws_manager = None  # Will be set during lifespan startup
    app.state.job_service = None
    app.state.export_service = None
    
    # Include API router
    try:
        app.include_router(api_router, prefix=config.web.api_v1_prefix)
        logger.info("✅ API routes registered")
    except Exception as e:
        logger.error(f"❌ Failed to register routes: {e}")
        raise
    
    # Mount static files
    try:
        # Frontend assets
        frontend_dir = Path("frontend")
        if frontend_dir.exists():
            app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
            app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
            app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")
            logger.info("✅ Frontend assets mounted")
        
        # Exports directory
        export_dir = Path(config.export.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/exports", StaticFiles(directory=str(export_dir)), name="exports")
        logger.info("✅ Exports directory mounted")
    
    except Exception as e:
        logger.warning(f"⚠️ Failed to mount static files: {e}")
    
    # Root endpoint - serve frontend
    @app.get("/")
    async def root():
        """Serve frontend application"""
        frontend_index = Path("frontend/index.html")
        if frontend_index.exists():
            return FileResponse(frontend_index)
        else:
            return {
                "message": f"Welcome to {config.project.name} API",
                "version": config.project.version,
                "docs": "/docs",
            }
    
    # Health check endpoint
    @app.get(f"{config.web.api_v1_prefix}/health")
    async def health_check():
        """Health check endpoint"""
        health_status = {
            "status": "healthy",
            "service": config.project.name,
            "version": config.project.version,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Add database health if available
        if db_manager:
            try:
                db_health = db_manager.health_check()
                health_status["databases"] = db_health
                
                # Overall database status
                all_healthy = all(db.get("status") == "healthy" for db in db_health.values())
                health_status["database_status"] = "healthy" if all_healthy else "degraded"
            
            except Exception as e:
                health_status["databases"] = {"status": "error", "error": str(e)}
                health_status["database_status"] = "unhealthy"
        else:
            health_status["databases"] = {"status": "not_initialized"}
            health_status["database_status"] = "not_initialized"
        
        return health_status
    
    logger.info("✅ Application created successfully")
    return app


# Create application instance
logger.info("Initializing application...")
app = create_app()
logger.info("✅ Application initialized")


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print(f"🚀 Starting {config.project.name} Server ...")
    print("=" * 70)

    log_level = config.logging.level
    
    # Run uvicorn server (simple approach)
    uvicorn.run(
        "backend.main:app",
        host=config.web.host,
        port=config.web.port,
        reload=True,
        reload_dirs=["backend", "frontend", "core", "services", "config"],
        log_level=log_level.lower(),
        access_log=False,  # ✅ Disable access logs (reduces noise)
        use_colors=False   # ✅ Disable colors for consistent format
    )
