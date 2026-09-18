---
name: colonoscopy-analysis
description: >
  Complete workflow for colonoscopy image analysis using MedGemma AI.
  Covers polyp detection, classification (Paris/Kudo/NICE), cancer screening,
  and clinical report generation. Designed for Dr. Jaime Andrés Benítez Kellendonk.
triggers:
  - "analyze colonoscopy"
  - "polyp detection"
  - "endoscopy image"
  - "colonoscopy report"
  - "GI cancer screening"
  - "análisis de colonoscopía"
  - "detección de pólipos"
  - "informe endoscópico"
---

# Colonoscopy Analysis Skill

Complete workflow for AI-assisted colonoscopy image analysis.

## Quick Start

1. User provides an endoscopy image (white light, NBI, or chromoendoscopy)
2. Load image with `vision_load` tool
3. Analyze with `medical_image_analyze` tool
4. Generate report with `medical_report_generate` tool

## Workflow Steps

### Step 1: Image Loading
```
Tool: vision_load
Args:
  paths: ["/path/to/endoscopy_image.jpg"]
  query: "Analyze this colonoscopy image for polyps and lesions"
```

### Step 2: Detailed Analysis
```
Tool: medical_image_analyze
Args:
  image_path: "/path/to/endoscopy_image.jpg"
  analysis_type: "polyp_detection"  # or polyp_classification, cancer_screening
  query: "Specific question about the image"
  language: "spanish"
```

### Step 3: Classification (if polyp found)
```
Tool: medical_image_analyze
Args:
  image_path: "/path/to/endoscopy_image.jpg"
  analysis_type: "polyp_classification"
  language: "spanish"
```

### Step 4: Clinical Report
```
Tool: medical_report_generate
Args:
  report_type: "colonoscopy"
  findings: "[Analysis results from step 2-3]"
  diagnosis: "[Diagnostic impression]"
  recommendations: "[Follow-up recommendations]"
  indication: "[Clinical indication for procedure]"
  additional_data:
    paris_classification: "0-Is"
    kudo_pit_pattern: "Tipo III-L"
    nice_classification: "Tipo 2"
    lesion_size: "15mm"
    location: "Colon ascendente"
  save_path: "/a0/usr/reports/"
```

## Analysis Types

| Type | Use When | Output |
|------|----------|--------|
| `polyp_detection` | First look at any endoscopy image | Presence/absence, location, morphology |
| `polyp_classification` | Polyp detected, need detailed classification | Paris, Kudo, NICE classifications |
| `cancer_screening` | Routine screening or risk assessment | Risk stratification, surveillance interval |
| `margin_assessment` | Surgical specimen evaluation | Margin status, distance to tumor |
| `histopathology` | Tissue sample analysis | Tissue type, grading, differential |
| `lesion_tracking` | Comparing images over time | Size change, morphology trends |

## Image Quality Tips

For best results, images should be:
- **Resolution:** At least 640x480 pixels
- **Format:** JPEG or PNG
- **Lighting:** White light or NBI (Narrow Band Imaging)
- **Framing:** Lesion centered in frame
- **Focus:** Sharp focus on the area of interest
- **Multiple angles:** If possible, provide close-up and overview images

## Clinical Standards Reference

### Paris Classification
| Code | Description |
|------|-------------|
| 0-Ip | Pedunculated polyp |
| 0-Is | Sessile polyp |
| 0-IIa | Slightly elevated |
| 0-IIb | Flat |
| 0-IIc | Slightly depressed |
| 0-III | Excavated/ulcerated |

### Kudo Pit Pattern
| Type | Pattern | Significance |
|------|---------|--------------|
| I | Normal round pits | Normal mucosa |
| II | Stellar/papillary | Hyperplastic |
| IIIS | Small round/tubular | Adenomatous (small) |
| IIIL | Large round/tubular | Adenomatous (large) |
| IV | Branch-like/gyrus-like | Villous adenoma |
| V | Irregular/non-structured | Suspected carcinoma |

### NICE Classification (NBI)
| Type | Features | Likely Diagnosis |
|------|----------|-----------------|
| 1 | Brownish, no vascular pattern | Hyperplastic |
| 2 | Brown, thick vessels, oval pits | Adenoma |
| 3 | Brown to dark, irregular vessels | Deep submucosal cancer |

## Error Handling

If the image is unclear or analysis is uncertain:
1. Report the uncertainty explicitly
2. Suggest additional imaging (e.g., NBI, chromoendoscopy)
3. Recommend clinical correlation
4. Never force a classification when confidence is low

## Integration with Agent Zero

This skill integrates with:
- `vision_load` tool for image loading
- `medical_image_analyze` tool for MedGemma inference
- `medical_report_generate` tool for structured reports
- `response` tool for final output to the physician
