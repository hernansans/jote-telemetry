import math

import numpy as np
import matplotlib.patheffects as pe
from matplotlib import transforms
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle

from ..data import fmt
from .base import Widget, register

# Outline used to keep yellow/white symbology readable over sky *and* ground.
_OUTLINE = [pe.withStroke(linewidth=3, foreground="black", alpha=0.55)]
_SOFT_GLOW = [pe.withStroke(linewidth=4, foreground="white", alpha=0.18)]


def _lerp(a, b, t):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return a + (b - a) * t


def _gradient_card(extent_radius, top, horizon_color_sky, horizon_color_gnd, bottom, alpha=1.0, n=512):
    """Build a sky/ground gradient image (origin='lower').

    Top rows fade from the horizon sky color to ``top``; bottom rows fade from
    the horizon ground color to ``bottom``; a thin white band marks the horizon.
    """
    ys = np.arange(n)
    center = (n - 1) / 2.0
    d = (ys - center) / center  # -1 (bottom) .. +1 (top)
    t = np.abs(d)[:, None]

    sky = _lerp(horizon_color_sky, top, t)
    gnd = _lerp(horizon_color_gnd, bottom, t)
    col = np.where(d[:, None] >= 0, sky, gnd)

    band = np.abs(ys - center) < max(1.0, n * 0.0035)
    col[band] = [245, 248, 255]

    img = np.repeat(col[:, None, :], n, axis=1)
    a = np.full((n, n, 1), alpha * 255.0)
    return np.concatenate([img, a], axis=-1).astype(np.uint8)


class _HorizonBase:
    """Shared geometry and per-frame transforms for every horizon style."""

    PITCH_SCALE = 4.2

    def __init__(self, cfg):
        self.cfg = cfg
        self.cx = cfg.get("x", 1680)
        self.cy = cfg.get("y", 810)
        self.radius = cfg.get("radius", 92)
        self.pitch_src = cfg.get("pitch", "Pitch (deg)")
        self.roll_src = cfg.get("roll", "Roll (deg)")
        self.slip_src = cfg.get("slip", "Lateral Acceleration (G)")
        self.pitch_scale = cfg.get("pitch_scale", self.PITCH_SCALE)

    def _attitude(self, fd):
        pitch = fd.value(self.pitch_src, default=0) or 0
        roll = fd.value(self.roll_src, default=0) or 0
        return pitch, roll

    def _card_transform(self, pitch, roll):
        """Card moves down with pitch (in its own frame), then banks with roll."""
        off = -pitch * self.pitch_scale
        affine = transforms.Affine2D().translate(0, off).rotate_deg_around(self.cx, self.cy, roll)
        return affine + self._ax.transData

    def _roll_transform(self, roll):
        affine = transforms.Affine2D().rotate_deg_around(self.cx, self.cy, roll)
        return affine + self._ax.transData

    def _add_card_image(self, ax, image, zorder):
        half = 3 * self.radius
        im = ax.imshow(
            image,
            extent=[self.cx - half, self.cx + half, self.cy - half, self.cy + half],
            origin="lower",
            interpolation="bilinear",
            aspect="auto",
            zorder=zorder,
        )
        im.set_clip_path(self._clip)
        return im

    def _make_clip(self, ax):
        self._clip = Circle((self.cx, self.cy), self.radius, transform=ax.transData)


# ============================================================
# GLASS PFD  — modern glass-cockpit attitude indicator
# ============================================================
class _GlassHorizon(_HorizonBase):
    SKY_TOP = (16, 92, 196)
    SKY_HORIZON = (120, 188, 250)
    GND_HORIZON = (150, 104, 54)
    GND_BOTTOM = (78, 50, 24)

    LADDER = [
        (10, 48, True), (20, 70, True), (30, 48, True),
        (5, 22, False), (15, 22, False), (25, 22, False),
    ]
    BANK_TICKS = [(-60, True), (-45, False), (-30, True), (-20, False),
                  (-10, False), (10, False), (20, False), (30, True),
                  (45, False), (60, True)]

    def draw_static(self, ax):
        cx, cy, r = self.cx, self.cy, self.radius
        # Bezel: layered circles for a subtle beveled rim.
        ax.add_patch(Circle((cx, cy), r + 20, color=(0.10, 0.11, 0.12, 1.0), zorder=2))
        ax.add_patch(Circle((cx, cy), r + 13, color=(0.22, 0.24, 0.26, 1.0), zorder=2))
        ax.add_patch(Circle((cx, cy), r + 7, color=(0.05, 0.05, 0.06, 1.0), zorder=3))

        # Fixed bank scale on the rim.
        for bank, major in self.BANK_TICKS:
            a = math.radians(90 - bank)
            inner = r + 7
            outer = r + (19 if major else 13)
            ax.plot(
                [cx + math.cos(a) * inner, cx + math.cos(a) * outer],
                [cy + math.sin(a) * inner, cy + math.sin(a) * outer],
                color="white", linewidth=2.0 if major else 1.4, zorder=10, alpha=0.95,
            )
        # Fixed zero reference triangle at the top (the aircraft datum).
        ax.add_patch(Polygon(
            [[cx - 9, cy + r + 20], [cx + 9, cy + r + 20], [cx, cy + r + 6]],
            closed=True, facecolor="white", edgecolor="none", zorder=10,
        ))

    def create_dynamic(self, ax):
        self._ax = ax
        cx, cy, r = self.cx, self.cy, self.radius
        self._make_clip(ax)

        card = _gradient_card(r, self.SKY_TOP, self.SKY_HORIZON, self.GND_HORIZON, self.GND_BOTTOM)
        self._card = self._add_card_image(ax, card, zorder=4)

        # Pitch ladder: one Line2D per mark with a center gap (via NaN).
        gap = 16
        self._ladder = []
        for deg, half_len, major in self.LADDER:
            (line,) = ax.plot([0], [0], color="white", linewidth=1.6 if major else 1.1,
                              alpha=0.95, zorder=6, solid_capstyle="round")
            line.set_clip_path(self._clip)
            texts = []
            if major:
                for side in (-1, 1):
                    txt = ax.text(0, 0, "", fontsize=10, color="white", alpha=0.95,
                                  ha="center", va="center", zorder=6, path_effects=_OUTLINE)
                    txt.set_clip_path(self._clip)
                    texts.append((side, txt))
            self._ladder.append((deg, half_len, gap, major, line, texts))

        # Border ring masks the card edge.
        ax.add_patch(Circle((cx, cy), r, fill=False, edgecolor="black", linewidth=7, zorder=7))
        self._ring = Circle((cx, cy), r, fill=False, edgecolor="white", linewidth=2.0, zorder=8)
        ax.add_patch(self._ring)

        # Moving roll pointer (rotates with bank, points at the fixed scale).
        self._pointer = Polygon(
            [[cx - 8, cy + r - 6], [cx + 8, cy + r - 6], [cx, cy + r - 20]],
            closed=True, facecolor="yellow", edgecolor="black", linewidth=0.8, zorder=11,
        )
        ax.add_patch(self._pointer)

        # Slip/skid inclinometer (under the pointer), banks with the aircraft.
        sy = cy + r - 34
        (self._slip_l,) = ax.plot([cx - 13, cx - 13], [sy - 7, sy + 7], color="white", linewidth=2, zorder=11)
        (self._slip_r,) = ax.plot([cx + 13, cx + 13], [sy - 7, sy + 7], color="white", linewidth=2, zorder=11)
        self._slip_ball = Circle((cx, sy), 5.5, facecolor="white", edgecolor="black", linewidth=0.8, zorder=11)
        ax.add_patch(self._slip_ball)
        self._slip_y = sy

        # Fixed aircraft symbol (yellow wings + dot), always on top.
        self._wings = [
            ax.plot([cx - 58, cx - 18], [cy, cy], color="yellow", linewidth=5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx + 18, cx + 58], [cy, cy], color="yellow", linewidth=5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx - 18, cx - 18], [cy, cy - 9], color="yellow", linewidth=5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx + 18, cx + 18], [cy, cy - 9], color="yellow", linewidth=5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
        ]
        ax.add_patch(Circle((cx, cy), 3.5, facecolor="yellow", edgecolor="black", linewidth=0.8, zorder=12))

    def update(self, fd):
        pitch, roll = self._attitude(fd)
        slip = fd.value(self.slip_src, default=0) or 0
        cx, cy = self.cx, self.cy
        t_card = self._card_transform(pitch, roll)
        t_roll = self._roll_transform(roll)

        self._card.set_transform(t_card)

        for deg, half_len, gap, major, line, texts in self._ladder:
            yy = cy + deg * self.pitch_scale
            line.set_data(
                [cx - half_len, cx - gap, np.nan, cx + gap, cx + half_len],
                [yy, yy, np.nan, yy, yy],
            )
            line.set_transform(t_card)
            for side, txt in texts:
                txt.set_position((cx + side * (half_len + 13), yy))
                txt.set_text(str(deg))
                txt.set_transform(t_card)

        self._pointer.set_transform(t_roll)
        # Slip ball offsets opposite the lateral acceleration; banks with roll.
        off = max(-11, min(11, -slip * 26))
        self._slip_ball.set_center((cx + off, self._slip_y))
        for art in (self._slip_l, self._slip_r, self._slip_ball):
            art.set_transform(t_roll)


# ============================================================
# MINIMAL — clean video-overlay look
# ============================================================
class _MinimalHorizon(_HorizonBase):
    SKY_TOP = (60, 150, 230)
    SKY_HORIZON = (130, 195, 245)
    GND_HORIZON = (150, 110, 70)
    GND_BOTTOM = (90, 65, 40)
    LADDER = [(10, 30), (20, 30), (-10, 30), (-20, 30)]

    def __init__(self, cfg):
        super().__init__(cfg)
        self.accent = cfg.get("accent", "#33e1ff")

    def draw_static(self, ax):
        # Borderless: nothing fixed but the boresight, drawn on top later.
        pass

    def create_dynamic(self, ax):
        self._ax = ax
        cx, cy, r = self.cx, self.cy, self.radius
        self._make_clip(ax)

        card = _gradient_card(r, self.SKY_TOP, self.SKY_HORIZON, self.GND_HORIZON, self.GND_BOTTOM, alpha=0.16)
        self._card = self._add_card_image(ax, card, zorder=4)

        (self._horizon,) = ax.plot([cx - r, cx + r], [cy, cy], color="white", linewidth=1.6,
                                   alpha=0.9, zorder=6, path_effects=_SOFT_GLOW)
        self._horizon.set_clip_path(self._clip)

        self._ladder = []
        for deg, half_len in self.LADDER:
            (line,) = ax.plot([0], [0], color="white", linewidth=1.2, alpha=0.75, zorder=6)
            line.set_clip_path(self._clip)
            self._ladder.append((deg, half_len, line))

        # Soft circular vignette edge (subtle, no hard bezel).
        ax.add_patch(Circle((cx, cy), r, fill=False, edgecolor=(1, 1, 1, 0.22), linewidth=1.4, zorder=8))

        # Accent boresight.
        ac = self.accent
        for seg in ([cx - 40, cx - 14], [cx + 14, cx + 40]):
            ax.plot(seg, [cy, cy], color=ac, linewidth=2.6, zorder=12, solid_capstyle="round")
        ax.plot([cx, cx], [cy - 7, cy + 7], color=ac, linewidth=2.6, zorder=12, solid_capstyle="round")
        ax.add_patch(Circle((cx, cy), 2.6, facecolor=ac, edgecolor="none", zorder=12))

    def update(self, fd):
        pitch, roll = self._attitude(fd)
        cx, cy = self.cx, self.cy
        t_card = self._card_transform(pitch, roll)

        self._card.set_transform(t_card)
        self._horizon.set_data([cx - self.radius, cx + self.radius], [cy, cy])
        self._horizon.set_transform(t_card)
        for deg, half_len, line in self._ladder:
            yy = cy + deg * self.pitch_scale
            line.set_data([cx - half_len, cx + half_len], [yy, yy])
            line.set_transform(t_card)


# ============================================================
# CLASSIC — skeuomorphic round gauge
# ============================================================
class _ClassicHorizon(_HorizonBase):
    SKY_TOP = (42, 111, 176)
    SKY_HORIZON = (157, 200, 238)
    GND_HORIZON = (150, 104, 54)
    GND_BOTTOM = (58, 40, 18)
    LADDER = [(10, 40), (20, 58), (-10, 40), (-20, 58)]
    BANK_TICKS = [-60, -45, -30, -20, -10, 10, 20, 30, 45, 60]

    def draw_static(self, ax):
        cx, cy, r = self.cx, self.cy, self.radius
        # Beveled metal bezel: concentric shaded rings.
        for rr, shade in [(r + 26, 0.08), (r + 20, 0.40), (r + 15, 0.62), (r + 10, 0.30), (r + 6, 0.05)]:
            ax.add_patch(Circle((cx, cy), rr, color=(shade, shade, shade + 0.02, 1.0), zorder=2))
        for bank in self.BANK_TICKS:
            a = math.radians(90 - bank)
            ax.plot(
                [cx + math.cos(a) * (r + 6), cx + math.cos(a) * (r + 14)],
                [cy + math.sin(a) * (r + 6), cy + math.sin(a) * (r + 14)],
                color="white", linewidth=1.6, zorder=10,
            )

    def create_dynamic(self, ax):
        self._ax = ax
        cx, cy, r = self.cx, self.cy, self.radius
        self._make_clip(ax)

        card = _gradient_card(r, self.SKY_TOP, self.SKY_HORIZON, self.GND_HORIZON, self.GND_BOTTOM)
        self._card = self._add_card_image(ax, card, zorder=4)

        self._ladder = []
        for deg, half_len in self.LADDER:
            (line,) = ax.plot([0], [0], color="white", linewidth=1.3, alpha=0.9, zorder=6)
            line.set_clip_path(self._clip)
            self._ladder.append((deg, half_len, line))

        ax.add_patch(Circle((cx, cy), r, fill=False, edgecolor="black", linewidth=6, zorder=7))

        # Glass reflection: a soft translucent highlight near the top.
        glass = Ellipse((cx, cy + r * 0.42), r * 1.3, r * 0.75, facecolor=(1, 1, 1, 0.10),
                        edgecolor="none", zorder=9)
        glass.set_clip_path(self._clip)
        ax.add_patch(glass)

        # Classic miniature airplane: orange wings + bank pointer triangle.
        orange = "#ff9000"
        self._wings = [
            ax.plot([cx - 55, cx - 16], [cy, cy], color=orange, linewidth=4.5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx + 16, cx + 55], [cy, cy], color=orange, linewidth=4.5, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
        ]
        ax.add_patch(Circle((cx, cy), 4, facecolor=orange, edgecolor="black", linewidth=0.8, zorder=12))
        self._pointer = Polygon(
            [[cx - 7, cy + r - 4], [cx + 7, cy + r - 4], [cx, cy + r - 16]],
            closed=True, facecolor=orange, edgecolor="black", linewidth=0.7, zorder=11,
        )
        ax.add_patch(self._pointer)

    def update(self, fd):
        pitch, roll = self._attitude(fd)
        cx, cy = self.cx, self.cy
        t_card = self._card_transform(pitch, roll)
        self._card.set_transform(t_card)
        for deg, half_len, line in self._ladder:
            yy = cy + deg * self.pitch_scale
            line.set_data([cx - half_len, cx + half_len], [yy, yy])
            line.set_transform(t_card)
        self._pointer.set_transform(self._roll_transform(roll))


# ============================================================
# PFD — full-screen rectangular attitude (glass-cockpit background)
# ============================================================
class _PfdHorizon(_HorizonBase):
    """Rectangular full-frame attitude, like a G1000/G3X PFD background.

    Fills a rectangle (``width`` x ``height`` centered on x/y) with the
    sky/ground gradient, a wide pitch ladder, a bank arc + roll pointer at the
    top, a slip/skid ball, and a fixed aircraft symbol at the center.
    """

    SKY_TOP = (18, 78, 170)
    SKY_HORIZON = (96, 168, 240)
    GND_HORIZON = (140, 96, 50)
    GND_BOTTOM = (60, 38, 16)
    LADDER = [(10, 80, True), (20, 110, True), (30, 80, True),
              (5, 36, False), (15, 36, False), (25, 36, False),
              (-5, 36, False), (-10, 80, True), (-15, 36, False),
              (-20, 110, True), (-25, 36, False), (-30, 80, True)]
    BANK_TICKS = [(-60, True), (-45, False), (-30, True), (-20, False),
                  (-10, False), (10, False), (20, False), (30, True),
                  (45, False), (60, True)]

    def __init__(self, cfg):
        super().__init__(cfg)
        self.w = cfg.get("width", 1920)
        self.h = cfg.get("height", 1080)
        self.pitch_scale = cfg.get("pitch_scale", 7.0)
        self.arc_r = cfg.get("bank_radius", 0.40 * self.h)
        # Sky/ground opacity. Lower it to let the underlying video show through.
        self.opacity = cfg.get("opacity", 1.0)
        # When False, draw no terrain at all: only the horizon line, ladder,
        # bank arc and symbology over a transparent background (best for video).
        self.fill = cfg.get("fill", True)

    def _rect(self):
        return self.cx - self.w / 2, self.cy - self.h / 2, self.w, self.h

    def draw_static(self, ax):
        cx, cy = self.cx, self.cy
        r = self.arc_r
        for bank, major in self.BANK_TICKS:
            a = math.radians(90 - bank)
            inner = r
            outer = r + (30 if major else 18)
            ax.plot(
                [cx + math.cos(a) * inner, cx + math.cos(a) * outer],
                [cy + math.sin(a) * inner, cy + math.sin(a) * outer],
                color="white", linewidth=3.0 if major else 2.0, zorder=10, alpha=0.97,
                path_effects=_OUTLINE,
            )
        # Fixed reference triangle at the top of the arc (aircraft datum).
        ax.add_patch(Polygon(
            [[cx - 15, cy + r + 30], [cx + 15, cy + r + 30], [cx, cy + r + 6]],
            closed=True, facecolor="white", edgecolor="black", linewidth=1.0, zorder=10,
        ))

    def create_dynamic(self, ax):
        self._ax = ax
        cx, cy = self.cx, self.cy
        x0, y0, w, h = self._rect()
        self._clip = Rectangle((x0, y0), w, h, transform=ax.transData)

        if self.fill:
            half = 0.72 * math.hypot(w, h)
            card = _gradient_card(half, self.SKY_TOP, self.SKY_HORIZON, self.GND_HORIZON,
                                  self.GND_BOTTOM, alpha=self.opacity)
            self._card = ax.imshow(
                card, extent=[cx - half, cx + half, cy - half, cy + half],
                origin="lower", interpolation="bilinear", aspect="auto", zorder=4,
            )
            self._card.set_clip_path(self._clip)
        else:
            self._card = None

        # Explicit horizon line (the only horizon when there is no terrain fill).
        (self._horizon,) = ax.plot([cx - w / 2, cx + w / 2], [cy, cy], color="white",
                                   linewidth=2.6, zorder=5, solid_capstyle="round",
                                   path_effects=_SOFT_GLOW)
        self._horizon.set_clip_path(self._clip)

        gap = 26
        self._ladder = []
        for deg, half_len, major in self.LADDER:
            (line,) = ax.plot([0], [0], color="white", linewidth=2.0 if major else 1.2,
                              alpha=0.95, zorder=6, solid_capstyle="round")
            line.set_clip_path(self._clip)
            texts = []
            if major:
                for side in (-1, 1):
                    txt = ax.text(0, 0, "", fontsize=15, color="white", ha="center", va="center",
                                  zorder=6, path_effects=_OUTLINE)
                    txt.set_clip_path(self._clip)
                    texts.append((side, txt))
            self._ladder.append((deg, half_len, gap, major, line, texts))

        # Moving roll pointer at the bank arc.
        r = self.arc_r
        self._pointer = Polygon(
            [[cx - 14, cy + r - 2], [cx + 14, cy + r - 2], [cx, cy + r - 30]],
            closed=True, facecolor="yellow", edgecolor="black", linewidth=1.0, zorder=11,
        )
        ax.add_patch(self._pointer)

        # Slip/skid bar just under the roll pointer.
        sy = cy + r - 40
        (self._slip_l,) = ax.plot([cx - 18, cx - 18], [sy - 9, sy + 9], color="white", linewidth=2.2, zorder=11)
        (self._slip_r,) = ax.plot([cx + 18, cx + 18], [sy - 9, sy + 9], color="white", linewidth=2.2, zorder=11)
        self._slip_ball = Rectangle((cx - 7, sy - 6), 14, 12, facecolor="white",
                                    edgecolor="black", linewidth=0.8, zorder=11)
        ax.add_patch(self._slip_ball)
        self._slip_y = sy

        # Fixed aircraft symbol: yellow boresight wings + chevron at the center.
        self._wings = [
            ax.plot([cx - 150, cx - 50], [cy, cy], color="yellow", linewidth=7, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx + 50, cx + 150], [cy, cy], color="yellow", linewidth=7, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx - 50, cx - 50], [cy, cy - 14], color="yellow", linewidth=7, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
            ax.plot([cx + 50, cx + 50], [cy, cy - 14], color="yellow", linewidth=7, zorder=12,
                    solid_capstyle="round", path_effects=_OUTLINE)[0],
        ]
        # Center chevron (the fixed velocity vector wedge).
        ax.add_patch(Polygon(
            [[cx - 34, cy - 34], [cx, cy - 6], [cx + 34, cy - 34], [cx, cy - 20]],
            closed=True, facecolor="yellow", edgecolor="black", linewidth=0.8, zorder=12,
        ))

    def update(self, fd):
        pitch, roll = self._attitude(fd)
        slip = fd.value(self.slip_src, default=0) or 0
        cx, cy = self.cx, self.cy
        t_card = self._card_transform(pitch, roll)
        t_roll = self._roll_transform(roll)

        if self._card is not None:
            self._card.set_transform(t_card)
        self._horizon.set_transform(t_card)
        for deg, half_len, gap, major, line, texts in self._ladder:
            yy = cy + deg * self.pitch_scale
            line.set_data(
                [cx - half_len, cx - gap, np.nan, cx + gap, cx + half_len],
                [yy, yy, np.nan, yy, yy],
            )
            line.set_transform(t_card)
            for side, txt in texts:
                txt.set_position((cx + side * (half_len + 18), yy))
                txt.set_text(str(abs(deg)))
                txt.set_transform(t_card)

        self._pointer.set_transform(t_roll)
        off = max(-15, min(15, -slip * 34))
        self._slip_ball.set_xy((cx - 7 + off, self._slip_y - 6))
        for art in (self._slip_l, self._slip_r, self._slip_ball):
            art.set_transform(t_roll)


_STYLES = {
    "glass": _GlassHorizon,
    "minimal": _MinimalHorizon,
    "classic": _ClassicHorizon,
    "pfd": _PfdHorizon,
}


@register
class ArtificialHorizon(Widget):
    """Attitude indicator. Pick a look with ``style`` in the template.

    Styles: ``glass`` (modern PFD, default), ``minimal`` (clean overlay),
    ``classic`` (skeuomorphic round gauge).
    """

    type = "artificial_horizon"

    def __init__(self, cfg):
        super().__init__(cfg)
        style = cfg.get("style", "glass")
        if style not in _STYLES:
            raise ValueError(f"Unknown horizon style '{style}'. Options: {', '.join(_STYLES)}")
        self._impl = _STYLES[style](cfg)

    def draw_static(self, ax):
        self._impl.draw_static(ax)

    def create_dynamic(self, ax):
        self._impl.create_dynamic(ax)

    def update(self, fd):
        self._impl.update(fd)
