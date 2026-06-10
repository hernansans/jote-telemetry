"""Parser del log CSV exportado por el GDU 460 (G3X Touch).

Estructura del archivo:
    línea 1  -> #airframe_info,clave="valor",...    (metadatos del equipo/aeronave)
    línea 2  -> nombres completos de columna         (header real, p.ej. "Oil Temp (deg F)")
    línea 3  -> nombres cortos / unidades            (p.ej. "E1 OilT")  -> se descarta
    línea 4+ -> muestras (1 Hz)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class FlightLog:
    df: pd.DataFrame
    airframe_info: dict[str, str] = field(default_factory=dict)
    source_path: str = ""

    @property
    def n_samples(self) -> int:
        return len(self.df)

    @property
    def duration_s(self) -> float:
        if "timestamp" not in self.df or self.df["timestamp"].isna().all():
            return float(self.n_samples)  # asume 1 Hz
        span = self.df["timestamp"].max() - self.df["timestamp"].min()
        return float(span.total_seconds())

    @property
    def start_time(self):
        if "timestamp" in self.df and not self.df["timestamp"].isna().all():
            return self.df["timestamp"].min()
        return None

    @property
    def end_time(self):
        if "timestamp" in self.df and not self.df["timestamp"].isna().all():
            return self.df["timestamp"].max()
        return None


def _parse_airframe_info(line: str) -> dict[str, str]:
    line = line.lstrip("#").strip()
    # quita un prefijo tipo "airframe_info," si está presente
    line = re.sub(r"^airframe_info\s*,", "", line)
    info: dict[str, str] = {}
    for key, val in re.findall(r'(\w+)\s*=\s*"([^"]*)"', line):
        info[key] = val
    return info


def load_log(path: str | Path) -> FlightLog:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        first_line = fh.readline()

    airframe_info = _parse_airframe_info(first_line) if first_line.startswith("#") else {}

    # Salta la línea de metadatos (0) y la fila de nombres cortos/unidades (2).
    # La fila 1 (nombres completos) queda como header.
    df = pd.read_csv(
        path,
        skiprows=[0, 2],
        dtype=str,
        keep_default_na=False,
        na_values=[""],
    )
    df.columns = [c.strip() for c in df.columns]

    df = _add_timestamp(df)
    return FlightLog(df=df, airframe_info=airframe_info, source_path=str(path))


def _add_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    date_col = _find(df, "Date (yyyy-mm-dd)", "Date")
    time_col = _find(df, "Time (hh:mm:ss)", "Time")
    if date_col and time_col:
        ts = pd.to_datetime(
            df[date_col].astype(str) + " " + df[time_col].astype(str),
            errors="coerce",
        )
        df = df.copy()
        df["timestamp"] = ts
    return df


def _find(df: pd.DataFrame, *candidates: str) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """Devuelve la columna como float, con no-numéricos a NaN."""
    if col not in df.columns:
        return pd.Series([float("nan")] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")
