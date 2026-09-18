#!/usr/bin/env python3
"""
Standalone endoscopy analysis script.
Can be used outside Agent Zero for direct MedGemma inference.

Usage:
    python analyze_endoscopy.py --image /path/to/image.jpg --type polyp_detection
    python analyze_endoscopy.py --image /path/to/image.jpg --type polyp_classification --lang spanish
    python analyze_endoscopy.py --image /path/to/image.jpg --type cancer_screening --query "Is this lesion suspicious?"

Requires:
    - MEDGEMMA_API_URL environment variable (RunPod endpoint)
    - MEDGEMMA_API_KEY environment variable (RunPod API key)
    - pip install aiohttp aiofiles
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path


ANALYSIS_PROMPTS = {
    "polyp_detection": """You are an expert gastroenterology AI analyzing a colonoscopy image.
Analyze this endoscopic image and provide:
1. POLYP DETECTION: Is a polyp visible? (Yes/No/Uncertain)
2. LOCATION ESTIMATE: Where in the colon is it located?
3. MORPHOLOGY: Shape, size estimate (mm), surface characteristics
4. COLOR: Normal mucosa, erythematous, pale, discolored?
5. VASCULAR PATTERN: NBI assessment if applicable
6. RECOMMENDATION: Biopsy, resection, or monitoring?
Respond in structured format.""",

    "polyp_classification": """Classify this polyp using international standards:
- PARIS: 0-Ip/0-Is/0-IIa/0-IIb/0-IIc/0-III
- KUDO: Type I-V
- NICE: Type 1-3
Provide classification with confidence level for each system.""",

    "cancer_screening": """Assess colorectal cancer risk:
1. LESION ASSESSMENT
2. RISK: Low/Intermediate/High
3. SURVEILLANCE RECOMMENDATION
4. RED FLAGS for malignancy
Use ESGE guidelines.""",

    "margin_assessment": """Evaluate surgical margins:
1. TISSUE IDENTIFICATION
2. MARGIN STATUS: Clear/Close/Involved
3. TUMOR PROXIMITY
4. TISSUE CHARACTERISTICS
5. RECOMMENDATION""",

    "histopathology": """Analyze this tissue sample:
1. TISSUE TYPE
2. ARCHITECTURE: Normal/Dysplastic/Neoplastic
3. CELLULAR FEATURES
4. GRADING if neoplastic
5. DIFFERENTIAL DIAGNOSIS""",

    "general_imaging": """Analyze this medical image:
1. IMAGE TYPE
2. FINDINGS
3. NORMAL vs ABNORMAL
4. DIFFERENTIAL DIAGNOSIS
5. RECOMMENDATION""",
}


async def call_medgemma(image_path: str, prompt: str) -> str:
    """Call MedGemma via RunPod serverless endpoint."""
    import aiohttp

    api_url = os.getenv("MEDGEMMA_API_URL", "").strip()
    api_key = os.getenv("MEDGEMMA_API_KEY", "").strip()

    if not api_url or not api_key:
        raise EnvironmentError(
            "Set MEDGEMMA_API_URL and MEDGEMMA_API_KEY environment variables.\n"
            "MEDGEMMA_API_URL: Your RunPod serverless endpoint URL\n"
            "MEDGEMMA_API_KEY: Your RunPod API key"
        )

    # Load image
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Detect mime type
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    mime = mime_map.get(ext, "image/jpeg")

    # Build request
    payload = {
        "model": "google/medgemma-1.5-4b-it",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{api_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"API error {resp.status}: {error_text[:500]}")

            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def main():
    parser = argparse.ArgumentParser(description="Endoscopy Image Analysis with MedGemma")
    parser.add_argument("--image", required=True, help="Path to endoscopy image")
    parser.add_argument("--type", default="polyp_detection", choices=list(ANALYSIS_PROMPTS.keys()),
                        help="Analysis type")
    parser.add_argument("--query", default="", help="Specific question about the image")
    parser.add_argument("--lang", default="spanish", choices=["spanish", "english"],
                        help="Response language")
    parser.add_argument("--output", default="", help="Save result to file")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}")
        sys.exit(1)

    # Build prompt
    prompt = ANALYSIS_PROMPTS[args.type]
    if args.query:
        prompt += f"\n\nSpecific question: {args.query}"
    if args.lang == "spanish":
        prompt += "\n\nRespond in Spanish with English medical terms in parentheses."

    print(f"🔬 Analyzing: {args.image}")
    print(f"📋 Type: {args.type}")
    print(f"🌐 Language: {args.lang}")
    print(f"⏳ Calling MedGemma via RunPod...\n")

    try:
        result = await call_medgemma(args.image, prompt)
        print("=" * 60)
        print(result)
        print("=" * 60)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"\n✅ Saved to: {args.output}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
