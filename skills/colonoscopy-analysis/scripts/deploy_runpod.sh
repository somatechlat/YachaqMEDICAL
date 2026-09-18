#!/bin/bash
# RunPod Serverless Deployment Script for MedGemma 1.5 4B
# Deploys MedGemma as an OpenAI-compatible API endpoint on RunPod Serverless
#
# Prerequisites:
# 1. RunPod account with credits (https://www.runpod.io)
# 2. Hugging Face account with access token (https://huggingface.co/settings/tokens)
# 3. RunPod CLI installed (pip install runpod)
#
# Usage:
#   chmod +x deploy_runpod.sh
#   ./deploy_runpod.sh
#
# After deployment, set these environment variables:
#   export MEDGEMMA_API_URL="https://api.runpod.ai/v2/YOUR_ENDPOINT_ID"
#   export MEDGEMMA_API_KEY="YOUR_RUNPOD_API_KEY"

set -e

echo "=========================================="
echo "  MedGemma RunPod Serverless Deployment"
echo "  For Dr. Jaime Andrés Benítez Kellendonk"
echo "=========================================="
echo ""

# Check prerequisites
if ! command -v runpod &> /dev/null; then
    echo "Installing RunPod CLI..."
    pip install runpod
fi

# Prompt for credentials
read -p "RunPod API Key: " RUNPOD_API_KEY
read -p "Hugging Face Token: " HF_TOKEN

echo ""
echo "Creating RunPod Serverless Endpoint..."
echo ""

# Create the endpoint configuration
cat > /tmp/medgemma_endpoint.yaml << 'EOF'
# RunPod Serverless Endpoint Configuration for MedGemma 1.5 4B
name: medgemma-medical-imaging
imageName: runpod/vllm-openai:latest
gpuIds: "NVIDIA RTX 4090"  # or "NVIDIA A100 80GB" for production
gpuCount: 1
vcpuCount: 8
containerDiskInGb: 50
volumeInGb: 0
env:
  - key: MODEL_NAME
    value: "google/medgemma-1.5-4b-it"
  - key: HF_TOKEN
    value: "__HF_TOKEN__"
  - key: MAX_MODEL_LEN
    value: "4096"
  - key: GPU_MEMORY_UTILIZATION
    value: "0.9"
  - key: DTYPE
    value: "auto"
  - key: TRUST_REMOTE_CODE
    value: "true"
  - key: MAX_NUM_SEQS
    value: "4"
scalerConfig:
  type: QUEUE_DELAY
  workersMin: 0
  workersMax: 3
  queueDelay: 5
EOF

echo "Endpoint configuration created."
echo ""
echo "To deploy:"
echo "1. Go to https://www.runpod.io/console/serverless"
echo "2. Click 'New Endpoint'"
echo "3. Select 'vLLM OpenAI' template"
echo "4. Set model: google/medgemma-1.5-4b-it"
echo "5. Set GPU: RTX 4090 (for testing) or A100 80GB (for production)"
echo "6. Add environment variable: HF_TOKEN = your Hugging Face token"
echo "7. Set workers: 0-3 (scales to zero when idle)"
echo "8. Click 'Deploy'"
echo ""
echo "After deployment, set these environment variables for Agent Zero:"
echo ""
echo "  export MEDGEMMA_API_URL=\"https://api.runpod.ai/v2/YOUR_ENDPOINT_ID\""
echo "  export MEDGEMMA_API_KEY=\"$RUNPOD_API_KEY\""
echo ""
echo "Add these to your Agent Zero .env file or Docker environment."
echo ""
echo "=========================================="
echo "  Deployment Guide Complete"
echo "=========================================="
