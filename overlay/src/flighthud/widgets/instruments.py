import math

from matplotlib.patches import Circle, Rectangle

from ..data import fmt
from .base import Widget, register


@register
class SpeedGauge(Widget):
    """Circular aviation-style airspeed gauge.

    Static: rim, color bands, ticks, numbers, label.
    Dynamic: needle and digital readout.
    """

    type = "speed_gauge"

    def _angle_for_value(self, v):
        ratio = (v - self.min) / (self.max - self.min)
        ratio = max(0, min(1, ratio))
        return math.radians(self.start_angle - ratio * self.total_angle)

    def draw_static(self, ax):
        self.cx = self.get("x", 205)
        self.cy = self.get("y", 158)
        self.radius = self.get("radius", 112)
        self.min = self.get("min", 0)
        self.max = self.get("max", 130)
        self.start_angle = self.get("start_angle", 230)
        self.total_angle = self.get("total_angle", 280)
        cx, cy, radius = self.cx, self.cy, self.radius

        ax.add_patch(Circle((cx, cy), radius + 10, color=(0, 0, 0, 0.82), zorder=1))
        ax.add_patch(Circle((cx, cy), radius, fill=False, edgecolor="white", linewidth=3, zorder=8))

        for v0, v1, color in self.get("bands", []):
            xs, ys = [], []
            for i in range(31):
                v = v0 + (v1 - v0) * i / 30
                a = self._angle_for_value(v)
                xs.append(cx + math.cos(a) * (radius - 8))
                ys.append(cy + math.sin(a) * (radius - 8))
            ax.plot(xs, ys, color=color, linewidth=8, solid_capstyle="butt", zorder=3)

        tick_minor = self.get("tick_minor", 5)   # loop step
        tick_mid   = self.get("tick_mid",   10)  # medium tick interval
        tick_major = self.get("tick_major", 20)  # big tick + label interval

        v = int(self.min)
        while v <= int(self.max):
            a = self._angle_for_value(v)
            if v % tick_major == 0:
                tick_len, lw = 22, 2.5
            elif v % tick_mid == 0:
                tick_len, lw = 16, 2.0
            else:
                tick_len, lw = 10, 1.3

            x1 = cx + math.cos(a) * (radius - tick_len)
            y1 = cy + math.sin(a) * (radius - tick_len)
            x2 = cx + math.cos(a) * radius
            y2 = cy + math.sin(a) * radius
            ax.plot([x1, x2], [y1, y2], color="white", linewidth=lw, zorder=4)

            if v % tick_major == 0 and v != 0:
                label_dist = self.get("label_dist", 45)
                xt = cx + math.cos(a) * (radius - label_dist)
                yt = cy + math.sin(a) * (radius - label_dist)
                label_str = str(abs(v) // self.get("label_divisor", 1))
                label_size = self.get("label_size", 17)
                ax.text(xt, yt, label_str, fontsize=label_size, color="white", ha="center", va="center", zorder=5)

            v += tick_minor

        ax.text(
            cx, cy - radius + 52, self.get("label", "IAS"),
            fontsize=15, color="white", ha="center", va="center", alpha=0.82, weight="bold", zorder=10,
        )
        # Optional UP / DN labels (VSI style — placed left of centre near the 0-line)
        if self.get("upper_label"):
            ax.text(cx - radius * 0.38, cy + radius * 0.22, self.get("upper_label"),
                    fontsize=11, color="white", ha="center", va="center", alpha=0.75, zorder=10)
        if self.get("lower_label"):
            ax.text(cx - radius * 0.38, cy - radius * 0.22, self.get("lower_label"),
                    fontsize=11, color="white", ha="center", va="center", alpha=0.75, zorder=10)

    def create_dynamic(self, ax):
        cx, cy = self.cx, self.cy
        (self._needle,) = ax.plot([cx, cx], [cy, cy], color="white", linewidth=7, solid_capstyle="round", zorder=7)
        (self._needle_shadow,) = ax.plot([cx, cx], [cy, cy], color="black", linewidth=2, alpha=0.35, zorder=8)
        ax.add_patch(Circle((cx, cy), 10, color="white", zorder=9))
        ax.add_patch(Circle((cx, cy), 5, color="black", zorder=10))
        self._value = ax.text(
            cx, cy - self.radius + 28, "",
            fontsize=self.get("value_size", 23), color="white",
            ha="center", va="center", weight="bold", zorder=10,
        )

    def update(self, fd):
        speed = fd.value(self.get("source"), default=0) or 0
        clamped = max(self.min, min(self.max, speed))
        a = self._angle_for_value(clamped)
        needle_len = self.radius - 48
        x = self.cx + math.cos(a) * needle_len
        y = self.cy + math.sin(a) * needle_len
        self._needle.set_data([self.cx, x], [self.cy, y])
        self._needle_shadow.set_data([self.cx, x], [self.cy, y])
        unit = self.get("unit", " kt")
        decimals = self.get("decimals", 0)
        self._value.set_text(f"{fmt(speed, decimals)}{unit}")


@register
class HeadingTape(Widget):
    """Horizontal heading/track tape.

    A fixed pool of tick/label artists is reused each frame; ticks that fall
    outside the tape are simply hidden.
    """

    type = "heading_tape"

    OFFSETS = list(range(-40, 41, 10))  # 9 candidate marks
    PIXELS_PER_DEGREE = 7

    def draw_static(self, ax):
        self.x = self.get("x", 420)
        self.y = self.get("y", 180)
        self.width = self.get("width", 430)
        self.center_x = self.x + self.width / 2

        ax.add_patch(Rectangle((self.x, self.y), self.width, 72, color=(0, 0, 0, 0.52), zorder=1))
        ax.plot(
            [self.center_x - 12, self.center_x, self.center_x + 12],
            [self.y + 70, self.y + 48, self.y + 70],
            color="yellow", linewidth=3, zorder=5,
        )

    def create_dynamic(self, ax):
        self._ticks = []
        self._labels = []
        for _ in self.OFFSETS:
            (tick,) = ax.plot([0, 0], [0, 0], color="white", linewidth=2, zorder=3)
            label = ax.text(0, 0, "", fontsize=15, color="white", alpha=0.9, zorder=4)
            self._ticks.append(tick)
            self._labels.append(label)
        self._heading = ax.text(
            self.center_x - 42, self.y + 8, "", fontsize=22, color="yellow", weight="bold", zorder=6
        )

    def update(self, fd):
        heading = fd.value(self.get("source"), angular=True, default=0) or 0
        heading = heading % 360
        for offset, tick, label in zip(self.OFFSETS, self._ticks, self._labels):
            deg = (round(heading / 10) * 10 + offset) % 360
            delta = ((deg - heading + 540) % 360) - 180
            mark_x = self.center_x + delta * self.PIXELS_PER_DEGREE

            if self.x < mark_x < self.x + self.width:
                tick.set_data([mark_x, mark_x], [self.y + 12, self.y + 34])
                tick.set_visible(True)
                label.set_position((mark_x - 16, self.y + 40))
                label.set_text(self._cardinal(deg))
                label.set_visible(True)
            else:
                tick.set_visible(False)
                label.set_visible(False)
        self._heading.set_text(f"{fmt(heading)}°")

    @staticmethod
    def _cardinal(deg):
        return {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, f"{deg:03d}")
