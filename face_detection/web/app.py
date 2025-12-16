"""
Web Dashboard for Face Pain Detection
Displays real-time pain analysis with video feed and recommendations.
"""

import sys
import json
import time
import base64
import threading
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, render_template, jsonify, Response, request

import cv2
import numpy as np

from face_detection.pain_detector import PainDetector, PainReading
from face_detection.video_source import VideoSource

app = Flask(__name__, template_folder='templates', static_folder='static')

# Global state
detector: PainDetector = None
video_source: VideoSource = None
current_reading: dict = None
is_running = False
is_calibrated = False
history = []
lock = threading.Lock()


def init_detector():
    """Initialize the pain detector."""
    global detector
    if detector is None:
        detector = PainDetector()
    return detector


def get_reading_dict(reading: PainReading) -> dict:
    """Convert reading to dictionary with description."""
    data = reading.to_dict()
    data['description'] = detector.get_level_description(reading.level, reading.pain_score)
    return data


def process_frame(frame: np.ndarray, calibrate: bool = False) -> tuple:
    """Process a frame and return reading + annotated frame."""
    global current_reading, is_calibrated, history
    
    reading = detector.analyze_frame(frame, calibrate_baseline=calibrate)
    
    if calibrate and reading.face_detected:
        is_calibrated = True
    
    # Draw annotations on frame
    annotated = draw_annotations(frame.copy(), reading)
    
    with lock:
        current_reading = get_reading_dict(reading)
        if reading.face_detected:
            history.append(current_reading)
            if len(history) > 100:
                history.pop(0)
    
    return reading, annotated


def draw_annotations(frame: np.ndarray, reading: PainReading) -> np.ndarray:
    """Draw pain indicators on the frame."""
    h, w = frame.shape[:2]
    
    # Color based on pain level
    colors = {
        'NONE': (16, 185, 129),      # Green (BGR)
        'MILD': (11, 158, 245),       # Yellow
        'MODERATE': (22, 115, 249),   # Orange
        'SEVERE': (68, 68, 239),      # Red
        'EXTREME': (38, 38, 220)      # Dark Red
    }
    color = colors.get(reading.level, (128, 128, 128))
    
    # Draw border based on pain level
    border_thickness = 8 if reading.level in ['SEVERE', 'EXTREME'] else 4
    cv2.rectangle(frame, (0, 0), (w-1, h-1), color, border_thickness)
    
    # Draw status panel
    panel_height = 80
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_height), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
    
    # Pain level text
    level_text = f"Pain: {reading.level}"
    cv2.putText(frame, level_text, (20, 35), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    
    # Pain score
    score_text = f"Score: {reading.pain_score:.1f}%"
    cv2.putText(frame, score_text, (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Face detection status
    if not reading.face_detected:
        cv2.putText(frame, "No Face Detected", (w//2 - 100, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    # Calibration indicator
    if is_calibrated:
        cv2.circle(frame, (w - 30, 30), 10, (0, 255, 0), -1)
    else:
        cv2.circle(frame, (w - 30, 30), 10, (0, 165, 255), -1)
    
    return frame


def generate_video_feed():
    """Generate video frames for streaming."""
    global is_running, video_source
    
    while is_running and video_source and video_source.is_open:
        frame_info = video_source.read_frame()
        
        if frame_info is None:
            if not video_source.is_camera:
                # Video file ended
                is_running = False
            break
        
        _, annotated = process_frame(frame_info.frame)
        
        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Rate limit
        time.sleep(1/30)


@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/start', methods=['POST'])
def start_analysis():
    """Start video analysis."""
    global is_running, video_source, history, is_calibrated
    
    if is_running:
        return jsonify({'error': 'Already running'}), 400
    
    data = request.json or {}
    source_type = data.get('source', 'camera')
    file_path = data.get('file_path')
    youtube_url = data.get('youtube_url')
    
    init_detector()
    
    try:
        if source_type == 'camera':
            video_source = VideoSource(camera=0, resize_width=640)
        elif source_type == 'youtube':
            if not youtube_url:
                return jsonify({'error': 'No YouTube URL provided'}), 400
            video_source = VideoSource(youtube_url=youtube_url, resize_width=640)
        else:
            if not file_path:
                return jsonify({'error': 'No file path provided'}), 400
            video_source = VideoSource(file_path=file_path, resize_width=640)
        
        video_source.open()
        is_running = True
        history = []
        is_calibrated = False
        
        response_data = {
            'status': 'started',
            'source': source_type,
            'fps': video_source.fps,
            'total_frames': video_source.total_frames
        }
        
        # Include YouTube info if available
        if source_type == 'youtube' and video_source.youtube_info:
            response_data['youtube_info'] = video_source.youtube_info
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stop', methods=['POST'])
def stop_analysis():
    """Stop video analysis."""
    global is_running, video_source
    
    is_running = False
    if video_source:
        video_source.stop()
        video_source.close()
        video_source = None
    
    return jsonify({'status': 'stopped'})


@app.route('/api/calibrate', methods=['POST'])
def calibrate():
    """Calibrate baseline expression."""
    global is_calibrated
    
    if not is_running or not video_source:
        return jsonify({'error': 'Not running'}), 400
    
    # Read a frame and calibrate
    frame_info = video_source.read_frame()
    if frame_info:
        reading, _ = process_frame(frame_info.frame, calibrate=True)
        if reading.face_detected:
            return jsonify({'status': 'calibrated', 'message': 'Baseline set from neutral expression'})
        else:
            return jsonify({'error': 'No face detected for calibration'}), 400
    
    return jsonify({'error': 'Could not read frame'}), 500


@app.route('/api/reading')
def get_current_reading():
    """Get the current pain reading."""
    with lock:
        if current_reading:
            return jsonify(current_reading)
    return jsonify({'face_detected': False, 'pain_score': 0, 'level': 'NONE'})


@app.route('/api/history')
def get_history():
    """Get pain reading history."""
    with lock:
        return jsonify(history[-50:])  # Last 50 readings


@app.route('/api/status')
def get_status():
    """Get current system status."""
    return jsonify({
        'is_running': is_running,
        'is_calibrated': is_calibrated,
        'source_type': 'camera' if (video_source and video_source.is_camera) else 'file',
        'frame_count': video_source.current_frame if video_source else 0,
        'progress': video_source.progress if video_source else 0
    })


@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    return Response(
        generate_video_feed(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


def create_app(video_file: str = None):
    """Create and configure the Flask app."""
    global video_source
    
    init_detector()
    
    if video_file:
        print(f"Pre-configured video file: {video_file}")
    
    return app


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Face Pain Detection Dashboard')
    parser.add_argument('--video', '-v', type=str, help='Path to video file')
    parser.add_argument('--port', '-p', type=int, default=5001, help='Port number')
    args = parser.parse_args()
    
    print("\n" + "=" * 50)
    print("  Face Pain Detection Dashboard")
    print(f"  Open http://localhost:{args.port} in your browser")
    print("=" * 50 + "\n")
    
    if args.video:
        print(f"Video file: {args.video}")
    else:
        print("Using webcam (default)")
    
    app.run(debug=True, host='0.0.0.0', port=args.port, threaded=True)

