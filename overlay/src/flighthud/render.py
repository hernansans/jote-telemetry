import matplotlib

# Headless, file-only backend: we never display a window, just rasterize.
# Avoids spinning up a GUI process (and a dock icon) on macOS.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .data import FrameData  # noqa: E402
from .widgets import build_widget  # noqa: E402


def _make_axes(width, height):
    """A fully transparent figure whose pixel size is exactly width x height."""
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    ax.patch.set_alpha(0)
    return fig, ax


class Renderer:
    """Renders HUD frames for one scene using matplotlib blitting.

    The static chrome is drawn once and its rasterization cached. Each frame
    only restores that cached background and redraws the dynamic artists on top
    (``draw_artist`` + ``blit``), so the heavy static layer is never
    re-rasterized and no per-frame compositing is needed.
    """

    def __init__(self, scene, df, fps, offset_seconds):
        self.df = df
        self.fps = fps
        self.offset = offset_seconds
        self.width = scene["width"]
        self.height = scene["height"]

        self.widgets = [build_widget(dict(w)) for w in scene["widgets"]]

        self._fig, self._ax = _make_axes(self.width, self.height)
        self._canvas = self._fig.canvas

        # 1) Draw static chrome and cache its rasterization as the background.
        for w in self.widgets:
            w.draw_static(self._ax)
        self._canvas.draw()
        self._bg = self._canvas.copy_from_bbox(self._fig.bbox)

        # 2) Create dynamic artists afterwards; collect them for per-frame redraw.
        before = {id(c) for c in self._ax.get_children()}
        for w in self.widgets:
            w.create_dynamic(self._ax)
        self._dynamic = [c for c in self._ax.get_children() if id(c) not in before]
        self._dynamic.sort(key=lambda a: a.get_zorder())

    def render(self, frame):
        """Return the rendered RGBA frame as a uint8 HxWx4 array."""
        fd = FrameData(self.df, frame, self.fps, self.offset)
        for w in self.widgets:
            w.update(fd)

        self._canvas.restore_region(self._bg)
        for art in self._dynamic:
            self._ax.draw_artist(art)
        self._canvas.blit(self._fig.bbox)
        return np.asarray(self._canvas.buffer_rgba()).copy()

    def close(self):
        plt.close(self._fig)
