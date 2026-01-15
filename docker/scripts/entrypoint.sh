#!/bin/bash
# ============================================
# Entrypoint script for Trishul Backend
# ============================================

set -e

echo "============================================"
echo "🚀 Trishul Backend Entrypoint"
echo "============================================"

# ============================================
# Environment Variables with Defaults
# ============================================
export DB_HOST="${DB_HOST:-mysql}"
export DB_PORT="${DB_PORT:-3306}"
export DB_USER="${DB_USER:-root}"
export DB_PASSWORD="${DB_PASSWORD:-trishul123}"

export DATA_DIR="${DATA_DIR:-/app/data}"
export COMPILED_DIR="${COMPILED_DIR:-/app/data/compiled_mibs}"
export CACHE_DIR="${CACHE_DIR:-/app/data/cache}"
export EXPORT_DIR="${EXPORT_DIR:-/app/data/exports}"
export UPLOAD_DIR="${UPLOAD_DIR:-/app/data/uploads}"
export LOG_FILE="${LOG_FILE:-/app/data/logs/trishul.log}"

export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-8000}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# ============================================
# Create Required Directories
# ============================================
echo "📁 Creating required directories..."
mkdir -p "$DATA_DIR"/{uploads,compiled_mibs,cache,exports,logs,config}

# ============================================
# Config Management (Hybrid ConfigMap + PVC)
# ============================================
CONFIG_PVC_PATH="$DATA_DIR/config/config.yaml"
CONFIG_DEFAULT_PATH="/app/config/config.yaml"
CONFIG_RUNTIME_PATH="/app/config/config.yaml"

if [ -f "$CONFIG_PVC_PATH" ]; then
    echo "✅ Using existing config from PVC: $CONFIG_PVC_PATH"
    # PVC config exists, it takes precedence (user may have modified via UI)
    # Don't overwrite, just use it
else
    echo "📝 Initializing config from ConfigMap to PVC"
    
    # ConfigMap is mounted read-only at /app/config/config.yaml
    # Copy it to PVC for persistence and future UI modifications
    if [ -f "$CONFIG_DEFAULT_PATH" ]; then
        cp "$CONFIG_DEFAULT_PATH" "$CONFIG_PVC_PATH"
        echo "✅ Config initialized and saved to PVC"
    else
        echo "⚠️  Warning: Default config not found at $CONFIG_DEFAULT_PATH"
    fi
fi

# ============================================
# Wait for MySQL
# ============================================
echo "⏳ Waiting for MySQL at $DB_HOST:$DB_PORT..."
max_retries=30
retry_count=0

while ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; do
    retry_count=$((retry_count + 1))
    if [ $retry_count -ge $max_retries ]; then
        echo "❌ MySQL not available after $max_retries attempts"
        exit 1
    fi
    echo "   Attempt $retry_count/$max_retries..."
    sleep 2
done

echo "✅ MySQL is ready!"

# ============================================
# Database Initialization
# ============================================
echo "🗄️  Database initialization will be handled by application startup"

# ============================================
# Start Application
# ============================================
echo "============================================"
echo "✅ Starting Trishul Backend..."
echo "============================================"
echo ""

# Execute the command passed to docker run
exec "$@"
