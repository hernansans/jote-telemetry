from .base import build_widget, known_types, register, Widget

# Import modules for their registration side effects.
from . import basic  # noqa: F401
from . import instruments  # noqa: F401
from . import horizon  # noqa: F401
from . import pfd  # noqa: F401
from . import eis  # noqa: F401
from . import info_panel  # noqa: F401

__all__ = ["build_widget", "known_types", "register", "Widget"]
