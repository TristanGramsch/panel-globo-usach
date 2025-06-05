# USACH Environmental Monitoring Dashboard

A web dashboard for monitoring air quality sensors in Chile. Displays real-time sensor data with health monitoring and maintenance prioritization.

**Client**: Professor Ernesto Gramsch, USACH University

## 🚀 Quick Start

### Prerequisites
- **Conda** (recommended): Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution)
- **Python 3.11+** (if using pip)

### Option 1: Conda (Recommended)
```bash
# Setup
conda env create -f environment.yml
conda activate panel-globo-usach

# Run dashboard
python dashboard.py
```

### Option 2: pip (Alternative)
```bash
# Setup
python -m venv piloto_env
source piloto_env/bin/activate  # On Windows: piloto_env\Scripts\activate
pip install -r requirements.txt

# Run dashboard
python dashboard.py
```

**Access**: http://localhost:8051

## ✨ Features

- **Estado General**: Live air quality overview with WHO guidelines
- **Análisis Específico**: Individual sensor analysis and charts  
- **Estado de Sensores**: Health monitoring and maintenance prioritization
- **Auto-refresh**: Updates every 10 minutes
- **Sensor Health**: Status tracking for operational planning

## 📁 Project Structure

```
panel-globo-usach/
├── dashboard.py              # Main dashboard application (Dash web app)
├── environment.yml           # Conda environment specification (recommended)
├── requirements.txt          # pip dependencies (alternative)
├── README.md                 # Project documentation
├── .gitignore               # Git ignore rules
│
├── config/
│   ├── settings.py          # Configuration settings and WHO guidelines
│   └── logging_config.py    # Centralized logging configuration
│
├── data/
│   ├── processors.py        # Data parsing and processing functions
│   └── fetch_piloto_files.py # Data fetching utility from servidor
│
├── utils/
│   └── helpers.py           # Air quality categorization and utility functions
│
├── scripts/
│   └── manage_logs.py       # Log management and cleanup utilities
│
├── piloto_data/             # Sensor data files (.dat format)
├── logs/                    # Application and system logs (organized by component)
├── instructions/            # Project documentation and requirements
└── piloto_env/             # Python virtual environment (if using pip)
```

## 🔧 Configuration

- **Port**: 8051 (dashboard server)
- **Data Source**: `http://ambiente.usach.cl/globo/`
- **Update Interval**: 10 minutes
- **WHO Guidelines**: Built-in air quality standards

## 📊 Sensor Health Logic

- **Saludable** (Green): Data received today
- **Advertencia** (Yellow): Data received yesterday, not today  
- **Crítico** (Red): No data for 2+ days

## 🔄 Data Flow

1. `fetch_piloto_files.py` downloads sensor data
2. `processors.py` parses .dat files 
3. `dashboard.py` displays real-time visualization
4. Auto-refresh every 10 minutes

## 📝 Logging Strategy

The system implements a comprehensive logging architecture with centralized configuration (`config/logging_config.py`) that provides Chile timezone-aware logging across four main components: dashboard, data_fetching, data_processing, and system operations. Each component generates both human-readable logs and structured JSON logs stored in organized directories (`logs/dashboard/`, `logs/data_fetching/`, etc.) with automatic daily rotation, error-specific log files, and performance metrics tracking. The logging system includes automated cleanup and archival capabilities through `scripts/manage_logs.py` which compresses old logs, manages retention policies (7-day active, 30+ day archive), and provides detailed status reports. All logs use Chile timezone formatting and include comprehensive error handling, performance tracking with execution times, and structured data for analysis, making troubleshooting and system monitoring efficient and organized.

## 🛠️ Log Management

```bash
# View current log status and disk usage
python scripts/manage_logs.py status

# Clean up old logs (dry run first)
python scripts/manage_logs.py cleanup --dry-run
python scripts/manage_logs.py cleanup

# Archive logs older than specific days
python scripts/manage_logs.py archive --days 7

# Purge old archives
python scripts/manage_logs.py purge --days 90
```

---

**Ready to use** - Run `python dashboard.py` and access the dashboard at http://localhost:8051 