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
from config.settings import DATA_DIR, MIN_FILE_SIZE_BYTES, get_chile_time, format_chile_time, CHILE_TIMEZONE
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

def safe_float(value):
    """
    Safely convert a value to float, returning 0.0 if conversion fails
    
    Args:
        value (str or numeric): Value to convert
        
    Returns:
        float: Converted value or 0.0 if conversion fails
    """
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in ['nan', 'null', 'none', '']:
                return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def parse_timestamp(date_str, time_str):
    """
    Parse date and time strings from sensor data files
    
    Args:
        date_str (str): Date string in format DD-MM-YY
        time_str (str): Time string in format HH:MM:SS
        
    Returns:
        datetime or None: Parsed datetime object or None if parsing fails
    """
    try:
        # Handle the date format DD-MM-YY
        date_parts = date_str.strip().split('-')
        if len(date_parts) != 3:
            return None
            
        day = int(date_parts[0])
        month = int(date_parts[1])
        year_2digit = int(date_parts[2])
        
        # Convert 2-digit year to 4-digit year
        # Assuming years 00-30 are 2000-2030, and 31-99 are 1931-1999
        if year_2digit <= 30:
            year = 2000 + year_2digit
        else:
            year = 1900 + year_2digit
            
        # Handle the time format HH:MM:SS
        time_parts = time_str.strip().split(':')
        if len(time_parts) != 3:
            return None
            
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2])
        
        # Create datetime object
        dt = datetime(year, month, day, hour, minute, second)
        return dt
        
    except (ValueError, IndexError) as e:
        logger.debug(f"Error parsing timestamp '{date_str}' '{time_str}': {e}")
        return None

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

def parse_piloto_file_header(file_path):
    """
    Parse file header to create dynamic column mapping
    
    Args:
        file_path (Path): Path to the data file
        
    Returns:
        dict: Column name to index mapping, or None if failed
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Read first few lines to find header
            header_line = None
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line.startswith('Ds,'):
                    header_line = line
                    break
                if line_num > 10:  # Don't search too far
                    break
            
            if not header_line:
                logger.warning(f"No header line found in {file_path.name}")
                return None
            
            # Parse header columns
            columns = [col.strip() for col in header_line.split(',')]
            column_map = {}
            
            # Create mapping for important columns
            for i, col in enumerate(columns):
                col_lower = col.lower()
                if 'fecha' in col_lower:
                    column_map['date'] = i
                elif 'hora' in col_lower:
                    column_map['time'] = i
                elif 'tem_bme280' in col_lower or 'temp' in col_lower:
                    column_map['temperature'] = i
                elif 'hum_bme280' in col_lower or 'hum' in col_lower:
                    column_map['humidity'] = i
                elif 'pres_bme280' in col_lower or 'pres' in col_lower:
                    column_map['pressure'] = i
                elif 'mp1.0' in col_lower:
                    column_map['mp1'] = i
                elif 'mp2.5' in col_lower:
                    column_map['mp25'] = i
                elif 'mp10' in col_lower and 'n10' not in col_lower:
                    column_map['mp10'] = i
                elif 'rad_solar' in col_lower:
                    column_map['solar_radiation'] = i
            
            logger.debug(f"Parsed header for {file_path.name}: {len(columns)} columns, mapped: {list(column_map.keys())}")
            return column_map
            
    except Exception as e:
        logger.warning(f"Error parsing header for {file_path.name}: {e}")
        return None

def validate_sensor_data(value, data_type):
    """
    Validate sensor data within reasonable bounds
    
    Args:
        value (float): The sensor value
        data_type (str): Type of data (temperature, humidity, etc.)
        
    Returns:
        tuple: (is_valid, validated_value)
    """
    if value is None:
        return False, 0.0
    
    # Define reasonable bounds for different sensor types
    bounds = {
        'temperature': (-50.0, 60.0),  # °C
        'humidity': (0.0, 100.0),      # %
        'pressure': (800.0, 1200.0),   # mb
        'mp1': (0.0, 1000.0),          # µg/m³
        'mp25': (0.0, 1000.0),         # µg/m³
        'mp10': (0.0, 1000.0),         # µg/m³
        'solar_radiation': (0.0, 2000.0)  # W/m²
    }
    
    if data_type not in bounds:
        return True, value  # Unknown type, accept as-is
    
    min_val, max_val = bounds[data_type]
    if min_val <= value <= max_val:
        return True, value
    else:
        # Value out of bounds, but don't reject entirely
        # Clamp to bounds and mark as suspect
        clamped_value = max(min_val, min(max_val, value))
        return False, clamped_value

def extract_data_by_header(parts, column_map, file_name):
    """
    Extract data using dynamic column positions
    
    Args:
        parts (list): Split line parts
        column_map (dict): Column mapping from header parsing
        file_name (str): File name for logging
        
    Returns:
        dict: Extracted data row or None if failed
    """
    try:
        # Extract timestamp first
        date_idx = column_map.get('date', 1)
        time_idx = column_map.get('time', 2)
        
        if date_idx >= len(parts) or time_idx >= len(parts):
            return None
            
        date_str = parts[date_idx]
        time_str = parts[time_idx]
        timestamp = parse_timestamp(date_str, time_str)
        
        if not timestamp:
            return None
        
        # Extract sensor data with validation
        row = {'Timestamp': timestamp}
        validation_warnings = []
        
        # Extract and validate each data type
        data_mappings = [
            ('temperature', 'Temperature'),
            ('humidity', 'Humidity'), 
            ('pressure', 'Pressure'),
            ('mp1', 'MP1'),
            ('mp25', 'MP25'),
            ('mp10', 'MP10'),
            ('solar_radiation', 'Solar_Radiation')
        ]
        
        for col_key, row_key in data_mappings:
            if col_key in column_map:
                idx = column_map[col_key]
                if idx < len(parts):
                    raw_value = safe_float(parts[idx])
                    is_valid, validated_value = validate_sensor_data(raw_value, col_key)
                    row[row_key] = validated_value
                    
                    if not is_valid and raw_value is not None:
                        validation_warnings.append(f"{row_key}: {raw_value} -> {validated_value}")
                else:
                    row[row_key] = 0.0
            else:
                row[row_key] = 0.0
        
        # Add sensor ID
        row['Sensor_ID'] = extract_sensor_id_from_filename(file_name)
        
        # Log validation warnings (limited)
        if validation_warnings and len(validation_warnings) <= 3:
            logger.debug(f"Data validation warnings in {file_name}: {', '.join(validation_warnings)}")
        
        return row
        
    except Exception as e:
        logger.debug(f"Error extracting data from line in {file_name}: {e}")
        return None

def parse_piloto_file(file_path):
    """
    Parse a single piloto data file with dynamic header parsing
    
    Args:
        file_path (str): Path to the data file
        
    Returns:
        pd.DataFrame: Parsed data or empty DataFrame if failed
    """
    try:
        start_time = get_chile_time()
        
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return pd.DataFrame()
        
        file_size = file_path.stat().st_size
        logger.debug(f"Parsing file {file_path.name} ({file_size} bytes)")
        
        # Parse header to get column mapping
        column_map = parse_piloto_file_header(file_path)
        if not column_map:
            logger.warning(f"Could not parse header for {file_path.name}, using fallback parsing")
            # Fallback to original logic for files without proper headers
            column_map = {
                'date': 1, 'time': 2, 'temperature': 3, 'humidity': 4, 
                'pressure': 5, 'mp1': 7, 'mp25': 8, 'mp10': 9
            }
        
        # Read and process the file
        data = []
        line_count = 0
        error_count = 0
        validation_warnings = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line_count += 1
                line = line.strip()
                
                # Skip empty lines and header lines
                if not line or line.startswith('#') or line.startswith('Ds,') or line.startswith('DS,'):
                    continue
                
                # Skip lines that start with day names (these are data lines we want)
                # but first check if they have the right format
                if not line.startswith(('Lu,', 'Ma,', 'Mi,', 'Ju,', 'Vi,', 'Sa,', 'Do,')):
                    continue
                
                try:
                    # Split the line by comma and clean up whitespace
                    parts = [part.strip() for part in line.split(',')]
                    
                    if len(parts) < max(column_map.values()) + 1:  # Ensure we have enough columns
                        continue
                    
                    # Extract data using dynamic column mapping
                    row = extract_data_by_header(parts, column_map, file_path.name)
                    
                    if row:
                        data.append(row)
                    else:
                        error_count += 1
                        if error_count <= 5:  # Log only first 5 errors
                            logger.warning(f"Could not extract data from {file_path.name}, line {line_num}")
                            
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        logger.warning(f"Error parsing line {line_num} in {file_path.name}: {e}")
        
        df = pd.DataFrame(data)
        
        # Set timestamp as index for time series operations
        if not df.empty and 'Timestamp' in df.columns:
            df.set_index('Timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        # Enhanced logging
        success_rate = (len(df) / max(line_count - 3, 1)) * 100  # Subtract header lines
        
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
                'success_rate_percent': round(success_rate, 1),
                'columns_detected': len(column_map),
                'duration_seconds': duration
            }
        )
        
        if len(df) == 0 and error_count > 0:
            logger.warning(f"File {file_path.name} produced no valid data rows ({error_count} errors)")
        elif error_count > 0:
            logger.info(f"File {file_path.name} parsed with {len(df)} rows ({error_count} errors, {success_rate:.1f}% success)")
        
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
        combined_df = pd.concat(all_data, ignore_index=False)  # Keep index (which is timestamp)
        
        # Reset index to make Timestamp a column for filtering
        combined_df.reset_index(inplace=True)
        
        # Apply date filtering if specified
        if start_date or end_date:
            original_count = len(combined_df)
            if start_date:
                combined_df = combined_df[combined_df['Timestamp'] >= start_date]
            if end_date:
                combined_df = combined_df[combined_df['Timestamp'] <= end_date]
            filtered_count = len(combined_df)
            logger.info(f"Date filtering: {original_count} -> {filtered_count} rows")
        
        # Sort by timestamp and set it back as index
        combined_df = combined_df.sort_values('Timestamp')
        combined_df.set_index('Timestamp', inplace=True)
        
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
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=CHILE_TIMEZONE).date()
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
        combined_df = pd.concat(all_data, ignore_index=False)  # Keep index (which is timestamp)
        
        # Reset index to make Timestamp a column again for grouping
        combined_df.reset_index(inplace=True)
        
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