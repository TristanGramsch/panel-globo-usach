#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Utility Functions
Common helper functions used across multiple modules
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from config.settings import WHO_GUIDELINES, ERROR_MESSAGES

def get_air_quality_category(avg_mp1):
    """
    Get air quality category and color based on WHO guidelines
    
    Args:
        avg_mp1 (float): Average MP1.0 level in μg/m³
        
    Returns:
        tuple: (category_label, color, risk_description)
    """
    for category_data in WHO_GUIDELINES.values():
        if avg_mp1 <= category_data['max']:
            return category_data['label'], category_data['color'], category_data['risk']
    
    # Fallback for very high values
    very_unhealthy = WHO_GUIDELINES['very_unhealthy']
    return very_unhealthy['label'], very_unhealthy['color'], very_unhealthy['risk']

def extract_sensor_id_from_filename(filename):
    """
    Extract sensor ID from piloto filename
    
    Args:
        filename (str): Filename like 'Piloto019-020625.dat'
        
    Returns:
        str: Sensor ID like '019' or None if invalid
    """
    try:
        return filename.split('-')[0].replace('Piloto', '')
    except:
        return None

def extract_date_from_filename(filename):
    """
    Extract date from piloto filename
    
    Args:
        filename (str): Filename like 'Piloto019-020625.dat'
        
    Returns:
        datetime: Extracted date or None if invalid
    """
    try:
        date_part = filename.split('-')[1].replace('.dat', '')
        day = int(date_part[:2])
        month = int(date_part[2:4])
        year = 2000 + int(date_part[4:6])
        return datetime(year, month, day)
    except:
        return None

def validate_dataframe(df, required_columns=None):
    """
    Validate if DataFrame is valid and has required columns
    
    Args:
        df (pd.DataFrame): DataFrame to validate
        required_columns (list): List of required column names
        
    Returns:
        bool: True if valid, False otherwise
    """
    if df is None or len(df) == 0:
        return False
    
    if required_columns:
        return all(col in df.columns for col in required_columns)
    
    return True

def safe_file_size_check(file_path, min_size_bytes=100):
    """
    Safely check if file exists and meets minimum size requirement
    
    Args:
        file_path (Path): Path to file
        min_size_bytes (int): Minimum file size in bytes
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    try:
        return file_path.exists() and file_path.stat().st_size >= min_size_bytes
    except:
        return False

def create_directory_if_not_exists(directory_path):
    """
    Create directory if it doesn't exist
    
    Args:
        directory_path (Path): Directory path to create
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
        return True
    except:
        return False

def format_timestamp(dt):
    """
    Format datetime for display
    
    Args:
        dt (datetime): Datetime object
        
    Returns:
        str: Formatted timestamp string
    """
    if dt is None:
        return "Unknown"
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def calculate_time_span_hours(start_dt, end_dt):
    """
    Calculate hours between two datetime objects
    
    Args:
        start_dt (datetime): Start datetime
        end_dt (datetime): End datetime
        
    Returns:
        float: Hours between dates or 0 if invalid
    """
    try:
        if start_dt and end_dt:
            return (end_dt - start_dt).total_seconds() / 3600
    except:
        pass
    return 0.0

def sanitize_sensor_id(sensor_id):
    """
    Sanitize sensor ID to ensure it's valid
    
    Args:
        sensor_id (str): Raw sensor ID
        
    Returns:
        str: Sanitized sensor ID or None if invalid
    """
    if not sensor_id:
        return None
    
    # Remove any non-numeric characters and ensure 3 digits
    try:
        numeric_id = ''.join(filter(str.isdigit, str(sensor_id)))
        if numeric_id:
            return numeric_id.zfill(3)  # Pad with zeros to make 3 digits
    except:
        pass
    
    return None

def get_error_message(error_type, default="An error occurred"):
    """
    Get standardized error message
    
    Args:
        error_type (str): Type of error
        default (str): Default message if type not found
        
    Returns:
        str: Error message
    """
    return ERROR_MESSAGES.get(error_type, default) 