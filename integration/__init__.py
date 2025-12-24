"""
Integration Module for Robotic Arm Feedback System

This module provides interfaces for integrating pain detection outputs
with external systems like the IRDS gesture recognition model.

The feedback data can be used to:
- Adjust gesture speed based on pain levels
- Modify gesture amplitude to reduce discomfort
- Trigger safety stops when critical pain is detected
"""

from .irds_interface import (
    PainFeedback,
    FeedbackPublisher,
    GestureModifier,
    create_feedback_server,
    create_feedback_client
)

__all__ = [
    'PainFeedback',
    'FeedbackPublisher', 
    'GestureModifier',
    'create_feedback_server',
    'create_feedback_client'
]



