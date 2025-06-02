#!/usr/bin/env python3
"""
Visualization script for air quality data analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from analyze_mp1_data import parse_piloto_file
import numpy as np

def create_air_quality_plots():
    """Create visualizations of air quality data"""
    data_dir = Path('piloto_data')
    
    if not data_dir.exists():
        print("No piloto_data directory found. Run fetch_piloto_files.py first.")
        return
    
    # Collect all data
    all_data = []
    sensor_data = {}
    
    for file_path in data_dir.glob("*.dat"):
        if file_path.stat().st_size == 0:
            continue
            
        sensor_id = file_path.name.split('-')[0].replace('Piloto', '')
        df = parse_piloto_file(file_path)
        
        if df is not None and len(df) > 0:
            df['sensor_id'] = sensor_id
            all_data.append(df)
            sensor_data[sensor_id] = df
    
    if not all_data:
        print("No valid data found.")
        return
    
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Air Quality Analysis - MP1.0 Particulate Matter', fontsize=16, fontweight='bold')
    
    # 1. Time series plot for all sensors
    ax1.set_title('MP1.0 Levels Over Time by Sensor', fontweight='bold')
    colors = plt.cm.tab10(np.linspace(0, 1, len(sensor_data)))
    
    for i, (sensor_id, df) in enumerate(sensor_data.items()):
        ax1.plot(df['datetime'], df['MP1.0'], alpha=0.7, 
                label=f'Sensor {sensor_id}', color=colors[i], linewidth=1)
    
    # Add WHO guidelines as horizontal lines
    ax1.axhline(y=15, color='green', linestyle='--', alpha=0.7, label='WHO Good (≤15)')
    ax1.axhline(y=25, color='yellow', linestyle='--', alpha=0.7, label='WHO Moderate (≤25)')
    ax1.axhline(y=35, color='orange', linestyle='--', alpha=0.7, label='WHO Unhealthy Sensitive (≤35)')
    ax1.axhline(y=75, color='red', linestyle='--', alpha=0.7, label='WHO Unhealthy (≤75)')
    
    ax1.set_xlabel('Time')
    ax1.set_ylabel('MP1.0 (μg/m³)')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Box plot comparison
    ax2.set_title('MP1.0 Distribution by Sensor', fontweight='bold')
    sensor_values = []
    sensor_labels = []
    
    for sensor_id in sorted(sensor_data.keys()):
        df = sensor_data[sensor_id]
        sensor_values.append(df['MP1.0'].values)
        sensor_labels.append(f'S{sensor_id}')
    
    bp = ax2.boxplot(sensor_values, labels=sensor_labels, patch_artist=True)
    
    # Color boxes based on average level
    for i, (patch, sensor_id) in enumerate(zip(bp['boxes'], sorted(sensor_data.keys()))):
        avg_val = sensor_data[sensor_id]['MP1.0'].mean()
        if avg_val <= 15:
            patch.set_facecolor('lightgreen')
        elif avg_val <= 25:
            patch.set_facecolor('yellow')
        elif avg_val <= 35:
            patch.set_facecolor('orange')
        elif avg_val <= 75:
            patch.set_facecolor('lightcoral')
        else:
            patch.set_facecolor('red')
    
    ax2.set_ylabel('MP1.0 (μg/m³)')
    ax2.set_xlabel('Sensor')
    ax2.grid(True, alpha=0.3)
    
    # Add WHO guideline lines
    ax2.axhline(y=15, color='green', linestyle='--', alpha=0.7)
    ax2.axhline(y=25, color='yellow', linestyle='--', alpha=0.7)
    ax2.axhline(y=35, color='orange', linestyle='--', alpha=0.7)
    ax2.axhline(y=75, color='red', linestyle='--', alpha=0.7)
    
    # 3. Average levels bar chart
    ax3.set_title('Average MP1.0 Levels by Sensor', fontweight='bold')
    sensor_avgs = []
    sensor_ids = []
    
    for sensor_id in sorted(sensor_data.keys()):
        avg_val = sensor_data[sensor_id]['MP1.0'].mean()
        sensor_avgs.append(avg_val)
        sensor_ids.append(f'Sensor {sensor_id}')
        
    bars = ax3.bar(sensor_ids, sensor_avgs)
    
    # Color bars based on WHO guidelines
    for bar, avg_val in zip(bars, sensor_avgs):
        if avg_val <= 15:
            bar.set_color('lightgreen')
        elif avg_val <= 25:
            bar.set_color('yellow')
        elif avg_val <= 35:
            bar.set_color('orange')
        elif avg_val <= 75:
            bar.set_color('lightcoral')
        else:
            bar.set_color('red')
    
    ax3.set_ylabel('Average MP1.0 (μg/m³)')
    ax3.tick_params(axis='x', rotation=45)
    ax3.grid(True, alpha=0.3)
    
    # Add WHO guideline lines
    ax3.axhline(y=15, color='green', linestyle='--', alpha=0.7)
    ax3.axhline(y=25, color='yellow', linestyle='--', alpha=0.7)
    ax3.axhline(y=35, color='orange', linestyle='--', alpha=0.7)
    ax3.axhline(y=75, color='red', linestyle='--', alpha=0.7)
    
    # 4. Data coverage overview
    ax4.set_title('Data Coverage by Sensor', fontweight='bold')
    sensor_counts = []
    sensor_labels = []
    
    for sensor_id in sorted(sensor_data.keys()):
        count = len(sensor_data[sensor_id])
        sensor_counts.append(count)
        sensor_labels.append(f'S{sensor_id}')
    
    bars = ax4.bar(sensor_labels, sensor_counts, color='skyblue')
    ax4.set_ylabel('Number of Data Points')
    ax4.set_xlabel('Sensor')
    ax4.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for bar, count in zip(bars, sensor_counts):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height + 10,
                f'{count}', ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig('air_quality_analysis.png', dpi=300, bbox_inches='tight')
    print("Air quality visualization saved as 'air_quality_analysis.png'")
    
    # Show summary statistics
    print("\n" + "="*60)
    print("DETAILED SENSOR STATISTICS")
    print("="*60)
    
    for sensor_id in sorted(sensor_data.keys()):
        df = sensor_data[sensor_id]
        avg_val = df['MP1.0'].mean()
        
        # Determine WHO category
        if avg_val <= 15:
            category = "Good (Very low health risk)"
        elif avg_val <= 25:
            category = "Moderate (Low health risk)"
        elif avg_val <= 35:
            category = "Unhealthy for Sensitive (Moderate health risk)"
        elif avg_val <= 75:
            category = "Unhealthy (High health risk)"
        else:
            category = "Very Unhealthy (Very high health risk)"
        
        print(f"\nSensor {sensor_id}:")
        print(f"  Average: {avg_val:.1f} μg/m³")
        print(f"  Range: {df['MP1.0'].min():.1f} - {df['MP1.0'].max():.1f} μg/m³")
        print(f"  Data points: {len(df)}")
        print(f"  WHO Category: {category}")
        
        # Calculate percentage of time in each category
        good = (df['MP1.0'] <= 15).sum()
        moderate = ((df['MP1.0'] > 15) & (df['MP1.0'] <= 25)).sum()
        unhealthy_sens = ((df['MP1.0'] > 25) & (df['MP1.0'] <= 35)).sum()
        unhealthy = ((df['MP1.0'] > 35) & (df['MP1.0'] <= 75)).sum()
        very_unhealthy = (df['MP1.0'] > 75).sum()
        
        total = len(df)
        print(f"  Time distribution:")
        print(f"    Good: {good/total*100:.1f}%")
        print(f"    Moderate: {moderate/total*100:.1f}%")
        print(f"    Unhealthy (Sensitive): {unhealthy_sens/total*100:.1f}%")
        print(f"    Unhealthy: {unhealthy/total*100:.1f}%")
        print(f"    Very Unhealthy: {very_unhealthy/total*100:.1f}%")

if __name__ == "__main__":
    create_air_quality_plots() 