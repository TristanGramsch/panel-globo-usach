#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Dashboard Layouts
Layout definitions for dashboard tabs and pages
"""

from dash import html, dcc
from datetime import datetime, timedelta
from config.settings import AUTO_REFRESH_INTERVAL, DASHBOARD_TITLE
from data.processors import get_available_sensors, get_date_range
from dashboard.components import create_control_panel

# Get global data for layouts
available_sensors = get_available_sensors()
min_date, max_date = get_date_range()

def create_main_layout():
    """
    Create the main dashboard layout with tabs
    
    Returns:
        html.Div: Main layout component
    """
    return html.Div([
        # Header
        html.Div([
            html.H1(DASHBOARD_TITLE, 
                   style={'textAlign': 'center', 'margin': '20px 0', 'color': '#2c3e50'}),
            html.Hr()
        ]),
        
        # Auto-refresh interval component
        dcc.Interval(
            id='interval-component',
            interval=AUTO_REFRESH_INTERVAL,
            n_intervals=0
        ),
        
        # Tab navigation
        dcc.Tabs(id='tabs', value='general-tab', children=[
            dcc.Tab(label='General Overview', value='general-tab'),
            dcc.Tab(label='Specific Sensor Analysis', value='specific-tab')
        ]),
        
        # Tab content container
        html.Div(id='tabs-content', style={'padding': '20px'})
    ])

def create_general_tab_layout():
    """
    Create the general overview tab layout
    
    Returns:
        html.Div: General tab layout
    """
    return html.Div([
        # Status cards container
        html.Div(id='status-cards', style={'margin': '20px 0'}),
        
        # Charts section
        html.Div([
            # Time series plot
            html.Div([
                dcc.Graph(id='time-series-plot')
            ], style={'width': '100%', 'display': 'inline-block', 'margin': '20px 0'}),
            
            # Sensor comparison plot
            html.Div([
                dcc.Graph(id='sensor-comparison-plot')
            ], style={'width': '100%', 'display': 'inline-block', 'margin': '20px 0'})
        ]),
        
        # Sensor details section
        html.Div(id='sensor-details', style={'margin': '20px 0'}),
        
        # Footer
        html.Div([
            html.P(id='last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("Dashboard auto-refreshes every 10 minutes for real-time monitoring", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
    ])

def create_specific_tab_layout():
    """
    Create the specific sensor analysis tab layout
    
    Returns:
        html.Div: Specific tab layout
    """
    # Create sensor options
    sensor_options = [{'label': f'Sensor {s}', 'value': s} for s in available_sensors]
    
    # Create date picker defaults
    default_start = min_date if min_date else datetime.now() - timedelta(days=7)
    default_end = max_date if max_date else datetime.now()
    
    return html.Div([
        # Control panel
        html.Div([
            html.Div([
                html.Label("Select Sensor:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id='sensor-dropdown',
                    options=sensor_options,
                    value=available_sensors[0] if available_sensors else None,
                    placeholder="Choose a sensor...",
                    style={'marginBottom': '20px'}
                )
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            html.Div([
                html.Label("Date Range:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=default_start,
                    end_date=default_end,
                    display_format='YYYY-MM-DD',
                    style={'marginBottom': '20px'}
                )
            ], style={'width': '48%', 'float': 'right', 'display': 'inline-block'})
        ], style={'background': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px'}),
        
        # Statistics cards
        html.Div(id='sensor-stats-cards', style={'margin': '20px 0'}),
        
        # Detailed plot
        html.Div([
            dcc.Graph(id='sensor-detailed-plot')
        ], style={'width': '100%', 'margin': '20px 0'}),
        
        # Footer
        html.Div([
            html.P(id='sensor-last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("Use the controls above to analyze specific sensors over custom time periods", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
    ])

def create_error_layout(error_title, error_message):
    """
    Create an error layout for when something goes wrong
    
    Args:
        error_title (str): Error title
        error_message (str): Error message
        
    Returns:
        html.Div: Error layout
    """
    return html.Div([
        html.Div([
            html.H1("USACH Air Quality Monitor", 
                   style={'textAlign': 'center', 'margin': '20px 0', 'color': '#2c3e50'}),
            html.Hr()
        ]),
        
        html.Div([
            html.H2(error_title, style={'color': '#e74c3c', 'textAlign': 'center'}),
            html.P(error_message, style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '1.1em'}),
            html.P("Please check the system logs for more details.", 
                   style={'textAlign': 'center', 'color': '#95a5a6', 'fontSize': '0.9em'})
        ], style={
            'background': '#f8d7da',
            'border': '1px solid #f5c6cb',
            'color': '#721c24',
            'padding': '40px',
            'borderRadius': '10px',
            'textAlign': 'center',
            'margin': '50px auto',
            'maxWidth': '600px'
        })
    ])

def create_loading_layout():
    """
    Create a loading layout while data is being processed
    
    Returns:
        html.Div: Loading layout
    """
    return html.Div([
        html.Div([
            html.H1("USACH Air Quality Monitor", 
                   style={'textAlign': 'center', 'margin': '20px 0', 'color': '#2c3e50'}),
            html.Hr()
        ]),
        
        html.Div([
            dcc.Loading(
                id="loading",
                children=[
                    html.Div([
                        html.H2("Loading Air Quality Data...", 
                               style={'color': '#3498db', 'textAlign': 'center'}),
                        html.P("Please wait while we process the latest environmental data.", 
                               style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '1.1em'})
                    ])
                ],
                type="circle",
                style={'margin': '50px auto'}
            )
        ], style={
            'background': '#d1ecf1',
            'border': '1px solid #bee5eb',
            'color': '#0c5460',
            'padding': '40px',
            'borderRadius': '10px',
            'textAlign': 'center',
            'margin': '50px auto',
            'maxWidth': '600px'
        })
    ]) 