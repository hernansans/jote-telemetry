"""Segmentación del vuelo en fases.

La altitud de presión del log está referenciada a 29.92" (presión estándar), no al
QNH del día. Por eso en tierra `Pressure Altitude` ≠ elevación oficial del aeródromo.
Para obtener una altura sobre la pista repetible y correcta, detectamos la
**referencia de pista** desde los propios datos (altitud de presión con el avión
detenido en tierra) y calculamos:

    altura_sobre_pista = Pressure Altitude − referencia_de_pista_detectada

Sobre esa altura + velocidades + tasa vertical, una máquina de estados clasifica
cada muestra en: rodaje, despegue, ascenso, crucero, descenso, toque, aterrizaje.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .csvlog import numeric

# --- Umbrales (calibrados con datos reales del JOTE) ---
AGL_AIRBORNE_FT = 20.0      # por encima => en vuelo
VS_CLIMB_FPM = 150.0        # tasa vertical (suavizada) para ascenso
VS_DESCENT_FPM = -150.0     # para descenso
SPEED_STOPPED_KT = 5.0      # por debajo => prácticamente detenido
SPEED_ROLL_KT = 25.0        # carrera de despegue/aterrizaje supera esto en tierra
MIN_PHASE_S = 8.0           # fases más cortas se fusionan con vecinas
SMOOTH_WIN = 11             # ventana (muestras ≈ s) para suavizar VS y AGL

# Fases que representan eventos puntuales: nunca se fusionan ni se descartan.
_EVENT_PHASES = {"despegue", "aterrizaje", "toque"}

_NOMBRES = {
    "rodaje": "Rodaje",
    "despegue": "Despegue (carrera)",
    "ascenso": "Ascenso",
    "crucero": "Crucero / nivelado",
    "descenso": "Descenso",
    "toque": "Toque y motor",
    "aterrizaje": "Aterrizaje (carrera)",
}


@dataclass
class Phase:
    indice: int
    fase: str
    nombre: str
    inicio: str | None
    fin: str | None
    duracion_s: float
    n_muestras: int
    idx_start: int  # posición 0-based en el df
    idx_end: int    # posición 0-based inclusive
    resumen: dict = field(default_factory=dict)


@dataclass
class PhaseResult:
    fases: list[Phase]
    eventos: dict
    referencia_pista_ft: float
    agl: pd.Series  # altura sobre pista (auto), alineada al índice del df

    def fase_por_posicion(self) -> list[str]:
        out = ["?"] * sum(p.n_muestras for p in self.fases)
        for p in self.fases:
            for pos in range(p.idx_start, p.idx_end + 1):
                if 0 <= pos < len(out):
                    out[pos] = p.fase
        return out

    def to_dict(self) -> dict:
        return {
            "referencia_pista_ft": round(self.referencia_pista_ft, 1),
            "eventos": self.eventos,
            "fases": [asdict(p) for p in self.fases],
        }


def detect_phases(df: pd.DataFrame) -> PhaseResult:
    n = len(df)
    palt = numeric(df, "Pressure Altitude (ft)")
    gs = numeric(df, "GPS Ground Speed (kt)")
    ias = numeric(df, "Indicated Airspeed (kt)")
    vs = numeric(df, "Vertical Speed (ft/min)")

    ref = _ground_reference(palt, gs, ias)
    agl = palt - ref

    agl_s = agl.rolling(SMOOTH_WIN, center=True, min_periods=1).median()
    vs_s = vs.rolling(SMOOTH_WIN, center=True, min_periods=1).median()
    spd = pd.concat([gs, ias], axis=1).max(axis=1)  # mejor estimación de velocidad

    # --- etiqueta cruda por muestra ---
    labels: list[str] = []
    for i in range(n):
        if agl_s.iloc[i] > AGL_AIRBORNE_FT:
            v = vs_s.iloc[i]
            if v > VS_CLIMB_FPM:
                labels.append("ascenso")
            elif v < VS_DESCENT_FPM:
                labels.append("descenso")
            else:
                labels.append("crucero")
        else:
            labels.append("tierra")

    runs = _coalesce(labels)
    runs = _refine_ground(runs, spd)
    runs = _merge_short(runs, df)
    runs = _refine_ground(runs, spd)  # re-clasifica tierra tras fusionar
    runs = _split_rolls(runs, spd)    # separa carrera de despegue/aterrizaje del rodaje

    fases = _to_phases(runs, df)
    for p in fases:
        p.resumen = _phase_summary(df, agl, p.idx_start, p.idx_end)

    eventos = _events(runs)
    if not agl.dropna().empty:
        eventos["altura_max_sobre_pista_ft"] = round(float(agl.max()), 0)

    return PhaseResult(fases=fases, eventos=eventos, referencia_pista_ft=float(ref), agl=agl)


# --------------------------------------------------------------------------- #

def _ground_reference(palt: pd.Series, gs: pd.Series, ias: pd.Series) -> float:
    """Altitud de presión con el avión detenido en tierra (mediana)."""
    detenido = (gs < SPEED_STOPPED_KT) & (ias < 30)
    cand = palt[detenido].dropna()
    if len(cand) >= 5:
        return float(cand.median())
    valid = palt.dropna()
    if valid.empty:
        return 0.0
    # fallback: percentil bajo (las muestras más bajas suelen ser en tierra)
    return float(valid.quantile(0.05))


def _coalesce(labels: list[str]) -> list[list]:
    """Agrupa etiquetas contiguas iguales -> [label, start_pos, end_pos]."""
    runs: list[list] = []
    if not labels:
        return runs
    start = 0
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            runs.append([labels[i - 1], start, i - 1])
            start = i
    runs.append([labels[-1], start, len(labels) - 1])
    return runs


def _refine_ground(runs: list[list], spd: pd.Series) -> list[list]:
    """Reclasifica los tramos 'tierra' en rodaje/despegue/aterrizaje/toque."""
    out = [list(r) for r in runs]
    for i, (label, s, e) in enumerate(out):
        if label not in ("tierra", "rodaje", "despegue", "aterrizaje", "toque"):
            continue
        vmax = float(spd.iloc[s:e + 1].max()) if e >= s else 0.0
        prev_air = i > 0 and out[i - 1][0] in ("ascenso", "crucero", "descenso")
        next_air = i < len(out) - 1 and out[i + 1][0] in ("ascenso", "crucero", "descenso")
        if vmax >= SPEED_ROLL_KT and prev_air and next_air:
            out[i][0] = "toque"
        elif vmax >= SPEED_ROLL_KT and next_air:
            out[i][0] = "despegue"
        elif vmax >= SPEED_ROLL_KT and prev_air:
            out[i][0] = "aterrizaje"
        else:
            out[i][0] = "rodaje"
    return out


def _split_rolls(runs: list[list], spd: pd.Series) -> list[list]:
    """Separa la carrera (aceleración/desaceleración) del rodaje contiguo.

    Un tramo 'despegue' suele empezar con rodaje + prueba de motor y termina en la
    carrera real; un 'aterrizaje' empieza con la carrera y sigue con rodaje hasta
    detenerse. El punto de corte es la última (despegue) / primera (aterrizaje)
    casi-detención del avión."""
    out: list[list] = []
    for label, s, e in runs:
        if label == "despegue":
            k = _last_below(spd, s, e, SPEED_STOPPED_KT)
            if k is None:
                k = _last_below(spd, s, e, SPEED_ROLL_KT)
            if k is not None and s <= k < e:
                out.append(["rodaje", s, k])
                out.append(["despegue", k + 1, e])
                continue
        elif label == "aterrizaje":
            k = _first_below(spd, s, e, SPEED_STOPPED_KT)
            if k is None:
                k = _first_below(spd, s, e, SPEED_ROLL_KT)
            if k is not None and s < k <= e:
                out.append(["aterrizaje", s, k - 1])
                out.append(["rodaje", k, e])
                continue
        out.append([label, s, e])
    return _coalesce_runs(out)


def _last_below(spd: pd.Series, s: int, e: int, thr: float) -> int | None:
    for i in range(e, s - 1, -1):
        v = spd.iloc[i]
        if pd.notna(v) and v < thr:
            return i
    return None


def _first_below(spd: pd.Series, s: int, e: int, thr: float) -> int | None:
    for i in range(s, e + 1):
        v = spd.iloc[i]
        if pd.notna(v) and v < thr:
            return i
    return None


def _merge_short(runs: list[list], df: pd.DataFrame) -> list[list]:
    """Fusiona fases aéreas/rodaje demasiado cortas con la vecina mayor.
    Los eventos (despegue/aterrizaje/toque) nunca se fusionan."""
    period = _period(df)
    runs = [list(r) for r in runs]
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for i, (label, s, e) in enumerate(runs):
            dur = (e - s + 1) * period
            if label in _EVENT_PHASES or dur >= MIN_PHASE_S:
                continue
            # elegir vecino con el que fusionar (el más largo)
            left = runs[i - 1] if i > 0 else None
            right = runs[i + 1] if i < len(runs) - 1 else None
            target = None
            if left and right:
                target = left if (left[2] - left[1]) >= (right[2] - right[1]) else right
            else:
                target = left or right
            if target is None:
                continue
            target[1] = min(target[1], s)
            target[2] = max(target[2], e)
            runs.pop(i)
            changed = True
            break
    return _coalesce_runs(runs)


def _coalesce_runs(runs: list[list]) -> list[list]:
    """Une tramos contiguos con la misma etiqueta tras fusionar."""
    out: list[list] = []
    for r in runs:
        if out and out[-1][0] == r[0] and out[-1][2] + 1 >= r[1]:
            out[-1][2] = max(out[-1][2], r[2])
        else:
            out.append(list(r))
    return out


def _to_phases(runs: list[list], df: pd.DataFrame) -> list[Phase]:
    period = _period(df)
    ts = df["timestamp"] if "timestamp" in df else None
    fases: list[Phase] = []
    for idx, (label, s, e) in enumerate(runs):
        inicio = str(ts.iloc[s]) if ts is not None and pd.notna(ts.iloc[s]) else None
        fin = str(ts.iloc[e]) if ts is not None and pd.notna(ts.iloc[e]) else None
        fases.append(Phase(
            indice=idx,
            fase=label,
            nombre=_NOMBRES.get(label, label),
            inicio=inicio,
            fin=fin,
            duracion_s=round((e - s + 1) * period, 1),
            n_muestras=e - s + 1,
            idx_start=s,
            idx_end=e,
        ))
    return fases


def _events(runs: list[list]) -> dict:
    labels = [r[0] for r in runs]
    air = {"ascenso", "crucero", "descenso"}
    despegues = aterrizajes = toques = 0
    for i, lab in enumerate(labels):
        if lab == "toque":
            toques += 1
        prev = labels[i - 1] if i > 0 else None
        nxt = labels[i + 1] if i < len(labels) - 1 else None
        # despegue real: tramo de tierra->aire
        if lab in ("despegue", "toque") and nxt in air:
            despegues += 1
        if lab in ("aterrizaje", "toque") and prev in air:
            aterrizajes += 1
    return {
        "despegues": despegues,
        "aterrizajes": aterrizajes,
        "toque_y_motor": toques,
    }


_RESUMEN_COLS = [
    ("RPM_max", "RPM", "max"),
    ("RPM_prom", "RPM", "mean"),
    ("IAS_max", "Indicated Airspeed (kt)", "max"),
    ("VS_max", "Vertical Speed (ft/min)", "max"),
    ("VS_min", "Vertical Speed (ft/min)", "min"),
    ("OilT_max", "Oil Temp (deg F)", "max"),
    ("CoolantT_max", "Coolant Temp (deg F)", "max"),
    ("OilP_min", "Oil Press (PSI)", "min"),
    ("FuelP_min", "Fuel Press (PSI)", "min"),
    ("MAP_max", "Manifold Press (inch Hg)", "max"),
    ("FuelFlow_prom", "Fuel Flow (gal/hour)", "mean"),
]


def _phase_summary(df: pd.DataFrame, agl: pd.Series, s: int, e: int) -> dict:
    out: dict = {}
    sl = slice(s, e + 1)
    a = agl.iloc[sl].dropna()
    if not a.empty:
        out["altura_max_ft"] = round(float(a.max()), 0)
    for nombre, col, agg in _RESUMEN_COLS:
        ser = numeric(df, col).iloc[sl].dropna()
        if ser.empty:
            continue
        val = getattr(ser, agg)()
        out[nombre] = round(float(val), 1)
    # EGT máx entre los 4 cilindros
    egts = [numeric(df, f"EGT{i} (deg F)").iloc[sl] for i in range(1, 5)]
    egt_vals = pd.concat(egts, axis=1).max(axis=1).dropna()
    if not egt_vals.empty:
        out["EGT_max"] = round(float(egt_vals.max()), 0)
    return out


def _period(df: pd.DataFrame) -> float:
    if "timestamp" in df and df["timestamp"].notna().sum() > 1:
        diffs = df["timestamp"].dropna().diff().dropna().dt.total_seconds()
        med = diffs.median()
        if med and med > 0:
            return float(med)
    return 1.0


def fase_en_timestamp(fases: list[Phase], ts: str | None) -> str | None:
    """Devuelve el nombre corto de fase que contiene a un timestamp dado."""
    if ts is None:
        return None
    t = pd.to_datetime(ts, errors="coerce")
    if pd.isna(t):
        return None
    for p in fases:
        ini = pd.to_datetime(p.inicio, errors="coerce") if p.inicio else None
        fin = pd.to_datetime(p.fin, errors="coerce") if p.fin else None
        if ini is not None and fin is not None and ini <= t <= fin:
            return p.fase
    return None
