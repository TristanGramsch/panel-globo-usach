#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Dash Dashboard
Interactive web dashboard for real-time air quality monitoring
"""

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import os
import glob
from datetime import datetime
from pathlib import Path
from analyze_mp1_data import analyze_current_data, parse_piloto_file

# Initialize the Dash app
app = dash.Dash(__name__)
app.title = "USACH Air Quality Monitor"

def get_air_quality_category(avg_mp1):
    """Get air quality category and color based on WHO guidelines"""
    if avg_mp1 <= 15:
        return "Good", "#27ae60", "Very low health risk"
    elif avg_mp1 <= 25:
        return "Moderate", "#f39c12", "Low health risk"
    elif avg_mp1 <= 35:
        return "Unhealthy for Sensitive", "#e67e22", "Moderate health risk"
    elif avg_mp1 <= 75:
        return "Unhealthy", "#e74c3c", "High health risk"
    else:
        return "Very Unhealthy", "#8e44ad", "Very high health risk"

def get_current_data():
    """Get current air quality data for dashboard"""
    try:
        # Try to import the analysis function
        from analyze_mp1_data import analyze_current_data
        
        result = analyze_current_data()
        if result is None:
            print("Warning: analyze_current_data returned None")
            return None, None
        
        combined_df, sensor_summaries = result
        
        # Validate the data
        if combined_df is None or len(combined_df) == 0:
            print("Warning: No data in combined_df")
            return None, None
            
        if sensor_summaries is None or len(sensor_summaries) == 0:
            print("Warning: No sensor summaries available")
            return None, None
            
        return combined_df, sensor_summaries
        
    except ImportError as e:
        print(f"Import error in get_current_data: {e}")
        print("Make sure analyze_mp1_data.py is available and working")
        return None, None
    except Exception as e:
        print(f"Error getting current data: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def create_time_series_plot():
    """Create time series plot of MP1.0 levels"""
    data_dir = Path('piloto_data')
    if not data_dir.exists():
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    all_data = []
    
    for file_path in data_dir.glob("*.dat"):
        if file_path.stat().st_size == 0:
            continue
            
        sensor_id = file_path.name.split('-')[0].replace('Piloto', '')
        df = parse_piloto_file(file_path)
        
        if df is not None and len(df) > 0:
            df['sensor_id'] = sensor_id
            all_data.append(df)
    
    if not all_data:
        return go.Figure().add_annotation(text="No valid data found", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set1
    
    for i, df in enumerate(all_data):
        sensor_id = df['sensor_id'].iloc[0]
        fig.add_trace(go.Scatter(
            x=df['datetime'],
            y=df['MP1.0'],
            mode='lines',
            name=f'Sensor {sensor_id}',
            line=dict(color=colors[i % len(colors)]),
            hovertemplate='<b>Sensor %{fullData.name}</b><br>' +
                         'Time: %{x}<br>' +
                         'MP1.0: %{y:.1f} μg/m³<extra></extra>'
        ))
    
    # Add WHO guideline lines
    fig.add_hline(y=15, line_dash="dash", line_color="green", 
                  annotation_text="WHO Good (≤15)")
    fig.add_hline(y=25, line_dash="dash", line_color="yellow", 
                  annotation_text="WHO Moderate (≤25)")
    fig.add_hline(y=35, line_dash="dash", line_color="orange", 
                  annotation_text="WHO Unhealthy Sensitive (≤35)")
    fig.add_hline(y=75, line_dash="dash", line_color="red", 
                  annotation_text="WHO Unhealthy (≤75)")
    
    fig.update_layout(
        title="MP1.0 Levels Over Time",
        xaxis_title="Time",
        yaxis_title="MP1.0 (μg/m³)",
        hovermode='x unified',
        showlegend=True,
        height=500
    )
    
    return fig

def create_sensor_comparison_plot():
    """Create bar chart comparing average MP1.0 levels by sensor"""
    combined_df, sensor_summaries = get_current_data()
    
    if sensor_summaries is None:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    # Prepare data for bar chart
    sensor_ids = []
    avg_values = []
    colors = []
    
    for sensor_id, stats in sensor_summaries.items():
        avg_mp1 = stats['mean_mp1']
        _, color, _ = get_air_quality_category(avg_mp1)
        
        sensor_ids.append(f'Sensor {sensor_id}')
        avg_values.append(avg_mp1)
        colors.append(color)
    
    # Sort by average value (highest first)
    sorted_data = sorted(zip(sensor_ids, avg_values, colors), key=lambda x: x[1], reverse=True)
    sensor_ids, avg_values, colors = zip(*sorted_data)
    
    fig = go.Figure(data=[
        go.Bar(
            x=list(sensor_ids),
            y=list(avg_values),
            marker_color=list(colors),
            hovertemplate='<b>%{x}</b><br>' +
                         'Average MP1.0: %{y:.1f} μg/m³<extra></extra>'
        )
    ])
    
    # Add WHO guideline lines
    fig.add_hline(y=15, line_dash="dash", line_color="green", opacity=0.7)
    fig.add_hline(y=25, line_dash="dash", line_color="yellow", opacity=0.7)
    fig.add_hline(y=35, line_dash="dash", line_color="orange", opacity=0.7)
    fig.add_hline(y=75, line_dash="dash", line_color="red", opacity=0.7)
    
    fig.update_layout(
        title="Average MP1.0 Levels by Sensor",
        xaxis_title="Sensor",
        yaxis_title="Average MP1.0 (μg/m³)",
        height=400,
        showlegend=False
    )
    
    return fig

def get_dashboard_stats():
    """Get summary statistics for dashboard cards"""
    try:
        combined_df, sensor_summaries = get_current_data()
        
        if combined_df is None or sensor_summaries is None or len(combined_df) == 0:
            return {
                'total_sensors': 0,
                'avg_mp1': 0,
                'max_mp1': 0,
                'total_points': 0,
                'overall_category': 'No Data',
                'overall_color': '#7f8c8d',
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'no_data'
            }
        
        overall_avg = combined_df['MP1.0'].mean()
        overall_category, overall_color, _ = get_air_quality_category(overall_avg)
        
        return {
            'total_sensors': len(sensor_summaries),
            'avg_mp1': round(overall_avg, 1),
            'max_mp1': round(combined_df['MP1.0'].max(), 1),
            'total_points': len(combined_df),
            'overall_category': overall_category,
            'overall_color': overall_color,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'ok'
        }
    except Exception as e:
        print(f"Error in get_dashboard_stats: {e}")
        return {
            'total_sensors': 0,
            'avg_mp1': 0,
            'max_mp1': 0,
            'total_points': 0,
            'overall_category': 'Error',
            'overall_color': '#e74c3c',
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'error'
        }

def get_health_recommendations(avg_mp1):
    """Get health recommendations based on air quality level"""
    if avg_mp1 <= 15:
        return [
            "✅ Air quality is satisfactory",
            "✅ Ideal for all outdoor activities",
            "✅ No health concerns for any group"
        ]
    elif avg_mp1 <= 25:
        return [
            "⚠️ Air quality is acceptable for most people",
            "⚠️ Sensitive individuals may experience minor symptoms",
            "💡 Consider reducing prolonged outdoor exertion"
        ]
    elif avg_mp1 <= 35:
        return [
            "🟠 Sensitive groups should limit outdoor activities",
            "🟠 Children and elderly should reduce outdoor time",
            "😷 Consider wearing masks during outdoor activities"
        ]
    elif avg_mp1 <= 75:
        return [
            "🔴 Everyone should limit outdoor activities",
            "🚫 Avoid prolonged outdoor exertion",
            "🏠 Keep windows closed and use air purifiers"
        ]
    else:
        return [
            "🚨 Avoid all outdoor activities",
            "🏠 Stay indoors with windows closed",
            "😷 Use air purifiers and masks if going outside"
        ]

# Define the layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("🌍 USACH Air Quality Monitor", 
                style={'textAlign': 'center', 'color': 'white', 'margin': '0'}),
        html.P("Real-time Environmental Data Dashboard", 
               style={'textAlign': 'center', 'color': 'white', 'opacity': '0.8', 'margin': '10px 0 0 0'})
    ], style={
        'background': 'linear-gradient(135deg, #2c3e50 0%, #34495e 100%)',
        'padding': '30px',
        'marginBottom': '0'
    }),
    
    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=5*60*1000,  # 5 minutes in milliseconds
        n_intervals=0
    ),
    
    # Main content
    html.Div([
        # Status cards
        html.Div(id='status-cards', style={'margin': '20px 0'}),
        
        # Health recommendations
        html.Div(id='health-recommendations', style={'margin': '20px 0'}),
        
        # Charts
        html.Div([
            html.Div([
                dcc.Graph(id='time-series-plot')
            ], style={'width': '100%', 'margin': '20px 0'}),
            
            html.Div([
                dcc.Graph(id='sensor-comparison-plot')
            ], style={'width': '100%', 'margin': '20px 0'})
        ]),
        
        # Sensor details
        html.Div(id='sensor-details', style={'margin': '20px 0'}),
        
        # Footer
        html.Div([
            html.P(id='last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("💡 Dashboard auto-refreshes every 5 minutes", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
        
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px'})
], style={'fontFamily': 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'})

# Callbacks for dynamic updates
@app.callback(
    [Output('status-cards', 'children'),
     Output('health-recommendations', 'children'),
     Output('time-series-plot', 'figure'),
     Output('sensor-comparison-plot', 'figure'),
     Output('sensor-details', 'children'),
     Output('last-update', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    try:
        stats = get_dashboard_stats()
        
        # Handle no data case
        if stats.get('status') == 'no_data':
            # Status cards for no data
            status_cards = html.Div([
                html.Div([
                    html.H2("No Data Available", style={'color': '#e74c3c', 'textAlign': 'center'}),
                    html.P("Run 'python fetch_piloto_files.py' to download data", 
                           style={'textAlign': 'center', 'color': '#7f8c8d'})
                ], style={
                    'background': '#ecf0f1',
                    'padding': '40px',
                    'borderRadius': '10px',
                    'textAlign': 'center',
                    'border': '2px dashed #bdc3c7'
                })
            ])
            
            # Empty recommendations
            health_recs = html.Div([
                html.H3("📋 Health Recommendations", style={'color': '#2c3e50'}),
                html.P("No air quality data available to provide recommendations.", 
                       style={'color': '#7f8c8d', 'fontStyle': 'italic'})
            ], style={
                'background': '#f8f9fa',
                'borderLeft': '4px solid #6c757d',
                'padding': '20px',
                'borderRadius': '5px'
            })
            
            # Empty plots
            empty_fig = go.Figure().add_annotation(
                text="No data available<br>Run 'python fetch_piloto_files.py' to download data",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#7f8c8d")
            )
            empty_fig.update_layout(
                title="Waiting for Data...",
                height=400
            )
            
            sensor_details = html.Div([
                html.H2("📊 Sensor Details", style={'color': '#2c3e50'}),
                html.P("No sensor data available.", style={'color': '#7f8c8d', 'fontStyle': 'italic'})
            ])
            
            last_update = f"Last checked: {stats['last_update']}"
            
            return status_cards, health_recs, empty_fig, empty_fig, sensor_details, last_update
        
        # Handle error case
        if stats.get('status') == 'error':
            error_msg = html.Div([
                html.H2("⚠️ Data Error", style={'color': '#e74c3c', 'textAlign': 'center'}),
                html.P("There was an error processing the air quality data. Please check the logs.", 
                       style={'textAlign': 'center', 'color': '#7f8c8d'})
            ], style={
                'background': '#f8d7da',
                'border': '1px solid #f5c6cb',
                'color': '#721c24',
                'padding': '20px',
                'borderRadius': '5px',
                'textAlign': 'center'
            })
            
            empty_fig = go.Figure().add_annotation(
                text="Error processing data",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#e74c3c")
            )
            
            return error_msg, error_msg, empty_fig, empty_fig, error_msg, f"Error at: {stats['last_update']}"
        
        # Normal case with data
        # Status cards
        status_cards = html.Div([
            html.Div([
                html.Div([
                    html.H2(str(stats['total_sensors']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Active Sensors", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['avg_mp1']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Avg MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['max_mp1']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Max MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['total_points']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Total Data Points", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card')
            ], style={
                'display': 'grid',
                'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))',
                'gap': '20px',
                'margin': '20px 0'
            }),
            
            # Overall status
            html.Div([
                html.H3(f"Overall Air Quality: {stats['overall_category']}", 
                        style={'color': 'white', 'margin': '0', 'textAlign': 'center'})
            ], style={
                'background': stats['overall_color'],
                'padding': '20px',
                'borderRadius': '10px',
                'margin': '20px 0',
                'textAlign': 'center'
            })
        ])
        
        # Health recommendations
        recommendations = get_health_recommendations(stats['avg_mp1'])
        health_recs = html.Div([
            html.H3("📋 Health Recommendations", style={'color': '#2c3e50', 'marginTop': '0'}),
            html.Ul([html.Li(rec, style={'margin': '5px 0', 'color': '#34495e'}) for rec in recommendations])
        ], style={
            'background': '#e8f4fd',
            'borderLeft': '4px solid #3498db',
            'padding': '20px',
            'borderRadius': '5px',
            'margin': '20px 0'
        })
        
        # Create plots
        time_series_fig = create_time_series_plot()
        comparison_fig = create_sensor_comparison_plot()
        
        # Sensor details
        combined_df, sensor_summaries = get_current_data()
        sensor_details = html.Div()
        
        if sensor_summaries:
            sensor_cards = []
            for sensor_id, sensor_stats in sorted(sensor_summaries.items(), 
                                         key=lambda x: x[1]['mean_mp1'], reverse=True):
                avg_mp1 = sensor_stats['mean_mp1']
                category, color, risk = get_air_quality_category(avg_mp1)
                
                card = html.Div([
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
                
                sensor_cards.append(card)
            
            sensor_details = html.Div([
                html.H2("📊 Sensor Details", style={'color': '#2c3e50'}),
                html.Div(sensor_cards, style={
                    'display': 'grid',
                    'gridTemplateColumns': 'repeat(auto-fill, minmax(400px, 1fr))',
                    'gap': '20px'
                })
            ])
        
        last_update = f"Last updated: {stats['last_update']}"
        
        return status_cards, health_recs, time_series_fig, comparison_fig, sensor_details, last_update
    
    except Exception as e:
        print(f"Error in update_dashboard callback: {e}")
        import traceback
        traceback.print_exc()
        
        # Return error state
        error_msg = html.Div([
            html.H2("⚠️ Dashboard Error", style={'color': '#e74c3c', 'textAlign': 'center'}),
            html.P(f"Error: {str(e)}", style={'textAlign': 'center', 'color': '#7f8c8d'})
        ], style={
            'background': '#f8d7da',
            'border': '1px solid #f5c6cb',
            'color': '#721c24',
            'padding': '20px',
            'borderRadius': '5px',
            'textAlign': 'center'
        })
        
        empty_fig = go.Figure().add_annotation(
            text=f"Dashboard Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="#e74c3c")
        )
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return error_msg, error_msg, empty_fig, empty_fig, error_msg, f"Error at: {current_time}"

# Add CSS styles
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

if __name__ == "__main__":
    print("🌐 Starting USACH Air Quality Dash Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8050")
    print("💡 Tip: Run 'python fetch_piloto_files.py' first to ensure you have data!")
    print("🔄 Dashboard auto-refreshes every 5 minutes")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=8050)