"""Motor determinístico de análisis.

Lee el log fila por fila y compara contra limites.yaml SIN intervención del LLM.
Produce un objeto estructurado (`Findings`) con números exactos: exceedances,
ventanas temporales, picos, alertas CAS acumuladas, AGL, etc.

Ese objeto es la entrada autoritativa para el LLM, que solo redacta/interpreta.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import pandas as pd

from .csvlog import FlightLog, numeric
from .phases import detect_phases, fase_en_timestamp

ELEVACION_AERODROMO_FT = 1748  # ver data/docs/aerodromo.md


@dataclass
class Segment:
    inicio: str | None
    fin: str | None
    duracion_s: float
    n_muestras: int
    pico: float | None
    fase: str | None = None


@dataclass
class Finding:
    parametro: str
    campo_csv: str
    severidad: str  # "violacion" | "atencion" | "info"
    descripcion: str
    umbral: str
    valor_extremo: float | None
    n_muestras: int
    duracion_s: float
    segmentos: list[Segment] = field(default_factory=list)
    fases: list[str] = field(default_factory=list)
    fuente: str = ""


@dataclass
class ParamStats:
    parametro: str
    campo_csv: str
    unidad: str
    min: float | None
    max: float | None
    promedio: float | None
    n_validos: int


@dataclass
class CasAlert:
    mensaje: str
    n_muestras: int
    duracion_s: float
    primera: str | None
    ultima: str | None


@dataclass
class Findings:
    metadata: dict
    fases_vuelo: list[dict] = field(default_factory=list)
    estadisticas: list[ParamStats] = field(default_factory=list)
    hallazgos: list[Finding] = field(default_factory=list)
    alertas_cas: list[CasAlert] = field(default_factory=list)
    diagnostico_motor: dict = field(default_factory=dict)
    analisis_flaps: dict = field(default_factory=dict)
    analisis_viento: dict = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata,
            "fases_vuelo": self.fases_vuelo,
            "estadisticas": [asdict(s) for s in self.estadisticas],
            "hallazgos": [asdict(h) for h in self.hallazgos],
            "alertas_cas": [asdict(c) for c in self.alertas_cas],
            "diagnostico_motor": self.diagnostico_motor,
            "analisis_flaps": self.analisis_flaps,
            "analisis_viento": self.analisis_viento,
            "notas": self.notas,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _ts(df: pd.DataFrame, idx) -> str | None:
    if "timestamp" in df and pd.notna(df.loc[idx, "timestamp"]):
        return str(df.loc[idx, "timestamp"])
    return None


def _sample_period_s(df: pd.DataFrame) -> float:
    if "timestamp" in df and df["timestamp"].notna().sum() > 1:
        diffs = df["timestamp"].dropna().diff().dropna().dt.total_seconds()
        med = diffs.median()
        if med and med > 0:
            return float(med)
    return 1.0


def _segments(mask: pd.Series, df: pd.DataFrame, values: pd.Series, period: float) -> list[Segment]:
    """Agrupa filas contiguas donde mask=True en segmentos temporales."""
    segs: list[Segment] = []
    idxs = list(df.index[mask.fillna(False)])
    if not idxs:
        return segs
    run = [idxs[0]]
    pos = {ix: i for i, ix in enumerate(df.index)}
    for prev, cur in zip(idxs, idxs[1:]):
        if pos[cur] == pos[prev] + 1:
            run.append(cur)
        else:
            segs.append(_make_seg(run, df, values, period))
            run = [cur]
    segs.append(_make_seg(run, df, values, period))
    return segs


def _make_seg(run: list, df: pd.DataFrame, values: pd.Series, period: float) -> Segment:
    vals = values.loc[run].dropna()
    peak = float(vals.abs().max()) if not vals.empty else None
    # devuelve el valor con mayor magnitud preservando el signo
    if not vals.empty:
        peak = float(vals.loc[vals.abs().idxmax()])
    return Segment(
        inicio=_ts(df, run[0]),
        fin=_ts(df, run[-1]),
        duracion_s=round(len(run) * period, 1),
        n_muestras=len(run),
        pico=peak,
    )


def _exceed(
    parametro: str,
    campo: str,
    series: pd.Series,
    mask: pd.Series,
    df: pd.DataFrame,
    period: float,
    severidad: str,
    descripcion: str,
    umbral: str,
    fuente: str,
) -> Finding | None:
    mask = mask.fillna(False)
    n = int(mask.sum())
    if n == 0:
        return None
    vals = series[mask].dropna()
    extremo = None
    if not vals.empty:
        extremo = float(vals.loc[vals.abs().idxmax()])
    return Finding(
        parametro=parametro,
        campo_csv=campo,
        severidad=severidad,
        descripcion=descripcion,
        umbral=umbral,
        valor_extremo=extremo,
        n_muestras=n,
        duracion_s=round(n * period, 1),
        segmentos=_segments(mask, df, series, period),
        fuente=fuente,
    )


def _ventana_operacional(df: pd.DataFrame, phase_result) -> pd.Series:
    """Bool series: True desde el inicio del primer tramo NO-rodaje (despegue/vuelo) hasta el
    fin del último tramo no-rodaje (aterrizaje). Modela la ventana en que la bomba eléctrica
    auxiliar debe estar activa (despegue–aterrizaje); fuera de ella (taxi inicial/final) las
    presiones de combustible pueden ser marginales en ralentí."""
    mask = pd.Series(False, index=df.index)
    no_rodaje = [p for p in phase_result.fases if p.fase != "rodaje"]
    if not no_rodaje:
        return mask
    mask.iloc[no_rodaje[0].idx_start: no_rodaje[-1].idx_end + 1] = True
    return mask


def _circular_mean_deg(series: pd.Series) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    rad = s * math.pi / 180.0
    x = float(rad.apply(math.cos).mean())
    y = float(rad.apply(math.sin).mean())
    if x == 0 and y == 0:
        return None
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _analisis_viento(df: pd.DataFrame, vuelo: dict, phase_result, period: float):
    """Componente de viento cruzado en las ventanas de despegue y aterrizaje.

    El rumbo de pista se estima con el track medio (true) de las carreras; el viento del log se
    asume en el mismo norte. El viento no siempre está disponible en la carrera (el G3X lo computa
    en movimiento/aire), por eso cada ventana incluye también la fase contigua (ascenso inicial /
    aproximación final). Límite: recomendación operacional, no estructural -> severidad 'atencion'.
    """
    cfg = vuelo.get("viento_cruzado", {})
    ws = numeric(df, cfg.get("campo_csv_velocidad", "Wind Speed (kt)"))
    wd = numeric(df, cfg.get("campo_csv_direccion", "Wind Direction (deg)"))
    trk = numeric(df, cfg.get("campo_csv_track", "GPS Ground Track (deg)"))
    if not (ws.notna().any() and wd.notna().any()):
        return {"disponible": False, "motivo": "sin datos de viento en el log"}, []

    fases = phase_result.fases
    roll_idx = [i for p in fases if p.fase in ("despegue", "aterrizaje")
                for i in range(p.idx_start, p.idx_end + 1)]
    rwy = _circular_mean_deg(trk.iloc[roll_idx]) if roll_idx else _circular_mean_deg(trk)
    if rwy is None:
        return {"disponible": False, "motivo": "sin track para estimar el rumbo de pista"}, []

    ang = (wd - rwy) * math.pi / 180.0
    xwind = ws * ang.apply(lambda a: abs(math.sin(a)) if pd.notna(a) else float("nan"))
    hwind = ws * ang.apply(lambda a: math.cos(a) if pd.notna(a) else float("nan"))
    limite = cfg.get("limite_kt", 15)
    fuente = cfg.get("fuente", "")

    def _mask(idxs: list[int]) -> pd.Series:
        m = pd.Series(False, index=df.index)
        if idxs:
            m.iloc[sorted(set(idxs))] = True
        return m

    def _resumen(mask: pd.Series) -> dict | None:
        sx = xwind[mask].dropna()
        if sx.empty:
            return None
        return {
            "xwind_max_kt": round(float(sx.max()), 1),
            "xwind_medio_kt": round(float(sx.mean()), 1),
            "headwind_medio_kt": round(float(hwind[mask].dropna().mean()), 1),
            "viento_medio_kt": round(float(ws[mask].dropna().mean()), 1),
        }

    findings: list[Finding] = []
    ventanas: dict = {}
    for nombre, fase_obj, vecino in [("despegue", "despegue", +1), ("aterrizaje", "aterrizaje", -1)]:
        roll_idx: list[int] = []
        vec_idx: list[int] = []
        for k, p in enumerate(fases):
            if p.fase == fase_obj:
                roll_idx += list(range(p.idx_start, p.idx_end + 1))
                kv = k + vecino
                if 0 <= kv < len(fases):
                    q = fases[kv]
                    vec_idx += list(range(q.idx_start, q.idx_end + 1))
        if not roll_idx:
            continue
        entrada: dict = {}
        # Carrera (superficie) -> contra esto se chequea el límite
        roll_mask = _mask(roll_idx)
        res_roll = _resumen(roll_mask)
        if res_roll is None:
            entrada["carrera"] = {"disponible": False,
                                  "motivo": "el G3X no computó viento durante la carrera (baja velocidad/en tierra)"}
        else:
            entrada["carrera"] = {"disponible": True, **res_roll}
            f = _exceed(f"Viento cruzado ({nombre})", "Wind Speed/Dir (derivado)", xwind,
                        roll_mask & (xwind > limite), df, period, "atencion",
                        f"Componente de viento cruzado de superficie en {nombre} por encima del máximo "
                        f"demostrado ({limite} kt). Recomendación operacional, no estructural.",
                        f"> {limite} kt cruzado", fuente)
            if f:
                findings.append(f)
        # Contexto en altura (ascenso inicial / aproximación) -> informativo, NO se flaguea
        res_vec = _resumen(_mask(vec_idx))
        if res_vec is not None:
            entrada["contexto_en_altura"] = {
                **res_vec,
                "nota": "Viento en ascenso/aproximación (en altura), NO el de superficie de la carrera; "
                        "los vientos aloft suelen ser mayores. No se usa para el límite.",
            }
        ventanas[nombre] = entrada

    info = {
        "disponible": True,
        "rumbo_pista_estimado_deg": round(rwy, 0),
        "limite_kt": limite,
        "ventanas": ventanas,
        "metodo": ("Rumbo de pista = track medio (true) de las carreras de despegue/aterrizaje; "
                   "viento del log asumido en el mismo norte. Cruzado = viento·sin(dir−rumbo). Validar."),
    }
    return info, findings


def _determinar_flaps(df: pd.DataFrame, vuelo: dict, phase_result):
    """Determina, desde los propios datos, cuándo los flaps estuvieron extendidos.

    'Flap Position' es un valor CRUDO del sensor (sin tabla de calibración a %). En lugar de
    asumir o gatear, se INFIERE el valor de 'flaps arriba' como el más frecuente del vuelo
    (la aeronave pasa la mayor parte retraída — además vuela por encima de VFE con ese valor,
    lo que confirma que es 'arriba') y se marca 'extendido' cuando el sensor se aparta de ese
    valor más que `delta_extendido`. Devuelve (mask, info) y reporta el método para que el
    analista/LLM lo valide.
    """
    cfg = vuelo.get("flaps", {})
    col = cfg.get("campo_csv", "Flap Position")
    delta = cfg.get("delta_extendido", 2)
    n = len(df)
    flaps = numeric(df, col)
    if col not in df.columns or not flaps.notna().any():
        return pd.Series([False] * n, index=df.index), {
            "disponible": False, "motivo": f"columna '{col}' ausente o sin datos"}

    retraido = float(flaps.mode().iloc[0])
    ext = ((flaps - retraido).abs() >= delta).fillna(False)

    ias = numeric(df, vuelo.get("ias", {}).get("campo_csv", "Indicated Airspeed (kt)"))
    fases_ext: list[str] = []
    for p in phase_result.fases:
        if ext.iloc[p.idx_start:p.idx_end + 1].any() and p.fase not in fases_ext:
            fases_ext.append(p.fase)
    ias_ext = ias[ext].dropna()
    info = {
        "disponible": True,
        "campo_csv": col,
        "valor_retraido_inferido": round(retraido, 1),
        "delta_extendido": delta,
        "distribucion_valores": {str(int(k)): int(v) for k, v in flaps.value_counts().sort_index().items()},
        "n_muestras_extendido": int(ext.sum()),
        "duracion_extendido_s": round(int(ext.sum()) * _sample_period_s(df), 1),
        "fases_con_flaps_extendidos": fases_ext,
        "ias_max_con_flaps_extendidos_kt": round(float(ias_ext.max()), 1) if not ias_ext.empty else None,
        "metodo": ("Inferido del sensor crudo (sin calibración): 'flaps arriba' = valor más "
                   "frecuente; 'extendido' = |sensor − ese valor| ≥ delta. Validar contra el vuelo."),
    }
    return ext, info


def _stat(parametro: str, campo: str, unidad: str, series: pd.Series) -> ParamStats:
    valid = series.dropna()
    return ParamStats(
        parametro=parametro,
        campo_csv=campo,
        unidad=unidad,
        min=round(float(valid.min()), 2) if not valid.empty else None,
        max=round(float(valid.max()), 2) if not valid.empty else None,
        promedio=round(float(valid.mean()), 2) if not valid.empty else None,
        n_validos=int(valid.count()),
    )


# --------------------------------------------------------------------------- #
# Motor principal
# --------------------------------------------------------------------------- #

def analyze(log: FlightLog, limits: dict) -> Findings:
    df = log.df
    period = _sample_period_s(df)

    phase_result = detect_phases(df)
    flaps_mask, flaps_info = _determinar_flaps(df, limits.get("vuelo", {}), phase_result)

    # Motor en marcha: con el motor apagado (RPM≈0, p.ej. el log arranca antes del encendido)
    # las presiones/temperaturas no son válidas y no deben evaluarse contra límites.
    _rpm_cfg0 = limits.get("motor", {}).get("rpm", {})
    motor_on = (numeric(df, _rpm_cfg0.get("campo_csv", "RPM"))
                > _rpm_cfg0.get("umbral_motor_encendido", 1000)).fillna(False)

    findings: list[Finding] = []
    stats: list[ParamStats] = []
    notas: list[str] = []

    if flaps_info.get("disponible"):
        n_ext = flaps_info["n_muestras_extendido"]
        if n_ext > 0:
            notas.append(
                f"Flaps (config. inferida del sensor crudo, 'arriba' ≈ "
                f"{flaps_info['valor_retraido_inferido']}): aparecen EXTENDIDOS en {n_ext} muestras "
                f"({flaps_info['duracion_extendido_s']} s), fases {flaps_info['fases_con_flaps_extendidos']}, "
                f"IAS máx con flaps {flaps_info['ias_max_con_flaps_extendidos_kt']} kt. "
                "Inferencia data-driven, no calibración — validar."
            )
        else:
            notas.append(
                f"Flaps: el sensor se mantuvo en su valor más frecuente "
                f"({flaps_info['valor_retraido_inferido']}) todo el vuelo → flaps aparentemente "
                "RETRAÍDOS siempre (inferido del sensor crudo, sin calibración). "
                "VFE no aplica; envolvente de carga evaluada con flaps arriba."
            )

    motor = limits.get("motor", {})
    vuelo = limits.get("vuelo", {})
    avionica = limits.get("avionica", {})

    # ---- RPM ----------------------------------------------------------------
    rpm_cfg = motor.get("rpm", {})
    rpm_col = rpm_cfg.get("campo_csv", "RPM")
    rpm = numeric(df, rpm_col)
    if rpm.notna().any():
        stats.append(_stat("RPM motor", rpm_col, "rpm", rpm))
        lim = rpm_cfg.get("limites", {})
        cont = lim.get("max_continuo")
        trans = lim.get("max_despegue_transitorio")
        fuente = rpm_cfg.get("fuente", "")
        if trans is not None:
            f = _exceed("RPM", rpm_col, rpm, rpm > trans, df, period, "violacion",
                        f"RPM por encima del máximo transitorio de despegue ({trans} rpm).",
                        f"> {trans} rpm", fuente)
            if f:
                findings.append(f)
        if cont is not None and trans is not None:
            zona = ((rpm > cont) & (rpm <= trans)).fillna(False)
            dur_lim = lim.get("max_despegue_duracion_s", 300)
            dur_total = int(zona.sum()) * period
            if dur_total > dur_lim:
                f = _exceed("RPM despegue (>5 min)", rpm_col, rpm, zona, df, period, "violacion",
                            f"RPM en zona de despegue ({cont}-{trans} rpm) durante {round(dur_total)} s "
                            f"acumulados, por encima del máximo admisible de {round(dur_lim)} s (5 min).",
                            f"{cont}-{trans} rpm > {round(dur_lim)} s acumulados", fuente)
            else:
                f = _exceed("RPM despegue", rpm_col, rpm, zona, df, period, "atencion",
                            f"RPM en zona de despegue ({cont}-{trans} rpm). Admisible máx. {round(dur_lim)} s "
                            f"(5 min); acumulado {round(dur_total)} s.",
                            f"{cont}-{trans} rpm (máx {round(dur_lim)} s)", fuente)
            if f:
                findings.append(f)
        elif cont is not None:
            f = _exceed("RPM", rpm_col, rpm, rpm > cont, df, period, "violacion",
                        f"RPM por encima del máximo continuo ({cont} rpm).",
                        f"> {cont} rpm", fuente)
            if f:
                findings.append(f)

    # ---- Temp aceite --------------------------------------------------------
    ot_cfg = motor.get("temp_aceite", {})
    ot_col = ot_cfg.get("campo_csv", "Oil Temp (deg F)")
    ot = numeric(df, ot_col)
    if ot.notna().any():
        stats.append(_stat("Temp aceite", ot_col, ot_cfg.get("unidad", "°F"), ot))
        lim = ot_cfg.get("limites", {})
        fuente = ot_cfg.get("fuente", "")
        mx = lim.get("max")
        if mx is not None:
            f = _exceed("Temp aceite", ot_col, ot, ot > mx, df, period, "violacion",
                        f"Temperatura de aceite por encima del máximo ({mx} °F).",
                        f"> {mx} °F", fuente)
            if f:
                findings.append(f)
        nmax = lim.get("normal_max")
        if nmax is not None and mx is not None:
            f = _exceed("Temp aceite", ot_col, ot, (ot > nmax) & (ot <= mx), df, period, "atencion",
                        f"Temperatura de aceite por encima del rango normal ({nmax} °F) "
                        f"pero bajo el máximo ({mx} °F).",
                        f"{nmax}-{mx} °F", fuente)
            if f:
                findings.append(f)

        # Regla alta potencia sin temperatura operativa (proxy del constructor)
        regla = ot_cfg.get("regla_alta_potencia_sin_temp_operativa")
        if regla:
            urpm = regla.get("umbral_rpm")
            utemp = regla.get("umbral_temp_operativa")
            if urpm is not None and utemp is not None and rpm.notna().any():
                mask = (rpm > urpm) & (ot < utemp)
                f = _exceed("Alta potencia con aceite frío", ot_col, ot, mask, df, period, "atencion",
                            f"Se aplicó alta potencia (RPM > {urpm}) con aceite por debajo de la "
                            f"temperatura operativa ({utemp} °F).",
                            f"RPM>{urpm} y OilT<{utemp} °F", regla.get("fuente", fuente))
                if f:
                    findings.append(f)

    # ---- Temp refrigerante --------------------------------------------------
    ct_cfg = motor.get("temp_refrigerante", {})
    ct_col = ct_cfg.get("campo_csv", "Coolant Temp (deg F)")
    ct = numeric(df, ct_col)
    if ct.notna().any():
        stats.append(_stat("Temp refrigerante", ct_col, ct_cfg.get("unidad", "°F"), ct))
        mx = ct_cfg.get("limites", {}).get("max")
        if mx is not None:
            f = _exceed("Temp refrigerante", ct_col, ct, ct > mx, df, period, "violacion",
                        f"Temperatura de refrigerante por encima del máximo ({mx} °F).",
                        f"> {mx} °F", ct_cfg.get("fuente", ""))
            if f:
                findings.append(f)

    # ---- Presión de aceite (condicional según RPM) --------------------------
    op_cfg = motor.get("presion_aceite", {})
    op_col = op_cfg.get("campo_csv", "Oil Press (PSI)")
    op = numeric(df, op_col)
    if op.notna().any():
        # Estadística solo con el motor en marcha (con motor apagado la presión lee ~0/negativa).
        stats.append(_stat("Presión aceite", op_col, op_cfg.get("unidad", "psi"), op.where(motor_on)))
        lim = op_cfg.get("limites", {})
        fuente = op_cfg.get("fuente", "")
        min_low = lim.get("min_por_debajo_3500rpm")
        norm_min = lim.get("normal_por_encima_3500rpm_min")
        norm_max = lim.get("normal_por_encima_3500rpm_max")
        max_frio = lim.get("max_arranque_frio")
        rpm_avail = rpm.notna().any()
        if rpm_avail and min_low is not None:
            mask = motor_on & (rpm < 3500) & (op < min_low)
            f = _exceed("Presión aceite (baja RPM)", op_col, op, mask, df, period, "violacion",
                        f"Presión de aceite por debajo del mínimo ({min_low} psi) con RPM < 3500 "
                        "(motor en marcha).",
                        f"< {min_low} psi @ RPM<3500", fuente)
            if f:
                findings.append(f)
        if rpm_avail and norm_min is not None:
            mask = (rpm >= 3500) & (op < norm_min)
            f = _exceed("Presión aceite (alta RPM)", op_col, op, mask, df, period, "violacion",
                        f"Presión de aceite por debajo del rango normal ({norm_min} psi) con RPM ≥ 3500.",
                        f"< {norm_min} psi @ RPM≥3500", fuente)
            if f:
                findings.append(f)
        if rpm_avail and norm_max is not None and max_frio is not None:
            mask = (rpm >= 3500) & (op > norm_max) & (op <= max_frio)
            f = _exceed("Presión aceite (alta RPM)", op_col, op, mask, df, period, "atencion",
                        f"Presión de aceite por encima del rango normal ({norm_max} psi) con RPM ≥ 3500 "
                        f"(admisible solo transitoriamente / arranque en frío hasta {max_frio} psi).",
                        f"{norm_max}-{max_frio} psi @ RPM≥3500", fuente)
            if f:
                findings.append(f)
        if max_frio is not None:
            f = _exceed("Presión aceite", op_col, op, op > max_frio, df, period, "violacion",
                        f"Presión de aceite por encima del máximo admisible ({max_frio} psi).",
                        f"> {max_frio} psi", fuente)
            if f:
                findings.append(f)

    # ---- EGT por cilindro ---------------------------------------------------
    egt_cfg = motor.get("egt", {})
    egt_cols = egt_cfg.get("campo_csv", [])
    if isinstance(egt_cols, str):
        egt_cols = [egt_cols]
    egt_max = egt_cfg.get("limites", {}).get("max")
    for col in egt_cols:
        s = numeric(df, col)
        if not s.notna().any():
            continue
        stats.append(_stat(f"EGT {col}", col, egt_cfg.get("unidad", "°F"), s))
        if egt_max is not None:
            f = _exceed(f"EGT {col}", col, s, s > egt_max, df, period, "violacion",
                        f"EGT por encima del máximo ({egt_max} °F) en {col}.",
                        f"> {egt_max} °F", egt_cfg.get("fuente", ""))
            if f:
                findings.append(f)

    # ---- Presión de combustible --------------------------------------------
    fp_cfg = motor.get("presion_combustible", {})
    fp_col = fp_cfg.get("campo_csv", "Fuel Press (PSI)")
    fp = numeric(df, fp_col)
    if fp.notna().any():
        stats.append(_stat("Presión combustible", fp_col, fp_cfg.get("unidad", "psi"), fp.where(motor_on)))
        lim = fp_cfg.get("limites", {})
        fuente = fp_cfg.get("fuente", "")
        if lim.get("min") is not None:
            bajo = (fp < lim["min"]).fillna(False)
            if fp_cfg.get("min_requiere_bomba_electrica"):
                oper = _ventana_operacional(df, phase_result)
            else:
                oper = pd.Series(True, index=df.index)
            f = _exceed("Presión combustible", fp_col, fp, bajo & oper, df, period, "violacion",
                        f"Presión de combustible por debajo del mínimo ({lim['min']} psi) en vuelo "
                        "(ventana despegue–aterrizaje, con bomba eléctrica auxiliar obligatoria).",
                        f"< {lim['min']} psi", fuente)
            if f:
                findings.append(f)
            f2 = _exceed("Presión combustible (rodaje/arranque)", fp_col, fp, bajo & ~oper, df, period, "info",
                        f"Presión de combustible por debajo del mínimo ({lim['min']} psi) en rodaje/arranque "
                        "(fuera de la ventana despegue–aterrizaje). Transitorio esperado: la bomba eléctrica "
                        "auxiliar suele estar apagada en tierra y la mecánica sola da presión marginal en "
                        "ralentí. NO es violación.",
                        f"< {lim['min']} psi en rodaje", fuente)
            if f2:
                findings.append(f2)
        if lim.get("max") is not None:
            f = _exceed("Presión combustible", fp_col, fp, fp > lim["max"], df, period, "violacion",
                        f"Presión de combustible por encima del máximo ({lim['max']} psi).",
                        f"> {lim['max']} psi", fuente)
            if f:
                findings.append(f)

    # ---- Informativos motor (sin límite): flujo, alternador, MAP ------------
    for key, label, unit_key in [
        ("flujo_combustible", "Flujo combustible", "unidad"),
        ("map", "MAP", "unidad"),
    ]:
        cfg = motor.get(key, {})
        col = cfg.get("campo_csv")
        if col:
            s = numeric(df, col)
            if s.notna().any():
                stats.append(_stat(label, col, cfg.get(unit_key, ""), s))
    # Consumo estimado del vuelo: integración del flujo de combustible (informativo, PERF08)
    ff = numeric(df, motor.get("flujo_combustible", {}).get("campo_csv", "Fuel Flow (gal/hour)"))
    if ff.notna().any():
        gal = float((ff.fillna(0) * (period / 3600.0)).sum())
        util = limits.get("planificacion", {}).get("sistema_combustible", {}).get("limites", {}).get("utilizable_l")
        util_txt = f" (de {util} L utilizables)" if util else ""
        notas.append(
            f"Consumo estimado del vuelo por integración del flujo de combustible: "
            f"{round(gal, 1)} gal ≈ {round(gal * 3.78541, 1)} L{util_txt}. Informativo (PERF08)."
        )
    alt_cfg = motor.get("alternador", {})
    for ck, lbl, uk in [("campo_csv_voltaje", "Voltaje", "unidad_voltaje"),
                        ("campo_csv_amperaje", "Amperaje alternador", "unidad_amperaje")]:
        col = alt_cfg.get(ck)
        if col:
            s = numeric(df, col)
            if s.notna().any():
                stats.append(_stat(lbl, col, alt_cfg.get(uk, ""), s))

    # ---- IAS / velocidades --------------------------------------------------
    ias_cfg = vuelo.get("ias", {})
    ias_col = ias_cfg.get("campo_csv", "Indicated Airspeed (kt)")
    ias = numeric(df, ias_col)
    if ias.notna().any():
        stats.append(_stat("IAS", ias_col, ias_cfg.get("unidad", "kt"), ias))
        lim = ias_cfg.get("limites", {})
        fuente = ias_cfg.get("fuente", "")
        if lim.get("vne") is not None:
            f = _exceed("IAS vs VNE", ias_col, ias, ias > lim["vne"], df, period, "violacion",
                        f"Velocidad indicada por encima de VNE ({lim['vne']} kt) — nunca exceder.",
                        f"> VNE {lim['vne']} kt", fuente)
            if f:
                findings.append(f)
        if lim.get("vno") is not None and lim.get("vne") is not None:
            f = _exceed("IAS vs VNO", ias_col, ias, (ias > lim["vno"]) & (ias <= lim["vne"]), df, period, "atencion",
                        f"IAS en zona de precaución ({lim['vno']}-{lim['vne']} kt), por encima de VNO. "
                        "Solo en aire calmo y con precaución.",
                        f"VNO {lim['vno']}–VNE {lim['vne']} kt", fuente)
            if f:
                findings.append(f)
        # VFE: solo aplica con flaps extendidos (config. determinada de los datos)
        vfe = lim.get("vfe")
        if vfe is not None and flaps_info.get("disponible"):
            f = _exceed("IAS vs VFE", ias_col, ias, flaps_mask & (ias > vfe), df, period, "violacion",
                        f"Velocidad indicada por encima de VFE ({vfe} kt) con flaps extendidos "
                        "(configuración inferida del sensor).",
                        f"> VFE {vfe} kt con flaps", fuente)
            if f:
                findings.append(f)

    # ---- Velocidad suelo / tasa vertical (info) -----------------------------
    for key, label in [("velocidad_suelo", "Velocidad sobre suelo"), ("tasa_vertical", "Tasa vertical")]:
        cfg = vuelo.get(key, {})
        col = cfg.get("campo_csv")
        if col:
            s = numeric(df, col)
            if s.notna().any():
                stats.append(_stat(label, col, cfg.get("unidad", ""), s))

    # ---- AGL / altura sobre pista ------------------------------------------
    agl_cfg = vuelo.get("agl", {})
    palt_col = agl_cfg.get("campo_csv_base", "Pressure Altitude (ft)")
    palt = numeric(df, palt_col)
    if palt.notna().any():
        # Altura sobre pista usando la referencia detectada del propio vuelo
        # (neutraliza la diferencia entre presión estándar 29.92" y el QNH del día).
        ref = phase_result.referencia_pista_ft
        agl = phase_result.agl
        stats.append(_stat("Altura sobre pista (auto)", f"{palt_col} − ref. {round(ref)} ft", "ft", agl))
        # AGL referido a la elevación oficial (lo que documenta el yaml), a título comparativo
        agl_msl = palt - ELEVACION_AERODROMO_FT
        stats.append(_stat("AGL (vs elev. oficial)", f"{palt_col} − {ELEVACION_AERODROMO_FT} ft", "ft", agl_msl))
        offset = ELEVACION_AERODROMO_FT - ref
        notas.append(
            f"Altura sobre pista calculada con referencia de presión detectada en tierra "
            f"({round(ref)} ft); altura máxima del vuelo: {round(float(agl.max()),0)} ft. "
            f"La altitud de presión en tierra ({round(ref)} ft) difiere {round(offset)} ft de la "
            f"elevación oficial ({ELEVACION_AERODROMO_FT} ft) por la presión del día (29.92\" vs QNH); "
            f"por eso el AGL referido a la elevación oficial aparece corrido ~{round(offset)} ft."
        )

    # ---- Factor de carga (G) -----------------------------------------------
    fc_cfg = vuelo.get("factor_carga", {})
    g_col = fc_cfg.get("campo_csv", "Normal Acceleration (G)")
    g = numeric(df, g_col)
    if g.notna().any():
        stats.append(_stat("Factor de carga normal", g_col, fc_cfg.get("unidad", "g"), g))
        lim = fc_cfg.get("limites", {})
        fuente = fc_cfg.get("fuente", "")
        pos = lim.get("flaps_arriba_pos")
        neg = lim.get("flaps_arriba_neg")
        # Envolvente ESTRUCTURAL (flaps arriba) — siempre válida, exceso = violación inequívoca.
        if pos is not None:
            f = _exceed("Factor de carga +g", g_col, g, g > pos, df, period, "violacion",
                        f"Factor de carga positivo por encima del límite estructural ({pos} g, flaps arriba). "
                        "Aeronave no acrobática.",
                        f"> +{pos} g", fuente)
            if f:
                findings.append(f)
        if neg is not None:
            f = _exceed("Factor de carga −g", g_col, g, g < neg, df, period, "violacion",
                        f"Factor de carga negativo por debajo del límite estructural ({neg} g, flaps arriba). "
                        "Aeronave no acrobática.",
                        f"< {neg} g", fuente)
            if f:
                findings.append(f)
        # Envolvente con flaps extendidos (más estricta) — usa la config. determinada de los datos.
        pos_f = lim.get("flaps_abajo_pos")
        neg_f = lim.get("flaps_abajo_neg")
        if flaps_info.get("disponible") and flaps_info.get("n_muestras_extendido", 0) > 0:
            if pos_f is not None:
                f = _exceed("Factor de carga +g (flaps extendidos)", g_col, g,
                            flaps_mask & (g > pos_f) & (g <= (pos or g.max())), df, period, "violacion",
                            f"Factor de carga por encima del límite con flaps extendidos ({pos_f} g).",
                            f"> +{pos_f} g con flaps", fuente)
                if f:
                    findings.append(f)
            if neg_f is not None:
                f = _exceed("Factor de carga −g (flaps extendidos)", g_col, g,
                            flaps_mask & (g < neg_f) & (g >= (neg or g.min())), df, period, "violacion",
                            f"Factor de carga por debajo del límite con flaps extendidos ({neg_f} g).",
                            f"< {neg_f} g con flaps", fuente)
                if f:
                    findings.append(f)

    # ---- Aceleración lateral (informativo) ---------------------------------
    lat_cfg = vuelo.get("aceleracion_lateral", {})
    lat_col = lat_cfg.get("campo_csv", "Lateral Acceleration (G)")
    lat = numeric(df, lat_col)
    if lat.notna().any():
        stats.append(_stat("Aceleración lateral", lat_col, lat_cfg.get("unidad", "g"), lat))

    # ---- Maniobra: alabeo / cabeceo (maniobras prohibidas) ------------------
    man_cfg = vuelo.get("maniobra", {})
    for key, label, desc in [
        ("alabeo", "Alabeo (roll)", "Ángulo de alabeo"),
        ("cabeceo", "Cabeceo (pitch)", "Actitud de cabeceo"),
    ]:
        cfg = man_cfg.get(key, {})
        col = cfg.get("campo_csv")
        if not col:
            continue
        s = numeric(df, col)
        if not s.notna().any():
            continue
        stats.append(_stat(label, col, cfg.get("unidad", "deg"), s))
        max_abs = cfg.get("limites", {}).get("max_abs")
        if max_abs is not None:
            f = _exceed(label, col, s, s.abs() > max_abs, df, period, "violacion",
                        f"{desc} por encima del límite de maniobra ({max_abs}°). Maniobra prohibida "
                        "(aeronave no acrobática).",
                        f"|{key}| > {max_abs}°", cfg.get("fuente", ""))
            if f:
                findings.append(f)

    # ---- Diagnóstico de motor (EGT spread, MAP/RPM) ------------------------
    diagnostico_motor, diag_findings = _diagnostico_motor(df, motor, period, phase_result)
    findings.extend(diag_findings)

    # ---- Viento cruzado en despegue/aterrizaje -----------------------------
    analisis_viento, viento_findings = _analisis_viento(df, vuelo, phase_result, period)
    findings.extend(viento_findings)

    # ---- Alertas CAS --------------------------------------------------------
    cas_alerts = _cas_alerts(df, avionica, period)

    # ---- AHRS / MISCOMP -----------------------------------------------------
    hdg_cfg = avionica.get("hdg_miscomp", {})
    ahrs_col = hdg_cfg.get("campo_csv", "AHRS/Mag 1 Status")
    if ahrs_col in df.columns:
        vals = df[ahrs_col].dropna().astype(str)
        miscomp = vals[vals.str.contains("MISCOMP", case=False, na=False)]
        if not miscomp.empty:
            notas.append(
                f"Se detectaron {len(miscomp)} muestras con 'MISCOMP' en {ahrs_col} "
                "(discrepancia entre unidades ADAHRS/SFD)."
            )

    # ---- Etiquetar cada hallazgo con la(s) fase(s) donde ocurrió -----------
    for f in findings:
        fases_f: list[str] = []
        for seg in f.segmentos:
            seg.fase = fase_en_timestamp(phase_result.fases, seg.inicio)
            if seg.fase and seg.fase not in fases_f:
                fases_f.append(seg.fase)
        f.fases = fases_f

    metadata = _metadata(log, df)
    metadata["referencia_pista_ft"] = round(phase_result.referencia_pista_ft, 1)
    metadata["eventos"] = phase_result.eventos

    return Findings(
        metadata=metadata,
        fases_vuelo=[_phase_dict(p) for p in phase_result.fases],
        estadisticas=stats,
        hallazgos=findings,
        alertas_cas=cas_alerts,
        diagnostico_motor=diagnostico_motor,
        analisis_flaps=flaps_info,
        analisis_viento=analisis_viento,
        notas=notas,
    )


def _phase_dict(p) -> dict:
    return {
        "indice": p.indice,
        "fase": p.fase,
        "nombre": p.nombre,
        "inicio": p.inicio,
        "fin": p.fin,
        "duracion_s": p.duracion_s,
        "idx_start": p.idx_start,
        "idx_end": p.idx_end,
        "resumen": p.resumen,
    }


def _diagnostico_motor(df: pd.DataFrame, motor: dict, period: float, phase_result) -> tuple[dict, list[Finding]]:
    """EGT spread entre cilindros y relación MAP/RPM (diagnóstico, sin límite de manual)."""
    diag: dict = {}
    findings: list[Finding] = []

    # --- EGT spread ---
    egt_cfg = motor.get("egt", {})
    egt_cols = egt_cfg.get("campo_csv", [])
    if isinstance(egt_cols, str):
        egt_cols = [egt_cols]
    egt_series = {c: numeric(df, c) for c in egt_cols if numeric(df, c).notna().any()}
    if len(egt_series) >= 2:
        d = egt_cfg.get("diagnostico", {})
        rpm = numeric(df, motor.get("rpm", {}).get("campo_csv", "RPM"))
        alta = rpm > d.get("alta_potencia_rpm", 4000)
        egt_df = pd.DataFrame(egt_series)
        spread = egt_df.max(axis=1) - egt_df.min(axis=1)
        spread_alta = spread[alta].dropna()
        medias_alta = egt_df[alta].mean()
        media_grupo = float(medias_alta.mean()) if not medias_alta.empty else None
        desvios = {c: round(float(medias_alta[c] - media_grupo), 0) for c in egt_df.columns} \
            if media_grupo is not None else {}
        # timestamp/fase del spread máximo
        max_ts = None
        if not spread.dropna().empty:
            idx_max = spread.idxmax()
            max_ts = _ts(df, idx_max)
        diag["egt"] = {
            "alta_potencia_rpm": d.get("alta_potencia_rpm", 4000),
            "medias_alta_potencia": {c: round(float(v), 0) for c, v in medias_alta.items()} if not medias_alta.empty else {},
            "spread_media_global": round(float(spread.mean()), 0) if not spread.dropna().empty else None,
            "spread_media_alta_potencia": round(float(spread_alta.mean()), 0) if not spread_alta.empty else None,
            "spread_max": round(float(spread.max()), 0) if not spread.dropna().empty else None,
            "spread_max_ts": max_ts,
            "spread_max_fase": fase_en_timestamp(phase_result.fases, max_ts),
            "cilindro_mas_caliente": str(medias_alta.idxmax()) if not medias_alta.empty else None,
            "cilindro_mas_frio": str(medias_alta.idxmin()) if not medias_alta.empty else None,
            "desvio_por_cilindro": desvios,
        }
        fuente = egt_cfg.get("fuente", "")
        # Atención si la dispersión media en alta potencia supera el umbral
        thr_spread = d.get("spread_atencion_f")
        if thr_spread is not None and not spread_alta.empty and spread_alta.mean() > thr_spread:
            findings.append(_exceed(
                "Dispersión de EGT", "EGT1-4", spread, alta & (spread > thr_spread), df, period,
                "atencion",
                f"Dispersión media entre cilindros en alta potencia ({round(spread_alta.mean())} °F) "
                f"por encima del umbral diagnóstico ({thr_spread} °F).",
                f"spread > {thr_spread} °F", fuente))
        # Atención si un cilindro se aparta del grupo
        thr_dev = d.get("desviacion_cilindro_f")
        if thr_dev is not None and media_grupo is not None:
            for c, dev in desvios.items():
                if abs(dev) > thr_dev:
                    findings.append(Finding(
                        parametro=f"EGT outlier ({c})", campo_csv=c, severidad="atencion",
                        descripcion=f"El cilindro {c} se aparta {dev:+.0f} °F de la media del grupo "
                                    f"en alta potencia (media {round(float(medias_alta[c]))} °F). "
                                    "Posible problema de bujía/carburación/admisión en ese cilindro.",
                        umbral=f"|desvío| > {thr_dev} °F", valor_extremo=round(float(medias_alta[c]), 0),
                        n_muestras=int(alta.sum()), duracion_s=round(int(alta.sum()) * period, 1),
                        fuente=fuente))

    # --- MAP / RPM ---
    map_cfg = motor.get("map", {})
    map_col = map_cfg.get("campo_csv", "Manifold Press (inch Hg)")
    mapp = numeric(df, map_col)
    rpm = numeric(df, motor.get("rpm", {}).get("campo_csv", "RPM"))
    if mapp.notna().any() and rpm.notna().any():
        d = map_cfg.get("diagnostico", {})
        rpm_alto = d.get("alta_potencia_rpm", 4500)
        map_baja = d.get("map_baja_inhg", 18)
        alta = rpm > rpm_alto
        diag["map_rpm"] = {
            "correlacion_map_rpm": round(float(mapp.corr(rpm)), 2),
            "map_media_alta_potencia": round(float(mapp[alta].mean()), 1) if alta.any() else None,
            "map_min_alta_potencia": round(float(mapp[alta].min()), 1) if alta.any() else None,
            "curva_teorica": "PENDIENTE: requiere curva MAP vs RPM del Rotax OM 912 (no disponible).",
        }
        mask = alta & (mapp < map_baja)
        if mask.any():
            findings.append(_exceed(
                "MAP baja con RPM alto", map_col, mapp, mask, df, period, "atencion",
                f"MAP por debajo de {map_baja} inHg con RPM > {rpm_alto} — posible pérdida de potencia "
                "o problema de admisión (heurística diagnóstica, no límite de manual).",
                f"MAP < {map_baja} inHg @ RPM>{rpm_alto}", map_cfg.get("fuente", "")))

    return diag, findings


def _cas_alerts(df: pd.DataFrame, avionica: dict, period: float) -> list[CasAlert]:
    cas_cfg = avionica.get("alertas_cas", {})
    cas_col = cas_cfg.get("campo_csv", "CAS Alert")
    if cas_col not in df.columns:
        return []
    out: list[CasAlert] = []
    sub = df[[cas_col]].copy()
    sub["timestamp"] = df.get("timestamp")
    sub = sub.dropna(subset=[cas_col])
    sub = sub[sub[cas_col].astype(str).str.strip() != ""]
    if sub.empty:
        return []
    for msg, grp in sub.groupby(cas_col):
        ts = grp["timestamp"].dropna() if "timestamp" in grp else pd.Series([], dtype="object")
        out.append(CasAlert(
            mensaje=str(msg),
            n_muestras=len(grp),
            duracion_s=round(len(grp) * period, 1),
            primera=str(ts.min()) if not ts.empty else None,
            ultima=str(ts.max()) if not ts.empty else None,
        ))
    out.sort(key=lambda c: c.n_muestras, reverse=True)
    return out


def _metadata(log: FlightLog, df: pd.DataFrame) -> dict:
    info = log.airframe_info
    return {
        "archivo_log": log.source_path,
        "matricula": info.get("aircraft_ident"),
        "equipo": info.get("product"),
        "unidad": info.get("unit"),
        "version_software": info.get("software_version"),
        "horas_celula": info.get("airframe_hours"),
        "horas_motor": info.get("engine_hours"),
        "muestras": log.n_samples,
        "duracion_s": round(log.duration_s, 1),
        "duracion_hms": _hms(log.duration_s),
        "inicio": str(log.start_time) if log.start_time is not None else None,
        "fin": str(log.end_time) if log.end_time is not None else None,
        "elevacion_aerodromo_ft": ELEVACION_AERODROMO_FT,
    }


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"
