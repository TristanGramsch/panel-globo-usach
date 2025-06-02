#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Dashboard Callbacks
Callback functions for dashboard interactivity
"""

from dash import Input, Output, callback, no_update
from datetime import datetime
import logging

from data.processors import get_current_data, get_sensor_data, get_available_sensors
from dashboard.charts import create_time_series_plot, create_sensor_comparison_plot, create_sensor_detailed_plot
from dashboard.components import create_stat_card, create_sensor_detail_card, create_error_message, create_status_grid
from dashboard.layouts import create_general_tab_layout, create_specific_tab_layout
from utils.helpers import parse_date, safe_file_size_check
from config.settings import WHO_GUIDELINES, ERROR_MESSAGES


def register_callbacks(app):
    """
    Register all dashboard callbacks with the Dash app
    
    Args:
        app: Dash application instance
    """
    
    @app.callback(
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    def render_tab_content(active_tab):
        """
        Render content based on active tab
        
        Args:
            active_tab (str): Active tab value
            
        Returns:
            html.Div: Tab content
        """
        try:
            if active_tab == 'general-tab':
                return create_general_tab_layout()
            elif active_tab == 'specific-tab':
                return create_specific_tab_layout()
            else:
                return create_error_message("Unknown Tab", "The requested tab could not be found.")
        except Exception as e:
            logging.error(f"Error rendering tab content: {e}")
            return create_error_message("Tab Error", "Unable to load tab content.")

    @app.callback(
        [Output('status-cards', 'children'),
         Output('sensor-details', 'children'),
         Output('last-update', 'children')],
        Input('interval-component', 'n_intervals')
    )
    def update_general_overview(n):
        """
        Update general overview tab components
        
        Args:
            n (int): Number of intervals elapsed
            
        Returns:
            tuple: Status cards, sensor details, last update
        """
        try:
            current_data = get_current_data()
            
            if current_data.empty:
                error_msg = create_error_message("No Data", ERROR_MESSAGES['no_data'])
                return error_msg, [], "Last updated: No data available"
            
            # Status cards
            active_sensors = len(current_data)
            total_readings = len(current_data)
            avg_mp1 = current_data['MP1'].mean() if 'MP1' in current_data.columns else 0
            
            status_cards = create_status_grid([
                create_stat_card("Active Sensors", active_sensors, "Currently reporting", '#3498db'),
                create_stat_card("Total Readings", total_readings, "Recent measurements", '#2ecc71'),
                create_stat_card("Avg MP1.0", f"{avg_mp1:.2f} μg/m³", "Across all sensors", '#e74c3c')
            ])
            
            # Sensor details
            sensor_details = []
            for _, row in current_data.iterrows():
                if 'Sensor_ID' in row and 'MP1' in row:
                    sensor_stats = {
                        'avg': row['MP1'],
                        'max': row['MP1'],
                        'count': 1,
                        'health_risk': get_health_risk_level(row['MP1'])
                    }
                    sensor_details.append(
                        create_sensor_detail_card(row['Sensor_ID'], sensor_stats)
                    )
            
            sensor_details_grid = create_status_grid(sensor_details, columns=3)
            
            # Last update
            last_update = f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return status_cards, sensor_details_grid, last_update
            
        except Exception as e:
            logging.error(f"Error updating general overview: {e}")
            error_msg = create_error_message("Update Error", "Unable to refresh dashboard data.")
            return error_msg, [], "Last updated: Error occurred"

    @app.callback(
        [Output('time-series-plot', 'figure'),
         Output('sensor-comparison-plot', 'figure')],
        Input('interval-component', 'n_intervals')
    )
    def update_general_plots(n):
        """
        Update general overview plots
        
        Args:
            n (int): Number of intervals elapsed
            
        Returns:
            tuple: Time series plot, sensor comparison plot
        """
        try:
            time_series_fig = create_time_series_plot()
            comparison_fig = create_sensor_comparison_plot()
            
            return time_series_fig, comparison_fig
            
        except Exception as e:
            logging.error(f"Error updating general plots: {e}")
            from dashboard.components import create_empty_plot
            error_plot = create_empty_plot("Error loading plot data")
            return error_plot, error_plot

    @app.callback(
        [Output('sensor-stats-cards', 'children'),
         Output('sensor-detailed-plot', 'figure'),
         Output('sensor-last-update', 'children')],
        [Input('sensor-dropdown', 'value'),
         Input('date-picker-range', 'start_date'),
         Input('date-picker-range', 'end_date'),
         Input('interval-component', 'n_intervals')]
    )
    def update_specific_sensor_analysis(sensor_id, start_date, end_date, n):
        """
        Update specific sensor analysis tab
        
        Args:
            sensor_id (str): Selected sensor ID
            start_date (str): Start date for analysis
            end_date (str): End date for analysis
            n (int): Number of intervals elapsed
            
        Returns:
            tuple: Statistics cards, detailed plot, last update
        """
        try:
            if not sensor_id:
                no_sensor_msg = create_error_message("No Sensor Selected", 
                                                   "Please select a sensor from the dropdown.")
                from dashboard.components import create_empty_plot
                empty_plot = create_empty_plot("Please select a sensor")
                return no_sensor_msg, empty_plot, "No sensor selected"
            
            # Parse dates
            start_dt = parse_date(start_date) if start_date else None
            end_dt = parse_date(end_date) if end_date else None
            
            # Get sensor data
            sensor_data = get_sensor_data(sensor_id, start_dt, end_dt)
            
            if sensor_data.empty:
                no_data_msg = create_error_message("No Data Available", 
                                                 f"No data found for sensor {sensor_id} in the selected period.")
                from dashboard.components import create_empty_plot
                empty_plot = create_empty_plot(f"No data for sensor {sensor_id}")
                return no_data_msg, empty_plot, "No data available"
            
            # Calculate statistics
            mp1_values = sensor_data['MP1'] if 'MP1' in sensor_data.columns else []
            
            if len(mp1_values) > 0:
                avg_mp1 = mp1_values.mean()
                max_mp1 = mp1_values.max()
                min_mp1 = mp1_values.min()
                std_mp1 = mp1_values.std()
                data_points = len(mp1_values)
                hours_of_data = (sensor_data.index.max() - sensor_data.index.min()).total_seconds() / 3600 if len(sensor_data) > 1 else 0
            else:
                avg_mp1 = max_mp1 = min_mp1 = std_mp1 = 0
                data_points = 0
                hours_of_data = 0
            
            # Create statistics cards
            stats_cards = create_status_grid([
                create_stat_card("Average", f"{avg_mp1:.2f} μg/m³", "Mean MP1.0 level", '#3498db'),
                create_stat_card("Maximum", f"{max_mp1:.2f} μg/m³", "Peak level recorded", '#e74c3c'),
                create_stat_card("Minimum", f"{min_mp1:.2f} μg/m³", "Lowest level recorded", '#2ecc71'),
                create_stat_card("Std Dev", f"{std_mp1:.2f} μg/m³", "Variation measure", '#f39c12'),
                create_stat_card("Data Points", str(data_points), "Total measurements", '#9b59b6'),
                create_stat_card("Hours of Data", f"{hours_of_data:.1f}h", "Time span covered", '#1abc9c')
            ], columns=6)
            
            # Create detailed plot
            detailed_plot = create_sensor_detailed_plot(sensor_id, start_dt, end_dt)
            
            # Last update
            last_update = f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Sensor: {sensor_id}"
            
            return stats_cards, detailed_plot, last_update
            
        except Exception as e:
            logging.error(f"Error updating specific sensor analysis: {e}")
            error_msg = create_error_message("Analysis Error", "Unable to analyze sensor data.")
            from dashboard.components import create_empty_plot
            error_plot = create_empty_plot("Error analyzing sensor data")
            return error_msg, error_plot, "Error occurred"


def get_health_risk_level(mp1_value):
    """
    Determine health risk level based on MP1.0 value
    
    Args:
        mp1_value (float): MP1.0 concentration value
        
    Returns:
        str: Health risk level
    """
    try:
        if mp1_value <= WHO_GUIDELINES['good_max']:
            return 'Good'
        elif mp1_value <= WHO_GUIDELINES['moderate_max']:
            return 'Moderate'
        elif mp1_value <= WHO_GUIDELINES['unhealthy_sensitive_max']:
            return 'Unhealthy for Sensitive Groups'
        elif mp1_value <= WHO_GUIDELINES['unhealthy_max']:
            return 'Unhealthy'
        elif mp1_value <= WHO_GUIDELINES['very_unhealthy_max']:
            return 'Very Unhealthy'
        else:
            return 'Hazardous'
    except Exception:
        return 'Unknown'


def get_air_quality_category(mp1_value):
    """
    Get air quality category and color based on MP1.0 value
    
    Args:
        mp1_value (float): MP1.0 concentration value
        
    Returns:
        tuple: (category, color)
    """
    try:
        if mp1_value <= WHO_GUIDELINES['good_max']:
            return 'Good', '#2ecc71'
        elif mp1_value <= WHO_GUIDELINES['moderate_max']:
            return 'Moderate', '#f39c12'
        elif mp1_value <= WHO_GUIDELINES['unhealthy_sensitive_max']:
            return 'Unhealthy for Sensitive Groups', '#e67e22'
        elif mp1_value <= WHO_GUIDELINES['unhealthy_max']:
            return 'Unhealthy', '#e74c3c'
        elif mp1_value <= WHO_GUIDELINES['very_unhealthy_max']:
            return 'Very Unhealthy', '#8e44ad'
        else:
            return 'Hazardous', '#c0392b'
    except Exception:
        return 'Unknown', '#95a5a6' 