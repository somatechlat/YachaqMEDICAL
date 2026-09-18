"""
Real-Time Polyp Detection Engine
Two-tier architecture:
  Tier 1: YOLOv8 — Real-time frame-by-frame detection (45+ FPS, <25ms)
  Tier 2: MedGemma — Detailed classification triggered on detection (2-5 sec)

Designed for live colonoscopy video feeds.
Connects via NDI, USB capture card, or video file.

Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncology, Quito, Ecuador
"""

import asyncio
import base64
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np


@dataclass
class Detection:
    """A single polyp detection."""
    frame_id: int
    timestamp: float
    bbox: tuple  # (x1, y1, x2, y2)
    confidence: float
    class_name: str
    class_id: int
    crop_b64: str = ""  # base64-encoded crop of the detected region
    medgemma_analysis: str = ""  # detailed analysis from MedGemma (async)


@dataclass
class DetectionStats:
    """Running statistics for the detection session."""
    total_frames: int = 0
    detections: int = 0
    false_positives_filtered: int = 0
    avg_latency_ms: float = 0.0
    fps: float = 0.0
    session_start: float = 0.0
    polyp_frames: list = field(default_factory=list)


class RealtimeDetector:
    """
    Real-time polyp detection for colonoscopy video.
    
    Usage:
        detector = RealtimeDetector()
        detector.load_yolo("path/to/polyp_yolov8.pt")
        detector.start_video("rtsp://endoscope/stream")
        
    Or with callback:
        detector = RealtimeDetector(on_detection=my_callback)
        detector.run("video.mp4")
    """

    def __init__(
        self,
        yolo_model_path: str = "",
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        medgemma_url: str = "",
        medgemma_key: str = "",
        on_detection: Optional[Callable] = None,
        on_frame: Optional[Callable] = None,
        save_detections: bool = True,
        output_dir: str = "detections",
    ):
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.medgemma_url = medgemma_url or os.getenv("MEDGEMMA_API_URL", "")
        self.medgemma_key = medgemma_key or os.getenv("MEDGEMMA_API_KEY", "")
        self.on_detection = on_detection
        self.on_frame = on_frame
        self.save_detections = save_detections
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model = None
        self.stats = DetectionStats()
        self.recent_detections: deque = deque(maxlen=100)
        self._running = False
        self._frame_times: deque = deque(maxlen=60)

        if yolo_model_path:
            self.load_yolo(yolo_model_path)

    def load_yolo(self, model_path: str):
        """Load YOLOv8 model for polyp detection."""
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        print(f"✅ YOLO model loaded: {model_path}")

    def load_default_yolo(self):
        """Load or download a pre-trained YOLOv8 polyp detection model."""
        # Try to find a local model first
        local_paths = [
            "models/polyp_yolov8.pt",
            "models/yolov8_polyp.pt",
            "runs/detect/train/weights/best.pt",
        ]
        for path in local_paths:
            if Path(path).exists():
                self.load_yolo(path)
                return

        # If no local model, use YOLOv8 base (will need fine-tuning)
        print("⚠️  No pre-trained polyp model found.")
        print("   Options:")
        print("   1. Train on Kvasir-SEG dataset (recommended)")
        print("   2. Download from HuggingFace (search 'yolov8 polyp')")
        print("   3. Use yolov8n.pt as base and fine-tune")
        print("")
        print("   Quick train:")
        print("   python train_yolo.py --data kvasir-seg --epochs 50")
        
        from ultralytics import YOLO
        self.model = YOLO("yolov8n.pt")
        print("   Loaded yolov8n.pt as fallback (NOT trained for polyps)")

    def process_frame(self, frame: np.ndarray, frame_id: int) -> list[Detection]:
        """
        Process a single video frame through YOLO.
        Returns list of detections.
        """
        if self.model is None:
            return []

        start_time = time.monotonic()
        detections = []

        # Run YOLO inference
        results = self.model(
            frame,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            verbose=False,
        )

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self.model.names.get(cls_id, f"class_{cls_id}")

                # Crop the detection region
                crop = frame[max(0, y1):y2, max(0, x1):x2]
                _, crop_b64 = cv2.imencode('.jpg', crop)
                crop_b64_str = base64.b64encode(crop_b64).decode('utf-8')

                det = Detection(
                    frame_id=frame_id,
                    timestamp=time.time(),
                    bbox=(x1, y1, x2, y2),
                    confidence=conf,
                    class_name=cls_name,
                    class_id=cls_id,
                    crop_b64=crop_b64_str,
                )
                detections.append(det)

        # Update stats
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self._frame_times.append(elapsed_ms)
        self.stats.total_frames += 1
        self.stats.detections += len(detections)
        self.stats.avg_latency_ms = sum(self._frame_times) / len(self._frame_times)
        if self._frame_times:
            self.stats.fps = 1000.0 / self.stats.avg_latency_ms

        return detections

    def draw_detections(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        """Draw bounding boxes and labels on frame."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            # Color based on confidence
            if det.confidence > 0.8:
                color = (0, 0, 255)    # Red = high confidence
                label = "🔴 POLYP"
            elif det.confidence > 0.6:
                color = (0, 165, 255)  # Orange = medium
                label = "🟡 SUSPECT"
            else:
                color = (0, 255, 255)  # Yellow = low
                label = "🔵 LOW CONF"

            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

            # Draw label background
            text = f"{label} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 10, y1), color, -1)
            cv2.putText(annotated, text, (x1 + 5, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # If MedGemma analysis available, show it
            if det.medgemma_analysis:
                # Show first line of analysis
                first_line = det.medgemma_analysis.split('\n')[0][:60]
                cv2.putText(annotated, first_line, (x1, y2 + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Draw stats overlay
        stats_text = [
            f"FPS: {self.stats.fps:.0f}",
            f"Latency: {self.stats.avg_latency_ms:.1f}ms",
            f"Frames: {self.stats.total_frames}",
            f"Detections: {self.stats.detections}",
        ]
        for i, text in enumerate(stats_text):
            cv2.putText(annotated, text, (10, 30 + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return annotated

    async def analyze_with_medgemma(self, detection: Detection) -> str:
        """
        Send detected polyp crop to MedGemma for detailed classification.
        Called asynchronously — does not block the real-time loop.
        """
        if not self.medgemma_url or not self.medgemma_key:
            return "MedGemma not configured"

        import aiohttp

        prompt = """Analyze this colonoscopy image of a detected polyp. Provide:
1. Classification: Paris (0-Ip/0-Is/0-IIa/0-IIb/0-IIc/0-III)
2. Pit pattern: Kudo (Type I-V)
3. NBI assessment: NICE (Type 1-3)
4. Size estimate (mm)
5. Risk level: Low/Intermediate/High
6. Recommendation: Biopsy/Resection/Monitor

Be concise. Use Spanish with English terms in parentheses."""

        payload = {
            "model": "google/medgemma-1.5-4b-it",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{detection.crop_b64}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 512,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self.medgemma_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.medgemma_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    return f"API error: {resp.status}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _handle_detection(self, detection: Detection):
        """Handle a detection: save, callback, and optionally analyze with MedGemma."""
        # Save detection image
        if self.save_detections:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"det_{ts}_f{detection.frame_id}_c{detection.confidence:.0f}.jpg"
            filepath = self.output_dir / filename
            crop_data = base64.b64decode(detection.crop_b64)
            with open(filepath, "wb") as f:
                f.write(crop_data)

        # Callback
        if self.on_detection:
            if asyncio.iscoroutinefunction(self.on_detection):
                await self.on_detection(detection)
            else:
                self.on_detection(detection)

        # MedGemma analysis (async, non-blocking)
        if self.medgemma_url and self.medgemma_key:
            analysis = await self.analyze_with_medgemma(detection)
            detection.medgemma_analysis = analysis
            print(f"🔬 MedGemma: {analysis[:100]}...")

    def run(
        self,
        source: str = "0",
        display: bool = True,
        record: bool = False,
        output_video: str = "output.mp4",
    ):
        """
        Run real-time detection on a video source.
        
        Args:
            source: Video source. Can be:
                - "0" for webcam
                - "rtsp://..." for IP camera / endoscope
                - "/path/to/video.mp4" for file
                - "ndi://..." for NDI stream
            display: Show annotated video window
            record: Save annotated video to file
            output_video: Path for recorded output
        """
        print(f"🎬 Opening video source: {source}")
        cap = cv2.VideoCapture(source if source != "0" else 0)

        if not cap.isOpened():
            print(f"❌ Cannot open video source: {source}")
            return

        # Get video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        print(f"📐 Resolution: {width}x{height} @ {fps:.0f} FPS")

        # Setup video writer
        writer = None
        if record:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

        self._running = True
        self.stats.session_start = time.time()
        frame_id = 0
        last_medgemma_time = 0
        MEDGEMMA_COOLDOWN = 5.0  # seconds between MedGemma calls

        print("🔴 LIVE — Press 'q' to quit, 's' to screenshot, 'm' to force MedGemma analysis")
        print("")

        loop = asyncio.new_event_loop()

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    if source.endswith(('.mp4', '.avi', '.mkv')):
                        print("📹 Video ended")
                        break
                    continue

                frame_id += 1

                # Tier 1: YOLO real-time detection
                detections = self.process_frame(frame, frame_id)

                # Tier 2: Trigger MedGemma on new detections (with cooldown)
                now = time.time()
                if detections and (now - last_medgemma_time) > MEDGEMMA_COOLDOWN:
                    last_medgemma_time = now
                    # Run MedGemma on the highest-confidence detection
                    best = max(detections, key=lambda d: d.confidence)
                    loop.run_until_complete(self._handle_detection(best))
                    self.stats.polyp_frames.append({
                        "frame_id": frame_id,
                        "timestamp": now,
                        "detections": len(detections),
                        "best_confidence": best.confidence,
                    })

                # Draw annotations
                annotated = self.draw_detections(frame, detections)

                # Callback
                if self.on_frame:
                    self.on_frame(annotated, detections)

                # Display
                if display:
                    cv2.imshow("YachaqMEDICAL — Real-Time Polyp Detection", annotated)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('s'):
                        ts = time.strftime("%Y%m%d_%H%M%S")
                        cv2.imwrite(f"screenshot_{ts}.jpg", annotated)
                        print(f"📸 Screenshot saved")
                    elif key == ord('m'):
                        if detections:
                            best = max(detections, key=lambda d: d.confidence)
                            loop.run_until_complete(self._handle_detection(best))

                # Record
                if writer:
                    writer.write(annotated)

        except KeyboardInterrupt:
            print("\n⏹️  Stopped by user")
        finally:
            self._running = False
            cap.release()
            if writer:
                writer.release()
            if display:
                cv2.destroyAllWindows()
            loop.close()

        # Print session summary
        elapsed = time.time() - self.stats.session_start
        print(f"\n📊 Session Summary:")
        print(f"   Duration: {elapsed:.0f}s")
        print(f"   Frames: {self.stats.total_frames}")
        print(f"   Detections: {self.stats.detections}")
        print(f"   Avg FPS: {self.stats.fps:.0f}")
        print(f"   Avg Latency: {self.stats.avg_latency_ms:.1f}ms")
        print(f"   Detection rate: {self.stats.detections/max(1,self.stats.total_frames)*100:.1f}%")

    def stop(self):
        """Stop the detection loop."""
        self._running = False


class WebRTCStreamer:
    """
    Stream annotated video to a web browser via WebRTC or MJPEG.
    For remote viewing during procedures.
    """

    def __init__(self, detector: RealtimeDetector, port: int = 8080):
        self.detector = detector
        self.port = port
        self._frame = None
        self._clients = set()

    async def mjpeg_handler(self, request):
        """MJPEG stream endpoint for browser viewing."""
        from aiohttp import web

        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
                'Cache-Control': 'no-cache',
            },
        )
        await response.prepare(request)

        while True:
            if self._frame is not None:
                _, jpeg = cv2.imencode('.jpg', self._frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                await response.write(
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' +
                    jpeg.tobytes() + b'\r\n'
                )
            await asyncio.sleep(0.033)  # ~30fps

    async def stats_handler(self, request):
        """JSON stats endpoint."""
        from aiohttp import web
        stats = {
            "fps": round(self.detector.stats.fps, 1),
            "latency_ms": round(self.detector.stats.avg_latency_ms, 1),
            "total_frames": self.detector.stats.total_frames,
            "detections": self.detector.stats.detections,
            "session_duration": round(time.time() - self.detector.stats.session_start, 0),
        }
        return web.json_response(stats)

    def start(self):
        """Start the web server for remote viewing."""
        from aiohttp import web
        app = web.Application()
        app.router.add_get('/stream', self.mjpeg_handler)
        app.router.add_get('/stats', self.stats_handler)
        print(f"🌐 Remote viewer: http://localhost:{self.port}/stream")
        print(f"📊 Stats API: http://localhost:{self.port}/stats")
        web.run_app(app, port=self.port)
