#!/usr/bin/env python3
"""
Quick Start Script for Face Pain Detection Dashboard
Run: python face_detection/start.py
"""

import subprocess
import sys
import webbrowser
import time
from pathlib import Path


def check_dependencies():
    """Check if required packages are installed."""
    missing = []
    
    try:
        import cv2
    except ImportError:
        missing.append('opencv-python')
        missing.append('opencv-contrib-python')
    
    try:
        import cv2.face
    except (ImportError, AttributeError):
        if 'opencv-contrib-python' not in missing:
            missing.append('opencv-contrib-python')
    
    try:
        import flask
    except ImportError:
        missing.append('flask')
    
    try:
        import numpy
    except ImportError:
        missing.append('numpy')
    
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print("Installing...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q'] + missing)
        print("Installation complete!\n")


def main():
    # Get paths
    script_dir = Path(__file__).parent
    web_app = script_dir / "web" / "app.py"
    
    print("\n" + "=" * 50)
    print("  😊 Face Pain Detection Dashboard - Quick Start")
    print("=" * 50)
    
    # Check dependencies
    check_dependencies()
    
    # Parse arguments
    video_file = None
    port = 5001
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ['--video', '-v'] and i + 1 < len(args):
            video_file = args[i + 1]
            i += 2
        elif args[i] in ['--port', '-p'] and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1
    
    print(f"\nDashboard URL: http://localhost:{port}")
    if video_file:
        print(f"Video file: {video_file}")
    else:
        print("Source: Webcam (default)")
    
    print("\nStarting server...")
    
    # Open browser after delay
    def open_browser():
        time.sleep(2)
        webbrowser.open(f"http://localhost:{port}")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start Flask app
    cmd = [sys.executable, str(web_app), '--port', str(port)]
    if video_file:
        cmd.extend(['--video', video_file])
    
    subprocess.run(cmd)


if __name__ == "__main__":
    main()

