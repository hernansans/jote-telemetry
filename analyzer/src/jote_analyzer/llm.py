"""Llamada a OpenAI: arma el contexto y pide el reporte narrativo en markdown."""

from __future__ import annotations

import json
import os

import yaml

from .analysis import Findings


def build_user_content(
    findings: Findings,
    limits: dict,
    docs: dict[str, str],
) -> str:
    """Arma el bloque de contexto que acompaña al prompt del sistema."""
    partes: list[str] = []

    partes.append("## Hallazgos determinísticos (AUTORITATIVOS — calculados en Python, no inventar números)\n")
    partes.append("```json")
    partes.append(json.dumps(findings.to_dict(), ensure_ascii=False, indent=2, default=str))
    partes.append("```\n")

    partes.append("## Límites mandatorios (limites.yaml — fuente de verdad con citas)\n")
    partes.append("```yaml")
    partes.append(yaml.safe_dump(limits, allow_unicode=True, sort_keys=False))
    partes.append("```\n")

    if docs:
        partes.append("## Documentación de contexto\n")
        for nombre, contenido in docs.items():
            partes.append(f"### {nombre}\n")
            partes.append(contenido)
            partes.append("")

    return "\n".join(partes)


def generate_report(
    system_prompt: str,
    user_content: str,
    *,
    model: str,
    api_key: str,
    temperature: float = 0.2,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return resp.choices[0].message.content or ""


def resolve_api_key() -> str | None:
    return os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
