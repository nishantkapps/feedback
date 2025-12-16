#!/usr/bin/env python3
"""
Robotic Arm Feedback System - Main Runner
==========================================

Simple script to run and test the piezo sensor pressure detection module.
Supports both real Arduino hardware and file-based simulation for testing.

Usage:
    python run.py              # Auto-detect mode (file if no Arduino found)
    python run.py --file       # Force file-based simulation
    python run.py --hardware   # Force hardware mode
    python run.py --speed 2    # Playback at 2x speed (file mode only)
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sensors.piezo_reader import PiezoSensor, PressureReading
from sensors.file_reader import FilePiezoSensor


# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ORANGE = "\033[33m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


# Color mapping for pressure levels
LEVEL_COLORS = {
    "NONE": Colors.GREEN,
    "LIGHT": Colors.YELLOW,
    "MODERATE": Colors.ORANGE,
    "HIGH": Colors.RED,
    "CRITICAL": Colors.MAGENTA,
}


def create_progress_bar(percent: float, width: int = 40) -> str:
    """Create a visual progress bar for pressure level."""
    filled = int(percent / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def display_reading(reading: PressureReading):
    """Display a single pressure reading with visual formatting."""
    color = LEVEL_COLORS.get(reading.level, Colors.RESET)
    bar = create_progress_bar(reading.percent)
    
    # Format output
    output = (
        f"\r{color}"
        f"[{bar}] "
        f"{reading.percent:5.1f}% "
        f"| Level: {reading.level:8s} "
        f"| Raw: {reading.raw:4d} "
        f"| Filtered: {reading.filtered:4d}"
        f"{Colors.RESET}"
    )
    
    print(output, end="", flush=True)


def display_reading_detailed(reading: PressureReading):
    """Display detailed reading information."""
    color = LEVEL_COLORS.get(reading.level, Colors.RESET)
    bar = create_progress_bar(reading.percent)
    
    print(f"\n{Colors.BOLD}{'─' * 60}{Colors.RESET}")
    print(f"{color}Pressure Level: {reading.level}{Colors.RESET}")
    print(f"[{bar}] {reading.percent:.2f}%")
    print(f"Raw Value: {reading.raw} | Filtered: {reading.filtered}")
    print(f"Pressure: {reading.pressure} | Timestamp: {reading.timestamp}ms")


class FeedbackController:
    """
    Simple feedback controller that responds to pressure levels.
    In a real system, this would interface with the robotic arm.
    """
    
    def __init__(self):
        self.arm_speed = 100  # Percentage
        self.arm_active = True
        self.last_alert_time = 0
        self.alert_cooldown = 2.0  # Seconds between alerts
    
    def process_reading(self, reading: PressureReading):
        """Process a reading and determine robotic arm response."""
        current_time = time.time()
        
        # Determine action based on pressure level
        if reading.level == "CRITICAL":
            self._emergency_stop(reading)
        elif reading.level == "HIGH":
            self._reduce_speed(reading, target_speed=20)
        elif reading.level == "MODERATE":
            self._reduce_speed(reading, target_speed=50)
        elif reading.level == "LIGHT":
            self._reduce_speed(reading, target_speed=80)
        else:  # NONE
            self._normal_operation(reading)
    
    def _emergency_stop(self, reading: PressureReading):
        """Emergency stop the robotic arm."""
        if self.arm_active:
            self.arm_active = False
            self.arm_speed = 0
            self._alert(f"\n{Colors.MAGENTA}{Colors.BOLD}"
                       f"⚠️  EMERGENCY STOP! Critical pressure detected: {reading.percent:.1f}%"
                       f"{Colors.RESET}\n")
    
    def _reduce_speed(self, reading: PressureReading, target_speed: int):
        """Reduce arm speed based on pressure."""
        if self.arm_speed > target_speed:
            self.arm_speed = target_speed
            if not self.arm_active:
                self.arm_active = True
    
    def _normal_operation(self, reading: PressureReading):
        """Resume normal operation."""
        if not self.arm_active:
            self.arm_active = True
            self._alert(f"\n{Colors.GREEN}✓ Resuming normal operation{Colors.RESET}\n")
        self.arm_speed = 100
    
    def _alert(self, message: str):
        """Display alert with cooldown."""
        current_time = time.time()
        if current_time - self.last_alert_time > self.alert_cooldown:
            print(message)
            self.last_alert_time = current_time


def run_with_hardware():
    """Run with actual Arduino hardware."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}Hardware Mode{Colors.RESET}")
    print("Searching for Arduino...")
    
    ports = PiezoSensor.list_available_ports()
    if not ports:
        print(f"{Colors.RED}No serial ports found. Is Arduino connected?{Colors.RESET}")
        return False
    
    print(f"Available ports: {ports}")
    
    try:
        with PiezoSensor() as sensor:
            print(f"{Colors.GREEN}Connected! Baseline: {sensor.baseline}{Colors.RESET}")
            return _run_sensor_loop(sensor)
    except ConnectionError as e:
        print(f"{Colors.RED}Connection error: {e}{Colors.RESET}")
        return False


def run_with_file(filepath: str, speed: float = 1.0, loop: bool = True):
    """Run with file-based simulation."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}File Simulation Mode{Colors.RESET}")
    print(f"Data file: {filepath}")
    print(f"Playback speed: {speed}x")
    
    if not Path(filepath).exists():
        print(f"{Colors.RED}Data file not found: {filepath}{Colors.RESET}")
        return False
    
    try:
        with FilePiezoSensor(filepath, playback_speed=speed, loop=loop) as sensor:
            print(f"{Colors.GREEN}Loaded {sensor.total_readings} readings{Colors.RESET}")
            return _run_sensor_loop(sensor)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return False


def _run_sensor_loop(sensor):
    """Main sensor reading loop."""
    controller = FeedbackController()
    
    def on_reading(reading: PressureReading):
        display_reading(reading)
        controller.process_reading(reading)
    
    print(f"\n{Colors.BOLD}Press Ctrl+C to stop{Colors.RESET}\n")
    
    sensor.start_reading(callback=on_reading)
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Stopping...{Colors.RESET}")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Robotic Arm Feedback System - Piezo Sensor Module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py              # Auto-detect (uses file if no Arduino)
  python run.py --file       # Force file simulation
  python run.py --hardware   # Force hardware mode
  python run.py --speed 5    # 5x playback speed
  python run.py --data custom_data.csv  # Use custom data file
        """
    )
    
    parser.add_argument(
        "--file", "-f",
        action="store_true",
        help="Use file-based simulation instead of hardware"
    )
    parser.add_argument(
        "--hardware", "-hw",
        action="store_true",
        help="Force hardware mode (fail if no Arduino)"
    )
    parser.add_argument(
        "--data", "-d",
        type=str,
        default="data/sample_sensor_data.csv",
        help="Path to sensor data CSV file (default: data/sample_sensor_data.csv)"
    )
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=1.0,
        help="Playback speed multiplier for file mode (default: 1.0)"
    )
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="Don't loop the data file"
    )
    
    args = parser.parse_args()
    
    # Print header
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  Robotic Arm Feedback System - Piezo Sensor Module{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    
    # Determine mode
    if args.hardware:
        success = run_with_hardware()
    elif args.file:
        success = run_with_file(args.data, args.speed, not args.no_loop)
    else:
        # Auto-detect: try hardware first, fall back to file
        print("\nAuto-detecting mode...")
        ports = PiezoSensor.list_available_ports()
        
        if ports:
            print(f"Arduino detected on {ports}")
            success = run_with_hardware()
        else:
            print("No Arduino found, using file simulation")
            success = run_with_file(args.data, args.speed, not args.no_loop)
    
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

