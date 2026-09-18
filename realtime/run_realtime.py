#!/usr/bin/env python3
"""
YachaqMEDICAL — Real-Time Colonoscopy AI System

Run real-time polyp detection during endoscopy procedures.

Two-tier architecture:
  Tier 1: YOLOv8 — Real-time detection (45+ FPS, <25ms per frame)
  Tier 2: MedGemma — Detailed classification on detection (2-5 sec)

Usage:
    # Live from webcam (testing)
    python run_realtime.py --source 0

    # Live from endoscope (RTSP stream)
    python run_realtime.py --source rtsp://192.168.1.100/stream

    # From video file
    python run_realtime.py --source procedure_video.mp4

    # With remote web viewer
    python run_realtime.py --source 0 --web-viewer --port 8080

    # With MedGemma detailed analysis
    python run_realtime.py --source 0 --medgemma

    # Record annotated output
    python run_realtime.py --source 0 --record output_annotated.mp4

Requirements:
    pip install ultralytics opencv-python aiohttp

For MedGemma integration:
    export MEDGEMMA_API_URL=https://api.runpod.ai/v2/YOUR_ID
    export MEDGEMMA_API_KEY=***
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="YachaqMEDICAL — Real-Time Colonoscopy AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_realtime.py --source 0                           # Webcam test
  python run_realtime.py --source rtsp://192.168.1.100/stream # Endoscope
  python run_realtime.py --source video.mp4 --record out.mp4  # Process video
  python run_realtime.py --source 0 --web-viewer --port 8080  # Remote viewer
        """
    )

    parser.add_argument("--source", default="0",
                        help="Video source: 0=webcam, rtsp://..., file path")
    parser.add_argument("--model", default="models/polyp_yolov8.pt",
                        help="YOLO model path")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Detection confidence threshold (0-1)")
    parser.add_argument("--medgemma", action="store_true",
                        help="Enable MedGemma detailed analysis on detections")
    parser.add_argument("--web-viewer", action="store_true",
                        help="Start web viewer for remote monitoring")
    parser.add_argument("--port", type=int, default=8080,
                        help="Web viewer port")
    parser.add_argument("--record", default="",
                        help="Save annotated video to file")
    parser.add_argument("--no-display", action="store_true",
                        help="No OpenCV window (headless mode)")
    parser.add_argument("--output-dir", default="detections",
                        help="Directory to save detection crops")

    args = parser.parse_args()

    # Check dependencies
    try:
        import cv2
    except ImportError:
        print("❌ OpenCV not installed. Run: pip install opencv-python")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ Ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    # Import our detector
    from realtime.detector import RealtimeDetector, WebRTCStreamer

    print("=" * 60)
    print("  YachaqMEDICAL — Real-Time Colonoscopy AI")
    print("  Dr. Jaime Andrés Benítez Kellendonk")
    print("  Surgical Oncology — Quito, Ecuador")
    print("=" * 60)
    print("")

    # Initialize detector
    detector = RealtimeDetector(
        confidence_threshold=args.confidence,
        medgemma_url=os.getenv("MEDGEMMA_API_URL", "") if args.medgemma else "",
        medgemma_key=os.getenv("MEDGEMMA_API_KEY", "") if args.medgemma else "",
        output_dir=args.output_dir,
    )

    # Load model
    model_path = Path(args.model)
    if model_path.exists():
        detector.load_yolo(str(model_path))
    else:
        print(f"⚠️  Model not found: {args.model}")
        print("   Using YOLOv8n base (not trained for polyps)")
        print("   Train first: python realtime/train_yolo.py")
        detector.load_default_yolo()

    # Start web viewer if requested
    if args.web_viewer:
        streamer = WebRTCStreamer(detector, port=args.port)
        # Run web viewer in background thread
        import threading
        web_thread = threading.Thread(target=streamer.start, daemon=True)
        web_thread.start()

    # Run detection
    detector.run(
        source=args.source,
        display=not args.no_display,
        record=bool(args.record),
        output_video=args.record or "output.mp4",
    )


if __name__ == "__main__":
    main()
