"""
Web Dashboard for Piezo Sensor Feedback System
Displays real-time pressure readings with visual feedback and descriptions.
"""

import csv
import json
import time
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


def load_sensor_data(filepath: str):
    """Load sensor data from CSV file."""
    global sensor_data
    data = []
    
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'timestamp': int(row['timestamp']),
                'raw': int(row['raw']),
                'filtered': int(row['filtered']),
                'pressure': int(row['pressure']),
                'percent': float(row['percent']),
                'level': row['level']
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
        
        while index < total:
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
    import sys
    
    # Default data file
    data_file = Path(__file__).parent.parent / 'data' / 'test_small.csv'
    
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    
    print(f"Loading data from: {data_file}")
    load_sensor_data(str(data_file))
    
    print("\n" + "=" * 50)
    print("  Piezo Sensor Dashboard")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

