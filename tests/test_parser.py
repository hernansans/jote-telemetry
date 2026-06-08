from pathlib import Path

from src.parser import load_log, parse_metadata

FIXTURE = Path(__file__).parent / "fixtures" / "log_sintetico_ejemplo.csv"


def test_parse_metadata():
    line = '#airframe_info,log_version="1.00",product="GDU 460",aircraft_ident="TEST 0000",airframe_hours="4.7"'
    meta = parse_metadata(line)
    assert meta["product"] == "GDU 460"
    assert meta["aircraft_ident"] == "TEST 0000"
    assert meta["airframe_hours"] == "4.7"


def test_load_log_metadata():
    metadata, _ = load_log(FIXTURE)
    assert metadata["product"] == "GDU 460"
    assert metadata["aircraft_ident"] == "TEST 0000"


def test_load_log_dataframe_has_expected_columns():
    _, df = load_log(FIXTURE)
    for col in [
        "Indicated Airspeed (kt)",
        "Pressure Altitude (ft)",
        "RPM",
        "Oil Temp (deg F)",
        "Coolant Temp (deg F)",
        "EGT1 (deg F)",
        "CAS Alert",
    ]:
        assert col in df.columns


def test_load_log_dataframe_row_count():
    _, df = load_log(FIXTURE)
    assert len(df) == 5


def test_load_log_values_are_numeric_where_expected():
    _, df = load_log(FIXTURE)
    rpm = df["RPM"].astype(float)
    assert (rpm == 5400).all()
    ias = df["Indicated Airspeed (kt)"].astype(float)
    assert ias.iloc[0] == 75
    assert ias.iloc[-1] == 79
