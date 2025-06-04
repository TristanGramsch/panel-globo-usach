#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Configuration Settings
Central configuration for WHO guidelines, paths, and application constants
"""

from pathlib import Path
from datetime import timedelta

# Project Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'piloto_data'
LOGS_DIR = PROJECT_ROOT / 'logs'

# Dashboard Configuration
DEFAULT_PORT = 8050
DASHBOARD_PORT = 8050  # Keep for backward compatibility
DASHBOARD_TITLE = "Monitor de Calidad del Aire USACH"
AUTO_REFRESH_INTERVAL = 10 * 60 * 1000  # 10 minutes in milliseconds
DEBUG_MODE = False

# WHO Air Quality Guidelines (MP1.0 μg/m³) - Spanish Labels
WHO_GUIDELINES = {
    'good_max': 15,
    'moderate_max': 25,
    'unhealthy_sensitive_max': 35,
    'unhealthy_max': 75,
    'very_unhealthy_max': 150,
    'good': {'max': 15, 'color': '#27ae60', 'label': 'Buena', 'risk': 'Riesgo para la salud muy bajo'},
    'moderate': {'max': 25, 'color': '#f39c12', 'label': 'Moderada', 'risk': 'Riesgo para la salud bajo'},
    'unhealthy_sensitive': {'max': 35, 'color': '#e67e22', 'label': 'Dañina para Grupos Sensibles', 'risk': 'Riesgo para la salud moderado'},
    'unhealthy': {'max': 75, 'color': '#e74c3c', 'label': 'Dañina', 'risk': 'Riesgo para la salud alto'},
    'very_unhealthy': {'max': float('inf'), 'color': '#8e44ad', 'label': 'Muy Dañina', 'risk': 'Riesgo para la salud muy alto'}
}

# Chart Configuration
CHART_COLORS = [
    '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
    '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#16a085'
]

# Data Processing
VALID_FILE_EXTENSIONS = ['.dat']
MIN_FILE_SIZE_BYTES = 100
MAX_PROCESSING_TIME_SECONDS = 300

# Error Messages - Spanish
ERROR_MESSAGES = {
    'no_data': "No hay datos disponibles. Ejecute 'python fetch_piloto_files.py' para descargar datos.",
    'processing_error': "Hubo un error procesando los datos de calidad del aire. Por favor revise los registros.",
    'sensor_not_found': "Datos del sensor seleccionado no encontrados.",
    'date_range_empty': "No hay datos disponibles para el rango de fechas seleccionado."
}

# CSS Styles
CSS_STYLES = {
    'stat_card': {
        'background': 'white',
        'padding': '20px',
        'borderRadius': '10px',
        'textAlign': 'center',
        'boxShadow': '0 2px 10px rgba(0,0,0,0.1)'
    },
    'tab_content': {
        'padding': '20px'
    },
    'grid_layout': {
        'display': 'grid',
        'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))',
        'gap': '20px',
        'margin': '20px 0'
    }
} 