import math
import re

import pandas as pd

# ============================================================
# Garmin G3X/GDU CSV loading, metadata, and per-frame sampling
# ============================================================

# Columns coerced to numeric on load. Anything not listed stays as text.
NUMERIC_COLUMNS = [
    "GPS Ground Speed (kt)",
    "GPS Ground Track (deg)",
    "GPS Altitude (ft)",
    "Baro Altitude (ft)",
    "Vertical Speed (ft/min)",
    "Wind Speed (kt)",
    "Wind Direction (deg)",
    "Indicated Airspeed (kt)",
    "True Airspeed (kt)",
    "Magnetic Heading (deg)",
    "Pitch (deg)",
    "Roll (deg)",
    "Lateral Acceleration (G)",
    "Normal Acceleration (G)",
    "RPM",
    "Oil Press (PSI)",
    "Oil Temp (deg F)",
    "Coolant Temp (deg F)",
    "Fuel Flow (gal/hour)",
    "Volts",
    "EGT1 (deg F)",
    "EGT2 (deg F)",
    "EGT3 (deg F)",
    "EGT4 (deg F)",
    "Flap Position",
    "Manifold Press (inch Hg)",
    "Alt Amps",
    "Fuel Press (PSI)",
    "Outside Air Temp (deg C)",
]


def read_airframe_info(csv_path):
    """Parse the leading '#airframe_info,...' metadata line into a dict.

    Returns an empty dict if the line is absent.
    """
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        first_line = f.readline().strip()

    if not first_line.startswith("#airframe_info"):
        return {}

    pairs = re.findall(r'(\w+)=("[^"]*"|[^,]+)', first_line)
    return {key: value.strip('"') for key, value in pairs}


def load_garmin_log(csv_path):
    """Read the Garmin CSV, skipping the leading metadata block."""
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    header_row = None
    for i, line in enumerate(lines):
        if line.startswith("Date (yyyy-mm-dd)"):
            header_row = i
            break

    if header_row is None:
        raise RuntimeError("Could not find the Garmin header row.")

    df = pd.read_csv(csv_path, skiprows=header_row)

    # Garmin's second row holds short names like Lcl Date, IAS, RPM, etc.
    # It is not flight data, so we drop it.
    df = df.iloc[1:].reset_index(drop=True)

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def default_title(csv_path, df):
    """Build a default title from data already in the log.

    Combines the aircraft identifier with the flight date when available.
    """
    info = read_airframe_info(csv_path)
    ident = info.get("aircraft_ident", "").strip()

    date = ""
    if "Date (yyyy-mm-dd)" in df.columns and len(df):
        date = str(safe(df.iloc[0], "Date (yyyy-mm-dd)", "")).strip()

    parts = [part for part in (ident, date) if part]
    return " · ".join(parts) if parts else "TELEMETRY HUD"


# -------------------------
# Unit transforms (referenced by name from templates)
# -------------------------
def _fahrenheit_to_celsius(value):
    return (value - 32) * 5 / 9


def _gph_to_lph(value):
    return value * 3.78541


TRANSFORMS = {
    "identity": lambda v: v,
    "fahrenheit_to_celsius": _fahrenheit_to_celsius,
    "gph_to_lph": _gph_to_lph,
}


# -------------------------
# Helpers
# -------------------------
def safe(row, col, default=None):
    """Read a cell without crashing if the column is missing or empty."""
    if col not in row:
        return default
    val = row[col]
    if pd.isna(val):
        return default
    return val


def fmt(val, dec=0, default="---"):
    """Short numeric format for on-screen values."""
    if val is None or pd.isna(val):
        return default
    try:
        return f"{val:.{dec}f}"
    except (TypeError, ValueError):
        return default


# -------------------------
# Per-frame sampling
# -------------------------
class FrameData:
    """Interpolated access to the log at a given video frame.

    Picks the two bracketing log samples for the frame's timestamp and
    interpolates between them so motion is smooth above the log's sample rate.
    """

    def __init__(self, df, frame, fps, offset_seconds):
        t_log = frame / fps + offset_seconds
        idx0 = int(math.floor(t_log))
        idx1 = idx0 + 1
        self.frac = t_log - idx0

        idx0 = max(0, idx0)
        idx1 = min(idx1, len(df) - 1)

        self.row0 = df.iloc[idx0]
        self.row1 = df.iloc[idx1]

    def value(self, col, transform="identity", angular=False, default=None):
        """Interpolated numeric value for a column, optionally transformed."""
        v = self._interp_angle(col) if angular else self._interp(col)
        if v is None:
            return default
        return TRANSFORMS.get(transform, TRANSFORMS["identity"])(v)

    def text(self, col, default="---"):
        """Raw (non-numeric) value, taken from the first bracketing sample."""
        return safe(self.row0, col, default)

    def _interp(self, col):
        v0 = safe(self.row0, col)
        v1 = safe(self.row1, col)
        if v0 is None:
            return v1
        if v1 is None:
            return v0
        return v0 + (v1 - v0) * self.frac

    def _interp_angle(self, col):
        a0 = safe(self.row0, col)
        a1 = safe(self.row1, col)
        if a0 is None:
            return a1
        if a1 is None:
            return a0
        delta = ((a1 - a0 + 540) % 360) - 180
        return (a0 + delta * self.frac) % 360
