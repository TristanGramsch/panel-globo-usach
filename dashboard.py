#!/usr/bin/env python3
"""
USACH Monitoreo Ambiental - Panel de Control Dash
Panel web interactivo para monitoreo de calidad del aire en tiempo real
"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import os
import glob
import threading
import time
import atexit
from datetime import datetime, timedelta
from pathlib import Path
import logging
from config.logging_config import (
    get_dashboard_logger, 
    setup_all_loggers,
    log_performance_metric
)
from apscheduler.schedulers.background import BackgroundScheduler

# Importar desde nuestra estructura modular
from data.processors import get_current_data, parse_piloto_file, get_sensor_data as get_sensor_data_processor
from data.fetch_piloto_files import fetch_and_update_data
from config.settings import (
    WHO_GUIDELINES, get_chile_time, format_chile_time, get_chile_date,
    get_data_status, get_data_freshness, DATA_FETCH_INTERVAL_MINUTES,
    CHILE_TIMEZONE, DATA_DIR, 
    get_developer_metrics, get_log_statistics, get_system_performance, 
    get_background_process_status, calculate_system_health_score, 
    get_recent_log_entries, DASHBOARD_PORT
)
from utils.helpers import get_air_quality_category

# Global variable to control background thread
background_fetcher_running = False
background_thread = None

# Set port and timezone
PORT = DASHBOARD_PORT
TIMEZONE = CHILE_TIMEZONE

def start_background_fetcher():
    """Start the background data fetching service"""
    logger = get_dashboard_logger()
    logger.info("Iniciando servicio de descarga en segundo plano")
    
    def initial_fetch():
        """Perform initial data fetch"""
        try:
            logger.info("Ejecutando descarga inicial de datos")
            start_time = get_chile_time()
            result = fetch_and_update_data()
            duration = (get_chile_time() - start_time).total_seconds()
            
            log_performance_metric(logger, "Initial data fetch", duration, {
                'success': result,
                'timestamp': start_time.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error en descarga inicial: {e}", exc_info=True)

    def scheduled_fetch():
        """Perform scheduled data fetch"""
        try:
            logger.info("Ejecutando descarga programada de datos")
            start_time = get_chile_time()
            result = fetch_and_update_data()
            duration = (get_chile_time() - start_time).total_seconds()
            
            log_performance_metric(logger, "Scheduled data fetch", duration, {
                'success': result,
                'timestamp': start_time.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error en descarga programada: {e}", exc_info=True)

    # Perform initial fetch
    initial_fetch()
    
    # Schedule regular fetches
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        func=scheduled_fetch,
        trigger="interval",
        minutes=DATA_FETCH_INTERVAL_MINUTES,
        id='data_fetch'
    )
    scheduler.start()
    logger.info(f"Servicio de descarga iniciado (cada {DATA_FETCH_INTERVAL_MINUTES} minutos)")
    return scheduler

def stop_background_fetcher(scheduler):
    """Stop the background data fetching service"""
    logger = get_dashboard_logger()
    if scheduler:
        scheduler.shutdown()
        logger.info("Deteniendo servicio de descarga en segundo plano")

# Register cleanup function
atexit.register(stop_background_fetcher)

# Inicializar la aplicación Dash
app = dash.Dash(__name__)
app.title = "Monitor de Calidad del Aire USACH"
app.config.suppress_callback_exceptions = True

def get_air_quality_category(avg_mp1):
    """Obtener categoría de calidad del aire y color basado en directrices OMS"""
    if avg_mp1 <= 15:
        return "Buena", "#27ae60", "Riesgo para la salud muy bajo"
    elif avg_mp1 <= 25:
        return "Moderada", "#f39c12", "Riesgo para la salud bajo"
    elif avg_mp1 <= 35:
        return "Dañina para Grupos Sensibles", "#e67e22", "Riesgo para la salud moderado"
    elif avg_mp1 <= 75:
        return "Contaminación dañina", "#e74c3c", "Alto riesgo para la salud"
    else:
        return "Muy Dañina", "#8e44ad", "Riesgo para la salud muy alto"

def create_empty_plot(message, title="No Data Available"):
    """Crear un gráfico vacío con un mensaje"""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="#7f8c8d")
    )
    fig.update_layout(
        title=title,
        height=400,
        showlegend=False,
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False)
    )
    return fig

def get_sensor_color(sensor_id, available_sensors):
    """Obtener color consistente para un sensor basado en su posición en la lista de sensores disponibles"""
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#f1c40f', '#8e44ad']
    
    # Convertir a lista ordenada para consistencia
    sorted_sensors = sorted(available_sensors)
    
    try:
        sensor_index = sorted_sensors.index(sensor_id)
        return colors[sensor_index % len(colors)]
    except ValueError:
        # Si el sensor no está en la lista, usar el primer color
        return colors[0]

def get_available_sensors():
    """Obtener lista de sensores disponibles desde archivos de datos"""
    data_dir = Path('piloto_data')
    if not data_dir.exists():
        return []
    
    sensors = set()
    for file_path in data_dir.glob("*.dat"):
        if file_path.stat().st_size > 0:
            sensor_id = file_path.name.split('-')[0].replace('Piloto', '')
            sensors.add(sensor_id)
    
    return sorted(list(sensors))

def get_date_range():
    """Obtener rango de fechas disponible desde archivos de datos"""
    data_dir = Path('piloto_data')
    if not data_dir.exists():
        return None, None
    
    dates = []
    for file_path in data_dir.glob("*.dat"):
        if file_path.stat().st_size > 0:
            try:
                # Extraer fecha del nombre del archivo (ej., Piloto019-020625.dat)
                date_part = file_path.name.split('-')[1].replace('.dat', '')
                # Convertir DDMMYY a datetime
                day = int(date_part[:2])
                month = int(date_part[2:4])
                year = 2000 + int(date_part[4:6])
                date_obj = datetime(year, month, day)
                dates.append(date_obj)
            except:
                continue
    
    if not dates:
        return None, None
    
    return min(dates), max(dates)

def get_sensor_data(sensor_id, start_date=None, end_date=None):
    """Obtener datos para un sensor específico dentro del rango de fechas"""
    return get_sensor_data_processor(sensor_id, start_date, end_date)

def get_sensor_health_status():
    """
    Calculate sensor health status based on last data received
    Returns dict with health information
    """
    logger = get_dashboard_logger()
    
    try:
        start_time = get_chile_time()
        data_dir = Path('piloto_data')
        if not data_dir.exists():
            return {
                'status': 'no_data',
                'last_update': format_chile_time()
            }
        
        today = get_chile_time()
        yesterday = today - timedelta(days=1)
        
        # Obtener todos los sensores únicos
        all_sensors = set()
        sensor_health = {}
        
        for file_path in data_dir.glob("*.dat"):
            try:
                # Extraer sensor ID y fecha del nombre del archivo
                filename = file_path.name
                sensor_id = filename.split('-')[0].replace('Piloto', '')
                date_part = filename.split('-')[1].replace('.dat', '')
                
                # Convertir fecha DDMMYY a datetime
                day = int(date_part[:2])
                month = int(date_part[2:4])
                year = 2000 + int(date_part[4:6])
                file_date = datetime(year, month, day)
                
                all_sensors.add(sensor_id)
                
                if sensor_id not in sensor_health:
                    sensor_health[sensor_id] = {
                        'last_data_date': None,
                        'last_file_size': 0,
                        'total_files': 0,
                        'empty_files': 0,
                        'working_today': False,
                        'working_yesterday': False,
                        'status': 'unknown'
                    }
                
                sensor_health[sensor_id]['total_files'] += 1
                
                # Verificar si el archivo tiene datos
                file_size = file_path.stat().st_size
                if file_size == 0:
                    sensor_health[sensor_id]['empty_files'] += 1
                else:
                    # Actualizar última fecha con datos
                    if (sensor_health[sensor_id]['last_data_date'] is None or 
                        file_date > sensor_health[sensor_id]['last_data_date']):
                        sensor_health[sensor_id]['last_data_date'] = file_date
                        sensor_health[sensor_id]['last_file_size'] = file_size
                
                # Verificar si está funcionando hoy
                if file_date.date() == today.date() and file_size > 0:
                    sensor_health[sensor_id]['working_today'] = True
                
                # Verificar si funcionó ayer
                if file_date.date() == yesterday.date() and file_size > 0:
                    sensor_health[sensor_id]['working_yesterday'] = True
                    
            except (ValueError, IndexError) as e:
                continue
        
        # Determinar estado de cada sensor
        for sensor_id in sensor_health:
            health = sensor_health[sensor_id]
            
            if health['working_today']:
                health['status'] = 'healthy'
            elif health['working_yesterday']:
                health['status'] = 'warning'
            elif health['last_data_date'] is not None:
                # Verificar hace cuántos días tuvo datos
                days_since_data = (today.date() - health['last_data_date'].date()).days
                if days_since_data <= 3:
                    health['status'] = 'warning'
                else:
                    health['status'] = 'critical'
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_performance_metric(logger, "Sensor health calculation", duration, {
            'total_sensors': len(sensor_health),
            'healthy_count': sum(1 for h in sensor_health.values() if h['status'] == 'healthy'),
            'warning_count': sum(1 for h in sensor_health.values() if h['status'] == 'warning'),
            'critical_count': sum(1 for h in sensor_health.values() if h['status'] == 'critical')
        })
        
        return {
            'sensors': sensor_health,
            'total_sensors': len(all_sensors),
            'healthy_count': sum(1 for h in sensor_health.values() if h['status'] == 'healthy'),
            'warning_count': sum(1 for h in sensor_health.values() if h['status'] == 'warning'),
            'critical_count': sum(1 for h in sensor_health.values() if h['status'] == 'critical'),
            'last_update': format_chile_time()
        }
        
    except Exception as e:
        logger.error(f"Error in get_sensor_health_status: {e}", exc_info=True)
        return {
            'status': 'error',
            'error_message': str(e),
            'last_update': format_chile_time()
        }

def create_sensor_health_plot(health_data):
    """Crear gráfico de estado de salud de sensores"""
    try:
        if health_data['status'] != 'success':
            return create_empty_plot("Error obteniendo datos de salud de sensores")
        
        sensor_health = health_data['sensors']
        
        # Preparar datos para el gráfico
        sensors = []
        statuses = []
        colors = []
        last_dates = []
        
        status_colors = {
            'healthy': '#27ae60',    # Verde
            'warning': '#f39c12',    # Naranja
            'critical': '#e74c3c'    # Rojo
        }
        
        for sensor_id, health in sorted(sensor_health.items()):
            sensors.append(f'Sensor {sensor_id}')
            statuses.append(health['status'].title())
            colors.append(status_colors[health['status']])
            
            if health['last_data_date']:
                last_dates.append(health['last_data_date'].strftime('%Y-%m-%d'))
            else:
                last_dates.append('Sin datos')
        
        fig = go.Figure(data=[
            go.Bar(
                x=sensors,
                y=[1] * len(sensors),  # Altura uniforme
                marker_color=colors,
                text=statuses,
                textposition='inside',
                hovertemplate='<b>%{x}</b><br>' +
                              'Estado: %{text}<br>' +
                              'Últimos datos: %{customdata}<extra></extra>',
                customdata=last_dates
            )
        ])
        
        fig.update_layout(
            title="Estado de Salud de Sensores",
            xaxis_title="Sensores",
            yaxis_title="Estado",
            showlegend=False,
            height=400,
            yaxis=dict(showticklabels=False, showgrid=False),
            xaxis=dict(tickangle=45)
        )
        
        return fig
        
    except Exception as e:
        print(f"Error creando gráfico de salud: {e}")
        return create_empty_plot("Error creando gráfico de salud")

def create_time_series_plot():
    """Crear gráfico de series temporales para todos los sensores"""
    try:
        # Obtener datos actuales para verificar sensores disponibles
        current_data = get_current_data()
        if current_data.empty:
            return create_empty_plot("No hay datos disponibles")
        
        fig = go.Figure()
        
        # Obtener datos para cada sensor disponible
        available_sensors = current_data['Sensor_ID'].unique()
        
        for sensor_id in sorted(available_sensors):
            sensor_data = get_sensor_data_processor(sensor_id)
            if not sensor_data.empty:
                sensor_color = get_sensor_color(sensor_id, available_sensors)
                fig.add_trace(go.Scatter(
                    x=sensor_data.index,
                    y=sensor_data['MP1'],
                    mode='lines',
                    name=f'Sensor {sensor_id}',
                    line=dict(color=sensor_color),
                    hovertemplate='<b>Sensor %{fullData.name}</b><br>' +
                                  'Fecha: %{x}<br>' +
                                  'MP1.0: %{y:.1f} μg/m³<extra></extra>'
                ))
        
        fig.update_layout(
            title="Niveles de MP1.0 a lo largo del tiempo",
            xaxis_title="Fecha",
            yaxis_title="MP1.0 (μg/m³)",
            hovermode='x unified',
            showlegend=True,
            height=500
        )
        
        # Agregar líneas de referencia OMS
        fig.add_hline(y=15, line_dash="dash", line_color="green", 
                      annotation_text="OMS: Buena (15 μg/m³)")
        fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                      annotation_text="OMS: Moderada (25 μg/m³)")
        fig.add_hline(y=35, line_dash="dash", line_color="red", 
                      annotation_text="OMS: Dañina (35 μg/m³)")
        
        return fig
        
    except Exception as e:
        print(f"Error creando gráfico de series temporales: {e}")
        return create_empty_plot("Error al crear el gráfico")

def create_sensor_specific_plot(sensor_id, start_date=None, end_date=None):
    """Crear gráfico específico para un sensor con rango de fechas opcional"""
    try:
        if not sensor_id:
            return create_empty_plot("Seleccione un sensor")
        
        # Obtener datos del sensor
        sensor_data = get_sensor_data_processor(sensor_id)
        
        if sensor_data.empty:
            return create_empty_plot(f"No hay datos para el sensor {sensor_id}")
        
        # Filtrar por rango de fechas si se proporciona
        if start_date and end_date:
            mask = (sensor_data.index >= start_date) & (sensor_data.index <= end_date)
            sensor_data = sensor_data.loc[mask]
            
            if sensor_data.empty:
                return create_empty_plot(f"No hay datos para el sensor {sensor_id} en el rango seleccionado")
        
        fig = go.Figure()
        
        # Agregar datos del sensor
        fig.add_trace(go.Scatter(
            x=sensor_data.index,
            y=sensor_data['MP1'],
            mode='lines+markers',
            name=f'Sensor {sensor_id}',
            line=dict(color='#3498db'),
            marker=dict(size=4),
            hovertemplate='<b>Sensor %{fullData.name}</b><br>' +
                          'Fecha: %{x}<br>' +
                          'MP1.0: %{y:.1f} μg/m³<extra></extra>'
        ))
        
        # Agregar línea de promedio
        avg_mp1 = sensor_data['MP1'].mean()
        fig.add_hline(y=avg_mp1, line_dash="dot", line_color="purple", 
                      annotation_text=f"Promedio: {avg_mp1:.1f} μg/m³")
        
        fig.update_layout(
            title=f"Sensor {sensor_id} - Análisis Detallado de MP1.0",
            xaxis_title="Fecha",
            yaxis_title="MP1.0 (μg/m³)",
            hovermode='x unified',
            showlegend=True,
            height=500
        )
        
        # Agregar líneas de referencia OMS
        fig.add_hline(y=15, line_dash="dash", line_color="green", 
                      annotation_text="OMS: Buena")
        fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                      annotation_text="OMS: Moderada")
        fig.add_hline(y=35, line_dash="dash", line_color="red", 
                      annotation_text="OMS: Dañina")
        
        return fig
        
    except Exception as e:
        print(f"Error creando gráfico específico del sensor: {e}")
        return create_empty_plot("Error al crear el gráfico")

def create_sensor_comparison_plot():
    """Crear gráfico de comparación de sensores"""
    try:
        current_data = get_current_data()
        if current_data.empty:
            return create_empty_plot("No hay datos disponibles")
        
        # Agrupar por sensor y calcular promedio
        sensor_averages = current_data.groupby('Sensor_ID')['MP1'].mean().reset_index()
        sensor_averages = sensor_averages.sort_values('MP1', ascending=False)
        
        # Obtener sensores disponibles para colores consistentes
        available_sensors = current_data['Sensor_ID'].unique()
        
        # Crear lista de colores para cada sensor en el gráfico
        bar_colors = [get_sensor_color(sensor_id, available_sensors) for sensor_id in sensor_averages['Sensor_ID']]
        
        fig = go.Figure(data=[
            go.Bar(
                x=sensor_averages['Sensor_ID'],
                y=sensor_averages['MP1'],
                marker_color=bar_colors,
                hovertemplate='<b>Sensor %{x}</b><br>' +
                              'Promedio MP1.0: %{y:.1f} μg/m³<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title="Promedio de MP1.0 por Sensor",
            xaxis_title="Identificador",
            yaxis_title="MP1.0 Promedio (μg/m³)",
            showlegend=False,
            height=400
        )
        
        # Agregar líneas de referencia OMS
        fig.add_hline(y=15, line_dash="dash", line_color="green", 
                      annotation_text="OMS: Buena")
        fig.add_hline(y=25, line_dash="dash", line_color="orange", 
                      annotation_text="OMS: Moderada")
        fig.add_hline(y=35, line_dash="dash", line_color="red", 
                      annotation_text="OMS: Dañina")
        
        return fig
        
    except Exception as e:
        print(f"Error creando gráfico de comparación: {e}")
        return create_empty_plot("Error al crear el gráfico")

def get_dashboard_stats():
    """
    Get comprehensive dashboard statistics including data freshness
    """
    logger = get_dashboard_logger()
    
    try:
        start_time = get_chile_time()
        current_data = get_current_data()
        data_freshness = get_data_freshness()
        
        if current_data.empty:
            return {
                'status': 'no_data',
                'last_update': format_chile_time(),
                'data_status': data_freshness
            }
        
        # Calcular estadísticas
        total_sensors = len(current_data['Sensor_ID'].unique())
        avg_mp1 = round(current_data['MP1'].mean(), 1)
        max_mp1 = round(current_data['MP1'].max(), 1)
        min_mp1 = round(current_data['MP1'].min(), 1)
        total_data_points = len(current_data)
        
        duration = (get_chile_time() - start_time).total_seconds()
        
        log_performance_metric(logger, "Dashboard stats calculation", duration, {
            'sensor_count': total_sensors,
            'data_points': total_data_points,
            'data_status': data_freshness['status']
        })
        
        return {
            'status': 'success',
            'total_sensors': total_sensors,
            'avg_mp1': avg_mp1,
            'max_mp1': max_mp1,
            'min_mp1': min_mp1,
            'total_points': total_data_points,
            'last_update': format_chile_time(),
            'data_status': data_freshness
        }
        
    except Exception as e:
        logger.error(f"Error in get_dashboard_stats: {e}", exc_info=True)
        return {
            'status': 'error',
            'last_update': format_chile_time(),
            'data_status': get_data_freshness()
        }

def get_sensor_stats(sensor_id, start_date=None, end_date=None):
    """Obtener estadísticas detalladas para un sensor específico"""
    try:
        df = get_sensor_data(sensor_id, start_date, end_date)
        
        if df is None or len(df) == 0:
            return {
                'status': 'no_data',
                'sensor_id': sensor_id,
                'last_update': format_chile_time()
            }
        
        stats = {
            'status': 'success',
            'sensor_id': sensor_id,
            'avg_mp1': df['MP1'].mean(),
            'max_mp1': df['MP1'].max(),
            'min_mp1': df['MP1'].min(),
            'std_mp1': df['MP1'].std(),
            'data_points': len(df),
            'date_range': f"{df.index.min().strftime('%Y-%m-%d')} a {df.index.max().strftime('%Y-%m-%d')}",
            'hours_covered': (df.index.max() - df.index.min()).total_seconds() / 3600 if len(df) > 1 else 0,
            'last_update': format_chile_time()
        }
        
        return stats
        
    except Exception as e:
        print(f"Error obteniendo estadísticas del sensor {sensor_id}: {e}")
        return {
            'status': 'error',
            'sensor_id': sensor_id,
            'last_update': format_chile_time()
        }

def render_health_tab():
    """Renderizar la pestaña de estado de sensores"""
    return html.Div([
        # Tarjetas de resumen de estado
        html.Div(id='health-summary-cards', style={'margin': '20px 0'}),
        
        # Caja explicativa de estados
        html.Div([
            html.H3("Explicación de Estados de Sensores", 
                   style={'color': '#2c3e50', 'marginBottom': '15px', 'textAlign': 'center'}),
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("●", style={'color': '#27ae60', 'fontSize': '20px', 'marginRight': '10px'}),
                        html.Strong("Saludable:", style={'color': '#27ae60'}),
                        html.Span(" El sensor ha enviado datos hoy.")
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("●", style={'color': '#f39c12', 'fontSize': '20px', 'marginRight': '10px'}),
                        html.Strong("Advertencia:", style={'color': '#f39c12'}),
                        html.Span(" El sensor envió datos ayer o en los últimos 3 días.")
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("●", style={'color': '#e74c3c', 'fontSize': '20px', 'marginRight': '10px'}),
                        html.Strong("Crítico:", style={'color': '#e74c3c'}),
                        html.Span(" El sensor no ha enviado datos por más de 3 días o nunca.")
                    ], style={'marginBottom': '0px'})
                ], style={'padding': '20px'})
            ], style={
                'background': '#f8f9fa',
                'border': '1px solid #dee2e6',
                'borderRadius': '10px',
                'margin': '20px 0'
            })
        ]),
        
        # Tabla detallada de sensores
        html.Div(id='sensor-health-table', style={'margin': '20px 0'}),
        
        # Pie de página
        html.Div([
            html.P(id='health-last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("Los sensores se consideran saludables si han enviado datos hoy. Estado de advertencia si enviaron ayer.", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
    ])

# Obtener sensores y fechas disponibles
available_sensors = get_available_sensors()
min_date, max_date = get_date_range()

# Definir el diseño con pestañas
app.layout = html.Div([
    # Encabezado
    html.Div([
        html.H1("Monitor de Calidad del Aire USACH", 
                style={'textAlign': 'center', 'color': 'white', 'margin': '0'}),
        html.P("Panel de Datos Ambientales en Tiempo Real", 
               style={'textAlign': 'center', 'color': 'white', 'opacity': '0.8', 'margin': '10px 0 0 0'})
    ], style={
        'background': 'linear-gradient(135deg, #2c3e50 0%, #34495e 100%)',
        'padding': '30px',
        'marginBottom': '0'
    }),
    
    # Intervalo de auto-actualización
    dcc.Interval(
        id='interval-component',
        interval=10*60*1000,  # 10 minutos en milisegundos
        n_intervals=0
    ),
    
    # Contenido principal con pestañas
    html.Div([
        dcc.Tabs(id="tabs", value="tab-1", children=[
            dcc.Tab(label="Resumen General", value="tab-1", style={'padding': '10px'}),
            dcc.Tab(label="Análisis de Sensor Específico", value="tab-2", style={'padding': '10px'}),
            dcc.Tab(label="Estado de Sensores", value="tab-3", style={'padding': '10px'}),
            dcc.Tab(label="🔧 Desarrollador", value="tab-4", style={'padding': '10px', 'background': '#2c3e50', 'color': 'white'})
        ], style={'marginBottom': '20px'}),
        
        html.Div(id='tabs-content')
        
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'padding': '0 20px'})
], style={'fontFamily': 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif'})

def render_general_tab():
    """Renderizar la pestaña de resumen general"""
    return html.Div([
        # Tarjetas de estado
        html.Div(id='status-cards', style={'margin': '20px 0'}),
        
        # Gráficos
        html.Div([
            html.Div([
                dcc.Graph(id='time-series-plot')
            ], style={'width': '100%', 'margin': '20px 0'}),
            
            html.Div([
                dcc.Graph(id='sensor-comparison-plot')
            ], style={'width': '100%', 'margin': '20px 0'})
        ]),
        
        # Detalles de sensores
        html.Div(id='sensor-details', style={'margin': '20px 0'}),
        
        # Pie de página
        html.Div([
            html.P(id='last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("El panel se actualiza automáticamente cada 10 minutos", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
    ])

def render_specific_tab():
    """Renderizar la pestaña de análisis de sensor específico"""
    # Crear opciones de sensores
    sensor_options = [{'label': f'Sensor {s}', 'value': s} for s in available_sensors]
    
    # Crear valores predeterminados del selector de fechas
    default_start = min_date if min_date else get_chile_time() - timedelta(days=7)
    default_end = max_date if max_date else get_chile_time()
    
    return html.Div([
        # Controles
        html.Div([
            html.Div([
                html.Label("Seleccionar Sensor:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id='sensor-dropdown',
                    options=sensor_options,
                    value=available_sensors[0] if available_sensors else None,
                    placeholder="Elegir un sensor...",
                    style={'marginBottom': '20px'}
                )
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            html.Div([
                html.Label("Rango de Fechas:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    start_date=default_start,
                    end_date=default_end,
                    display_format='YYYY-MM-DD',
                    style={'marginBottom': '20px'}
                )
            ], style={'width': '48%', 'float': 'right', 'display': 'inline-block'})
        ], style={'background': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px'}),
        
        # Tarjetas de estadísticas
        html.Div(id='sensor-stats-cards', style={'margin': '20px 0'}),
        
        # Gráfico detallado
        html.Div([
            dcc.Graph(id='sensor-detailed-plot')
        ], style={'width': '100%', 'margin': '20px 0'}),
        
        # Pie de página
        html.Div([
            html.P(id='sensor-last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("Use los controles superiores para analizar sensores específicos en períodos de tiempo personalizados", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '15px', 'marginTop': '30px'})
    ])

def render_developer_tab():
    """Renderizar la pestaña de desarrollador con métricas del sistema"""
    return html.Div([
        # Encabezado de desarrollador
        html.Div([
            html.H2("🔧 Panel de Desarrollador", style={'color': '#2c3e50', 'margin': '0'}),
            html.P("Métricas del sistema, logs y rendimiento", style={'color': '#7f8c8d', 'margin': '5px 0'})
        ], style={'background': '#ecf0f1', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px'}),
        
        # Tarjetas de métricas principales
        html.Div(id='dev-metrics-cards', style={'margin': '20px 0'}),
        
        # Gráficos de rendimiento
        html.Div([
            html.Div([
                html.H3("📊 Rendimiento del Sistema", style={'color': '#2c3e50', 'marginBottom': '15px'}),
                dcc.Graph(id='performance-chart')
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginRight': '2%'}),
            
            html.Div([
                html.H3("📈 Estado de Logs", style={'color': '#2c3e50', 'marginBottom': '15px'}),
                dcc.Graph(id='logs-chart')
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
        ], style={'margin': '20px 0'}),
        
        # Tabla de logs recientes
        html.Div([
            html.H3("📋 Logs Recientes", style={'color': '#2c3e50', 'marginBottom': '15px'}),
            html.Div([
                html.Label("Nivel de Log:", style={'marginRight': '10px', 'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='log-level-filter',
                    options=[
                        {'label': 'Todos', 'value': 'ALL'},
                        {'label': 'ERROR', 'value': 'ERROR'},
                        {'label': 'WARNING', 'value': 'WARNING'},
                        {'label': 'INFO', 'value': 'INFO'}
                    ],
                    value='ERROR',
                    style={'width': '150px', 'display': 'inline-block'}
                )
            ], style={'marginBottom': '15px'}),
            html.Div(id='recent-logs-table')
        ], style={'background': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px', 'margin': '20px 0'}),
        
        # Información de sistema
        html.Div(id='system-info', style={'margin': '20px 0'}),
        
        # Pie de página
        html.Div([
            html.P(id='dev-last-update', style={'textAlign': 'center', 'color': '#7f8c8d', 'margin': '10px 0'}),
            html.P("Panel actualizado cada 30 segundos • Logs y métricas en tiempo real", 
                   style={'textAlign': 'center', 'color': '#7f8c8d', 'fontSize': '0.9em', 'margin': '5px 0'})
        ], style={'background': '#2c3e50', 'color': 'white', 'padding': '15px', 'marginTop': '30px', 'borderRadius': '10px'})
    ])

def get_developer_dashboard_data():
    """Obtener datos para el panel de desarrollador"""
    try:
        logger.info("Getting developer metrics")
        return get_developer_metrics()
    except Exception as e:
        logger.error(f"Error getting developer metrics: {e}", exc_info=True)
        return {
            'timestamp': format_chile_time(),
            'error': str(e),
            'system_health': 0
        }

def create_performance_chart(metrics):
    """Crear gráfico de rendimiento del sistema"""
    try:
        if 'error' in metrics:
            return create_empty_plot("Error obteniendo métricas de rendimiento")
        
        performance = metrics.get('performance', {})
        
        if performance.get('status') != 'active':
            return create_empty_plot(performance.get('message', 'Métricas no disponibles'))
        
        # Crear gráfico de barras para uso de recursos
        categories = ['CPU', 'Memoria', 'Disco']
        values = [
            performance.get('cpu', {}).get('percent', 0),
            performance.get('memory', {}).get('percent_used', 0),
            performance.get('disk', {}).get('percent_used', 0)
        ]
        
        # Colores basados en el nivel de uso
        colors = []
        for val in values:
            if val > 90:
                colors.append('#e74c3c')  # Rojo
            elif val > 80:
                colors.append('#f39c12')  # Naranja
            elif val > 60:
                colors.append('#f1c40f')  # Amarillo
            else:
                colors.append('#27ae60')  # Verde
        
        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=values,
                marker_color=colors,
                text=[f'{v:.1f}%' for v in values],
                textposition='inside'
            )
        ])
        
        fig.update_layout(
            title="Uso de Recursos del Sistema",
            yaxis_title="Porcentaje de Uso (%)",
            height=300,
            showlegend=False
        )
        
        # Agregar líneas de referencia
        fig.add_hline(y=80, line_dash="dash", line_color="orange", annotation_text="Advertencia (80%)")
        fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Crítico (90%)")
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating performance chart: {e}")
        return create_empty_plot(f"Error: {str(e)}")

def create_logs_chart(metrics):
    """Crear gráfico de estado de logs"""
    try:
        logs = metrics.get('logs', {})
        
        if not logs or logs.get('status') != 'success':
            return create_empty_plot("Datos de logs no disponibles")
        
        # Datos para el gráfico de logs por componente
        components = []
        log_counts = []
        error_counts = []
        
        for component, info in logs.get('component_info', {}).items():
            if component != 'total_size_mb':
                components.append(component.replace('_', ' ').title())
                log_counts.append(info.get('file_count', 0))
                error_counts.append(len(info.get('recent_errors', [])))
        
        # Si no hay datos, mostrar mensaje
        if not components:
            return create_empty_plot("No hay datos de logs disponibles")
        
        fig = go.Figure()
        
        # Barras para archivos de log
        fig.add_trace(go.Bar(
            name='Archivos de Log',
            x=components,
            y=log_counts,
            marker_color='#3498db',
            text=log_counts,
            textposition='auto',
        ))
        
        # Barras para errores recientes
        fig.add_trace(go.Bar(
            name='Errores Recientes',
            x=components,
            y=error_counts,
            marker_color='#e74c3c',
            text=error_counts,
            textposition='auto',
        ))
        
        fig.update_layout(
            title="📝 Estado de Logs por Componente",
            xaxis_title="Componente",
            yaxis_title="Cantidad",
            font=dict(family="Arial, sans-serif", size=12),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            barmode='group',
            height=400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(128,128,128,0.2)'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating logs chart: {e}")
        return create_empty_plot(f"Error: {str(e)}")

# Callback para contenido de pestañas
@app.callback(Output('tabs-content', 'children'),
              Input('tabs', 'value'))
def render_content(tab):
    if tab == 'tab-1':
        return render_general_tab()
    elif tab == 'tab-2':
        return render_specific_tab()
    elif tab == 'tab-3':
        return render_health_tab()
    elif tab == 'tab-4':
        return render_developer_tab()

# Callbacks para actualizaciones de pestaña general
@app.callback(
    [Output('status-cards', 'children'),
     Output('time-series-plot', 'figure'),
     Output('sensor-comparison-plot', 'figure'),
     Output('sensor-details', 'children'),
     Output('last-update', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_general_dashboard(n):
    try:
        stats = get_dashboard_stats()
        
        # Manejar caso sin datos
        if stats.get('status') == 'no_data':
            # Tarjetas de estado para sin datos
            status_cards = html.Div([
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
            
            # Gráficos vacíos
            empty_fig = go.Figure().add_annotation(
                text="No hay datos disponibles<br>Ejecute 'python fetch_piloto_files.py' para descargar datos",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#7f8c8d")
            )
            empty_fig.update_layout(
                title="Esperando Datos...",
                height=400
            )
            
            sensor_details = html.Div([
                html.H2("Detalle", style={'color': '#2c3e50', 'marginBottom': '20px'}),
                html.Div([
                    html.P("No hay datos de sensores disponibles", 
                           style={'textAlign': 'center', 'color': '#7f8c8d', 'fontStyle': 'italic'})
                ], style={
                    'display': 'grid',
                    'gridTemplateColumns': 'repeat(auto-fit, minmax(250px, 1fr))',
                    'gap': '15px'
                })
            ])
            
            # Create status info with both data freshness and dashboard refresh
            data_status = stats['data_status']
            status_info = html.Div([
                html.P(f"Última actualización de datos: {data_status['last_update']}", 
                       style={'margin': '2px 0', 'fontSize': '0.9em', 'color': '#2c3e50'}),
                html.P(f"Estado: {data_status['message']}", 
                       style={'margin': '2px 0', 'fontSize': '0.85em', 
                              'color': '#27ae60' if data_status['status'] == 'fresh' 
                                      else '#f39c12' if data_status['status'] == 'stale' 
                                      else '#e74c3c'}),
                html.P(f"Última verificación del panel: {stats['last_update']}", 
                       style={'margin': '2px 0', 'fontSize': '0.8em', 'color': '#7f8c8d'})
            ], style={'textAlign': 'center'})
            
            return status_cards, empty_fig, empty_fig, sensor_details, status_info
        
        # Manejar caso de error
        if stats.get('status') == 'error':
            error_msg = html.Div([
                html.H2("Error de Datos", style={'color': '#e74c3c', 'textAlign': 'center'}),
                html.P("Hubo un error procesando los datos de calidad del aire. Por favor revise los registros.", 
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
                text="Error procesando datos",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#e74c3c")
            )
            
            return error_msg, empty_fig, empty_fig, error_msg, f"Error en: {stats['last_update']}"
        
        # Caso normal con datos
        # Tarjetas de estado
        status_cards = html.Div([
            html.Div([
                html.Div([
                    html.H2(str(stats['total_sensors']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Sensores Activos", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['avg_mp1']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Promedio MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['max_mp1']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Máx MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(stats['total_points']), style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Datos totales", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card')
            ], style={
                'display': 'grid',
                'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))',
                'gap': '20px',
                'margin': '20px 0'
            })
        ])
        
        # Crear gráficos
        time_series_fig = create_time_series_plot()
        comparison_fig = create_sensor_comparison_plot()
        
        # Crear detalles de sensores
        current_data = get_current_data()
        if not current_data.empty:
            sensor_cards = []
            for sensor_id in sorted(current_data['Sensor_ID'].unique()):
                sensor_data = current_data[current_data['Sensor_ID'] == sensor_id]
                current_mp1 = sensor_data['MP1'].iloc[0] if not sensor_data.empty else 0
                category, color, risk = get_air_quality_category(current_mp1)
                
                sensor_card = html.Div([
                    html.H4(f"Sensor {sensor_id}", style={'margin': '0 0 10px 0', 'color': '#2c3e50'}),
                    html.P(f"MP1.0: {current_mp1:.1f} μg/m³", style={'margin': '5px 0', 'fontSize': '1.1em', 'fontWeight': 'bold'}),
                    html.P(f"Estado: {category}", style={'margin': '5px 0', 'color': color, 'fontWeight': 'bold'}),
                    html.P(f"Evaluación: {risk}", style={'margin': '5px 0', 'color': '#7f8c8d', 'fontSize': '0.9em'})
                ], style={
                    'background': 'white',
                    'padding': '15px',
                    'borderRadius': '8px',
                    'border': f'2px solid {color}',
                    'margin': '10px 0'
                })
                sensor_cards.append(sensor_card)
            
            sensor_details = html.Div([
                html.H2("Detalle", style={'color': '#2c3e50', 'marginBottom': '20px'}),
                html.Div(sensor_cards, style={
                    'display': 'grid',
                    'gridTemplateColumns': 'repeat(auto-fit, minmax(250px, 1fr))',
                    'gap': '15px'
                })
            ])
        else:
            sensor_details = html.Div([
                html.H2("Detalle", style={'color': '#2c3e50'}),
                html.P("No hay datos de sensores disponibles.", style={'color': '#7f8c8d', 'fontStyle': 'italic'})
            ])
        
        # Create status info with both data freshness and dashboard refresh
        data_status = stats['data_status']
        status_info = html.Div([
            html.P(f"Última actualización de datos: {data_status['last_update']}", 
                   style={'margin': '2px 0', 'fontSize': '0.9em', 'color': '#2c3e50'}),
            html.P(f"Estado: {data_status['message']}", 
                   style={'margin': '2px 0', 'fontSize': '0.85em', 
                          'color': '#27ae60' if data_status['status'] == 'fresh' 
                                  else '#f39c12' if data_status['status'] == 'stale' 
                                  else '#e74c3c'}),
            html.P(f"Última verificación del panel: {stats['last_update']}", 
                   style={'margin': '2px 0', 'fontSize': '0.8em', 'color': '#7f8c8d'})
        ], style={'textAlign': 'center'})
        
        return status_cards, time_series_fig, comparison_fig, sensor_details, status_info
    
    except Exception as e:
        print(f"Error en callback update_general_dashboard: {e}")
        import traceback
        traceback.print_exc()
        
        # Retornar estado de error
        error_msg = html.Div([
            html.H2("Error del Panel", style={'color': '#e74c3c', 'textAlign': 'center'}),
            html.P(f"Error: {str(e)}", style={'textAlign': 'center', 'color': '#7f8c8d'})
        ])
        
        empty_fig = go.Figure().add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="#e74c3c")
        )
        
        current_time = format_chile_time()
        
        return error_msg, empty_fig, empty_fig, error_msg, f"Error en: {current_time}"

# Callbacks para análisis de sensor específico
@app.callback(
    [Output('sensor-dropdown', 'options'),
     Output('sensor-dropdown', 'value'),
     Output('sensor-stats-cards', 'children'),
     Output('sensor-detailed-plot', 'figure'),
     Output('sensor-last-update', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('sensor-dropdown', 'value'),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_sensor_analysis(n, selected_sensor, start_date, end_date):
    try:
        current_data = get_current_data()
        
        # Obtener sensores disponibles para el dropdown
        if not current_data.empty:
            sensor_options = [{'label': f'Sensor {sid}', 'value': sid} 
                            for sid in sorted(current_data['Sensor_ID'].unique())]
            
            # Predeterminar al primer sensor si no hay ninguno seleccionado
            if not selected_sensor:
                selected_sensor = sorted(current_data['Sensor_ID'].unique())[0]
        else:
            sensor_options = []
            selected_sensor = None
        
        # Manejar sin sensor seleccionado o sin datos
        if not selected_sensor or current_data.empty:
            empty_stats = html.Div([
                html.H3("No Hay Datos Disponibles", style={'textAlign': 'center', 'color': '#7f8c8d'}),
                html.P("Seleccione un sensor o verifique si hay datos disponibles.", 
                       style={'textAlign': 'center', 'color': '#7f8c8d'})
            ])
            
            empty_fig = go.Figure().add_annotation(
                text="No hay datos de sensores disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#7f8c8d")
            )
            empty_fig.update_layout(title="Seleccione un Sensor", height=500)
            
            current_time = format_chile_time()
            return sensor_options, selected_sensor, empty_stats, empty_fig, f"Última verificación: {current_time}"
        
        # Obtener datos del sensor usando el procesador modular
        sensor_data = get_sensor_data(selected_sensor, start_date, end_date)
        
        if sensor_data.empty:
            empty_stats = html.Div([
                html.H3("No Hay Datos en el Rango Seleccionado", style={'textAlign': 'center', 'color': '#7f8c8d'}),
                html.P("Intente seleccionar un rango de fechas diferente.", 
                       style={'textAlign': 'center', 'color': '#7f8c8d'})
            ])
            
            empty_fig = go.Figure().add_annotation(
                text="No hay datos en el rango de fechas seleccionado",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#7f8c8d")
            )
            empty_fig.update_layout(title=f"Sensor {selected_sensor} - Sin Datos", height=500)
            
            current_time = format_chile_time()
            return sensor_options, selected_sensor, empty_stats, empty_fig, f"Última verificación: {current_time}"
        
        # Calcular estadísticas
        avg_mp1 = sensor_data['MP1'].mean()
        max_mp1 = sensor_data['MP1'].max()
        min_mp1 = sensor_data['MP1'].min()
        std_mp1 = sensor_data['MP1'].std()
        data_points = len(sensor_data)
        
        # Calcular horas de datos (aproximado)
        if len(sensor_data) > 1:
            time_span = sensor_data.index.max() - sensor_data.index.min()
            hours_of_data = time_span.total_seconds() / 3600
        else:
            hours_of_data = 0
        
        # Crear tarjetas de estadísticas
        stats_cards = html.Div([
            html.Div([
                html.H3(f"{avg_mp1:.1f}", style={'margin': '0', 'color': '#2c3e50'}),
                html.P("Promedio MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card'),
            
            html.Div([
                html.H3(f"{max_mp1:.1f}", style={'margin': '0', 'color': '#e74c3c'}),
                html.P("Máximo MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card'),
            
            html.Div([
                html.H3(f"{min_mp1:.1f}", style={'margin': '0', 'color': '#27ae60'}),
                html.P("Mínimo MP1.0 (μg/m³)", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card'),
            
            html.Div([
                html.H3(f"{std_mp1:.1f}", style={'margin': '0', 'color': '#f39c12'}),
                html.P("Desviación Estándar", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card'),
            
            html.Div([
                html.H3(f"{data_points:,}", style={'margin': '0', 'color': '#3498db'}),
                html.P("Datos totales", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card'),
            
            html.Div([
                html.H3(f"{hours_of_data:.1f}", style={'margin': '0', 'color': '#9b59b6'}),
                html.P("Horas de Datos", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
            ], className='stat-card')
        ], style={
            'display': 'grid',
            'gridTemplateColumns': 'repeat(auto-fit, minmax(180px, 1fr))',
            'gap': '15px',
            'margin': '20px 0'
        })
        
        # Crear gráfico detallado
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=sensor_data.index,  # datetime es el índice
            y=sensor_data['MP1'],
            mode='lines+markers',
            name=f'Sensor {selected_sensor}',
            line=dict(color='#3498db', width=2),
            marker=dict(size=4)
        ))
        
        # Agregar línea de promedio
        fig.add_hline(
            y=avg_mp1,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Promedio: {avg_mp1:.1f} μg/m³"
        )
        
        fig.update_layout(
            title=f'Análisis Detallado - Sensor {selected_sensor}',
            xaxis_title='Fecha',
            yaxis_title='Material Particulado MP1.0 (μg/m³)',
            height=500,
            hovermode='x unified',
            showlegend=True,
            template='plotly_white'
        )
        
        current_time = format_chile_time()
        last_update = f"Última actualización: {current_time}"
        
        return sensor_options, selected_sensor, stats_cards, fig, last_update
    
    except Exception as e:
        print(f"Error en callback update_sensor_analysis: {e}")
        import traceback
        traceback.print_exc()
        
        # Retornar estado de error
        error_msg = html.Div([
            html.H3("Error de Análisis", style={'color': '#e74c3c', 'textAlign': 'center'}),
            html.P(f"Error: {str(e)}", style={'textAlign': 'center', 'color': '#7f8c8d'})
        ])
        
        empty_fig = go.Figure().add_annotation(
            text=f"Error: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="#e74c3c")
        )
        
        current_time = format_chile_time()
        
        return [], None, error_msg, empty_fig, f"Error en: {current_time}"

# Callback para actualizaciones de pestaña de estado
@app.callback(
    [Output('health-summary-cards', 'children'),
     Output('sensor-health-table', 'children'),
     Output('health-last-update', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_health_dashboard(n):
    try:
        health_data = get_sensor_health_status()
        
        # Handle different health_data response structures
        if 'status' in health_data and health_data['status'] == 'no_data':
            no_data_msg = html.Div([
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
            
            return no_data_msg, no_data_msg, f"Última verificación: {health_data['last_update']}"
        
        if 'status' in health_data and health_data['status'] == 'error':
            error_msg = html.Div([
                html.H2("Error de Datos", style={'color': '#e74c3c', 'textAlign': 'center'}),
                html.P("Hubo un error procesando los datos de estado de sensores.", 
                       style={'textAlign': 'center', 'color': '#7f8c8d'})
            ], style={
                'background': '#f8d7da',
                'border': '1px solid #f5c6cb',
                'color': '#721c24',
                'padding': '20px',
                'borderRadius': '5px',
                'textAlign': 'center'
            })
            
            return error_msg, error_msg, f"Error en: {health_data['last_update']}"
        
        # Caso normal con datos
        # Create summary data structure for compatibility
        summary = {
            'total_sensors': health_data['total_sensors'],
            'healthy': health_data['healthy_count'],
            'warning': health_data['warning_count'],
            'critical': health_data['critical_count'],
            'healthy_percentage': round((health_data['healthy_count'] / health_data['total_sensors']) * 100, 1) if health_data['total_sensors'] > 0 else 0
        }
        
        # Tarjetas de resumen
        summary_cards = html.Div([
            html.Div([
                html.Div([
                    html.H2(str(summary['healthy']), style={'margin': '0', 'color': '#27ae60'}),
                    html.P("Sensores Saludables", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(summary['warning']), style={'margin': '0', 'color': '#f39c12'}),
                    html.P("En Advertencia", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(str(summary['critical']), style={'margin': '0', 'color': '#e74c3c'}),
                    html.P("Estado Crítico", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card'),
                
                html.Div([
                    html.H2(f"{summary['healthy_percentage']}%", style={'margin': '0', 'color': '#2c3e50'}),
                    html.P("Sensores Funcionando Hoy", style={'margin': '5px 0 0 0', 'color': '#7f8c8d'})
                ], className='stat-card')
            ], style={
                'display': 'grid',
                'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))',
                'gap': '20px',
                'margin': '20px 0'
            })
        ])
        
        # Tabla detallada
        sensor_health = health_data['sensors']
        table_rows = []
        
        # Encabezado de tabla
        table_header = html.Tr([
            html.Th("Sensor ID", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'}),
            html.Th("Estado", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'}),
            html.Th("Últimos Datos", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'}),
            html.Th("Archivos Totales", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'}),
            html.Th("Archivos Vacíos", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'}),
            html.Th("Funcionando Hoy", style={'padding': '12px', 'textAlign': 'left', 'background': '#f8f9fa'})
        ])
        
        # Filas de datos
        for sensor_id in sorted(sensor_health.keys()):
            health = sensor_health[sensor_id]
            
            status_colors = {
                'healthy': '#d4edda',
                'warning': '#fff3cd', 
                'critical': '#f8d7da'
            }
            
            status_text_colors = {
                'healthy': '#155724',
                'warning': '#856404',
                'critical': '#721c24'
            }
            
            table_rows.append(html.Tr([
                html.Td(f"Sensor {sensor_id}", style={'padding': '12px'}),
                html.Td(
                    html.Span(health['status'].title(), 
                             style={
                                 'padding': '4px 8px',
                                 'borderRadius': '4px',
                                 'background': status_colors[health['status']],
                                 'color': status_text_colors[health['status']],
                                 'fontSize': '0.9em'
                             }),
                    style={'padding': '12px'}
                ),
                html.Td(
                    health['last_data_date'].strftime('%Y-%m-%d') if health['last_data_date'] else 'Sin datos',
                    style={'padding': '12px'}
                ),
                html.Td(str(health['total_files']), style={'padding': '12px'}),
                html.Td(str(health['empty_files']), style={'padding': '12px'}),
                html.Td(
                    "✓" if health['working_today'] else "✗",
                    style={
                        'padding': '12px',
                        'color': '#27ae60' if health['working_today'] else '#e74c3c',
                        'fontWeight': 'bold'
                    }
                )
            ]))
        
        health_table = html.Div([
            html.H2("Detalle de Estado de Sensores", style={'color': '#2c3e50', 'marginBottom': '20px'}),
            html.Table([
                html.Thead([table_header]),
                html.Tbody(table_rows)
            ], style={
                'width': '100%',
                'borderCollapse': 'collapse',
                'border': '1px solid #dee2e6'
            })
        ])
        
        last_update = f"Última verificación: {health_data['last_update']}"
        
        return summary_cards, health_table, last_update
        
    except Exception as e:
        print(f"Error actualizando dashboard de estado: {e}")
        error_msg = html.Div([
            html.H2("Error", style={'color': '#e74c3c'}),
            html.P(f"Error inesperado: {str(e)}")
        ])
        return error_msg, error_msg, f"Error en: {format_chile_time()}"

# Callback para el panel de desarrollador
@app.callback(
    [Output('dev-metrics-cards', 'children'),
     Output('performance-chart', 'figure'),
     Output('logs-chart', 'figure'),
     Output('system-info', 'children'),
     Output('dev-last-update', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_developer_dashboard(n):
    """Actualizar el panel de desarrollador"""
    try:
        # Obtener métricas del sistema
        metrics = get_developer_dashboard_data()
        
        if 'error' in metrics:
            error_msg = html.Div([
                html.H3("❌ Error", style={'color': '#e74c3c'}),
                html.P(f"Error obteniendo métricas: {metrics['error']}")
            ])
            empty_fig = create_empty_plot("Error en métricas")
            return error_msg, empty_fig, empty_fig, error_msg, f"Error: {metrics['timestamp']}"
        
        # Crear tarjetas de métricas principales
        metrics_cards = create_developer_metrics_cards(metrics)
        
        # Crear gráficos
        perf_chart = create_performance_chart(metrics)
        logs_chart = create_logs_chart(metrics)
        
        # Crear información del sistema
        system_info = create_system_info_section(metrics)
        
        # Timestamp de actualización
        last_update = f"Última actualización: {metrics['timestamp']}"
        
        return metrics_cards, perf_chart, logs_chart, system_info, last_update
        
    except Exception as e:
        logger.error(f"Error updating developer dashboard: {e}", exc_info=True)
        error_msg = html.Div([
            html.H3("❌ Error del Sistema", style={'color': '#e74c3c'}),
            html.P(f"Error inesperado: {str(e)}")
        ])
        empty_fig = create_empty_plot("Error del sistema")
        return error_msg, empty_fig, empty_fig, error_msg, f"Error: {format_chile_time()}"

# Callback para la tabla de logs recientes
@app.callback(
    Output('recent-logs-table', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('log-level-filter', 'value')]
)
def update_recent_logs_table(n, log_level):
    """Actualizar la tabla de logs recientes"""
    try:
        # Obtener logs recientes
        recent_logs = get_recent_log_entries(level=log_level, limit=15)
        
        if not recent_logs:
            return html.P("No hay logs disponibles", style={'textAlign': 'center', 'color': '#7f8c8d'})
        
        # Crear tabla
        table_header = html.Tr([
            html.Th("Timestamp", style={'padding': '12px', 'background': '#f8f9fa', 'border': '1px solid #dee2e6'}),
            html.Th("Componente", style={'padding': '12px', 'background': '#f8f9fa', 'border': '1px solid #dee2e6'}),
            html.Th("Nivel", style={'padding': '12px', 'background': '#f8f9fa', 'border': '1px solid #dee2e6'}),
            html.Th("Mensaje", style={'padding': '12px', 'background': '#f8f9fa', 'border': '1px solid #dee2e6'})
        ])
        
        table_rows = []
        for log_entry in recent_logs:
            # Color del nivel de log
            level_color = {
                'ERROR': '#e74c3c',
                'WARNING': '#f39c12', 
                'INFO': '#3498db',
                'DEBUG': '#95a5a6'
            }.get(log_entry['level'], '#2c3e50')
            
            row = html.Tr([
                html.Td(log_entry['timestamp'], style={'padding': '8px', 'border': '1px solid #dee2e6', 'fontSize': '0.85em'}),
                html.Td(log_entry['component'], style={'padding': '8px', 'border': '1px solid #dee2e6', 'fontWeight': 'bold'}),
                html.Td(log_entry['level'], style={
                    'padding': '8px', 
                    'border': '1px solid #dee2e6',
                    'color': level_color,
                    'fontWeight': 'bold'
                }),
                html.Td(
                    log_entry['message'][:100] + ('...' if len(log_entry['message']) > 100 else ''),
                    style={'padding': '8px', 'border': '1px solid #dee2e6', 'fontSize': '0.9em'}
                )
            ])
            table_rows.append(row)
        
        table = html.Table([
            html.Thead([table_header]),
            html.Tbody(table_rows)
        ], style={
            'width': '100%',
            'borderCollapse': 'collapse',
            'border': '1px solid #dee2e6'
        })
        
        return table
        
    except Exception as e:
        logger.error(f"Error updating logs table: {e}")
        return html.P(f"Error cargando logs: {str(e)}", style={'color': '#e74c3c'})

def create_developer_metrics_cards(metrics):
    """Crear tarjetas de métricas principales para desarrollador"""
    try:
        # Obtener puntuación de salud del sistema
        health_score = metrics.get('system_health', 0)
        health_color = '#27ae60' if health_score >= 80 else '#f39c12' if health_score >= 60 else '#e74c3c'
        
        # Status del pipeline de datos
        data_pipeline = metrics.get('data_pipeline', {})
        pipeline_status = data_pipeline.get('status', {}).get('status', 'unknown')
        pipeline_color = '#27ae60' if pipeline_status == 'success' else '#e74c3c' if pipeline_status == 'error' else '#f39c12'
        
        # Status de logs
        logs = metrics.get('logs', {})
        log_errors = len(logs.get('recent_errors', []))
        log_color = '#27ae60' if log_errors == 0 else '#f39c12' if log_errors < 5 else '#e74c3c'
        
        # Status de rendimiento
        performance = metrics.get('performance', {})
        perf_status = performance.get('status', 'unknown')
        perf_color = '#27ae60' if perf_status == 'active' else '#e74c3c'
        
        # Background process status
        bg_process = metrics.get('background_process', {})
        fetcher = bg_process.get('fetcher', {})
        fetch_status = fetcher.get('status', 'unknown')
        fetch_color = '#27ae60' if fetch_status == 'running' else '#f39c12'
        
        cards = html.Div([
            # Salud general del sistema
            html.Div([
                html.H3("🎯 Salud del Sistema", style={'color': '#2c3e50', 'margin': '0 0 10px 0'}),
                html.H1(f"{health_score}%", style={'color': health_color, 'margin': '0', 'fontSize': '3em'}),
                html.P("Puntuación General", style={'color': '#7f8c8d', 'margin': '5px 0'})
            ], className='stat-card', style={'border-left': f'4px solid {health_color}'}),
            
            # Pipeline de datos
            html.Div([
                html.H3("📊 Pipeline de Datos", style={'color': '#2c3e50', 'margin': '0 0 10px 0'}),
                html.H2(pipeline_status.title(), style={'color': pipeline_color, 'margin': '0'}),
                html.P(f"Archivos procesados: {data_pipeline.get('status', {}).get('files_fetched', 0)}", 
                       style={'color': '#7f8c8d', 'margin': '5px 0'})
            ], className='stat-card', style={'border-left': f'4px solid {pipeline_color}'}),
            
            # Logs
            html.Div([
                html.H3("📝 Estado de Logs", style={'color': '#2c3e50', 'margin': '0 0 10px 0'}),
                html.H2(f"{log_errors} Errores", style={'color': log_color, 'margin': '0'}),
                html.P(f"Tamaño total: {logs.get('total_size_mb', 0)} MB", 
                       style={'color': '#7f8c8d', 'margin': '5px 0'})
            ], className='stat-card', style={'border-left': f'4px solid {log_color}'}),
            
            # Rendimiento
            html.Div([
                html.H3("⚡ Rendimiento", style={'color': '#2c3e50', 'margin': '0 0 10px 0'}),
                html.H2(perf_status.title(), style={'color': perf_color, 'margin': '0'}),
                html.P(f"CPU: {performance.get('cpu', {}).get('percent', 0):.1f}% | " +
                       f"RAM: {performance.get('memory', {}).get('percent_used', 0):.1f}%", 
                       style={'color': '#7f8c8d', 'margin': '5px 0'})
            ], className='stat-card', style={'border-left': f'4px solid {perf_color}'}),
            
            # Background Process
            html.Div([
                html.H3("🔄 Auto-Fetcher", style={'color': '#2c3e50', 'margin': '0 0 10px 0'}),
                html.H2(fetch_status.title(), style={'color': fetch_color, 'margin': '0'}),
                html.P(f"Última ejecución: {fetcher.get('last_fetch', 'Nunca')[:10] if fetcher.get('last_fetch') != 'Nunca' else 'Nunca'}", 
                       style={'color': '#7f8c8d', 'margin': '5px 0'})
            ], className='stat-card', style={'border-left': f'4px solid {fetch_color}'})
            
        ], style={
            'display': 'grid',
            'gridTemplateColumns': 'repeat(auto-fit, minmax(250px, 1fr))',
            'gap': '20px'
        })
        
        return cards
        
    except Exception as e:
        logger.error(f"Error creating developer metrics cards: {e}")
        return html.Div([
            html.H3("❌ Error", style={'color': '#e74c3c'}),
            html.P(f"Error creando tarjetas: {str(e)}")
        ])

def create_system_info_section(metrics):
    """Crear sección de información del sistema"""
    try:
        performance = metrics.get('performance', {})
        bg_process = metrics.get('background_process', {})
        
        if performance.get('status') != 'active':
            return html.Div([
                html.H3("💻 Información del Sistema", style={'color': '#2c3e50'}),
                html.P(performance.get('message', 'Información no disponible'), style={'color': '#7f8c8d'})
            ])
        
        memory = performance.get('memory', {})
        disk = performance.get('disk', {})
        cpu = performance.get('cpu', {})
        fetcher = bg_process.get('fetcher', {})
        
        info_section = html.Div([
            html.H3("💻 Información del Sistema", style={'color': '#2c3e50', 'marginBottom': '20px'}),
            
            html.Div([
                # Columna izquierda - Recursos
                html.Div([
                    html.H4("🖥️ Recursos", style={'color': '#34495e', 'marginBottom': '15px'}),
                    html.P(f"• Memoria Total: {memory.get('total_gb', 0)} GB", style={'margin': '8px 0'}),
                    html.P(f"• Memoria Disponible: {memory.get('available_gb', 0)} GB", style={'margin': '8px 0'}),
                    html.P(f"• Uso de Memoria: {memory.get('percent_used', 0):.1f}%", style={'margin': '8px 0'}),
                    html.P(f"• Proceso Dashboard: {memory.get('process_mb', 0)} MB", style={'margin': '8px 0'}),
                    html.P(f"• Espacio en Disco: {disk.get('free_gb', 0):.1f} GB libre de {disk.get('total_gb', 0)} GB", style={'margin': '8px 0'}),
                    html.P(f"• Uso de CPU: {cpu.get('percent', 0):.1f}%", style={'margin': '8px 0'})
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                
                # Columna derecha - Procesos
                html.Div([
                    html.H4("🔄 Procesos de Fondo", style={'color': '#34495e', 'marginBottom': '15px'}),
                    html.P(f"• Estado del Fetcher: {fetcher.get('status', 'unknown').title()}", style={'margin': '8px 0'}),
                    html.P(f"• Archivos Obtenidos: {fetcher.get('files_fetched', 0)}", style={'margin': '8px 0'}),
                    html.P(f"• Archivos Actualizados: {fetcher.get('files_updated', 0)}", style={'margin': '8px 0'}),
                    html.P(f"• Duración del Último Fetch: {fetcher.get('fetch_duration', 0):.1f}s", style={'margin': '8px 0'}),
                    html.P(f"• Próxima Ejecución: {fetcher.get('next_estimated', 'Desconocido')[:16] if fetcher.get('next_estimated') != 'Unknown' else 'Desconocido'}", style={'margin': '8px 0'}),
                    html.P(f"• Errores Recientes: {fetcher.get('recent_errors', 0)}", style={'margin': '8px 0'})
                ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '4%'})
            ])
        ], style={'background': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px'})
        
        return info_section
        
    except Exception as e:
        logger.error(f"Error creating system info section: {e}")
        return html.Div([
            html.H3("❌ Error", style={'color': '#e74c3c'}),
            html.P(f"Error creando información del sistema: {str(e)}")
        ])

# CSS personalizado
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
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
                border-left: 4px solid #3498db;
            }
            .stat-card:hover {
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                transform: translateY(-2px);
                transition: all 0.3s ease;
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

if __name__ == '__main__':
    try:
        # Initialize logging system
        setup_all_loggers()
        logger = get_dashboard_logger()
        
        # Log startup
        logger.info("="*60)
        logger.info("INICIANDO PANEL DE CONTROL DE CALIDAD DEL AIRE USACH")
        logger.info("="*60)
        
        print("Iniciando Panel de Control de Calidad del Aire USACH...")
        print(f"El panel estará disponible en: http://localhost:{PORT}")
        
        # Start background data fetcher
        print("Iniciando servicio de descarga automática de datos...")
        scheduler = start_background_fetcher()
        print("✓ Datos se actualizarán automáticamente cada 10 minutos")
        
        # Display features
        print("Características del panel:")
        print("   - Resumen General (Pestaña 1)")
        print("   - Análisis de Sensor Específico (Pestaña 2)")
        print("   - Estado de Sensores (Pestaña 3)")
        print("   - Actualización automática de datos en segundo plano")
        print("Presione Ctrl+C para detener el servidor")
        print("-" * 60)
        
        logger.info(f"Panel iniciado en puerto {PORT}")
        logger.info("Servicio de descarga automática activado")
        
        # Start the Dash app
        app.run(host='0.0.0.0', port=PORT, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Interrupción de usuario detectada")
        print("\n✓ Deteniendo el servidor...")
        stop_background_fetcher(scheduler)
        logger.info("Servidor detenido correctamente")
        
    except Exception as e:
        logger.critical(f"Error crítico al iniciar la aplicación: {e}", exc_info=True)
        print(f"\n✗ Error crítico: {e}")
        print("Revise los logs para más detalles")
        
    finally:
        logger.info("="*60)
        logger.info("PANEL DE CONTROL FINALIZADO")
        logger.info("="*60)
