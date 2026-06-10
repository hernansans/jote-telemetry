"""CLI: python -m jote_analyzer --data <dir> --log <archivo.csv>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .analysis import analyze
from .csvlog import load_log
from .limits import load_docs, load_limits
from .llm import build_user_content, generate_report, resolve_api_key

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "analisis_vuelo.md"
DEFAULT_CSS = PROJECT_ROOT / "assets" / "report.css"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jote-analyzer",
        description="Análisis post-vuelo del JOTE: logs Garmin GDU 460 contra límites mandatorios.",
    )
    p.add_argument("--data", default="data",
                   help="Directorio con limites.yaml y docs/ (default: ./data)")
    p.add_argument("--log", required=True, action="append", dest="logs",
                   help="Archivo CSV del log. Repetible para comparar varios vuelos.")
    p.add_argument("--prompt", default=str(DEFAULT_PROMPT),
                   help=f"Prompt del sistema en .md (default: {DEFAULT_PROMPT})")
    p.add_argument("--out", default=None,
                   help="Archivo de salida (default: reports/report_<log>.md). Si termina en "
                        ".pdf genera el PDF ahí (y el .md al lado); si no, el .md ahí.")
    p.add_argument("--model", default=None,
                   help="Modelo OpenAI (default: env OPENAI_MODEL o gpt-4.1)")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--no-llm", action="store_true",
                   help="Solo corre el análisis determinístico y vuelca el JSON; no llama al LLM.")
    p.add_argument("--pdf", action="store_true",
                   help="Además del .md, genera un PDF (requiere: uv sync --extra pdf).")
    p.add_argument("--css", default=str(DEFAULT_CSS),
                   help=f"Hoja de estilos para el PDF (default: {DEFAULT_CSS})")
    p.add_argument("--no-charts", action="store_true",
                   help="No generar los gráficos (strip chart) del reporte.")
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)

    data_dir = Path(args.data)
    try:
        limits = load_limits(data_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    docs = load_docs(data_dir)

    # --- Análisis determinístico de cada log ---
    analizados = []
    for log_path in args.logs:
        path = Path(log_path)
        if not path.exists():
            print(f"error: no existe el log {path}", file=sys.stderr)
            return 2
        print(f"• Analizando {path.name} ...", file=sys.stderr)
        log = load_log(path)
        findings = analyze(log, limits)
        analizados.append((path, log, findings))
        _print_resumen(findings)

    # Guarda el/los JSON de hallazgos (trazabilidad)
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    for path, log, findings in analizados:
        jpath = reports_dir / f"hallazgos_{path.stem}.json"
        jpath.write_text(
            json.dumps(findings.to_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  hallazgos → {jpath}", file=sys.stderr)

    # --- Gráficos (strip chart) por vuelo ---
    charts_por_stem: dict[str, list[Path]] = {}
    if not args.no_charts:
        charts_por_stem = _generate_charts(analizados, limits, reports_dir)

    if args.no_llm:
        print("\n--no-llm: se omite la generación del reporte narrativo.", file=sys.stderr)
        return 0

    # --- Contexto para el LLM ---
    api_key = resolve_api_key()
    if not api_key:
        print("error: falta OPENAI_KEY (o OPENAI_API_KEY) en el entorno o en .env",
              file=sys.stderr)
        return 2

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        print(f"error: no existe el prompt {prompt_path}", file=sys.stderr)
        return 2
    system_prompt = prompt_path.read_text(encoding="utf-8")

    model = args.model or _env_model()

    if len(analizados) == 1:
        _, _, findings = analizados[0]
        user_content = build_user_content(findings, limits, docs)
    else:
        # Multi-vuelo: concatena los hallazgos de cada log para comparación/tendencias.
        bloques = []
        for path, _, findings in analizados:
            bloques.append(f"# === Vuelo: {path.name} ===\n")
            bloques.append(build_user_content(findings, limits, docs))
        user_content = "\n\n".join(bloques)

    print(f"\n• Generando reporte con {model} ...", file=sys.stderr)
    try:
        report = generate_report(
            system_prompt, user_content,
            model=model, api_key=api_key, temperature=args.temperature,
        )
    except Exception as e:  # noqa: BLE001
        print(f"error al llamar a OpenAI: {e}", file=sys.stderr)
        return 1

    # Gráficos: el de MAP/RPM se inserta tras la sección Motor; el resto va al Anexo.
    report = _ensamblar_graficos(report, analizados, charts_por_stem)

    # --out define el archivo de salida. Si termina en .pdf, el PDF va ahí (e implica --pdf)
    # y el .md se guarda al lado; si no, el .md va ahí y el PDF al lado (cuando se pide --pdf).
    stem0 = analizados[0][0].stem
    if args.out:
        out_arg = Path(args.out)
        if out_arg.suffix.lower() == ".pdf":
            md_path, pdf_path, want_pdf = out_arg.with_suffix(".md"), out_arg, True
        else:
            md_path = out_arg if out_arg.suffix else out_arg.with_suffix(".md")
            md_path, pdf_path, want_pdf = md_path, md_path.with_suffix(".pdf"), args.pdf
    else:
        md_path = reports_dir / f"report_{stem0}.md"
        pdf_path, want_pdf = md_path.with_suffix(".pdf"), args.pdf

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(report, encoding="utf-8")
    print(f"\n✓ Reporte → {md_path}", file=sys.stderr)

    if want_pdf:
        from .pdf import markdown_to_pdf
        try:
            markdown_to_pdf(report, pdf_path, css_path=args.css,
                            title=f"Análisis de vuelo — {stem0}")
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"✓ PDF     → {pdf_path}", file=sys.stderr)

    return 0


def _generate_charts(analizados, limits, reports_dir: Path) -> dict[str, list[tuple[str, Path]]]:
    try:
        from .charts import generate_map_rpm_scatter, generate_strip_chart
    except ImportError:
        print("  (gráficos omitidos: falta matplotlib — uv sync --extra pdf)", file=sys.stderr)
        return {}
    out: dict[str, list[tuple[str, Path, str | None]]] = {}
    # (título, función, sufijo de archivo, sección destino)
    #   sección = None  -> va al Anexo al final
    #   sección = "Motor" -> se inserta al final de esa sección del reporte
    especificaciones = [
        ("Perfil del vuelo y parámetros vs tiempo", generate_strip_chart, "perfil", None),
        ("MAP vs RPM (diagnóstico)", generate_map_rpm_scatter, "map_rpm", "Motor"),
    ]
    for path, log, findings in analizados:
        fd = findings.to_dict()
        for titulo, fn, sufijo, seccion in especificaciones:
            try:
                png = fn(log, fd, limits, reports_dir / f"chart_{path.stem}_{sufijo}.png")
            except Exception as e:  # noqa: BLE001
                print(f"  (gráfico {sufijo} de {path.name} falló: {e})", file=sys.stderr)
                png = None
            if png is not None:
                out.setdefault(path.stem, []).append((titulo, Path(png), seccion))
                print(f"  gráfico → {png}", file=sys.stderr)
    return out


def _chart_block(titulo: str, png: Path, sufijo: str = "", con_h2: bool = False) -> str:
    """Bloque HTML de un gráfico (no se parte entre páginas, ver CSS .anexo-bloque)."""
    encabezado = "<h2>Anexo — Gráficos</h2>\n" if con_h2 else ""
    return (f'<div class="anexo-bloque">\n{encabezado}'
            f'<h3>{titulo}{sufijo}</h3>\n'
            f'<img src="{png.resolve()}" alt="{titulo}" />\n</div>')


def _insert_chart_after_section(report: str, keyword: str, block: str) -> str | None:
    """Inserta `block` al final de la sección '## … <keyword> …' del reporte.
    Devuelve None si no se encuentra esa sección (el llamador lo manda al Anexo)."""
    lines = report.split("\n")
    start = next((i for i, ln in enumerate(lines)
                  if ln.startswith("## ") and keyword.lower() in ln.lower()), None)
    if start is None:
        return None
    end = next((j for j in range(start + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    return "\n".join(lines[:end] + ["", block, ""] + lines[end:])


def _ensamblar_graficos(report: str, analizados, charts_por_stem: dict) -> str:
    """Inserta los gráficos con sección destino dentro del reporte (p.ej. MAP/RPM tras
    'Motor') y manda el resto al Anexo al final."""
    if not charts_por_stem:
        return report
    multi = len(analizados) > 1
    anexo: list[tuple[str | None, str, Path]] = []  # (sub-etiqueta, título, png)

    if not multi:
        stem = analizados[0][0].stem
        for titulo, png, seccion in charts_por_stem.get(stem, []):
            if seccion:
                nuevo = _insert_chart_after_section(report, seccion, _chart_block(titulo, png))
                if nuevo is not None:
                    report = nuevo
                    continue
            anexo.append((None, titulo, png))
    else:
        for path, _log, _f in analizados:
            for titulo, png, _seccion in charts_por_stem.get(path.stem, []):
                anexo.append((path.name, titulo, png))

    if anexo:
        bloques = []
        for i, (sub, titulo, png) in enumerate(anexo):
            sufijo = f" — {sub}" if sub else ""
            bloques.append(_chart_block(titulo, png, sufijo=sufijo, con_h2=(i == 0)))
        report = report.rstrip() + "\n\n" + "\n\n".join(bloques)
    return report


def _env_model() -> str:
    import os
    return os.getenv("OPENAI_MODEL", "gpt-4.1")


def _print_resumen(findings) -> None:
    viol = [h for h in findings.hallazgos if h.severidad == "violacion"]
    aten = [h for h in findings.hallazgos if h.severidad == "atencion"]
    ev = findings.metadata.get("eventos", {})
    print(f"  {findings.metadata['muestras']} muestras, "
          f"{findings.metadata['duracion_hms']} de vuelo | "
          f"{len(findings.fases_vuelo)} fases, "
          f"{ev.get('despegues', 0)} desp./{ev.get('aterrizajes', 0)} aterr./"
          f"{ev.get('toque_y_motor', 0)} toques, "
          f"altura máx {ev.get('altura_max_sobre_pista_ft', '?')} ft", file=sys.stderr)
    print(f"  {len(viol)} violación(es), {len(aten)} atención(es), "
          f"{len(findings.alertas_cas)} tipo(s) de alerta CAS", file=sys.stderr)
    for h in viol:
        fases = f" [{', '.join(h.fases)}]" if h.fases else ""
        print(f"    ⚠ VIOLACIÓN {h.parametro}{fases}: {h.descripcion} "
              f"(pico {h.valor_extremo}, {h.duracion_s}s)", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
