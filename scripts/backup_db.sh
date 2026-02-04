#!/bin/bash
#===============================================================================
# SQLite Database Backup Script
#===============================================================================
# This script creates safe backups of the trades.db SQLite database
# Run via cron every hour: 0 * * * * /path/to/backup_db.sh
#
# Features:
#   - Uses SQLite's .backup command for transaction-safe backups
#   - Compresses backups with gzip
#   - Keeps last 24 hourly + 7 daily backups (auto-cleanup)
#   - Optional upload to Oracle Cloud Object Storage
#===============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_FILE="${PROJECT_DIR}/trades.db"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE_ONLY=$(date +"%Y%m%d")
HOUR=$(date +"%H")

# OCI Object Storage Config (optional - set these if using OCI)
OCI_BUCKET_NAME=""  # e.g., "screener-backups"
OCI_NAMESPACE=""    # Your OCI namespace

# Retention settings
HOURLY_RETENTION=24  # Keep last 24 hourly backups
DAILY_RETENTION=7    # Keep last 7 daily backups

#===============================================================================
# Functions
#===============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

create_backup() {
    BACKUP_FILE="${BACKUP_DIR}/trades_${TIMESTAMP}.db"
    COMPRESSED_FILE="${BACKUP_FILE}.gz"

    # Ensure backup directory exists
    mkdir -p "$BACKUP_DIR"

    # Create safe backup using SQLite's .backup command
    log "Creating backup of ${DB_FILE}..."
    sqlite3 "$DB_FILE" ".backup '${BACKUP_FILE}'"

    # Compress the backup
    log "Compressing backup..."
    gzip "$BACKUP_FILE"

    # Get file size
    local size=$(du -h "$COMPRESSED_FILE" | cut -f1)
    log "Backup created: ${COMPRESSED_FILE} (${size})"
}

cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    # Keep only last N hourly backups
    local count=$(ls -1 ${BACKUP_DIR}/trades_*.db.gz 2>/dev/null | wc -l)
    if [ "$count" -gt "$HOURLY_RETENTION" ]; then
        local to_delete=$((count - HOURLY_RETENTION))
        log "Removing ${to_delete} old hourly backup(s)..."
        ls -1t ${BACKUP_DIR}/trades_*.db.gz | tail -n "$to_delete" | xargs rm -f
    fi
}

upload_to_oci() {
    local backup_file=$1

    if [ -z "$OCI_BUCKET_NAME" ] || [ -z "$OCI_NAMESPACE" ]; then
        log "OCI config not set, skipping cloud upload"
        return 0
    fi

    if ! command -v oci &> /dev/null; then
        log "OCI CLI not installed, skipping cloud upload"
        return 0
    fi

    log "Uploading to Oracle Cloud Object Storage..."
    local filename=$(basename "$backup_file")
    
    oci os object put \
        --bucket-name "$OCI_BUCKET_NAME" \
        --namespace "$OCI_NAMESPACE" \
        --file "$backup_file" \
        --name "backups/${filename}" \
        --force

    log "Upload complete: ${filename}"
}

verify_backup() {
    local backup_file=$1
    local temp_db="/tmp/verify_backup_$$.db"

    log "Verifying backup integrity..."
    
    # Decompress to temp location
    gunzip -c "$backup_file" > "$temp_db"
    
    # Run integrity check
    local result=$(sqlite3 "$temp_db" "PRAGMA integrity_check;")
    rm -f "$temp_db"

    if [ "$result" = "ok" ]; then
        log "Backup integrity: OK ✓"
        return 0
    else
        log "WARNING: Backup integrity check failed!"
        return 1
    fi
}

#===============================================================================
# Main
#===============================================================================

main() {
    log "========================================="
    log "Starting database backup..."
    log "========================================="

    # Check if database exists
    if [ ! -f "$DB_FILE" ]; then
        log "ERROR: Database file not found: ${DB_FILE}"
        exit 1
    fi

    # Check if sqlite3 is available
    if ! command -v sqlite3 &> /dev/null; then
        log "ERROR: sqlite3 is not installed"
        exit 1
    fi

    # Create the backup (sets COMPRESSED_FILE global variable)
    create_backup

    # Verify backup integrity
    verify_backup "$COMPRESSED_FILE"

    # Upload to cloud (if configured)
    upload_to_oci "$COMPRESSED_FILE"

    # Cleanup old backups
    cleanup_old_backups

    log "========================================="
    log "Backup completed successfully!"
    log "========================================="
}

main "$@"
