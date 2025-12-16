"""
Face Pain Detection Module
Part of Robotic Arm Feedback System

This module analyzes facial expressions to detect pain levels
using computer vision and facial landmark detection.

Components:
- PainDetector: Main class for pain level detection
- FaceAnalyzer: Facial landmark and expression analysis
- VideoSource: Video/camera input handler
"""

from .pain_detector import PainDetector, PainReading
from .video_source import VideoSource

__all__ = ['PainDetector', 'PainReading', 'VideoSource']

