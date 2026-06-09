import tomllib
from importlib import resources
from pathlib import Path


def load_template(name_or_path):
    """Load a template by built-in name or filesystem path.

    A value that resolves to an existing file is read directly; otherwise it is
    looked up among the templates shipped with the package
    (``flighthud/templates/<name>.toml``).
    """
    path = Path(name_or_path)
    if path.is_file():
        data = path.read_bytes()
    else:
        templates = resources.files("flighthud.templates")
        resource = templates / f"{name_or_path}.toml"
        if not resource.is_file():
            available = sorted(
                p.name[:-5] for p in templates.iterdir() if p.name.endswith(".toml")
            )
            raise FileNotFoundError(
                f"Template '{name_or_path}' not found. "
                f"Built-in templates: {', '.join(available)}; "
                f"or pass a path to a .toml file."
            )
        data = resource.read_bytes()

    template = tomllib.loads(data.decode("utf-8"))
    return template


def build_scene(template, width=None, height=None, title="", horizon_style=None):
    """Resolve a template into a render-ready scene dict.

    CLI overrides (width/height) take precedence over the template canvas.
    The title is injected into any ``title`` widget, and ``horizon_style``, if
    given, overrides the ``style`` of every ``artificial_horizon`` widget.
    """
    canvas = template.get("canvas", {})
    scene = {
        "width": width or canvas.get("width", 1920),
        "height": height or canvas.get("height", 1080),
        "widgets": [dict(w) for w in template.get("widget", [])],
    }
    for w in scene["widgets"]:
        if w.get("type") == "title":
            w["text"] = title
        if w.get("type") == "artificial_horizon" and horizon_style:
            w["style"] = horizon_style
    return scene
