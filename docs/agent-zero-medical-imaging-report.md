# Agent Zero × Medical Imaging: Complete Implementation Guide
### For Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncologist, Quito, Ecuador

---

## 1. DR. JAIME ANDRÉS BENÍTEZ KELLENDONK — Profile

| Field | Detail |
|---|---|
| **Full Name** | Jaime Andrés Benítez Kellendonk |
| **Specialty** | Cirugía Oncológica (Surgical Oncology) |
| **Education** | Médico Cirujano — Pontificia Universidad Católica del Ecuador (PUCE) |
| **Location** | Quito, Pichincha, Ecuador |
| **Practice** | Consultorios Pichincha |
| **LinkedIn** | @jaimeandresbenitez |
| **Family** | Ana María Kellendonk Correa (Dermatology, same clinic) |

**Clinical focus for this system:** Colonoscopy polyp detection, GI cancer screening, tumor margin assessment, histopathology analysis.

---

## 2. WHAT WAS BUILT

All files are in the cloned `agent-zero/` repository:

### Agent Profile
```
agents/medical-imaging/
├── agent.yaml                          # Profile configuration
└── prompts/
    ├── agent.system.main.role.md       # Role definition (Spanish + English)
    ├── agent.system.main.specifics.md  # Clinical workflow, classification standards
    ├── agent.system.tools.md           # Tool usage instructions
    └── agent.system.main.communication.md  # Response format, language adaptation
```

### Custom Tools
```
tools/
├── medical_image_analyze.py            # MedGemma inference via RunPod
└── medical_report_generate.py          # Structured clinical report generator
```

### Skills
```
skills/colonoscopy-analysis/
├── SKILL.md                            # Complete workflow guide
├── Dockerfile.runpod                   # RunPod deployment config
└── scripts/
    ├── analyze_endoscopy.py            # Standalone analysis script
    └── deploy_runpod.sh               # RunPod deployment script
```

---

## 3. HOW IT ALL CONNECTS (Architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Zero (Docker Container)                 │
│                                                                 │
│  ┌───────────┐     ┌──────────────────────────────────────┐    │
│  │  WebUI    │     │  Agent: medical-imaging profile       │    │
│  │           │     │                                      │    │
│  │  Upload   │────▶│  System Prompt (role + specifics +   │    │
│  │  image    │     │  communication + tools)               │    │
│  └───────────┘     │                                      │    │
│                    │  Agent Loop:                           │    │
│                    │  1. vision_load(image_path)            │    │
│                    │  2. medical_image_analyze(type)        │    │
│                    │  3. medical_report_generate(template)  │    │
│                    │  4. response(text)                     │    │
│                    └──────────────┬───────────────────────┘    │
│                                  │                              │
│                    ┌─────────────▼───────────────────┐         │
│                    │  Tool: medical_image_analyze.py  │         │
│                    │                                  │         │
│                    │  Builds prompt per analysis type │         │
│                    │  Encodes image → base64          │         │
│                    │  Calls RunPod API (vLLM)         │         │
│                    │  Formats result with disclaimers │         │
│                    └─────────────┬───────────────────┘         │
│                                  │                              │
│                    ┌─────────────▼───────────────────┐         │
│                    │  RunPod Serverless GPU           │         │
│                    │                                  │         │
│                    │  vLLM + MedGemma 1.5 4B          │         │
│                    │  (Google HAI-DEF)                │         │
│                    │                                  │         │
│                    │  • RTX 4090 (testing)            │         │
│                    │  • A100 80GB (production)        │         │
│                    │  • Scales to zero when idle      │         │
│                    └──────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. SETUP INSTRUCTIONS

### Step 1: Deploy MedGemma on RunPod

**Option A: Quick Deploy (Recommended)**

1. Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
2. Click **"New Endpoint"**
3. Select **"vLLM OpenAI"** template
4. Configure:
   - **Model:** `google/medgemma-1.5-4b-it`
   - **GPU:** RTX 4090 (testing, ~$0.44/hr) or A100 80GB (production, ~$1.50/hr)
   - **Workers:** 0-3 (scales to zero = free when idle)
   - **Environment Variables:**
     - `HF_TOKEN` = your Hugging Face token
     - `MAX_MODEL_LEN` = 4096
     - `GPU_MEMORY_UTILIZATION` = 0.9
5. Click **Deploy**
6. Copy the endpoint URL (format: `https://api.runpod.ai/v2/XXXXX`)

**Option B: CLI Deploy**
```bash
cd agent-zero/skills/colonoscopy-analysis/scripts/
chmod +x deploy_runpod.sh
./deploy_runpod.sh
```

**Option C: Custom Docker**
```bash
cd agent-zero/skills/colonoscopy-analysis/
docker build -t medgemma-runpod -f Dockerfile.runpod .
# Test locally:
docker run --gpus all -p 8000:8000 -e HF_TOKEN=your_token medgemma-runpod
```

### Step 2: Configure Agent Zero

Add to your `.env` file or Docker environment:

```bash
# MedGemma on RunPod
MEDGEMMA_API_URL=https://api.runpod.ai/v2/YOUR_ENDPOINT_ID
MEDGEMMA_API_KEY=YOUR_RUNPOD_API_KEY
```

### Step 3: Start Agent Zero

```bash
# Standard Agent Zero start
docker run -p 80:80 \
  -v a0_usr:/a0/usr \
  -e MEDGEMMA_API_URL=$MEDGEMMA_API_URL \
  -e MEDGEMMA_API_KEY=$MEDGEMMA_API_KEY \
  agent0ai/agent-zero
```

### Step 4: Select the Medical Imaging Profile

In the WebUI:
1. Open the chat
2. Select **"Medical Imaging Assistant"** from the agent profile dropdown
3. Start uploading colonoscopy images

---

## 5. USAGE EXAMPLES

### Example 1: Polyp Detection
```
User: [uploads colonoscopy_image.jpg] "Analiza esta imagen de colonoscopía"

Agent:
1. Calls vision_load → loads and previews the image
2. Calls medical_image_analyze(type=polyp_detection) → runs MedGemma inference
3. Reports findings with confidence levels in Spanish
4. Includes disclaimers
```

### Example 2: Detailed Classification
```
User: "Clasifica este pólipo con los estándares Paris, Kudo y NICE"

Agent:
1. Calls medical_image_analyze(type=polyp_classification)
2. Returns structured classification:
   - París: 0-Is (sésil)
   - Kudo: Tipo III-L (tubular grande)
   - NICE: Tipo 2 (probable adenoma)
   - Confianza: Moderada (75%)
```

### Example 3: Generate Clinical Report
```
User: "Genera un informe completo para el paciente"

Agent:
1. Calls medical_report_generate(report_type=colonoscopy)
2. Generates structured report in Spanish
3. Saves to /a0/usr/reports/informe_colonoscopía_20260919.md
4. Includes all classifications, findings, and recommendations
```

### Example 4: Standalone Script (No Agent Zero)
```bash
# Direct analysis without Agent Zero
cd agent-zero/skills/colonoscopy-analysis/scripts/

export MEDGEMMA_API_URL="https://api.runpod.ai/v2/YOUR_ID"
export MEDGEMMA_API_KEY="YOUR_KEY"

python analyze_endoscopy.py \
  --image /path/to/colonoscopy.jpg \
  --type polyp_detection \
  --lang spanish \
  --output results.md
```

---

## 6. COST ESTIMATES

| Scenario | GPU | Cost per Image | Monthly (100 images) | Notes |
|---|---|---|---|---|
| **Testing** | RTX 4090 | ~$0.01 | ~$1.00 | Scales to zero |
| **Production** | A100 80GB | ~$0.03 | ~$3.00 | Faster inference |
| **High Volume** | A100 80GB x2 | ~$0.02 | ~$2.00 | Batch processing |

**RunPod pricing (serverless):**
- RTX 4090: ~$0.44/hr (pay per second, scales to zero)
- A100 80GB: ~$1.50/hr (pay per second, scales to zero)
- Cold start: ~10-30 seconds (first request after idle)
- Warm: ~1-3 seconds per image

---

## 7. CLINICAL STANDARDS IMPLEMENTED

### Paris Classification (Polyp Morphology)
| Code | Description | Image Features |
|---|---|---|
| 0-Ip | Pedunculated | Stalk visible, head protrudes |
| 0-Is | Sessile | Broad base, dome-shaped |
| 0-IIa | Slightly elevated | <2.5mm elevation |
| 0-IIb | Flat | No elevation |
| 0-IIc | Slightly depressed | <2.5mm depression |
| 0-III | Excavated | Ulcerated/necrotic |

### Kudo Pit Pattern
| Type | Pattern | Clinical Significance |
|---|---|---|
| I | Normal round pits | Normal mucosa |
| II | Stellar/papillary | Hyperplastic polyp |
| IIIS | Small tubular | Adenomatous (small gland) |
| IIIL | Large tubular | Adenomatous (large gland) |
| IV | Branch-like/gyrus | Villous adenoma |
| V | Irregular/non-structured | Suspected carcinoma |

### NICE Classification (NBI)
| Type | Vascular Pattern | Pit Pattern | Diagnosis |
|---|---|---|---|
| 1 | Brownish, absent vessels | Round, regular | Hyperplastic |
| 2 | Brown, thick vessels | Oval, elongated | Adenoma |
| 3 | Dark, irregular vessels | Distorted/absent | Deep SM cancer |

---

## 8. WHAT I KNOW ABOUT THE CODEBASE

### Agent Zero Architecture — Complete Understanding

**Core Loop (`agent.py`):**
- `AgentContext` manages conversation state, threading, pausing
- `Agent.monologue()` is the main loop: prompt → LLM → tool → repeat
- `Agent.prepare_prompt()` assembles system prompt from modular templates
- `Agent.process_llm_result_tools()` extracts JSON tool calls from LLM response
- `Agent._execute_tool_request()` loads tool class, calls `before_execution()` → `execute()` → `after_execution()`
- Tools are auto-discovered from `tools/` directory by filename match

**Tool System (`helpers/tool.py`):**
- Base class: `Tool(agent, name, method, args, message, loop_data)`
- Returns `Response(message=str, break_loop=bool)`
- `before_execution()` — logs, prints args
- `after_execution()` — adds result to conversation history
- Tools are matched by `tool_name` in JSON → looks for `tools/{tool_name}.py`

**Prompt System (`helpers/files.py`):**
- Templates use `{{ include "file.md" }}` directives
- `{{tools}}` placeholder auto-generates tool documentation
- `{{agent_profiles}}` lists available subordinate agents
- Variables loaded from companion `.py` files (e.g., `agent.system.main.tips.py`)
- Search order: project/agents/ → usr/agents/ → agents/ → plugins/

**Extension System (`helpers/extension.py`):**
- `@extensible` decorator creates start/end extension points
- Plugins hook into any extensible function via folder structure
- Extensions can modify data, intercept calls, add behavior

**Model System (`models.py`):**
- Uses LiteLLM for provider abstraction (OpenAI, Anthropic, Google, local, etc.)
- `LiteLLMChatWrapper` handles chat with streaming, reasoning, retry
- `unified_turn()` returns `LLMResult` with response, reasoning, function_calls
- Vision model configured separately via `plugins/_model_config`
- Supports `vision_load` for image analysis

**Plugin System (`plugins/`):**
- 40+ plugins, each with `extensions/` folder for hooks
- `_code_execution` — Python/NodeJS/Terminal in container
- `_model_config` — Model presets, vision config, provider metadata
- `_browser` — Playwright-based browser automation
- `_memory` — Long-term memory with vector DB
- `_skills` — Skill discovery and loading

**This integration uses:**
- Custom agent profile in `agents/medical-imaging/`
- Custom tools in `tools/medical_image_analyze.py` and `tools/medical_report_generate.py`
- Skill in `skills/colonoscopy-analysis/`
- RunPod serverless GPU for MedGemma inference
- OpenAI-compatible API (vLLM) for seamless integration

---

## 9. NEXT STEPS

1. **Create RunPod account** and add credits (~$10 for testing)
2. **Deploy MedGemma endpoint** using the guide above
3. **Set environment variables** in Agent Zero
4. **Test with sample images** from Kvasir dataset or Dr. Benítez's cases
5. **Refine prompts** based on Dr. Benítez's feedback
6. **Add to production** with A100 GPU for faster inference

---

*Report generated: 2026-09-19*
*Agent Zero repo: cloned, studied, 3,034 files analyzed*
*Custom files created: 8 (agent profile, tools, skills, deployment configs)*
*Doctor: Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncologist, Quito, Ecuador*
*Medical model: MedGemma 1.5 4B (Google Health AI Developer Foundations)*
*Inference: RunPod Serverless GPU (vLLM, OpenAI-compatible API)*
