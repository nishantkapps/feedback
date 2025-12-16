"""
File-based Sensor Reader for Testing
Part of Robotic Arm Feedback System

This module provides a mock sensor interface that reads from CSV files,
allowing testing without actual hardware.
"""

import csv
import time
import threading
from pathlib import Path
from typing import Callable, Optional, Iterator
from collections import deque

from .piezo_reader import PressureReading


class FilePiezoSensor:
    """
    Mock piezo sensor that reads data from a CSV file.
    Useful for testing and development without hardware.
    
    Usage:
        sensor = FilePiezoSensor('data/sample_sensor_data.csv')
        sensor.connect()
        sensor.start_reading(callback=lambda r: print(r))
    """
    
    # Pressure level constants (same as real sensor)
    LEVEL_NONE = "NONE"
    LEVEL_LIGHT = "LIGHT"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_HIGH = "HIGH"
    LEVEL_CRITICAL = "CRITICAL"
    
    def __init__(
        self,
        filepath: str,
        playback_speed: float = 1.0,
        loop: bool = True,
        history_size: int = 100
    ):
        """
        Initialize the file-based sensor reader.
        
        Args:
            filepath: Path to CSV file with sensor data
            playback_speed: Speed multiplier (1.0 = real-time, 2.0 = 2x speed)
            loop: Whether to loop back to start when file ends
            history_size: Number of readings to keep in history
        """
        self.filepath = Path(filepath)
        self.playback_speed = playback_speed
        self.loop = loop
        self.history_size = history_size
        
        self._data: list[dict] = []
        self._current_index = 0
        self._reading_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._finished_flag = threading.Event()  # Signals when playback is done
        self._history: deque = deque(maxlen=history_size)
        self._callbacks: list[Callable[[PressureReading], None]] = []
        self._is_connected = False
        self._baseline = 512  # Default baseline
        
    def connect(self) -> bool:
        """
        Load the CSV file and prepare for reading.
        
        Returns:
            True if file loaded successfully
        """
        if not self.filepath.exists():
            raise FileNotFoundError(f"Sensor data file not found: {self.filepath}")
        
        self._data = []
        
        with open(self.filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._data.append({
                    'timestamp': int(row['timestamp']),
                    'raw': int(row['raw']),
                    'filtered': int(row['filtered']),
                    'pressure': int(row['pressure']),
                    'percent': float(row['percent']),
                    'level': row['level']
                })
        
        if not self._data:
            raise ValueError("CSV file is empty or has invalid format")
        
        self._current_index = 0
        self._is_connected = True
        print(f"Loaded {len(self._data)} readings from {self.filepath}")
        return True
    
    def disconnect(self):
        """Stop reading and clean up."""
        self.stop_reading()
        self._is_connected = False
        print("File sensor disconnected")
    
    def _create_reading(self, data: dict) -> PressureReading:
        """Create a PressureReading from CSV data."""
        return PressureReading(
            raw=data['raw'],
            filtered=data['filtered'],
            pressure=data['pressure'],
            percent=data['percent'],
            level=data['level'],
            timestamp=data['timestamp'],
            received_at=time.time()
        )
    
    def read_once(self) -> Optional[PressureReading]:
        """
        Read the next data point from the file.
        
        Returns:
            PressureReading or None if at end and not looping
        """
        if not self._is_connected or not self._data:
            return None
        
        if self._current_index >= len(self._data):
            if self.loop:
                self._current_index = 0
            else:
                return None
        
        data = self._data[self._current_index]
        self._current_index += 1
        
        return self._create_reading(data)
    
    def start_reading(
        self,
        callback: Optional[Callable[[PressureReading], None]] = None
    ):
        """
        Start continuous reading with timing based on timestamps.
        
        Args:
            callback: Function to call with each reading
        """
        if self._reading_thread and self._reading_thread.is_alive():
            print("Already reading")
            return
        
        if callback:
            self._callbacks.append(callback)
        
        self._current_index = 0
        self._stop_flag.clear()
        self._finished_flag.clear()
        self._reading_thread = threading.Thread(target=self._reading_loop, daemon=True)
        self._reading_thread.start()
        print(f"Started playback at {self.playback_speed}x speed")
    
    def stop_reading(self):
        """Stop continuous reading."""
        self._stop_flag.set()
        
        if self._reading_thread:
            self._reading_thread.join(timeout=2.0)
            self._reading_thread = None
        
        self._callbacks.clear()
        print("Stopped reading")
    
    def _reading_loop(self):
        """Background thread for timed playback."""
        last_timestamp = None
        
        while not self._stop_flag.is_set():
            reading = self.read_once()
            
            if reading is None:
                if not self.loop:
                    print("\nEnd of data file reached")
                    self._finished_flag.set()
                    break
                continue
            
            # Calculate delay based on timestamps
            if last_timestamp is not None:
                delay = (reading.timestamp - last_timestamp) / 1000.0  # Convert ms to seconds
                delay /= self.playback_speed
                
                if delay > 0:
                    time.sleep(delay)
            
            last_timestamp = reading.timestamp
            
            self._history.append(reading)
            
            for callback in self._callbacks:
                try:
                    callback(reading)
                except Exception as e:
                    print(f"Callback error: {e}")
        
        self._finished_flag.set()
    
    def add_callback(self, callback: Callable[[PressureReading], None]):
        """Add a callback for readings."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PressureReading], None]):
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_history(self) -> list[PressureReading]:
        """Get history of recent readings."""
        return list(self._history)
    
    def get_latest(self) -> Optional[PressureReading]:
        """Get the most recent reading."""
        return self._history[-1] if self._history else None
    
    def is_pressure_critical(self) -> bool:
        """Check if current pressure is critical."""
        latest = self.get_latest()
        return latest and latest.level == self.LEVEL_CRITICAL
    
    def is_pressure_high(self) -> bool:
        """Check if current pressure is high or above."""
        latest = self.get_latest()
        return latest and latest.level in [self.LEVEL_HIGH, self.LEVEL_CRITICAL]
    
    def get_average_pressure(self, samples: int = 10) -> float:
        """Calculate average pressure from recent readings."""
        history = list(self._history)
        if not history:
            return 0.0
        recent = history[-samples:]
        return sum(r.percent for r in recent) / len(recent)
    
    @property
    def is_connected(self) -> bool:
        """Check if connected (file loaded)."""
        return self._is_connected
    
    @property
    def is_finished(self) -> bool:
        """Check if playback has finished (only relevant when loop=False)."""
        return self._finished_flag.is_set()
    
    @property
    def baseline(self) -> int:
        """Get baseline value."""
        return self._baseline
    
    @property
    def total_readings(self) -> int:
        """Get total number of readings in file."""
        return len(self._data)
    
    @property
    def current_position(self) -> int:
        """Get current position in file."""
        return self._current_index
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

