#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Web Dashboard
A Flask-based web interface for real-time air quality monitoring
"""

from flask import Flask, render_template, jsonify, send_file
import os
import pandas as pd
from datetime import datetime, timedelta
import json
import glob
from analyze_mp1_data import parse_piloto_file, get_air_quality_category

app = Flask(__name__)

def get_latest_data():
    """Get the latest air quality data from all sensors"""
    data_dir = "piloto_data"
    if not os.path.exists(data_dir):
        return None
    
    all_data = []
    sensor_stats = {}
    
    # Get all .dat files
    dat_files = glob.glob(os.path.join(data_dir, "*.dat"))
    
    for file_path in dat_files:
        if os.path.getsize(file_path) == 0:
            continue
            
        try:
            df = parse_piloto_file(file_path)
            if df is not None and not df.empty and 'MP1.0' in df.columns:
                # Extract sensor number from filename
                filename = os.path.basename(file_path)
                sensor_match = filename.replace('Piloto', '').split('-')[0]
                sensor_id = sensor_match
                
                # Calculate statistics
                mp1_data = df['MP1.0'].dropna()
                if len(mp1_data) > 0:
                    avg_mp1 = mp1_data.mean()
                    max_mp1 = mp1_data.max()
                    min_mp1 = mp1_data.min()
                    latest_reading = mp1_data.iloc[-1] if len(mp1_data) > 0 else None
                    latest_time = df['datetime'].iloc[-1] if 'datetime' in df.columns else None
                    
                    category, color, risk = get_air_quality_category(avg_mp1)
                    
                    sensor_stats[sensor_id] = {
                        'sensor_id': sensor_id,
                        'avg_mp1': round(avg_mp1, 1),
                        'max_mp1': round(max_mp1, 1),
                        'min_mp1': round(min_mp1, 1),
                        'latest_reading': round(latest_reading, 1) if latest_reading else None,
                        'latest_time': latest_time.strftime('%Y-%m-%d %H:%M:%S') if latest_time else None,
                        'data_points': len(mp1_data),
                        'category': category,
                        'color': color,
                        'risk': risk
                    }
                    
                    # Add to all_data for time series
                    df_copy = df.copy()
                    df_copy['sensor_id'] = sensor_id
                    all_data.append(df_copy)
                    
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Combine all data for overall statistics
    overall_stats = None
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        if 'MP1.0' in combined_df.columns:
            mp1_data = combined_df['MP1.0'].dropna()
            if len(mp1_data) > 0:
                overall_avg = mp1_data.mean()
                overall_category, overall_color, overall_risk = get_air_quality_category(overall_avg)
                
                overall_stats = {
                    'avg_mp1': round(overall_avg, 1),
                    'max_mp1': round(mp1_data.max(), 1),
                    'min_mp1': round(mp1_data.min(), 1),
                    'total_sensors': len(sensor_stats),
                    'total_points': len(mp1_data),
                    'category': overall_category,
                    'color': overall_color,
                    'risk': overall_risk,
                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
    
    return {
        'sensors': sensor_stats,
        'overall': overall_stats,
        'raw_data': all_data
    }

def get_health_recommendations(avg_mp1):
    """Get health recommendations based on air quality level"""
    if avg_mp1 <= 15:
        return {
            'level': 'Good',
            'icon': '🟢',
            'recommendations': [
                'Air quality is satisfactory',
                'Ideal for all outdoor activities',
                'No health concerns for any group'
            ]
        }
    elif avg_mp1 <= 25:
        return {
            'level': 'Moderate',
            'icon': '🟡',
            'recommendations': [
                'Air quality is acceptable for most people',
                'Sensitive individuals may experience minor symptoms',
                'Consider reducing prolonged outdoor exertion'
            ]
        }
    elif avg_mp1 <= 35:
        return {
            'level': 'Unhealthy for Sensitive Groups',
            'icon': '🟠',
            'recommendations': [
                'Sensitive groups should limit outdoor activities',
                'Children and elderly should reduce outdoor time',
                'Consider wearing masks during outdoor activities'
            ]
        }
    elif avg_mp1 <= 75:
        return {
            'level': 'Unhealthy',
            'icon': '🔴',
            'recommendations': [
                'Everyone should limit outdoor activities',
                'Avoid prolonged outdoor exertion',
                'Keep windows closed and use air purifiers'
            ]
        }
    else:
        return {
            'level': 'Very Unhealthy',
            'icon': '🟣',
            'recommendations': [
                'Avoid all outdoor activities',
                'Stay indoors with windows closed',
                'Use air purifiers and masks if going outside'
            ]
        }

@app.route('/')
def dashboard():
    """Main dashboard page"""
    data = get_latest_data()
    if not data or not data['overall']:
        return render_template('dashboard.html', error="No data available")
    
    # Get health recommendations
    recommendations = get_health_recommendations(data['overall']['avg_mp1'])
    
    # Sort sensors by pollution level (highest first)
    sorted_sensors = sorted(data['sensors'].values(), 
                          key=lambda x: x['avg_mp1'], reverse=True)
    
    return render_template('dashboard.html', 
                         overall=data['overall'],
                         sensors=sorted_sensors,
                         recommendations=recommendations)

@app.route('/api/data')
def api_data():
    """API endpoint for current data"""
    data = get_latest_data()
    if not data:
        return jsonify({'error': 'No data available'})
    
    return jsonify(data)

@app.route('/api/sensor/<sensor_id>')
def api_sensor(sensor_id):
    """API endpoint for specific sensor data"""
    data = get_latest_data()
    if not data or sensor_id not in data['sensors']:
        return jsonify({'error': 'Sensor not found'})
    
    return jsonify(data['sensors'][sensor_id])

@app.route('/chart')
def chart_page():
    """Chart visualization page"""
    return render_template('chart.html')

@app.route('/api/chart_data')
def chart_data():
    """API endpoint for chart data"""
    data = get_latest_data()
    if not data or not data['raw_data']:
        return jsonify({'error': 'No data available'})
    
    # Prepare data for charts
    chart_data = {
        'sensors': [],
        'timestamps': [],
        'values': {}
    }
    
    for df in data['raw_data']:
        if 'datetime' in df.columns and 'MP1.0' in df.columns:
            sensor_id = df['sensor_id'].iloc[0]
            
            # Sample data points (take every 10th point to reduce load)
            sample_df = df.iloc[::10].copy()
            
            timestamps = sample_df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
            values = sample_df['MP1.0'].fillna(0).tolist()
            
            chart_data['values'][sensor_id] = {
                'timestamps': timestamps,
                'values': values,
                'color': data['sensors'][sensor_id]['color']
            }
            
            if sensor_id not in chart_data['sensors']:
                chart_data['sensors'].append(sensor_id)
    
    return jsonify(chart_data)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create basic HTML templates
    dashboard_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>USACH Air Quality Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.8;
            font-size: 1.1em;
        }
        .overall-status {
            padding: 30px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }
        .status-card {
            display: inline-block;
            padding: 20px 40px;
            border-radius: 10px;
            margin: 10px;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
        }
        .good { background: #27ae60; }
        .moderate { background: #f39c12; }
        .unhealthy-sensitive { background: #e67e22; }
        .unhealthy { background: #e74c3c; }
        .very-unhealthy { background: #8e44ad; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }
        .stat-label {
            color: #7f8c8d;
            margin-top: 5px;
        }
        .sensors-section {
            padding: 30px;
        }
        .sensor-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .sensor-card {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            background: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .sensor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .sensor-id {
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
        }
        .sensor-status {
            padding: 5px 15px;
            border-radius: 20px;
            color: white;
            font-size: 0.9em;
            font-weight: bold;
        }
        .sensor-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }
        .sensor-stat {
            text-align: center;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .recommendations {
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 30px;
            border-radius: 5px;
        }
        .recommendations h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .recommendations ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .recommendations li {
            margin: 5px 0;
            color: #34495e;
        }
        .nav-links {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
        }
        .nav-links a {
            display: inline-block;
            margin: 0 10px;
            padding: 10px 20px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.3s;
        }
        .nav-links a:hover {
            background: #2980b9;
        }
        .error {
            text-align: center;
            padding: 50px;
            color: #e74c3c;
            font-size: 1.2em;
        }
        .refresh-info {
            text-align: center;
            padding: 10px;
            background: #ecf0f1;
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function() {
            location.reload();
        }, 300000);
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 USACH Air Quality Monitor</h1>
            <p>Real-time Environmental Data Dashboard</p>
        </div>
        
        {% if error %}
        <div class="error">
            <h2>⚠️ {{ error }}</h2>
            <p>Please ensure data has been collected using the fetch script.</p>
        </div>
        {% else %}
        
        <div class="overall-status">
            <div class="status-card {{ overall.color }}">
                {{ recommendations.icon }} {{ overall.category }}
            </div>
            <p style="margin-top: 15px; color: #7f8c8d;">
                Overall Air Quality: <strong>{{ overall.avg_mp1 }} μg/m³</strong>
            </p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ overall.total_sensors }}</div>
                <div class="stat-label">Active Sensors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ overall.avg_mp1 }}</div>
                <div class="stat-label">Avg MP1.0 (μg/m³)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ overall.max_mp1 }}</div>
                <div class="stat-label">Max MP1.0 (μg/m³)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ overall.total_points }}</div>
                <div class="stat-label">Total Data Points</div>
            </div>
        </div>
        
        <div class="recommendations">
            <h3>{{ recommendations.icon }} Health Recommendations</h3>
            <ul>
                {% for rec in recommendations.recommendations %}
                <li>{{ rec }}</li>
                {% endfor %}
            </ul>
        </div>
        
        <div class="sensors-section">
            <h2>📊 Sensor Details</h2>
            <div class="sensor-grid">
                {% for sensor in sensors %}
                <div class="sensor-card">
                    <div class="sensor-header">
                        <div class="sensor-id">Sensor {{ sensor.sensor_id }}</div>
                        <div class="sensor-status {{ sensor.color }}">{{ sensor.category }}</div>
                    </div>
                    <div class="sensor-stats">
                        <div class="sensor-stat">
                            <strong>{{ sensor.avg_mp1 }}</strong><br>
                            <small>Avg MP1.0</small>
                        </div>
                        <div class="sensor-stat">
                            <strong>{{ sensor.max_mp1 }}</strong><br>
                            <small>Max MP1.0</small>
                        </div>
                        <div class="sensor-stat">
                            <strong>{{ sensor.data_points }}</strong><br>
                            <small>Data Points</small>
                        </div>
                        <div class="sensor-stat">
                            <strong>{{ sensor.latest_reading or 'N/A' }}</strong><br>
                            <small>Latest Reading</small>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        {% endif %}
        
        <div class="nav-links">
            <a href="/">🏠 Dashboard</a>
            <a href="/chart">📈 Charts</a>
            <a href="/api/data">🔗 API Data</a>
        </div>
        
        <div class="refresh-info">
            Last updated: {{ overall.last_update if overall else 'Unknown' }} | 
            Page auto-refreshes every 5 minutes
        </div>
    </div>
</body>
</html>'''
    
    chart_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>USACH Air Quality Charts</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .chart-container {
            padding: 30px;
            height: 500px;
        }
        .nav-links {
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
        }
        .nav-links a {
            display: inline-block;
            margin: 0 10px;
            padding: 10px 20px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.3s;
        }
        .nav-links a:hover {
            background: #2980b9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Air Quality Trends</h1>
            <p>MP1.0 Particulate Matter Over Time</p>
        </div>
        
        <div class="chart-container">
            <canvas id="airQualityChart"></canvas>
        </div>
        
        <div class="nav-links">
            <a href="/">🏠 Dashboard</a>
            <a href="/chart">📈 Charts</a>
            <a href="/api/data">🔗 API Data</a>
        </div>
    </div>
    
    <script>
        fetch('/api/chart_data')
            .then(response => response.json())
            .then(data => {
                const ctx = document.getElementById('airQualityChart').getContext('2d');
                
                const datasets = [];
                const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#f1c40f'];
                
                let colorIndex = 0;
                for (const sensorId of data.sensors) {
                    const sensorData = data.values[sensorId];
                    datasets.push({
                        label: `Sensor ${sensorId}`,
                        data: sensorData.values,
                        borderColor: colors[colorIndex % colors.length],
                        backgroundColor: colors[colorIndex % colors.length] + '20',
                        fill: false,
                        tension: 0.1
                    });
                    colorIndex++;
                }
                
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.values[data.sensors[0]]?.timestamps || [],
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'MP1.0 (μg/m³)'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Time'
                                }
                            }
                        },
                        plugins: {
                            title: {
                                display: true,
                                text: 'Air Quality Trends by Sensor'
                            },
                            legend: {
                                display: true,
                                position: 'top'
                            }
                        }
                    }
                });
            })
            .catch(error => {
                console.error('Error loading chart data:', error);
                document.querySelector('.chart-container').innerHTML = '<p style="text-align: center; color: #e74c3c;">Error loading chart data</p>';
            });
    </script>
</body>
</html>'''
    
    # Write template files
    with open('templates/dashboard.html', 'w') as f:
        f.write(dashboard_html)
    
    with open('templates/chart.html', 'w') as f:
        f.write(chart_html)
    
    print("🌐 Starting USACH Air Quality Web Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("📈 Charts available at: http://localhost:5000/chart")
    print("🔗 API available at: http://localhost:5000/api/data")
    print("\n💡 Tip: Run 'python fetch_piloto_files.py' first to ensure you have data!")
    
    app.run(debug=True, host='0.0.0.0', port=5000) 