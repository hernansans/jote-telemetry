import os
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from .data import default_title, load_garmin_log
from .pipeline import generate
from .scene import build_scene, load_template

DEFAULT_FPS = 30
DEFAULT_DURATION_SECONDS = 295
DEFAULT_OFFSET_SECONDS = 331


class HorizonStyle(str, Enum):
    glass = "glass"
    minimal = "minimal"
    classic = "classic"

app = typer.Typer(
    add_completion=False,
    help="Generate flight HUD overlay frames (or an alpha video) from a Garmin G3X/GDU CSV log.",
)


@app.command()
def run(
    csv: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Garmin CSV log (with its header metadata included).",
    ),
    output: Path = typer.Option(
        Path("frames_overlay_hud"),
        "-o",
        "--output",
        help="Output: a directory for PNG frames, or a .mov/.webm file for an alpha video.",
    ),
    template: str = typer.Option(
        "default",
        "-t",
        "--template",
        help="Built-in template name (default, minimal) or a path to a .toml template.",
    ),
    fps: int = typer.Option(DEFAULT_FPS, "--fps", help="Frames per second."),
    duration: float = typer.Option(
        DEFAULT_DURATION_SECONDS, "-d", "--duration", help="Clip duration in seconds."
    ),
    offset: float = typer.Option(
        DEFAULT_OFFSET_SECONDS,
        "--offset",
        help="Offset in seconds from the start of the log to the start of the clip.",
    ),
    width: Optional[int] = typer.Option(None, "--width", help="Override canvas width in pixels."),
    height: Optional[int] = typer.Option(None, "--height", help="Override canvas height in pixels."),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="On-screen title. Defaults to the aircraft ident and date read from the log.",
    ),
    horizon_style: Optional[HorizonStyle] = typer.Option(
        None,
        "--horizon-style",
        help="Override the artificial horizon style (glass, minimal, classic).",
    ),
    jobs: Optional[int] = typer.Option(
        None, "-j", "--jobs", help="Parallel worker processes (default: CPU count)."
    ),
):
    """Render the HUD overlay."""
    df = load_garmin_log(str(csv))
    resolved_title = title if title is not None else default_title(str(csv), df)
    scene = build_scene(
        load_template(template),
        width=width,
        height=height,
        title=resolved_title,
        horizon_style=horizon_style.value if horizon_style else None,
    )
    generate(
        scene=scene,
        df=df,
        output=str(output),
        fps=fps,
        offset=offset,
        duration_seconds=duration,
        jobs=jobs or os.cpu_count() or 1,
    )


def main():
    app()


if __name__ == "__main__":
    main()
