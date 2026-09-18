#!/usr/bin/env bash
# YachaqMEDICAL — Complete Setup Script
# Sets up everything: environment, datasets, models, and services
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./setup.sh                    # Full setup
#   ./setup.sh --minimal          # Just the basics
#   ./setup.sh --gpu-only         # GPU/CUDA setup only
#   ./setup.sh --dataset-only     # Download datasets only

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_ok() { echo -e "${GREEN}✅ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_err() { echo -e "${RED}❌ $1${NC}"; }
print_step() { echo -e "${BLUE}▶ $1${NC}"; }

# ─── Parse args ────────────────────────────────────────────
MINIMAL=false
GPU_ONLY=false
DATASET_ONLY=false

for arg in "$@"; do
    case $arg in
        --minimal) MINIMAL=true ;;
        --gpu-only) GPU_ONLY=true ;;
        --dataset-only) DATASET_ONLY=true ;;
    esac
done

# ─── System check ──────────────────────────────────────────
print_header "YachaqMEDICAL Setup"
echo "  Dr. Jaime Andrés Benítez Kellendonk"
echo "  Surgical Oncology — Quito, Ecuador"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    print_err "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
print_ok "Python $PYTHON_VERSION"

# Check pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    print_err "pip not found. Install pip first."
    exit 1
fi
PIP=$(command -v pip3 || command -v pip)
print_ok "pip found: $PIP"

# ─── GPU Detection ─────────────────────────────────────────
print_step "Checking GPU..."

GPU_AVAILABLE=false
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        GPU_AVAILABLE=true
        print_ok "GPU detected: $GPU_INFO"
    fi
fi

if [ "$GPU_AVAILABLE" = false ]; then
    print_warn "No GPU detected. CPU mode will be slower."
    echo "  Options:"
    echo "    1. Install CUDA: https://developer.nvidia.com/cuda-downloads"
    echo "    2. Use RunPod serverless (recommended): https://www.runpod.io"
    echo "    3. Use Google Colab (free GPU)"
fi

if [ "$GPU_ONLY" = true ]; then
    exit 0
fi

# ─── Virtual Environment ───────────────────────────────────
print_step "Creating virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_ok "Virtual environment created"
else
    print_ok "Virtual environment exists"
fi

source venv/bin/activate || . venv/Scripts/activate 2>/dev/null
print_ok "Activated venv"

# ─── Install Dependencies ──────────────────────────────────
print_step "Installing dependencies..."

$PIP install --upgrade pip > /dev/null 2>&1

# Core dependencies
$PIP install ultralytics opencv-python numpy aiohttp aiofiles > /dev/null 2>&1
print_ok "Core dependencies installed"

# Dataset/training dependencies
if [ "$MINIMAL" = false ]; then
    $PIP install datasets scikit-learn Pillow matplotlib > /dev/null 2>&1
    print_ok "Training dependencies installed"
fi

# Web viewer
if [ "$MINIMAL" = false ]; then
    $PIP install aiohttp > /dev/null 2>&1
    print_ok "Web viewer dependencies installed"
fi

if [ "$DATASET_ONLY" = true ]; then
    # Skip to dataset download
    true
else
    # ─── Verify Installation ──────────────────────────────────
    print_step "Verifying installation..."

    python3 -c "
import cv2
import numpy as np
from ultralytics import YOLO
print('  OpenCV:', cv2.__version__)
print('  NumPy:', np.__version__)
print('  Ultralytics: OK')
" 2>/dev/null && print_ok "All imports verified" || print_warn "Some imports failed"

fi

# ─── Download Datasets ─────────────────────────────────────
print_step "Downloading datasets..."

DATASET_DIR="datasets"
mkdir -p "$DATASET_DIR"

# Kvasir-VQA-x1 from HuggingFace
if [ ! -d "$DATASET_DIR/kvasir-vqa" ]; then
    print_step "Downloading Kvasir-VQA-x1 (this may take a few minutes)..."
    python3 -c "
from datasets import load_dataset
import os
ds = load_dataset('SimulaMet/Kvasir-VQA-x1', split='train', trust_remote_code=True)
os.makedirs('$DATASET_DIR/kvasir-vqa/images', exist_ok=True)
count = 0
for i, item in enumerate(ds):
    if i >= 500: break
    img = item.get('image')
    if img:
        img.save(f'$DATASET_DIR/kvasir-vqa/images/kvasir_{i:04d}.jpg')
        count += 1
print(f'  Downloaded {count} images')
" 2>/dev/null && print_ok "Kvasir-VQA downloaded" || print_warn "Kvasir-VQA download failed (try manually)"
else
    print_ok "Kvasir-VQA exists"
fi

# ─── Create Project Structure ──────────────────────────────
print_step "Creating project structure..."

mkdir -p models detections runs/detect benchmarks/results
print_ok "Project structure created"

# ─── Environment File ──────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || cat > .env << 'EOF'
# YachaqMEDICAL Configuration
# Fill in your values:

# RunPod Serverless GPU (for MedGemma)
MEDGEMMA_API_URL=https://api.runpod.ai/v2/YOUR_ENDPOINT_ID
MEDGEMMA_API_KEY=***

# Hugging Face (for model download)
HF_TOKEN=***
EOF
    print_ok "Created .env file — EDIT THIS with your credentials"
else
    print_ok ".env exists"
fi

# ─── Done ──────────────────────────────────────────────────
print_header "Setup Complete!"
echo "  Next steps:"
echo ""
echo "  1. Edit .env with your RunPod credentials"
echo ""
echo "  2. Train YOLO model (takes ~30 min with GPU):"
echo "     python realtime/train_yolo.py --epochs 50"
echo ""
echo "  3. Run benchmarks:"
echo "     python benchmarks/benchmark_suite.py --model models/polyp_yolov8.pt --dataset datasets/kvasir-vqa"
echo ""
echo "  4. Run real-time detection:"
echo "     python realtime/run_realtime.py --source 0 --medgemma"
echo ""
echo "  5. Or use Agent Zero with the medical-imaging profile"
echo ""
echo "  📖 Read docs/COST-AND-BENCHMARKS.md for cost details"
echo "  📖 Read docs/SETUP-GUIDE.md for full instructions"
echo ""
