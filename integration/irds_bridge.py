#!/usr/bin/env python3
"""
IRDS Bridge - Connects Pain Detection to Gesture Control

This bridge runs alongside the pain detection dashboards and publishes
feedback data in a format consumable by the IRDS gesture recognition system.

Usage:
    # Start with file output (IRDS reads from file)
    python integration/irds_bridge.py --output-file data/irds_feedback.json
    
    # Start with socket output (IRDS listens on socket)
    python integration/irds_bridge.py --socket-port 5555
    
    # Start with both piezo and face detection sources
    python integration/irds_bridge.py --piezo --face --fused
"""

import sys
import time
import argparse
import threading
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.irds_interface import (
    FeedbackPublisher,
    GestureModifier,
    piezo_to_feedback,
    face_to_feedback,
    fuse_feedback,
    PainFeedback
)


class IRDSBridge:
    """
    Bridge between pain detection modules and IRDS gesture system.
    
    Subscribes to pain detection data from piezo sensor and face detector,
    converts to IRDS-compatible format, and publishes for consumption.
    """
    
    def __init__(
        self,
        output_file: str = None,
        socket_host: str = None,
        socket_port: int = 5555,
        enable_piezo: bool = True,
        enable_face: bool = True,
        enable_fused: bool = True,
        piezo_weight: float = 0.6,
        face_weight: float = 0.4
    ):
        """
        Initialize the bridge.
        
        Args:
            output_file: Path to output JSON file
            socket_host: Host for socket publishing
            socket_port: Port for socket publishing
            enable_piezo: Enable piezo sensor input
            enable_face: Enable face detection input
            enable_fused: Enable fused output mode
            piezo_weight: Weight for piezo in fusion
            face_weight: Weight for face in fusion
        """
        self.enable_piezo = enable_piezo
        self.enable_face = enable_face
        self.enable_fused = enable_fused
        self.piezo_weight = piezo_weight
        self.face_weight = face_weight
        
        # Create publisher
        self.publisher = FeedbackPublisher(
            output_file=output_file,
            socket_host=socket_host,
            socket_port=socket_port,
            use_udp=True
        )
        
        # Create modifier for calculating gesture adjustments
        self.modifier = GestureModifier()
        
        # Latest readings from each source
        self._piezo_feedback = None
        self._face_feedback = None
        self._lock = threading.Lock()
        
        # Running flag
        self._running = False
    
    def update_piezo(self, reading):
        """
        Update with new piezo sensor reading.
        
        Args:
            reading: PressureReading from piezo sensor
        """
        with self._lock:
            self._piezo_feedback = piezo_to_feedback(reading, self.modifier)
        
        if not self.enable_fused:
            self.publisher.publish(self._piezo_feedback)
    
    def update_face(self, reading):
        """
        Update with new face detection reading.
        
        Args:
            reading: PainReading from face detector
        """
        with self._lock:
            self._face_feedback = face_to_feedback(reading, self.modifier)
        
        if not self.enable_fused:
            self.publisher.publish(self._face_feedback)
    
    def publish_fused(self):
        """Publish fused feedback from all sources."""
        with self._lock:
            fused = fuse_feedback(
                self._piezo_feedback,
                self._face_feedback,
                self.piezo_weight,
                self.face_weight
            )
        
        self.publisher.publish(fused)
        return fused
    
    def start_fusion_loop(self, interval: float = 0.1):
        """
        Start a loop that publishes fused feedback at regular intervals.
        
        Args:
            interval: Time between updates in seconds
        """
        self._running = True
        
        def fusion_loop():
            while self._running:
                if self.enable_fused:
                    self.publish_fused()
                time.sleep(interval)
        
        self._fusion_thread = threading.Thread(target=fusion_loop, daemon=True)
        self._fusion_thread.start()
    
    def stop(self):
        """Stop the bridge."""
        self._running = False
        self.publisher.close()
    
    def get_latest(self) -> PainFeedback:
        """Get the latest feedback."""
        return self.publisher.get_latest()


def create_mock_piezo_reading(pressure: float):
    """Create a mock piezo reading for testing."""
    from dataclasses import dataclass
    
    @dataclass
    class MockReading:
        raw: int
        filtered: int
        pressure: int
        percent: float
        level: str
        timestamp: int
    
    percent = (pressure / 511.0) * 100.0
    
    if percent < 5.0:
        level = "NONE"
    elif percent < 20.0:
        level = "LIGHT"
    elif percent < 50.0:
        level = "MODERATE"
    elif percent < 80.0:
        level = "HIGH"
    else:
        level = "CRITICAL"
    
    return MockReading(
        raw=int(pressure),
        filtered=int(pressure),
        pressure=int(pressure),
        percent=percent,
        level=level,
        timestamp=int(time.time() * 1000)
    )


def create_mock_face_reading(pain_score: float):
    """Create a mock face reading for testing."""
    from dataclasses import dataclass
    
    @dataclass
    class MockReading:
        pain_score: float
        level: str
        brow_furrow: float
        eye_squeeze: float
        nose_wrinkle: float
        lip_raise: float
        face_detected: bool
        frame_number: int
    
    if pain_score < 20:
        level = "NONE"
    elif pain_score < 40:
        level = "MILD"
    elif pain_score < 60:
        level = "MODERATE"
    elif pain_score < 80:
        level = "SEVERE"
    else:
        level = "EXTREME"
    
    return MockReading(
        pain_score=pain_score,
        level=level,
        brow_furrow=pain_score / 100.0,
        eye_squeeze=pain_score / 100.0,
        nose_wrinkle=pain_score / 100.0,
        lip_raise=pain_score / 100.0,
        face_detected=True,
        frame_number=1
    )


def demo_bridge():
    """Demo the bridge with simulated data."""
    print("=" * 60)
    print("IRDS Bridge Demo")
    print("=" * 60)
    
    # Create bridge with file output
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "irds_feedback.json"
    
    bridge = IRDSBridge(
        output_file=str(output_file),
        enable_fused=True
    )
    
    print(f"\nOutput file: {output_file}")
    print("\nSimulating pain detection data...\n")
    
    # Simulate different pain scenarios
    scenarios = [
        (0, 0, "No pain"),
        (50, 30, "Light piezo pressure, mild face pain"),
        (150, 50, "Moderate piezo, moderate face"),
        (300, 70, "High piezo, severe face"),
        (450, 90, "Critical piezo, extreme face"),
        (100, 20, "Returning to light pain"),
        (0, 0, "Pain subsided"),
    ]
    
    for piezo_val, face_val, description in scenarios:
        print(f"\n{'='*50}")
        print(f"Scenario: {description}")
        print(f"  Piezo pressure: {piezo_val}")
        print(f"  Face pain score: {face_val}")
        
        # Update with mock readings
        piezo_reading = create_mock_piezo_reading(piezo_val)
        face_reading = create_mock_face_reading(face_val)
        
        bridge.update_piezo(piezo_reading)
        bridge.update_face(face_reading)
        
        # Publish fused feedback
        feedback = bridge.publish_fused()
        
        print(f"\nFused Feedback:")
        print(f"  Pain Level: {feedback.pain_level} ({feedback.pain_level_name})")
        print(f"  Pain Score: {feedback.pain_score:.1f}%")
        print(f"  Confidence: {feedback.confidence:.2f}")
        print(f"\nGesture Modifiers for IRDS:")
        print(f"  Speed:     {feedback.speed_modifier:.2f} ({feedback.speed_modifier*100:.0f}%)")
        print(f"  Amplitude: {feedback.amplitude_modifier:.2f} ({feedback.amplitude_modifier*100:.0f}%)")
        print(f"  Force:     {feedback.force_modifier:.2f} ({feedback.force_modifier*100:.0f}%)")
        print(f"  Pause:     {feedback.should_pause}")
        print(f"  Stop:      {feedback.should_stop}")
        
        time.sleep(0.5)
    
    bridge.stop()
    
    print(f"\n{'='*60}")
    print(f"Demo complete!")
    print(f"Feedback written to: {output_file}")
    print(f"\nIRDS can consume this file to adjust gesture parameters.")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='IRDS Bridge - Connect Pain Detection to Gesture Control')
    parser.add_argument('--output-file', type=str, default='data/irds_feedback.json',
                        help='Path to output JSON file')
    parser.add_argument('--socket-host', type=str, default=None,
                        help='Host for socket publishing')
    parser.add_argument('--socket-port', type=int, default=5555,
                        help='Port for socket publishing')
    parser.add_argument('--piezo', action='store_true', default=True,
                        help='Enable piezo sensor input')
    parser.add_argument('--face', action='store_true', default=True,
                        help='Enable face detection input')
    parser.add_argument('--fused', action='store_true', default=True,
                        help='Enable fused output mode')
    parser.add_argument('--piezo-weight', type=float, default=0.6,
                        help='Weight for piezo in fusion (0-1)')
    parser.add_argument('--face-weight', type=float, default=0.4,
                        help='Weight for face in fusion (0-1)')
    parser.add_argument('--demo', action='store_true',
                        help='Run demo with simulated data')
    
    args = parser.parse_args()
    
    if args.demo:
        demo_bridge()
        return
    
    # Create and run bridge
    bridge = IRDSBridge(
        output_file=args.output_file,
        socket_host=args.socket_host,
        socket_port=args.socket_port,
        enable_piezo=args.piezo,
        enable_face=args.face,
        enable_fused=args.fused,
        piezo_weight=args.piezo_weight,
        face_weight=args.face_weight
    )
    
    print("IRDS Bridge started")
    print(f"  Output file: {args.output_file}")
    if args.socket_host:
        print(f"  Socket: {args.socket_host}:{args.socket_port}")
    print("\nWaiting for pain detection data...")
    print("Press Ctrl+C to stop\n")
    
    try:
        bridge.start_fusion_loop(interval=0.1)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bridge...")
        bridge.stop()


if __name__ == '__main__':
    main()



