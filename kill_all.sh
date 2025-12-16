#!/bin/bash
# Kill all running feedback system processes

echo "Killing feedback system processes..."

# Kill by process name patterns
pkill -f "face_detection" 2>/dev/null
pkill -f "piezo" 2>/dev/null
pkill -f "start.py" 2>/dev/null
pkill -f "web/app.py" 2>/dev/null
pkill -f "flask" 2>/dev/null

# Kill by port
fuser -k 5000/tcp 2>/dev/null
fuser -k 5001/tcp 2>/dev/null

# Kill any python processes with our modules
pkill -f "sensors.piezo_reader" 2>/dev/null
pkill -f "sensors.file_reader" 2>/dev/null
pkill -f "pain_detector" 2>/dev/null

echo "Done! All processes killed."
echo ""
echo "To restart:"
echo "  Piezo sensor:    python start.py"
echo "  Face detection:  python face_detection/start.py"

