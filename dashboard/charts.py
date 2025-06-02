#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Dashboard Charts
Functions for creating interactive plots and visualizations
"""

import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from pathlib import Path
from config.settings import CHART_COLORS, DATA_DIR, WHO_GUIDELINES
from utils.helpers import safe_file_size_check
from data.processors import parse_piloto_file, get_current_data, get_sensor_data, get_available_sensors
from dashboard.components import create_empty_plot

def get_air_quality_category(mp1_value):
    """Get air quality category and color based on MP1.0 value"""
    if mp1_value <= WHO_GUIDELINES['good_max']:
        return 'Good', '#27ae60', WHO_GUIDELINES['good']['risk']
    elif mp1_value <= WHO_GUIDELINES['moderate_max']:
        return 'Moderate', '#f39c12', WHO_GUIDELINES['moderate']['risk']
    elif mp1_value <= WHO_GUIDELINES['unhealthy_sensitive_max']:
        return 'Unhealthy for Sensitive', '#e67e22', WHO_GUIDELINES['unhealthy_sensitive']['risk']
    elif mp1_value <= WHO_GUIDELINES['unhealthy_max']:
        return 'Unhealthy', '#e74c3c', WHO_GUIDELINES['unhealthy']['risk']
    else:
        return 'Very Unhealthy', '#8e44ad', WHO_GUIDELINES['very_unhealthy']['risk']

def extract_sensor_id_from_filename(filename):
    """Extract sensor ID from filename"""
    try:
        if '_' in filename:
            return filename.split('_')[-1].replace('.dat', '')
        return None
    except:
        return None

def create_time_series_plot():
    """
    Create time series plot of MP1.0 levels for all sensors
    
    Returns:
        go.Figure: Plotly figure
    """
    try:
        if not DATA_DIR.exists():
            return create_empty_plot("No data directory found", "Waiting for Data...")
        
        # Get available sensors
        available_sensors = get_available_sensors()
        if not available_sensors:
            return create_empty_plot("No sensors found", "No Data Available")
        
        fig = go.Figure()
        
        # Create a trace for each sensor
        for i, sensor_id in enumerate(available_sensors[:10]):  # Limit to 10 sensors for readability
            sensor_data = get_sensor_data(sensor_id)
            
            if not sensor_data.empty and 'MP1' in sensor_data.columns:
                color = CHART_COLORS[i % len(CHART_COLORS)]
                
                fig.add_trace(go.Scatter(
                    x=sensor_data.index,
                    y=sensor_data['MP1'],
                    mode='lines',
                    name=f'Sensor {sensor_id}',
                    line=dict(color=color, width=2),
                    hovertemplate=f'<b>Sensor {sensor_id}</b><br>' +
                                 'Time: %{x}<br>' +
                                 'MP1.0: %{y:.1f} μg/m³<br>' +
                                 '<extra></extra>'
                ))
        
        if len(fig.data) == 0:
            return create_empty_plot("No valid data found", "No Data Available")
        
        fig.update_layout(
            title='Multi-Sensor Air Quality Time Series',
            xaxis_title='Time',
            yaxis_title='MP1.0 Particulate Matter (μg/m³)',
            height=500,
            hovermode='x unified',
            showlegend=True,
            template='plotly_white',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
        
    except Exception as e:
        print(f"Error creating time series plot: {e}")
        return create_empty_plot("Error loading data", "Chart Error")

def create_sensor_comparison_plot():
    """
    Create bar chart comparing average MP1.0 levels across sensors
    
    Returns:
        go.Figure: Plotly figure
    """
    try:
        current_data = get_current_data()
        
        if current_data.empty:
            return create_empty_plot("No sensor data available", "Sensor Comparison")
        
        # Extract data for plotting
        sensor_ids = []
        avg_mp1_values = []
        colors = []
        
        for _, row in current_data.iterrows():
            if 'Sensor_ID' in row and 'MP1' in row:
                sensor_ids.append(f"Sensor {row['Sensor_ID']}")
                avg_mp1_values.append(row['MP1'])
                
                # Color code based on WHO guidelines
                _, color, _ = get_air_quality_category(row['MP1'])
                colors.append(color)
        
        if not sensor_ids:
            return create_empty_plot("No valid sensor data", "Sensor Comparison")
        
        fig = go.Figure(data=[
            go.Bar(
                x=sensor_ids,
                y=avg_mp1_values,
                marker_color=colors,
                text=[f"{val:.1f}" for val in avg_mp1_values],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>' +
                             'MP1.0: %{y:.1f} μg/m³<br>' +
                             '<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title='Sensor Comparison - Current MP1.0 Levels',
            xaxis_title='Sensors',
            yaxis_title='MP1.0 (μg/m³)',
            height=400,
            template='plotly_white',
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        print(f"Error creating sensor comparison plot: {e}")
        return create_empty_plot("Error loading sensor data", "Comparison Chart Error")

def create_sensor_detailed_plot(sensor_id, start_date=None, end_date=None):
    """
    Create detailed plot for a specific sensor
    
    Args:
        sensor_id (str): Sensor ID
        start_date (datetime): Start date filter
        end_date (datetime): End date filter
        
    Returns:
        go.Figure: Plotly figure
    """
    try:
        sensor_data = get_sensor_data(sensor_id, start_date, end_date)
        
        if sensor_data.empty or 'MP1' not in sensor_data.columns:
            return create_empty_plot(
                "No data available for selected sensor and date range",
                f"Sensor {sensor_id} - No Data"
            )
        
        # Calculate average for reference line
        avg_mp1 = sensor_data['MP1'].mean()
        
        fig = go.Figure()
        
        # Add main data trace
        fig.add_trace(go.Scatter(
            x=sensor_data.index,
            y=sensor_data['MP1'],
            mode='lines+markers',
            name=f'Sensor {sensor_id}',
            line=dict(color='#3498db', width=2),
            marker=dict(size=4),
            hovertemplate=f'<b>Sensor {sensor_id}</b><br>' +
                         'Time: %{x}<br>' +
                         'MP1.0: %{y:.1f} μg/m³<br>' +
                         '<extra></extra>'
        ))
        
        # Add average line
        fig.add_hline(
            y=avg_mp1,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Average: {avg_mp1:.1f} μg/m³"
        )
        
        # Add WHO guideline lines
        guidelines = [
            (WHO_GUIDELINES['good_max'], 'Good/Moderate', '#27ae60'),
            (WHO_GUIDELINES['moderate_max'], 'Moderate/Unhealthy Sensitive', '#f39c12'),
            (WHO_GUIDELINES['unhealthy_sensitive_max'], 'Unhealthy Sensitive/Unhealthy', '#e67e22'),
            (WHO_GUIDELINES['unhealthy_max'], 'Unhealthy/Very Unhealthy', '#e74c3c')
        ]
        
        for value, label, color in guidelines:
            fig.add_hline(
                y=value,
                line_dash="dot",
                line_color=color,
                annotation_text=f"WHO {label}: {value} μg/m³",
                annotation_position="top right"
            )
        
        fig.update_layout(
            title=f'Detailed Analysis - Sensor {sensor_id}',
            xaxis_title='Time',
            yaxis_title='MP1.0 Particulate Matter (μg/m³)',
            height=600,
            hovermode='x',
            template='plotly_white',
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        print(f"Error creating detailed plot for sensor {sensor_id}: {e}")
        return create_empty_plot("Error loading sensor data", f"Sensor {sensor_id} - Error")

def create_sensor_specific_plot(sensor_id, start_date=None, end_date=None):
    """
    Legacy function - redirects to create_sensor_detailed_plot
    """
    return create_sensor_detailed_plot(sensor_id, start_date, end_date) 