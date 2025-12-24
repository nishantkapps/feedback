#!/usr/bin/env python3
"""
Nachi Cobot Interface Module

Translates IRDS pain feedback into Nachi robot-compatible commands.
Supports communication via:
- EtherNet/IP (industrial protocol)
- TCP/IP Socket (simple integration)
- File-based (for testing/simulation)

Nachi FD11 Controller Compatible Parameters:
- Speed Override: 0-100% (maps to our speed_modifier)
- External Signals: Start/Stop/Pause (maps to our control flags)
- Motion Parameters: Can be adjusted based on amplitude/force modifiers

Reference: Nachi FD Controller documentation
"""

import json
import time
import socket
import struct
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Callable, Dict, Any
from pathlib import Path
from enum import Enum


class NachiProtocol(Enum):
    """Supported communication protocols for Nachi robots."""
    TCP_SOCKET = "tcp"          # Simple TCP/IP socket
    ETHERNET_IP = "ethernet_ip"  # EtherNet/IP industrial protocol
    FILE = "file"               # File-based for testing


@dataclass
class NachiCommand:
    """
    Command structure for Nachi FD11 controller.
    
    These parameters map to Nachi's internal control registers:
    - speed_override: OVRD register (0-100%)
    - external_pause: External pause signal
    - external_stop: Emergency stop signal
    - motion_scale: Motion amplitude scaling
    - force_limit: Force limitation percentage
    """
    # Core control parameters
    speed_override: int         # 0-100 (percentage)
    motion_scale: int           # 0-100 (percentage)
    force_limit: int            # 0-100 (percentage)
    
    # Control signals
    external_pause: bool        # Pause robot motion
    external_stop: bool         # Emergency stop
    enable_motion: bool         # Allow motion
    
    # Metadata
    timestamp: float
    source: str                 # 'pain_feedback'
    confidence: float           # 0-1 confidence in the reading
    pain_level: int             # 0-4 for reference
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    def to_bytes(self) -> bytes:
        """
        Convert to binary format for industrial protocols.
        
        Format (16 bytes):
        - Byte 0: speed_override (uint8)
        - Byte 1: motion_scale (uint8)
        - Byte 2: force_limit (uint8)
        - Byte 3: flags (bit0=pause, bit1=stop, bit2=enable)
        - Byte 4-5: pain_level (uint16)
        - Byte 6-7: confidence * 1000 (uint16)
        - Byte 8-15: timestamp (double)
        """
        flags = (
            (1 if self.external_pause else 0) |
            (2 if self.external_stop else 0) |
            (4 if self.enable_motion else 0)
        )
        
        return struct.pack(
            '<BBBBHHd',
            self.speed_override,
            self.motion_scale,
            self.force_limit,
            flags,
            self.pain_level,
            int(self.confidence * 1000),
            self.timestamp
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'NachiCommand':
        """Parse from binary format."""
        speed, motion, force, flags, pain, conf, ts = struct.unpack('<BBBBHHd', data)
        
        return cls(
            speed_override=speed,
            motion_scale=motion,
            force_limit=force,
            external_pause=bool(flags & 1),
            external_stop=bool(flags & 2),
            enable_motion=bool(flags & 4),
            timestamp=ts,
            source='pain_feedback',
            confidence=conf / 1000.0,
            pain_level=pain
        )


class IRDSToNachiTranslator:
    """
    Translates IRDS pain feedback to Nachi robot commands.
    
    Mapping:
    - speed_modifier (0.0-1.0) → speed_override (0-100%)
    - amplitude_modifier (0.0-1.0) → motion_scale (0-100%)
    - force_modifier (0.0-1.0) → force_limit (0-100%)
    - should_pause → external_pause
    - should_stop → external_stop
    """
    
    def __init__(
        self,
        min_speed: int = 5,      # Minimum speed override (%)
        min_motion: int = 10,    # Minimum motion scale (%)
        min_force: int = 10      # Minimum force limit (%)
    ):
        """
        Initialize translator with safety limits.
        
        Args:
            min_speed: Minimum speed percentage (prevents 0% lockup)
            min_motion: Minimum motion scale
            min_force: Minimum force limit
        """
        self.min_speed = min_speed
        self.min_motion = min_motion
        self.min_force = min_force
    
    def translate(self, irds_feedback: dict) -> NachiCommand:
        """
        Translate IRDS feedback to Nachi command.
        
        Args:
            irds_feedback: Dictionary from irds_feedback.json
            
        Returns:
            NachiCommand ready for transmission
        """
        # Extract modifiers (default to 1.0 if missing)
        speed_mod = irds_feedback.get('speed_modifier', 1.0)
        amp_mod = irds_feedback.get('amplitude_modifier', 1.0)
        force_mod = irds_feedback.get('force_modifier', 1.0)
        
        # Convert to percentages with safety limits
        speed_override = max(self.min_speed, int(speed_mod * 100))
        motion_scale = max(self.min_motion, int(amp_mod * 100))
        force_limit = max(self.min_force, int(force_mod * 100))
        
        # If emergency stop, set everything to minimum
        if irds_feedback.get('should_stop', False):
            speed_override = 0
            motion_scale = 0
        
        return NachiCommand(
            speed_override=speed_override,
            motion_scale=motion_scale,
            force_limit=force_limit,
            external_pause=irds_feedback.get('should_pause', False),
            external_stop=irds_feedback.get('should_stop', False),
            enable_motion=not irds_feedback.get('should_stop', False),
            timestamp=irds_feedback.get('timestamp', time.time()),
            source='pain_feedback',
            confidence=irds_feedback.get('confidence', 0.0),
            pain_level=irds_feedback.get('pain_level', 0)
        )


class NachiInterface:
    """
    Interface for communicating with Nachi FD11 controller.
    
    Supports multiple protocols:
    - TCP Socket: Simple integration for testing
    - File: Write commands to file for simulation
    - EtherNet/IP: Industrial protocol (requires additional libraries)
    """
    
    def __init__(
        self,
        protocol: NachiProtocol = NachiProtocol.TCP_SOCKET,
        host: str = '192.168.1.100',
        port: int = 5000,
        output_file: str = None
    ):
        """
        Initialize Nachi interface.
        
        Args:
            protocol: Communication protocol to use
            host: Nachi controller IP address
            port: Port number for socket communication
            output_file: File path for file-based output
        """
        self.protocol = protocol
        self.host = host
        self.port = port
        self.output_file = Path(output_file) if output_file else None
        
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._translator = IRDSToNachiTranslator()
        self._lock = threading.Lock()
        self._last_command: Optional[NachiCommand] = None
    
    def connect(self) -> bool:
        """
        Connect to Nachi controller.
        
        Returns:
            True if connection successful
        """
        if self.protocol == NachiProtocol.FILE:
            # File mode - always "connected"
            if self.output_file:
                self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self._connected = True
            return True
        
        elif self.protocol == NachiProtocol.TCP_SOCKET:
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(5.0)
                self._socket.connect((self.host, self.port))
                self._connected = True
                print(f"Connected to Nachi controller at {self.host}:{self.port}")
                return True
            except Exception as e:
                print(f"Failed to connect to Nachi controller: {e}")
                self._connected = False
                return False
        
        elif self.protocol == NachiProtocol.ETHERNET_IP:
            # EtherNet/IP requires pycomm3 or similar library
            print("EtherNet/IP protocol requires additional setup")
            print("Install: pip install pycomm3")
            return False
        
        return False
    
    def disconnect(self):
        """Disconnect from Nachi controller."""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
        self._connected = False
    
    def send_command(self, command: NachiCommand) -> bool:
        """
        Send command to Nachi controller.
        
        Args:
            command: NachiCommand to send
            
        Returns:
            True if sent successfully
        """
        if not self._connected:
            print("Not connected to Nachi controller")
            return False
        
        with self._lock:
            self._last_command = command
            
            if self.protocol == NachiProtocol.FILE:
                return self._send_file(command)
            elif self.protocol == NachiProtocol.TCP_SOCKET:
                return self._send_socket(command)
        
        return False
    
    def _send_file(self, command: NachiCommand) -> bool:
        """Write command to file."""
        try:
            with open(self.output_file, 'w') as f:
                f.write(command.to_json())
            return True
        except Exception as e:
            print(f"File write error: {e}")
            return False
    
    def _send_socket(self, command: NachiCommand) -> bool:
        """Send command via TCP socket."""
        try:
            # Send binary format
            data = command.to_bytes()
            self._socket.send(data)
            return True
        except Exception as e:
            print(f"Socket send error: {e}")
            return False
    
    def send_irds_feedback(self, irds_feedback: dict) -> bool:
        """
        Convenience method to send IRDS feedback directly.
        
        Args:
            irds_feedback: Dictionary from irds_feedback.json
            
        Returns:
            True if sent successfully
        """
        command = self._translator.translate(irds_feedback)
        return self.send_command(command)
    
    def get_last_command(self) -> Optional[NachiCommand]:
        """Get the last command sent."""
        return self._last_command


class NachiFeedbackBridge:
    """
    Bridge that monitors IRDS feedback file and sends to Nachi controller.
    
    Usage:
        bridge = NachiFeedbackBridge(
            irds_file='data/irds_feedback.json',
            nachi_host='192.168.1.100'
        )
        bridge.start()
    """
    
    def __init__(
        self,
        irds_file: str = 'data/irds_feedback.json',
        nachi_host: str = '192.168.1.100',
        nachi_port: int = 5000,
        protocol: NachiProtocol = NachiProtocol.FILE,
        output_file: str = 'data/nachi_command.json',
        poll_interval: float = 0.1
    ):
        """
        Initialize the bridge.
        
        Args:
            irds_file: Path to IRDS feedback JSON file
            nachi_host: Nachi controller IP
            nachi_port: Nachi controller port
            protocol: Communication protocol
            output_file: Output file for file-based mode
            poll_interval: How often to check for updates (seconds)
        """
        self.irds_file = Path(irds_file)
        self.poll_interval = poll_interval
        
        self.nachi = NachiInterface(
            protocol=protocol,
            host=nachi_host,
            port=nachi_port,
            output_file=output_file
        )
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_mtime = 0
        self._callback: Optional[Callable[[NachiCommand], None]] = None
    
    def set_callback(self, callback: Callable[[NachiCommand], None]):
        """Set callback for when commands are sent."""
        self._callback = callback
    
    def start(self):
        """Start the bridge."""
        if not self.nachi.connect():
            print("Failed to connect to Nachi interface")
            return False
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        
        print(f"Nachi bridge started")
        print(f"  Monitoring: {self.irds_file}")
        print(f"  Protocol: {self.nachi.protocol.value}")
        
        return True
    
    def stop(self):
        """Stop the bridge."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self.nachi.disconnect()
    
    def _poll_loop(self):
        """Poll IRDS file for changes."""
        while self._running:
            try:
                if self.irds_file.exists():
                    mtime = self.irds_file.stat().st_mtime
                    if mtime > self._last_mtime:
                        self._last_mtime = mtime
                        self._process_update()
            except Exception as e:
                print(f"Poll error: {e}")
            
            time.sleep(self.poll_interval)
    
    def _process_update(self):
        """Process an IRDS feedback update."""
        try:
            with open(self.irds_file) as f:
                irds_data = json.load(f)
            
            command = self.nachi._translator.translate(irds_data)
            self.nachi.send_command(command)
            
            if self._callback:
                self._callback(command)
                
        except Exception as e:
            print(f"Process error: {e}")


def print_comparison():
    """Print comparison between IRDS output and Nachi input."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║           IRDS Feedback → Nachi Cobot Parameter Mapping                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  IRDS OUTPUT (irds_feedback.json)    →    NACHI FD11 INPUT                  ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║                                                                              ║
║  speed_modifier (0.0-1.0)            →    Speed Override (0-100%)           ║
║  amplitude_modifier (0.0-1.0)        →    Motion Scale (0-100%)             ║
║  force_modifier (0.0-1.0)            →    Force Limit (0-100%)              ║
║  should_pause (bool)                 →    External Pause Signal             ║
║  should_stop (bool)                  →    Emergency Stop Signal             ║
║  confidence (0.0-1.0)                →    Signal Quality Indicator          ║
║  pain_level (0-4)                    →    Reference/Logging                 ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  COMMUNICATION PROTOCOLS SUPPORTED                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║                                                                              ║
║  ✓ TCP/IP Socket      - Simple integration, JSON or binary                  ║
║  ✓ File-based         - For testing and simulation                          ║
║  ○ EtherNet/IP        - Industrial protocol (requires pycomm3)              ║
║  ○ PROFINET           - Industrial protocol (requires additional setup)     ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  EXAMPLE MAPPING                                                             ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║                                                                              ║
║  Pain Level: MODERATE (2)                                                    ║
║    speed_modifier: 0.5    →   speed_override: 50%                           ║
║    amplitude_modifier: 0.7 →  motion_scale: 70%                             ║
║    force_modifier: 0.6    →   force_limit: 60%                              ║
║    should_pause: False    →   external_pause: OFF                           ║
║    should_stop: False     →   emergency_stop: OFF                           ║
║                                                                              ║
║  Pain Level: CRITICAL (4)                                                    ║
║    speed_modifier: 0.0    →   speed_override: 0%                            ║
║    should_stop: True      →   emergency_stop: ON                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


def demo():
    """Demonstrate the Nachi interface."""
    print("\n" + "=" * 60)
    print("  Nachi Cobot Interface Demo")
    print("=" * 60)
    
    print_comparison()
    
    # Create sample IRDS feedback
    sample_feedback = {
        "pain_level": 2,
        "pain_level_name": "MODERATE",
        "pain_score": 45.5,
        "speed_modifier": 0.5,
        "amplitude_modifier": 0.7,
        "force_modifier": 0.6,
        "should_pause": False,
        "should_stop": False,
        "confidence": 0.85,
        "timestamp": time.time()
    }
    
    print("\n📥 Sample IRDS Feedback:")
    print(json.dumps(sample_feedback, indent=2))
    
    # Translate to Nachi command
    translator = IRDSToNachiTranslator()
    nachi_cmd = translator.translate(sample_feedback)
    
    print("\n📤 Translated Nachi Command:")
    print(nachi_cmd.to_json())
    
    print("\n📡 Binary format (16 bytes):")
    binary = nachi_cmd.to_bytes()
    print(f"   {binary.hex()}")
    
    # Create output file
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "nachi_command.json"
    
    with open(output_file, 'w') as f:
        f.write(nachi_cmd.to_json())
    
    print(f"\n✓ Command saved to: {output_file}")
    
    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--compare':
        print_comparison()
    else:
        demo()



