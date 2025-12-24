#!/usr/bin/env python3
"""
IRDS Feedback Publisher - Works with Face Detection Dashboard

This script monitors the face detection dashboard API and publishes
IRDS-compatible feedback in real-time.

USAGE:
    Step 1: Start face detection dashboard
        python face_detection/start.py
    
    Step 2: In browser (http://localhost:5001):
        - Select "YouTube URL"
        - Enter your YouTube link
        - Click "Start Analysis"
    
    Step 3: In another terminal, run this script:
        python integration/run_with_dashboard.py

The script will poll the dashboard and publish IRDS feedback to:
    data/irds_feedback.json
"""

import sys
import time
import json
import requests
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration.irds_interface import GestureModifier, PainFeedback


# Dashboard API configuration
DASHBOARD_URL = "http://localhost:5001"
POLL_INTERVAL = 0.2  # seconds


def get_dashboard_reading():
    """Get current reading from face detection dashboard."""
    try:
        resp = requests.get(f"{DASHBOARD_URL}/api/reading", timeout=1)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException:
        return None
    return None


def get_dashboard_status():
    """Get dashboard status."""
    try:
        resp = requests.get(f"{DASHBOARD_URL}/api/status", timeout=1)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException:
        return None
    return None


def convert_to_irds_feedback(reading: dict, modifier: GestureModifier) -> PainFeedback:
    """Convert dashboard reading to IRDS feedback."""
    # Map face detection levels to pain levels
    level_map = {
        'NONE': 0,
        'MILD': 1,
        'MODERATE': 2,
        'SEVERE': 3,
        'EXTREME': 4
    }
    
    level = reading.get('level', 'NONE')
    pain_level = level_map.get(level, 0)
    pain_score = reading.get('pain_score', 0)
    
    return modifier.create_feedback(
        pain_level=pain_level,
        pain_level_name=level,
        pain_score=pain_score,
        source='face',
        confidence=0.9 if reading.get('face_detected', False) else 0.0,
        details={
            'brow_furrow': reading.get('brow_furrow', 0),
            'eye_squeeze': reading.get('eye_squeeze', 0),
            'nose_wrinkle': reading.get('nose_wrinkle', 0),
            'lip_raise': reading.get('lip_raise', 0),
            'face_detected': reading.get('face_detected', False)
        }
    )


def print_header():
    print("\n" + "=" * 65)
    print("  IRDS Feedback Publisher - Face Detection Dashboard")
    print("=" * 65)


def print_status(feedback: PainFeedback, frame: int):
    """Print current status."""
    emojis = ["😊", "😐", "😣", "😖", "😫"]
    emoji = emojis[min(feedback.pain_level, 4)]
    
    colors = ["\033[92m", "\033[93m", "\033[93m", "\033[91m", "\033[91m"]
    color = colors[min(feedback.pain_level, 4)]
    reset = "\033[0m"
    
    status = f"{color}{emoji} {feedback.pain_level_name:10}{reset}"
    
    line = (f"#{frame:4d} | {status} | "
            f"Score: {feedback.pain_score:5.1f}% | "
            f"Speed: {feedback.speed_modifier:.0%} | "
            f"Amp: {feedback.amplitude_modifier:.0%}")
    
    if feedback.should_stop:
        line += f" | {color}🛑 STOP{reset}"
    elif feedback.should_pause:
        line += f" | {color}⏸️ PAUSE{reset}"
    
    print(f"\r{line}          ", end="", flush=True)


def main():
    print_header()
    
    # Setup output
    output_file = project_root / "data" / "irds_feedback.json"
    output_file.parent.mkdir(exist_ok=True)
    
    modifier = GestureModifier()
    
    print(f"\n📤 Output: {output_file}")
    print(f"🌐 Dashboard: {DASHBOARD_URL}")
    
    # Check if dashboard is running
    print("\n⏳ Connecting to dashboard...")
    status = get_dashboard_status()
    
    if status is None:
        print(f"\n❌ Cannot connect to dashboard at {DASHBOARD_URL}")
        print("\n   Please start the dashboard first:")
        print("   $ python face_detection/start.py")
        print("\n   Then open http://localhost:5001 in your browser")
        print("   and start analysis with a YouTube URL")
        return 1
    
    print(f"✓ Connected!")
    print(f"  Running: {status.get('is_running', False)}")
    
    if not status.get('is_running', False):
        print("\n⚠️  Dashboard is not running analysis")
        print("   Go to http://localhost:5001 and:")
        print("   1. Select 'YouTube URL'")
        print("   2. Enter your YouTube link")
        print("   3. Click 'Start Analysis'")
        print("\n   Waiting for analysis to start...")
        
        # Wait for analysis to start
        while True:
            status = get_dashboard_status()
            if status and status.get('is_running', False):
                break
            time.sleep(0.5)
        
        print("✓ Analysis started!")
    
    print("\n" + "-" * 65)
    print("  Publishing IRDS feedback... (Ctrl+C to stop)")
    print("-" * 65 + "\n")
    
    frame_count = 0
    last_reading = None
    
    try:
        while True:
            # Check status
            status = get_dashboard_status()
            if status is None or not status.get('is_running', False):
                if frame_count > 0:
                    print("\n\n📹 Analysis stopped")
                    break
                time.sleep(0.5)
                continue
            
            # Get reading
            reading = get_dashboard_reading()
            if reading is None:
                time.sleep(POLL_INTERVAL)
                continue
            
            # Only process new readings
            if reading == last_reading:
                time.sleep(POLL_INTERVAL)
                continue
            
            last_reading = reading
            frame_count += 1
            
            # Convert to IRDS feedback
            feedback = convert_to_irds_feedback(reading, modifier)
            
            # Write to file
            with open(output_file, 'w') as f:
                f.write(feedback.to_json())
            
            # Print status
            print_status(feedback, frame_count)
            
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    
    # Summary
    print("\n" + "-" * 65)
    print(f"\n✓ Complete! Published {frame_count} feedback updates")
    print(f"  Output: {output_file}")
    
    if output_file.exists():
        print(f"\n📋 Last feedback:")
        with open(output_file) as f:
            data = json.load(f)
        print(f"  Pain Level: {data.get('pain_level_name')} ({data.get('pain_score', 0):.1f}%)")
        print(f"  Speed Modifier: {data.get('speed_modifier', 1):.0%}")
        print(f"  Amplitude Modifier: {data.get('amplitude_modifier', 1):.0%}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())



