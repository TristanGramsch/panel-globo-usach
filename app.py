#!/usr/bin/env python3
"""
USACH Environmental Monitoring Dashboard
Main application entry point
"""

import sys
import logging
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import dash
    from dash import html
    
    # Import our modules
    from config.settings import DASHBOARD_TITLE, DEFAULT_PORT, DEBUG_MODE
    from dashboard.layouts import create_main_layout, create_error_layout
    from dashboard.callbacks import register_callbacks
    from data.processors import get_available_sensors
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('dashboard.log')
    ]
)

logger = logging.getLogger(__name__)

def create_app():
    """
    Create and configure the Dash application
    
    Returns:
        dash.Dash: Configured Dash app
    """
    try:
        # Initialize Dash app
        app = dash.Dash(__name__, title=DASHBOARD_TITLE)
        
        # Suppress callback exceptions for dynamic content
        app.config.suppress_callback_exceptions = True
        
        # Check if we have data and sensors available
        available_sensors = get_available_sensors()
        
        if not available_sensors:
            logger.warning("No sensors found in data directory")
            app.layout = create_error_layout(
                "No Data Available",
                "No sensor data files were found. Please check that data files exist in the data directory."
            )
        else:
            logger.info(f"Found {len(available_sensors)} sensors: {available_sensors}")
            # Set main layout
            app.layout = create_main_layout()
            
            # Register callbacks
            register_callbacks(app)
        
        return app
        
    except Exception as e:
        logger.error(f"Error creating app: {e}")
        # Create minimal error app
        app = dash.Dash(__name__, title="Error - USACH Monitor")
        app.layout = create_error_layout(
            "Application Error",
            f"Failed to initialize dashboard: {str(e)}"
        )
        return app

def main():
    """
    Main function to run the dashboard
    """
    try:
        logger.info("Starting USACH Environmental Monitoring Dashboard...")
        
        # Create the app
        app = create_app()
        
        # Run the server
        logger.info(f"Dashboard starting on http://localhost:{DEFAULT_PORT}")
        app.run_server(
            debug=DEBUG_MODE,
            host='0.0.0.0',
            port=DEFAULT_PORT,
            dev_tools_hot_reload=DEBUG_MODE
        )
        
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user")
    except Exception as e:
        logger.error(f"Error running dashboard: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 