#!/bin/bash

# USACH Environmental Monitoring System - Startup Script
# Simple startup script for the air quality monitoring dashboard

echo "=================================================="
echo "USACH Environmental Monitoring System - Startup"
echo "=================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found. Please run this script from the project root directory."
    exit 1
fi

echo "✓ Python 3 found"
echo "✓ Project directory verified"

# Check for required modules
echo ""
echo "Checking dependencies..."
python3 -c "import dash, plotly, pandas, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠ Warning: Some dependencies may be missing"
    echo "Installing requirements..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

echo "✓ Dependencies verified"

# Fetch latest data
echo ""
echo "Fetching latest air quality data..."
if [ -f "data/fetch_piloto_files.py" ]; then
    cd data
    python3 fetch_piloto_files.py
    cd ..
    echo "✓ Data fetch completed"
else
    echo "⚠ Warning: Data fetcher not found, using existing data"
fi

# Check for data files
echo ""
echo "Checking for data files..."
DATA_COUNT=$(find . -name "*.dat" -type f 2>/dev/null | wc -l)
if [ $DATA_COUNT -eq 0 ]; then
    echo "⚠ Warning: No .dat files found. Dashboard will show limited functionality."
else
    echo "✓ Found $DATA_COUNT data files"
fi

# Start the dashboard
echo ""
echo "=================================================="
echo "Starting USACH Air Quality Dashboard..."
echo "=================================================="
echo ""
echo "Dashboard will be available at: http://localhost:8050"
echo "Press Ctrl+C to stop the dashboard"
echo ""

# Run the new modular app
python3 app.py 