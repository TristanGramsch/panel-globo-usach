#!/bin/bash

# USACH Environmental Monitoring System - Startup Script
# This script activates the virtual environment and starts the monitoring system

echo "🌍 USACH Environmental Monitoring System"
echo "========================================"

# Check if virtual environment exists
if [ -d "piloto_env" ]; then
    echo "📦 Activating virtual environment..."
    source piloto_env/bin/activate
else
    echo "⚠️ Virtual environment not found!"
    echo "💡 Create it with: python -m venv piloto_env"
    echo "💡 Then run: source piloto_env/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if requirements are installed
echo "🔍 Checking dependencies..."
python -c "import requests, pandas, matplotlib, flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the monitoring system
echo "🚀 Starting monitoring system..."
python start_monitoring.py 