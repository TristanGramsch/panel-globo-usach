#!/bin/bash

# USACH Environmental Monitoring System - Startup Script
# This script starts the unified monitoring dashboard

echo "🌍 USACH Environmental Monitoring System"
echo "========================================"
echo ""

# Check if conda environment exists
if conda env list | grep -q "usach-monitor"; then
    echo "✅ Conda environment 'usach-monitor' found"
    echo "🔄 Activating environment..."
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate usach-monitor
else
    echo "❌ Conda environment 'usach-monitor' not found"
    echo "💡 Please run: conda env create -f environment.yml"
    exit 1
fi

# Check if required directories exist
echo "📁 Checking directories..."
mkdir -p logs
mkdir -p piloto_data

# Start the application
echo "🚀 Starting USACH Environmental Monitoring Dashboard..."
echo "📊 Dashboard will be available at: http://localhost:8050"
echo "🔄 Data fetching and dashboard refresh every 10 minutes"
echo ""
echo "💡 Press Ctrl+C to stop the application"
echo "----------------------------------------"

python main.py 