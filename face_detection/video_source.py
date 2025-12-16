"""
Video Source Handler
Handles video file, camera, and YouTube streaming for face pain detection.
Supports progressive loading for long videos.
"""

import time
import threading
import re
import os
from pathlib import Path
from typing import Optional, Generator
from dataclasses import dataclass
from queue import Queue, Empty

try:
    import cv2
    import numpy as np
except ImportError as e:
    raise ImportError("OpenCV not installed. Run: pip install opencv-python") from e


@dataclass
class FrameInfo:
    """Information about a video frame."""
    frame: np.ndarray
    frame_number: int
    timestamp: float
    fps: float
    total_frames: int
    width: int
    height: int


def is_youtube_url(url: str) -> bool:
    """Check if a URL is a YouTube link."""
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/embed/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/v/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    return False


def get_youtube_stream_url(youtube_url: str, quality: str = 'medium') -> Optional[str]:
    """
    Get direct stream URL from YouTube using yt-dlp.
    Uses format that supports streaming (not download-only).
    
    Args:
        youtube_url: YouTube video URL
        quality: 'low', 'medium', or 'high'
        
    Returns:
        Direct stream URL or None if failed
    """
    try:
        import yt_dlp
        
        # Format selection for streaming compatibility
        # Prefer formats that can be streamed (not fragmented)
        format_map = {
            'low': 'best[height<=360][ext=mp4]/best[height<=360]/worst',
            'medium': 'best[height<=480][ext=mp4]/best[height<=480]/best[height<=720]',
            'high': 'best[height<=720][ext=mp4]/best[height<=720]/best'
        }
        
        ydl_opts = {
            'format': format_map.get(quality, format_map['medium']),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        print(f"Extracting stream URL (quality: {quality})...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            
            # Get the direct URL
            if 'url' in info:
                return info['url']
            
            # For formats with separate audio/video, get video URL
            if 'requested_formats' in info:
                for fmt in info['requested_formats']:
                    if fmt.get('vcodec') != 'none' and 'url' in fmt:
                        return fmt['url']
            
            # Fallback to formats list
            if 'formats' in info:
                # Prefer mp4 formats that are streamable
                for fmt in reversed(info['formats']):
                    if (fmt.get('url') and 
                        fmt.get('vcodec') != 'none' and
                        fmt.get('ext') == 'mp4' and
                        not fmt.get('fragments')):  # Avoid fragmented streams
                        return fmt['url']
                
                # Last resort: any video format
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and fmt.get('vcodec') != 'none':
                        return fmt['url']
        
        return None
        
    except ImportError:
        print("yt-dlp not installed. Run: pip install yt-dlp")
        return None
    except Exception as e:
        print(f"Error getting YouTube stream: {e}")
        return None


def get_youtube_info(youtube_url: str) -> dict:
    """Get video information from YouTube."""
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
            }
    except Exception as e:
        print(f"Error getting YouTube info: {e}")
        return {}


class FrameBuffer:
    """Thread-safe frame buffer for progressive video loading."""
    
    def __init__(self, max_size: int = 60):
        self._queue = Queue(maxsize=max_size)
        self._stop_flag = threading.Event()
        self._eof = threading.Event()
        self._error = None
        
    def put(self, frame_info: FrameInfo, timeout: float = 1.0) -> bool:
        """Add frame to buffer."""
        if self._stop_flag.is_set():
            return False
        try:
            self._queue.put(frame_info, timeout=timeout)
            return True
        except:
            return False
    
    def get(self, timeout: float = 1.0) -> Optional[FrameInfo]:
        """Get frame from buffer."""
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None
    
    def stop(self):
        """Signal to stop."""
        self._stop_flag.set()
    
    def set_eof(self):
        """Signal end of file."""
        self._eof.set()
    
    def set_error(self, error: str):
        """Set error message."""
        self._error = error
        self._stop_flag.set()
    
    @property
    def is_stopped(self) -> bool:
        return self._stop_flag.is_set()
    
    @property
    def is_eof(self) -> bool:
        return self._eof.is_set() and self._queue.empty()
    
    @property
    def error(self) -> Optional[str]:
        return self._error
    
    @property
    def size(self) -> int:
        return self._queue.qsize()


class VideoSource:
    """
    Video source handler supporting camera, file, and YouTube streaming.
    
    For YouTube videos, uses progressive streaming to start playback quickly.
    
    Usage:
        # From camera
        source = VideoSource(camera=0)
        
        # From file
        source = VideoSource(file_path='video.mp4')
        
        # From YouTube (streams progressively)
        source = VideoSource(youtube_url='https://www.youtube.com/watch?v=...')
        
        # Read frames
        for frame_info in source.frames():
            process(frame_info.frame)
    """
    
    def __init__(
        self,
        file_path: Optional[str] = None,
        camera: Optional[int] = None,
        youtube_url: Optional[str] = None,
        target_fps: float = 30.0,
        resize_width: Optional[int] = None,
        youtube_quality: str = 'medium',
        buffer_size: int = 60
    ):
        """
        Initialize video source.
        
        Args:
            file_path: Path to video file
            camera: Camera device index (0 for default webcam)
            youtube_url: YouTube video URL
            target_fps: Target frame rate for processing
            resize_width: Resize frames to this width (maintains aspect ratio)
            youtube_quality: Quality for YouTube ('low', 'medium', 'high')
            buffer_size: Frame buffer size for streaming
        """
        # Validate inputs
        sources = sum([file_path is not None, camera is not None, youtube_url is not None])
        if sources > 1:
            raise ValueError("Specify only one source: file_path, camera, or youtube_url")
        
        if sources == 0:
            camera = 0  # Default to webcam
        
        self.file_path = file_path
        self.camera_index = camera
        self.youtube_url = youtube_url
        self.target_fps = target_fps
        self.resize_width = resize_width
        self.youtube_quality = youtube_quality
        self.buffer_size = buffer_size
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_camera = camera is not None
        self._is_youtube = youtube_url is not None
        self._stream_url: Optional[str] = None
        self._frame_count = 0
        self._start_time = 0
        self._stop_flag = threading.Event()
        self._youtube_info: dict = {}
        
        # For progressive loading
        self._frame_buffer: Optional[FrameBuffer] = None
        self._reader_thread: Optional[threading.Thread] = None
        
        # Video properties (set after open)
        self.fps = 0
        self.total_frames = 0
        self.width = 0
        self.height = 0
        self.duration = 0
    
    def open(self) -> bool:
        """
        Open the video source.
        
        Returns:
            True if successful
        """
        if self._is_camera:
            self._cap = cv2.VideoCapture(self.camera_index)
            source_name = f"camera {self.camera_index}"
            
        elif self._is_youtube:
            print(f"Connecting to YouTube: {self.youtube_url}")
            
            # Get video info
            self._youtube_info = get_youtube_info(self.youtube_url)
            if self._youtube_info:
                title = self._youtube_info.get('title', 'Unknown')
                duration = self._youtube_info.get('duration', 0)
                print(f"Video: {title}")
                print(f"Duration: {duration // 60}m {duration % 60}s")
            
            # Get stream URL
            self._stream_url = get_youtube_stream_url(self.youtube_url, self.youtube_quality)
            if not self._stream_url:
                raise RuntimeError("Failed to get YouTube stream URL. Check the URL and try again.")
            
            print("Opening stream (this may take a few seconds)...")
            
            # Set environment variable to help with streaming
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
            
            self._cap = cv2.VideoCapture(self._stream_url, cv2.CAP_FFMPEG)
            
            # Set buffer size for smoother streaming
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
            
            source_name = "YouTube"
            
        else:
            if not Path(self.file_path).exists():
                raise FileNotFoundError(f"Video file not found: {self.file_path}")
            self._cap = cv2.VideoCapture(self.file_path)
            source_name = self.file_path
        
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open {source_name}")
        
        # Get video properties
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if self.total_frames > 0 and self.fps > 0:
            self.duration = self.total_frames / self.fps
        elif self._is_youtube and self._youtube_info.get('duration'):
            self.duration = self._youtube_info['duration']
        
        self._frame_count = 0
        self._start_time = time.time()
        self._stop_flag.clear()
        
        print(f"Opened {source_name}: {self.width}x{self.height} @ {self.fps:.1f}fps")
        
        # Start background reader for YouTube
        if self._is_youtube:
            self._start_background_reader()
        
        return True
    
    def _start_background_reader(self):
        """Start background thread to buffer frames."""
        self._frame_buffer = FrameBuffer(max_size=self.buffer_size)
        self._reader_thread = threading.Thread(target=self._background_read, daemon=True)
        self._reader_thread.start()
        
        # Wait for initial frames to buffer
        print("Buffering frames...")
        timeout = time.time() + 10  # 10 second timeout
        while self._frame_buffer.size < 10 and time.time() < timeout:
            if self._frame_buffer.error:
                raise RuntimeError(f"Stream error: {self._frame_buffer.error}")
            time.sleep(0.1)
        
        if self._frame_buffer.size > 0:
            print(f"Buffered {self._frame_buffer.size} frames, starting playback...")
        else:
            print("Warning: No frames buffered yet, playback may be choppy")
    
    def _background_read(self):
        """Background thread to continuously read frames."""
        consecutive_failures = 0
        max_failures = 30  # Allow some failures for network hiccups
        
        while not self._stop_flag.is_set() and not self._frame_buffer.is_stopped:
            try:
                ret, frame = self._cap.read()
                
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        self._frame_buffer.set_eof()
                        break
                    time.sleep(0.1)
                    continue
                
                consecutive_failures = 0
                self._frame_count += 1
                
                # Resize if needed
                if self.resize_width and frame.shape[1] != self.resize_width:
                    aspect = frame.shape[0] / frame.shape[1]
                    new_height = int(self.resize_width * aspect)
                    frame = cv2.resize(frame, (self.resize_width, new_height))
                
                frame_info = FrameInfo(
                    frame=frame,
                    frame_number=self._frame_count,
                    timestamp=time.time() - self._start_time,
                    fps=self.fps,
                    total_frames=self.total_frames,
                    width=frame.shape[1],
                    height=frame.shape[0]
                )
                
                if not self._frame_buffer.put(frame_info, timeout=1.0):
                    break
                    
            except Exception as e:
                self._frame_buffer.set_error(str(e))
                break
    
    def close(self):
        """Release video source."""
        self._stop_flag.set()
        
        if self._frame_buffer:
            self._frame_buffer.stop()
        
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        
        if self._cap:
            self._cap.release()
            self._cap = None
    
    def read_frame(self) -> Optional[FrameInfo]:
        """
        Read a single frame.
        
        Returns:
            FrameInfo or None if no more frames
        """
        if not self._cap or not self._cap.isOpened():
            return None
        
        # For YouTube, read from buffer
        if self._is_youtube and self._frame_buffer:
            frame_info = self._frame_buffer.get(timeout=0.5)
            if frame_info is None and self._frame_buffer.is_eof:
                return None
            return frame_info
        
        # Direct read for camera and local files
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        
        self._frame_count += 1
        
        # Resize if specified
        if self.resize_width and frame.shape[1] != self.resize_width:
            aspect = frame.shape[0] / frame.shape[1]
            new_height = int(self.resize_width * aspect)
            frame = cv2.resize(frame, (self.resize_width, new_height))
        
        return FrameInfo(
            frame=frame,
            frame_number=self._frame_count,
            timestamp=time.time() - self._start_time,
            fps=self.fps,
            total_frames=self.total_frames,
            width=frame.shape[1],
            height=frame.shape[0]
        )
    
    def frames(self, skip_frames: int = 0) -> Generator[FrameInfo, None, None]:
        """
        Generator that yields frames.
        
        Args:
            skip_frames: Number of frames to skip between yields (for performance)
            
        Yields:
            FrameInfo for each frame
        """
        if not self._cap:
            self.open()
        
        frame_interval = 1.0 / self.target_fps
        last_frame_time = 0
        skip_counter = 0
        
        while not self._stop_flag.is_set():
            # Rate limiting for real-time playback
            current_time = time.time()
            if not self._is_camera:
                elapsed = current_time - last_frame_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
            
            frame_info = self.read_frame()
            if frame_info is None:
                break
            
            # Skip frames if specified
            if skip_frames > 0:
                skip_counter += 1
                if skip_counter <= skip_frames:
                    continue
                skip_counter = 0
            
            last_frame_time = time.time()
            yield frame_info
    
    def stop(self):
        """Signal to stop frame iteration."""
        self._stop_flag.set()
        if self._frame_buffer:
            self._frame_buffer.stop()
    
    @property
    def is_camera(self) -> bool:
        """Check if source is a camera."""
        return self._is_camera
    
    @property
    def is_youtube(self) -> bool:
        """Check if source is YouTube."""
        return self._is_youtube
    
    @property
    def is_open(self) -> bool:
        """Check if source is open."""
        return self._cap is not None and self._cap.isOpened()
    
    @property
    def current_frame(self) -> int:
        """Get current frame number."""
        return self._frame_count
    
    @property
    def progress(self) -> float:
        """Get playback progress (0-1) for video files."""
        if self._is_camera or self.total_frames == 0:
            return 0
        return self._frame_count / self.total_frames
    
    @property
    def youtube_info(self) -> dict:
        """Get YouTube video info."""
        return self._youtube_info
    
    @property
    def source_type(self) -> str:
        """Get source type string."""
        if self._is_camera:
            return "camera"
        elif self._is_youtube:
            return "youtube"
        else:
            return "file"
    
    @property
    def buffer_status(self) -> str:
        """Get buffer status for YouTube streams."""
        if self._frame_buffer:
            return f"{self._frame_buffer.size}/{self.buffer_size} frames"
        return "N/A"
    
    def seek(self, frame_number: int):
        """Seek to specific frame (video files only)."""
        if self._is_camera or self._is_youtube:
            return
        if self._cap:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self._frame_count = frame_number
    
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def create_test_video(output_path: str, duration: float = 5.0, fps: int = 30):
    """
    Create a simple test video with changing colors.
    Useful for testing without a real video file.
    """
    width, height = 640, 480
    total_frames = int(duration * fps)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    for i in range(total_frames):
        # Create gradient color based on frame
        hue = int((i / total_frames) * 180)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = [hue, 200, 200]  # HSV-like values
        frame = cv2.cvtColor(frame, cv2.COLOR_HSV2BGR)
        
        # Add frame number text
        cv2.putText(
            frame, f"Frame {i+1}/{total_frames}",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
        )
        
        out.write(frame)
    
    out.release()
    print(f"Created test video: {output_path}")
