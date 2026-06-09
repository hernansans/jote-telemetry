"""
EIS panel widget — Garmin G3X style, compact square block (per PARAMETRODEMOTOR.png).

Layout (top → bottom):
  ┌────────────────────────────────────────┐
  │        (MAP dial)   (RPM dial)         │   <- centred
  │                                        │
  │     FUEL GPH   OIL PSI   OIL °F        │   <- compact bars, centred
  │       6.2        45        162         │
  ├────────────────────────────────────────┤
  │  EGT °F            │   CHT °F   AMPS   │
  │  ▐1 ▐2 ▐3 ▐4       │    198      7     │
  │                    │   FLAP    VOLTS   │
  │ 1494 1425 1371 1319│    17°     14.0   │
  └────────────────────────────────────────┘

x, y, width, height define the bounding box (origin = bottom-left).
"""
import math
from matplotlib.patches import Circle, Rectangle
from ..data import fmt
from .base import Widget, register

_BG    = (0.07, 0.07, 0.07, 0.93)
_GREEN = "#2fb24a"
_YELL  = "#e8c220"
_RED   = "#cc2222"
_WHITE = "white"
_CYAN  = "#00d4ff"
_DIM   = (1, 1, 1, 0.55)


def _f2c(v):
    """Fahrenheit -> Celsius (used for CHT, EGT, Oil Temp display)."""
    return (v - 32) * 5.0 / 9.0


def _dial_a(frac, start=220, sweep=280):
    return math.radians(start - max(0., min(1., frac)) * sweep)


def _dial_static(ax, cx, cy, r, bands, vmin, vmax, label, z=3,
                 start=220, sweep=280):
    ax.add_patch(Circle((cx, cy), r+2, color=_BG, zorder=z))
    ax.add_patch(Circle((cx, cy), r, fill=False,
                        edgecolor="white", linewidth=1.6, zorder=z+1))
    for v0, v1, color in bands:
        for i in range(40):
            a0 = _dial_a((v0+(v1-v0)*i/40    -vmin)/(vmax-vmin), start, sweep)
            a1 = _dial_a((v0+(v1-v0)*(i+1)/40-vmin)/(vmax-vmin), start, sweep)
            ax.plot([cx+math.cos(a0)*(r-7), cx+math.cos(a1)*(r-7)],
                    [cy+math.sin(a0)*(r-7), cy+math.sin(a1)*(r-7)],
                    color=color, linewidth=6, solid_capstyle="butt", zorder=z+1)
    for i in range(6):
        a = _dial_a(i/5, start, sweep)
        ax.plot([cx+math.cos(a)*(r-9), cx+math.cos(a)*r],
                [cy+math.sin(a)*(r-9), cy+math.sin(a)*r],
                color="white", linewidth=1.3, zorder=z+2)
    ax.text(cx, cy+r*0.32, label, fontsize=8, color=_DIM,
            ha="center", va="center", weight="bold", zorder=z+5)


def _hbar_static(ax, x, y, w, h, vmin, vmax, bands, label, z=3):
    ax.add_patch(Rectangle((x, y), w, h, color=(0,0,0,.65), zorder=z))
    for v0, v1, c in bands:
        x0 = x + (max(v0,vmin)-vmin)/(vmax-vmin)*w
        x1 = x + (min(v1,vmax)-vmin)/(vmax-vmin)*w
        ax.add_patch(Rectangle((x0, y+1), x1-x0, h-2, color=c, zorder=z+1))
    ax.add_patch(Rectangle((x, y), w, h, fill=False,
                            edgecolor=(1,1,1,.28), linewidth=.7, zorder=z+2))
    ax.text(x + w/2, y+h+2, label, fontsize=6.5, color=_DIM,
            ha="center", va="bottom", weight="bold", zorder=z+3)


@register
class DialGauge(Widget):
    """Standalone circular dial in the same EIS style as MAP/RPM.

    Config keys: x, y, r, source, vmin, vmax, label, bands, unit, decimals.
    Bands: list of [v0, v1, color] — same format as eis_panel bands.
    """
    type = "dial_gauge"

    def draw_static(self, ax):
        self._cx    = self.get("x", 100)
        self._cy    = self.get("y", 100)
        self._r     = self.get("r", 69)
        self._vmin  = self.get("vmin", 0)
        self._vmax  = self.get("vmax", 100)
        self._start = self.get("start", 220)
        self._sweep = self.get("sweep", 280)
        _dial_static(ax, self._cx, self._cy, self._r,
                     bands=self.get("bands", []),
                     vmin=self._vmin, vmax=self._vmax,
                     label=self.get("label", ""),
                     z=3, start=self._start, sweep=self._sweep)

    def create_dynamic(self, ax):
        cx, cy, r = self._cx, self._cy, self._r
        self._needle, = ax.plot([cx]*2, [cy]*2,
                                color=_WHITE, linewidth=2.4,
                                solid_capstyle="round", zorder=8)
        ax.add_patch(Circle((cx, cy), 3.5, color=_WHITE, zorder=9))
        self._value = ax.text(cx, cy - r * 0.48, "",
                              fontsize=self.get("value_size", 11),
                              color=_WHITE, weight="bold",
                              ha="center", va="center", zorder=10)

    def update(self, fd):
        val  = fd.value(self.get("source"), default=0) or 0
        unit = self.get("unit", "")
        decs = self.get("decimals", 0)
        frac = max(0., min(1., (val - self._vmin) / (self._vmax - self._vmin)))
        a    = _dial_a(frac, self._start, self._sweep)
        cx, cy, r = self._cx, self._cy, self._r
        nx = cx + math.cos(a) * (r - 12)
        ny = cy + math.sin(a) * (r - 12)
        self._needle.set_data([cx, nx], [cy, ny])
        self._value.set_text(f"{fmt(val, decs)}{unit}")


@register
class EisPanel(Widget):
    type = "eis_panel"

    def _geo(self):
        x = self.get("x", 1480)
        y = self.get("y", 0)
        w = self.get("width", 440)
        h = self.get("height", 400)
        cx_panel = x + w/2

        # Three stacked bands.
        dial_band_h = h * 0.40
        bar_band_h  = h * 0.20
        low_band_h  = h - dial_band_h - bar_band_h

        bar_band_y0  = y + low_band_h
        dial_band_y0 = bar_band_y0 + bar_band_h

        # ---- Dial band: MAP / RPM, centred -------------------------------------
        r = 69
        dial_cy = dial_band_y0 + dial_band_h * 0.46
        gap = 26
        rpm_cx = cx_panel + gap/2 + r
        map_cx = cx_panel - gap/2 - r

        # ---- Bar band: FUEL / OIL PSI / OIL °F, compact & centred --------------
        bar_h = 14
        bar_w = 70
        bar_gap = 18
        bars_total_w = bar_w*3 + bar_gap*2
        fuel_x = cx_panel - bars_total_w/2
        oilp_x = fuel_x + bar_w + bar_gap
        oilt_x = oilp_x + bar_w + bar_gap
        bar_y  = bar_band_y0 + bar_band_h * 0.30

        # ---- Lower band: EGT (left half) | 2x2 grid (right half) ---------------
        mid_x = cx_panel
        ax_div_y0 = y
        ax_div_y1 = y + low_band_h

        egt_bar_w   = 28
        egt_bar_gap = 10
        egt_total_w = 4*egt_bar_w + 3*egt_bar_gap
        egt_x0      = x + (mid_x - x - egt_total_w) / 2
        egt_base_y  = low_band_h * 0.30 + y
        egt_max_h   = low_band_h * 0.50
        egt_label_y = egt_base_y + egt_max_h + 14

        # 2x2 grid on the right half: CHT|AMPS (top row), FLAP|VOLTS (bottom row)
        grid_cx0 = mid_x + (x + w - mid_x) * 0.30
        grid_cx1 = mid_x + (x + w - mid_x) * 0.72
        grid_row_top = y + low_band_h * 0.74
        grid_row_bot = y + low_band_h * 0.30
        grid_label_dy = 17

        return dict(
            x=x, y=y, w=w, h=h, cx_panel=cx_panel,
            dial_band_y0=dial_band_y0, dial_band_h=dial_band_h,
            bar_band_y0=bar_band_y0, bar_band_h=bar_band_h,
            low_band_h=low_band_h,
            r=r, dial_cy=dial_cy, map_cx=map_cx, rpm_cx=rpm_cx,
            bar_y=bar_y, bar_h=bar_h, bar_w=bar_w,
            fuel_x=fuel_x, oilp_x=oilp_x, oilt_x=oilt_x,
            mid_x=mid_x,
            egt_x0=egt_x0, egt_bar_w=egt_bar_w, egt_bar_gap=egt_bar_gap,
            egt_base_y=egt_base_y, egt_max_h=egt_max_h, egt_label_y=egt_label_y,
            grid_cx0=grid_cx0, grid_cx1=grid_cx1,
            grid_row_top=grid_row_top, grid_row_bot=grid_row_bot,
            grid_label_dy=grid_label_dy,
        )

    # ── static ────────────────────────────────────────────────────────────────

    def draw_static(self, ax):
        g = self._geo()
        x, y, w, h = g["x"], g["y"], g["w"], g["h"]

        # Background panel only behind the lower band (EGT / CHT / AMPS / FLAP /
        # VOLTS). The dial band (MAP/RPM) and bar band (FUEL L/H, OIL PSI,
        # OIL °C) render directly over the video — no backing panel — per the
        # approved "main" refinement.
        low_y0 = g["bar_band_y0"]
        ax.add_patch(Rectangle((x, y), w, low_y0 - y, color=_BG, zorder=1))
        ax.add_patch(Rectangle((x, y), w, low_y0 - y, fill=False,
                                edgecolor=(1,1,1,.18), linewidth=1, zorder=2))
        # column separator inside the lower band only
        ax.plot([g["mid_x"], g["mid_x"]], [y+10, low_y0-10],
                color=(1,1,1,.13), linewidth=.8, zorder=2)

        # ── Dials ─────────────────────────────────────────────────────────────
        _dial_static(ax, g["map_cx"], g["dial_cy"], g["r"],
                     bands=[(10,25,_GREEN),(25,28,_YELL),(28,30,_RED)],
                     vmin=10, vmax=30, label="MAN IN")
        _dial_static(ax, g["rpm_cx"], g["dial_cy"], g["r"],
                     bands=[(0,5500,_GREEN),(5500,5800,_YELL),(5800,6200,_RED)],
                     vmin=0, vmax=6200, label="RPM")

        # ── Bars (metric units: L/h, °C) ──────────────────────────────────────
        _hbar_static(ax, g["fuel_x"], g["bar_y"], g["bar_w"], g["bar_h"],
                     0, 76, [(0,45,_GREEN),(45,64,_YELL),(64,76,_RED)], "FUEL L/H")
        _hbar_static(ax, g["oilp_x"], g["bar_y"], g["bar_w"], g["bar_h"],
                     0, 120, [(0,25,_RED),(25,55,_YELL),(55,95,_GREEN),(95,120,_YELL)], "OIL PSI")
        _hbar_static(ax, g["oilt_x"], g["bar_y"], g["bar_w"], g["bar_h"],
                     38, 138, [(38,82,_GREEN),(82,110,_YELL),(110,138,_RED)], "OIL °C")

        # ── EGT slots (left half of lower band) ──────────────────────────────
        for i in range(4):
            ex = g["egt_x0"] + i*(g["egt_bar_w"]+g["egt_bar_gap"])
            ax.add_patch(Rectangle((ex, g["egt_base_y"]),
                                    g["egt_bar_w"], g["egt_max_h"],
                                    color=(0,0,0,.5), zorder=2))
            ax.add_patch(Rectangle((ex, g["egt_base_y"]),
                                    g["egt_bar_w"], g["egt_max_h"],
                                    fill=False, edgecolor=(1,1,1,.2),
                                    linewidth=.6, zorder=3))
        ax.text(g["egt_x0"] + (4*g["egt_bar_w"]+3*g["egt_bar_gap"])/2,
                g["egt_label_y"], "EGT °C", fontsize=7.5, color=_DIM,
                ha="center", va="bottom", weight="bold", zorder=3)

        # ── 2x2 grid labels (right half of lower band) ───────────────────────
        dy = g["grid_label_dy"]
        for lbl, gx, gy in [("CHT °C",  g["grid_cx0"], g["grid_row_top"]),
                            ("AMPS",    g["grid_cx1"], g["grid_row_top"]),
                            ("FLAP",    g["grid_cx0"], g["grid_row_bot"]),
                            ("VOLTS",   g["grid_cx1"], g["grid_row_bot"])]:
            ax.text(gx, gy+dy, lbl, fontsize=7.5, color=_DIM,
                    ha="center", va="bottom", weight="bold", zorder=3)

    # ── dynamic ───────────────────────────────────────────────────────────────

    def create_dynamic(self, ax):
        g = self._geo()
        cy, r = g["dial_cy"], g["r"]
        by, bh, bw = g["bar_y"], g["bar_h"], g["bar_w"]
        kn = dict(color=_WHITE, linewidth=2.4, solid_capstyle="round", zorder=8)
        kp = dict(color=_CYAN,  linewidth=2, zorder=8)

        # MAP / RPM dials
        self._map_n, = ax.plot([g["map_cx"]]*2, [cy]*2, **kn)
        ax.add_patch(Circle((g["map_cx"], cy), 3.5, color=_WHITE, zorder=9))
        self._map_v = ax.text(g["map_cx"], cy-r*.48, "",
                              fontsize=11, color=_WHITE, weight="bold",
                              ha="center", va="center", zorder=10)

        self._rpm_n, = ax.plot([g["rpm_cx"]]*2, [cy]*2, **kn)
        ax.add_patch(Circle((g["rpm_cx"], cy), 3.5, color=_WHITE, zorder=9))
        self._rpm_v = ax.text(g["rpm_cx"], cy-r*.48, "",
                              fontsize=11, color=_WHITE, weight="bold",
                              ha="center", va="center", zorder=10)

        def _ptr(bx):
            l, = ax.plot([bx, bx], [by-5, by+bh+5], **kp)
            t  = ax.text(bx+bw/2, by-5, "", fontsize=9, color=_WHITE,
                         weight="bold", ha="center", va="top", zorder=10)
            return l, t

        self._fuel_p, self._fuel_v = _ptr(g["fuel_x"])
        self._oilp_p, self._oilp_v = _ptr(g["oilp_x"])
        self._oilt_p, self._oilt_v = _ptr(g["oilt_x"])

        # EGT vertical bars + per-cylinder values
        self._egt_bars, self._egt_vals = [], []
        for i in range(4):
            ex = g["egt_x0"] + i*(g["egt_bar_w"]+g["egt_bar_gap"])
            bar = ax.add_patch(Rectangle(
                (ex+2, g["egt_base_y"]+1), g["egt_bar_w"]-4, 0,
                color=_GREEN, zorder=4))
            val = ax.text(ex+g["egt_bar_w"]/2, g["egt_base_y"]-3, "",
                          fontsize=7, color=_WHITE, weight="bold",
                          ha="center", va="top", zorder=10)
            self._egt_bars.append(bar)
            self._egt_vals.append(val)

        # 2x2 grid values
        def _gridval(gx, gy):
            return ax.text(gx, gy, "", fontsize=14, color=_WHITE,
                           weight="bold", ha="center", va="top", zorder=10)

        self._cht   = _gridval(g["grid_cx0"], g["grid_row_top"])
        self._amps  = _gridval(g["grid_cx1"], g["grid_row_top"])
        self._flap  = _gridval(g["grid_cx0"], g["grid_row_bot"])
        self._volts = _gridval(g["grid_cx1"], g["grid_row_bot"])

    def update(self, fd):
        g = self._geo()
        cy, r = g["dial_cy"], g["r"]
        by, bh, bw = g["bar_y"], g["bar_h"], g["bar_w"]

        def _px(bx, vmin, vmax, v):
            return bx + max(0., min(1., (v-vmin)/(vmax-vmin))) * bw

        v = fd.value("Manifold Press (inch Hg)", default=15) or 15
        a = _dial_a((v-10)/20)
        self._map_n.set_data([g["map_cx"], g["map_cx"]+math.cos(a)*(r-12)],
                              [cy,          cy+math.sin(a)*(r-12)])
        self._map_v.set_text(f"{v:.1f}")

        v = fd.value("RPM", default=0) or 0
        a = _dial_a(v/6200)
        self._rpm_n.set_data([g["rpm_cx"], g["rpm_cx"]+math.cos(a)*(r-12)],
                              [cy,          cy+math.sin(a)*(r-12)])
        self._rpm_v.set_text(f"{int(v)}")

        # Fuel flow: gal/hour -> L/hour
        v = (fd.value("Fuel Flow (gal/hour)", default=0) or 0) * 3.78541
        px = _px(g["fuel_x"], 0, 76, v)
        self._fuel_p.set_data([px,px],[by-5,by+bh+5]); self._fuel_v.set_text(f"{v:.1f}")

        v = fd.value("Oil Press (PSI)", default=0) or 0
        px = _px(g["oilp_x"], 0, 120, v)
        self._oilp_p.set_data([px,px],[by-5,by+bh+5]); self._oilp_v.set_text(f"{int(v)}")

        # Oil temp: °F -> °C
        v = _f2c(fd.value("Oil Temp (deg F)", default=32) or 32)
        px = _px(g["oilt_x"], 38, 138, v)
        self._oilt_p.set_data([px,px],[by-5,by+bh+5]); self._oilt_v.set_text(f"{int(v)}")

        # EGT: °F -> °C  (thresholds 1500°F≈816°C green/yellow, 1650°F≈899°C yellow/red)
        EGT_MIN, EGT_MAX = 316, 982
        for i, (bar, val) in enumerate(zip(self._egt_bars, self._egt_vals)):
            v = _f2c(fd.value(f"EGT{i+1} (deg F)", default=600) or 600)
            frac = max(0., min(1., (v-EGT_MIN)/(EGT_MAX-EGT_MIN)))
            bh_egt = frac * g["egt_max_h"]
            ex = g["egt_x0"] + i*(g["egt_bar_w"]+g["egt_bar_gap"])
            bar.set_bounds(ex+2, g["egt_base_y"]+1, g["egt_bar_w"]-4, bh_egt)
            bar.set_facecolor(_GREEN if v < 816 else (_YELL if v < 899 else _RED))
            val.set_text(f"{int(v)}")

        # CHT: °F -> °C
        v = _f2c(fd.value("Coolant Temp (deg F)", default=32) or 32)
        self._cht.set_text(f"{int(v)}")
        self._amps.set_text(f"{int(fd.value('Alt Amps', default=0) or 0)}")
        self._flap.set_text(f"{int(fd.value('Flap Position', default=0) or 0)}°")
        self._volts.set_text(f"{(fd.value('Volts', default=0) or 0):.1f}")
