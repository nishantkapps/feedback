#!/usr/bin/env python3
"""
Simple IRDS Feedback Monitor

Run this while face detection dashboard is running to see
how the gesture modifiers change in real-time.

Usage:
    # Step 1: Start face detection in another terminal
    python face_detection/start.py
    
    # Step 2: In browser, select YouTube and enter a URL
    
    # Step 3: Run this monitor
    python integration/monitor_irds.py
"""

import sys
import time
import json
from pathlib import Path

def main():
    feedback_file = Path(__file__).parent.parent / "data" / "irds_feedback.json"
    
    print("=" * 60)
    print("  IRDS Feedback Monitor")
    print("=" * 60)
    print(f"\n📁 Watching: {feedback_file}")
    print("\n💡 To generate feedback:")
    print("   1. Run: python face_detection/start.py")
    print("   2. Open: http://localhost:5001")
    print("   3. Select YouTube and enter a video URL")
    print("   4. Click 'Start Analysis'")
    print("\n   Or run: python integration/irds_bridge.py --demo")
    print("\nPress Ctrl+C to stop\n")
    print("=" * 60)
    
    last_mtime = 0
    emojis = ["😊 NONE", "😐 LIGHT", "😣 MODERATE", "😖 HIGH", "😫 CRITICAL"]
    
    try:
        while True:
            if feedback_file.exists():
                mtime = feedback_file.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    
                    with open(feedback_file) as f:
                        data = json.load(f)
                    
                    level = data.get('pain_level', 0)
                    score = data.get('pain_score', 0)
                    speed = data.get('speed_modifier', 1.0)
                    amp = data.get('amplitude_modifier', 1.0)
                    force = data.get('force_modifier', 1.0)
                    pause = data.get('should_pause', False)
                    stop = data.get('should_stop', False)
                    
                    # Clear line and print
                    status = emojis[min(level, 4)]
                    
                    print(f"\r{status:15} | Score: {score:5.1f}% | "
                          f"Speed: {speed:.0%} | Amp: {amp:.0%} | Force: {force:.0%}", end="")
                    
                    if stop:
                        print(" | 🛑 STOP!", end="")
                    elif pause:
                        print(" | ⏸️ PAUSE", end="")
                    
                    print("          ", end="", flush=True)
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\n\n✓ Monitor stopped")


if __name__ == '__main__':
    main()

