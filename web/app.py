"""
Web Dashboard for Piezo Sensor Feedback System
Displays real-time pressure readings with visual feedback and recommendations.
"""

import sys
import json
import time
import signal
import atexit
import threading
from pathlib import Path

from flask import Flask, render_template, jsonify, Response

app = Flask(__name__, template_folder='templates', static_folder='static')

# Global state
sensor_data = []
current_index = 0
is_playing = False
playback_speed = 1.0
data_lock = threading.Lock()
shutdown_event = threading.Event()
stream_thread = None


def cleanup():
    """Cleanup resources on shutdown."""
    global is_playing, stream_thread
    print("\nCleaning up resources...")
    
    is_playing = False
    shutdown_event.set()
    
    if stream_thread and stream_thread.is_alive():
        stream_thread.join(timeout=2)
    
    print("Cleanup complete.")


# Register cleanup handlers
atexit.register(cleanup)


def signal_handler(signum, frame):
    """Handle termination signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_sensor_data(filepath: str):
    """Load sensor data from CSV file."""
    global sensor_data
    
    # Import here to avoid circular imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from sensors.file_reader import PressureClassifier
    
    classifier = PressureClassifier()
    data = []
    
    import csv
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = int(row['timestamp'])
            pressure = int(row['pressure'])
            
            # Use classifier to compute level and percent
            classification = classifier.get_classification_details(pressure)
            
            data.append({
                'timestamp': timestamp,
                'raw': 512 + pressure,  # Simulated raw value
                'filtered': 512 + pressure,
                'pressure': pressure,
                'percent': classification['percent'],
                'level': classification['level']
            })
    
    with data_lock:
        sensor_data = data
    
    return len(data)


def get_level_description(level: str, percent: float) -> dict:
    """Get description and recommendations for each pressure level."""
    descriptions = {
        'NONE': {
            'title': 'No Pressure Detected',
            'description': 'The sensor is in its resting state with no significant pressure applied.',
            'recommendation': 'Normal operation - robotic arm can operate at full speed.',
            'color': '#10b981',  # Green
            'icon': '✓',
            'arm_status': 'Full Speed (100%)'
        },
        'LIGHT': {
            'title': 'Light Pressure',
            'description': 'Minor pressure detected. This could indicate light contact or the beginning of interaction.',
            'recommendation': 'Monitor the situation - slight reduction in arm speed recommended.',
            'color': '#f59e0b',  # Yellow/Amber
            'icon': '○',
            'arm_status': 'Reduced Speed (80%)'
        },
        'MODERATE': {
            'title': 'Moderate Pressure',
            'description': 'Significant pressure detected. The sensor is experiencing notable force.',
            'recommendation': 'Caution advised - reduce arm speed and monitor closely.',
            'color': '#f97316',  # Orange
            'icon': '◐',
            'arm_status': 'Caution Mode (50%)'
        },
        'HIGH': {
            'title': 'High Pressure',
            'description': 'High pressure levels detected! This may indicate discomfort or excessive force.',
            'recommendation': 'Warning - pause robotic arm operation and assess the situation.',
            'color': '#ef4444',  # Red
            'icon': '●',
            'arm_status': 'Paused (20%)'
        },
        'CRITICAL': {
            'title': 'CRITICAL PRESSURE',
            'description': 'Extremely high pressure detected! Immediate action required to prevent injury.',
            'recommendation': 'EMERGENCY STOP - Halt all robotic arm operations immediately!',
            'color': '#dc2626',  # Dark Red
            'icon': '⚠',
            'arm_status': 'EMERGENCY STOP (0%)'
        }
    }
    
    info = descriptions.get(level, descriptions['NONE'])
    info['percent'] = percent
    info['level'] = level
    return info


@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/data')
def get_all_data():
    """Return all sensor data."""
    with data_lock:
        return jsonify(sensor_data)


@app.route('/api/reading/<int:index>')
def get_reading(index: int):
    """Get a specific reading by index."""
    with data_lock:
        if 0 <= index < len(sensor_data):
            reading = sensor_data[index]
            reading['description'] = get_level_description(reading['level'], reading['percent'])
            reading['index'] = index
            reading['total'] = len(sensor_data)
            return jsonify(reading)
        return jsonify({'error': 'Index out of range'}), 404


@app.route('/api/stream')
def stream_data():
    """Stream sensor data as Server-Sent Events."""
    def generate():
        index = 0
        with data_lock:
            total = len(sensor_data)
        
        while index < total and not shutdown_event.is_set():
            with data_lock:
                if index < len(sensor_data):
                    reading = sensor_data[index].copy()
                    reading['description'] = get_level_description(reading['level'], reading['percent'])
                    reading['index'] = index
                    reading['total'] = total
                    
                    yield f"data: {json.dumps(reading)}\n\n"
            
            index += 1
            time.sleep(0.1 / playback_speed)  # 100ms between readings, adjusted by speed
        
        # Send end signal
        yield f"data: {json.dumps({'end': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


def create_app(data_file: str = None):
    """Create and configure the Flask app."""
    if data_file:
        count = load_sensor_data(data_file)
        print(f"Loaded {count} sensor readings")
    return app


if __name__ == '__main__':
    import argparse
    
    # Default data file
    data_file = Path(__file__).parent.parent / 'data' / 'sample_sensor_data.csv'
    
    parser = argparse.ArgumentParser(description='Piezo Sensor Dashboard')
    parser.add_argument('data_file', nargs='?', default=str(data_file), help='Path to sensor data CSV')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Port number')
    args = parser.parse_args()
    
    print(f"Loading data from: {args.data_file}")
    load_sensor_data(args.data_file)
    
    print("\n" + "=" * 50)
    print("  Piezo Sensor Dashboard")
    print(f"  Open http://localhost:{args.port} in your browser")
    print("=" * 50 + "\n")
    
    try:
        # Disable debug mode to avoid duplicate processes
        app.run(debug=False, host='0.0.0.0', port=args.port)
    finally:
        cleanup()
