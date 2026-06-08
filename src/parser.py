"""Parser para los logs CSV exportados por el GDU 460 (Garmin G3X Touch).

Estructura del archivo:
  línea 1: metadata del vuelo, formato `#airframe_info,clave="valor",...`
  línea 2: encabezado con nombres completos de columna (los que usamos)
  línea 3: alias cortos de columna (se descarta)
  línea 4+: datos, una fila por segundo
"""
import re
import pandas as pd

_METADATA_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def parse_metadata(first_line: str) -> dict:
    """Extrae los pares clave="valor" de la línea `#airframe_info`."""
    return dict(_METADATA_PATTERN.findall(first_line))


def load_log(path: str) -> tuple[dict, pd.DataFrame]:
    """Carga un log del GDU 460 y devuelve (metadata, DataFrame).

    El DataFrame conserva los nombres de columna completos del CSV
    (p. ej. "Indicated Airspeed (kt)"), que son los mismos que se referencian
    en `docs/limites.yaml` bajo `campo_csv`.
    """
    with open(path, encoding="utf-8") as f:
        first_line = f.readline()

    metadata = parse_metadata(first_line)
    df = pd.read_csv(path, skiprows=1, header=0)
    df = df.drop(index=0).reset_index(drop=True)  # descarta la fila de alias cortos

    return metadata, df
