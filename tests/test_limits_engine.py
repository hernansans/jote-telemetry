import pandas as pd

from src.limits_engine import analizar, load_limits

LIMITES_PATH = "docs/limites.yaml"


def _df(valores, columna="Oil Temp (deg F)"):
    return pd.DataFrame({columna: valores})


def _spec(min_=None, max_=None, campo="Oil Temp (deg F)"):
    limites = {}
    if min_ is not None:
        limites["min"] = min_
    if max_ is not None:
        limites["max"] = max_
    return {"motor": {"param_test": {"campo_csv": campo, "unidad": "u", "fuente": "fixture", "limites": limites}}}


def test_detecta_excursion_sobre_el_maximo():
    df = _df([100, 200, 300, 150])
    resultado = analizar(df, _spec(max_=250))
    assert len(resultado.excursiones) == 1
    exc = resultado.excursiones[0]
    assert exc.tipo == "por_encima_del_maximo"
    assert len(exc.filas) == 1
    assert exc.filas.iloc[0]["Oil Temp (deg F)"] == 300


def test_detecta_excursion_bajo_el_minimo():
    df = _df([100, 50, 80])
    resultado = analizar(df, _spec(min_=60))
    assert len(resultado.excursiones) == 1
    exc = resultado.excursiones[0]
    assert exc.tipo == "por_debajo_del_minimo"
    assert len(exc.filas) == 1


def test_sin_excursiones_dentro_de_limites():
    df = _df([100, 110, 120])
    resultado = analizar(df, _spec(min_=50, max_=200))
    assert resultado.excursiones == []


def test_parametro_con_limites_no_simples_queda_pendiente():
    limites_yaml = {
        "motor": {
            "rpm": {
                "campo_csv": "RPM",
                "limites": {"max_continuo": 5500, "max_despegue_transitorio": 5800},
            }
        }
    }
    df = pd.DataFrame({"RPM": [5000, 5400]})
    resultado = analizar(df, limites_yaml)
    assert resultado.excursiones == []
    assert "motor.rpm" in resultado.pendientes


def test_campo_csv_como_lista_evalua_cada_columna():
    limites_yaml = {
        "motor": {
            "egt": {
                "campo_csv": ["EGT1 (deg F)", "EGT2 (deg F)"],
                "unidad": "°F",
                "fuente": "fixture",
                "limites": {"max": 1000},
            }
        }
    }
    df = pd.DataFrame({"EGT1 (deg F)": [900, 1100], "EGT2 (deg F)": [950, 960]})
    resultado = analizar(df, limites_yaml)
    assert len(resultado.excursiones) == 1
    assert resultado.excursiones[0].campo_csv == "EGT1 (deg F)"


def test_load_limits_real_yaml_no_lanza_y_tiene_categorias_esperadas():
    limites = load_limits(LIMITES_PATH)
    assert "motor" in limites
    assert "vuelo" in limites
    assert "avionica" in limites
