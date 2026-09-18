"""
Clinical Report Generator Tool for Agent Zero
Generates structured medical reports following international standards.

Designed for Dr. Jaime Andrés Benítez Kellendonk — Surgical Oncologist, Quito, Ecuador

Generates reports in Spanish following:
- ASGE (American Society for Gastrointestinal Endoscopy) guidelines
- Paris classification for polyp morphology
- Kudo pit pattern classification
- NICE classification (NBI International Colorectal Endoscopic)
- ESGE surveillance recommendations
"""

import json
import os
from datetime import datetime
from typing import Any

from helpers.tool import Tool, Response
from helpers.print_style import PrintStyle


# Report templates
REPORT_TEMPLATES = {
    "colonoscopy": """# INFORME DE ENDOSCOPÍA DIGESTIVA

## Datos del Procedimiento
- **Fecha:** {date}
- **Endoscopista:** {physician}
- **Tipo de procedimiento:** Colonoscopía total / parcial
- **Indicación:** {indication}
- **Calidad de preparación:** {prep_quality}
- **Íleon terminal:** {ileum_reached}
- **Ciego:** {cecum_reached}

---

## Hallazgos Endoscópicos

{findings}

---

## Diagnóstico

{diagnosis}

---

## Recomendaciones

{recommendations}

---

## Clasificación de Lesiones

{classification}

---

**⚠️ AVISO:** Este informe es generado por un sistema de inteligencia artificial como herramienta de apoyo diagnóstico. Los hallazgos deben ser confirmados por el médico tratante. El sistema no constituye un dispositivo médico aprobado.

**Sistema:** MedGemma 1.5 4B (Google Health AI Developer Foundations)
**Fecha de generación:** {generation_date}
**Versión del análisis:** v1.0

---
*Dr. Jaime Andrés Benítez Kellendonk — Cirugía Oncológica*
*Consultorios Pichincha, Quito, Ecuador*
""",

    "pathology": """# INFORME DE ANATOMÍA PATOLÓGICA

## Datos de la Muestra
- **Fecha de recepción:** {date}
- **Tipo de muestra:** {sample_type}
- **Procedimiento:** {procedure}
- **Número de piezas:** {num_pieces}
- **Fijación:** {fixation}

---

## Descripción Macroscópica

{macro_description}

---

## Descripción Microscópica

{micro_description}

---

## Diagnóstico Histopatológico

{diagnosis}

---

## Clasificación y Grading

{grading}

---

## Recomendaciones

{recommendations}

---

**⚠️ AVISO:** Este análisis es generado por inteligencia artificial como herramienta de apoyo. El diagnóstico definitivo requiere evaluación por patólogo certificado. Los resultados deben correlacionarse con la clínica del paciente.

**Sistema:** MedGemma 1.5 4B (Google Health AI Developer Foundations)
**Fecha de generación:** {generation_date}

---
*Dr. Jaime Andrés Benítez Kellendonk — Cirugía Oncológica*
*Consultorios Pichincha, Quito, Ecuador*
""",

    "surgical": """# INFORME QUIRÚRGICO — EVALUACIÓN DE MÁRGENES

## Datos del Procedimiento
- **Fecha:** {date}
- **Cirujano:** {physician}
- **Procedimiento:** {procedure}
- **Tipo de muestra:** {sample_type}

---

## Evaluación de Márgenes

{margin_assessment}

---

## Descripción de la Pieza Quirúrgica

{specimen_description}

---

## Hallazgos Intraoperatorios

{intraop_findings}

---

## Diagnóstico

{diagnosis}

---

## Recomendaciones

{recommendations}

---

**⚠️ AVISO:** Esta evaluación de márgenes es generada por IA como consulta intraoperatoria. El diagnóstico definitivo requiere estudio histopatológico permanente por patólogo certificado.

**Sistema:** MedGemma 1.5 4B (Google Health AI Developer Foundations)
**Fecha de generación:** {generation_date}

---
*Dr. Jaime Andrés Benítez Kellendonk — Cirugía Oncológica*
*Consultorios Pichincha, Quito, Ecuador*
""",
}


class MedicalReportGenerate(Tool):
    """Generates structured clinical reports following international medical standards."""

    async def execute(self, **kwargs) -> Response:
        report_type = self.args.get("report_type", "colonoscopy").strip().lower()
        findings = self.args.get("findings", "").strip()
        diagnosis = self.args.get("diagnosis", "").strip()
        recommendations = self.args.get("recommendations", "").strip()
        physician = self.args.get("physician", "Dr. Jaime Andrés Benítez Kellendonk").strip()
        indication = self.args.get("indication", "").strip()
        patient_id = self.args.get("patient_id", "").strip()
        save_path = self.args.get("save_path", "").strip()
        additional_data = self.args.get("additional_data", {})

        # Validate
        valid_types = list(REPORT_TEMPLATES.keys())
        if report_type not in valid_types:
            return Response(
                message=f"Error: Invalid report_type '{report_type}'. Valid types: {', '.join(valid_types)}",
                break_loop=False,
            )

        if not findings:
            return Response(
                message="Error: `findings` is required. Provide the clinical findings to include in the report.",
                break_loop=False,
            )

        # Build report
        try:
            report = self._generate_report(
                report_type=report_type,
                findings=findings,
                diagnosis=diagnosis,
                recommendations=recommendations,
                physician=physician,
                indication=indication,
                additional_data=additional_data,
            )
        except Exception as e:
            return Response(
                message=f"Error generating report: {str(e)}",
                break_loop=False,
            )

        # Save if path provided
        save_info = ""
        if save_path:
            try:
                save_info = await self._save_report(report, save_path, report_type)
            except Exception as e:
                save_info = f"\n⚠️ Error saving report: {str(e)}"

        return Response(
            message=f"{report}{save_info}",
            break_loop=False,
        )

    def _generate_report(
        self,
        report_type: str,
        findings: str,
        diagnosis: str,
        recommendations: str,
        physician: str,
        indication: str,
        additional_data: dict,
    ) -> str:
        """Generate the report from template and data."""
        template = REPORT_TEMPLATES[report_type]
        now = datetime.now()

        # Common substitutions
        replacements = {
            "date": now.strftime("%d de %B de %Y").replace("January", "enero").replace("February", "febrero")
                .replace("March", "marzo").replace("April", "abril").replace("May", "mayo")
                .replace("June", "junio").replace("July", "julio").replace("August", "agosto")
                .replace("September", "septiembre").replace("October", "octubre")
                .replace("November", "noviembre").replace("December", "diciembre"),
            "generation_date": now.strftime("%Y-%m-%d %H:%M"),
            "physician": physician,
            "indication": indication or "No especificada",
            "findings": findings or "No se reportaron hallazgos.",
            "diagnosis": diagnosis or "Pendiente de evaluación clínica.",
            "recommendations": recommendations or "Seguimiento clínico según criterio médico.",
            "classification": self._build_classification_table(additional_data),
            "prep_quality": additional_data.get("prep_quality", "No evaluada"),
            "ileum_reached": additional_data.get("ileum_reached", "No reportado"),
            "cecum_reached": additional_data.get("cecum_reached", "No reportado"),
            "sample_type": additional_data.get("sample_type", "No especificada"),
            "procedure": additional_data.get("procedure", "No especificado"),
            "num_pieces": additional_data.get("num_pieces", "No reportado"),
            "fixation": additional_data.get("fixation", "Formol al 10%"),
            "macro_description": additional_data.get("macro_description", "Pendiente de procesamiento."),
            "micro_description": additional_data.get("micro_description", "Pendiente de procesamiento."),
            "grading": additional_data.get("grading", "Pendiente de evaluación."),
            "margin_assessment": additional_data.get("margin_assessment", findings),
            "specimen_description": additional_data.get("specimen_description", "No proporcionada."),
            "intraop_findings": additional_data.get("intraop_findings", "No reportados."),
        }

        # Apply replacements
        report = template
        for key, value in replacements.items():
            report = report.replace(f"{{{key}}}", str(value))

        return report

    def _build_classification_table(self, data: dict) -> str:
        """Build classification section from available data."""
        sections = []

        # Paris classification
        paris = data.get("paris_classification")
        if paris:
            sections.append(f"**París:** {paris}")

        # Kudo pit pattern
        kudo = data.get("kudo_pit_pattern")
        if kudo:
            sections.append(f"**Kudo (Patrón de criptas):** {kudo}")

        # NICE classification
        nice = data.get("nice_classification")
        if nice:
            sections.append(f"**NICE (NBI):** {nice}")

        # Size
        size = data.get("lesion_size")
        if size:
            sections.append(f"**Tamaño estimado:** {size}")

        # Location
        location = data.get("location")
        if location:
            sections.append(f"**Localización:** {location}")

        if not sections:
            return "No se proporcionaron datos de clasificación estructurada."

        return "\n".join(sections)

    async def _save_report(self, report: str, save_path: str, report_type: str) -> str:
        """Save report to file."""
        import aiofiles

        # Generate filename if path is a directory
        if os.path.isdir(save_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"informe_{report_type}_{timestamp}.md"
            save_path = os.path.join(save_path, filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

        async with aiofiles.open(save_path, "w", encoding="utf-8") as f:
            await f.write(report)

        return f"\n\n✅ Informe guardado en: `{save_path}`"
