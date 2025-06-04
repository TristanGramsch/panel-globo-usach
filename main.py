#!/usr/bin/env python3
"""
USACH Environmental Monitoring System - Main Application
Unified entry point that handles data fetching and dashboard display with tabbed interface
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import pandas as pd

# Import our modules
from config.settings import (
    AUTO_REFRESH_INTERVAL, DEFAULT_PORT, DEBUG_MODE, 
    DASHBOARD_TITLE, WHO_GUIDELINES
)
from data.processors import get_current_data, get_available_sensors, get_sensor_data
from data.fetch_piloto_files import PilotoFileFetcher
from utils.helpers import get_air_quality_category

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/main_application.log')
    ]
)
logger = logging.getLogger(__name__)

class USACHMonitoringApp:
    def __init__(self):
        self.app = dash.Dash(__name__, title=DASHBOARD_TITLE)
        self.app.config.suppress_callback_exceptions = True
        self.fetcher = PilotoFileFetcher()
        self.last_fetch = None
        self.data_fetch_interval = 10 * 60  # 10 minutes in seconds
        self.setup_layout()
        self.setup_callbacks()
        self.start_background_fetcher()
    
    def fetch_data_background(self):
        """Background thread to fetch data periodically"""
        while True:
            try:
                logger.info("Background data fetch starting...")
                
                # Check server health first
                if self.fetcher.check_server_health():
                    result = self.fetcher.run_fetch_cycle()
                    self.last_fetch = datetime.now()
                    logger.info(f"Background fetch completed: {result}")
                else:
                    logger.warning("Server health check failed, skipping fetch")
                
            except Exception as e:
                logger.error(f"Error in background data fetch: {e}")
            
            # Wait for next fetch cycle
            time.sleep(self.data_fetch_interval)
    
    def start_background_fetcher(self):
        """Start the background data fetching thread"""
        # Initial fetch
        try:
            logger.info("Performing initial data fetch...")
            if self.fetcher.check_server_health():
                result = self.fetcher.run_fetch_cycle()
                self.last_fetch = datetime.now()
                logger.info(f"Initial fetch completed: {result}")
            else:
                logger.warning("Server unavailable for initial fetch")
        except Exception as e:
            logger.error(f"Error in initial data fetch: {e}")
        
        # Start background thread
        fetch_thread = threading.Thread(target=self.fetch_data_background, daemon=True)
        fetch_thread.start()
        logger.info("Background data fetcher started")
    
    def get_sensor_status_today(self):
        """Get today's sensor status (working vs not working)"""
        today = datetime.now().date()
        available_sensors = get_available_sensors()
        sensor_status = {"working": [], "not_working": []}
        
        for sensor_id in available_sensors:
            try:
                sensor_data = get_sensor_data(sensor_id)
                
                if not sensor_data.empty:
                    # Check if sensor has data from today
                    if hasattr(sensor_data.index, 'date'):
                        today_data = sensor_data[sensor_data.index.date == today]
                    else:
                        # Fallback: check if any data is from today
                        today_data = sensor_data[sensor_data.index >= datetime.combine(today, datetime.min.time())]
                    
                    if not today_data.empty:
                        sensor_status["working"].append(sensor_id)
                    else:
                        sensor_status["not_working"].append(sensor_id)
                else:
                    sensor_status["not_working"].append(sensor_id)
            except Exception as e:
                logger.warning(f"Error checking sensor {sensor_id} status: {e}")
                sensor_status["not_working"].append(sensor_id)
        
        return sensor_status
    
    def create_status_cards(self):
        """Create status cards for the dashboard"""
        current_data = get_current_data()
        sensor_status = self.get_sensor_status_today()
        
        if current_data.empty:
            return html.Div([
                html.H4("No Data Available", className="text-danger"),
                html.P("No sensor data found. Please check data fetching.")
            ])
        
        # Calculate statistics safely
        try:
            avg_mp1 = current_data['MP1'].mean()
            max_mp1 = current_data['MP1'].max()
        except Exception as e:
            logger.error(f"Error calculating MP1 statistics: {e}")
            avg_mp1 = 0
            max_mp1 = 0
        
        total_sensors = len(get_available_sensors())
        working_today = len(sensor_status["working"])
        
        # Get air quality category
        category, color, risk = get_air_quality_category(avg_mp1)
        
        # Safe division to avoid errors
        operational_pct = (working_today / total_sensors * 100) if total_sensors > 0 else 0
        
        return html.Div([
            html.Div([
                html.H4(f"{avg_mp1:.1f} μg/m³", className="mb-1"),
                html.P("Average MP1.0", className="text-muted mb-1"),
                html.Small(f"{category}", style={"color": color, "fontWeight": "bold"})
            ], className="col-md-3 text-center"),
            
            html.Div([
                html.H4(f"{max_mp1:.1f} μg/m³", className="mb-1"),
                html.P("Maximum MP1.0", className="text-muted mb-1"),
                html.Small("Highest reading", className="text-muted")
            ], className="col-md-3 text-center"),
            
            html.Div([
                html.H4(f"{working_today}/{total_sensors}", className="mb-1"),
                html.P("Sensors Working Today", className="text-muted mb-1"),
                html.Small(f"{operational_pct:.0f}% operational", 
                          className="text-success" if operational_pct > 80 else "text-warning")
            ], className="col-md-3 text-center"),
            
            html.Div([
                html.H4(f"{self.last_fetch.strftime('%H:%M') if self.last_fetch else 'Unknown'}", className="mb-1"),
                html.P("Last Update", className="text-muted mb-1"),
                html.Small(f"{self.last_fetch.strftime('%Y-%m-%d') if self.last_fetch else 'Never'}", className="text-muted")
            ], className="col-md-3 text-center")
        ], className="row")
    
    def create_general_overview_chart(self):
        """Create the general overview chart (all sensors)"""
        fig = go.Figure()
        available_sensors = get_available_sensors()
        
        for sensor_id in available_sensors[:10]:  # Limit to 10 sensors for performance
            sensor_data = get_sensor_data(sensor_id)
            if not sensor_data.empty:
                fig.add_trace(go.Scatter(
                    x=sensor_data.index,
                    y=sensor_data['MP1'],
                    mode='lines',
                    name=f'Sensor {sensor_id}',
                    hovertemplate='<b>Sensor %{fullData.name}</b><br>' +
                                  'Time: %{x}<br>' +
                                  'MP1.0: %{y:.1f} μg/m³<extra></extra>'
                ))
        
        # Add WHO guideline lines
        fig.add_hline(y=15, line_dash="dash", line_color="green", 
                      annotation_text="WHO Good (15 μg/m³)")
        fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                      annotation_text="WHO Moderate (25 μg/m³)")
        fig.add_hline(y=35, line_dash="dash", line_color="red", 
                      annotation_text="WHO Unhealthy (35 μg/m³)")
        
        fig.update_layout(
            title="Air Quality Trends - All Sensors MP1.0",
            xaxis_title="Time",
            yaxis_title="MP1.0 (μg/m³)",
            hovermode='x unified',
            height=500
        )
        
        return fig
    
    def create_sensor_specific_chart(self, selected_sensor):
        """Create chart for a specific sensor"""
        if not selected_sensor:
            return go.Figure().add_annotation(
                text="Please select a sensor",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        sensor_data = get_sensor_data(selected_sensor)
        
        if sensor_data.empty:
            return go.Figure().add_annotation(
                text=f"No data available for Sensor {selected_sensor}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=sensor_data.index,
            y=sensor_data['MP1'],
            mode='lines+markers',
            name=f'Sensor {selected_sensor}',
            line=dict(width=2),
            marker=dict(size=4)
        ))
        
        # Add WHO guideline lines
        fig.add_hline(y=15, line_dash="dash", line_color="green", 
                      annotation_text="WHO Good (15 μg/m³)")
        fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                      annotation_text="WHO Moderate (25 μg/m³)")
        fig.add_hline(y=35, line_dash="dash", line_color="red", 
                      annotation_text="WHO Unhealthy (35 μg/m³)")
        
        fig.update_layout(
            title=f"Air Quality Trends - Sensor {selected_sensor}",
            xaxis_title="Time",
            yaxis_title="MP1.0 (μg/m³)",
            height=500
        )
        
        return fig
    
    def create_sensor_health_overview(self):
        """Create sensor health overview with detailed status"""
        available_sensors = get_available_sensors()
        sensor_status = self.get_sensor_status_today()
        
        # Create detailed sensor analysis
        sensor_details = []
        
        for sensor_id in available_sensors:
            try:
                sensor_data = get_sensor_data(sensor_id)
                
                detail = {
                    'Sensor_ID': sensor_id,
                    'Status': 'Working' if sensor_id in sensor_status['working'] else 'Not Working',
                    'Data_Points_Today': 0,
                    'Last_Reading': 'Never',
                    'Average_MP1': 0,
                    'Data_Quality': 'No Data'
                }
                
                if not sensor_data.empty:
                    # Check today's data
                    today = datetime.now().date()
                    today_data = sensor_data[sensor_data.index.date == today] if hasattr(sensor_data.index, 'date') else pd.DataFrame()
                    
                    detail['Data_Points_Today'] = len(today_data)
                    detail['Last_Reading'] = sensor_data.index[-1].strftime('%Y-%m-%d %H:%M')
                    detail['Average_MP1'] = sensor_data['MP1'].mean()
                    
                    # Determine data quality
                    if len(today_data) > 100:
                        detail['Data_Quality'] = 'Excellent'
                    elif len(today_data) > 50:
                        detail['Data_Quality'] = 'Good'
                    elif len(today_data) > 10:
                        detail['Data_Quality'] = 'Fair'
                    elif len(today_data) > 0:
                        detail['Data_Quality'] = 'Poor'
                
                sensor_details.append(detail)
                
            except Exception as e:
                logger.error(f"Error analyzing sensor {sensor_id}: {e}")
                sensor_details.append({
                    'Sensor_ID': sensor_id,
                    'Status': 'Error',
                    'Data_Points_Today': 0,
                    'Last_Reading': 'Error',
                    'Average_MP1': 0,
                    'Data_Quality': 'Error'
                })
        
        # Create health overview table
        health_table = html.Table([
            html.Thead([
                html.Tr([
                    html.Th("Sensor ID"),
                    html.Th("Status"),
                    html.Th("Data Points Today"),
                    html.Th("Last Reading"),
                    html.Th("Avg MP1.0 (μg/m³)"),
                    html.Th("Data Quality")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(f"Sensor {detail['Sensor_ID']}"),
                    html.Td(detail['Status'], 
                            style={'color': 'green' if detail['Status'] == 'Working' else 'red'}),
                    html.Td(str(detail['Data_Points_Today'])),
                    html.Td(detail['Last_Reading']),
                    html.Td(f"{detail['Average_MP1']:.1f}" if detail['Average_MP1'] > 0 else "N/A"),
                    html.Td(detail['Data_Quality'])
                ]) for detail in sensor_details
            ])
        ], className="table table-striped")
        
        return html.Div([
            html.H4("Sensor Health Overview"),
            html.P(f"Total Sensors: {len(available_sensors)} | Working Today: {len(sensor_status['working'])} | Not Working: {len(sensor_status['not_working'])}"),
            health_table
        ])
    
    def setup_layout(self):
        """Setup the tabbed dashboard layout"""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1("USACH Environmental Monitoring System", className="text-center mb-4"),
                html.Hr()
            ]),
            
            # Status cards (always visible)
            html.Div(id="status-cards", className="mb-4"),
            
            # Tabs
            dcc.Tabs(id="main-tabs", value="tab-general", children=[
                dcc.Tab(label="General Overview", value="tab-general"),
                dcc.Tab(label="Sensor Specific", value="tab-sensor"),
                dcc.Tab(label="Sensor Health", value="tab-health")
            ]),
            
            # Tab contents
            html.Div(id="tab-content", className="mt-4"),
            
            # Auto-refresh component
            dcc.Interval(
                id='interval-component',
                interval=AUTO_REFRESH_INTERVAL,  # 10 minutes
                n_intervals=0
            )
        ], className="container")
    
    def setup_callbacks(self):
        """Setup dashboard callbacks"""
        @self.app.callback(
            Output('status-cards', 'children'),
            [Input('interval-component', 'n_intervals')]
        )
        def update_status_cards(n):
            try:
                return self.create_status_cards()
            except Exception as e:
                logger.error(f"Error updating status cards: {e}")
                return html.Div([
                    html.H4("Status Error", className="text-danger"),
                    html.P(f"Error: {str(e)}")
                ])
        
        @self.app.callback(
            Output('tab-content', 'children'),
            [Input('main-tabs', 'value'),
             Input('interval-component', 'n_intervals')]
        )
        def update_tab_content(active_tab, n):
            try:
                if active_tab == 'tab-general':
                    # General Overview Tab
                    return html.Div([
                        html.H3("General Air Quality Overview"),
                        html.P("Showing air quality trends for all sensors"),
                        dcc.Graph(
                            id="general-chart",
                            figure=self.create_general_overview_chart()
                        ),
                        html.Hr(),
                        html.H4("Daily Sensor Status Summary"),
                        html.Div(id="sensor-status-summary")
                    ])
                
                elif active_tab == 'tab-sensor':
                    # Sensor Specific Tab
                    available_sensors = get_available_sensors()
                    return html.Div([
                        html.H3("Sensor-Specific Analysis"),
                        html.Div([
                            html.Label("Select Sensor:"),
                            dcc.Dropdown(
                                id='sensor-dropdown',
                                options=[{'label': f'Sensor {s}', 'value': s} for s in available_sensors],
                                value=available_sensors[0] if available_sensors else None,
                                placeholder="Select a sensor"
                            )
                        ], className="mb-3"),
                        dcc.Graph(id="sensor-specific-chart"),
                        html.Div(id="sensor-details")
                    ])
                
                elif active_tab == 'tab-health':
                    # Sensor Health Tab
                    return html.Div([
                        html.H3("Sensor Health & Maintenance Overview"),
                        html.P("Monitor sensor operational status and data quality for maintenance planning"),
                        self.create_sensor_health_overview()
                    ])
                
            except Exception as e:
                logger.error(f"Error updating tab content: {e}")
                return html.Div([
                    html.H4("Tab Content Error", className="text-danger"),
                    html.P(f"Error: {str(e)}")
                ])
        
        @self.app.callback(
            [Output('sensor-status-summary', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_sensor_status_summary(n):
            try:
                sensor_status = self.get_sensor_status_today()
                return [html.Div([
                    html.Div([
                        html.H5(f"Working Today ({len(sensor_status['working'])})", className="text-success"),
                        html.P(", ".join([f"Sensor {s}" for s in sensor_status["working"]]) or "None"),
                    ], className="col-md-6"),
                    
                    html.Div([
                        html.H5(f"Not Working Today ({len(sensor_status['not_working'])})", className="text-danger"),
                        html.P(", ".join([f"Sensor {s}" for s in sensor_status["not_working"]]) or "None"),
                    ], className="col-md-6")
                ], className="row")]
            except Exception as e:
                logger.error(f"Error updating sensor status summary: {e}")
                return [html.Div("Error loading sensor status")]
        
        @self.app.callback(
            [Output('sensor-specific-chart', 'figure'),
             Output('sensor-details', 'children')],
            [Input('sensor-dropdown', 'value')]
        )
        def update_sensor_specific(selected_sensor):
            try:
                chart = self.create_sensor_specific_chart(selected_sensor)
                
                if selected_sensor:
                    sensor_data = get_sensor_data(selected_sensor)
                    if not sensor_data.empty:
                        details = html.Div([
                            html.H5(f"Sensor {selected_sensor} Details"),
                            html.P(f"Total data points: {len(sensor_data)}"),
                            html.P(f"Date range: {sensor_data.index.min().strftime('%Y-%m-%d')} to {sensor_data.index.max().strftime('%Y-%m-%d')}"),
                            html.P(f"Average MP1.0: {sensor_data['MP1'].mean():.2f} μg/m³"),
                            html.P(f"Max MP1.0: {sensor_data['MP1'].max():.2f} μg/m³"),
                            html.P(f"Min MP1.0: {sensor_data['MP1'].min():.2f} μg/m³")
                        ])
                    else:
                        details = html.P("No data available for this sensor")
                else:
                    details = html.P("Please select a sensor")
                
                return chart, details
            except Exception as e:
                logger.error(f"Error updating sensor specific view: {e}")
                empty_fig = go.Figure()
                return empty_fig, html.P(f"Error: {str(e)}")
    
    def run(self):
        """Run the dashboard application"""
        logger.info(f"Starting USACH Environmental Monitoring Dashboard on port {DEFAULT_PORT}")
        logger.info(f"Dashboard will auto-refresh every {AUTO_REFRESH_INTERVAL/1000/60:.0f} minutes")
        logger.info(f"Data fetching runs every {self.data_fetch_interval/60:.0f} minutes in background")
        
        self.app.run(
            debug=DEBUG_MODE,
            host='0.0.0.0',
            port=DEFAULT_PORT
        )

def main():
    """Main entry point"""
    try:
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Create and run the app
        app = USACHMonitoringApp()
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 