#!/usr/bin/env python3
"""
Test IRDS Integration with Face Detection

This script demonstrates how the IRDS integration works with
live face pain detection from a YouTube video.

Usage:
    # Test with default YouTube video
    python integration/test_with_face_detection.py
    
    # Test with custom YouTube link
    python integration/test_with_face_detection.py --url "https://youtube.com/watch?v=..."
    
    # Test with webcam
    python integration/test_with_face_detection.py --webcam
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.irds_interface import (
    FeedbackPublisher,
    GestureModifier,
    face_to_feedback,
    PainFeedback
)


def print_header():
    print("\n" + "=" * 70)
    print("  IRDS Integration Test - Face Pain Detection")
    print("=" * 70)


def print_feedback(feedback: PainFeedback, step: int):
    """Print feedback in a nice format."""
    # Pain level emoji
    emojis = ["😊", "😐", "😣", "😖", "😫"]
    emoji = emojis[min(feedback.pain_level, 4)]
    
    # Color codes for terminal
    colors = {
        0: "\033[92m",  # Green
        1: "\033[93m",  # Yellow
        2: "\033[93m",  # Yellow
        3: "\033[91m",  # Red
        4: "\033[91m",  # Bright Red
    }
    reset = "\033[0m"
    color = colors.get(feedback.pain_level, reset)
    
    print(f"\n{'─' * 70}")
    print(f"  Step {step} | {color}{emoji} {feedback.pain_level_name}{reset}")
    print(f"{'─' * 70}")
    print(f"  Pain Score: {feedback.pain_score:.1f}%")
    print(f"  Confidence: {feedback.confidence:.2f}")
    print()
    print(f"  IRDS Gesture Modifiers:")
    print(f"    Speed:     {feedback.speed_modifier:.2f} ({feedback.speed_modifier*100:.0f}%)")
    print(f"    Amplitude: {feedback.amplitude_modifier:.2f} ({feedback.amplitude_modifier*100:.0f}%)")
    print(f"    Force:     {feedback.force_modifier:.2f} ({feedback.force_modifier*100:.0f}%)")
    print()
    
    if feedback.should_stop:
        print(f"  {color}🛑 EMERGENCY STOP TRIGGERED!{reset}")
    elif feedback.should_pause:
        print(f"  {color}⏸️  GESTURE PAUSED{reset}")
    else:
        print(f"  ✓ Gesture executing normally")


def monitor_feedback_file(feedback_file: Path, stop_event: threading.Event):
    """Monitor the feedback file and print updates."""
    last_mtime = 0
    step = 0
    
    print("\n📊 Monitoring pain feedback...")
    print("   (Modifiers update as face detection runs)\n")
    
    while not stop_event.is_set():
        try:
            if feedback_file.exists():
                mtime = feedback_file.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    step += 1
                    
                    with open(feedback_file) as f:
                        data = json.load(f)
                    
                    feedback = PainFeedback.from_dict(data)
                    print_feedback(feedback, step)
        except Exception as e:
            pass
        
        time.sleep(0.5)


def run_face_detection(source: str, output_file: Path):
    """Run face detection in a subprocess."""
    import subprocess
    
    # Build the curl command to start face detection
    # The face detection dashboard API expects source_type and source
    
    if source.startswith(('http://', 'https://', 'www.')):
        source_type = 'youtube'
    elif source == '0' or source.lower() == 'webcam':
        source_type = 'webcam'
        source = '0'
    else:
        source_type = 'file'
    
    print(f"\n🎥 Starting face detection...")
    print(f"   Source: {source}")
    print(f"   Type: {source_type}")
    
    # Import and use the pain detector directly
    from face_detection.pain_detector import PainDetector
    from face_detection.video_source import VideoSource
    
    detector = PainDetector()
    video = VideoSource()
    modifier = GestureModifier()
    publisher = FeedbackPublisher(output_file=str(output_file))
    
    # Connect to video source
    if source_type == 'youtube':
        success = video.open_youtube(source)
    elif source_type == 'webcam':
        success = video.open_webcam(int(source))
    else:
        success = video.open_file(source)
    
    if not success:
        print(f"❌ Failed to open video source: {source}")
        return False
    
    print(f"✓ Video source opened")
    print(f"\n📤 Publishing feedback to: {output_file}")
    
    frame_count = 0
    try:
        while True:
            frame = video.read_frame()
            if frame is None:
                break
            
            # Detect pain
            result = detector.detect_pain(frame)
            frame_count += 1
            
            # Create mock reading for conversion
            class MockFaceReading:
                def __init__(self, r):
                    self.pain_score = r['pain_score']
                    self.level = r['level']
                    self.brow_furrow = r['features'].get('brow_furrow', 0)
                    self.eye_squeeze = r['features'].get('eye_squeeze', 0)
                    self.nose_wrinkle = r['features'].get('nose_wrinkle', 0)
                    self.lip_raise = r['features'].get('lip_raise', 0)
                    self.face_detected = r['face_detected']
                    self.frame_number = frame_count
            
            reading = MockFaceReading(result)
            feedback = face_to_feedback(reading, modifier)
            publisher.publish(feedback)
            
            # Small delay to not overwhelm
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        pass
    finally:
        video.release()
        publisher.close()
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test IRDS integration with face detection')
    parser.add_argument('--url', type=str, 
                        default='https://www.youtube.com/watch?v=5qap5aO4i9A',
                        help='YouTube URL for face detection')
    parser.add_argument('--webcam', action='store_true',
                        help='Use webcam instead of YouTube')
    parser.add_argument('--file', type=str,
                        help='Use video file')
    parser.add_argument('--monitor-only', action='store_true',
                        help='Only monitor existing feedback file')
    args = parser.parse_args()
    
    print_header()
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    output_file = project_root / "data" / "irds_feedback.json"
    output_file.parent.mkdir(exist_ok=True)
    
    if args.monitor_only:
        # Just monitor the feedback file
        stop_event = threading.Event()
        try:
            monitor_feedback_file(output_file, stop_event)
        except KeyboardInterrupt:
            stop_event.set()
        return
    
    # Determine source
    if args.webcam:
        source = '0'
    elif args.file:
        source = args.file
    else:
        source = args.url
    
    # Start monitoring in background
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_feedback_file,
        args=(output_file, stop_event),
        daemon=True
    )
    monitor_thread.start()
    
    print("\n" + "─" * 70)
    print("  Press Ctrl+C to stop")
    print("─" * 70)
    
    try:
        # Run face detection
        run_face_detection(source, output_file)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        print("\n\n✓ Test complete!")
        print(f"  Feedback saved to: {output_file}")
        print("\n  To use in IRDS:")
        print(f"    feedback_file = '{output_file}'")
        print("    # Read and apply modifiers to gesture execution")


if __name__ == '__main__':
    main()

