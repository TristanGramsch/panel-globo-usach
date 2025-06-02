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
from config.settings import DATA_DIR, MIN_FILE_SIZE_BYTES
from utils.helpers import (
    extract_sensor_id_from_filename, 
    extract_date_from_filename,
    safe_file_size_check,
    sanitize_sensor_id
)

def get_available_sensors():
    """
    Get list of available sensor IDs from data files
    
    Returns:
        list: List of sensor IDs
    """
    try:
        sensors = set()
        
        # Look for .dat files in the data directory
        pattern = str(DATA_DIR / "*.dat")
        data_files = glob.glob(pattern)
        
        for file_path in data_files:
            filename = os.path.basename(file_path)
            sensor_id = extract_sensor_id_from_filename(filename)
            if sensor_id:
                sanitized_id = sanitize_sensor_id(sensor_id)
                if sanitized_id:
                    sensors.add(sanitized_id)
        
        return sorted(list(sensors))
        
    except Exception as e:
        logging.error(f"Error getting available sensors: {e}")
        return []

def get_date_range():
    """
    Get the date range of available data
    
    Returns:
        tuple: (start_date, end_date) or (None, None) if no data
    """
    try:
        dates = []
        
        # Look for .dat files in the data directory
        pattern = str(DATA_DIR / "*.dat")
        data_files = glob.glob(pattern)
        
        for file_path in data_files:
            filename = os.path.basename(file_path)
            file_date = extract_date_from_filename(filename)
            if file_date:
                dates.append(file_date)
        
        if dates:
            return min(dates), max(dates)
        else:
            return None, None
            
    except Exception as e:
        logging.error(f"Error getting date range: {e}")
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
        # Read the file - first row has column names, skip the units row (row 1), data starts at row 2
        df = pd.read_csv(file_path, header=0, skiprows=[1], encoding='latin-1')
        
        # Clean column names (remove extra spaces)
        df.columns = df.columns.str.strip()
        
        # Create datetime column - handle the space-separated format
        if 'Fecha' in df.columns and 'Hora' in df.columns:
            # Clean the data columns
            df['Fecha'] = df['Fecha'].astype(str).str.strip()
            df['Hora'] = df['Hora'].astype(str).str.strip()
            
            # Create datetime column
            df['datetime'] = pd.to_datetime(df['Fecha'] + ' ' + df['Hora'], format='%d-%m-%y %H:%M:%S', errors='coerce')
        else:
            logging.warning(f"Date/Time columns not found in {file_path}")
            logging.warning(f"Available columns: {list(df.columns)}")
            return None
        
        # Extract MP1.0 data - look for both possible column formats
        mp1_columns = [col for col in df.columns if 'MP1.0[St.P]' in col]
        if not mp1_columns:
            # Try the simpler format
            mp1_columns = [col for col in df.columns if col == 'MP1.0']
        
        if mp1_columns:
            mp1_col = mp1_columns[0]
            # Convert to numeric, handling the zero-padded format (00156 -> 156)
            df['MP1.0'] = pd.to_numeric(df[mp1_col], errors='coerce')
            
            # Create the columns expected by the dashboard
            df['MP1'] = df['MP1.0']  # For consistency with dashboard expectations
            
            # Extract sensor ID from filename
            filename = os.path.basename(file_path)
            sensor_id = extract_sensor_id_from_filename(filename)
            if sensor_id:
                df['Sensor_ID'] = sanitize_sensor_id(sensor_id)
            else:
                logging.warning(f"Could not extract sensor ID from {file_path}")
                return None
            
            # Filter out rows with invalid datetime
            df = df.dropna(subset=['datetime'])
            
            if df.empty:
                logging.warning(f"No valid data after parsing {file_path}")
                return None
            
            # Set datetime as index
            df.set_index('datetime', inplace=True)
            
            # Keep only the columns we need
            df = df[['MP1', 'Sensor_ID']]
            
            return df
        else:
            logging.warning(f"No MP1.0 column found in {file_path}")
            logging.warning(f"Available columns: {list(df.columns)}")
            return None
        
    except Exception as e:
        logging.error(f"Error parsing file {file_path}: {e}")
        return None

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
        # Find files for this sensor using correct Piloto naming pattern
        pattern = str(DATA_DIR / f"Piloto{sensor_id}-*.dat")
        sensor_files = glob.glob(pattern)
        
        if not sensor_files:
            logging.warning(f"No files found for sensor {sensor_id}")
            return pd.DataFrame()
        
        # Load and combine data
        dataframes = []
        for file_path in sensor_files:
            # Convert string path to Path object for size check
            file_path_obj = Path(file_path)
            if safe_file_size_check(file_path_obj, MIN_FILE_SIZE_BYTES):
                df = parse_piloto_file(file_path)
                if df is not None and not df.empty:
                    dataframes.append(df)
        
        if not dataframes:
            return pd.DataFrame()
        
        # Combine all dataframes
        combined_df = pd.concat(dataframes, ignore_index=False)
        
        # Filter by date range if provided
        if start_date:
            combined_df = combined_df[combined_df.index >= start_date]
        if end_date:
            combined_df = combined_df[combined_df.index <= end_date]
        
        # Sort by datetime
        combined_df.sort_index(inplace=True)
        
        # Remove duplicates (keep first occurrence)
        combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
        
        return combined_df
        
    except Exception as e:
        logging.error(f"Error getting sensor data for {sensor_id}: {e}")
        return pd.DataFrame()

def get_current_data():
    """
    Get current air quality data for dashboard
    
    Returns:
        pd.DataFrame: Current data for all sensors
    """
    try:
        # Get latest data for each sensor
        current_data = []
        available_sensors = get_available_sensors()
        
        for sensor_id in available_sensors:
            sensor_data = get_sensor_data(sensor_id)
            if not sensor_data.empty:
                # Get the most recent reading
                latest = sensor_data.iloc[-1]
                latest_dict = latest.to_dict()
                latest_dict['Sensor_ID'] = sensor_id
                current_data.append(latest_dict)
        
        if current_data:
            return pd.DataFrame(current_data)
        else:
            return pd.DataFrame()
            
    except Exception as e:
        logging.error(f"Error getting current data: {e}")
        return pd.DataFrame() 