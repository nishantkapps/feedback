"""
IRDS Integration Interface
Provides pain feedback data to the IRDS gesture recognition system
for adjusting gesture parameters based on detected pain levels.

This interface can be used in multiple ways:
1. File-based: Write feedback to JSON files that IRDS can read
2. Socket-based: Real-time TCP/UDP communication
3. Shared memory: For low-latency communication
4. REST API: HTTP endpoints for distributed systems
"""

import json
import time
import threading
import socket
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from enum import Enum
import queue


class PainLevel(Enum):
    """Pain levels matching both piezo and face detection modules."""
    NONE = 0
    LIGHT = 1       # Piezo: LIGHT, Face: MILD
    MODERATE = 2
    HIGH = 3        # Piezo: HIGH, Face: SEVERE
    CRITICAL = 4    # Piezo: CRITICAL, Face: EXTREME


@dataclass
class PainFeedback:
    """
    Pain feedback data structure for IRDS integration.
    
    This data can be used by IRDS to modify gesture execution:
    - speed_modifier: Multiply gesture speed by this value
    - amplitude_modifier: Multiply gesture amplitude by this value
    - force_modifier: Multiply gesture force by this value
    - should_pause: If True, pause gesture execution
    - should_stop: If True, emergency stop
    """
    # Timestamp
    timestamp: float
    
    # Pain metrics
    pain_level: int                    # 0-4 (NONE to CRITICAL)
    pain_level_name: str               # Human-readable level
    pain_score: float                  # 0-100 percentage
    
    # Source information
    source: str                        # 'piezo', 'face', or 'fused'
    confidence: float                  # 0-1 confidence in the reading
    
    # Recommended gesture modifiers
    speed_modifier: float              # 0.0-1.0 (1.0 = full speed)
    amplitude_modifier: float          # 0.0-1.0 (1.0 = full amplitude)
    force_modifier: float              # 0.0-1.0 (1.0 = full force)
    
    # Control flags
    should_pause: bool                 # Pause gesture execution
    should_stop: bool                  # Emergency stop
    
    # Optional detailed metrics
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PainFeedback':
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PainFeedback':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class GestureModifier:
    """
    Calculate gesture modifications based on pain feedback.
    
    Maps pain levels to gesture parameter adjustments that can be
    applied by the IRDS gesture model.
    """
    
    # Default modifier mappings
    DEFAULT_SPEED_MAP = {
        PainLevel.NONE: 1.0,
        PainLevel.LIGHT: 0.8,
        PainLevel.MODERATE: 0.5,
        PainLevel.HIGH: 0.2,
        PainLevel.CRITICAL: 0.0
    }
    
    DEFAULT_AMPLITUDE_MAP = {
        PainLevel.NONE: 1.0,
        PainLevel.LIGHT: 0.9,
        PainLevel.MODERATE: 0.7,
        PainLevel.HIGH: 0.5,
        PainLevel.CRITICAL: 0.0
    }
    
    DEFAULT_FORCE_MAP = {
        PainLevel.NONE: 1.0,
        PainLevel.LIGHT: 0.85,
        PainLevel.MODERATE: 0.6,
        PainLevel.HIGH: 0.3,
        PainLevel.CRITICAL: 0.0
    }
    
    def __init__(
        self,
        speed_map: Optional[Dict[PainLevel, float]] = None,
        amplitude_map: Optional[Dict[PainLevel, float]] = None,
        force_map: Optional[Dict[PainLevel, float]] = None
    ):
        """
        Initialize gesture modifier.
        
        Args:
            speed_map: Custom mapping of pain levels to speed modifiers
            amplitude_map: Custom mapping of pain levels to amplitude modifiers
            force_map: Custom mapping of pain levels to force modifiers
        """
        self.speed_map = speed_map or self.DEFAULT_SPEED_MAP.copy()
        self.amplitude_map = amplitude_map or self.DEFAULT_AMPLITUDE_MAP.copy()
        self.force_map = force_map or self.DEFAULT_FORCE_MAP.copy()
    
    def get_modifiers(
        self,
        pain_level: int,
        pain_score: float,
        source: str = 'piezo'
    ) -> Dict[str, float]:
        """
        Calculate gesture modifiers for given pain level.
        
        Args:
            pain_level: Pain level (0-4)
            pain_score: Pain score (0-100)
            source: Source of pain reading
            
        Returns:
            Dictionary with speed, amplitude, and force modifiers
        """
        level = PainLevel(min(4, max(0, pain_level)))
        
        # Get base modifiers from maps
        speed = self.speed_map.get(level, 1.0)
        amplitude = self.amplitude_map.get(level, 1.0)
        force = self.force_map.get(level, 1.0)
        
        # Fine-tune based on pain score within level
        # Higher pain score within a level = slightly lower modifiers
        score_factor = 1.0 - (pain_score % 20) / 100  # 0.8-1.0 adjustment
        
        return {
            'speed_modifier': speed * score_factor,
            'amplitude_modifier': amplitude * score_factor,
            'force_modifier': force * score_factor,
            'should_pause': level == PainLevel.HIGH,
            'should_stop': level == PainLevel.CRITICAL
        }
    
    def create_feedback(
        self,
        pain_level: int,
        pain_level_name: str,
        pain_score: float,
        source: str,
        confidence: float = 1.0,
        details: Optional[Dict] = None
    ) -> PainFeedback:
        """
        Create a complete PainFeedback object with modifiers.
        
        Args:
            pain_level: Pain level (0-4)
            pain_level_name: Human-readable level name
            pain_score: Pain score (0-100)
            source: Source ('piezo', 'face', or 'fused')
            confidence: Confidence in reading (0-1)
            details: Additional details dictionary
            
        Returns:
            Complete PainFeedback object
        """
        modifiers = self.get_modifiers(pain_level, pain_score, source)
        
        return PainFeedback(
            timestamp=time.time(),
            pain_level=pain_level,
            pain_level_name=pain_level_name,
            pain_score=pain_score,
            source=source,
            confidence=confidence,
            speed_modifier=modifiers['speed_modifier'],
            amplitude_modifier=modifiers['amplitude_modifier'],
            force_modifier=modifiers['force_modifier'],
            should_pause=modifiers['should_pause'],
            should_stop=modifiers['should_stop'],
            details=details
        )


class FeedbackPublisher:
    """
    Publish pain feedback for consumption by IRDS.
    
    Supports multiple output methods:
    - File: Write to JSON file
    - Socket: TCP/UDP communication
    - Callback: Direct function calls
    """
    
    def __init__(
        self,
        output_file: Optional[str] = None,
        socket_host: Optional[str] = None,
        socket_port: int = 5555,
        use_udp: bool = True
    ):
        """
        Initialize feedback publisher.
        
        Args:
            output_file: Path to output JSON file (updated on each publish)
            socket_host: Host for socket communication
            socket_port: Port for socket communication
            use_udp: Use UDP (True) or TCP (False) for socket
        """
        self.output_file = Path(output_file) if output_file else None
        self.socket_host = socket_host
        self.socket_port = socket_port
        self.use_udp = use_udp
        
        self._socket = None
        self._callbacks: List[Callable[[PainFeedback], None]] = []
        self._history: List[PainFeedback] = []
        self._max_history = 100
        self._lock = threading.Lock()
        
        # Initialize socket if host specified
        if socket_host:
            self._init_socket()
    
    def _init_socket(self):
        """Initialize socket connection."""
        try:
            if self.use_udp:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.connect((self.socket_host, self.socket_port))
            print(f"Socket initialized: {self.socket_host}:{self.socket_port} ({'UDP' if self.use_udp else 'TCP'})")
        except Exception as e:
            print(f"Socket initialization failed: {e}")
            self._socket = None
    
    def add_callback(self, callback: Callable[[PainFeedback], None]):
        """Add callback function for feedback events."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PainFeedback], None]):
        """Remove callback function."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def publish(self, feedback: PainFeedback):
        """
        Publish pain feedback to all outputs.
        
        Args:
            feedback: PainFeedback object to publish
        """
        with self._lock:
            # Store in history
            self._history.append(feedback)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        
        # Write to file
        if self.output_file:
            self._write_to_file(feedback)
        
        # Send via socket
        if self._socket:
            self._send_socket(feedback)
        
        # Call callbacks
        for callback in self._callbacks:
            try:
                callback(feedback)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def _write_to_file(self, feedback: PainFeedback):
        """Write feedback to JSON file."""
        try:
            # Ensure directory exists
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write current feedback
            with open(self.output_file, 'w') as f:
                f.write(feedback.to_json())
            
            # Also write history
            history_file = self.output_file.with_suffix('.history.json')
            with open(history_file, 'w') as f:
                history_data = [fb.to_dict() for fb in self._history[-20:]]
                json.dump(history_data, f, indent=2)
                
        except Exception as e:
            print(f"File write error: {e}")
    
    def _send_socket(self, feedback: PainFeedback):
        """Send feedback via socket."""
        try:
            data = feedback.to_json().encode('utf-8')
            
            if self.use_udp:
                self._socket.sendto(data, (self.socket_host, self.socket_port))
            else:
                self._socket.send(data)
                
        except Exception as e:
            print(f"Socket send error: {e}")
    
    def get_latest(self) -> Optional[PainFeedback]:
        """Get the most recent feedback."""
        with self._lock:
            return self._history[-1] if self._history else None
    
    def get_history(self, count: int = 10) -> List[PainFeedback]:
        """Get recent feedback history."""
        with self._lock:
            return self._history[-count:]
    
    def close(self):
        """Close socket connection."""
        if self._socket:
            self._socket.close()
            self._socket = None


class FeedbackSubscriber:
    """
    Subscribe to pain feedback from the feedback system.
    For use by IRDS or other consuming systems.
    """
    
    def __init__(
        self,
        input_file: Optional[str] = None,
        socket_host: str = '0.0.0.0',
        socket_port: int = 5555,
        use_udp: bool = True
    ):
        """
        Initialize feedback subscriber.
        
        Args:
            input_file: Path to input JSON file to poll
            socket_host: Host to listen on for socket
            socket_port: Port to listen on
            use_udp: Use UDP (True) or TCP (False)
        """
        self.input_file = Path(input_file) if input_file else None
        self.socket_host = socket_host
        self.socket_port = socket_port
        self.use_udp = use_udp
        
        self._socket = None
        self._running = False
        self._thread = None
        self._callback: Optional[Callable[[PainFeedback], None]] = None
        self._last_feedback: Optional[PainFeedback] = None
        self._last_file_mtime = 0
    
    def start(self, callback: Callable[[PainFeedback], None]):
        """
        Start listening for feedback.
        
        Args:
            callback: Function to call when feedback is received
        """
        self._callback = callback
        self._running = True
        
        if self.input_file:
            # File polling mode
            self._thread = threading.Thread(target=self._poll_file, daemon=True)
        else:
            # Socket listening mode
            self._init_socket()
            self._thread = threading.Thread(target=self._listen_socket, daemon=True)
        
        self._thread.start()
    
    def _init_socket(self):
        """Initialize listening socket."""
        if self.use_udp:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self._socket.bind((self.socket_host, self.socket_port))
        
        if not self.use_udp:
            self._socket.listen(1)
        
        self._socket.settimeout(1.0)
        print(f"Listening on {self.socket_host}:{self.socket_port}")
    
    def _poll_file(self):
        """Poll file for updates."""
        while self._running:
            try:
                if self.input_file.exists():
                    mtime = self.input_file.stat().st_mtime
                    if mtime > self._last_file_mtime:
                        self._last_file_mtime = mtime
                        with open(self.input_file, 'r') as f:
                            data = f.read()
                        feedback = PainFeedback.from_json(data)
                        self._last_feedback = feedback
                        if self._callback:
                            self._callback(feedback)
            except Exception as e:
                pass  # Ignore file read errors
            
            time.sleep(0.1)  # Poll every 100ms
    
    def _listen_socket(self):
        """Listen for socket messages."""
        while self._running:
            try:
                if self.use_udp:
                    data, addr = self._socket.recvfrom(4096)
                else:
                    conn, addr = self._socket.accept()
                    data = conn.recv(4096)
                    conn.close()
                
                feedback = PainFeedback.from_json(data.decode('utf-8'))
                self._last_feedback = feedback
                if self._callback:
                    self._callback(feedback)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"Socket error: {e}")
    
    def stop(self):
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._socket:
            self._socket.close()
    
    def get_latest(self) -> Optional[PainFeedback]:
        """Get the most recent feedback."""
        return self._last_feedback


def create_feedback_server(
    output_file: str = None,
    socket_port: int = 5555
) -> FeedbackPublisher:
    """
    Create a feedback server for publishing pain data.
    
    Args:
        output_file: Path to output JSON file
        socket_port: Port for UDP socket
        
    Returns:
        Configured FeedbackPublisher
    """
    return FeedbackPublisher(
        output_file=output_file,
        socket_host='localhost',
        socket_port=socket_port,
        use_udp=True
    )


def create_feedback_client(
    input_file: str = None,
    socket_port: int = 5555
) -> FeedbackSubscriber:
    """
    Create a feedback client for receiving pain data.
    For use by IRDS or other systems.
    
    Args:
        input_file: Path to input JSON file to poll
        socket_port: Port to listen on
        
    Returns:
        Configured FeedbackSubscriber
    """
    return FeedbackSubscriber(
        input_file=input_file,
        socket_port=socket_port,
        use_udp=True
    )


# Mapping from sensor module levels to PainLevel
PIEZO_LEVEL_MAP = {
    'NONE': PainLevel.NONE,
    'LIGHT': PainLevel.LIGHT,
    'MODERATE': PainLevel.MODERATE,
    'HIGH': PainLevel.HIGH,
    'CRITICAL': PainLevel.CRITICAL
}

FACE_LEVEL_MAP = {
    'NONE': PainLevel.NONE,
    'MILD': PainLevel.LIGHT,
    'MODERATE': PainLevel.MODERATE,
    'SEVERE': PainLevel.HIGH,
    'EXTREME': PainLevel.CRITICAL
}


def piezo_to_feedback(reading, modifier: GestureModifier = None) -> PainFeedback:
    """
    Convert piezo sensor reading to PainFeedback.
    
    Args:
        reading: PressureReading from piezo sensor
        modifier: GestureModifier instance (creates default if None)
        
    Returns:
        PainFeedback object
    """
    if modifier is None:
        modifier = GestureModifier()
    
    level = PIEZO_LEVEL_MAP.get(reading.level, PainLevel.NONE)
    
    return modifier.create_feedback(
        pain_level=level.value,
        pain_level_name=reading.level,
        pain_score=reading.percent,
        source='piezo',
        confidence=1.0,
        details={
            'raw': reading.raw,
            'filtered': reading.filtered,
            'pressure': reading.pressure,
            'timestamp': reading.timestamp
        }
    )


def face_to_feedback(reading, modifier: GestureModifier = None) -> PainFeedback:
    """
    Convert face pain reading to PainFeedback.
    
    Args:
        reading: PainReading from face detector
        modifier: GestureModifier instance (creates default if None)
        
    Returns:
        PainFeedback object
    """
    if modifier is None:
        modifier = GestureModifier()
    
    level = FACE_LEVEL_MAP.get(reading.level, PainLevel.NONE)
    
    return modifier.create_feedback(
        pain_level=level.value,
        pain_level_name=reading.level,
        pain_score=reading.pain_score,
        source='face',
        confidence=0.9 if reading.face_detected else 0.0,
        details={
            'brow_furrow': reading.brow_furrow,
            'eye_squeeze': reading.eye_squeeze,
            'nose_wrinkle': reading.nose_wrinkle,
            'lip_raise': reading.lip_raise,
            'face_detected': reading.face_detected,
            'frame_number': reading.frame_number
        }
    )


def fuse_feedback(
    piezo_feedback: Optional[PainFeedback],
    face_feedback: Optional[PainFeedback],
    piezo_weight: float = 0.6,
    face_weight: float = 0.4
) -> PainFeedback:
    """
    Fuse feedback from multiple sources.
    
    Uses weighted combination of piezo and face feedback to create
    a unified pain assessment.
    
    Args:
        piezo_feedback: Feedback from piezo sensor
        face_feedback: Feedback from face detector
        piezo_weight: Weight for piezo feedback (0-1)
        face_weight: Weight for face feedback (0-1)
        
    Returns:
        Fused PainFeedback object
    """
    modifier = GestureModifier()
    
    # Handle missing sources
    if piezo_feedback is None and face_feedback is None:
        return modifier.create_feedback(
            pain_level=0,
            pain_level_name='NONE',
            pain_score=0.0,
            source='fused',
            confidence=0.0
        )
    
    if piezo_feedback is None:
        face_feedback.source = 'fused'
        return face_feedback
    
    if face_feedback is None:
        piezo_feedback.source = 'fused'
        return piezo_feedback
    
    # Weighted fusion
    total_weight = piezo_weight + face_weight
    piezo_w = piezo_weight / total_weight
    face_w = face_weight / total_weight
    
    # Fuse pain score
    fused_score = (
        piezo_feedback.pain_score * piezo_w * piezo_feedback.confidence +
        face_feedback.pain_score * face_w * face_feedback.confidence
    )
    
    # Determine fused level (take max for safety)
    fused_level = max(piezo_feedback.pain_level, face_feedback.pain_level)
    
    # Fuse modifiers (take minimum for safety)
    fused_speed = min(piezo_feedback.speed_modifier, face_feedback.speed_modifier)
    fused_amplitude = min(piezo_feedback.amplitude_modifier, face_feedback.amplitude_modifier)
    fused_force = min(piezo_feedback.force_modifier, face_feedback.force_modifier)
    
    # Fuse confidence
    fused_confidence = (
        piezo_feedback.confidence * piezo_w +
        face_feedback.confidence * face_w
    )
    
    # Level name from max level
    level_names = ['NONE', 'LIGHT', 'MODERATE', 'HIGH', 'CRITICAL']
    fused_level_name = level_names[min(fused_level, 4)]
    
    return PainFeedback(
        timestamp=time.time(),
        pain_level=fused_level,
        pain_level_name=fused_level_name,
        pain_score=fused_score,
        source='fused',
        confidence=fused_confidence,
        speed_modifier=fused_speed,
        amplitude_modifier=fused_amplitude,
        force_modifier=fused_force,
        should_pause=piezo_feedback.should_pause or face_feedback.should_pause,
        should_stop=piezo_feedback.should_stop or face_feedback.should_stop,
        details={
            'piezo': piezo_feedback.details,
            'face': face_feedback.details,
            'weights': {'piezo': piezo_w, 'face': face_w}
        }
    )



