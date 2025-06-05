import logging
import logging.handlers
import os
import json
from datetime import datetime
from .settings import get_chile_time

# Create logs directory structure
LOGS_BASE_DIR = "logs"
LOG_DIRS = [
    "logs/dashboard",
    "logs/data_fetching", 
    "logs/data_processing",
    "logs/system",
    "logs/archive"
]

# Ensure log directories exist
for log_dir in LOG_DIRS:
    os.makedirs(log_dir, exist_ok=True)

class ChileTimezoneFormatter(logging.Formatter):
    """Custom formatter that uses Chile timezone for all log entries"""
    
    def formatTime(self, record, datefmt=None):
        # Get current time in Chile timezone
        chile_time = get_chile_time()
        if datefmt:
            return chile_time.strftime(datefmt)
        else:
            return chile_time.strftime('%Y-%m-%d %H:%M:%S CLT')
    
    def format(self, record):
        # Add Chile timestamp to record
        record.chile_time = get_chile_time().isoformat()
        return super().format(record)

class StructuredJsonFormatter(ChileTimezoneFormatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': get_chile_time().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry['extra'] = record.extra_data
            
        return json.dumps(log_entry, ensure_ascii=False)

def setup_component_logger(component_name, log_level=logging.INFO, include_json=False):
    """
    Setup a logger for a specific component with appropriate handlers
    
    Args:
        component_name: Name of the component (dashboard, data_fetching, data_processing, system)
        log_level: Logging level (default: INFO)
        include_json: Whether to include JSON formatted logs (default: False)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(component_name)
    logger.setLevel(log_level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatters
    standard_formatter = ChileTimezoneFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    json_formatter = StructuredJsonFormatter()
    
    # Get current date for log file naming
    current_date = get_chile_time().strftime('%Y%m%d')
    
    # Standard log file (all levels)
    log_file = f"logs/{component_name}/{component_name}_{current_date}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=50*1024*1024,  # 50MB
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(standard_formatter)
    logger.addHandler(file_handler)
    
    # Error-only log file
    error_log_file = f"logs/{component_name}/{component_name}_errors_{current_date}.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(standard_formatter)
    logger.addHandler(error_handler)
    
    # JSON log file (optional)
    if include_json:
        json_log_file = f"logs/{component_name}/{component_name}_structured_{current_date}.json"
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=50*1024*1024,  # 50MB
            backupCount=7,
            encoding='utf-8'
        )
        json_handler.setLevel(log_level)
        json_handler.setFormatter(json_formatter)
        logger.addHandler(json_handler)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
    console_handler.setFormatter(ChileTimezoneFormatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    # Critical errors go to a special never-rotating file
    critical_handler = logging.FileHandler(
        'logs/critical.log',
        encoding='utf-8'
    )
    critical_handler.setLevel(logging.CRITICAL)
    critical_handler.setFormatter(standard_formatter)
    logger.addHandler(critical_handler)
    
    return logger

def log_performance_metric(logger, operation, duration_seconds, extra_data=None):
    """
    Log performance metrics in a standardized way
    
    Args:
        logger: Logger instance
        operation: Description of the operation
        duration_seconds: Time taken in seconds
        extra_data: Additional data to log
    """
    message = f"Performance: {operation} completed in {duration_seconds:.3f}s"
    
    if extra_data:
        # Add extra data to the log record
        logger.info(message, extra={'extra_data': extra_data})
    else:
        logger.info(message)

def log_data_operation(logger, operation_type, file_count=None, success_count=None, error_count=None, details=None):
    """
    Log data operations (fetch, process, etc.) in a standardized way
    
    Args:
        logger: Logger instance
        operation_type: Type of operation (fetch, process, validate, etc.)
        file_count: Total number of files involved
        success_count: Number of successful operations
        error_count: Number of failed operations
        details: Additional details dictionary
    """
    message = f"Data {operation_type}"
    
    extra_data = {
        'operation_type': operation_type
    }
    
    if file_count is not None:
        message += f" - {file_count} files"
        extra_data['file_count'] = file_count
        
    if success_count is not None:
        message += f" ({success_count} success"
        extra_data['success_count'] = success_count
        
        if error_count is not None:
            message += f", {error_count} errors)"
            extra_data['error_count'] = error_count
        else:
            message += ")"
    
    if details:
        extra_data.update(details)
    
    level = logging.ERROR if error_count and error_count > 0 else logging.INFO
    
    if level == logging.ERROR:
        logger.error(message, extra={'extra_data': extra_data})
    else:
        logger.info(message, extra={'extra_data': extra_data})

# Pre-configured loggers for common components
dashboard_logger = None
data_fetching_logger = None
data_processing_logger = None
system_logger = None

def get_dashboard_logger():
    """Get or create dashboard logger"""
    global dashboard_logger
    if dashboard_logger is None:
        dashboard_logger = setup_component_logger('dashboard', include_json=True)
    return dashboard_logger

def get_data_fetching_logger():
    """Get or create data fetching logger"""
    global data_fetching_logger
    if data_fetching_logger is None:
        data_fetching_logger = setup_component_logger('data_fetching', include_json=True)
    return data_fetching_logger

def get_data_processing_logger():
    """Get or create data processing logger"""
    global data_processing_logger
    if data_processing_logger is None:
        data_processing_logger = setup_component_logger('data_processing')
    return data_processing_logger

def get_system_logger():
    """Get or create system logger"""
    global system_logger
    if system_logger is None:
        system_logger = setup_component_logger('system')
    return system_logger

def setup_all_loggers():
    """Initialize all loggers - call this at application startup"""
    get_dashboard_logger()
    get_data_fetching_logger() 
    get_data_processing_logger()
    get_system_logger()
    
    # Log the initialization
    system_logger = get_system_logger()
    system_logger.info("Logging system initialized with Chile timezone")
    system_logger.info(f"Log directories created: {LOG_DIRS}") 