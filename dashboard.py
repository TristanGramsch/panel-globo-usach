#!/usr/bin/env python3
"""
Simple Air Quality Dashboard for USACH Environmental Monitoring
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from analyze_mp1_data import analyze_current_data

def print_header():
    """Print dashboard header"""
    print("="*80)
    print("🌍 USACH ENVIRONMENTAL MONITORING DASHBOARD 🌍")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def print_air_quality_alert(avg_level):
    """Print color-coded air quality alert"""
    if avg_level <= 15:
        status = "🟢 GOOD"
        risk = "Very low health risk"
    elif avg_level <= 25:
        status = "🟡 MODERATE" 
        risk = "Low health risk"
    elif avg_level <= 35:
        status = "🟠 UNHEALTHY FOR SENSITIVE"
        risk = "Moderate health risk"
    elif avg_level <= 75:
        status = "🔴 UNHEALTHY"
        risk = "High health risk"
    else:
        status = "🟣 VERY UNHEALTHY"
        risk = "Very high health risk"
    
    print(f"Overall Air Quality: {status}")
    print(f"Health Risk Level: {risk}")
    print()

def print_sensor_alerts(sensor_summaries):
    """Print alerts for problematic sensors"""
    critical_sensors = []
    warning_sensors = []
    
    for sensor_id, stats in sensor_summaries.items():
        avg = stats['mean_mp1']
        if avg > 75:
            critical_sensors.append((sensor_id, avg))
        elif avg > 35:
            warning_sensors.append((sensor_id, avg))
    
    if critical_sensors:
        print("🚨 CRITICAL ALERTS - VERY UNHEALTHY LEVELS:")
        for sensor_id, avg in sorted(critical_sensors, key=lambda x: x[1], reverse=True):
            print(f"   Sensor {sensor_id}: {avg:.1f} μg/m³")
        print()
    
    if warning_sensors:
        print("⚠️  WARNING ALERTS - UNHEALTHY LEVELS:")
        for sensor_id, avg in sorted(warning_sensors, key=lambda x: x[1], reverse=True):
            print(f"   Sensor {sensor_id}: {avg:.1f} μg/m³")
        print()

def print_recommendations(overall_avg):
    """Print health recommendations based on air quality"""
    print("📋 HEALTH RECOMMENDATIONS:")
    print("-" * 40)
    
    if overall_avg <= 15:
        print("✅ Air quality is good. Normal outdoor activities are safe.")
    elif overall_avg <= 25:
        print("⚠️  Sensitive individuals should consider limiting prolonged outdoor exertion.")
    elif overall_avg <= 35:
        print("⚠️  Sensitive groups should avoid prolonged outdoor exertion.")
        print("   Everyone else should limit prolonged outdoor exertion.")
    elif overall_avg <= 75:
        print("🚫 Everyone should avoid prolonged outdoor exertion.")
        print("   Sensitive groups should avoid all outdoor exertion.")
    else:
        print("🚨 HEALTH WARNING: Everyone should avoid all outdoor exertion.")
        print("   Stay indoors and keep windows closed.")
        print("   Use air purifiers if available.")
    print()

def run_dashboard():
    """Run the main dashboard"""
    print_header()
    
    # Check if data exists
    data_dir = Path('piloto_data')
    if not data_dir.exists():
        print("❌ No data directory found!")
        print("   Run 'python fetch_piloto_files.py' first to download data.")
        return
    
    # Count available files
    dat_files = list(data_dir.glob("*.dat"))
    non_empty_files = [f for f in dat_files if f.stat().st_size > 0]
    
    print(f"📊 DATA STATUS:")
    print(f"   Total files: {len(dat_files)}")
    print(f"   Non-empty files: {len(non_empty_files)}")
    print(f"   Empty files: {len(dat_files) - len(non_empty_files)}")
    print()
    
    # Run analysis
    try:
        result = analyze_current_data()
        if result is None:
            print("❌ No valid data found for analysis.")
            return
            
        combined_df, sensor_summaries = result
        
        # Overall statistics
        overall_avg = combined_df['MP1.0'].mean()
        overall_max = combined_df['MP1.0'].max()
        total_points = len(combined_df)
        
        print_air_quality_alert(overall_avg)
        
        print(f"📈 CURRENT STATISTICS:")
        print(f"   Average MP1.0: {overall_avg:.1f} μg/m³")
        print(f"   Maximum MP1.0: {overall_max:.1f} μg/m³")
        print(f"   Total data points: {total_points:,}")
        print(f"   Active sensors: {len(sensor_summaries)}")
        print()
        
        # Sensor alerts
        print_sensor_alerts(sensor_summaries)
        
        # Top 3 worst sensors
        sensor_rankings = [(sensor_id, stats['mean_mp1']) for sensor_id, stats in sensor_summaries.items()]
        sensor_rankings.sort(key=lambda x: x[1], reverse=True)
        
        print("🏆 TOP 3 HIGHEST POLLUTION SENSORS:")
        for i, (sensor_id, avg) in enumerate(sensor_rankings[:3]):
            stats = sensor_summaries[sensor_id]
            print(f"   {i+1}. Sensor {sensor_id}: {avg:.1f} μg/m³ (max: {stats['max_mp1']:.1f})")
        print()
        
        # Health recommendations
        print_recommendations(overall_avg)
        
        # Data freshness
        latest_reading = combined_df['datetime'].max()
        time_since = datetime.now() - latest_reading.to_pydatetime()
        
        print(f"🕐 DATA FRESHNESS:")
        print(f"   Latest reading: {latest_reading}")
        print(f"   Time since last update: {time_since}")
        print()
        
        print("💡 TIP: Run 'python fetch_piloto_files.py' to update data")
        print("       Run 'python visualize_air_quality.py' for detailed charts")
        
    except Exception as e:
        print(f"❌ Error running analysis: {e}")
        print("   Check that data files are properly formatted.")

if __name__ == "__main__":
    run_dashboard() 