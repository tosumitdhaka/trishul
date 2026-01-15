"""
Launch script for MIB Parser Tool - Optimized
"""

import sys
import os
from pathlib import Path

# Add parent directory to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Change working directory to project root
os.chdir(root_dir)

import uvicorn
from services.config_service import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Load config
try:
    config = Config()
    
    # ✅ Setup logging with config
    from utils.logger import setup_logging
    setup_logging(config)
    logger = get_logger(__name__)

except Exception as e:
    # Use basic logging if config fails
    import logging
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"❌ Failed to load config: {e}")
    logging.info(f"   Please check config/config.yaml")
    sys.exit(1)



def print_banner():
    """Print startup banner"""
    banner = f"""
══════════════════════════════════════════════════════════════════════
{config.project.name}
Version: {config.project.version}
══════════════════════════════════════════════════════════════════════
"""
    print(banner)


def check_requirements():
    """Check if required directories and files exist"""
    issues = []
    
    # Get current working directory (should be project root now)
    cwd = Path.cwd()
    
    # Check required directories
    required_dirs = [
        "backend",
        "frontend",
        "core",
        "services",
        "config"
    ]
    
    for dir_name in required_dirs:
        dir_path = cwd / dir_name
        if not dir_path.exists():
            issues.append(f"Missing directory: {dir_name} (expected at {dir_path})")
    
    # Check config file
    config_file = cwd / "config" / "config.yaml"
    if not config_file.exists():
        issues.append(f"Missing config file: config/config.yaml (expected at {config_file})")
    
    # Check frontend index
    frontend_index = cwd / "frontend" / "index.html"
    if not frontend_index.exists():
        issues.append(f"Missing frontend: frontend/index.html (expected at {frontend_index})")
    
    return issues

def main():
    """Main entry point"""
    try:
        # Print banner
        print_banner()
        
        # Show current directory
        print(f"📁 Working Directory: {Path.cwd()}")
        
        # Check requirements
        #print("🔍 Checking requirements...")
        issues = check_requirements()
        
        if issues:
            print("❌ Found issues:")
            for issue in issues:
                print(f"   • {issue}")
            print()
            print("💡 Tip: Make sure you're running from the project root or web/ directory")
            print(f"   Current directory: {Path.cwd()}")
            sys.exit(1)
        
        print("✅ All requirements satisfied")
        
        log_level = config.logging.level
        print(f"🔍 Logging Level: {log_level}")
        
        # Start server
        print()
        print(f"🚀 Starting {config.project.name} Server ...")
        print()


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
                
    except KeyboardInterrupt:
        print("\n")
        print("=" * 70)
        print("🛑 Server stopped by user")
        print("=" * 70)
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}", exc_info=True)
        print()
        print("=" * 70)
        print(f"❌ Error: {e}")
        print("=" * 70)
        print()
        print("💡 Troubleshooting tips:")
        print("   1. Check if port is already in use")
        print("   2. Verify database connection settings")
        print("   3. Check logs for detailed error information")
        print("   4. Make sure you're in the correct directory")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
