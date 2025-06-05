#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Data Processing Module
Functions for processing and analyzing air quality data
"""

import os
import glob
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import DATA_DIR, MIN_FILE_SIZE_BYTES, get_chile_time, format_chile_time
from utils.helpers import (
    extract_sensor_id_from_filename, 
    extract_date_from_filename,
    safe_file_size_check,
    sanitize_sensor_id
)
from config.logging_config import (
    get_data_processing_logger,
    log_performance_metric,
    log_data_operation
)

# Initialize the data processing logger
logger = get_data_processing_logger()

def get_available_sensors():
    """
    Get list of available sensor IDs from data files
    
    Returns:
        list: List of sensor IDs
    """
    try:
        start_time = get_chile_time()
        data_dir = Path('piloto_data')
        if not data_dir.exists():
            logger.warning("Data directory does not exist")
            return []
        
        sensors = set()
        for file_path in data_dir.glob('Piloto*.dat'):
            # Extract sensor ID from filename (e.g., Piloto013-020625.dat -> 013)
            filename = file_path.name
            if filename.startswith('Piloto') and '-' in filename:
                sensor_id = filename.split('-')[0].replace('Piloto', '')
                sensors.add(sensor_id)
        
        sensor_list = sorted(list(sensors))
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_performance_metric(
            logger,
            "Get available sensors",
            duration,
            {'sensor_count': len(sensor_list)}
        )
        
        return sensor_list
        
    except Exception as e:
        logger.error(f"Error getting available sensors: {e}", exc_info=True)
        return []

def get_sensor_date_range(sensor_id):
    """Get the date range of available data for a sensor"""
    try:
        start_time = get_chile_time()
        data_dir = Path('piloto_data')
        
        dates = []
        pattern = f'Piloto{sensor_id}-*.dat'
        
        for file_path in data_dir.glob(pattern):
            filename = file_path.name
            # Extract date from filename (e.g., Piloto013-020625.dat -> 020625)
            if '-' in filename and filename.endswith('.dat'):
                date_part = filename.split('-')[1].replace('.dat', '')
                if len(date_part) == 6:  # Format: DDMMYY
                    try:
                        # Parse date: DDMMYY -> datetime
                        day = int(date_part[:2])
                        month = int(date_part[2:4])
                        year = 2000 + int(date_part[4:6])
                        dates.append(datetime(year, month, day))
                    except ValueError:
                        logger.warning(f"Invalid date format in filename: {filename}")
                        continue
        
        if not dates:
            logger.info(f"No data files found for sensor {sensor_id}")
            return None, None
            
        min_date = min(dates)
        max_date = max(dates)
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_performance_metric(
            logger,
            f"Get date range for sensor {sensor_id}",
            duration,
            {
                'sensor_id': sensor_id,
                'date_range_days': (max_date - min_date).days,
                'files_found': len(dates)
            }
        )
        
        return min_date, max_date
        
    except Exception as e:
        logger.error(f"Error getting date range: {e}", exc_info=True)
        return None, None

def parse_piloto_file(file_path):
    """
    Parse a single piloto data file
    
    Args:
        file_path (str): Path to the data file
        
    Returns:
        pd.DataFrame or None: Parsed data or None if failed
    """
    try:
        start_time = get_chile_time()
        
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return pd.DataFrame()
        
        file_size = file_path.stat().st_size
        logger.debug(f"Parsing file {file_path.name} ({file_size} bytes)")
        
        # Read and process the file
        data = []
        line_count = 0
        error_count = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                try:
                    parts = line.split(',')
                    if len(parts) >= 8:  # Minimum required columns
                        # Parse timestamp (assuming format: DD/MM/YY HH:MM:SS)
                        timestamp_str = parts[0].strip()
                        timestamp = parse_timestamp(timestamp_str)
                        
                        if timestamp:
                            row = {
                                'Timestamp': timestamp,
                                'MP1': safe_float(parts[1]),
                                'MP25': safe_float(parts[2]),
                                'MP10': safe_float(parts[3]),
                                'Temperature': safe_float(parts[4]),
                                'Humidity': safe_float(parts[5]),
                                'Pressure': safe_float(parts[6]),
                                'Sensor_ID': parts[7].strip() if len(parts) > 7 else 'Unknown'
                            }
                            data.append(row)
                        else:
                            error_count += 1
                            if error_count <= 5:  # Log only first 5 errors
                                logger.warning(f"Invalid timestamp in {file_path.name}, line {line_num}: {timestamp_str}")
                    else:
                        error_count += 1
                        if error_count <= 5:
                            logger.warning(f"Insufficient columns in {file_path.name}, line {line_num}: {len(parts)} columns")
                            
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        logger.warning(f"Error parsing line {line_num} in {file_path.name}: {e}")
        
        df = pd.DataFrame(data)
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_data_operation(
            logger,
            "file_parsing",
            file_count=1,
            success_count=1 if len(df) > 0 else 0,
            error_count=1 if error_count > 0 else 0,
            details={
                'filename': file_path.name,
                'file_size_bytes': file_size,
                'lines_processed': line_count,
                'data_rows_extracted': len(df),
                'parsing_errors': error_count,
                'duration_seconds': duration
            }
        )
        
        return df
        
    except Exception as e:
        logger.error(f"Error parsing file {file_path}: {e}", exc_info=True)
        return pd.DataFrame()

def get_sensor_data(sensor_id, start_date=None, end_date=None):
    """
    Get data for a specific sensor within date range
    
    Args:
        sensor_id (str): Sensor ID
        start_date (datetime, optional): Start date
        end_date (datetime, optional): End date
        
    Returns:
        pd.DataFrame: Sensor data
    """
    try:
        start_time = get_chile_time()
        data_dir = Path('piloto_data')
        
        if not data_dir.exists():
            logger.warning("Data directory does not exist")
            return pd.DataFrame()
        
        # Find all files for this sensor
        pattern = f'Piloto{sensor_id}-*.dat'
        files = list(data_dir.glob(pattern))
        
        if not files:
            logger.info(f"No data files found for sensor {sensor_id}")
            return pd.DataFrame()
        
        logger.info(f"Processing {len(files)} files for sensor {sensor_id}")
        
        # Parse all files and combine
        all_data = []
        files_processed = 0
        files_with_errors = 0
        
        for file_path in files:
            df = parse_piloto_file(file_path)
            if not df.empty:
                all_data.append(df)
                files_processed += 1
            else:
                files_with_errors += 1
        
        if not all_data:
            logger.warning(f"No valid data found for sensor {sensor_id}")
            return pd.DataFrame()
        
        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Apply date filtering if specified
        if start_date or end_date:
            original_count = len(combined_df)
            if start_date:
                combined_df = combined_df[combined_df['Timestamp'] >= start_date]
            if end_date:
                combined_df = combined_df[combined_df['Timestamp'] <= end_date]
            filtered_count = len(combined_df)
            logger.info(f"Date filtering: {original_count} -> {filtered_count} rows")
        
        # Sort by timestamp
        combined_df = combined_df.sort_values('Timestamp').reset_index(drop=True)
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_data_operation(
            logger,
            "sensor_data_retrieval",
            file_count=len(files),
            success_count=files_processed,
            error_count=files_with_errors,
            details={
                'sensor_id': sensor_id,
                'total_rows': len(combined_df),
                'date_range': f"{start_date} to {end_date}" if start_date or end_date else "all",
                'duration_seconds': duration
            }
        )
        
        return combined_df
        
    except Exception as e:
        logger.error(f"Error getting sensor data for {sensor_id}: {e}", exc_info=True)
        return pd.DataFrame()

def get_current_data():
    """
    Get current air quality data for dashboard
    
    Returns:
        pd.DataFrame: Current data for all sensors
    """
    try:
        start_time = get_chile_time()
        data_dir = Path('piloto_data')
        
        if not data_dir.exists():
            logger.warning("Data directory does not exist")
            return pd.DataFrame()
        
        # Get all .dat files
        files = list(data_dir.glob('Piloto*.dat'))
        
        if not files:
            logger.warning("No data files found")
            return pd.DataFrame()
        
        # Get files from today and yesterday to ensure we have recent data
        today = get_chile_time().date()
        yesterday = today - timedelta(days=1)
        
        recent_files = []
        for file_path in files:
            # Check file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=CHILE_TZ).date()
            if mtime >= yesterday:
                recent_files.append(file_path)
        
        if not recent_files:
            logger.warning("No recent data files found")
            # Fall back to all files if no recent ones
            recent_files = files
        
        logger.info(f"Processing {len(recent_files)} recent files for current data")
        
        # Parse recent files
        all_data = []
        files_processed = 0
        files_with_errors = 0
        
        for file_path in recent_files:
            df = parse_piloto_file(file_path)
            if not df.empty:
                all_data.append(df)
                files_processed += 1
            else:
                files_with_errors += 1
        
        if not all_data:
            logger.error("No valid current data found")
            return pd.DataFrame()
        
        # Combine and get most recent data per sensor
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Get the most recent reading for each sensor
        current_data = combined_df.loc[combined_df.groupby('Sensor_ID')['Timestamp'].idxmax()]
        current_data = current_data.sort_values('Sensor_ID').reset_index(drop=True)
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_data_operation(
            logger,
            "current_data_retrieval",
            file_count=len(recent_files),
            success_count=files_processed,
            error_count=files_with_errors,
            details={
                'sensors_found': len(current_data),
                'total_data_points': len(combined_df),
                'duration_seconds': duration
            }
        )
        
        return current_data
        
    except Exception as e:
        logger.error(f"Error getting current data: {e}", exc_info=True)
        return pd.DataFrame() 