class Widget:
    """Base class for HUD widgets.

    A widget separates what it draws into two layers:

    - ``draw_static(ax)``  : chrome that never changes (boxes, scales, ticks,
      fixed labels). Rasterized once into a cached background.
    - ``create_dynamic(ax)``: artists that change per frame (needles, values,
      moving cards). Created once, then mutated by ``update``.
    - ``update(fd)``       : mutate the dynamic artists from a ``FrameData``.

    Static-only widgets implement just ``draw_static``.
    """

    type = None

    def __init__(self, cfg):
        self.cfg = cfg

    def get(self, key, default=None):
        return self.cfg.get(key, default)

    def draw_static(self, ax):
        pass

    def create_dynamic(self, ax):
        pass

    def update(self, fd):
        pass


_REGISTRY = {}


def register(cls):
    """Class decorator: register a widget under its ``type`` name."""
    if not cls.type:
        raise ValueError(f"{cls.__name__} must define a 'type'")
    _REGISTRY[cls.type] = cls
    return cls


def build_widget(cfg):
    """Instantiate a widget from a template entry (a dict with a 'type')."""
    wtype = cfg.get("type")
    if wtype not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown widget type '{wtype}'. Known types: {known}")
    return _REGISTRY[wtype](cfg)


def known_types():
    return sorted(_REGISTRY)
