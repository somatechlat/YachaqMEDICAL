# YachaqMEDICAL

**AI-Powered Medical Imaging Assistant for Surgical Oncology**

Built for Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncologist, Quito, Ecuador

## What Is This

An AI agent that analyzes medical images (colonoscopy, endoscopy, histopathology) using Google's MedGemma model, deployed on serverless GPU infrastructure. Integrates with Agent Zero for the conversational interface.

## Capabilities

| Feature | Description |
|---|---|
| **Polyp Detection** | Detect polyps in colonoscopy images |
| **Polyp Classification** | Paris, Kudo pit pattern, NICE classification |
| **Cancer Screening** | Colorectal cancer risk stratification |
| **Margin Assessment** | Surgical margin evaluation |
| **Histopathology** | Tissue sample analysis support |
| **Clinical Reports** | Structured reports in Spanish (ASGE standards) |

## Real-Time System (NEW)

Analyze colonoscopy video **LIVE during the procedure**.

```bash
# Install dependencies
pip install -r realtime/requirements.txt

# Train YOLO on Kvasir-SEG dataset (one-time)
python realtime/train_yolo.py --epochs 50

# Run real-time detection from endoscope stream
python realtime/run_realtime.py --source rtsp://192.168.1.100/stream --medgemma

# Or from webcam for testing
python realtime/run_realtime.py --source 0

# With remote web viewer (for other doctors to watch)
python realtime/run_realtime.py --source 0 --web-viewer --port 8080
```

**Architecture:**
- **Tier 1 (YOLOv8):** Real-time polyp detection at 45+ FPS, <25ms latency
- **Tier 2 (MedGemma):** Detailed classification triggered on detection (Paris/Kudo/NICE)
- **Web Viewer:** Remote monitoring via browser (MJPEG stream)

## Quick Start

### 1. Deploy MedGemma on RunPod

1. Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
2. Create endpoint with **vLLM OpenAI** template
3. Model: `google/medgemma-1.5-4b-it`
4. GPU: RTX 4090 (testing) or A100 80GB (production)
5. Workers: 0-3 (scales to zero when idle)
6. Add env var: `HF_TOKEN` = your Hugging Face token

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your RunPod endpoint and API key
```

### 3. Use with Agent Zero

Copy the `agents/`, `tools/`, and `skills/` directories into your Agent Zero installation:

```bash
cp -r agents/ /path/to/agent-zero/agents/
cp -r tools/ /path/to/agent-zero/tools/
cp -r skills/ /path/to/agent-zero/skills/
```

Start Agent Zero and select the **"Medical Imaging Assistant"** profile.

### 4. Standalone Usage (No Agent Zero)

```bash
cd skills/colonoscopy-analysis/scripts/
export MEDGEMMA_API_URL="https://api.runpod.ai/v2/YOUR_ID"
export MEDGEMMA_API_KEY="***"

python analyze_endoscopy.py \
  --image /path/to/colonoscopy.jpg \
  --type polyp_detection \
  --lang spanish
```

## Project Structure

```
YachaqMEDICAL/
├── realtime/                              # 🔴 REAL-TIME SYSTEM
│   ├── detector.py                        # Two-tier detection engine (YOLO + MedGemma)
│   ├── train_yolo.py                      # Train YOLO on Kvasir-SEG dataset
│   ├── run_realtime.py                    # Main entry point for live detection
│   └── requirements.txt                   # Dependencies
├── agents/medical-imaging/                # Agent Zero integration
│   ├── agent.yaml
│   └── prompts/
├── tools/                                 # Agent Zero tools
│   ├── medical_image_analyze.py           # MedGemma inference
│   └── medical_report_generate.py         # Clinical reports
├── skills/colonoscopy-analysis/           # Workflow skill
│   ├── SKILL.md
│   ├── Dockerfile.runpod
│   └── scripts/
├── docs/                                  # Documentation
│   ├── agent-zero-medical-imaging-report.md
│   └── COST-AND-BENCHMARKS.md
├── .env.example
└── README.md
```

## Clinical Standards

- **Paris Classification** — Polyp morphology (0-Ip, 0-Is, 0-IIa, 0-IIb, 0-IIc, 0-III)
- **Kudo Pit Pattern** — Crypt pattern analysis (Type I-V)
- **NICE Classification** — NBI vascular assessment (Type 1-3)
- **ASGE Guidelines** — Reporting and surveillance recommendations
- **ESGE Guidelines** — Cancer screening protocols

## Cost

| Scenario | GPU | Cost per Image | Notes |
|---|---|---|---|
| Testing | RTX 4090 | ~$0.01 | Scales to zero |
| Production | A100 80GB | ~$0.03 | Faster inference |

## Disclaimer

This system is a clinical decision-support tool. It does NOT replace medical judgment. All findings must be verified by the attending physician. Not a diagnostic device.

## Credits

- **Physician:** Dr. Jaime Andrés Benítez Kellendonk — Cirugía Oncológica, Quito, Ecuador
- **Medical Model:** MedGemma 1.5 4B (Google Health AI Developer Foundations)
- **Agent Framework:** Agent Zero (agent0ai/agent-zero)
- **Inference:** RunPod Serverless GPU
