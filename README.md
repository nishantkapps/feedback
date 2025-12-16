# Robotic Arm Feedback System

A multi-modal feedback system for controlling a robotic arm based on user pain/discomfort detection. The system integrates multiple sensor inputs to provide real-time feedback for safe human-robot interaction.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Option 1: Piezo Sensor Dashboard (pressure detection)
python start.py

# Option 2: Face Pain Detection Dashboard (facial expression analysis)
python face_detection/start.py
```

## Overview

This system provides feedback through three channels:

| Module | Status | Description |
|--------|--------|-------------|
| **Pressure Sensors** | ✅ Complete | Arduino-based piezo sensors for force feedback |
| **Camera Feedback** | ✅ Complete | Facial expression analysis for pain detection |
| **EMG Sensors** | 🔜 Planned | Electromyography signals from the body |

---

## Module 1: Piezo Sensor (Pressure Detection)

Detects pressure/force using a piezo sensor connected to Arduino.

### Quick Start

```bash
python start.py
```

Opens dashboard at **http://localhost:5000**

### Features
- Real-time pressure gauge
- 5-level pressure categorization (NONE → CRITICAL)
- Robotic arm speed recommendations
- Supports hardware (Arduino) or file-based simulation

### Pressure Levels

| Level | Range | Action |
|-------|-------|--------|
| NONE | 0-5% | Full Speed (100%) |
| LIGHT | 5-20% | Reduced Speed (80%) |
| MODERATE | 20-50% | Caution Mode (50%) |
| HIGH | 50-80% | Paused (20%) |
| CRITICAL | 80-100% | EMERGENCY STOP |

[📖 Full Piezo Sensor Documentation](sensors/)

---

## Module 2: Face Pain Detection

Analyzes facial expressions to detect pain using computer vision.

### Quick Start

```bash
python face_detection/start.py
```

Opens dashboard at **http://localhost:5001**

### Features
- Real-time facial landmark detection (MediaPipe)
- Pain level analysis based on FACS (Facial Action Coding System)
- Webcam or video file input
- Calibration for personalized baseline
- Live annotated video feed

### Pain Indicators Analyzed

| Feature | Description |
|---------|-------------|
| Brow Furrow | Lowered/furrowed eyebrows |
| Eye Squeeze | Narrowed or closed eyes |
| Nose Wrinkle | Wrinkled nose bridge |
| Lip Raise | Raised upper lip |

### Pain Levels

| Level | Score | Emoji | Action |
|-------|-------|-------|--------|
| NONE | 0-10% | 😊 | Full Speed (100%) |
| MILD | 10-30% | 😐 | Reduced Speed (80%) |
| MODERATE | 30-55% | 😣 | Caution Mode (50%) |
| SEVERE | 55-80% | 😖 | Paused (20%) |
| EXTREME | 80-100% | 😫 | EMERGENCY STOP |

[📖 Full Face Detection Documentation](face_detection/README.md)

---

## Project Structure

```
feedback/
├── start.py                    # Piezo sensor quick start
├── run.py                      # Terminal-based piezo runner
├── requirements.txt
├── README.md
│
├── arduino/                    # Arduino firmware
│   └── piezo_sensor/
│       └── piezo_sensor.ino
│
├── data/                       # Sample sensor data
│   ├── sample_sensor_data.csv
│   └── test_small.csv
│
├── sensors/                    # Piezo sensor module
│   ├── __init__.py
│   ├── piezo_reader.py
│   └── file_reader.py
│
├── web/                        # Piezo sensor dashboard
│   ├── app.py
│   └── templates/
│       └── dashboard.html
│
└── face_detection/             # Face pain detection module
    ├── __init__.py
    ├── pain_detector.py        # Core pain detection
    ├── video_source.py         # Video/camera handler
    ├── start.py                # Quick start script
    ├── README.md
    └── web/
        ├── app.py
        └── templates/
            └── dashboard.html
```

## Hardware Requirements

### For Piezo Sensor Module
- Arduino board (Uno, Nano, or compatible)
- Piezo sensor/disc
- 1MΩ resistor
- Jumper wires

### For Face Detection Module
- Webcam (or video file)
- Good lighting for face visibility

## Installation

```bash
# Clone/download the project
cd feedback

# Install Python dependencies
pip install -r requirements.txt

# For piezo sensor with Arduino:
# Upload arduino/piezo_sensor/piezo_sensor.ino via Arduino IDE
```

## Running Both Dashboards

You can run both modules simultaneously on different ports:

```bash
# Terminal 1: Piezo Sensor (port 5000)
python start.py

# Terminal 2: Face Detection (port 5001)
python face_detection/start.py
```

## Future Development

- [ ] EMG sensor integration
- [ ] Sensor fusion (combine all inputs)
- [ ] ROS2 integration for robotic arm control
- [ ] WebSocket for lower latency
- [ ] Combined dashboard view

## License

MIT License
