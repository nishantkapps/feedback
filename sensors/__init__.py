"""
Sensors Module for Robotic Arm Feedback System

This module provides interfaces for various sensors used in the
feedback loop for the robotic arm control system.

Available sensors:
- PiezoSensor: Pressure detection via piezo sensor connected to Arduino
- FilePiezoSensor: File-based mock sensor for testing without hardware
"""

from .piezo_reader import PiezoSensor, PressureReading
from .file_reader import FilePiezoSensor

__all__ = ['PiezoSensor', 'PressureReading', 'FilePiezoSensor']

