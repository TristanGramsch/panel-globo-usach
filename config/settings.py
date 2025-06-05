#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Configuration Settings
Central configuration for WHO guidelines, paths, and application constants
"""

from pathlib import Path
from datetime import timedelta, datetime, timezone
import json

# Project Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'piloto_data'
LOGS_DIR = PROJECT_ROOT / 'logs'
DATA_STATUS_FILE = PROJECT_ROOT / 'data_status.json'

# Data Fetching Configuration
DATA_FETCH_INTERVAL_MINUTES = 10  # How often to fetch data
DATA_SERVER_URL = "http://ambiente.usach.cl/globo/"
DATA_FETCH_TIMEOUT_SECONDS = 30

# Timezone Configuration
# Chile Standard Time (CLT) - UTC-3 (Chile stopped observing DST in 2019)
CHILE_TIMEZONE = timezone(timedelta(hours=-3))

def get_chile_time():
    """Get current time in Chile timezone (CLT, UTC-3)"""
    return datetime.now(CHILE_TIMEZONE)

def format_chile_time(dt=None, format_str='%Y-%m-%d %H:%M:%S'):
    """Format datetime in Chile timezone with timezone label"""
    if dt is None:
        dt = get_chile_time()
    elif dt.tzinfo is None:
        # Convert naive datetime to Chile timezone
        dt = dt.replace(tzinfo=CHILE_TIMEZONE)
    elif dt.tzinfo != CHILE_TIMEZONE:
        # Convert from other timezone to Chile timezone
        dt = dt.astimezone(CHILE_TIMEZONE)
    
    return f"{dt.strftime(format_str)} CLT"

def get_chile_date():
    """Get current date in Chile timezone"""
    return get_chile_time().date()

# Data Status Management
def get_data_status():
    """Get current data fetching status"""
    try:
        if DATA_STATUS_FILE.exists():
            with open(DATA_STATUS_FILE, 'r', encoding='utf-8') as f:
                status = json.load(f)
                # Convert ISO timestamps back to datetime objects
                if 'last_fetch_time' in status and status['last_fetch_time']:
                    status['last_fetch_time'] = datetime.fromisoformat(status['last_fetch_time'].replace('Z', '+00:00'))
                if 'last_success_time' in status and status['last_success_time']:
                    status['last_success_time'] = datetime.fromisoformat(status['last_success_time'].replace('Z', '+00:00'))
                return status
    except Exception as e:
        pass
    
    # Return default status if file doesn't exist or has errors
    return {
        'last_fetch_time': None,
        'last_success_time': None,
        'status': 'never_fetched',
        'files_fetched': 0,
        'files_updated': 0,
        'errors': [],
        'fetch_duration_seconds': 0
    }

def update_data_status(status, fetch_time=None, success=True, files_fetched=0, files_updated=0, error_msg=None, duration=0):
    """Update data fetching status"""
    try:
        current_status = get_data_status()
        
        if fetch_time is None:
            fetch_time = get_chile_time()
        
        # Update status
        current_status['last_fetch_time'] = fetch_time
        current_status['files_fetched'] = files_fetched
        current_status['files_updated'] = files_updated
        current_status['fetch_duration_seconds'] = duration
        
        if success:
            current_status['status'] = 'success'
            current_status['last_success_time'] = fetch_time
            current_status['errors'] = []  # Clear errors on success
        else:
            current_status['status'] = 'error'
            if error_msg:
                if 'errors' not in current_status:
                    current_status['errors'] = []
                current_status['errors'].append({
                    'time': fetch_time.isoformat(),
                    'message': error_msg
                })
                # Keep only last 5 errors
                current_status['errors'] = current_status['errors'][-5:]
        
        # Convert datetime objects to ISO strings for JSON storage
        status_to_save = current_status.copy()
        if status_to_save['last_fetch_time']:
            status_to_save['last_fetch_time'] = status_to_save['last_fetch_time'].isoformat()
        if status_to_save['last_success_time']:
            status_to_save['last_success_time'] = status_to_save['last_success_time'].isoformat()
        
        # Save to file
        with open(DATA_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status_to_save, f, indent=2, ensure_ascii=False)
            
        return True
    except Exception as e:
        return False

def get_data_freshness():
    """Get information about how fresh the data is"""
    status = get_data_status()
    current_time = get_chile_time()
    
    if not status['last_success_time']:
        return {
            'status': 'no_data',
            'message': 'No se han obtenido datos del servidor',
            'age_minutes': None,
            'last_update': 'Nunca'
        }
    
    age = current_time - status['last_success_time']
    age_minutes = age.total_seconds() / 60
    
    if age_minutes < DATA_FETCH_INTERVAL_MINUTES * 1.5:  # Allow 50% tolerance
        freshness_status = 'fresh'
        message = f'Datos actualizados (hace {int(age_minutes)} minutos)'
    elif age_minutes < DATA_FETCH_INTERVAL_MINUTES * 3:
        freshness_status = 'stale'
        message = f'Datos un poco desactualizados (hace {int(age_minutes)} minutos)'
    else:
        freshness_status = 'very_stale'
        message = f'Datos muy desactualizados (hace {int(age_minutes)} minutos)'
    
    return {
        'status': freshness_status,
        'message': message,
        'age_minutes': age_minutes,
        'last_update': format_chile_time(status['last_success_time'])
    }

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

def get_developer_metrics():
    """
    Get comprehensive developer metrics for system monitoring
    """
    current_time = get_chile_time()
    
    # Get basic data status
    data_status = get_data_status()
    data_freshness = get_data_freshness()
    
    # Log file analysis
    log_stats = get_log_statistics()
    
    # System performance metrics
    performance_stats = get_system_performance()
    
    # Background process status
    process_status = get_background_process_status()
    
    return {
        'timestamp': format_chile_time(current_time),
        'data_pipeline': {
            'status': data_status,
            'freshness': data_freshness
        },
        'logs': log_stats,
        'performance': performance_stats,
        'background_process': process_status,
        'system_health': calculate_system_health_score(data_status, log_stats, performance_stats)
    }

def get_log_statistics():
    """
    Get statistics about log files and recent activity
    """
    import os
    from pathlib import Path
    
    logs_dir = Path('logs')
    if not logs_dir.exists():
        return {'status': 'no_logs', 'message': 'Logs directory not found'}
    
    try:
        # Get log file sizes and counts
        components = ['dashboard', 'data_fetching', 'data_processing', 'system']
        log_stats = {}
        
        today = get_chile_time().strftime('%Y%m%d')
        total_size = 0
        total_files = 0
        recent_errors = []
        
        for component in components:
            component_dir = logs_dir / component
            if component_dir.exists():
                files = list(component_dir.glob('*.log'))
                size = sum(f.stat().st_size for f in files) / (1024 * 1024)  # MB
                
                # Check for today's error log
                error_log = component_dir / f"{component}_errors_{today}.log"
                error_count = 0
                if error_log.exists() and error_log.stat().st_size > 0:
                    try:
                        with open(error_log, 'r') as f:
                            error_count = len(f.readlines())
                            if error_count > 0:
                                recent_errors.append({
                                    'component': component,
                                    'count': error_count
                                })
                    except:
                        pass
                
                log_stats[component] = {
                    'files': len(files),
                    'size_mb': round(size, 2),
                    'errors_today': error_count
                }
                
                total_size += size
                total_files += len(files)
        
        return {
            'status': 'active',
            'total_size_mb': round(total_size, 2),
            'total_files': total_files,
            'components': log_stats,
            'recent_errors': recent_errors,
            'last_check': format_chile_time()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error reading logs: {str(e)}',
            'last_check': format_chile_time()
        }

def get_system_performance():
    """
    Get system performance metrics
    """
    try:
        import psutil
        import os
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage for logs directory
        disk_usage = psutil.disk_usage('.')
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Process info
        process = psutil.Process(os.getpid())
        
        return {
            'status': 'active',
            'memory': {
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'percent_used': memory.percent,
                'process_mb': round(process.memory_info().rss / (1024**2), 2)
            },
            'disk': {
                'total_gb': round(disk_usage.total / (1024**3), 2),
                'free_gb': round(disk_usage.free / (1024**3), 2),
                'percent_used': round((disk_usage.used / disk_usage.total) * 100, 1)
            },
            'cpu': {
                'percent': cpu_percent,
                'process_percent': round(process.cpu_percent(), 2)
            },
            'last_check': format_chile_time()
        }
        
    except ImportError:
        return {
            'status': 'unavailable',
            'message': 'psutil not available - install with: pip install psutil',
            'last_check': format_chile_time()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error getting performance metrics: {str(e)}',
            'last_check': format_chile_time()
        }

def get_background_process_status():
    """
    Get status of background processes
    """
    try:
        # Check if we have recent fetch activity
        data_status = get_data_status()
        
        # Estimate next fetch time (every 10 minutes from last attempt)
        next_fetch = "Unknown"
        if data_status.get('last_fetch_time'):
            last_fetch = parse_chile_time(data_status['last_fetch_time'])
            next_estimated = last_fetch + timedelta(minutes=10)
            next_fetch = format_chile_time(next_estimated)
        
        # Background fetcher status
        fetcher_status = {
            'status': 'running' if data_status.get('last_fetch_time') else 'unknown',
            'last_fetch': data_status.get('last_fetch_time', 'Never'),
            'last_success': data_status.get('last_success_time', 'Never'),
            'next_estimated': next_fetch,
            'files_fetched': data_status.get('files_fetched', 0),
            'files_updated': data_status.get('files_updated', 0),
            'recent_errors': len(data_status.get('errors', [])),
            'fetch_duration': data_status.get('fetch_duration_seconds', 0)
        }
        
        return {
            'fetcher': fetcher_status,
            'last_check': format_chile_time()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error getting background process status: {str(e)}',
            'last_check': format_chile_time()
        }

def calculate_system_health_score(data_status, log_stats, performance_stats):
    """
    Calculate overall system health score (0-100)
    """
    try:
        score = 100
        
        # Data pipeline health (40% weight)
        if data_status.get('status') == 'never_fetched':
            score -= 40
        elif data_status.get('status') == 'error':
            score -= 30
        elif len(data_status.get('errors', [])) > 0:
            score -= 10
        
        # Log health (20% weight)
        if log_stats.get('status') == 'error':
            score -= 20
        elif len(log_stats.get('recent_errors', [])) > 5:
            score -= 15
        elif len(log_stats.get('recent_errors', [])) > 0:
            score -= 5
        
        # Performance health (40% weight)
        if performance_stats.get('status') == 'error':
            score -= 20
        elif performance_stats.get('status') == 'active':
            memory_usage = performance_stats.get('memory', {}).get('percent_used', 0)
            disk_usage = performance_stats.get('disk', {}).get('percent_used', 0)
            cpu_usage = performance_stats.get('cpu', {}).get('percent', 0)
            
            if memory_usage > 90:
                score -= 15
            elif memory_usage > 80:
                score -= 10
            
            if disk_usage > 95:
                score -= 15
            elif disk_usage > 90:
                score -= 10
            
            if cpu_usage > 90:
                score -= 10
            elif cpu_usage > 80:
                score -= 5
        
        return max(0, min(100, score))
        
    except Exception:
        return 50  # Default middle score if calculation fails

def get_recent_log_entries(component='all', level='ERROR', limit=10):
    """
    Get recent log entries for debugging
    """
    from pathlib import Path
    import re
    
    logs_dir = Path('logs')
    today = get_chile_time().strftime('%Y%m%d')
    entries = []
    
    try:
        components = ['dashboard', 'data_fetching', 'data_processing', 'system'] if component == 'all' else [component]
        
        for comp in components:
            comp_dir = logs_dir / comp
            if not comp_dir.exists():
                continue
                
            log_file = comp_dir / f"{comp}_{today}.log"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        
                    for line in reversed(lines[-100:]):  # Check last 100 lines
                        if level in line or level == 'ALL':
                            # Extract timestamp, level, and message
                            match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) CLT - (\w+) - (\w+) - (.+)', line.strip())
                            if match:
                                timestamp, logger, log_level, message = match.groups()
                                entries.append({
                                    'timestamp': timestamp,
                                    'component': comp,
                                    'level': log_level,
                                    'message': message
                                })
                                
                                if len(entries) >= limit:
                                    break
                except Exception:
                    continue
                    
            if len(entries) >= limit:
                break
        
        # Sort by timestamp (most recent first)
        entries.sort(key=lambda x: x['timestamp'], reverse=True)
        return entries[:limit]
        
    except Exception as e:
        return [{'timestamp': format_chile_time(), 'component': 'system', 'level': 'ERROR', 
                'message': f'Error reading log entries: {str(e)}'}] 