# USACH Environmental Monitoring System

A minimal, production-ready system for monitoring air quality sensors throughout Chile. This system automatically fetches sensor data, provides real-time dashboard visualization with **three specialized tabs**, and tracks sensor health for maintenance planning.

## 🎯 Purpose

**Client**: Professor Ernesto Gramsch, USACH University  
**Goal**: Monitor pollution sensors to determine maintenance priorities and sensor health status

## ✨ Key Features

### 🔄 Automatic Data Management
- **Continuous data fetching** from `http://ambiente.usach.cl/globo/` every 10 minutes
- **Smart file management** - downloads only new/updated sensor files
- **Server health monitoring** with automatic retry logic
- **Robust error handling** for unreliable server connections

### 📊 Three-Tab Dashboard Interface
1. **General Overview Tab**: Live air quality monitoring with WHO guideline compliance for all sensors
2. **Sensor Specific Tab**: Detailed analysis and charts for individual sensors
3. **Sensor Health Tab**: Comprehensive maintenance overview and sensor status tracking

### 🔧 Sensor Health Monitoring
- **Daily operational status** for each sensor with detailed metrics
- **Data completeness tracking** and quality assessment
- **Maintenance priority indicators** with data points count
- **Historical performance analysis** with last reading timestamps

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Conda (recommended) or pip

### Installation

#### Option 1: Conda (Recommended)
```bash
# Clone the repository
git clone <repository-url>
cd panel-globo-usach

# Create conda environment
conda env create -f environment.yml
conda activate usach-monitor

# Run the application
python main.py
```

#### Option 2: pip
```bash
# Clone the repository
git clone <repository-url>
cd panel-globo-usach

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Access Dashboard
Open your browser and navigate to: **http://localhost:8050**

## 📁 Project Structure (Minimal)

```
panel-globo-usach/
├── main.py                    # 🎯 Single entry point - runs everything
├── environment.yml            # 📦 Conda environment specification
├── requirements.txt           # 📦 pip dependencies (minimal)
├── README.md                  # 📖 This documentation
│
├── config/
│   └── settings.py           # ⚙️ All configuration settings
│
├── data/
│   ├── fetch_piloto_files.py # 📡 Data fetching from server
│   └── processors.py         # 🔄 Data parsing and processing
│
├── utils/
│   └── helpers.py            # 🛠️ Utility functions
│
├── piloto_data/              # 📊 Downloaded sensor data (auto-created)
└── logs/                     # 📝 Application logs (auto-created)
```

## 🔧 Configuration

### Key Settings (config/settings.py)
- **Data refresh interval**: 10 minutes
- **Dashboard port**: 8050
- **WHO air quality guidelines**: Built-in compliance checking
- **Server URL**: `http://ambiente.usach.cl/globo/`

### Environment Variables
No environment variables required - all settings are in `config/settings.py`

## 📊 Dashboard Features

### Tab 1: General Overview
- **Status Overview Cards**: Average MP1.0, maximum readings, sensor count, last update
- **Multi-sensor Chart**: Real-time trends for all sensors with WHO reference lines
- **Daily Status Summary**: Working vs non-working sensors for today

### Tab 2: Sensor Specific Analysis
- **Sensor Selection Dropdown**: Choose any available sensor for detailed analysis
- **Individual Sensor Charts**: High-resolution time series with markers
- **Detailed Statistics**: Data range, point count, min/max/average values
- **WHO Compliance Tracking**: Visual guidelines for selected sensor

### Tab 3: Sensor Health & Maintenance
- **Comprehensive Health Table**: All sensors with detailed status
- **Maintenance Indicators**: 
  - **Status**: Working/Not Working today
  - **Data Points Today**: Count of readings received
  - **Last Reading**: Timestamp of most recent data
  - **Average MP1.0**: Overall sensor performance
  - **Data Quality**: Excellent/Good/Fair/Poor/No Data
- **Priority Ranking**: Visual indicators for sensors requiring attention

## 🔄 How It Works

### 1. Automatic Data Collection
- Application starts background thread for data fetching
- Every 10 minutes: checks server health and downloads new/updated files
- Handles server outages gracefully with retry logic
- Logs all operations for monitoring

### 2. Real-Time Processing
- Parses downloaded `.dat` files automatically
- Extracts MP1.0 particulate matter readings
- Organizes data by sensor and timestamp
- Validates data completeness

### 3. Three-Tab Dashboard Updates
- **All tabs refresh** every 10 minutes automatically
- **General tab** shows live data as it becomes available
- **Sensor tab** updates when sensor selection changes
- **Health tab** tracks which sensors provided data today

## 🚨 Sensor Status Logic

### "Working Today" Criteria
A sensor is considered "working today" if:
- It has provided at least one data point today
- The data file is not empty
- The data is parseable and valid

### "Not Working Today" Criteria
A sensor needs attention if:
- No data received today
- Data file is empty or corrupted
- Parsing errors occur

### Data Quality Assessment
- **Excellent**: 100+ data points today
- **Good**: 50-99 data points today
- **Fair**: 10-49 data points today
- **Poor**: 1-9 data points today
- **No Data**: 0 data points today

## 📝 Logging

### Log Files
- **Main application**: `logs/main_application.log`
- **Data fetching**: `logs/piloto_fetcher_YYYYMMDD.log`

### Log Information
- Data fetch operations and results
- Server health status
- Processing errors and warnings
- Dashboard update cycles
- Tab-specific operations

## 🔧 Troubleshooting

### Common Issues

#### No Data Displayed
```bash
# Check if data directory exists and has files
ls -la piloto_data/

# Check recent logs
tail -f logs/main_application.log
```

#### Server Connection Issues
- Server `ambiente.usach.cl` is frequently unreliable
- Application automatically retries failed connections
- Check logs for server health status

#### Dashboard Not Updating
- Dashboard auto-refreshes every 10 minutes across all tabs
- Force refresh with browser reload (Ctrl+F5)
- Check background data fetching in logs

#### Tab-Specific Issues
- **General tab**: Check if multiple sensors have data
- **Sensor tab**: Verify selected sensor has data files
- **Health tab**: Check if sensor status calculation is working

### Manual Data Fetch
```bash
# Force immediate data update
python -c "from data.fetch_piloto_files import PilotoFileFetcher; PilotoFileFetcher().run_fetch_cycle()"
```

## 🚀 Production Deployment

### Server Requirements
- Python 3.11+
- 2GB RAM minimum
- Stable internet connection
- Port 8050 accessible

### Deployment Steps
1. Clone repository to server
2. Create conda environment: `conda env create -f environment.yml`
3. Activate environment: `conda activate usach-monitor`
4. Run application: `python main.py`
5. Access via server IP: `http://your-server-ip:8050`

### Process Management (Optional)
```bash
# Using systemd (Linux)
sudo systemctl enable usach-monitor
sudo systemctl start usach-monitor

# Using screen (simple)
screen -S usach-monitor python main.py
```

## 📊 Data Format

### Sensor Files
- **Format**: `Piloto{ID}-{DDMMYY}.dat`
- **Example**: `Piloto019-040625.dat` (Sensor 019, June 4, 2025)
- **Content**: CSV with MP1.0 readings, timestamps, and metadata

### Supported Sensors
Currently monitoring sensors: 013, 019, 023, 048, 052, 057, 078, 081, 098, 100, 102

## 🎨 Dashboard Navigation

### Tab Usage Guide
1. **Start with General Overview**: Get overall air quality status
2. **Use Sensor Specific**: Investigate individual sensor performance
3. **Check Sensor Health**: Plan maintenance visits and identify problems

### Key Performance Indicators
- **WHO Compliance**: Green/Orange/Red reference lines
- **Operational Status**: Percentage of working sensors
- **Data Quality**: Points per day indicator
- **Maintenance Priority**: Red = immediate attention needed

## 🤝 Support

### For Technical Issues
1. Check logs in `logs/` directory
2. Verify server connectivity
3. Ensure all dependencies are installed
4. Check specific tab functionality

### For Sensor Maintenance
- Use **Sensor Health tab** "Not Working Today" list to prioritize field visits
- Check **Data Quality** column to identify problematic sensors
- Monitor **Data Points Today** to detect partial failures
- Use **Last Reading** timestamps to identify silent failures

---

**🌍 USACH Environmental Monitoring System** - Helping protect air quality in Chile through intelligent sensor monitoring with comprehensive three-tab dashboard interface. 