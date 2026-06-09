import math
import os

import matplotlib.patheffects as pe
import numpy as np
from PIL import Image
from matplotlib import transforms
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Circle, Polygon, Rectangle

from ..data import fmt
from .base import Widget, register

_OUTLINE = [pe.withStroke(linewidth=2.5, foreground="black", alpha=0.6)]


def _box_with_notch(x, y, w, h, side, facecolor, zorder):
    """A value box (Rectangle) plus a triangular notch on ``side`` pointing out."""
    rect = Rectangle((x, y), w, h, facecolor=facecolor, edgecolor="white",
                     linewidth=1.5, zorder=zorder)
    cy = y + h / 2
    if side == "right":
        tip = [[x + w, y + h * 0.30], [x + w + 12, cy], [x + w, y + h * 0.70]]
    else:
        tip = [[x, y + h * 0.30], [x - 12, cy], [x, y + h * 0.70]]
    notch = Polygon(tip, closed=True, facecolor=facecolor, edgecolor="white",
                    linewidth=1.5, zorder=zorder)
    return rect, notch


@register
class VerticalTape(Widget):
    """Vertical scrolling tape (airspeed, altitude, ...).

    The current value sits in a center box; the scale scrolls behind it. Optional
    color ``bands`` ride the inner edge, and an optional secondary readout
    (e.g. TAS) shows below.
    """

    type = "tape"

    def draw_static(self, ax):
        c = self.cfg
        self.x = c.get("x", 60)
        self.y = c.get("y", 240)
        self.w = c.get("width", 120)
        self.h = c.get("height", 600)
        self.cy = self.y + self.h / 2
        self.ppu = c.get("pixels_per_unit", 2.2)
        self.big = c.get("big_step", 20)
        self.small = c.get("small_step", 10)
        self.source = c.get("source")
        self.transform = c.get("transform", "identity")
        self.decimals = c.get("decimals", 0)
        self.box_side = c.get("box_side", "right")
        self.bands = c.get("bands", [])
        self.sub_source = c.get("sub_source")
        self.sub_template = c.get("sub_template", "{value}")
        self.sub_transform = c.get("sub_transform", "identity")
        self.sub_decimals = c.get("sub_decimals", 0)

        ax.add_patch(Rectangle((self.x, self.y), self.w, self.h,
                               facecolor=(0.06, 0.07, 0.09, 0.55), edgecolor="none", zorder=20))
        if self.sub_source:
            ax.add_patch(Rectangle((self.x, self.y - 34), self.w, 30,
                                   facecolor=(0.06, 0.07, 0.09, 0.7), edgecolor="none", zorder=20))

    def _inner_x(self):
        return self.x + self.w if self.box_side == "right" else self.x

    def create_dynamic(self, ax):
        from matplotlib.path import Path as MplPath

        # Build a clip transform: unit square → tape data bounds → display px.
        # The two-argument set_clip_path(path, transform) form is the only API
        # that reliably clips Rectangle patches in the Agg backend — clip_box /
        # TransformedBbox approaches do not survive the multiprocess render workers.
        _clip_path = MplPath.unit_rectangle()
        _clip_tf   = (transforms.Affine2D()
                      .scale(self.w, self.h)
                      .translate(self.x, self.y)
                      + ax.transData)

        def _clip(artist):
            artist.set_clip_path(_clip_path, _clip_tf)
            artist.set_clip_on(True)

        inner = self._inner_x()
        sgn = -1 if self.box_side == "right" else 1  # ticks point inward

        # Color bands ride the inner edge (they scroll with the scale).
        self._bands = []
        for lo, hi, color in self.bands:
            bx = inner - 7 if self.box_side == "right" else inner
            rect = Rectangle((bx, self.cy), 7, 1, facecolor=color, edgecolor="none", zorder=21)
            _clip(rect)
            ax.add_patch(rect)
            self._bands.append((lo, hi, rect))

        # Tick + number pool (reused each frame).
        n = int(self.h / (self.big * self.ppu)) + 3
        self._marks = []
        for _ in range(n):
            (tick,) = ax.plot([0, 0], [0, 0], color="white", linewidth=2, zorder=22)
            _clip(tick)
            txt = ax.text(0, 0, "", fontsize=15, color="white", ha="center", va="center",
                          zorder=22, path_effects=_OUTLINE)
            _clip(txt)
            self._marks.append((tick, txt))
        # Minor ticks.
        nm = int(self.h / (self.small * self.ppu)) + 3
        self._minor = []
        for _ in range(nm):
            (tick,) = ax.plot([0, 0], [0, 0], color="white", linewidth=1.1, alpha=0.8, zorder=22)
            _clip(tick)
            self._minor.append(tick)

        # Center value box.
        bh = 42
        rect, notch = _box_with_notch(self.x, self.cy - bh / 2, self.w, bh, self.box_side,
                                      (0, 0, 0, 0.92), zorder=24)
        ax.add_patch(rect)
        ax.add_patch(notch)
        self._value = ax.text(self.x + self.w / 2, self.cy, "", fontsize=26, color="white",
                              ha="center", va="center", weight="bold", zorder=25)

        if self.sub_source:
            self._sub = ax.text(self.x + self.w / 2, self.y - 19, "", fontsize=14, color="white",
                                ha="center", va="center", zorder=25)
        self._sgn = sgn
        self._inner = inner

    def update(self, fd):
        value = fd.value(self.source, transform=self.transform, default=0) or 0
        inner, sgn = self._inner, self._sgn

        base = round(value / self.big) * self.big
        half = len(self._marks) // 2
        for i, (tick, txt) in enumerate(self._marks):
            v = base + (i - half) * self.big
            y = self.cy + (v - value) * self.ppu
            if self.y <= y <= self.y + self.h and v >= 0:
                tick.set_data([inner, inner + sgn * 16], [y, y])
                tick.set_visible(True)
                txt.set_position((self.x + self.w / 2, y))
                txt.set_text(str(int(round(v))))
                txt.set_visible(True)
            else:
                tick.set_visible(False)
                txt.set_visible(False)

        basem = round(value / self.small) * self.small
        halfm = len(self._minor) // 2
        for i, tick in enumerate(self._minor):
            v = basem + (i - halfm) * self.small
            y = self.cy + (v - value) * self.ppu
            if self.y <= y <= self.y + self.h and v >= 0 and v % self.big != 0:
                tick.set_data([inner, inner + sgn * 9], [y, y])
                tick.set_visible(True)
            else:
                tick.set_visible(False)

        for lo, hi, rect in self._bands:
            y_lo = self.cy + (lo - value) * self.ppu
            y_hi = self.cy + (hi - value) * self.ppu
            rect.set_y(min(y_lo, y_hi))
            rect.set_height(abs(y_hi - y_lo))

        self._value.set_text(fmt(value, self.decimals))
        if self.sub_source:
            sv = fd.value(self.sub_source, transform=self.sub_transform, default=None)
            self._sub.set_text(self.sub_template.format(value=fmt(sv, self.sub_decimals)))


@register
class Vsi(Widget):
    """Vertical speed indicator: a thin scale with a moving pointer."""

    type = "vsi"

    def draw_static(self, ax):
        c = self.cfg
        self.x = c.get("x", 1575)
        self.y = c.get("y", 470)
        self.w = c.get("width", 54)
        self.h = c.get("height", 480)
        self.cy = self.y + self.h / 2
        self.source = c.get("source", "Vertical Speed (ft/min)")
        self.max_fpm = c.get("max_fpm", 2000)
        self.step = c.get("step", 500)
        self.ppu = (self.h / 2 - 14) / self.max_fpm

        ax.add_patch(Rectangle((self.x, self.y), self.w, self.h,
                               facecolor=(0.06, 0.07, 0.09, 0.55), edgecolor="none", zorder=20))
        # Zero reference line.
        ax.plot([self.x, self.x + self.w], [self.cy, self.cy], color=(1, 1, 1, 0.45),
                linewidth=1.0, zorder=21)
        # Scale ticks; label the thousands.
        v = -((self.max_fpm // self.step) * self.step)
        while v <= self.max_fpm:
            y = self.cy + v * self.ppu
            major = (v % 1000 == 0)
            ax.plot([self.x, self.x + (12 if major else 7)], [y, y], color="white",
                    linewidth=1.4 if major else 1.0, alpha=0.85, zorder=21)
            if major and v != 0:
                ax.text(self.x + self.w - 4, y, str(abs(v) // 1000), fontsize=12, color="white",
                        va="center", ha="right", alpha=0.85, zorder=21)
            v += self.step

    def create_dynamic(self, ax):
        # Pointer: a filled chevron pointing toward the altitude tape (left).
        self._ptr = Polygon([[self.x, self.cy], [self.x + 16, self.cy - 8], [self.x + 16, self.cy + 8]],
                            closed=True, facecolor="#33e1ff", edgecolor="black", linewidth=0.6, zorder=23)
        ax.add_patch(self._ptr)
        self._readout = ax.text(self.x + self.w / 2, self.y + self.h + 13, "", fontsize=13,
                               color="#33e1ff", ha="center", va="center", zorder=23)

    def update(self, fd):
        vs = fd.value(self.source, default=0) or 0
        y = self.cy + max(-self.max_fpm, min(self.max_fpm, vs)) * self.ppu
        self._ptr.set_xy([[self.x, y], [self.x + 16, y - 8], [self.x + 16, y + 8]])
        self._readout.set_text(f"{fmt(vs)}")


@register
class HeadingRose(Widget):
    """Compass rose / HSI showing heading or track, with a fixed aircraft."""

    type = "heading_rose"

    def draw_static(self, ax):
        c = self.cfg
        self.cx = c.get("x", 960)
        self.cy = c.get("y", 200)
        self.r = c.get("radius", 175)
        self.source = c.get("source", "GPS Ground Track (deg)")
        self.label = c.get("label", "TRK")
        cx, cy, r = self.cx, self.cy, self.r

        ax.add_patch(Circle((cx, cy), r + 6, facecolor=(0.05, 0.06, 0.08, 0.42),
                            edgecolor=(1, 1, 1, 0.8), linewidth=1.5, zorder=20))
        # Fixed cyan track/lubber pointer at the top.
        ax.add_patch(Polygon([[cx - 11, cy + r + 8], [cx + 11, cy + r + 8], [cx, cy + r - 10]],
                             closed=True, facecolor="#33e1ff", edgecolor="black", linewidth=0.8, zorder=24))
        # Heading value box at the top.
        ax.add_patch(Rectangle((cx - 46, cy + r + 9), 92, 32, facecolor="black",
                               edgecolor="white", linewidth=1.4, zorder=24))

        # Fixed aircraft symbol in the center — custom PNG if provided,
        # otherwise the default white-line glyph.
        icon_path = c.get("aircraft_icon")
        if icon_path and os.path.isfile(icon_path):
            pil_img = Image.open(icon_path).convert("RGBA")
            # Auto-crop to the visible (non-transparent) content so the
            # icon's silhouette — not its canvas — sits at the rose centre.
            alpha_bbox = pil_img.getchannel("A").getbbox()
            if alpha_bbox:
                pil_img = pil_img.crop(alpha_bbox)
            img = np.asarray(pil_img)
            zoom = c.get("aircraft_icon_zoom", 0.18)
            box = OffsetImage(img, zoom=zoom)
            ab = AnnotationBbox(box, (cx, cy), frameon=False, zorder=24,
                                annotation_clip=False)
            ax.add_artist(ab)
        else:
            ax.plot([cx - 24, cx + 24], [cy, cy], color="white", linewidth=3, zorder=24, solid_capstyle="round")
            ax.plot([cx, cx], [cy - 18, cy + 16], color="white", linewidth=3, zorder=24, solid_capstyle="round")
            ax.plot([cx - 11, cx + 11], [cy - 13, cy - 13], color="white", linewidth=3, zorder=24, solid_capstyle="round")

    def create_dynamic(self, ax):
        self._ax = ax
        cx, cy, r = self.cx, self.cy, self.r
        self._ring = []  # rotating tick/label artists share one transform
        for b in range(0, 360, 5):
            a = math.radians(90 - b)
            major = (b % 30 == 0)
            mid = (b % 10 == 0)
            inner = r - (18 if major else (12 if mid else 7))
            (tick,) = ax.plot(
                [cx + math.cos(a) * inner, cx + math.cos(a) * r],
                [cy + math.sin(a) * inner, cy + math.sin(a) * r],
                color="white", linewidth=2.0 if major else (1.3 if mid else 1.0),
                alpha=0.95, zorder=22,
            )
            self._ring.append(tick)
            if major:
                cardinal = {0: "N", 90: "E", 180: "S", 270: "W"}.get(b)
                lab = cardinal or str(b // 10)
                rl = r - 36
                txt = ax.text(cx + math.cos(a) * rl, cy + math.sin(a) * rl, lab,
                              fontsize=17 if cardinal else 14, color="white",
                              ha="center", va="center",
                              weight="bold" if cardinal else "normal", zorder=22)
                self._ring.append(txt)

        self._value = ax.text(cx, cy + r + 25, "", fontsize=20, color="white",
                              ha="center", va="center", weight="bold", zorder=25)

    def update(self, fd):
        heading = fd.value(self.source, angular=True, default=0) or 0
        heading = heading % 360
        # Rotate the whole card so the current heading sits under the lubber line.
        t = transforms.Affine2D().rotate_deg_around(self.cx, self.cy, heading) + self._ax.transData
        for art in self._ring:
            art.set_transform(t)
        self._value.set_text(f"{int(round(heading)):03d}°")
