"""Conversión del reporte markdown a PDF (markdown -> HTML -> PDF con weasyprint).

Self-contained: no requiere pandoc ni binarios externos. Las dependencias
(`markdown`, `weasyprint`) son opcionales — se instalan con el extra `pdf`:

    uv sync --extra pdf
"""

from __future__ import annotations

from pathlib import Path

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>"""


def markdown_to_pdf(
    md_text: str,
    out_path: str | Path,
    *,
    css_path: str | Path | None = None,
    title: str = "Reporte de análisis de vuelo",
) -> Path:
    try:
        import markdown as md_lib
        from weasyprint import HTML
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Faltan dependencias para PDF. Instalá con:  uv sync --extra pdf"
        ) from e

    body = md_lib.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "toc"],
    )

    css = ""
    if css_path:
        css_path = Path(css_path)
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")

    html = _HTML_TEMPLATE.format(title=title, css=css, body=body)

    out_path = Path(out_path)
    HTML(string=html, base_url=str(out_path.parent)).write_pdf(str(out_path))
    return out_path
