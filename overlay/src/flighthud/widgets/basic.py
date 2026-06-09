from matplotlib.patches import Rectangle

from ..data import fmt
from .base import Widget, register


@register
class Panel(Widget):
    """A translucent background box."""

    type = "panel"

    def draw_static(self, ax):
        ax.add_patch(
            Rectangle(
                (self.get("x", 0), self.get("y", 0)),
                self.get("width", 100),
                self.get("height", 100),
                color=tuple(self.get("color", [0, 0, 0, 0.45])),
                zorder=self.get("zorder", 1),
            )
        )


@register
class Label(Widget):
    """A fixed text label."""

    type = "label"

    def draw_static(self, ax):
        ax.text(
            self.get("x", 0),
            self.get("y", 0),
            self.get("text", ""),
            fontsize=self.get("size", 17),
            color=self.get("color", "white"),
            alpha=self.get("alpha", 1.0),
            weight=self.get("weight", "bold"),
            ha=self.get("ha", "left"),
            va=self.get("va", "baseline"),
        )


@register
class Title(Widget):
    """Top banner: a background box plus the run title.

    The title text is injected at render time (CLI ``--title`` or a value
    derived from the log), so it is set on ``cfg['text']`` before drawing.
    """

    type = "title"

    def draw_static(self, ax):
        bg = self.get("bg")
        if bg:
            ax.add_patch(
                Rectangle(
                    (bg[0], bg[1]),
                    bg[2],
                    bg[3],
                    color=tuple(self.get("bg_color", [0, 0, 0, 0.45])),
                    zorder=0,
                )
            )
        ax.text(
            self.get("x", 80),
            self.get("y", 960),
            self.get("text", ""),
            fontsize=self.get("size", 24),
            color=self.get("color", "white"),
            weight="bold",
        )


@register
class Metric(Widget):
    """Small label above a large value (GS, ALT, RPM, OIL TEMP, ...)."""

    type = "metric"

    def draw_static(self, ax):
        ax.text(
            self.get("x", 0),
            self.get("y", 0) + 46,
            self.get("label", ""),
            fontsize=12,
            color="white",
            alpha=0.70,
            weight="bold",
        )

    def create_dynamic(self, ax):
        self._value = ax.text(
            self.get("x", 0),
            self.get("y", 0),
            "",
            fontsize=self.get("size", 28),
            color="white",
            weight="bold",
        )

    def update(self, fd):
        v = fd.value(self.get("source"), transform=self.get("transform", "identity"))
        self._value.set_text(f"{fmt(v, self.get('decimals', 0))}{self.get('unit', '')}")


@register
class Readout(Widget):
    """A single dynamic line built from a template, e.g. 'Volts: {value}'."""

    type = "readout"

    def create_dynamic(self, ax):
        self._text = ax.text(
            self.get("x", 0),
            self.get("y", 0),
            "",
            fontsize=self.get("size", 17),
            color="white",
            alpha=self.get("alpha", 0.88),
        )

    def update(self, fd):
        if self.get("numeric", True):
            v = fd.value(self.get("source"), transform=self.get("transform", "identity"))
            value = fmt(v, self.get("decimals", 0))
        else:
            value = fd.text(self.get("source"), default=self.get("default", "---"))
        self._text.set_text(self.get("template", "{value}").format(value=value))
