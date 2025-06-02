# USACH Environmental Monitoring System

A robust Python-based system for monitoring environmental sensor data from the USACH server, with comprehensive air quality analysis and visualization capabilities.

## 🌟 Features

### Data Collection
- **Smart File Management**: Automatically downloads only new or updated Piloto*.dat files
- **Robust Error Handling**: Gracefully handles server timeouts, network issues, and malformed responses
- **Comprehensive Logging**: Detailed logs of all operations with timestamps
- **File Integrity Checking**: Detects and logs empty files from server
- **Automatic Organization**: Files organized by date in dedicated directories

### Air Quality Analysis
- **MP1.0 Particulate Matter Analysis**: Comprehensive analysis of fine particulate matter levels
- **WHO Guidelines Compliance**: Automatic categorization based on World Health Organization air quality standards
- **Multi-Sensor Support**: Handles different sensor data formats automatically
- **Statistical Analysis**: Detailed statistics including averages, ranges, and time distributions
- **Health Risk Assessment**: Real-time health risk categorization and recommendations

### Visualization & Monitoring
- **Interactive Dashboard**: Real-time air quality status with color-coded alerts
- **Comprehensive Charts**: Time series, box plots, and comparative visualizations
- **Health Alerts**: Automatic alerts for unhealthy air quality levels
- **Data Coverage Analysis**: Monitor sensor performance and data availability

## 📊 Air Quality Categories (WHO Guidelines)

| Level | Range (μg/m³) | Health Risk | Color Code |
|-------|---------------|-------------|------------|
| Good | ≤15 | Very low | 🟢 Green |
| Moderate | 15-25 | Low | 🟡 Yellow |
| Unhealthy for Sensitive | 25-35 | Moderate | 🟠 Orange |
| Unhealthy | 35-75 | High | 🔴 Red |
| Very Unhealthy | >75 | Very high | 🟣 Purple |

## 🚀 Quick Start

### Installation

1. **Clone or download the project files**
2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv piloto_env
   source piloto_env/bin/activate  # On Windows: piloto_env\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

1. **Download current data**:
   ```bash
   python fetch_piloto_files.py
   ```

2. **View air quality dashboard**:
   ```bash
   python dashboard.py
   ```

3. **Generate detailed analysis**:
   ```bash
   python analyze_mp1_data.py
   ```

4. **Create visualizations**:
   ```bash
   python visualize_air_quality.py
   ```

## 📁 Project Structure

```
panel-globo-usach/
├── fetch_piloto_files.py      # Main data fetcher
├── analyze_mp1_data.py        # Air quality analysis engine
├── visualize_air_quality.py   # Visualization generator
├── dashboard.py               # Real-time monitoring dashboard
├── test_fetcher.py           # Test suite
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── piloto_data/              # Downloaded data files
├── logs/                     # Operation logs
└── air_quality_analysis.png  # Generated visualization
```

## 🔧 Configuration

### Server Settings
The system connects to: `http://www.aire.usach.cl/Piloto/`

### File Patterns
- Downloads files matching: `Piloto*.dat`
- Focuses on current month data
- Handles both detailed and simplified sensor formats

### Logging
- Logs stored in `logs/` directory
- Automatic log rotation
- Configurable log levels

## 📈 Analysis Capabilities

### Supported Metrics
- **MP1.0 Particulate Matter**: Fine particles (≤1.0 μm)
- **Temperature & Humidity**: Environmental conditions
- **Atmospheric Pressure**: Barometric readings
- **Wind Data**: Direction and speed
- **CO2 Levels**: Carbon dioxide concentrations

### Data Processing
- Automatic column detection for different sensor formats
- Handles both `MP1.0[St.P]` and `MP1.0` column formats
- Robust datetime parsing
- Missing data handling

## 🖥️ Dashboard Features

The dashboard provides:
- **Real-time Status**: Current air quality level with color coding
- **Critical Alerts**: Immediate warnings for dangerous pollution levels
- **Sensor Rankings**: Identification of most polluted areas
- **Health Recommendations**: WHO-based guidance for outdoor activities
- **Data Freshness**: Information about last update times

## 📊 Visualization Options

Generated charts include:
- **Time Series**: Pollution trends over time for all sensors
- **Box Plots**: Distribution comparison between sensors
- **Bar Charts**: Average pollution levels by sensor
- **Coverage Analysis**: Data availability and sensor performance

## 🔍 Example Analysis Output

```
SENSOR RANKINGS BY AVERAGE MP1.0
============================================================
 1. Sensor 100:  145.2 μg/m³ (721 points) - 🟣 VERY UNHEALTHY
 2. Sensor 078:   77.6 μg/m³ (879 points) - 🟣 VERY UNHEALTHY  
 3. Sensor 013:   73.6 μg/m³ (871 points) - 🔴 UNHEALTHY
 4. Sensor 052:   48.5 μg/m³ (859 points) - 🔴 UNHEALTHY
 5. Sensor 023:   20.6 μg/m³ (844 points) - 🟡 MODERATE
```

## 🚨 Health Alerts

The system automatically generates alerts:
- **🚨 CRITICAL**: Very unhealthy levels (>75 μg/m³)
- **⚠️ WARNING**: Unhealthy levels (35-75 μg/m³)
- **📋 RECOMMENDATIONS**: Activity guidance based on current conditions

## 🔄 Automation

### Scheduled Updates
Set up automatic data collection with cron (Linux/Mac) or Task Scheduler (Windows):

```bash
# Update data every hour
0 * * * * /path/to/piloto_env/bin/python /path/to/fetch_piloto_files.py
```

### Continuous Monitoring
For real-time monitoring, run the dashboard periodically or integrate with monitoring systems.

## 🛠️ Troubleshooting

### Common Issues

1. **No data downloaded**:
   - Check internet connection
   - Verify server accessibility
   - Review logs in `logs/` directory

2. **Analysis errors**:
   - Ensure data files exist in `piloto_data/`
   - Check file formats and encoding
   - Verify pandas installation

3. **Visualization problems**:
   - Install matplotlib: `pip install matplotlib`
   - Check display settings for headless systems
   - Verify file permissions

### Debug Mode
Enable verbose logging by modifying the logging level in the scripts.

## 📝 Logging

All operations are logged with:
- **Timestamps**: Precise operation timing
- **Status Codes**: HTTP response tracking
- **File Operations**: Download and processing status
- **Error Details**: Comprehensive error information

Log files are automatically rotated and stored in the `logs/` directory.

## 🔮 Future Enhancements

- **Web Dashboard**: Browser-based real-time monitoring
- **Database Integration**: Long-term data storage and analysis
- **Alert System**: Email/SMS notifications for critical conditions
- **Mobile App**: Smartphone access to air quality data
- **Predictive Analytics**: Machine learning for pollution forecasting
- **Multi-Location Support**: Expansion to other monitoring networks

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📞 Support

For questions or support, please open an issue in the project repository. 