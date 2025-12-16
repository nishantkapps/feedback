# Robotic Arm Feedback System

A multi-modal feedback system for controlling a robotic arm based on user pain/discomfort detection. The system integrates multiple sensor inputs to provide real-time feedback for safe human-robot interaction.

## Overview

This system provides feedback through three channels:
1. **Camera Feedback** - Facial expression analysis for pain detection (future)
2. **Pressure Sensors** - Arduino-based piezo sensors for force feedback (implemented)
3. **EMG Sensors** - Electromyography signals from the body (future)

## Current Implementation

### Piezo Sensor Module

The pressure detection module uses a piezo sensor connected to an Arduino to detect and measure pressure/force applied during robotic arm interaction.

## Hardware Requirements

### For Pressure Sensing
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

## Software Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Upload Arduino Sketch

1. Open `arduino/piezo_sensor/piezo_sensor.ino` in Arduino IDE
2. Select your board type (Tools > Board)
3. Select the correct port (Tools > Port)
4. Upload the sketch (Ctrl+U or Upload button)

### 3. Run the Python Reader

```bash
python -m sensors.piezo_reader
```

Or use programmatically:

```python
from sensors import PiezoSensor, PressureReading

# Auto-detect Arduino port
sensor = PiezoSensor()
sensor.connect()

# Read continuously with callback
def on_pressure(reading: PressureReading):
    print(f"Pressure: {reading.percent}% - Level: {reading.level}")
    
    if reading.level == "CRITICAL":
        # Trigger emergency stop on robotic arm
        pass

sensor.start_reading(callback=on_pressure)

# Or read single values
reading = sensor.read_once()

# Cleanup
sensor.disconnect()
```

## Pressure Levels

The system categorizes pressure into five levels:

| Level | Pressure Range | Suggested Action |
|-------|----------------|------------------|
| NONE | 0-5% | Normal operation |
| LIGHT | 5-20% | Monitor |
| MODERATE | 20-50% | Reduce speed |
| HIGH | 50-80% | Pause operation |
| CRITICAL | 80-100% | Emergency stop |

## API Reference

### PiezoSensor Class

```python
PiezoSensor(
    port: str = None,        # Serial port (auto-detect if None)
    baudrate: int = 115200,  # Must match Arduino sketch
    timeout: float = 1.0,    # Read timeout
    history_size: int = 100  # Readings to keep in history
)
```

#### Methods

- `connect()` - Establish connection to Arduino
- `disconnect()` - Close connection
- `read_once()` - Read single pressure value
- `start_reading(callback)` - Start continuous reading
- `stop_reading()` - Stop continuous reading
- `calibrate()` - Recalibrate baseline
- `get_latest()` - Get most recent reading
- `get_history()` - Get all stored readings
- `get_average_pressure(samples)` - Calculate average pressure
- `is_pressure_critical()` - Check if pressure is critical
- `is_pressure_high()` - Check if pressure is high or above

### PressureReading Dataclass

```python
@dataclass
class PressureReading:
    raw: int         # Raw analog value (0-1023)
    filtered: int    # Filtered value (moving average)
    pressure: int    # Pressure above baseline
    percent: float   # Pressure percentage (0-100%)
    level: str       # Category: NONE/LIGHT/MODERATE/HIGH/CRITICAL
    timestamp: int   # Arduino millis() timestamp
    received_at: float  # Python time.time() when received
```

## Project Structure

```
feedback/
├── arduino/
│   └── piezo_sensor/
│       └── piezo_sensor.ino    # Arduino sketch
├── sensors/
│   ├── __init__.py
│   └── piezo_reader.py         # Python sensor interface
├── requirements.txt
└── README.md
```

## Troubleshooting

### Port Not Found
```python
# List available ports
from sensors import PiezoSensor
print(PiezoSensor.list_available_ports())
```

### Permission Denied (Linux)
```bash
sudo chmod 666 /dev/ttyUSB0
# Or add user to dialout group:
sudo usermod -a -G dialout $USER
```

### Noisy Readings
- Add a 1MΩ resistor in parallel with the piezo sensor
- Use `calibrate()` method to recalibrate baseline
- Increase the filter size in the Arduino sketch

## Future Development

- [ ] Camera-based facial expression analysis for pain detection
- [ ] EMG sensor integration
- [ ] Sensor fusion algorithm
- [ ] ROS2 integration for robotic arm control
- [ ] Web dashboard for monitoring

## License

MIT License

