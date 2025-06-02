#!/usr/bin/env python3
"""
Quick analysis script for MP1.0 data from Piloto files
"""

import os
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

def parse_piloto_file(file_path):
    """Parse a Piloto .dat file and extract MP1.0 data"""
    try:
        # Read the file - first row has column names, skip the units row (row 1), data starts at row 2
        df = pd.read_csv(file_path, header=0, skiprows=[1], encoding='latin-1')
        
        # Clean column names (remove extra spaces)
        df.columns = df.columns.str.strip()
        
        # Debug: print column names for first file
        if 'Piloto100-010625.dat' in str(file_path):
            print(f"Columns found: {list(df.columns)}")
        
        # Create datetime column - handle the space-separated format
        if 'Fecha' in df.columns and 'Hora' in df.columns:
            # Clean the data columns
            df['Fecha'] = df['Fecha'].astype(str).str.strip()
            df['Hora'] = df['Hora'].astype(str).str.strip()
            
            # Create datetime column
            df['datetime'] = pd.to_datetime(df['Fecha'] + ' ' + df['Hora'], format='%d-%m-%y %H:%M:%S', errors='coerce')
        else:
            print(f"Warning: Date/Time columns not found in {file_path}")
            print(f"Available columns: {list(df.columns)}")
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
            return df[['datetime', 'MP1.0']].dropna()
        else:
            print(f"Warning: No MP1.0 column found in {file_path}")
            print(f"Available columns: {list(df.columns)}")
            return None
            
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

def analyze_current_data():
    """Analyze current month's MP1.0 data"""
    data_dir = Path('piloto_data')
    
    if not data_dir.exists():
        print("No piloto_data directory found. Run fetch_piloto_files.py first.")
        return
    
    print("Analyzing MP1.0 data from downloaded Piloto files...")
    print("="*60)
    
    all_data = []
    sensor_summaries = {}
    
    # Process each .dat file
    for file_path in data_dir.glob("*.dat"):
        if file_path.stat().st_size == 0:
            print(f"Skipping empty file: {file_path.name}")
            continue
            
        # Extract sensor ID from filename
        sensor_id = file_path.name.split('-')[0].replace('Piloto', '')
        
        print(f"Processing {file_path.name} (Sensor {sensor_id})...")
        
        df = parse_piloto_file(file_path)
        if df is not None and len(df) > 0:
            df['sensor_id'] = sensor_id
            all_data.append(df)
            
            # Calculate basic statistics
            stats = {
                'records': len(df),
                'min_mp1': df['MP1.0'].min(),
                'max_mp1': df['MP1.0'].max(),
                'mean_mp1': df['MP1.0'].mean(),
                'std_mp1': df['MP1.0'].std(),
                'first_reading': df['datetime'].min(),
                'last_reading': df['datetime'].max()
            }
            sensor_summaries[sensor_id] = stats
            
            print(f"  → {stats['records']} data points")
            print(f"  → MP1.0 range: {stats['min_mp1']:.1f} - {stats['max_mp1']:.1f} μg/m³")
            print(f"  → MP1.0 average: {stats['mean_mp1']:.1f} μg/m³")
            print(f"  → Data span: {stats['first_reading']} to {stats['last_reading']}")
            print()
    
    if not all_data:
        print("No valid data found in any files.")
        return
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    print("OVERALL SUMMARY")
    print("="*60)
    print(f"Total sensors with data: {len(sensor_summaries)}")
    print(f"Total data points: {len(combined_df)}")
    print(f"Date range: {combined_df['datetime'].min()} to {combined_df['datetime'].max()}")
    print(f"Overall MP1.0 range: {combined_df['MP1.0'].min():.1f} - {combined_df['MP1.0'].max():.1f} μg/m³")
    print(f"Overall MP1.0 average: {combined_df['MP1.0'].mean():.1f} μg/m³")
    print()
    
    # Sensor rankings
    print("SENSOR RANKINGS BY AVERAGE MP1.0")
    print("="*60)
    sensor_avgs = [(sensor_id, stats['mean_mp1']) for sensor_id, stats in sensor_summaries.items()]
    sensor_avgs.sort(key=lambda x: x[1], reverse=True)
    
    for i, (sensor_id, avg_mp1) in enumerate(sensor_avgs):
        stats = sensor_summaries[sensor_id]
        print(f"{i+1:2d}. Sensor {sensor_id:3s}: {avg_mp1:6.1f} μg/m³ ({stats['records']} points)")
    
    print("\nAir Quality Assessment (WHO guidelines):")
    print("- Good (≤15 μg/m³): Very low health risk")
    print("- Moderate (15-25 μg/m³): Low health risk") 
    print("- Unhealthy for sensitive (25-35 μg/m³): Moderate health risk")
    print("- Unhealthy (35-75 μg/m³): High health risk")
    print("- Very Unhealthy (>75 μg/m³): Very high health risk")
    
    return combined_df, sensor_summaries

if __name__ == "__main__":
    try:
        combined_df, sensor_summaries = analyze_current_data()
    except Exception as e:
        print(f"Analysis failed: {e}") 