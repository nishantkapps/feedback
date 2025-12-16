"""
Pain Detector Module
Analyzes facial expressions to estimate pain levels.

Uses OpenCV's DNN face detector and facial landmark detection.
Pain detection is based on Facial Action Units (FAUs) associated with pain:
- AU4: Brow lowerer (furrowed brow)
- AU6: Cheek raiser
- AU7: Lid tightener
- AU9: Nose wrinkler
- AU10: Upper lip raiser
- AU43: Eyes closed
"""

import time
import urllib.request
from dataclasses import dataclass
from typing import Optional, Tuple
from collections import deque
from pathlib import Path
import numpy as np

try:
    import cv2
except ImportError as e:
    raise ImportError(
        "OpenCV not installed. Run: pip install opencv-python"
    ) from e


# Model URLs for downloading
FACE_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
FACE_MODEL_URL = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
LANDMARK_MODEL_URL = "https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml"


@dataclass
class PainReading:
    """Data class representing a pain assessment reading."""
    pain_score: float          # 0-100 pain score
    level: str                 # NONE/MILD/MODERATE/SEVERE/EXTREME
    brow_furrow: float         # Brow lowering intensity
    eye_squeeze: float         # Eye closure/squinting intensity
    nose_wrinkle: float        # Nose wrinkle intensity
    lip_raise: float           # Upper lip raise intensity
    face_detected: bool        # Whether a face was detected
    timestamp: float           # Unix timestamp
    frame_number: int          # Video frame number
    
    def to_dict(self) -> dict:
        return {
            'pain_score': round(self.pain_score, 2),
            'level': self.level,
            'brow_furrow': round(self.brow_furrow, 2),
            'eye_squeeze': round(self.eye_squeeze, 2),
            'nose_wrinkle': round(self.nose_wrinkle, 2),
            'lip_raise': round(self.lip_raise, 2),
            'face_detected': self.face_detected,
            'timestamp': self.timestamp,
            'frame_number': self.frame_number
        }


class PainDetector:
    """
    Facial pain detector using OpenCV DNN face detection.
    
    Analyzes facial landmarks to detect pain-related expressions
    based on Facial Action Coding System (FACS).
    
    Usage:
        detector = PainDetector()
        
        # From image/frame
        reading = detector.analyze_frame(frame)
        
        # Continuous from video
        for reading in detector.analyze_video(video_path):
            print(f"Pain level: {reading.level}")
    """
    
    # Pain level thresholds
    LEVEL_NONE = "NONE"
    LEVEL_MILD = "MILD"
    LEVEL_MODERATE = "MODERATE"
    LEVEL_SEVERE = "SEVERE"
    LEVEL_EXTREME = "EXTREME"
    
    def __init__(
        self,
        confidence_threshold: float = 0.5,
        history_size: int = 30,
        models_dir: str = None
    ):
        """
        Initialize the pain detector.
        
        Args:
            confidence_threshold: Minimum confidence for face detection
            history_size: Number of readings to keep for smoothing
            models_dir: Directory to store/load model files
        """
        self.confidence_threshold = confidence_threshold
        self._history: deque = deque(maxlen=history_size)
        self._frame_count = 0
        self._baseline_calibrated = False
        self._baseline = {}
        
        # Setup models directory
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            self.models_dir = Path(__file__).parent / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize face detector and landmark detector
        self._init_detectors()
    
    def _download_file(self, url: str, filepath: Path) -> bool:
        """Download a file if it doesn't exist."""
        if filepath.exists():
            return True
        
        print(f"Downloading {filepath.name}...")
        try:
            urllib.request.urlretrieve(url, str(filepath))
            print(f"Downloaded {filepath.name}")
            return True
        except Exception as e:
            print(f"Failed to download {filepath.name}: {e}")
            return False
    
    def _init_detectors(self):
        """Initialize face and landmark detectors."""
        # Download models if needed
        proto_path = self.models_dir / "deploy.prototxt"
        model_path = self.models_dir / "face_model.caffemodel"
        landmark_path = self.models_dir / "lbfmodel.yaml"
        
        self._download_file(FACE_PROTO_URL, proto_path)
        self._download_file(FACE_MODEL_URL, model_path)
        self._download_file(LANDMARK_MODEL_URL, landmark_path)
        
        # Load face detector
        if proto_path.exists() and model_path.exists():
            self.face_net = cv2.dnn.readNetFromCaffe(str(proto_path), str(model_path))
            print("Face detector loaded")
        else:
            # Fallback to Haar cascade
            self.face_net = None
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            print("Using Haar cascade face detector (fallback)")
        
        # Load landmark detector
        if landmark_path.exists():
            self.landmark_detector = cv2.face.createFacemarkLBF()
            self.landmark_detector.loadModel(str(landmark_path))
            self.has_landmarks = True
            print("Landmark detector loaded")
        else:
            self.has_landmarks = False
            print("Landmark detector not available - using simplified detection")
    
    def _detect_face_dnn(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect face using DNN."""
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0), swapRB=False, crop=False
        )
        
        self.face_net.setInput(blob)
        detections = self.face_net.forward()
        
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > self.confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                # Ensure valid coordinates
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                return (x1, y1, x2 - x1, y2 - y1)
        
        return None
    
    def _detect_face_haar(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect face using Haar cascade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        
        if len(faces) > 0:
            return tuple(faces[0])
        return None
    
    def _detect_face(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect face in frame."""
        if self.face_net is not None:
            return self._detect_face_dnn(frame)
        else:
            return self._detect_face_haar(frame)
    
    def _get_landmarks(self, frame: np.ndarray, face_rect: Tuple) -> Optional[np.ndarray]:
        """Get facial landmarks for detected face."""
        if not self.has_landmarks:
            return None
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = np.array([[face_rect]])
        
        success, landmarks = self.landmark_detector.fit(gray, faces)
        
        if success and len(landmarks) > 0:
            return landmarks[0][0]  # 68 landmarks
        return None
    
    def analyze_frame(
        self,
        frame: np.ndarray,
        calibrate_baseline: bool = False
    ) -> PainReading:
        """
        Analyze a single frame for pain indicators.
        
        Args:
            frame: BGR image from OpenCV
            calibrate_baseline: If True, use this frame as neutral baseline
            
        Returns:
            PainReading with pain assessment
        """
        self._frame_count += 1
        
        # Detect face
        face_rect = self._detect_face(frame)
        
        if face_rect is None:
            return PainReading(
                pain_score=0,
                level=self.LEVEL_NONE,
                brow_furrow=0,
                eye_squeeze=0,
                nose_wrinkle=0,
                lip_raise=0,
                face_detected=False,
                timestamp=time.time(),
                frame_number=self._frame_count
            )
        
        # Get landmarks if available
        landmarks = self._get_landmarks(frame, face_rect)
        
        # Extract metrics
        if landmarks is not None:
            metrics = self._extract_landmark_metrics(landmarks, face_rect)
        else:
            metrics = self._extract_basic_metrics(frame, face_rect)
        
        if calibrate_baseline:
            self._calibrate_baseline(metrics)
        
        # Calculate pain indicators
        brow_furrow = self._calculate_brow_furrow(metrics)
        eye_squeeze = self._calculate_eye_squeeze(metrics)
        nose_wrinkle = self._calculate_nose_wrinkle(metrics)
        lip_raise = self._calculate_lip_raise(metrics)
        
        # Combine into overall pain score
        pain_score = (
            brow_furrow * 0.30 +
            eye_squeeze * 0.35 +
            nose_wrinkle * 0.15 +
            lip_raise * 0.20
        )
        
        # Apply smoothing
        pain_score = self._smooth_score(pain_score)
        
        # Determine level
        level = self._score_to_level(pain_score)
        
        reading = PainReading(
            pain_score=pain_score,
            level=level,
            brow_furrow=brow_furrow,
            eye_squeeze=eye_squeeze,
            nose_wrinkle=nose_wrinkle,
            lip_raise=lip_raise,
            face_detected=True,
            timestamp=time.time(),
            frame_number=self._frame_count
        )
        
        self._history.append(reading)
        return reading
    
    def _extract_landmark_metrics(self, landmarks: np.ndarray, face_rect: Tuple) -> dict:
        """Extract metrics from 68-point facial landmarks."""
        # Landmark indices (68-point model):
        # Jaw: 0-16, Right eyebrow: 17-21, Left eyebrow: 22-26
        # Nose: 27-35, Right eye: 36-41, Left eye: 42-47
        # Outer lip: 48-59, Inner lip: 60-67
        
        x, y, w, h = face_rect
        face_height = h
        
        # Eye openness (vertical distance between upper and lower eyelid)
        right_eye_top = landmarks[37:39].mean(axis=0)
        right_eye_bottom = landmarks[40:42].mean(axis=0)
        left_eye_top = landmarks[43:45].mean(axis=0)
        left_eye_bottom = landmarks[46:48].mean(axis=0)
        
        right_eye_openness = np.linalg.norm(right_eye_top - right_eye_bottom) / face_height
        left_eye_openness = np.linalg.norm(left_eye_top - left_eye_bottom) / face_height
        
        # Brow position (distance from brow to eye)
        right_brow = landmarks[17:22].mean(axis=0)
        left_brow = landmarks[22:27].mean(axis=0)
        right_eye_center = landmarks[36:42].mean(axis=0)
        left_eye_center = landmarks[42:48].mean(axis=0)
        
        right_brow_height = (right_eye_center[1] - right_brow[1]) / face_height
        left_brow_height = (left_eye_center[1] - left_brow[1]) / face_height
        
        # Inner brow distance (for furrow)
        inner_brow_dist = np.linalg.norm(landmarks[21] - landmarks[22]) / face_height
        
        # Nose bridge length
        nose_bridge = np.linalg.norm(landmarks[27] - landmarks[30]) / face_height
        
        # Lip to nose distance
        upper_lip = landmarks[51]  # Top of upper lip
        nose_tip = landmarks[33]
        lip_to_nose = np.linalg.norm(upper_lip - nose_tip) / face_height
        
        # Mouth openness
        mouth_top = landmarks[51]
        mouth_bottom = landmarks[57]
        mouth_openness = np.linalg.norm(mouth_top - mouth_bottom) / face_height
        
        return {
            'right_eye_openness': right_eye_openness,
            'left_eye_openness': left_eye_openness,
            'right_brow_height': right_brow_height,
            'left_brow_height': left_brow_height,
            'inner_brow_dist': inner_brow_dist,
            'nose_bridge': nose_bridge,
            'lip_to_nose': lip_to_nose,
            'mouth_openness': mouth_openness,
            'face_height': face_height,
            'has_landmarks': True
        }
    
    def _extract_basic_metrics(self, frame: np.ndarray, face_rect: Tuple) -> dict:
        """Extract basic metrics without landmarks (fallback)."""
        x, y, w, h = face_rect
        face_roi = frame[y:y+h, x:x+w]
        
        # Convert to grayscale and analyze regions
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        # Estimate eye region (upper third of face)
        eye_region = gray[int(h*0.2):int(h*0.4), :]
        
        # Estimate brow region
        brow_region = gray[int(h*0.1):int(h*0.25), :]
        
        # Use edge detection to estimate tension
        edges = cv2.Canny(gray, 50, 150)
        
        # Edge density in different regions (more edges = more expression)
        eye_edges = cv2.Canny(eye_region, 50, 150)
        brow_edges = cv2.Canny(brow_region, 50, 150)
        
        eye_edge_density = np.sum(eye_edges > 0) / eye_edges.size
        brow_edge_density = np.sum(brow_edges > 0) / brow_edges.size
        
        return {
            'eye_edge_density': eye_edge_density,
            'brow_edge_density': brow_edge_density,
            'face_height': h,
            'has_landmarks': False
        }
    
    def _calibrate_baseline(self, metrics: dict):
        """Set baseline from neutral expression."""
        self._baseline = metrics.copy()
        self._baseline_calibrated = True
    
    def _calculate_brow_furrow(self, metrics: dict) -> float:
        """Calculate brow furrow intensity (0-100)."""
        if metrics.get('has_landmarks'):
            avg_brow = (metrics['right_brow_height'] + metrics['left_brow_height']) / 2
            
            if self._baseline_calibrated and 'right_brow_height' in self._baseline:
                baseline_brow = (self._baseline['right_brow_height'] + self._baseline['left_brow_height']) / 2
                # Lower brow = higher furrow
                change = (baseline_brow - avg_brow) / max(baseline_brow, 0.01)
                inner_change = 0
                if 'inner_brow_dist' in self._baseline:
                    inner_change = (self._baseline['inner_brow_dist'] - metrics['inner_brow_dist']) / max(self._baseline['inner_brow_dist'], 0.01)
                score = (max(0, change) * 60 + max(0, inner_change) * 40) * 100
            else:
                # Without baseline, use typical values
                score = max(0, (0.15 - avg_brow) * 300)
        else:
            # Fallback: use edge density
            density = metrics.get('brow_edge_density', 0)
            if self._baseline_calibrated and 'brow_edge_density' in self._baseline:
                change = (density - self._baseline['brow_edge_density']) / max(self._baseline['brow_edge_density'], 0.01)
                score = max(0, change) * 100
            else:
                score = density * 200
        
        return min(100, max(0, score))
    
    def _calculate_eye_squeeze(self, metrics: dict) -> float:
        """Calculate eye squeeze intensity (0-100)."""
        if metrics.get('has_landmarks'):
            avg_openness = (metrics['right_eye_openness'] + metrics['left_eye_openness']) / 2
            
            if self._baseline_calibrated and 'right_eye_openness' in self._baseline:
                baseline_openness = (self._baseline['right_eye_openness'] + self._baseline['left_eye_openness']) / 2
                # Less open = more squeeze
                change = (baseline_openness - avg_openness) / max(baseline_openness, 0.01)
                score = max(0, change) * 100
            else:
                # Without baseline
                normal_openness = 0.045
                score = max(0, (normal_openness - avg_openness) / normal_openness * 100)
        else:
            density = metrics.get('eye_edge_density', 0)
            if self._baseline_calibrated and 'eye_edge_density' in self._baseline:
                change = (density - self._baseline['eye_edge_density']) / max(self._baseline['eye_edge_density'], 0.01)
                score = max(0, change) * 100
            else:
                score = density * 150
        
        return min(100, max(0, score))
    
    def _calculate_nose_wrinkle(self, metrics: dict) -> float:
        """Calculate nose wrinkle intensity (0-100)."""
        if not metrics.get('has_landmarks'):
            return 0
        
        if self._baseline_calibrated and 'nose_bridge' in self._baseline:
            change = (self._baseline['nose_bridge'] - metrics['nose_bridge']) / max(self._baseline['nose_bridge'], 0.01)
            score = max(0, change) * 150
        else:
            score = 0
        
        return min(100, max(0, score))
    
    def _calculate_lip_raise(self, metrics: dict) -> float:
        """Calculate upper lip raise intensity (0-100)."""
        if not metrics.get('has_landmarks'):
            return 0
        
        if self._baseline_calibrated and 'lip_to_nose' in self._baseline:
            change = (self._baseline['lip_to_nose'] - metrics['lip_to_nose']) / max(self._baseline['lip_to_nose'], 0.01)
            score = max(0, change) * 100
        else:
            score = 0
        
        return min(100, max(0, score))
    
    def _smooth_score(self, score: float) -> float:
        """Apply temporal smoothing."""
        if len(self._history) < 3:
            return score
        
        recent_scores = [r.pain_score for r in list(self._history)[-5:]]
        recent_scores.append(score)
        
        weights = [0.1, 0.1, 0.15, 0.2, 0.2, 0.25][-len(recent_scores):]
        weights = [w / sum(weights) for w in weights]
        
        return sum(s * w for s, w in zip(recent_scores, weights))
    
    def _score_to_level(self, score: float) -> str:
        """Convert pain score to level."""
        if score < 10:
            return self.LEVEL_NONE
        elif score < 30:
            return self.LEVEL_MILD
        elif score < 55:
            return self.LEVEL_MODERATE
        elif score < 80:
            return self.LEVEL_SEVERE
        else:
            return self.LEVEL_EXTREME
    
    def get_level_description(self, level: str, score: float) -> dict:
        """Get description and recommendations for pain level."""
        descriptions = {
            self.LEVEL_NONE: {
                'title': 'No Pain Detected',
                'description': 'Facial expression appears relaxed with no signs of discomfort.',
                'recommendation': 'Normal operation - robotic arm can continue at full speed.',
                'color': '#10b981',
                'icon': '😊',
                'arm_status': 'Full Speed (100%)'
            },
            self.LEVEL_MILD: {
                'title': 'Mild Discomfort',
                'description': 'Slight tension detected in facial muscles. Minor brow movement or eye narrowing.',
                'recommendation': 'Monitor closely - consider reducing arm speed slightly.',
                'color': '#f59e0b',
                'icon': '😐',
                'arm_status': 'Reduced Speed (80%)'
            },
            self.LEVEL_MODERATE: {
                'title': 'Moderate Pain',
                'description': 'Noticeable pain indicators: furrowed brow, partially closed eyes, or tense expression.',
                'recommendation': 'Reduce robotic arm speed and check for issues.',
                'color': '#f97316',
                'icon': '😣',
                'arm_status': 'Caution Mode (50%)'
            },
            self.LEVEL_SEVERE: {
                'title': 'Severe Pain',
                'description': 'Strong pain expression: deeply furrowed brow, squeezed eyes, raised upper lip.',
                'recommendation': 'Pause robotic arm operation immediately!',
                'color': '#ef4444',
                'icon': '😖',
                'arm_status': 'Paused (20%)'
            },
            self.LEVEL_EXTREME: {
                'title': 'EXTREME PAIN',
                'description': 'Maximum pain expression detected. Subject is in significant distress.',
                'recommendation': 'EMERGENCY STOP - Halt all operations and provide assistance!',
                'color': '#dc2626',
                'icon': '😫',
                'arm_status': 'EMERGENCY STOP (0%)'
            }
        }
        
        info = descriptions.get(level, descriptions[self.LEVEL_NONE])
        info['score'] = score
        info['level'] = level
        return info
    
    def get_history(self) -> list:
        """Get recent pain readings."""
        return list(self._history)
    
    def get_latest(self) -> Optional[PainReading]:
        """Get most recent reading."""
        return self._history[-1] if self._history else None
    
    def reset(self):
        """Reset detector state."""
        self._history.clear()
        self._frame_count = 0
        self._baseline_calibrated = False
    
    def close(self):
        """Release resources."""
        pass  # No cleanup needed for OpenCV
