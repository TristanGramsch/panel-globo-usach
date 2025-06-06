#!/usr/bin/env python3
"""
USACH Environmental Data Fetcher
Downloads and manages piloto sensor data files from servidor
"""

import os
import re
import sys
import time
import requests
import logging
import json
import urllib.parse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin
import hashlib
from config.settings import PROJECT_ROOT, get_chile_time, format_chile_time, get_chile_date, DATA_SERVER_URL, DATA_FETCH_TIMEOUT_SECONDS, update_data_status
from config.logging_config import (
    get_data_fetching_logger,
    log_performance_metric,
    log_data_operation
)

# Configuración
BASE_URL = DATA_SERVER_URL
DATA_DIR = PROJECT_ROOT / 'piloto_data'
LOG_DIR = PROJECT_ROOT / 'logs'
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
USER_AGENT = "USACH-Piloto-Monitor/1.0"

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Configurar logging con timestamp en Chile
chile_time_str = get_chile_time().strftime('%Y%m%d')
log_file = os.path.join(LOG_DIR, f"piloto_fetcher_{chile_time_str}.log")

def setup_logging():
    """Setup logging for the fetcher - now using centralized logging"""
    # Just return the centralized logger
    return get_data_fetching_logger()

class PilotoFileFetcher:
    def __init__(self, base_url: str = BASE_URL, local_dir: str = DATA_DIR):
        self.base_url = base_url
        self.local_dir = Path(local_dir)
        self.local_dir.mkdir(exist_ok=True)
        
        # Use centralized logger
        self.logger = get_data_fetching_logger()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.session.timeout = DATA_FETCH_TIMEOUT_SECONDS
        
    def check_server_health(self) -> bool:
        """Check if the server is accessible"""
        try:
            response = self.session.head(self.base_url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                self.logger.info("Server is accessible")
                return True
            else:
                self.logger.warning(f"Server returned status code: {response.status_code}")
                return False
        except requests.RequestException as e:
            self.logger.error(f"Server health check failed: {e}")
            return False
    
    def get_directory_listing(self) -> Optional[str]:
        """Get the HTML listing of files from the server"""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                self.logger.info(f"Fetching directory listing (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
                response = self.session.get(self.base_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                self.logger.warning(f"Directory listing attempt {attempt + 1} failed: {e}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                    
        self.logger.error("All attempts to fetch directory listing failed")
        return None
    
    def parse_piloto_files(self, html_content: str) -> List[Dict[str, str]]:
        """Parse HTML content to extract Piloto file information"""
        piloto_files = []
        
        # Regex pattern to match Piloto file entries in HTML
        # Looking for: <a href="Piloto{ID}-{DDMMYY}.dat">Piloto{ID}-{DDMMYY}.dat</a>
        file_pattern = re.compile(
            r'href="(Piloto\d+-\d{6}\.dat)"[^>]*>.*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*</td><td[^>]*>\s*(\d+[KMG]?|\d+)\s*</td>',
            re.IGNORECASE | re.DOTALL
        )
        
        # Alternative pattern for simpler extraction
        simple_pattern = re.compile(r'href="(Piloto\d+-\d{6}\.dat)"', re.IGNORECASE)
        
        matches = file_pattern.findall(html_content)
        if not matches:
            # Fallback to simple pattern
            simple_matches = simple_pattern.findall(html_content)
            for filename in simple_matches:
                piloto_files.append({
                    'filename': filename,
                    'last_modified': 'unknown',
                    'size': 'unknown'
                })
        else:
            for filename, last_modified, size in matches:
                piloto_files.append({
                    'filename': filename,
                    'last_modified': last_modified,
                    'size': size
                })
        
        self.logger.info(f"Found {len(piloto_files)} Piloto files")
        return piloto_files
    
    def filter_current_month_files(self, files: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter files to only include current month with proper date validation"""
        current_date = get_chile_time()
        current_month_str = current_date.strftime("%m%y")
        
        current_month_files = []
        invalid_dates_skipped = 0
        
        for file_info in files:
            filename = file_info['filename']
            # Extract date from filename: Piloto{ID}-{DDMMYY}.dat
            match = re.search(r'Piloto\d+-(\d{6})\.dat', filename)
            if match:
                date_str = match.group(1)
                file_month_str = date_str[2:6]  # MMYY part
                
                # First check if it's the current month
                if file_month_str == current_month_str:
                    # Now validate the actual date
                    try:
                        day = int(date_str[:2])
                        month = int(date_str[2:4])
                        year = 2000 + int(date_str[4:6])
                        
                        # Try to create datetime - this will raise ValueError for invalid dates
                        from datetime import datetime
                        datetime(year, month, day)
                        
                        # If we get here, the date is valid
                        current_month_files.append(file_info)
                        
                    except ValueError:
                        # Invalid date (like June 31st) - skip it
                        invalid_dates_skipped += 1
                        self.logger.warning(f"Skipping file with invalid date: {filename}")
        
        self.logger.info(f"Filtered to {len(current_month_files)} files for current month ({current_month_str})")
        if invalid_dates_skipped > 0:
            self.logger.info(f"Skipped {invalid_dates_skipped} files with invalid dates")
        
        return current_month_files
    
    def get_local_file_info(self, filename: str) -> Optional[Dict[str, any]]:
        """Get information about locally stored file"""
        local_path = self.local_dir / filename
        if local_path.exists():
            stat = local_path.stat()
            return {
                'path': local_path,
                'size': stat.st_size,
                'mtime': get_chile_time().fromtimestamp(stat.st_mtime),
                'exists': True
            }
        return {'exists': False}
    
    def should_download_file(self, file_info: Dict[str, str]) -> bool:
        """Determine if a file should be downloaded or updated"""
        filename = file_info['filename']
        local_info = self.get_local_file_info(filename)
        
        if not local_info['exists']:
            self.logger.info(f"File {filename} not found locally, will download")
            return True
        
        # If we have server timestamp info, compare
        if file_info['last_modified'] != 'unknown':
            try:
                # Parse server timestamp (assuming format: YYYY-MM-DD HH:MM)
                server_time = get_chile_time().strptime(file_info['last_modified'], '%Y-%m-%d %H:%M')
                local_time = local_info['mtime']
                
                if server_time > local_time:
                    self.logger.info(f"File {filename} is newer on server, will update")
                    return True
                else:
                    self.logger.debug(f"File {filename} is up to date")
                    return False
            except ValueError:
                self.logger.warning(f"Could not parse server timestamp for {filename}")
        
        # For files updated today, always check (since they update throughout the day)
        today = get_chile_time().date()
        file_date = local_info['mtime'].date()
        if file_date == today:
            self.logger.info(f"File {filename} was modified today, checking for updates")
            return True
        
        return False
    
    def download_file(self, filename: str) -> bool:
        """Download a single file from the server"""
        url = urljoin(self.base_url, filename)
        local_path = self.local_dir / filename
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                self.logger.info(f"Downloading {filename} (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
                
                # Get file with streaming to handle large files
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
                response.raise_for_status()
                
                # Create temporary file first
                temp_path = local_path.with_suffix('.tmp')
                
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Check if file is empty
                if temp_path.stat().st_size == 0:
                    self.logger.warning(f"Downloaded file {filename} is empty")
                    # Still save empty files for completeness
                
                # Move temp file to final location
                temp_path.rename(local_path)
                
                self.logger.info(f"Successfully downloaded {filename} ({local_path.stat().st_size} bytes)")
                return True
                
            except requests.RequestException as e:
                self.logger.warning(f"Download attempt {attempt + 1} failed for {filename}: {e}")
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    self.logger.error(f"Failed to download {filename} after {RETRY_ATTEMPTS} attempts")
                    return False
            except Exception as e:
                self.logger.error(f"Unexpected error downloading {filename}: {e}")
                return False
    
    def get_sensor_summary(self, files: List[Dict[str, str]]) -> Dict[str, int]:
        """Get summary of sensors and their file counts"""
        sensor_counts = {}
        for file_info in files:
            filename = file_info['filename']
            match = re.search(r'Piloto(\d+)-', filename)
            if match:
                sensor_id = match.group(1)
                sensor_counts[sensor_id] = sensor_counts.get(sensor_id, 0) + 1
        return sensor_counts
    
    def run_fetch_cycle(self) -> Dict[str, any]:
        """Run a complete fetch cycle and return statistics"""
        start_time = get_chile_time()
        self.logger.info("Starting Piloto file fetch cycle")
        
        stats = {
            'start_time': start_time,
            'server_accessible': False,
            'files_found': 0,
            'files_downloaded': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'errors': 0,
            'sensors': {},
            'elapsed_time': 0
        }

        try:
            # Check server health
            if not self.check_server_health():
                log_data_operation(
                    self.logger, 
                    "fetch_cycle_failed", 
                    details={'reason': 'server_not_accessible'}
                )
                return stats

            stats['server_accessible'] = True

            # Get directory listing
            html_content = self.get_directory_listing()
            if not html_content:
                log_data_operation(
                    self.logger, 
                    "fetch_cycle_failed", 
                    details={'reason': 'could_not_get_directory_listing'}
                )
                return stats

            # Parse files and filter
            all_files = self.parse_piloto_files(html_content)
            self.logger.info(f"Found {len(all_files)} Piloto files")
            stats['files_found'] = len(all_files)

            current_month_files = self.filter_current_month_files(all_files)
            current_month_str = get_chile_time().strftime('%m%y')
            self.logger.info(f"Filtered to {len(current_month_files)} files for current month ({current_month_str})")

            # Process each file
            for file_info in current_month_files:
                filename = file_info['filename']
                
                try:
                    if self.should_download_file(file_info):
                        if self.download_file(filename):
                            if file_info.get('is_new', False):
                                stats['files_downloaded'] += 1
                            else:
                                stats['files_updated'] += 1
                        else:
                            stats['errors'] += 1
                    else:
                        stats['files_skipped'] += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing file {filename}: {e}")
                    stats['errors'] += 1

            # Calculate elapsed time
            end_time = get_chile_time()
            elapsed_time = (end_time - start_time).total_seconds()
            stats['elapsed_time'] = elapsed_time

            # Get sensor summary
            stats['sensors'] = self.get_sensor_summary(current_month_files)

            # Log completion
            self.logger.info(f"Fetch cycle completed in {elapsed_time:.2f}s")
            log_data_operation(
                self.logger,
                "fetch_cycle_completed",
                file_count=stats['files_found'],
                success_count=stats['files_downloaded'] + stats['files_updated'],
                error_count=stats['errors'],
                details={
                    'duration_seconds': elapsed_time,
                    'files_downloaded': stats['files_downloaded'],
                    'files_updated': stats['files_updated'],
                    'files_skipped': stats['files_skipped'],
                    'sensors_detected': len(stats['sensors'])
                }
            )

        except Exception as e:
            self.logger.error(f"Unexpected error in fetch cycle: {e}", exc_info=True)
            stats['errors'] += 1

        return stats

def fetch_and_update_data():
    """
    Main function to fetch data and update status
    Enhanced with detailed logging
    """
    logger = get_data_fetching_logger()
    start_time = get_chile_time()
    
    logger.info(f"Iniciando descarga de datos a las {format_chile_time(start_time)}")
    
    # Initialize tracking variables
    files_fetched = 0
    files_updated = 0
    success = False
    error_msg = ""
    
    try:
        # Setup logging for the session
        setup_logging()
        
        # Create fetcher and run cycle
        fetcher = PilotoFileFetcher()
        
        if fetcher.check_server_health():
            # Run the fetch cycle
            stats = fetcher.run_fetch_cycle()
            
            # Extract results
            files_fetched = stats.get('files_found', 0)
            files_updated = stats.get('files_updated', 0) + stats.get('files_downloaded', 0)
            success = stats.get('errors', 1) == 0  # Success if no errors
            
            if success:
                logger.info(f"Descarga exitosa: {files_fetched} archivos encontrados, {files_updated} actualizados")
            else:
                error_msg = f"Descarga completada con {stats.get('errors', 0)} errores"
                logger.warning(error_msg)
        else:
            error_msg = "No se pudo acceder al servidor"
            logger.error(error_msg)
            
    except Exception as e:
        error_msg = f"Error durante la descarga: {str(e)}"
        logger.error(error_msg, exc_info=True)
    
    # Calculate duration
    end_time = get_chile_time()
    duration = (end_time - start_time).total_seconds()
    
    # Log performance metric
    log_performance_metric(
        logger,
        "Data fetch operation",
        duration,
        {
            'files_fetched': files_fetched,
            'files_updated': files_updated,
            'success': success,
            'error_msg': error_msg if error_msg else None
        }
    )
    
    # Update status
    update_data_status(
        status='success' if success else 'error',
        fetch_time=start_time,
        success=success,
        files_fetched=files_fetched,
        files_updated=files_updated,
        error_msg=error_msg,
        duration=duration
    )
    
    logger.info(f"Proceso completado en {duration:.1f} segundos")
    return success

def main():
    """Main execution function"""
    fetcher = PilotoFileFetcher()
    
    try:
        # Run single fetch cycle
        stats = fetcher.run_fetch_cycle()
        
        # Print summary
        print("\n" + "="*50)
        print("PILOTO FILE FETCH SUMMARY")
        print("="*50)
        print(f"Server accessible: {stats['server_accessible']}")
        print(f"Files found: {stats['files_found']}")
        print(f"Files downloaded: {stats['files_downloaded']}")
        print(f"Files updated: {stats['files_updated']}")
        print(f"Files skipped: {stats['files_skipped']}")
        print(f"Errors: {stats['errors']}")
        print(f"Sensors detected: {list(stats['sensors'].keys())}")
        print(f"Elapsed time: {stats.get('elapsed_time', 0):.2f}s")
        print("="*50)
        
        if stats['errors'] > 0:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nFetch interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 