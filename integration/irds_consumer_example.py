#!/usr/bin/env python3
"""
IRDS Consumer Example - Shows how IRDS can consume pain feedback

This example demonstrates how the IRDS gesture model can read pain feedback
from the feedback system and adjust gesture parameters accordingly.

NOTE: This file is for reference only. It does NOT modify the IRDS project.
      Copy and adapt this code for use in the IRDS project.

Usage in IRDS:
    1. Copy the FeedbackConsumer class to IRDS project
    2. Initialize it with the feedback file path or socket port
    3. Call get_modifiers() before executing each gesture
    4. Apply modifiers to gesture speed, amplitude, and force
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Callable
import threading


@dataclass
class GestureModifiers:
    """Modifiers to apply to gesture execution."""
    speed_modifier: float = 1.0
    amplitude_modifier: float = 1.0
    force_modifier: float = 1.0
    should_pause: bool = False
    should_stop: bool = False
    pain_level: int = 0
    pain_score: float = 0.0
    timestamp: float = 0.0
    confidence: float = 0.0


class FeedbackConsumer:
    """
    Consume pain feedback for IRDS gesture adjustment.
    
    This class reads feedback data published by the feedback system
    and provides modifiers for gesture execution.
    
    Example usage:
        consumer = FeedbackConsumer('/path/to/feedback/data/irds_feedback.json')
        consumer.start()
        
        # In gesture execution loop:
        modifiers = consumer.get_modifiers()
        if modifiers.should_stop:
            emergency_stop()
        elif modifiers.should_pause:
            pause_gesture()
        else:
            execute_gesture(
                speed=base_speed * modifiers.speed_modifier,
                amplitude=base_amplitude * modifiers.amplitude_modifier,
                force=base_force * modifiers.force_modifier
            )
    """
    
    def __init__(
        self,
        feedback_file: str = None,
        socket_port: int = None,
        default_on_missing: bool = True,
        stale_threshold: float = 2.0
    ):
        """
        Initialize the feedback consumer.
        
        Args:
            feedback_file: Path to feedback JSON file to poll
            socket_port: Port to listen on for UDP feedback
            default_on_missing: If True, return safe defaults when no data
            stale_threshold: Seconds after which data is considered stale
        """
        self.feedback_file = Path(feedback_file) if feedback_file else None
        self.socket_port = socket_port
        self.default_on_missing = default_on_missing
        self.stale_threshold = stale_threshold
        
        self._modifiers = GestureModifiers()
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._last_update = 0
        self._last_file_mtime = 0
        
        # Callback for pain events
        self._on_high_pain: Optional[Callable] = None
        self._on_critical_pain: Optional[Callable] = None
    
    def set_high_pain_callback(self, callback: Callable):
        """Set callback for high pain detection (level 3)."""
        self._on_high_pain = callback
    
    def set_critical_pain_callback(self, callback: Callable):
        """Set callback for critical pain detection (level 4)."""
        self._on_critical_pain = callback
    
    def start(self):
        """Start polling for feedback data."""
        self._running = True
        
        if self.feedback_file:
            self._thread = threading.Thread(target=self._poll_file, daemon=True)
        elif self.socket_port:
            self._thread = threading.Thread(target=self._listen_socket, daemon=True)
        
        if self._thread:
            self._thread.start()
            print(f"Feedback consumer started")
    
    def stop(self):
        """Stop polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _poll_file(self):
        """Poll JSON file for updates."""
        while self._running:
            try:
                if self.feedback_file and self.feedback_file.exists():
                    mtime = self.feedback_file.stat().st_mtime
                    if mtime > self._last_file_mtime:
                        self._last_file_mtime = mtime
                        self._read_feedback_file()
            except Exception as e:
                pass
            time.sleep(0.05)  # 50ms polling interval
    
    def _read_feedback_file(self):
        """Read and parse feedback file."""
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            self._update_modifiers(data)
        except Exception as e:
            pass
    
    def _listen_socket(self):
        """Listen for UDP socket messages."""
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', self.socket_port))
        sock.settimeout(1.0)
        
        print(f"Listening for feedback on port {self.socket_port}")
        
        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
                feedback = json.loads(data.decode('utf-8'))
                self._update_modifiers(feedback)
            except socket.timeout:
                continue
            except Exception as e:
                pass
        
        sock.close()
    
    def _update_modifiers(self, data: dict):
        """Update modifiers from feedback data."""
        with self._lock:
            old_level = self._modifiers.pain_level
            
            self._modifiers = GestureModifiers(
                speed_modifier=data.get('speed_modifier', 1.0),
                amplitude_modifier=data.get('amplitude_modifier', 1.0),
                force_modifier=data.get('force_modifier', 1.0),
                should_pause=data.get('should_pause', False),
                should_stop=data.get('should_stop', False),
                pain_level=data.get('pain_level', 0),
                pain_score=data.get('pain_score', 0.0),
                timestamp=data.get('timestamp', time.time()),
                confidence=data.get('confidence', 0.0)
            )
            self._last_update = time.time()
            
            # Trigger callbacks for pain level changes
            new_level = self._modifiers.pain_level
            if new_level >= 4 and old_level < 4 and self._on_critical_pain:
                self._on_critical_pain()
            elif new_level >= 3 and old_level < 3 and self._on_high_pain:
                self._on_high_pain()
    
    def get_modifiers(self) -> GestureModifiers:
        """
        Get current gesture modifiers.
        
        Returns:
            GestureModifiers with current values
            If data is stale or missing and default_on_missing is True,
            returns safe conservative defaults.
        """
        with self._lock:
            # Check if data is stale
            if self._last_update > 0:
                age = time.time() - self._last_update
                if age > self.stale_threshold:
                    if self.default_on_missing:
                        # Return conservative defaults for stale data
                        return GestureModifiers(
                            speed_modifier=0.5,
                            amplitude_modifier=0.5,
                            force_modifier=0.5,
                            should_pause=True,
                            confidence=0.0
                        )
            
            # Return current modifiers or defaults
            if self._last_update == 0 and self.default_on_missing:
                return GestureModifiers()
            
            return GestureModifiers(
                speed_modifier=self._modifiers.speed_modifier,
                amplitude_modifier=self._modifiers.amplitude_modifier,
                force_modifier=self._modifiers.force_modifier,
                should_pause=self._modifiers.should_pause,
                should_stop=self._modifiers.should_stop,
                pain_level=self._modifiers.pain_level,
                pain_score=self._modifiers.pain_score,
                timestamp=self._modifiers.timestamp,
                confidence=self._modifiers.confidence
            )
    
    def is_safe_to_proceed(self) -> bool:
        """Check if it's safe to continue gesture execution."""
        modifiers = self.get_modifiers()
        return not modifiers.should_stop and not modifiers.should_pause
    
    def get_adjusted_params(
        self,
        base_speed: float,
        base_amplitude: float,
        base_force: float
    ) -> Dict[str, float]:
        """
        Get adjusted gesture parameters.
        
        Args:
            base_speed: Base gesture speed
            base_amplitude: Base gesture amplitude
            base_force: Base gesture force
            
        Returns:
            Dictionary with adjusted speed, amplitude, force
        """
        modifiers = self.get_modifiers()
        
        return {
            'speed': base_speed * modifiers.speed_modifier,
            'amplitude': base_amplitude * modifiers.amplitude_modifier,
            'force': base_force * modifiers.force_modifier,
            'is_safe': not modifiers.should_stop and not modifiers.should_pause
        }


def demo_consumer():
    """Demo the feedback consumer."""
    print("=" * 60)
    print("IRDS Feedback Consumer Demo")
    print("=" * 60)
    
    # Path to feedback file
    feedback_file = Path(__file__).parent.parent / "data" / "irds_feedback.json"
    
    if not feedback_file.exists():
        print(f"\nFeedback file not found: {feedback_file}")
        print("Run the bridge first: python integration/irds_bridge.py --demo")
        return
    
    # Create consumer
    consumer = FeedbackConsumer(
        feedback_file=str(feedback_file),
        stale_threshold=5.0
    )
    
    # Set callbacks
    def on_high_pain():
        print("\n⚠️  HIGH PAIN DETECTED - Pausing gesture!")
    
    def on_critical():
        print("\n🛑 CRITICAL PAIN - EMERGENCY STOP!")
    
    consumer.set_high_pain_callback(on_high_pain)
    consumer.set_critical_pain_callback(on_critical)
    
    # Start consumer
    consumer.start()
    
    print(f"\nReading feedback from: {feedback_file}")
    print("\nSimulating gesture execution with pain feedback...\n")
    
    # Simulate gesture execution
    base_speed = 1.0
    base_amplitude = 1.0
    base_force = 1.0
    
    for i in range(10):
        modifiers = consumer.get_modifiers()
        
        print(f"\n--- Gesture Step {i+1} ---")
        print(f"Pain Level: {modifiers.pain_level} (Score: {modifiers.pain_score:.1f}%)")
        
        if modifiers.should_stop:
            print("❌ STOP: Emergency stop triggered!")
            break
        elif modifiers.should_pause:
            print("⏸️  PAUSE: Gesture paused due to high pain")
        else:
            adjusted = consumer.get_adjusted_params(
                base_speed, base_amplitude, base_force
            )
            print(f"✓ Executing with:")
            print(f"  Speed: {adjusted['speed']:.2f}")
            print(f"  Amplitude: {adjusted['amplitude']:.2f}")
            print(f"  Force: {adjusted['force']:.2f}")
        
        time.sleep(0.5)
    
    consumer.stop()
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


# Code snippet for IRDS integration
IRDS_INTEGRATION_SNIPPET = '''
# =====================================================
# IRDS Integration Code Snippet
# =====================================================
# Copy this code to your IRDS project to consume pain feedback

from pathlib import Path
import json
import time
import threading
from dataclasses import dataclass
from typing import Dict

@dataclass
class GestureModifiers:
    speed_modifier: float = 1.0
    amplitude_modifier: float = 1.0
    force_modifier: float = 1.0
    should_pause: bool = False
    should_stop: bool = False
    pain_level: int = 0
    pain_score: float = 0.0

class PainFeedbackReader:
    """Simple reader for pain feedback file."""
    
    def __init__(self, feedback_file: str):
        self.feedback_file = Path(feedback_file)
        self._modifiers = GestureModifiers()
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._last_mtime = 0
    
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
    
    def stop(self):
        self._running = False
    
    def _poll(self):
        while self._running:
            try:
                if self.feedback_file.exists():
                    mtime = self.feedback_file.stat().st_mtime
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        with open(self.feedback_file) as f:
                            data = json.load(f)
                        with self._lock:
                            self._modifiers = GestureModifiers(
                                speed_modifier=data.get('speed_modifier', 1.0),
                                amplitude_modifier=data.get('amplitude_modifier', 1.0),
                                force_modifier=data.get('force_modifier', 1.0),
                                should_pause=data.get('should_pause', False),
                                should_stop=data.get('should_stop', False),
                                pain_level=data.get('pain_level', 0),
                                pain_score=data.get('pain_score', 0.0)
                            )
            except:
                pass
            time.sleep(0.05)
    
    def get_modifiers(self) -> GestureModifiers:
        with self._lock:
            return self._modifiers

# Usage in IRDS gesture execution:
# 
# feedback = PainFeedbackReader('/path/to/feedback/data/irds_feedback.json')
# feedback.start()
#
# # In your gesture loop:
# mods = feedback.get_modifiers()
# if mods.should_stop:
#     emergency_stop()
# elif mods.should_pause:
#     pause()
# else:
#     execute_gesture(
#         speed=base_speed * mods.speed_modifier,
#         amplitude=base_amplitude * mods.amplitude_modifier
#     )
'''


def print_integration_guide():
    """Print the integration guide for IRDS."""
    print("=" * 60)
    print("IRDS Integration Guide")
    print("=" * 60)
    print("""
The feedback system outputs pain data in a JSON format that IRDS can
consume to adjust gesture parameters in real-time.

ARCHITECTURE:
                                    
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Piezo Sensor   │───▶│                 │    │                 │
│    Arduino      │    │   Feedback      │───▶│     IRDS        │
└─────────────────┘    │   Bridge        │    │   Gesture       │
                       │                 │    │   Model         │
┌─────────────────┐    │   (irds_bridge) │    │                 │
│  Face Detection │───▶│                 │    └─────────────────┘
│    Camera       │    └─────────────────┘            │
└─────────────────┘             │                     │
                                │                     ▼
                                ▼              ┌─────────────────┐
                       ┌─────────────────┐     │  Robotic Arm    │
                       │  JSON File or   │     │  Gesture        │
                       │  UDP Socket     │     │  Execution      │
                       └─────────────────┘     └─────────────────┘

DATA FLOW:
1. Pain sensors (piezo/face) detect pain levels
2. Feedback bridge converts to gesture modifiers
3. IRDS reads modifiers from file or socket
4. Gesture execution adjusts speed/amplitude/force

FEEDBACK JSON FORMAT:
{
    "timestamp": 1734355200.123,
    "pain_level": 2,              // 0=NONE, 1=LIGHT, 2=MODERATE, 3=HIGH, 4=CRITICAL
    "pain_level_name": "MODERATE",
    "pain_score": 45.5,           // 0-100 percentage
    "source": "fused",            // 'piezo', 'face', or 'fused'
    "confidence": 0.85,           // 0-1 confidence
    "speed_modifier": 0.5,        // Multiply gesture speed by this
    "amplitude_modifier": 0.7,    // Multiply amplitude by this
    "force_modifier": 0.6,        // Multiply force by this
    "should_pause": false,        // True = pause gesture execution
    "should_stop": false          // True = emergency stop
}

QUICK START:
1. Start feedback bridge:
   cd /home/nishant/project/feedback
   python integration/irds_bridge.py --demo

2. In IRDS, read the feedback file:
   feedback_file = '/home/nishant/project/feedback/data/irds_feedback.json'

3. Apply modifiers to gesture execution (see code snippet below)
""")
    print(IRDS_INTEGRATION_SNIPPET)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--guide':
        print_integration_guide()
    else:
        demo_consumer()

