"""
Medical Image Analysis Tool for Agent Zero
Connects to MedGemma (Google HAI-DEF) via RunPod serverless GPU for medical image inference.

Designed for Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncologist, Quito, Ecuador

Supported analysis types:
- polyp_detection: Detect polyps in colonoscopy images
- polyp_classification: Classify polyps (Paris, Kudo, NICE)
- cancer_screening: Colorectal cancer risk assessment
- margin_assessment: Surgical margin evaluation
- histopathology: Tissue sample analysis
- lesion_tracking: Multi-image comparison
- general_imaging: General medical image interpretation

Requires environment variables:
- MEDGEMMA_API_URL: RunPod serverless endpoint URL
- MEDGEMMA_API_KEY: RunPod API key
"""

import base64
import json
import os
from typing import Any

from helpers.tool import Tool, Response
from helpers.print_style import PrintStyle


# Prompt templates for each analysis type
ANALYSIS_PROMPTS = {
    "polyp_detection": """You are an expert gastroenterology AI analyzing a colonoscopy image.
Analyze this endoscopic image and provide:
1. POLYP DETECTION: Is a polyp visible? (Yes/No/Uncertain)
2. LOCATION ESTIMATE: Where in the colon is it located based on visual cues?
3. MORPHOLOGY: Describe the shape, size estimate (mm), surface characteristics
4. COLOR: Normal mucosa, erythematous, pale, discolored?
5. VASCULAR PATTERN: Any visible vascular patterns (NBI assessment if applicable)?
6. RECOMMENDATION: Should this be biopsied, resected, or monitored?

Respond in structured format with clear findings.""",

    "polyp_classification": """You are an expert gastroenterology AI performing detailed polyp classification.
Analyze this endoscopic image and classify the lesion using international standards:

PARIS CLASSIFICATION:
- 0-Ip: Pedunculated
- 0-Is: Sessile
- 0-IIa: Slightly elevated
- 0-IIb: Flat
- 0-IIc: Slightly depressed
- 0-III: Excavated/ulcerated

KUDO PIT PATTERN:
- Type I: Normal round pits
- Type II: Stellar or papillary pits
- Type IIIS: Small round or tubular pits
- Type IIIL: Large round or tubular pits
- Type IV: Branch-like or gyrus-like pits
- Type V: Irregular or non-structured pits

NICE CLASSIFICATION (NBI):
- Type 1: Likely hyperplastic
- Type 2: Likely adenoma
- Type 3: Likely deep submucosal invasive cancer

Provide classification with confidence level for each system.""",

    "cancer_screening": """You are an expert gastroenterology AI performing cancer risk assessment.
Analyze this endoscopic image for colorectal cancer screening:

1. LESION ASSESSMENT: Describe any visible lesions
2. RISK STRATIFICATION:
   - Low risk: Small (<10mm), uniform, no suspicious features
   - Intermediate risk: 10-20mm, or with some suspicious features
   - High risk: >20mm, irregular surface, depressed component, non-lifting sign
3. SURVEILLANCE RECOMMENDATION: Based on findings, recommend follow-up interval
4. RED FLAGS: Any features suggesting malignancy (ulceration, bleeding, rigidity, obstructing)

Use ESGE (European Society of Gastrointestinal Endoscopy) guidelines for recommendations.""",

    "margin_assessment": """You are an expert surgical pathology AI analyzing surgical margins.
Analyze this image for tumor margin assessment:

1. TISSUE IDENTIFICATION: What type of tissue is visible?
2. MARGIN STATUS: Are margins clear, close, or involved?
3. TUMOR PROXIMITY: If tumor is visible, estimate distance to nearest margin
4. TISSUE CHARACTERISTICS: Necrosis, inflammation, fibrosis, viable tumor cells?
5. RECOMMENDATION: Is re-excision needed? Additional sampling?

Note: This is for intraoperative consultation. Final assessment requires permanent pathology.""",

    "histopathology": """You are an expert pathology AI analyzing a histological image.
Analyze this tissue sample:

1. TISSUE TYPE: Epithelial, connective, muscle, neural, etc.
2. ARCHITECTURE: Normal, dysplastic, neoplastic?
3. CELLULAR FEATURES: Nuclear atypia, mitotic figures, cellular density
4. GRADING: If neoplastic, provide grade (well/moderately/poorly differentiated)
5. INFLAMMATION: Present? Type? Severity?
6. SPECIAL FEATURES: Glandular formation, mucin production, necrosis, invasion

Provide differential diagnosis with probability ranking.""",

    "lesion_tracking": """You are an expert gastroenterology AI comparing images over time.
If multiple images are provided, analyze for:
1. SIZE CHANGE: Has the lesion grown, shrunk, or remained stable?
2. MORPHOLOGY CHANGE: Any changes in shape, color, or surface?
3. INTERVAL: What is the likely time between images?
4. TREND: Is the lesion progressing, stable, or regressing?
5. RECOMMENDATION: Continue surveillance, intervene, or increase frequency?""",

    "general_imaging": """You are an expert medical imaging AI.
Analyze this medical image and provide:
1. IMAGE TYPE: What modality is this? (endoscopy, pathology, radiology, etc.)
2. FINDINGS: Describe all visible findings
3. NORMAL vs ABNORMAL: Is this within normal limits?
4. DIFFERENTIAL DIAGNOSIS: List possible diagnoses with probability
5. RECOMMENDATION: Additional imaging, clinical correlation, or follow-up needed?""",
}


class MedicalImageAnalyze(Tool):
    """Analyzes medical images using MedGemma via RunPod serverless GPU."""

    async def execute(self, **kwargs) -> Response:
        image_path = self.args.get("image_path", "").strip()
        analysis_type = self.args.get("analysis_type", "general_imaging").strip()
        query = self.args.get("query", "").strip()
        language = self.args.get("language", "spanish").strip().lower()

        # Validate inputs
        if not image_path:
            return Response(
                message="Error: `image_path` is required. Provide the path to the medical image.",
                break_loop=False,
            )

        valid_types = list(ANALYSIS_PROMPTS.keys())
        if analysis_type not in valid_types:
            return Response(
                message=f"Error: Invalid analysis_type '{analysis_type}'. Valid types: {', '.join(valid_types)}",
                break_loop=False,
            )

        # Load and encode image
        try:
            image_b64 = await self._load_image(image_path)
        except Exception as e:
            return Response(
                message=f"Error loading image: {str(e)}",
                break_loop=False,
            )

        # Build the prompt
        system_prompt = ANALYSIS_PROMPTS.get(analysis_type, ANALYSIS_PROMPTS["general_imaging"])
        if query:
            system_prompt += f"\n\nSpecific question from the physician: {query}"
        if language == "spanish":
            system_prompt += "\n\nRespond in Spanish. Use standard medical terminology in Spanish with English terms in parentheses where appropriate."

        # Call MedGemma via RunPod
        try:
            result = await self._call_medgemma(image_b64, system_prompt)
        except Exception as e:
            PrintStyle(font_color="red", padding=True).print(f"MedGemma API error: {str(e)}")
            return Response(
                message=f"Error calling MedGemma: {str(e)}\n\nPlease check MEDGEMMA_API_URL and MEDGEMMA_API_KEY environment variables.",
                break_loop=False,
            )

        # Format response
        formatted = self._format_result(result, analysis_type, image_path)
        return Response(message=formatted, break_loop=False)

    async def _load_image(self, image_path: str) -> str:
        """Load image from path and encode as base64."""
        import aiofiles

        # Handle relative paths
        if not os.path.isabs(image_path):
            # Try common locations
            candidates = [
                image_path,
                os.path.join(os.getcwd(), image_path),
                os.path.join("/a0/usr", image_path),
            ]
            for candidate in candidates:
                if os.path.exists(candidate):
                    image_path = candidate
                    break
            else:
                raise FileNotFoundError(f"Image not found: {image_path}")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file does not exist: {image_path}")

        # Read and encode
        async with aiofiles.open(image_path, "rb") as f:
            data = await f.read()

        # Validate it's an image
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".webp": "image/webp",
        }
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in mime_types:
            raise ValueError(f"Unsupported image format: {ext}. Supported: {', '.join(mime_types.keys())}")

        return base64.b64encode(data).decode("utf-8")

    async def _call_medgemma(self, image_b64: str, prompt: str) -> str:
        """Call MedGemma via RunPod serverless endpoint."""
        import aiohttp

        api_url = os.getenv("MEDGEMMA_API_URL", "").strip()
        api_key = os.getenv("MEDGEMMA_API_KEY", "").strip()

        if not api_url or not api_key:
            raise EnvironmentError(
                "MEDGEMMA_API_URL and MEDGEMMA_API_KEY environment variables are required. "
                "Set them to your RunPod serverless endpoint URL and API key."
            )

        # Build OpenAI-compatible request for vLLM on RunPod
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
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.1,  # Low temp for clinical accuracy
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # RunPod serverless uses /v1/chat/completions (OpenAI-compatible)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"API returned status {resp.status}: {error_text[:500]}")

                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    def _format_result(self, result: str, analysis_type: str, image_path: str) -> str:
        """Format the analysis result with metadata and disclaimers."""
        type_labels = {
            "polyp_detection": "Detección de Pólipos",
            "polyp_classification": "Clasificación de Pólipos",
            "cancer_screening": "Detección de Cáncer Colorrectal",
            "margin_assessment": "Evaluación de Márgenes Quirúrgicos",
            "histopathology": "Análisis Histopatológico",
            "lesion_tracking": "Seguimiento de Lesiones",
            "general_imaging": "Interpretación de Imagen Médica",
        }

        label = type_labels.get(analysis_type, analysis_type)

        return f"""## 🔬 Análisis: {label}

**Imagen:** {os.path.basename(image_path)}
**Modelo:** MedGemma 1.5 4B (Google HAI-DEF)
**Tipo de análisis:** {analysis_type}

---

{result}

---

⚠️ **AVISO IMPORTANTE:** Este análisis es generado por inteligencia artificial y constituye una herramienta de apoyo a la decisión clínica. NO reemplaza el juicio clínico del médico tratante. Todos los hallazgos deben ser verificados por el Dr. Jaime Andrés Benítez Kellendonk o el especialista competente. Este sistema no es un dispositivo diagnóstico aprobado.

📋 **Recomendación:** Correlacionar con cuadro clínico del paciente, antecedentes, y estudios complementarios."""
