# YachaqMEDICAL — Complete Setup & Run Guide
## Expert System Design for Dr. Jaime Andrés Benítez Kellendonk

---

## WHERE TO RUN IT

### Option A: Your Own Machine (Testing/Development)

**Requirements:**
- **OS:** Linux (Ubuntu 22.04+), macOS, or Windows (WSL2)
- **RAM:** 8GB minimum, 16GB recommended
- **GPU:** NVIDIA GPU with 6GB+ VRAM (RTX 3060 or better)
  - No GPU? Use RunPod cloud (see Option B)
- **Disk:** 20GB free space
- **Python:** 3.10 or newer

**Setup:**
```bash
# Clone the repo
git clone https://github.com/somatechlat/YachaqMEDICAL.git
cd YachaqMEDICAL

# Run the setup script
chmod +x scripts/setup.sh
./setup.sh

# Edit .env with your credentials
nano .env

# Activate environment
source venv/bin/activate

# Train the model
python realtime/train_yolo.py --epochs 50

# Run real-time detection
python realtime/run_realtime.py --source 0
```

### Option B: RunPod Cloud (No GPU Needed Locally)

**This is what you should use for demos and production.**

1. **Create RunPod account:** https://www.runpod.io
2. **Add $10 credits** (lasts months)
3. **Deploy MedGemma:**
   - Go to Serverless → New Endpoint
   - Template: "vLLM OpenAI"
   - Model: `google/medgemma-1.5-4b-it`
   - GPU: RTX 4090 ($1.10/hr, scales to zero)
   - Workers: 0-3
   - Env: `HF_TOKEN` = your HuggingFace token
4. **Copy endpoint URL and API key**
5. **Set in .env:**
   ```
   MEDGEMMA_API_URL=https://api.runpod.ai/v2/YOUR_ID
   MEDGEMMA_API_KEY=***
   ```

### Option C: VPS + RunPod (Production)

**Best for clinic deployment:**
- **VPS:** DigitalOcean/Hetzner ($6/month, 4GB RAM, 2 vCPU)
  - Runs Agent Zero + WebUI + Web Viewer
  - No GPU needed on VPS
- **RunPod:** MedGemma inference ($0.001/image)
- **YOLO:** Runs on CPU on VPS (YOLOv8n is fast enough)

```bash
# On VPS
git clone https://github.com/somatechlat/YachaqMEDICAL.git
cd YachaqMEDICAL
./setup.sh
source venv/bin/activate

# Start the web viewer (doctors access via browser)
python realtime/run_realtime.py --source rtsp://endoscope/stream \
    --medgemma --web-viewer --port 8080 --no-display
```

---

## HOW TO RUN IT

### 1. First-Time Setup (Do This Once)

```bash
cd YachaqMEDICAL
source venv/bin/activate

# Step 1: Download dataset
python realtime/train_yolo.py --download-only

# Step 2: Train YOLO model (30 min with GPU, 2-4 hours on CPU)
python realtime/train_yolo.py --epochs 50 --model n

# Step 3: Run benchmarks to verify
python benchmarks/benchmark_suite.py \
    --model models/polyp_yolov8.pt \
    --dataset datasets/kvasir-vqa
```

### 2. Running Real-Time Detection

**From webcam (testing):**
```bash
python realtime/run_realtime.py --source 0 --model models/polyp_yolov8.pt
```

**From endoscope stream:**
```bash
# RTSP stream (most endoscopes)
python realtime/run_realtime.py --source rtsp://192.168.1.100/stream

# USB capture card
python realtime/run_realtime.py --source /dev/video0

# HDMI capture (via NDI)
python realtime/run_realtime.py --source ndi://endoscope
```

**With MedGemma detailed analysis:**
```bash
export MEDGEMMA_API_URL="https://api.runpod.ai/v2/YOUR_ID"
export MEDGEMMA_API_KEY="***"
python realtime/run_realtime.py --source 0 --medgemma
```

**With web viewer (remote monitoring):**
```bash
python realtime/run_realtime.py --source 0 --web-viewer --port 8080
# Open http://localhost:8080/stream in any browser
```

**Record annotated video:**
```bash
python realtime/run_realtime.py --source procedure.mp4 --record annotated_output.mp4
```

### 3. Running Benchmarks

**Single model:**
```bash
python benchmarks/benchmark_suite.py \
    --model models/polyp_yolov8.pt \
    --dataset datasets/kvasir-vqa \
    --output results/benchmark.json
```

**Compare models:**
```bash
python benchmarks/benchmark_suite.py \
    --compare models/polyp_yolov8.pt models/yolov8s_polyp.pt \
    --dataset datasets/kvasir-vqa
```

**Custom confidence/IoU thresholds:**
```bash
python benchmarks/benchmark_suite.py \
    --model models/polyp_yolov8.pt \
    --dataset datasets/kvasir-vqa \
    --conf 0.3 --iou 0.6
```

### 4. Using Agent Zero Integration

```bash
# Copy files to Agent Zero installation
cp -r agents/ /path/to/agent-zero/agents/
cp -r tools/ /path/to/agent-zero/tools/
cp -r skills/ /path/to/agent-zero/skills/

# In Agent Zero WebUI, select "Medical Imaging Assistant" profile
# Upload colonoscopy images → get analysis + reports
```

### 5. Standalone Image Analysis (No Video)

```bash
# Single image analysis
python skills/colonoscopy-analysis/scripts/analyze_endoscopy.py \
    --image path/to/colonoscopy.jpg \
    --type polyp_detection \
    --lang spanish \
    --output results.md
```

---

## BENCHMARK FEATURES (What We Measure)

### Detection Metrics

| Metric | What It Measures | Target | Why It Matters |
|---|---|---|---|
| **Sensitivity (Recall)** | % of real polyps detected | >95% | Missed polyps = missed cancer |
| **Specificity** | % of normal frames correctly identified | >90% | Too many false alarms = wasted time |
| **Precision** | % of detections that are real polyps | >85% | False positives cause unnecessary procedures |
| **F1 Score** | Balance of precision and recall | >90% | Single number for overall quality |
| **mAP@50** | Detection accuracy at IoU 0.5 | >80% | Standard object detection metric |

### Speed Metrics

| Metric | What It Measures | Target | Why It Matters |
|---|---|---|---|
| **FPS** | Frames processed per second | >30 | Real-time requires ≥30 FPS |
| **Latency** | Time per frame in ms | <33ms | Doctor can't wait for analysis |
| **P95 Latency** | 95th percentile latency | <50ms | Worst-case performance |

### Clinical Metrics

| Metric | What It Measures | Target | Why It Matters |
|---|---|---|---|
| **FP/Procedure** | False alarms per colonoscopy | <1.0 | GI Genius achieves 0.3 |
| **Miss Rate** | Polyps completely missed | <5% | Every miss is a potential cancer |
| **Detection Rate** | % of procedures with ≥1 detection | Track | Quality indicator |

### What Gets Benchmarked

```
benchmarks/
├── benchmark_suite.py          # Main benchmark runner
├── results/                    # Saved results (JSON)
│   ├── yolov8n_results.json
│   ├── yolov8s_results.json
│   └── comparison.json
└── datasets/                   # Test datasets
    ├── kvasir-vqa/             # 500 images with Q&A
    ├── kvasir-seg/             # 1000 images with masks
    └── cvc-clinicdb/           # 612 images
```

---

## SYSTEM ARCHITECTURE (Expert Design)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YachaqMEDICAL System                             │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    INPUT LAYER                                   │   │
│  │                                                                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │  │ Webcam   │  │ RTSP     │  │ USB      │  │ Video    │        │   │
│  │  │ (test)   │  │ Stream   │  │ Capture  │  │ File     │        │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │   │
│  │       └──────────────┴──────────────┴──────────────┘             │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼──────────────────────────────────┐   │
│  │                    DETECTION LAYER                               │   │
│  │                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │  TIER 1: YOLOv8 Real-Time Detector                      │    │   │
│  │  │  • 45+ FPS, <25ms per frame                             │    │   │
│  │  │  • Bounding box detection                               │    │   │
│  │  │  • Confidence scoring                                   │    │   │
│  │  │  • Runs locally (no cloud needed)                       │    │   │
│  │  └──────────────────────┬──────────────────────────────────┘    │   │
│  │                         │ polyp detected                         │   │
│  │  ┌──────────────────────▼──────────────────────────────────┐    │   │
│  │  │  TIER 2: MedGemma Detailed Analysis                     │    │   │
│  │  │  • Paris classification (0-Ip, 0-Is, 0-IIa, etc.)      │    │   │
│  │  │  • Kudo pit pattern (Type I-V)                          │    │   │
│  │  │  • NICE classification (Type 1-3)                       │    │   │
│  │  │  • Risk assessment                                      │    │   │
│  │  │  • Runs on RunPod (cloud GPU)                           │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼──────────────────────────────────┐   │
│  │                    OUTPUT LAYER                                  │   │
│  │                                                                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │  │ Annotated│  │ Web      │  │ Clinical │  │ Detection│        │   │
│  │  │ Video    │  │ Viewer   │  │ Reports  │  │ Crops    │        │   │
│  │  │ (screen) │  │ (browser)│  │ (Spanish)│  │ (saved)  │        │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    BENCHMARK LAYER                               │   │
│  │                                                                  │   │
│  │  • Sensitivity/Specificity/Precision/F1                         │   │
│  │  • FPS and latency tracking                                     │   │
│  │  • mAP@50 and mAP@50:95                                         │   │
│  │  • False positives per procedure                                │   │
│  │  • Comparison with GI Genius, CAD-EYE, EndoAID                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## FILE STRUCTURE

```
YachaqMEDICAL/
│
├── 📁 realtime/                    # REAL-TIME DETECTION SYSTEM
│   ├── detector.py                 # Two-tier detection engine
│   ├── train_yolo.py              # YOLO training pipeline
│   ├── run_realtime.py            # CLI entry point
│   └── requirements.txt           # Dependencies
│
├── 📁 agents/medical-imaging/      # AGENT ZERO INTEGRATION
│   ├── agent.yaml                  # Profile config
│   └── prompts/                    # System prompts
│
├── 📁 tools/                       # AGENT ZERO TOOLS
│   ├── medical_image_analyze.py    # MedGemma inference
│   └── medical_report_generate.py  # Clinical reports
│
├── 📁 skills/colonoscopy-analysis/ # WORKFLOW SKILL
│   ├── SKILL.md                    # Usage guide
│   ├── Dockerfile.runpod           # RunPod deployment
│   └── scripts/                    # Standalone scripts
│
├── 📁 benchmarks/                  # BENCHMARK SUITE
│   ├── benchmark_suite.py          # Full benchmark runner
│   └── results/                    # Saved results
│
├── 📁 scripts/                     # SETUP & UTILITIES
│   └── setup.sh                    # One-command setup
│
├── 📁 docs/                        # DOCUMENTATION
│   ├── SETUP-GUIDE.md              # This file
│   ├── COST-AND-BENCHMARKS.md      # Cost analysis
│   └── agent-zero-medical-imaging-report.md
│
├── 📁 models/                      # TRAINED MODELS
│   └── polyp_yolov8.pt            # (after training)
│
├── 📁 detections/                  # SAVED DETECTIONS
│   └── det_20260919_*.jpg          # (auto-generated)
│
├── .env.example                    # Environment template
├── .env                            # Your credentials (git-ignored)
├── .gitignore
└── README.md
```

---

## QUICK REFERENCE

| Task | Command |
|---|---|
| **Setup everything** | `./scripts/setup.sh` |
| **Train YOLO** | `python realtime/train_yolo.py --epochs 50` |
| **Run detection (webcam)** | `python realtime/run_realtime.py --source 0` |
| **Run detection (endoscope)** | `python realtime/run_realtime.py --source rtsp://...` |
| **With MedGemma** | `python realtime/run_realtime.py --source 0 --medgemma` |
| **Web viewer** | `python realtime/run_realtime.py --source 0 --web-viewer` |
| **Benchmark** | `python benchmarks/benchmark_suite.py --model models/polyp_yolov8.pt` |
| **Compare models** | `python benchmarks/benchmark_suite.py --compare model1.pt model2.pt` |
| **Analyze single image** | `python skills/.../analyze_endoscopy.py --image photo.jpg` |
| **Generate report** | Use Agent Zero with medical-imaging profile |

---

*Setup guide for YachaqMEDICAL — AI Medical Imaging for Surgical Oncology*
*Dr. Jaime Andrés Benítez Kellendonk — Quito, Ecuador*
