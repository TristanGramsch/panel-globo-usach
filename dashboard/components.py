#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Dashboard Components
Reusable UI components for the Dash dashboard
"""

import plotly.graph_objs as go
import plotly.express as px
from dash import html, dcc
from datetime import datetime
from config.settings import CHART_COLORS, CSS_STYLES
from utils.helpers import get_air_quality_category, format_timestamp

def create_stat_card(title, value, subtitle=None, color='#2c3e50'):
    """
    Create a statistic card component
    
    Args:
        title (str): Card title
        value (str/int): Main value to display
        subtitle (str): Optional subtitle
        color (str): Text color
        
    Returns:
        html.Div: Dash component
    """
    return html.Div([
        html.H3(str(value), style={'margin': '0', 'color': color}),
        html.P(title, style={'margin': '5px 0 0 0', 'color': '#7f8c8d'}),
        html.Small(subtitle, style={'color': '#95a5a6'}) if subtitle else None
    ], className='stat-card', style=CSS_STYLES['stat_card'])

def create_error_message(title, message, error_type='warning'):
    """
    Create an error message component
    
    Args:
        title (str): Error title
        message (str): Error message
        error_type (str): Type of error ('warning', 'error', 'info')
        
    Returns:
        html.Div: Dash component
    """
    colors = {
        'warning': {'bg': '#fff3cd', 'border': '#ffeaa7', 'text': '#856404'},
        'error': {'bg': '#f8d7da', 'border': '#f5c6cb', 'text': '#721c24'},
        'info': {'bg': '#d1ecf1', 'border': '#bee5eb', 'text': '#0c5460'}
    }
    
    color_scheme = colors.get(error_type, colors['info'])
    
    return html.Div([
        html.H3(title, style={'color': color_scheme['text'], 'textAlign': 'center'}),
        html.P(message, style={'textAlign': 'center', 'color': color_scheme['text']})
    ], style={
        'background': color_scheme['bg'],
        'border': f"1px solid {color_scheme['border']}",
        'color': color_scheme['text'],
        'padding': '20px',
        'borderRadius': '5px',
        'textAlign': 'center'
    })

def create_sensor_detail_card(sensor_id, sensor_stats):
    """
    Create a detailed sensor information card
    
    Args:
        sensor_id (str): Sensor ID
        sensor_stats (dict): Sensor statistics
        
    Returns:
        html.Div: Dash component
    """
    avg_mp1 = sensor_stats['mean_mp1']
    category, color, risk = get_air_quality_category(avg_mp1)
    
    return html.Div([
        html.Div([
            html.H4(f"Sensor {sensor_id}", style={'color': '#2c3e50', 'margin': '0'}),
            html.Span(category, style={
                'background': color,
                'color': 'white',
                'padding': '5px 15px',
                'borderRadius': '20px',
                'fontSize': '0.9em',
                'fontWeight': 'bold'
            })
        ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '15px'}),
        
        html.Div([
            html.Div([
                html.Strong(f"{avg_mp1:.1f}"),
                html.Br(),
                html.Small("Avg MP1.0")
            ], style={'textAlign': 'center', 'padding': '10px', 'background': '#f8f9fa', 'borderRadius': '5px'}),
            
            html.Div([
                html.Strong(f"{sensor_stats['max_mp1']:.1f}"),
                html.Br(),
                html.Small("Max MP1.0")
            ], style={'textAlign': 'center', 'padding': '10px', 'background': '#f8f9fa', 'borderRadius': '5px'}),
            
            html.Div([
                html.Strong(f"{sensor_stats['records']}"),
                html.Br(),
                html.Small("Data Points")
            ], style={'textAlign': 'center', 'padding': '10px', 'background': '#f8f9fa', 'borderRadius': '5px'}),
            
            html.Div([
                html.Strong(risk),
                html.Br(),
                html.Small("Health Risk")
            ], style={'textAlign': 'center', 'padding': '10px', 'background': '#f8f9fa', 'borderRadius': '5px'})
        ], style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr 1fr 1fr', 'gap': '10px'})
        
    ], style={
        'border': '1px solid #ddd',
        'borderRadius': '10px',
        'padding': '20px',
        'background': 'white',
        'boxShadow': '0 2px 5px rgba(0,0,0,0.1)',
        'margin': '10px'
    })

def create_empty_plot(message, title="No Data Available"):
    """
    Create an empty plot with a message
    
    Args:
        message (str): Message to display
        title (str): Plot title
        
    Returns:
        go.Figure: Plotly figure
    """
    fig = go.Figure().add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="#7f8c8d")
    )
    fig.update_layout(
        title=title,
        height=400,
        template='plotly_white'
    )
    return fig

def create_status_grid(items, columns=4):
    """
    Create a responsive grid layout for status items
    
    Args:
        items (list): List of Dash components
        columns (int): Number of columns
        
    Returns:
        html.Div: Grid container
    """
    return html.Div(items, style={
        'display': 'grid',
        'gridTemplateColumns': f'repeat(auto-fit, minmax(200px, 1fr))',
        'gap': '20px',
        'margin': '20px 0'
    })

def create_footer(last_update, additional_text=None):
    """
    Create a footer component
    
    Args:
        last_update (str): Last update timestamp
        additional_text (str): Optional additional text
        
    Returns:
        html.Div: Footer component
    """
    return html.Div([
        html.P(last_update, style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
        html.P(additional_text, 
               style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'}) 
               if additional_text else None
    ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})

def create_control_panel(sensor_options, selected_sensor, start_date, end_date):
    """
    Create a control panel for sensor and date selection
    
    Args:
        sensor_options (list): List of sensor options
        selected_sensor (str): Currently selected sensor
        start_date (datetime): Start date
        end_date (datetime): End date
        
    Returns:
        html.Div: Control panel component
    """
    return html.Div([
        html.Div([
            html.Label("Select Sensor:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
            dcc.Dropdown(
                id='sensor-dropdown',
                options=sensor_options,
                value=selected_sensor,
                placeholder="Choose a sensor...",
                style={'marginBottom': '20px'}
            )
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        
        html.Div([
            html.Label("Date Range:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=start_date,
                end_date=end_date,
                display_format='YYYY-MM-DD',
                style={'marginBottom': '20px'}
            )
        ], style={'width': '48%', 'float': 'right', 'display': 'inline-block'})
    ], style={'background': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px'}) 