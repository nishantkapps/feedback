# Face Pain Detection Module

Facial expression analysis for pain detection in the Robotic Arm Feedback System.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the dashboard (opens browser automatically)
python face_detection/start.py
```

Then:
1. Select **Webcam** or **Video File** as source
2. Click **"▶ Start Analysis"**
3. Click **"🎯 Calibrate"** with a neutral expression for best results
4. Watch the pain level analysis in real-time!

## Features

- **Real-time facial expression analysis** using MediaPipe Face Mesh
- **Pain level detection** based on Facial Action Coding System (FACS)
- **Live video feed** with annotations
- **Pain history chart**
- **Robotic arm recommendations** based on detected pain levels

## Pain Indicators

The system analyzes these facial features associated with pain:

| Feature | Description | FACS Code |
|---------|-------------|-----------|
| Brow Furrow | Lowered/furrowed brows | AU4 |
| Eye Squeeze | Narrowed/closed eyes | AU6, AU7, AU43 |
| Nose Wrinkle | Wrinkled nose bridge | AU9 |
| Lip Raise | Raised upper lip | AU10 |

## Pain Levels

| Level | Score | Emoji | Robotic Arm Action |
|-------|-------|-------|-------------------|
| NONE | 0-10% | 😊 | Full Speed (100%) |
| MILD | 10-30% | 😐 | Reduced Speed (80%) |
| MODERATE | 30-55% | 😣 | Caution Mode (50%) |
| SEVERE | 55-80% | 😖 | Paused (20%) |
| EXTREME | 80-100% | 😫 | EMERGENCY STOP (0%) |

## Usage Options

### Option 1: Quick Start Script (Recommended)

```bash
# Webcam (default)
python face_detection/start.py

# With video file
python face_detection/start.py --video path/to/video.mp4

# Custom port
python face_detection/start.py --port 8080
```

### Option 2: Direct Flask Server

```bash
python face_detection/web/app.py --port 5001
```

### Option 3: Programmatic Use

```python
from face_detection import PainDetector, VideoSource
import cv2

# Initialize
detector = PainDetector()
source = VideoSource(camera=0)  # or VideoSource(file_path='video.mp4')

with source:
    for frame_info in source.frames():
        # Analyze frame
        reading = detector.analyze_frame(frame_info.frame)
        
        print(f"Pain: {reading.level} ({reading.pain_score:.1f}%)")
        
        if reading.level in ['SEVERE', 'EXTREME']:
            # Trigger safety response
            print("⚠️ High pain detected!")

detector.close()
```

## Calibration

For best results, calibrate with a **neutral expression**:

1. Start the analysis
2. Look at the camera with a relaxed, neutral face
3. Click **"🎯 Calibrate"**

This sets a baseline so the system can better detect changes from your neutral expression.

## Project Structure

```
face_detection/
├── __init__.py
├── pain_detector.py      # Core pain detection logic
├── video_source.py       # Video/camera input handling
├── start.py              # Quick start script
├── README.md
└── web/
    ├── app.py            # Flask web server
    └── templates/
        └── dashboard.html
```

## API Reference

### PainDetector

```python
detector = PainDetector(
    min_detection_confidence=0.5,  # Face detection threshold
    min_tracking_confidence=0.5,   # Landmark tracking threshold
    history_size=30                # Readings to keep for smoothing
)

# Analyze a frame
reading = detector.analyze_frame(frame, calibrate_baseline=False)

# Get level description
info = detector.get_level_description(reading.level, reading.pain_score)
```

### PainReading

```python
@dataclass
class PainReading:
    pain_score: float      # 0-100 overall pain score
    level: str             # NONE/MILD/MODERATE/SEVERE/EXTREME
    brow_furrow: float     # 0-100 brow lowering intensity
    eye_squeeze: float     # 0-100 eye closure intensity
    nose_wrinkle: float    # 0-100 nose wrinkle intensity
    lip_raise: float       # 0-100 lip raise intensity
    face_detected: bool    # Whether a face was found
    timestamp: float       # Unix timestamp
    frame_number: int      # Video frame number
```

### VideoSource

```python
# From webcam
source = VideoSource(camera=0)

# From file
source = VideoSource(file_path='video.mp4')

# With options
source = VideoSource(
    camera=0,
    target_fps=30.0,
    resize_width=640
)
```

## Troubleshooting

### Camera Not Found
- Check if webcam is connected and not in use by another app
- Try different camera index: `VideoSource(camera=1)`

### Poor Detection
- Ensure good lighting on face
- Face should be clearly visible and facing camera
- Calibrate with neutral expression

### Slow Performance
- Reduce frame resolution with `resize_width`
- Skip frames in video processing

## Technical Details

The pain detection is based on research into Facial Action Coding System (FACS) and pain expression. Key papers:

- Prkachin's Pain Intensity Scale
- Facial Action Units associated with pain (AU4, AU6, AU7, AU9, AU10, AU43)

The system uses MediaPipe Face Mesh for 468-point facial landmark detection, which is then analyzed for pain-related muscle movements.

