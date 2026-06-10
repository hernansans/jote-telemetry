"""Carga de limites.yaml (la 'fuente de verdad' destilada de los manuales)."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_limits(data_dir: str | Path) -> dict:
    path = Path(data_dir) / "limites.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró limites.yaml en {path}. "
            "Pasá con --data el directorio que lo contiene."
        )
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_docs(data_dir: str | Path) -> dict[str, str]:
    """Lee todos los .md de data/docs/ como contexto adicional para el LLM."""
    docs_dir = Path(data_dir) / "docs"
    out: dict[str, str] = {}
    if docs_dir.is_dir():
        for md in sorted(docs_dir.glob("*.md")):
            out[md.name] = md.read_text(encoding="utf-8")
    return out
