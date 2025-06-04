# USACH Environmental Monitoring Dashboard

A web dashboard for monitoring air quality sensors in Chile. Displays real-time sensor data with health monitoring and maintenance prioritization.

**Client**: Professor Ernesto Gramsch, USACH University

## 🚀 Quick Start

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
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── .gitignore               # Git ignore rules
│
├── config/
│   └── settings.py          # Configuration settings and WHO guidelines
│
├── data/
│   ├── processors.py        # Data parsing and processing functions
│   └── fetch_piloto_files.py # Data fetching utility from servidor
│
├── utils/
│   └── helpers.py           # Air quality categorization and utility functions
│
├── piloto_data/             # Sensor data files (.dat format)
├── logs/                    # Application and system logs
├── instructions/            # Project documentation and requirements
└── piloto_env/             # Python virtual environment
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

## 📝 Logging

- Main logs: `logs/`
- Data processing errors and sensor status tracked
- Server connection status monitoring

---

**Ready to use** - Run `python dashboard.py` and access the dashboard at http://localhost:8051 