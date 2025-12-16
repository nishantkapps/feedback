"""
Piezo Sensor Reader Module
Part of Robotic Arm Feedback System

This module handles serial communication with an Arduino running
the piezo sensor sketch and processes pressure readings.
"""

import json
import time
import threading
from dataclasses import dataclass
from typing import Callable, Optional
from collections import deque

import serial
import serial.tools.list_ports


@dataclass
class PressureReading:
    """Data class representing a single pressure reading."""
    raw: int
    filtered: int
    pressure: int
    percent: float
    level: str
    timestamp: int
    received_at: float  # Python timestamp when data was received


class PiezoSensor:
    """
    Interface for reading piezo sensor data from Arduino.
    
    Usage:
        sensor = PiezoSensor(port='/dev/ttyUSB0')
        sensor.connect()
        
        # Continuous reading with callback
        sensor.start_reading(callback=lambda reading: print(reading))
        
        # Or single reading
        reading = sensor.read_once()
    """
    
    # Pressure level thresholds for feedback system
    LEVEL_NONE = "NONE"
    LEVEL_LIGHT = "LIGHT"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 115200,
        timeout: float = 1.0,
        history_size: int = 100
    ):
        """
        Initialize the piezo sensor reader.
        
        Args:
            port: Serial port (auto-detect if None)
            baudrate: Serial communication speed (must match Arduino)
            timeout: Serial read timeout in seconds
            history_size: Number of readings to keep in history
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.history_size = history_size
        
        self._serial: Optional[serial.Serial] = None
        self._reading_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._history: deque = deque(maxlen=history_size)
        self._callbacks: list[Callable[[PressureReading], None]] = []
        self._is_ready = False
        self._baseline: Optional[int] = None
        
    @staticmethod
    def list_available_ports() -> list[str]:
        """List all available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    @staticmethod
    def find_arduino_port() -> Optional[str]:
        """
        Attempt to auto-detect Arduino port.
        
        Returns:
            Port string if found, None otherwise
        """
        ports = serial.tools.list_ports.comports()
        
        # Common Arduino identifiers
        arduino_keywords = ['arduino', 'ch340', 'cp210', 'ftdi', 'usb', 'acm']
        
        for port in ports:
            description = (port.description or '').lower()
            manufacturer = (port.manufacturer or '').lower()
            
            for keyword in arduino_keywords:
                if keyword in description or keyword in manufacturer:
                    return port.device
        
        # Fallback: return first USB/ACM port
        for port in ports:
            if 'usb' in port.device.lower() or 'acm' in port.device.lower():
                return port.device
                
        return None
    
    def connect(self) -> bool:
        """
        Establish connection to the Arduino.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._serial and self._serial.is_open:
            return True
            
        # Auto-detect port if not specified
        if not self.port:
            self.port = self.find_arduino_port()
            if not self.port:
                raise ConnectionError(
                    "Could not auto-detect Arduino. "
                    f"Available ports: {self.list_available_ports()}"
                )
        
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Wait for Arduino to reset after serial connection
            time.sleep(2)
            
            # Wait for READY signal
            self._wait_for_ready()
            
            print(f"Connected to piezo sensor on {self.port}")
            return True
            
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to {self.port}: {e}")
    
    def _wait_for_ready(self, timeout: float = 10.0):
        """Wait for Arduino to complete initialization."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._serial.in_waiting:
                line = self._serial.readline().decode('utf-8', errors='ignore').strip()
                print(f"Arduino: {line}")
                
                if line == "READY":
                    self._is_ready = True
                    return
                    
                # Parse baseline value
                if line.startswith("Baseline calibrated:"):
                    try:
                        self._baseline = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
        
        raise TimeoutError("Arduino did not send READY signal")
    
    def disconnect(self):
        """Close the serial connection."""
        self.stop_reading()
        
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("Disconnected from piezo sensor")
    
    def read_once(self) -> Optional[PressureReading]:
        """
        Read a single pressure value.
        
        Returns:
            PressureReading object or None if read failed
        """
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Not connected to sensor")
        
        try:
            line = self._serial.readline().decode('utf-8', errors='ignore').strip()
            
            if line.startswith('{'):
                return self._parse_reading(line)
                
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
            
        return None
    
    def _parse_reading(self, json_str: str) -> PressureReading:
        """Parse a JSON reading from Arduino."""
        data = json.loads(json_str)
        
        return PressureReading(
            raw=data['raw'],
            filtered=data['filtered'],
            pressure=data['pressure'],
            percent=data['percent'],
            level=data['level'],
            timestamp=data['timestamp'],
            received_at=time.time()
        )
    
    def start_reading(
        self,
        callback: Optional[Callable[[PressureReading], None]] = None
    ):
        """
        Start continuous reading in a background thread.
        
        Args:
            callback: Function to call with each new reading
        """
        if self._reading_thread and self._reading_thread.is_alive():
            print("Already reading")
            return
            
        if callback:
            self._callbacks.append(callback)
        
        self._stop_flag.clear()
        self._reading_thread = threading.Thread(target=self._reading_loop, daemon=True)
        self._reading_thread.start()
        print("Started continuous reading")
    
    def stop_reading(self):
        """Stop continuous reading."""
        self._stop_flag.set()
        
        if self._reading_thread:
            self._reading_thread.join(timeout=2.0)
            self._reading_thread = None
            
        self._callbacks.clear()
        print("Stopped reading")
    
    def _reading_loop(self):
        """Background thread for continuous reading."""
        while not self._stop_flag.is_set():
            reading = self.read_once()
            
            if reading:
                self._history.append(reading)
                
                for callback in self._callbacks:
                    try:
                        callback(reading)
                    except Exception as e:
                        print(f"Callback error: {e}")
    
    def add_callback(self, callback: Callable[[PressureReading], None]):
        """Add a callback for pressure readings."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PressureReading], None]):
        """Remove a previously added callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_history(self) -> list[PressureReading]:
        """Get the history of recent readings."""
        return list(self._history)
    
    def get_latest(self) -> Optional[PressureReading]:
        """Get the most recent reading."""
        return self._history[-1] if self._history else None
    
    def calibrate(self) -> bool:
        """
        Request recalibration of the sensor baseline.
        
        Returns:
            True if calibration successful
        """
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Not connected to sensor")
        
        self._serial.write(b"CALIBRATE\n")
        
        # Wait for calibration response
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if self._serial.in_waiting:
                line = self._serial.readline().decode('utf-8', errors='ignore').strip()
                
                if "New baseline:" in line:
                    try:
                        self._baseline = int(line.split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
                        
                if line == "CALIBRATION_COMPLETE":
                    print(f"Calibration complete. New baseline: {self._baseline}")
                    return True
        
        return False
    
    def is_pressure_critical(self) -> bool:
        """Check if current pressure level is critical."""
        latest = self.get_latest()
        return latest and latest.level == self.LEVEL_CRITICAL
    
    def is_pressure_high(self) -> bool:
        """Check if current pressure level is high or above."""
        latest = self.get_latest()
        return latest and latest.level in [self.LEVEL_HIGH, self.LEVEL_CRITICAL]
    
    def get_average_pressure(self, samples: int = 10) -> float:
        """
        Calculate average pressure from recent readings.
        
        Args:
            samples: Number of recent samples to average
            
        Returns:
            Average pressure percentage
        """
        history = list(self._history)
        if not history:
            return 0.0
            
        recent = history[-samples:]
        return sum(r.percent for r in recent) / len(recent)
    
    @property
    def baseline(self) -> Optional[int]:
        """Get the current baseline value."""
        return self._baseline
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to sensor."""
        return self._serial is not None and self._serial.is_open
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


def main():
    """Demo/test function for the piezo sensor module."""
    print("=" * 50)
    print("Piezo Sensor Reader - Demo")
    print("=" * 50)
    
    # List available ports
    ports = PiezoSensor.list_available_ports()
    print(f"\nAvailable serial ports: {ports}")
    
    if not ports:
        print("No serial ports found. Please connect your Arduino.")
        return
    
    # Callback function to display readings
    def display_reading(reading: PressureReading):
        # Create a simple visual bar
        bar_length = int(reading.percent / 2)
        bar = "█" * bar_length + "░" * (50 - bar_length)
        
        # Color code based on level
        level_colors = {
            "NONE": "\033[92m",      # Green
            "LIGHT": "\033[93m",      # Yellow
            "MODERATE": "\033[33m",   # Orange
            "HIGH": "\033[91m",       # Red
            "CRITICAL": "\033[95m",   # Magenta
        }
        reset = "\033[0m"
        color = level_colors.get(reading.level, "")
        
        print(f"\r{color}[{bar}] {reading.percent:5.1f}% | {reading.level:8s}{reset}", end="")
    
    try:
        # Use context manager for automatic connection/disconnection
        with PiezoSensor() as sensor:
            print(f"\nConnected! Baseline: {sensor.baseline}")
            print("\nPress Ctrl+C to stop\n")
            
            # Start reading with callback
            sensor.start_reading(callback=display_reading)
            
            # Keep running until interrupted
            while True:
                time.sleep(0.1)
                
                # Check for critical pressure
                if sensor.is_pressure_critical():
                    print("\n⚠️  CRITICAL PRESSURE DETECTED!")
                    
    except KeyboardInterrupt:
        print("\n\nStopping...")
    except ConnectionError as e:
        print(f"\nConnection error: {e}")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()

