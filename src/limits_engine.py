"""Motor de comparación: contrasta los datos de un log contra docs/limites.yaml.

v1 — alcance simple e intencional: solo evalúa límites declarados como `min` y/o
`max` directos (límites absolutos de un solo valor). Otros tipos de límite —
RPM transitorio, presión de aceite dependiente de RPM, IAS contra VNE/VNO/VA
según fase de vuelo, curva MAP, etc. — requieren lógica específica por
parámetro y se reportan como "pendiente" en lugar de evaluarse de forma
incorrecta con una regla genérica que no aplica.
"""
from dataclasses import dataclass, field

import pandas as pd
import yaml


@dataclass
class Excursion:
    """Una franja de filas donde un parámetro cruzó un límite simple."""
    parametro: str
    campo_csv: str
    tipo: str          # "por_debajo_del_minimo" | "por_encima_del_maximo"
    limite: float
    unidad: str
    fuente: str
    filas: pd.DataFrame  # subconjunto del log con las filas en excursión


@dataclass
class ResultadoAnalisis:
    excursiones: list[Excursion] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)  # parámetros con límites no-simples


def load_limits(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_alta_potencia_sin_temp_operativa(nombre: str, regla: dict, df: pd.DataFrame) -> list[Excursion]:
    """Regla compuesta: alerta si RPM supera el umbral de "alta potencia" antes
    de que el aceite alcance su temperatura de operación normal.

    Es un proxy operacional definido por el constructor para "desde la prueba
    de magnetos en adelante" — ver docs/limites.yaml -> regla_alta_potencia_sin_temp_operativa
    y memory/fases-de-vuelo.md.
    """
    campo_rpm = regla.get("campo_csv_rpm")
    campo_temp = regla.get("campo_csv_temp")
    if campo_rpm not in df.columns or campo_temp not in df.columns:
        return []

    rpm = pd.to_numeric(df[campo_rpm], errors="coerce")
    temp = pd.to_numeric(df[campo_temp], errors="coerce")
    mask = (rpm > regla["umbral_rpm"]) & (temp < regla["umbral_temp_operativa"])
    filas = df[mask]
    if filas.empty:
        return []

    return [Excursion(
        parametro=nombre,
        campo_csv=f"{campo_rpm} + {campo_temp}",
        tipo="alta_potencia_sin_temperatura_operativa",
        limite=regla["umbral_temp_operativa"],
        unidad="",
        fuente=regla.get("fuente", ""),
        filas=filas,
    )]


def _check_param(nombre: str, spec: dict, df: pd.DataFrame) -> tuple[list[Excursion], bool]:
    """Evalúa un parámetro. Devuelve (excursiones, tiene_limites_simples)."""
    limites = spec.get("limites") or {}
    campo = spec.get("campo_csv")
    excursiones: list[Excursion] = []

    simples = {k: v for k, v in limites.items() if k in ("min", "max")}
    if not simples or not campo or campo not in df.columns:
        return excursiones, bool(simples)

    valores = pd.to_numeric(df[campo], errors="coerce")

    if "min" in simples:
        bajo = df[valores < simples["min"]]
        if not bajo.empty:
            excursiones.append(Excursion(
                parametro=nombre, campo_csv=campo, tipo="por_debajo_del_minimo",
                limite=simples["min"], unidad=spec.get("unidad", ""),
                fuente=spec.get("fuente", ""), filas=bajo,
            ))

    if "max" in simples:
        sobre = df[valores > simples["max"]]
        if not sobre.empty:
            excursiones.append(Excursion(
                parametro=nombre, campo_csv=campo, tipo="por_encima_del_maximo",
                limite=simples["max"], unidad=spec.get("unidad", ""),
                fuente=spec.get("fuente", ""), filas=sobre,
            ))

    return excursiones, True


def analizar(df: pd.DataFrame, limites_yaml: dict) -> ResultadoAnalisis:
    """Recorre todas las categorías/parámetros de limites.yaml y compara contra el log.

    `campo_csv` puede ser una lista (p. ej. EGT por cilindro): se evalúa cada
    columna de la lista como una instancia independiente del mismo parámetro.
    """
    resultado = ResultadoAnalisis()

    for categoria, parametros in limites_yaml.items():
        if not isinstance(parametros, dict):
            continue
        for nombre, spec in parametros.items():
            if not isinstance(spec, dict):
                continue

            regla_alta_potencia = spec.get("regla_alta_potencia_sin_temp_operativa")
            if regla_alta_potencia:
                resultado.excursiones.extend(
                    _check_alta_potencia_sin_temp_operativa(
                        f"{categoria}.{nombre}.alta_potencia_sin_temp_operativa", regla_alta_potencia, df
                    )
                )

            campo = spec.get("campo_csv")
            campos = campo if isinstance(campo, list) else [campo]
            limites = spec.get("limites") or {}
            simples = {k: v for k, v in limites.items() if k in ("min", "max")}
            no_simples = {k: v for k, v in limites.items() if k not in ("min", "max")}

            evaluado = False
            for c in campos:
                if c is None:
                    continue
                spec_individual = dict(spec, campo_csv=c)
                excursiones, tiene_simples = _check_param(f"{categoria}.{nombre}", spec_individual, df)
                resultado.excursiones.extend(excursiones)
                evaluado = evaluado or (tiene_simples and c in df.columns)

            if no_simples and not simples:
                resultado.pendientes.append(f"{categoria}.{nombre}")
            elif simples and not evaluado:
                resultado.pendientes.append(f"{categoria}.{nombre} (columna no encontrada en el log)")

    return resultado
