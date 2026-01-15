"""
Settings API - Simple JSON Response
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
from pathlib import Path
from datetime import datetime
from ruamel.yaml import YAML

from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class SettingUpdate(BaseModel):
    """Single setting update"""
    path: str  # Dot-separated path (e.g., 'parser.cache_enabled')
    value: Any


class BulkSettingsUpdate(BaseModel):
    """Multiple setting updates"""
    updates: List[SettingUpdate]


# ============================================
# YAML Manager (Simple)
# ============================================

class SimpleYAMLManager:
    """Simple YAML manager with comment preservation"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self.yaml.width = 4096
        self.yaml.indent(mapping=2, sequence=2, offset=0)
    
    def load(self) -> Dict[str, Any]:
        """Load YAML file"""
        try:
            if not self.config_path.exists():
                logger.error(f"Config file not found: {self.config_path}")
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = self.yaml.load(f)
            
            logger.info(f"✅ Loaded config from {self.config_path}")
            return dict(data) if data else {}
            
        except Exception as e:
            logger.error(f"Failed to load YAML: {e}", exc_info=True)
            return {}
    
    def save(self, data: Dict[str, Any]) -> bool:
        """Save YAML file with backup"""
        try:
            # Create backup
            self._create_backup()
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.yaml.dump(data, f)
            
            logger.info(f"✅ Saved config to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save YAML: {e}", exc_info=True)
            return False
    
    def update_value(self, data: Dict, path: str, value: Any) -> Dict:
        """Update value by dot-separated path"""
        keys = path.split('.')
        current = data
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set value
        final_key = keys[-1]
        
        # Preserve type
        if final_key in current:
            old_value = current[final_key]
            if isinstance(old_value, bool):
                value = bool(value)
            elif isinstance(old_value, int):
                value = int(value)
            elif isinstance(old_value, float):
                value = float(value)
        
        current[final_key] = value
        logger.info(f"Updated {path}: {value}")
        
        return data
    
    def _create_backup(self):
        """Create timestamped backup"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.config_path.parent / f"{self.config_path.name}.backup.{timestamp}"
            
            import shutil
            shutil.copy2(self.config_path, backup_path)
            
            logger.info(f"✅ Created backup: {backup_path}")
            
            # Keep only last 5 backups
            self._cleanup_old_backups()
            
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _cleanup_old_backups(self, keep: int = 5):
        """Keep only recent backups"""
        try:
            backup_pattern = f"{self.config_path.name}.backup.*"
            backups = sorted(
                self.config_path.parent.glob(backup_pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for backup in backups[keep:]:
                backup.unlink()
                logger.info(f"Deleted old backup: {backup}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup backups: {e}")


# ============================================
# Endpoints
# ============================================

@router.get("/")
async def get_all_settings(request: Request):
    """
    Get all settings as flat JSON.
    
    Returns:
        All config.yaml fields as JSON
    """
    try:
        logger.info("📡 GET /api/v1/settings/ - Loading settings...")
        
        yaml_manager = SimpleYAMLManager()
        data = yaml_manager.load()
        
        logger.info(f"✅ Settings loaded: {list(data.keys())}")
        
        return {
            "success": True,
            "settings": data,  # Flat JSON structure
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.post("/")
async def update_settings(request: Request, updates: BulkSettingsUpdate):
    """
    Update multiple settings.
    
    Args:
        updates: List of setting updates with paths and values
    
    Returns:
        Success message
    """
    try:
        logger.info(f"📝 POST /api/v1/settings/ - Updating {len(updates.updates)} settings...")
        
        yaml_manager = SimpleYAMLManager()
        data = yaml_manager.load()
        
        # Apply updates
        updated_paths = []
        for update in updates.updates:
            try:
                data = yaml_manager.update_value(data, update.path, update.value)
                updated_paths.append(update.path)
                logger.info(f"  ✓ Updated {update.path} = {update.value}")
            except Exception as e:
                logger.error(f"  ✗ Failed to update {update.path}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to update {update.path}: {str(e)}"
                )
        
        # Save YAML
        if not yaml_manager.save(data):
            raise HTTPException(status_code=500, detail="Failed to save settings")
        
        logger.info(f"✅ Settings saved: {', '.join(updated_paths)}")
        
        # Hot reload config
        try:
            current_config = request.app.state.config
            current_config.reload()
            logger.info("✅ Config reloaded (no restart needed)")
            requires_restart = False
            restart_message = "✅ Settings applied immediately!"
        except Exception as reload_error:
            logger.warning(f"⚠️ Failed to hot-reload: {reload_error}")
            requires_restart = True
            restart_message = "⚠️ Please restart the server."
        
        return {
            "success": True,
            "message": f"Updated {len(updated_paths)} settings",
            "updated_paths": updated_paths,
            "requires_restart": requires_restart,
            "restart_message": restart_message,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/reload")
async def reload_config(request: Request):
    """Reload configuration from YAML"""
    try:
        logger.info("🔄 Manual config reload requested")
        
        current_config = request.app.state.config
        current_config.reload()
        
        logger.info("✅ Configuration reloaded")
        
        return {
            "success": True,
            "message": "Configuration reloaded successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reload config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")


@router.get("/backups")
async def list_backups(request: Request):
    """List available config backups"""
    try:
        config_path = Path("config/config.yaml")
        backup_pattern = f"{config_path.name}.backup.*"
        
        backups = []
        for backup_file in sorted(
            config_path.parent.glob(backup_pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": backup_file.stat().st_size,
                "modified": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat()
            })
        
        return {
            "success": True,
            "backups": backups,
            "count": len(backups)
        }
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.post("/restore/{backup_name}")
async def restore_backup(request: Request, backup_name: str):
    """Restore config from backup"""
    try:
        config_path = Path("config/config.yaml")
        backup_path = config_path.parent / backup_name
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")
        
        if not backup_name.startswith(f"{config_path.name}.backup."):
            raise HTTPException(status_code=400, detail="Invalid backup file")
        
        import shutil
        shutil.copy2(backup_path, config_path)
        
        # Reload config
        current_config = request.app.state.config
        current_config.reload()
        
        logger.info(f"✅ Config restored from {backup_name}")
        
        return {
            "success": True,
            "message": f"Configuration restored from {backup_name}",
            "requires_restart": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to restore backup: {str(e)}")
