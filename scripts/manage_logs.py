#!/usr/bin/env python3
"""
Log Management Script for USACH Environmental Monitoring Dashboard

This script provides utilities to manage, clean, and archive log files
according to the established logging strategy.

Usage:
    python scripts/manage_logs.py [command] [options]

Commands:
    cleanup   - Remove old log files and archive them
    status    - Show current log status and disk usage
    archive   - Archive logs older than specified days
    purge     - Remove archived logs older than specified days
"""

import os
import sys
import argparse
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json
import pytz

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_chile_time, format_chile_time
from config.logging_config import get_system_logger

def get_file_size_mb(file_path):
    """Get file size in MB"""
    try:
        return file_path.stat().st_size / (1024 * 1024)
    except:
        return 0

def get_directory_size_mb(dir_path):
    """Get total directory size in MB"""
    total_size = 0
    try:
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except:
        pass
    return total_size / (1024 * 1024)

def get_aware_datetime(timestamp):
    """Convert timestamp to timezone-aware datetime in Chile timezone"""
    chile_tz = pytz.timezone('America/Santiago')
    naive_dt = datetime.fromtimestamp(timestamp)
    return chile_tz.localize(naive_dt)

def compress_file(source_path, dest_path):
    """Compress a file using gzip"""
    try:
        with open(source_path, 'rb') as f_in:
            with gzip.open(dest_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception as e:
        print(f"Error compressing {source_path}: {e}")
        return False

def show_log_status():
    """Show current log status and disk usage"""
    logger = get_system_logger()
    logger.info("Generating log status report")
    
    logs_dir = Path('logs')
    if not logs_dir.exists():
        print("❌ Logs directory does not exist")
        return
    
    print("="*60)
    print("USACH DASHBOARD - LOG STATUS REPORT")
    print("="*60)
    print(f"Report generated: {format_chile_time(get_chile_time())}")
    print()
    
    # Overall statistics
    total_size = get_directory_size_mb(logs_dir)
    print(f"📊 OVERALL STATISTICS")
    print(f"   Total log space used: {total_size:.2f} MB")
    print()
    
    # Component breakdown
    components = ['dashboard', 'data_fetching', 'data_processing', 'system']
    
    for component in components:
        component_dir = logs_dir / component
        if component_dir.exists():
            size = get_directory_size_mb(component_dir)
            file_count = len(list(component_dir.glob('*')))
            
            print(f"📁 {component.upper().replace('_', ' ')}")
            print(f"   Size: {size:.2f} MB")
            print(f"   Files: {file_count}")
            
            # Show recent files
            recent_files = sorted(component_dir.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True)[:3]
            if recent_files:
                print(f"   Recent files:")
                for file_path in recent_files:
                    file_size = get_file_size_mb(file_path)
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    print(f"     • {file_path.name} ({file_size:.1f} MB) - {mtime.strftime('%Y-%m-%d %H:%M')}")
            print()
    
    # Archive status
    archive_dir = logs_dir / 'archive'
    if archive_dir.exists():
        archive_size = get_directory_size_mb(archive_dir)
        archive_files = len(list(archive_dir.rglob('*')))
        print(f"📦 ARCHIVE")
        print(f"   Size: {archive_size:.2f} MB")
        print(f"   Files: {archive_files}")
        print()
    
    # Old files that could be cleaned
    cutoff_date = get_chile_time() - timedelta(days=7)
    old_files = []
    
    for component in components:
        component_dir = logs_dir / component
        if component_dir.exists():
            for file_path in component_dir.glob('*.log'):
                mtime = get_aware_datetime(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    old_files.append(file_path)
    
    if old_files:
        old_size = sum(get_file_size_mb(f) for f in old_files)
        print(f"⚠️  FILES READY FOR CLEANUP")
        print(f"   Files older than 7 days: {len(old_files)}")
        print(f"   Potential space to save: {old_size:.2f} MB")
        print("   Run 'python scripts/manage_logs.py cleanup' to clean these files")
    else:
        print("✅ No old files found - logs are current")
    
    print("="*60)

def cleanup_logs(days_to_keep=7, archive_days=30, dry_run=False):
    """Clean up old log files"""
    logger = get_system_logger()
    
    action = "would be" if dry_run else "will be"
    print(f"🧹 LOG CLEANUP {'(DRY RUN)' if dry_run else ''}")
    print(f"   Files older than {days_to_keep} days {action} compressed and archived")
    print(f"   Archives older than {archive_days} days {action} deleted")
    print()
    
    logs_dir = Path('logs')
    archive_dir = logs_dir / 'archive'
    current_date = get_chile_time()
    
    # Create archive directory structure
    if not dry_run:
        archive_year_dir = archive_dir / str(current_date.year) / f"{current_date.month:02d}"
        archive_year_dir.mkdir(parents=True, exist_ok=True)
    
    cutoff_date = current_date - timedelta(days=days_to_keep)
    archive_cutoff = current_date - timedelta(days=archive_days)
    
    components = ['dashboard', 'data_fetching', 'data_processing', 'system']
    total_processed = 0
    total_size_saved = 0
    
    # Process each component
    for component in components:
        component_dir = logs_dir / component
        if not component_dir.exists():
            continue
            
        print(f"📁 Processing {component} logs...")
        
        # Find old log files
        old_files = []
        for file_path in component_dir.glob('*.log'):
            mtime = get_aware_datetime(file_path.stat().st_mtime)
            if mtime < cutoff_date:
                old_files.append(file_path)
        
        # Archive old files
        for file_path in old_files:
            file_size = get_file_size_mb(file_path)
            
            if dry_run:
                print(f"   Would archive: {file_path.name} ({file_size:.1f} MB)")
            else:
                # Compress and move to archive
                archive_path = archive_year_dir / f"{file_path.name}.gz"
                if compress_file(file_path, archive_path):
                    file_path.unlink()  # Remove original
                    print(f"   ✅ Archived: {file_path.name} ({file_size:.1f} MB)")
                    logger.info(f"Log file archived: {file_path.name} -> {archive_path}")
                else:
                    print(f"   ❌ Failed to archive: {file_path.name}")
                    logger.error(f"Failed to archive log file: {file_path.name}")
            
            total_processed += 1
            total_size_saved += file_size
    
    # Clean old archives
    if archive_dir.exists():
        print(f"📦 Processing archives...")
        old_archives = []
        
        for archive_file in archive_dir.rglob('*.gz'):
            mtime = get_aware_datetime(archive_file.stat().st_mtime)
            if mtime < archive_cutoff:
                old_archives.append(archive_file)
        
        for archive_file in old_archives:
            file_size = get_file_size_mb(archive_file)
            
            if dry_run:
                print(f"   Would delete: {archive_file.name} ({file_size:.1f} MB)")
            else:
                archive_file.unlink()
                print(f"   🗑️  Deleted: {archive_file.name} ({file_size:.1f} MB)")
                logger.info(f"Old archive deleted: {archive_file.name}")
            
            total_size_saved += file_size
    
    print()
    print(f"📊 CLEANUP SUMMARY")
    print(f"   Files processed: {total_processed}")
    print(f"   Space {'that would be' if dry_run else ''} saved: {total_size_saved:.2f} MB")
    
    if not dry_run:
        logger.info(f"Log cleanup completed: {total_processed} files, {total_size_saved:.2f} MB saved")

def archive_logs(days=7):
    """Archive logs older than specified days"""
    logger = get_system_logger()
    cleanup_logs(days_to_keep=days, archive_days=365, dry_run=False)

def purge_old_archives(days=90):
    """Purge archived logs older than specified days"""
    logger = get_system_logger()
    logger.info(f"Purging archives older than {days} days")
    
    archive_dir = Path('logs/archive')
    if not archive_dir.exists():
        print("No archive directory found")
        return
    
    cutoff_date = get_chile_time() - timedelta(days=days)
    purged_count = 0
    purged_size = 0
    
    for archive_file in archive_dir.rglob('*.gz'):
        mtime = get_aware_datetime(archive_file.stat().st_mtime)
        if mtime < cutoff_date:
            file_size = get_file_size_mb(archive_file)
            archive_file.unlink()
            purged_count += 1
            purged_size += file_size
            print(f"Purged: {archive_file.name} ({file_size:.1f} MB)")
    
    print(f"Purged {purged_count} files, {purged_size:.2f} MB")
    logger.info(f"Archive purge completed: {purged_count} files, {purged_size:.2f} MB")

def main():
    parser = argparse.ArgumentParser(description='USACH Dashboard Log Management')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show log status')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old logs')
    cleanup_parser.add_argument('--days', type=int, default=7, help='Days to keep (default: 7)')
    cleanup_parser.add_argument('--archive-days', type=int, default=30, help='Days to keep archives (default: 30)')
    cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    
    # Archive command
    archive_parser = subparsers.add_parser('archive', help='Archive old logs')
    archive_parser.add_argument('--days', type=int, default=7, help='Days to keep unarchived (default: 7)')
    
    # Purge command
    purge_parser = subparsers.add_parser('purge', help='Purge old archives')
    purge_parser.add_argument('--days', type=int, default=90, help='Days to keep archives (default: 90)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Ensure we're in the right directory
    if not Path('logs').exists():
        print("❌ Error: Must be run from the dashboard root directory")
        print("   Current directory should contain 'logs' folder")
        return
    
    if args.command == 'status':
        show_log_status()
    elif args.command == 'cleanup':
        cleanup_logs(args.days, args.archive_days, args.dry_run)
    elif args.command == 'archive':
        archive_logs(args.days)
    elif args.command == 'purge':
        purge_old_archives(args.days)

if __name__ == '__main__':
    main() 