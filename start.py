#!/usr/bin/env python3
"""
Quick Start Script for Piezo Sensor Dashboard
Run: python start.py
"""

import subprocess
import sys
import webbrowser
import time
from pathlib import Path

def main():
    # Get project root
    project_root = Path(__file__).parent
    
    # Default data file
    data_file = project_root / "data" / "sample_sensor_data.csv"
    
    # Allow custom data file as argument
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    
    print("\n" + "=" * 50)
    print("  🤖 Piezo Sensor Dashboard - Quick Start")
    print("=" * 50)
    print(f"\nData file: {data_file}")
    print("Starting web server...")
    
    # Open browser after a short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:5000")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start the Flask app
    web_app = project_root / "web" / "app.py"
    subprocess.run([sys.executable, str(web_app), str(data_file)])

if __name__ == "__main__":
    main()

