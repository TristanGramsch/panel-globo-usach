#!/usr/bin/env python3
"""
Sistema de Monitoreo Ambiental USACH - Aplicación Principal
Punto de entrada unificado que maneja la obtención de datos y visualización del panel con interfaz de pestañas
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
    DASHBOARD_TITLE, WHO_GUIDELINES, ERROR_MESSAGES
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
        """Hilo en segundo plano para obtener datos periódicamente"""
        while True:
            try:
                logger.info("Iniciando obtención de datos en segundo plano...")
                
                # Check server health first
                if self.fetcher.check_server_health():
                    result = self.fetcher.run_fetch_cycle()
                    self.last_fetch = datetime.now()
                    logger.info(f"Obtención en segundo plano completada: {result}")
                else:
                    logger.warning("Verificación de salud del servidor falló, omitiendo obtención")
                
            except Exception as e:
                logger.error(f"Error en obtención de datos en segundo plano: {e}")
            
            # Wait for next fetch cycle
            time.sleep(self.data_fetch_interval)
    
    def start_background_fetcher(self):
        """Iniciar el hilo de obtención de datos en segundo plano"""
        # Initial fetch
        try:
            logger.info("Realizando obtención inicial de datos...")
            if self.fetcher.check_server_health():
                result = self.fetcher.run_fetch_cycle()
                self.last_fetch = datetime.now()
                logger.info(f"Obtención inicial completada: {result}")
            else:
                logger.warning("Servidor no disponible para obtención inicial")
        except Exception as e:
            logger.error(f"Error en obtención inicial de datos: {e}")
        
        # Start background thread
        fetch_thread = threading.Thread(target=self.fetch_data_background, daemon=True)
        fetch_thread.start()
        logger.info("Iniciador de datos en segundo plano activado")
    
    def get_sensor_status_today(self):
        """Obtener estado de sensores de hoy (funcionando vs no funcionando)"""
        try:
            today = datetime.now().date()
            available_sensors = get_available_sensors()
            sensor_status = {"working": [], "not_working": []}
            
            # Ensure available_sensors is a list
            if not isinstance(available_sensors, list):
                logger.error(f"get_available_sensors returned {type(available_sensors)}: {available_sensors}")
                return sensor_status
            
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
                    logger.warning(f"Error verificando estado del sensor {sensor_id}: {e}")
                    sensor_status["not_working"].append(sensor_id)
            
            return sensor_status
        except Exception as e:
            logger.error(f"Error en get_sensor_status_today: {e}")
            return {"working": [], "not_working": []}
    
    def create_status_cards(self):
        """Crear tarjetas de estado para el panel"""
        try:
            current_data = get_current_data()
            sensor_status = self.get_sensor_status_today()
            
            if current_data.empty:
                return html.Div([
                    html.Div([
                        html.H2("No Hay Datos Disponibles", style={'color': '#e74c3c', 'textAlign': 'center'}),
                        html.P("Ejecute 'python fetch_piloto_files.py' para descargar datos", 
                               style={'textAlign': 'center', 'color': '#7f8c8d'})
                    ], style={
                        'background': '#ecf0f1',
                        'padding': '40px',
                        'borderRadius': '10px',
                        'textAlign': 'center',
                        'border': '2px dashed #bdc3c7'
                    })
                ])
            
            # Calculate statistics safely
            try:
                avg_mp1 = current_data['MP1'].mean()
                max_mp1 = current_data['MP1'].max()
            except Exception as e:
                logger.error(f"Error calculando estadísticas MP1: {e}")
                avg_mp1 = 0
                max_mp1 = 0
            
            # Safe access to sensor status
            available_sensors = get_available_sensors()
            total_sensors = len(available_sensors) if isinstance(available_sensors, list) else 0
            working_today = len(sensor_status.get("working", [])) if isinstance(sensor_status, dict) else 0
            
            # Get air quality category
            category, color, risk = get_air_quality_category(avg_mp1)
            
            # Safe division to avoid errors
            operational_pct = (working_today / total_sensors * 100) if total_sensors > 0 else 0
            
            return html.Div([
                html.Div([
                    html.Div([
                        html.H3(f"{avg_mp1:.1f} μg/m³", style={'margin': '0', 'color': color}),
                        html.P("MP1.0 Promedio", style={'margin': '5px 0', 'color': '#7f8c8d'}),
                        html.Small(f"{category}", style={"color": color, "fontWeight": "bold"})
                    ], style={'textAlign': 'center', 'padding': '20px', 'background': '#fff', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 'margin': '10px'}),
                    
                    html.Div([
                        html.H3(f"{max_mp1:.1f} μg/m³", style={'margin': '0', 'color': '#e74c3c'}),
                        html.P("MP1.0 Máximo", style={'margin': '5px 0', 'color': '#7f8c8d'}),
                        html.Small("Lectura más alta", style={'color': '#7f8c8d'})
                    ], style={'textAlign': 'center', 'padding': '20px', 'background': '#fff', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 'margin': '10px'}),
                    
                    html.Div([
                        html.H3(f"{working_today}/{total_sensors}", style={'margin': '0', 'color': '#27ae60'}),
                        html.P("Sensores Activos Hoy", style={'margin': '5px 0', 'color': '#7f8c8d'}),
                        html.Small(f"{operational_pct:.0f}% operacional", 
                                  style={'color': '#27ae60' if operational_pct > 80 else '#f39c12'})
                    ], style={'textAlign': 'center', 'padding': '20px', 'background': '#fff', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 'margin': '10px'}),
                    
                    html.Div([
                        html.H3(f"{self.last_fetch.strftime('%H:%M') if self.last_fetch else 'Desconocido'}", style={'margin': '0', 'color': '#3498db'}),
                        html.P("Última Actualización", style={'margin': '5px 0', 'color': '#7f8c8d'}),
                        html.Small(f"{self.last_fetch.strftime('%d/%m/%Y') if self.last_fetch else 'Nunca'}", style={'color': '#7f8c8d'})
                    ], style={'textAlign': 'center', 'padding': '20px', 'background': '#fff', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 'margin': '10px'})
                ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'space-around'})
            ])
        except Exception as e:
            logger.error(f"Error creando tarjetas de estado: {e}")
            return html.Div([
                html.H4("Error de Estado", style={'color': '#e74c3c'}),
                html.P(f"Error: {str(e)}")
            ])
    
    def create_general_overview_chart(self):
        """Crear gráfico de resumen general - Matching previous Spanish dashboard"""
        try:
            available_sensors = get_available_sensors()
            fig = go.Figure()
            
            if not available_sensors:
                fig.add_annotation(
                    text="No hay datos de sensores disponibles<br>Ejecute 'python fetch_piloto_files.py' para descargar datos",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font={'size': 16, 'color': '#7f8c8d'}
                )
                fig.update_layout(
                    title="Datos de Calidad del Aire - Resumen General",
                    xaxis={'visible': False},
                    yaxis={'visible': False},
                    plot_bgcolor='white'
                )
                return fig
            
            # Colors for different sensors
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            
            # Add data for each sensor
            for i, sensor_id in enumerate(available_sensors[:10]):  # Limit to 10 sensors
                sensor_data = get_sensor_data(sensor_id)
                if not sensor_data.empty:
                    fig.add_trace(go.Scatter(
                        x=sensor_data.index,
                        y=sensor_data['MP1'],
                        mode='lines+markers',
                        name=f'Sensor {sensor_id}',
                        line={'color': colors[i % len(colors)], 'width': 2},
                        marker={'size': 4}
                    ))
            
            # Add WHO reference lines (OMS in Spanish)
            fig.add_hline(y=15, line_dash="dash", line_color="green",
                         annotation_text="OMS Buena (15 μg/m³)")
            fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                         annotation_text="OMS Moderada (25 μg/m³)")
            fig.add_hline(y=35, line_dash="dash", line_color="red",
                         annotation_text="OMS Dañina (35 μg/m³)")
            
            fig.update_layout(
                title="Datos de Calidad del Aire - Resumen General",
                xaxis_title="Fecha",
                yaxis_title="MP1.0 (μg/m³)",
                hovermode='x unified',
                plot_bgcolor='white',
                height=500,
                margin={'l': 50, 'r': 50, 't': 60, 'b': 50}
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creando gráfico de resumen general: {e}")
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text=f"Error cargando datos: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return empty_fig
    
    def create_sensor_comparison_plot(self):
        """Crear gráfico de comparación de sensores - Like previous Spanish dashboard"""
        try:
            available_sensors = get_available_sensors()
            
            if not available_sensors:
                fig = go.Figure()
                fig.add_annotation(
                    text="No hay datos de sensores disponibles",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font={'size': 16, 'color': '#7f8c8d'}
                )
                fig.update_layout(
                    title="Comparación de Sensores",
                    xaxis={'visible': False},
                    yaxis={'visible': False},
                    plot_bgcolor='white'
                )
                return fig
            
            # Calculate daily averages for each sensor
            sensor_averages = {}
            for sensor_id in available_sensors:
                sensor_data = get_sensor_data(sensor_id)
                if not sensor_data.empty:
                    daily_avg = sensor_data.resample('D')['MP1'].mean()
                    sensor_averages[f'Sensor {sensor_id}'] = daily_avg
            
            if not sensor_averages:
                fig = go.Figure()
                fig.add_annotation(
                    text="No hay suficientes datos para comparación",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False
                )
                return fig
            
            # Create bar chart with latest averages
            latest_averages = []
            sensor_names = []
            colors = []
            
            for sensor_name, daily_data in sensor_averages.items():
                if not daily_data.empty:
                    latest_avg = daily_data.iloc[-1]
                    latest_averages.append(latest_avg)
                    sensor_names.append(sensor_name)
                    
                    # Color based on WHO guidelines
                    if latest_avg <= 15:
                        colors.append('#27ae60')  # Green
                    elif latest_avg <= 25:
                        colors.append('#f39c12')  # Orange
                    elif latest_avg <= 35:
                        colors.append('#e67e22')  # Dark orange
                    else:
                        colors.append('#e74c3c')  # Red
            
            fig = go.Figure([go.Bar(
                x=sensor_names,
                y=latest_averages,
                marker_color=colors,
                text=[f'{val:.1f}' for val in latest_averages],
                textposition='auto'
            )])
            
            # Add WHO reference lines
            fig.add_hline(y=15, line_dash="dash", line_color="green",
                         annotation_text="OMS Buena")
            fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                         annotation_text="OMS Moderada")
            fig.add_hline(y=35, line_dash="dash", line_color="red",
                         annotation_text="OMS Dañina")
            
            fig.update_layout(
                title="Comparación de Sensores - Promedios Más Recientes",
                xaxis_title="Sensores",
                yaxis_title="MP1.0 (μg/m³)",
                plot_bgcolor='white',
                height=400,
                margin={'l': 50, 'r': 50, 't': 60, 'b': 100}
            )
            
            # Rotate x-axis labels for better readability
            fig.update_xaxes(tickangle=45)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creando gráfico de comparación: {e}")
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text=f"Error: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            return empty_fig
    
    def create_sensor_specific_chart(self, sensor_id):
        """Crear gráfico específico de sensor - Spanish version"""
        try:
            if not sensor_id:
                fig = go.Figure()
                fig.add_annotation(
                    text="Seleccione un sensor para ver los datos",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font={'size': 16, 'color': '#7f8c8d'}
                )
                fig.update_layout(
                    title="Análisis de Sensor Específico",
                    xaxis={'visible': False},
                    yaxis={'visible': False},
                    plot_bgcolor='white'
                )
                return fig
            
            sensor_data = get_sensor_data(sensor_id)
            
            if sensor_data.empty:
                fig = go.Figure()
                fig.add_annotation(
                    text=f"No hay datos disponibles para el Sensor {sensor_id}",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font={'size': 16, 'color': '#e74c3c'}
                )
                fig.update_layout(
                    title=f"Sensor {sensor_id} - Sin Datos",
                    xaxis={'visible': False},
                    yaxis={'visible': False},
                    plot_bgcolor='white'
                )
                return fig
            
            fig = go.Figure()
            
            # Add main data trace
            fig.add_trace(go.Scatter(
                x=sensor_data.index,
                y=sensor_data['MP1'],
                mode='lines+markers',
                name=f'Sensor {sensor_id}',
                line={'color': '#1f77b4', 'width': 2},
                marker={'size': 4}
            ))
            
            # Add WHO reference lines (OMS in Spanish)
            fig.add_hline(y=15, line_dash="dash", line_color="green",
                         annotation_text="OMS Buena (15 μg/m³)")
            fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                         annotation_text="OMS Moderada (25 μg/m³)")
            fig.add_hline(y=35, line_dash="dash", line_color="red",
                         annotation_text="OMS Dañina (35 μg/m³)")
            
            # Add average line
            avg_value = sensor_data['MP1'].mean()
            fig.add_hline(y=avg_value, line_dash="dot", line_color="purple",
                         annotation_text=f"Promedio: {avg_value:.1f} μg/m³")
            
            fig.update_layout(
                title=f"Sensor {sensor_id} - Análisis Detallado",
                xaxis_title="Fecha",
                yaxis_title="MP1.0 (μg/m³)",
                hovermode='x unified',
                plot_bgcolor='white',
                height=500,
                margin={'l': 50, 'r': 50, 't': 60, 'b': 50}
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creando gráfico específico del sensor {sensor_id}: {e}")
            empty_fig = go.Figure()
            empty_fig.add_annotation(
                text=f"Error cargando sensor {sensor_id}: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            empty_fig.update_layout(title=f"Error - Sensor {sensor_id}")
            return empty_fig
    
    def create_sensor_health_overview(self):
        """Crear resumen de salud de sensores con estado detallado"""
        available_sensors = get_available_sensors()
        sensor_status = self.get_sensor_status_today()
        
        # Create detailed sensor analysis
        sensor_details = []
        
        for sensor_id in available_sensors:
            try:
                sensor_data = get_sensor_data(sensor_id)
                
                detail = {
                    'Sensor_ID': sensor_id,
                    'Status': 'Funcionando' if sensor_id in sensor_status['working'] else 'No Funcionando',
                    'Data_Points_Today': 0,
                    'Last_Reading': 'Nunca',
                    'Average_MP1': 0,
                    'Data_Quality': 'Sin Datos'
                }
                
                if not sensor_data.empty:
                    # Check today's data
                    today = datetime.now().date()
                    today_data = sensor_data[sensor_data.index.date == today] if hasattr(sensor_data.index, 'date') else pd.DataFrame()
                    
                    detail['Data_Points_Today'] = len(today_data)
                    detail['Last_Reading'] = sensor_data.index[-1].strftime('%d/%m/%Y %H:%M')
                    detail['Average_MP1'] = sensor_data['MP1'].mean()
                    
                    # Determine data quality
                    if len(today_data) > 100:
                        detail['Data_Quality'] = 'Excelente'
                    elif len(today_data) > 50:
                        detail['Data_Quality'] = 'Buena'
                    elif len(today_data) > 10:
                        detail['Data_Quality'] = 'Regular'
                    elif len(today_data) > 0:
                        detail['Data_Quality'] = 'Pobre'
                
                sensor_details.append(detail)
                
            except Exception as e:
                logger.error(f"Error analizando sensor {sensor_id}: {e}")
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
                    html.Th("ID Sensor"),
                    html.Th("Estado"),
                    html.Th("Puntos de Datos Hoy"),
                    html.Th("Última Lectura"),
                    html.Th("MP1.0 Promedio (μg/m³)"),
                    html.Th("Calidad de Datos")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(f"Sensor {detail['Sensor_ID']}"),
                    html.Td(detail['Status'], 
                            style={'color': 'green' if detail['Status'] == 'Funcionando' else 'red'}),
                    html.Td(str(detail['Data_Points_Today'])),
                    html.Td(detail['Last_Reading']),
                    html.Td(f"{detail['Average_MP1']:.1f}" if detail['Average_MP1'] > 0 else "N/A"),
                    html.Td(detail['Data_Quality'])
                ]) for detail in sensor_details
            ])
        ], style={'width': '100%', 'border': '1px solid #ddd', 'borderCollapse': 'collapse'})
        
        return html.Div([
            html.H4("Resumen de Salud de Sensores"),
            html.P(f"Total de Sensores: {len(available_sensors)} | Funcionando Hoy: {len(sensor_status['working'])} | No Funcionando: {len(sensor_status['not_working'])}"),
            health_table
        ])
    
    def setup_layout(self):
        """Configurar diseño del panel con pestañas"""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1("Sistema de Monitoreo Ambiental USACH", style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': '30px'}),
                html.Hr()
            ]),
            
            # Status cards (always visible)
            html.Div(id="status-cards", style={'margin': '20px 0'}),
            
            # Tabs
            dcc.Tabs(id="main-tabs", value="tab-general", children=[
                dcc.Tab(label="Resumen General", value="tab-general", style={'padding': '10px'}),
                dcc.Tab(label="Análisis de Sensor Específico", value="tab-sensor", style={'padding': '10px'}),
                dcc.Tab(label="Salud de Sensores", value="tab-health", style={'padding': '10px'})
            ], style={'marginBottom': '20px'}),
            
            # Tab contents
            html.Div(id="tab-content", style={'margin': '20px 0'}),
            
            # Footer
            html.Div([
                html.P(id='last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
                html.P("El panel se actualiza automáticamente cada 10 minutos", 
                       style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
            ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'}),
            
            # Auto-refresh component
            dcc.Interval(
                id='interval-component',
                interval=AUTO_REFRESH_INTERVAL,  # 10 minutes
                n_intervals=0
            )
        ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px', 'fontFamily': 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'})
    
    def setup_callbacks(self):
        """Configurar callbacks del panel"""
        @self.app.callback(
            Output('status-cards', 'children'),
            [Input('interval-component', 'n_intervals')]
        )
        def update_status_cards(n):
            try:
                return self.create_status_cards()
            except Exception as e:
                logger.error(f"Error actualizando tarjetas de estado: {e}")
                return html.Div([
                    html.H4("Error de Estado", style={'color': '#e74c3c'}),
                    html.P(f"Error: {str(e)}")
                ])
        
        @self.app.callback(
            [Output('tab-content', 'children'),
             Output('last-update', 'children')],
            [Input('main-tabs', 'value'),
             Input('interval-component', 'n_intervals')]
        )
        def update_tab_content(active_tab, n):
            """Actualizar contenido de pestañas - callback principal"""
            try:
                # Ensure we have valid inputs
                if active_tab is None:
                    active_tab = 'tab-general'
                if n is None:
                    n = 0
                
                last_update_text = f"Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                
                if active_tab == 'tab-general':
                    # Resumen General Tab - exactly like previous Spanish dashboard
                    content = html.Div([
                        # Gráficos
                        html.Div([
                            html.Div([
                                dcc.Graph(
                                    id='time-series-plot',
                                    figure=self.create_general_overview_chart()
                                )
                            ], style={'width': '100%', 'margin': '20px 0'}),
                            
                            html.Div([
                                dcc.Graph(
                                    id='sensor-comparison-plot',
                                    figure=self.create_sensor_comparison_plot()
                                )
                            ], style={'width': '100%', 'margin': '20px 0'})
                        ]),
                        
                        # Detalles de sensores para el tab general
                        self.create_general_sensor_details(),
                        
                        # Resumen de estado de sensores
                        html.Div([
                            html.H3("Estado de Sensores Hoy", style={'color': '#2c3e50'}),
                            self.create_sensor_status_summary()
                        ])
                    ])
                    return content, last_update_text
                
                elif active_tab == 'tab-sensor':
                    # Análisis de Sensor Específico Tab - exactly like previous Spanish dashboard
                    try:
                        available_sensors = get_available_sensors()
                        content = html.Div([
                            html.H3("Análisis de Sensor Específico", style={'color': '#2c3e50', 'marginBottom': '20px'}),
                            html.Div([
                                html.Label("Seleccionar Sensor:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                                dcc.Dropdown(
                                    id='sensor-dropdown',
                                    options=[{'label': f'Sensor {s}', 'value': s} for s in available_sensors],
                                    value=available_sensors[0] if available_sensors else None,
                                    placeholder="Elegir un sensor...",
                                    style={'marginBottom': '20px'}
                                )
                            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                            dcc.Graph(id="sensor-specific-chart"),
                            html.Div(id="sensor-specific-details")
                        ])
                        return content, last_update_text
                    except Exception as e:
                        logger.error(f"Error creando pestaña de sensor específico: {e}")
                        content = html.Div([
                            html.H3("Análisis de Sensor Específico", style={'color': '#2c3e50'}),
                            html.P(f"Error cargando sensores: {str(e)}", style={'color': '#e74c3c'})
                        ])
                        return content, last_update_text
                
                elif active_tab == 'tab-health':
                    # Salud de Sensores Tab - new tab for maintenance
                    try:
                        content = html.Div([
                            html.H3("Salud de Sensores y Resumen de Mantenimiento", style={'color': '#2c3e50'}),
                            html.P("Monitorear estado operacional de sensores y calidad de datos para planificación de mantenimiento"),
                            self.create_sensor_health_overview()
                        ])
                        return content, last_update_text
                    except Exception as e:
                        logger.error(f"Error creando pestaña de salud de sensores: {e}")
                        content = html.Div([
                            html.H3("Salud de Sensores", style={'color': '#2c3e50'}),
                            html.P(f"Error cargando salud de sensores: {str(e)}", style={'color': '#e74c3c'})
                        ])
                        return content, last_update_text
                
                else:
                    # Default fallback
                    content = html.Div([
                        html.H3("Panel no disponible", style={'color': '#e74c3c'}),
                        html.P("Pestaña no reconocida. Seleccione una pestaña válida.")
                    ])
                    return content, last_update_text
                
            except Exception as e:
                logger.error(f"Error crítico actualizando contenido de pestaña: {e}")
                error_content = html.Div([
                    html.H4("Error de Contenido de Pestaña", style={'color': '#e74c3c'}),
                    html.P(f"Error: {str(e)}")
                ])
                error_time = f"Error: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                return error_content, error_time
        
        @self.app.callback(
            [Output('sensor-specific-chart', 'figure'),
             Output('sensor-specific-details', 'children')],
            [Input('sensor-dropdown', 'value')]
        )
        def update_sensor_specific(selected_sensor):
            try:
                chart = self.create_sensor_specific_chart(selected_sensor)
                
                if selected_sensor:
                    sensor_data = get_sensor_data(selected_sensor)
                    if not sensor_data.empty:
                        avg_mp1 = sensor_data['MP1'].mean()
                        category, color, risk = get_air_quality_category(avg_mp1)
                        
                        details = html.Div([
                            html.H4(f"Detalles del Sensor {selected_sensor}", style={'color': '#2c3e50', 'marginTop': '20px'}),
                            html.Div([
                                html.P([html.Strong("Puntos de datos totales: "), f"{len(sensor_data)}"]),
                                html.P([html.Strong("Rango de fechas: "), f"{sensor_data.index.min().strftime('%d/%m/%Y')} a {sensor_data.index.max().strftime('%d/%m/%Y')}"]),
                                html.P([html.Strong("MP1.0 Promedio: "), f"{avg_mp1:.2f} μg/m³"]),
                                html.P([html.Strong("MP1.0 Máximo: "), f"{sensor_data['MP1'].max():.2f} μg/m³"]),
                                html.P([html.Strong("MP1.0 Mínimo: "), f"{sensor_data['MP1'].min():.2f} μg/m³"]),
                                html.P([html.Strong("Categoría OMS: "), html.Span(category, style={'color': color, 'fontWeight': 'bold'})]),
                                html.P([html.Strong("Evaluación de riesgo: "), risk])
                            ], style={'background': '#f8f9fa', 'padding': '15px', 'borderRadius': '5px', 'marginTop': '10px'})
                        ])
                    else:
                        details = html.P("No hay datos disponibles para este sensor")
                else:
                    details = html.P("Por favor seleccione un sensor")
                
                return chart, details
            except Exception as e:
                logger.error(f"Error actualizando sensor específico: {e}")
                empty_fig = go.Figure()
                empty_fig.add_annotation(text=f"Error: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
                return empty_fig, html.P(f"Error: {str(e)}")

    def create_general_sensor_details(self):
        """Crear detalles de sensores para el tab general"""
        try:
            current_data = get_current_data()
            
            if current_data.empty:
                return html.Div([
                    html.H3("Detalles de Sensores", style={'color': '#2c3e50'}),
                    html.P("No hay datos de sensores disponibles.", style={'color': '#7f8c8d', 'fontStyle': 'italic'})
                ])
            
            # Create sensor detail cards
            available_sensors = get_available_sensors()
            sensor_cards = []
            
            for sensor_id in available_sensors[:6]:  # Show first 6 sensors
                sensor_data = get_sensor_data(sensor_id)
                
                if not sensor_data.empty:
                    avg_mp1 = sensor_data['MP1'].mean()
                    latest_reading = sensor_data['MP1'].iloc[-1]
                    data_points = len(sensor_data)
                    category, color, risk = get_air_quality_category(avg_mp1)
                    
                    card = html.Div([
                        html.H4(f"Sensor {sensor_id}", style={'margin': '0 0 10px 0', 'color': '#2c3e50'}),
                        html.P(f"Última Lectura: {latest_reading:.1f} μg/m³", style={'margin': '5px 0'}),
                        html.P(f"Promedio: {avg_mp1:.1f} μg/m³", style={'margin': '5px 0'}),
                        html.P(f"Puntos de Datos: {data_points}", style={'margin': '5px 0'}),
                        html.P(f"Estado: {category}", style={'margin': '5px 0', 'color': color, 'fontWeight': 'bold'})
                    ], style={
                        'background': '#fff',
                        'padding': '15px',
                        'borderRadius': '8px',
                        'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                        'margin': '10px',
                        'width': '300px',
                        'display': 'inline-block',
                        'verticalAlign': 'top'
                    })
                    sensor_cards.append(card)
            
            return html.Div([
                html.H3("Detalles de Sensores", style={'color': '#2c3e50', 'marginBottom': '20px'}),
                html.Div(sensor_cards, style={'textAlign': 'center'})
            ])
        except Exception as e:
            logger.error(f"Error creando detalles de sensores generales: {e}")
            return html.Div("Error cargando detalles de sensores")

    def create_sensor_status_summary(self):
        """Crear resumen de estado de sensores"""
        try:
            sensor_status = self.get_sensor_status_today()
            return html.Div([
                html.Div([
                    html.H4(f"Funcionando Hoy ({len(sensor_status['working'])})", style={'color': '#27ae60'}),
                    html.P(", ".join([f"Sensor {s}" for s in sensor_status["working"]]) or "Ninguno"),
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '15px', 'background': '#d5f4e6', 'borderRadius': '5px', 'margin': '5px'}),
                
                html.Div([
                    html.H4(f"No Funcionando Hoy ({len(sensor_status['not_working'])})", style={'color': '#e74c3c'}),
                    html.P(", ".join([f"Sensor {s}" for s in sensor_status["not_working"]]) or "Ninguno"),
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '15px', 'background': '#fadbd8', 'borderRadius': '5px', 'margin': '5px'})
            ])
        except Exception as e:
            logger.error(f"Error creando resumen de estado de sensores: {e}")
            return html.Div("Error cargando estado de sensores")
    
    def run(self):
        """Ejecutar la aplicación del panel"""
        logger.info(f"Iniciando Panel de Monitoreo Ambiental USACH en puerto {DEFAULT_PORT}")
        logger.info(f"Panel se auto-actualizará cada {AUTO_REFRESH_INTERVAL/1000/60:.0f} minutos")
        logger.info(f"Obtención de datos se ejecuta cada {self.data_fetch_interval/60:.0f} minutos en segundo plano")
        
        self.app.run(
            debug=DEBUG_MODE,
            host='0.0.0.0',
            port=DEFAULT_PORT
        )

def main():
    """Punto de entrada principal"""
    try:
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Create and run the app
        app = USACHMonitoringApp()
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Aplicación detenida por el usuario")
    except Exception as e:
        logger.error(f"Error de aplicación: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 