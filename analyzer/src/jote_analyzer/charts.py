"""Gráficos del vuelo (strip chart estilo ensayos en vuelo).

Genera un PNG con paneles apilados que comparten el eje de tiempo: altura sobre
pista, IAS (con VNE/VNO/VA/VFE), RPM, temperaturas, presiones, factor de carga y
EGTs. El fondo se sombrea por fase del vuelo.

Requiere `matplotlib` (extra `pdf`). Si no está instalado, el llamador debe omitir.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .csvlog import FlightLog, numeric

# Colores por fase (fondo de los paneles)
_PHASE_COLORS = {
    "rodaje": "#d9d9d9",
    "despegue": "#ffd27f",
    "ascenso": "#bfe6bf",
    "crucero": "#bcd6f0",
    "descenso": "#cfeef0",
    "toque": "#f6b8b8",
    "aterrizaje": "#ffc299",
}
_PHASE_LABELS = {
    "rodaje": "Rodaje",
    "despegue": "Despegue",
    "ascenso": "Ascenso",
    "crucero": "Crucero",
    "descenso": "Descenso",
    "toque": "Toque y motor",
    "aterrizaje": "Aterrizaje",
}


def generate_strip_chart(log: FlightLog, findings_dict: dict, limits: dict, out_path: str | Path) -> Path | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    df = log.df
    if "timestamp" not in df or df["timestamp"].isna().all():
        return None
    t0 = df["timestamp"].min()
    tmin = (df["timestamp"] - t0).dt.total_seconds() / 60.0  # minutos transcurridos

    motor = limits.get("motor", {})
    vuelo = limits.get("vuelo", {})
    ref = findings_dict.get("metadata", {}).get("referencia_pista_ft", 0)

    # --- definición de paneles: (titulo, ylabel, [(serie,label,color)], [(y,label,color,estilo)]) ---
    palt = numeric(df, "Pressure Altitude (ft)")
    altura = palt - ref

    ias = numeric(df, "Indicated Airspeed (kt)")
    ias_lim = vuelo.get("ias", {}).get("limites", {})

    rpm = numeric(df, "RPM")
    rpm_lim = motor.get("rpm", {}).get("limites", {})

    oilt = numeric(df, "Oil Temp (deg F)")
    coolt = numeric(df, "Coolant Temp (deg F)")
    oilt_lim = motor.get("temp_aceite", {}).get("limites", {})
    coolt_lim = motor.get("temp_refrigerante", {}).get("limites", {})

    oilp = numeric(df, "Oil Press (PSI)")
    fuelp = numeric(df, "Fuel Press (PSI)")
    fuelp_lim = motor.get("presion_combustible", {}).get("limites", {})

    g = numeric(df, "Normal Acceleration (G)")
    g_lim = vuelo.get("factor_carga", {}).get("limites", {})

    egts = [(f"EGT{i}", numeric(df, f"EGT{i} (deg F)")) for i in range(1, 5)]
    egt_max = motor.get("egt", {}).get("limites", {}).get("max")

    panels = [
        ("Altura sobre pista", "ft",
         [(altura, "Altura s/pista", "#1f4e79")], []),
        ("Velocidad indicada (IAS)", "kt",
         [(ias, "IAS", "#1f4e79")],
         [(ias_lim.get("vne"), "VNE", "#cc0000", "-"),
          (ias_lim.get("vno"), "VNO", "#e69500", "--"),
          (ias_lim.get("va"), "VA", "#996600", ":"),
          (ias_lim.get("vfe"), "VFE", "#3a7d3a", ":")]),
        ("RPM motor", "rpm",
         [(rpm, "RPM", "#1f4e79")],
         [(rpm_lim.get("max_continuo"), "máx continuo", "#e69500", "--"),
          (rpm_lim.get("max_despegue_transitorio"), "máx transitorio", "#cc0000", "-")]),
        ("Temperaturas motor", "°F",
         [(oilt, "Aceite", "#cc6600"), (coolt, "Refrigerante", "#0077b6")],
         [(oilt_lim.get("max"), "aceite máx", "#cc0000", "-"),
          (oilt_lim.get("normal_max"), "aceite normal máx", "#e69500", "--"),
          (coolt_lim.get("max"), "refrig. máx", "#9d0208", ":")]),
        ("Presiones", "psi",
         [(oilp, "Aceite", "#cc6600"), (fuelp, "Combustible", "#2a9d8f")],
         [(fuelp_lim.get("min"), "comb. mín", "#cc0000", "--"),
          (fuelp_lim.get("max"), "comb. máx", "#e69500", "--")]),
        ("Factor de carga normal", "g",
         [(g, "g", "#1f4e79")],
         [(g_lim.get("flaps_arriba_pos"), "+límite", "#cc0000", "-"),
          (g_lim.get("flaps_arriba_neg"), "−límite", "#cc0000", "-")]),
        ("EGT por cilindro", "°F",
         [(s, lbl, c) for (lbl, s), c in zip(egts, ["#e63946", "#f4a261", "#2a9d8f", "#264653"])],
         [(egt_max, "EGT máx", "#cc0000", "-")]),
    ]
    # descartar paneles sin datos
    panels = [p for p in panels if any(s.notna().any() for s, *_ in p[2])]
    if not panels:
        return None

    n = len(panels)
    # aspecto apaisado para que entre completo en una página A4 landscape
    fig, axes = plt.subplots(n, 1, figsize=(15, 1.5 * n + 1), sharex=True)
    if n == 1:
        axes = [axes]

    fases = findings_dict.get("fases_vuelo", [])
    fases_presentes = _shade_phases(axes, fases, t0, tmin)

    for ax, (titulo, ylabel, series, lineas) in zip(axes, panels):
        for serie, label, color in series:
            ax.plot(tmin, serie, color=color, linewidth=0.9, label=label)
        for y, label, color, estilo in lineas:
            if y is not None:
                ax.axhline(y, color=color, linestyle=estilo, linewidth=0.8, alpha=0.8)
                ax.text(tmin.max(), y, f" {label}", color=color, fontsize=6,
                        va="center", ha="left")
        ax.set_ylabel(f"{titulo}\n[{ylabel}]", fontsize=7)
        ax.grid(True, alpha=0.25, linewidth=0.4)
        ax.tick_params(labelsize=6)
        if len(series) > 1:
            ax.legend(loc="upper right", fontsize=5, ncol=len(series), framealpha=0.7)

    axes[-1].set_xlabel("Tiempo desde inicio (min)", fontsize=7)

    # leyenda de fases arriba
    if fases_presentes:
        handles = [Patch(facecolor=_PHASE_COLORS.get(f, "#eee"), label=_PHASE_LABELS.get(f, f))
                   for f in fases_presentes]
        fig.legend(handles=handles, loc="upper center", ncol=len(handles),
                   fontsize=6, frameon=False, bbox_to_anchor=(0.5, 1.0))

    fig.suptitle("")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = Path(out_path)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_map_rpm_scatter(log: FlightLog, findings_dict: dict, limits: dict, out_path: str | Path) -> Path | None:
    """Scatter MAP (y) vs RPM (x), con los puntos coloreados por fase del vuelo."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    df = log.df
    rpm = numeric(df, "RPM")
    mapp = numeric(df, "Manifold Press (inch Hg)")
    if not (rpm.notna().any() and mapp.notna().any()):
        return None

    # color por fase (posición de muestra)
    fases = findings_dict.get("fases_vuelo", [])
    colores = ["#bbbbbb"] * len(df)
    presentes: list[str] = []
    for fase in fases:
        nombre = fase.get("fase")
        c = _PHASE_COLORS.get(nombre)
        if c is None:
            continue
        s, e = fase.get("idx_start"), fase.get("idx_end")
        if s is None or e is None:
            continue
        for pos in range(s, min(e + 1, len(colores))):
            colores[pos] = c
        if nombre not in presentes:
            presentes.append(nombre)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(rpm, mapp, c=colores, s=10, alpha=0.8, edgecolors="none")
    ax.set_xlabel("RPM")
    ax.set_ylabel("MAP (inch Hg)")
    ax.set_title("MAP vs RPM (color = fase del vuelo)", fontsize=10)
    ax.grid(True, alpha=0.3, linewidth=0.5)

    diag = findings_dict.get("diagnostico_motor", {}).get("map_rpm", {})
    corr = diag.get("correlacion_map_rpm")
    if corr is not None:
        ax.text(0.02, 0.97, f"corr(MAP, RPM) = {corr}", transform=ax.transAxes,
                fontsize=8, va="top", ha="left",
                bbox=dict(boxstyle="round", fc="white", ec="#ccc", alpha=0.8))

    if presentes:
        handles = [Patch(facecolor=_PHASE_COLORS.get(f, "#eee"), label=_PHASE_LABELS.get(f, f))
                   for f in presentes]
        ax.legend(handles=handles, loc="lower right", fontsize=6, framealpha=0.8, title="Fase")

    fig.tight_layout()
    out_path = Path(out_path)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _shade_phases(axes, fases: list[dict], t0, tmin) -> list[str]:
    presentes: list[str] = []
    for fase in fases:
        nombre = fase.get("fase")
        color = _PHASE_COLORS.get(nombre)
        if color is None:
            continue
        ini = pd.to_datetime(fase.get("inicio"), errors="coerce")
        fin = pd.to_datetime(fase.get("fin"), errors="coerce")
        if pd.isna(ini) or pd.isna(fin):
            continue
        x0 = (ini - t0).total_seconds() / 60.0
        x1 = (fin - t0).total_seconds() / 60.0
        for ax in axes:
            ax.axvspan(x0, x1, color=color, alpha=0.5, linewidth=0, zorder=0)
        if nombre not in presentes:
            presentes.append(nombre)
    return presentes
