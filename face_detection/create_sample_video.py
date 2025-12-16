#!/usr/bin/env python3
"""
Create Sample Videos for Face Pain Detection Testing

This script provides multiple options:
1. Generate a synthetic test video with animated face-like shapes
2. Download sample videos from free sources
3. List YouTube URLs that can be used for testing
"""

import sys
import os
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    print("OpenCV not installed. Run: pip install opencv-python numpy")
    sys.exit(1)


def create_synthetic_face_video(output_path: str, duration: float = 10.0, fps: int = 30):
    """
    Create a synthetic video with animated face-like shapes.
    Useful for basic testing of video processing pipeline.
    
    Args:
        output_path: Output video file path
        duration: Video duration in seconds
        fps: Frames per second
    """
    width, height = 640, 480
    total_frames = int(duration * fps)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    print(f"Creating synthetic video: {output_path}")
    print(f"Duration: {duration}s, FPS: {fps}, Total frames: {total_frames}")
    
    for i in range(total_frames):
        # Create frame with gradient background
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Background color (slight animation)
        bg_intensity = 40 + int(20 * np.sin(i / 30))
        frame[:] = (bg_intensity, bg_intensity + 10, bg_intensity + 20)
        
        # Calculate animation phase (0 to 1, cycling)
        phase = (i % (fps * 3)) / (fps * 3)  # 3-second cycle
        
        # Face position (center with slight movement)
        face_x = width // 2 + int(20 * np.sin(i / 20))
        face_y = height // 2 + int(10 * np.sin(i / 15))
        
        # Draw face (oval)
        face_color = (200, 180, 160)  # Skin tone
        cv2.ellipse(frame, (face_x, face_y), (80, 100), 0, 0, 360, face_color, -1)
        
        # Simulate different expressions based on phase
        if phase < 0.33:
            # Neutral expression
            expression = "NEUTRAL"
            eye_openness = 12
            brow_offset = 0
            mouth_curve = 0
        elif phase < 0.66:
            # Mild discomfort
            expression = "MILD PAIN"
            eye_openness = 8
            brow_offset = 5
            mouth_curve = -5
        else:
            # Pain expression
            expression = "PAIN"
            eye_openness = 4
            brow_offset = 10
            mouth_curve = -10
        
        # Draw eyes (adjust based on expression)
        eye_color = (255, 255, 255)
        pupil_color = (50, 50, 50)
        
        # Left eye
        left_eye_x = face_x - 30
        left_eye_y = face_y - 20
        cv2.ellipse(frame, (left_eye_x, left_eye_y), (15, eye_openness), 0, 0, 360, eye_color, -1)
        cv2.circle(frame, (left_eye_x, left_eye_y), 5, pupil_color, -1)
        
        # Right eye
        right_eye_x = face_x + 30
        right_eye_y = face_y - 20
        cv2.ellipse(frame, (right_eye_x, right_eye_y), (15, eye_openness), 0, 0, 360, eye_color, -1)
        cv2.circle(frame, (right_eye_x, right_eye_y), 5, pupil_color, -1)
        
        # Draw eyebrows (furrowed when in pain)
        brow_color = (100, 80, 60)
        # Left brow
        cv2.line(frame, 
                 (left_eye_x - 20, left_eye_y - 20 + brow_offset),
                 (left_eye_x + 15, left_eye_y - 25),
                 brow_color, 3)
        # Right brow  
        cv2.line(frame,
                 (right_eye_x - 15, right_eye_y - 25),
                 (right_eye_x + 20, right_eye_y - 20 + brow_offset),
                 brow_color, 3)
        
        # Draw nose
        nose_color = (180, 160, 140)
        cv2.line(frame, (face_x, face_y - 10), (face_x, face_y + 15), nose_color, 2)
        cv2.ellipse(frame, (face_x, face_y + 15), (8, 5), 0, 0, 180, nose_color, 2)
        
        # Draw mouth (curved based on expression)
        mouth_color = (150, 100, 100)
        mouth_y = face_y + 40
        
        # Draw curved mouth
        pts = np.array([
            [face_x - 25, mouth_y],
            [face_x - 10, mouth_y + mouth_curve],
            [face_x + 10, mouth_y + mouth_curve],
            [face_x + 25, mouth_y]
        ], np.int32)
        cv2.polylines(frame, [pts], False, mouth_color, 3)
        
        # Add expression label
        label_color = (0, 255, 0) if expression == "NEUTRAL" else (0, 255, 255) if expression == "MILD PAIN" else (0, 0, 255)
        cv2.putText(frame, expression, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, label_color, 2)
        
        # Add frame info
        cv2.putText(frame, f"Frame: {i+1}/{total_frames}", (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Add instruction
        cv2.putText(frame, "Synthetic Test Video - Use real video for accurate detection",
                    (20, height - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        
        out.write(frame)
        
        # Progress indicator
        if (i + 1) % fps == 0:
            print(f"  Progress: {(i+1)/total_frames*100:.0f}%")
    
    out.release()
    print(f"Video saved: {output_path}")
    return output_path


def download_sample_video(output_path: str, url: str = None):
    """
    Download a sample video using yt-dlp.
    
    Args:
        output_path: Where to save the video
        url: YouTube URL (uses default if not provided)
    """
    try:
        import yt_dlp
    except ImportError:
        print("yt-dlp not installed. Run: pip install yt-dlp")
        return None
    
    # Default: A short creative commons video with faces
    if url is None:
        # Using a sample video URL - replace with actual URL when using
        print("Please provide a YouTube URL with the --url argument")
        print("\nSuggested test videos (copy URL and use with --url):")
        print_sample_urls()
        return None
    
    print(f"Downloading video from: {url}")
    print(f"Saving to: {output_path}")
    
    ydl_opts = {
        'format': 'best[height<=480][ext=mp4]/best[height<=480]/best',
        'outtmpl': output_path,
        'quiet': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"Download complete: {output_path}")
        return output_path
    except Exception as e:
        print(f"Download failed: {e}")
        return None


def print_sample_urls():
    """Print suggested YouTube URLs for testing."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                    Sample YouTube URLs for Testing                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  For face pain detection testing, use videos with:                ║
║  - Clear frontal face views                                       ║
║  - Good lighting                                                  ║
║  - Various facial expressions                                     ║
║                                                                   ║
║  Suggested search terms on YouTube:                               ║
║  - "facial expression demonstration"                              ║
║  - "pain expression face"                                         ║
║  - "facial action coding system demo"                             ║
║  - "emotion recognition test video"                               ║
║                                                                   ║
║  Usage in dashboard:                                              ║
║  1. Select "YouTube" as source                                    ║
║  2. Paste the YouTube URL                                         ║
║  3. Click "Start Analysis"                                        ║
║                                                                   ║
╚══════════════════════════════════════════════════════════════════╝
""")


def record_webcam_video(output_path: str, duration: float = 10.0):
    """
    Record a video from webcam for testing.
    
    Args:
        output_path: Output video file path
        duration: Recording duration in seconds
    """
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return None
    
    fps = 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    print(f"Recording from webcam for {duration} seconds...")
    print("Press 'q' to stop early")
    print("")
    print("TIP: Make different facial expressions:")
    print("  - Neutral face (first few seconds)")
    print("  - Slight frown / squint")
    print("  - Exaggerated pain expression")
    print("")
    
    start_time = cv2.getTickCount()
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
        
        if elapsed >= duration:
            break
        
        # Add recording indicator
        cv2.circle(frame, (30, 30), 10, (0, 0, 255), -1)
        cv2.putText(frame, f"REC {elapsed:.1f}s / {duration}s", (50, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        out.write(frame)
        frame_count += 1
        
        # Display preview
        cv2.imshow('Recording (Press Q to stop)', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    
    print(f"\nRecording complete!")
    print(f"Saved {frame_count} frames to: {output_path}")
    return output_path


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create sample videos for face pain detection testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create synthetic test video
  python create_sample_video.py --synthetic
  
  # Record from webcam
  python create_sample_video.py --record --duration 15
  
  # Download from YouTube
  python create_sample_video.py --download --url "https://youtube.com/watch?v=..."
  
  # Show suggested YouTube URLs
  python create_sample_video.py --list-urls
        """
    )
    
    parser.add_argument('--synthetic', action='store_true',
                        help='Create synthetic test video with animated face')
    parser.add_argument('--record', action='store_true',
                        help='Record video from webcam')
    parser.add_argument('--download', action='store_true',
                        help='Download video from YouTube')
    parser.add_argument('--list-urls', action='store_true',
                        help='Show suggested YouTube URLs for testing')
    parser.add_argument('--url', type=str,
                        help='YouTube URL to download')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file path')
    parser.add_argument('--duration', '-d', type=float, default=10.0,
                        help='Video duration in seconds (default: 10)')
    
    args = parser.parse_args()
    
    # Default output directory
    output_dir = Path(__file__).parent.parent / 'data' / 'videos'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.list_urls:
        print_sample_urls()
        return
    
    if args.synthetic:
        output_path = args.output or str(output_dir / 'synthetic_face_test.mp4')
        create_synthetic_face_video(output_path, args.duration)
        
    elif args.record:
        output_path = args.output or str(output_dir / 'webcam_recording.mp4')
        record_webcam_video(output_path, args.duration)
        
    elif args.download:
        output_path = args.output or str(output_dir / 'downloaded_video.mp4')
        download_sample_video(output_path, args.url)
        
    else:
        # Default: create synthetic video
        print("No option specified. Creating synthetic test video...")
        print("Use --help to see all options\n")
        output_path = str(output_dir / 'synthetic_face_test.mp4')
        create_synthetic_face_video(output_path, args.duration)


if __name__ == '__main__':
    main()

