# Robotic Arm Feedback System

A multi-modal feedback system for controlling a robotic arm based on user pain/discomfort detection. The system integrates multiple sensor inputs to provide real-time feedback for safe human-robot interaction.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the dashboard (opens browser automatically)
python start.py
```

Then click **"▶ Start Monitoring"** in the browser to begin.

## Overview

This system provides feedback through three channels:
1. **Camera Feedback** - Facial expression analysis for pain detection (future)
2. **Pressure Sensors** - Arduino-based piezo sensors for force feedback ✅
3. **EMG Sensors** - Electromyography signals from the body (future)

## Current Implementation

### Piezo Sensor Module

The pressure detection module uses a piezo sensor connected to an Arduino to detect and measure pressure/force applied during robotic arm interaction.

## Running Options

### Option 1: Web Dashboard (Recommended)

```bash
# With default data (sample_sensor_data.csv)
python start.py

# With custom data file
python start.py data/test_small.csv
```

Opens an interactive dashboard at **http://localhost:5000** with:
- Real-time pressure gauge
- Color-coded status levels
- Text descriptions and recommendations
- Pressure history chart
- Robotic arm status indicator

### Option 2: Terminal Mode

```bash
# Auto-detect (file simulation if no Arduino)
python run.py

# Force file simulation
python run.py --file

# Custom data file with speed control
python run.py --file --data data/test_small.csv --speed 10 --no-loop

# Force hardware mode (requires Arduino)
python run.py --hardware
```

### Option 3: Direct Flask Server

```bash
python web/app.py data/sample_sensor_data.csv
```

## Hardware Setup (For Real Arduino)

### Requirements
- Arduino board (Uno, Nano, or compatible)
- Piezo sensor/disc
- 1MΩ resistor (parallel with piezo sensor for stability)
- Jumper wires

### Wiring Diagram

```
Piezo Sensor          Arduino
------------          -------
  (+) ──────────────── A0
  (-) ──────────────── GND
  
  [1MΩ resistor in parallel with piezo sensor]
```

### Arduino Setup

1. Open `arduino/piezo_sensor/piezo_sensor.ino` in Arduino IDE
2. Select your board type (Tools > Board)
3. Select the correct port (Tools > Port)
4. Upload the sketch (Ctrl+U or Upload button)

## Pressure Levels

The system categorizes pressure into five levels:

| Level | Range | Color | Robotic Arm Action |
|-------|-------|-------|-------------------|
| NONE | 0-5% | 🟢 Green | Full Speed (100%) |
| LIGHT | 5-20% | 🟡 Yellow | Reduced Speed (80%) |
| MODERATE | 20-50% | 🟠 Orange | Caution Mode (50%) |
| HIGH | 50-80% | 🔴 Red | Paused (20%) |
| CRITICAL | 80-100% | 🔴 Dark Red | EMERGENCY STOP (0%) |

## Project Structure

```
feedback/
├── start.py                    # Quick start script
├── run.py                      # Terminal-based runner
├── requirements.txt
├── README.md
├── arduino/
│   └── piezo_sensor/
│       └── piezo_sensor.ino    # Arduino firmware
├── data/
│   ├── sample_sensor_data.csv  # Full test data (113 readings)
│   └── test_small.csv          # Small test data (15 readings)
├── sensors/
│   ├── __init__.py
│   ├── piezo_reader.py         # Hardware sensor interface
│   └── file_reader.py          # File-based mock sensor
└── web/
    ├── app.py                  # Flask web server
    └── templates/
        └── dashboard.html      # Dashboard UI
```

## API Reference

### PiezoSensor Class (Hardware)

```python
from sensors import PiezoSensor

with PiezoSensor() as sensor:
    def on_pressure(reading):
        print(f"Pressure: {reading.percent}%")
        if reading.level == "CRITICAL":
            # Trigger emergency stop
            pass
    
    sensor.start_reading(callback=on_pressure)
```

### FilePiezoSensor Class (Testing)

```python
from sensors import FilePiezoSensor

with FilePiezoSensor('data/test_small.csv', playback_speed=2.0) as sensor:
    sensor.start_reading(callback=lambda r: print(r.level))
```

### PressureReading Dataclass

```python
@dataclass
class PressureReading:
    raw: int         # Raw analog value (0-1023)
    filtered: int    # Filtered value (moving average)
    pressure: int    # Pressure above baseline
    percent: float   # Pressure percentage (0-100%)
    level: str       # NONE/LIGHT/MODERATE/HIGH/CRITICAL
    timestamp: int   # Arduino millis() timestamp
    received_at: float  # Python time.time()
```

## Troubleshooting

### Port Not Found
```python
from sensors import PiezoSensor
print(PiezoSensor.list_available_ports())
```

### Permission Denied (Linux)
```bash
sudo chmod 666 /dev/ttyUSB0
# Or add user to dialout group:
sudo usermod -a -G dialout $USER
```

### Dashboard Not Loading
- Ensure Flask is installed: `pip install flask`
- Check if port 5000 is available
- Try: `python web/app.py data/sample_sensor_data.csv`

## Future Development

- [ ] Camera-based facial expression analysis
- [ ] EMG sensor integration
- [ ] Sensor fusion algorithm
- [ ] ROS2 integration for robotic arm control
- [ ] WebSocket for lower latency updates

## License

MIT License
