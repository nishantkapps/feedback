# IRDS Integration Module

This module provides interfaces for integrating the pain detection feedback system with the IRDS gesture recognition model. The feedback data allows IRDS to adjust gesture parameters (speed, amplitude, force) based on detected pain levels from piezo sensors and facial expression analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Pain Detection System                             │
│                                                                      │
│  ┌─────────────────┐         ┌─────────────────┐                    │
│  │  Piezo Sensor   │         │  Face Detection │                    │
│  │    Arduino      │         │    Camera       │                    │
│  └────────┬────────┘         └────────┬────────┘                    │
│           │                           │                              │
│           ▼                           ▼                              │
│  ┌────────────────────────────────────────────────┐                 │
│  │              IRDS Bridge                        │                 │
│  │         (integration/irds_bridge.py)           │                 │
│  │                                                 │                 │
│  │  • Converts sensor data to feedback format     │                 │
│  │  • Fuses multiple sources                       │                 │
│  │  • Calculates gesture modifiers                 │                 │
│  └────────────────────┬───────────────────────────┘                 │
│                       │                                              │
└───────────────────────┼──────────────────────────────────────────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │   Output Methods     │
             │                      │
             │  • JSON File         │
             │  • UDP Socket        │
             │  • TCP Socket        │
             │  • Direct Callback   │
             └──────────┬───────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        IRDS System                                    │
│                                                                       │
│  ┌────────────────────┐      ┌──────────────────────────┐            │
│  │  Feedback Consumer │ ───▶ │   Gesture Model          │            │
│  │  (reads modifiers) │      │   (adjusted execution)   │            │
│  └────────────────────┘      └────────────┬─────────────┘            │
│                                            │                          │
└────────────────────────────────────────────┼──────────────────────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │  Robotic Arm    │
                                    │  (safe motion)  │
                                    └─────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `irds_interface.py` | Core interface classes and data structures |
| `irds_bridge.py` | Bridge that connects pain sensors to IRDS output |
| `irds_consumer_example.py` | Example code for IRDS to consume feedback |

## Quick Start

### 1. Run the Demo

```bash
cd /home/nishant/project/feedback

# Run bridge demo with simulated data
python integration/irds_bridge.py --demo

# Run consumer demo (reads the output)
python integration/irds_consumer_example.py
```

### 2. Start the Bridge (Real Operation)

```bash
# File output mode (IRDS polls file)
python integration/irds_bridge.py --output-file data/irds_feedback.json

# Socket output mode (real-time UDP)
python integration/irds_bridge.py --socket-host localhost --socket-port 5555
```

### 3. View Integration Guide

```bash
python integration/irds_consumer_example.py --guide
```

## Feedback Data Format

The bridge outputs JSON data that IRDS can consume:

```json
{
    "timestamp": 1734355200.123,
    "pain_level": 2,
    "pain_level_name": "MODERATE",
    "pain_score": 45.5,
    "source": "fused",
    "confidence": 0.85,
    "speed_modifier": 0.5,
    "amplitude_modifier": 0.7,
    "force_modifier": 0.6,
    "should_pause": false,
    "should_stop": false,
    "details": {
        "piezo": { "raw": 150, "filtered": 145, "pressure": 145 },
        "face": { "brow_furrow": 0.45, "eye_squeeze": 0.32 }
    }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | float | Unix timestamp of the reading |
| `pain_level` | int | 0-4 (NONE, LIGHT, MODERATE, HIGH, CRITICAL) |
| `pain_level_name` | string | Human-readable level name |
| `pain_score` | float | 0-100 percentage |
| `source` | string | 'piezo', 'face', or 'fused' |
| `confidence` | float | 0-1 confidence in the reading |
| `speed_modifier` | float | 0-1 multiply gesture speed by this |
| `amplitude_modifier` | float | 0-1 multiply gesture amplitude by this |
| `force_modifier` | float | 0-1 multiply gesture force by this |
| `should_pause` | bool | If true, pause gesture execution |
| `should_stop` | bool | If true, emergency stop |

## Gesture Modifier Mapping

The bridge maps pain levels to gesture modifiers:

| Pain Level | Speed | Amplitude | Force | Action |
|------------|-------|-----------|-------|--------|
| NONE (0) | 100% | 100% | 100% | Normal execution |
| LIGHT (1) | 80% | 90% | 85% | Slight reduction |
| MODERATE (2) | 50% | 70% | 60% | Noticeable reduction |
| HIGH (3) | 20% | 50% | 30% | **Pause recommended** |
| CRITICAL (4) | 0% | 0% | 0% | **Emergency stop** |

## Integration with IRDS

### Option 1: File-Based Integration

```python
# In IRDS project - read from file
import json
from pathlib import Path

feedback_file = Path('/home/nishant/project/feedback/data/irds_feedback.json')

def get_gesture_modifiers():
    if feedback_file.exists():
        with open(feedback_file) as f:
            data = json.load(f)
        return {
            'speed': data.get('speed_modifier', 1.0),
            'amplitude': data.get('amplitude_modifier', 1.0),
            'force': data.get('force_modifier', 1.0),
            'is_safe': not data.get('should_stop', False)
        }
    return {'speed': 1.0, 'amplitude': 1.0, 'force': 1.0, 'is_safe': True}

# In gesture execution:
mods = get_gesture_modifiers()
if not mods['is_safe']:
    emergency_stop()
else:
    execute_gesture(
        speed=base_speed * mods['speed'],
        amplitude=base_amplitude * mods['amplitude']
    )
```

### Option 2: Socket-Based Integration

```python
# In IRDS project - listen on UDP socket
import socket
import json
import threading

class PainFeedbackReceiver:
    def __init__(self, port=5555):
        self.port = port
        self.latest = {}
        self._running = False
    
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
    
    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.port))
        sock.settimeout(1.0)
        
        while self._running:
            try:
                data, _ = sock.recvfrom(4096)
                self.latest = json.loads(data.decode())
            except socket.timeout:
                continue
    
    def get_modifiers(self):
        return self.latest
```

## Sensor Fusion

When both piezo and face detection are enabled, the bridge fuses the readings:

- **Pain Level**: Maximum of both sources (conservative)
- **Pain Score**: Weighted average based on confidence
- **Modifiers**: Minimum of both sources (conservative)
- **Control Flags**: OR of both sources (if either says stop, stop)

Default weights:
- Piezo sensor: 60%
- Face detection: 40%

Configure weights:
```bash
python integration/irds_bridge.py --piezo-weight 0.7 --face-weight 0.3
```

## API Reference

### PainFeedback

```python
@dataclass
class PainFeedback:
    timestamp: float
    pain_level: int           # 0-4
    pain_level_name: str      # Human-readable
    pain_score: float         # 0-100
    source: str               # 'piezo', 'face', 'fused'
    confidence: float         # 0-1
    speed_modifier: float     # 0-1
    amplitude_modifier: float # 0-1
    force_modifier: float     # 0-1
    should_pause: bool
    should_stop: bool
    details: Optional[Dict]
```

### GestureModifier

```python
modifier = GestureModifier()
feedback = modifier.create_feedback(
    pain_level=2,
    pain_level_name='MODERATE',
    pain_score=45.0,
    source='piezo',
    confidence=0.9
)
```

### FeedbackPublisher

```python
publisher = FeedbackPublisher(
    output_file='data/irds_feedback.json',
    socket_host='localhost',
    socket_port=5555
)
publisher.publish(feedback)
```

## Safety Considerations

1. **Stale Data**: The consumer treats data older than 2 seconds as stale and applies conservative defaults
2. **Missing Data**: When no feedback is available, the system allows normal operation but logs warnings
3. **Critical Pain**: Level 4 (CRITICAL) triggers an immediate stop flag
4. **Network Failures**: Socket errors are logged but don't crash the system

## Testing

```bash
# Test the bridge
python integration/irds_bridge.py --demo

# Test the consumer
python integration/irds_consumer_example.py

# View integration guide
python integration/irds_consumer_example.py --guide
```



