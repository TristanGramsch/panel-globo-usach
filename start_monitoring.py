#!/usr/bin/env python3
"""
USACH Environmental Monitoring - Startup Script
Fetches latest data and starts the web dashboard
"""

import subprocess
import sys
import os
import time
from datetime import datetime

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("🌍 USACH ENVIRONMENTAL MONITORING SYSTEM")
    print("=" * 60)
    print(f"🕒 Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import requests
        import pandas
        import matplotlib
        import flask
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Run: pip install -r requirements.txt")
        return False

def fetch_latest_data():
    """Fetch the latest data from the server"""
    print("📡 Fetching latest environmental data...")
    try:
        result = subprocess.run([sys.executable, "fetch_piloto_files.py"], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Data fetch completed successfully")
            # Print summary from the output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'SUMMARY' in line or 'Files found:' in line or 'Files downloaded:' in line:
                    print(f"   {line}")
            return True
        else:
            print(f"⚠️ Data fetch completed with warnings")
            print(f"   Exit code: {result.returncode}")
            return True  # Continue anyway, might have partial data
            
    except subprocess.TimeoutExpired:
        print("⏰ Data fetch timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error during data fetch: {e}")
        return False

def start_dashboard():
    """Start the web dashboard"""
    print("🌐 Starting web dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("📈 Charts available at: http://localhost:5000/chart")
    print("🔗 API available at: http://localhost:5000/api/data")
    print()
    print("💡 Tips:")
    print("   - Dashboard auto-refreshes every 5 minutes")
    print("   - Press Ctrl+C to stop the server")
    print("   - Run this script again to update data and restart")
    print()
    print("🚀 Starting server...")
    print("-" * 60)
    
    try:
        # Start the web dashboard
        subprocess.run([sys.executable, "web_dashboard.py"])
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")

def main():
    """Main startup function"""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check if data directory exists
    if not os.path.exists("piloto_data"):
        print("📁 Creating data directory...")
        os.makedirs("piloto_data", exist_ok=True)
    
    # Check if logs directory exists
    if not os.path.exists("logs"):
        print("📁 Creating logs directory...")
        os.makedirs("logs", exist_ok=True)
    
    # Fetch latest data
    data_success = fetch_latest_data()
    
    if not data_success:
        print("⚠️ Data fetch failed, but continuing with existing data...")
    
    print()
    
    # Check if we have any data
    data_files = []
    if os.path.exists("piloto_data"):
        data_files = [f for f in os.listdir("piloto_data") if f.endswith('.dat')]
    
    if not data_files:
        print("⚠️ No data files found!")
        print("💡 The dashboard will show 'No data available'")
        print("   Try running 'python fetch_piloto_files.py' manually")
    else:
        print(f"📊 Found {len(data_files)} data files")
    
    print()
    
    # Start the dashboard
    start_dashboard()

if __name__ == "__main__":
    main() 