#!/usr/bin/env python3
"""
Simple Test Script for IRDS Integration

Tests the full pipeline: Face Detection → IRDS Feedback

Usage:
    # Test with a YouTube video (default: a face video)
    python integration/run_test.py
    
    # Test with custom YouTube URL
    python integration/run_test.py --url "https://youtube.com/watch?v=..."
    
    # Test with webcam
    python integration/run_test.py --webcam
"""

import sys
import os
import time
import json
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from integration.irds_interface import GestureModifier, face_to_feedback, FeedbackPublisher


def create_face_reading(result, frame_num):
    """Create a reading object from detector result."""
    class FaceReading:
        def __init__(self, r, fn):
            self.pain_score = r.get('pain_score', 0)
            self.level = r.get('level', 'NONE')
            self.brow_furrow = r.get('features', {}).get('brow_furrow', 0)
            self.eye_squeeze = r.get('features', {}).get('eye_squeeze', 0)
            self.nose_wrinkle = r.get('features', {}).get('nose_wrinkle', 0)
            self.lip_raise = r.get('features', {}).get('lip_raise', 0)
            self.face_detected = r.get('face_detected', False)
            self.frame_number = fn
    return FaceReading(result, frame_num)


def print_status(feedback, frame):
    """Print current status."""
    emojis = ["😊", "😐", "😣", "😖", "😫"]
    emoji = emojis[min(feedback.pain_level, 4)]
    
    # Colors
    colors = ["\033[92m", "\033[93m", "\033[93m", "\033[91m", "\033[91m"]
    color = colors[min(feedback.pain_level, 4)]
    reset = "\033[0m"
    
    status = f"{color}{emoji} {feedback.pain_level_name:10}{reset}"
    
    line = (f"Frame {frame:4d} | {status} | "
            f"Score: {feedback.pain_score:5.1f}% | "
            f"Speed: {feedback.speed_modifier:.0%} | "
            f"Amp: {feedback.amplitude_modifier:.0%}")
    
    if feedback.should_stop:
        line += f" | {color}🛑 STOP!{reset}"
    elif feedback.should_pause:
        line += f" | {color}⏸️ PAUSE{reset}"
    
    print(f"\r{line}", end="", flush=True)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Test IRDS integration')
    parser.add_argument('--url', type=str,
                        default='https://www.youtube.com/watch?v=5qap5aO4i9A',
                        help='YouTube URL')
    parser.add_argument('--webcam', action='store_true', help='Use webcam')
    parser.add_argument('--file', type=str, help='Video file path')
    parser.add_argument('--max-frames', type=int, default=300,
                        help='Max frames to process (default: 300)')
    args = parser.parse_args()
    
    print("=" * 70)
    print("  IRDS Integration Test - Face Pain Detection")
    print("=" * 70)
    
    # Setup output
    output_file = project_root / "data" / "irds_feedback.json"
    output_file.parent.mkdir(exist_ok=True)
    
    print(f"\n📤 Output: {output_file}")
    
    # Import face detection modules
    print("\n📦 Loading face detection modules...")
    try:
        from face_detection.pain_detector import PainDetector
        from face_detection.video_source import VideoSource
    except ImportError as e:
        print(f"❌ Failed to import: {e}")
        print("   Make sure you're in the project directory")
        return 1
    
    # Initialize
    detector = PainDetector()
    modifier = GestureModifier()
    publisher = FeedbackPublisher(output_file=str(output_file))
    
    # Open video source
    if args.webcam:
        source = "Webcam"
        print(f"\n🎥 Opening webcam...")
        video = VideoSource(camera=0)
    elif args.file:
        source = args.file
        print(f"\n🎥 Opening file: {source}")
        video = VideoSource(file_path=args.file)
    else:
        source = args.url
        print(f"\n🎥 Opening YouTube: {source}")
        print("   (This may take a moment...)")
        video = VideoSource(youtube_url=args.url, youtube_quality='medium')
    
    success = video.open()
    if not success:
        print(f"\n❌ Failed to open video source")
        return 1
    
    print(f"✓ Video opened successfully")
    print(f"\n📊 Processing (max {args.max_frames} frames)...")
    print("   Press Ctrl+C to stop\n")
    print("-" * 70)
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while frame_count < args.max_frames:
            frame_info = video.read_frame()
            if frame_info is None:
                print("\n\n📹 Video ended")
                break
            
            frame_count += 1
            
            # Detect pain
            result = detector.detect_pain(frame_info.frame)
            
            # Convert to feedback
            reading = create_face_reading(result, frame_count)
            feedback = face_to_feedback(reading, modifier)
            
            # Publish
            publisher.publish(feedback)
            
            # Print status
            print_status(feedback, frame_count)
            
            # Small delay
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    
    finally:
        video.close()
        publisher.close()
    
    # Summary
    elapsed = time.time() - start_time
    fps = frame_count / elapsed if elapsed > 0 else 0
    
    print("\n" + "-" * 70)
    print(f"\n✓ Test complete!")
    print(f"  Frames processed: {frame_count}")
    print(f"  Time: {elapsed:.1f}s ({fps:.1f} fps)")
    print(f"  Output: {output_file}")
    
    # Show last feedback
    print(f"\n📋 Last feedback (for IRDS):")
    with open(output_file) as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

