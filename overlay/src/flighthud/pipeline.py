import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from .render import Renderer

VIDEO_EXTS = {".mov", ".webm"}

# Alpha video codecs the encoder knows how to mux. Each entry is the container
# extension plus the ffmpeg `-c:v ...` arguments.
#
# ProRes 4444 is the default for .mov: it is what DaVinci Resolve (el editor del
# proyecto) importa de forma confiable. qtrle (QuickTime Animation / RLE) es mucho
# más rápido de encodear pero Resolve NO lo importa bien — dejarlo solo como opt-in
# para destinos no-Resolve (web / FCP / Premiere en Mac). Ver memory/overlay-codec-resolve.md.
CODECS = {
    "prores4444": {"ext": ".mov", "args": ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]},
    "qtrle": {"ext": ".mov", "args": ["-c:v", "qtrle", "-pix_fmt", "argb"]},
    "vp9": {"ext": ".webm", "args": ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p"]},
}

# Codec elegido por defecto según la extensión de salida (preserva el comportamiento
# previo: .mov ⇒ ProRes 4444, .webm ⇒ VP9).
_DEFAULT_CODEC_FOR_EXT = {".mov": "prores4444", ".webm": "vp9"}

# Per-worker renderer, built once in the process initializer.
_RENDERER = None


def _init_worker(scene, df, fps, offset):
    global _RENDERER
    _RENDERER = Renderer(scene, df, fps, offset)


def _render_to_png(item):
    frame, path = item
    arr = _RENDERER.render(frame)
    # Low compression: we favor encode speed over file size for batch frames.
    Image.fromarray(arr, "RGBA").save(path, compress_level=1)
    return frame


def render_frames(scene, df, out_dir, fps, offset, total_frames, jobs):
    """Render ``total_frames`` PNGs into ``out_dir`` using ``jobs`` processes."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = [(f, str(out_dir / f"frame_{f:06d}.png")) for f in range(total_frames)]

    print(f"Rendering {total_frames} frames into '{out_dir}' with {jobs} worker(s)...")

    if jobs == 1:
        _init_worker(scene, df, fps, offset)
        for i, item in enumerate(items):
            _render_to_png(item)
            if i % 300 == 0:
                print(f"Frame {i}/{total_frames}")
    else:
        with ProcessPoolExecutor(
            max_workers=jobs, initializer=_init_worker, initargs=(scene, df, fps, offset)
        ) as ex:
            for i, _ in enumerate(ex.map(_render_to_png, items, chunksize=16)):
                if i % 300 == 0:
                    print(f"Frame {i}/{total_frames}")

    return out_dir


def _resolve_codec(out_path, codec):
    """Pick the codec for an output, validating it against the file extension.

    With ``codec=None`` the default for the extension is used (.mov ⇒ ProRes 4444,
    .webm ⇒ VP9), preserving the previous extension-driven behavior.
    """
    ext = out_path.suffix.lower()
    if codec is None:
        codec = _DEFAULT_CODEC_FOR_EXT.get(ext)
        if codec is None:
            raise ValueError(f"Unsupported video extension '{ext}'. Use .mov or .webm for alpha.")
        return codec
    if codec not in CODECS:
        raise ValueError(f"Unknown codec '{codec}'. Choose one of: {', '.join(CODECS)}.")
    expected = CODECS[codec]["ext"]
    if ext != expected:
        raise ValueError(f"Codec '{codec}' needs a '{expected}' output, got '{ext}'.")
    return codec


def _ffmpeg_encode_cmd(frames_dir, input_fps, output_fps, out_path, codec):
    # Read the (possibly low-rate) rendered frames at `input_fps`, then resample to
    # `output_fps` so ffmpeg duplicates frames up to the output rate. The telemetry
    # HUD changes slowly, so rendering ~4–6 unique frames/s and letting the encoder
    # fill the rest looks identical and is far cheaper than one render per frame.
    cmd = ["ffmpeg", "-y", "-framerate", str(input_fps), "-i", str(Path(frames_dir) / "frame_%06d.png")]
    cmd += CODECS[codec]["args"]
    cmd += ["-r", str(output_fps)]
    cmd.append(str(out_path))
    return cmd


def render_video(scene, df, out_path, render_fps, output_fps, offset, total_frames, jobs, codec=None):
    """Render frames to a temp dir, then mux into an alpha video with ffmpeg.

    ``render_fps`` is the rate of unique rendered frames (drives the time mapping);
    ``output_fps`` is the final video frame rate (ffmpeg duplicates to reach it).
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH; install it or output to a frames directory.")

    out_path = Path(out_path)
    codec = _resolve_codec(out_path, codec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flighthud-") as tmp:
        render_frames(scene, df, tmp, render_fps, offset, total_frames, jobs)
        cmd = _ffmpeg_encode_cmd(tmp, render_fps, output_fps, out_path, codec)
        print(f"Encoding {out_path} ({codec}, render @ {render_fps} → {output_fps} fps) ...")
        subprocess.run(cmd, check=True)
    print(f"Done. Wrote {out_path}.")


def generate(scene, df, output, fps, offset, duration_seconds, jobs, codec=None, render_fps=None):
    """Render to either a PNG directory or an alpha video, by output extension.

    ``render_fps`` (default = ``fps``) is how many unique frames are rendered per
    second. When lower than ``fps``, only video output benefits automatically (the
    encoder duplicates frames); for a PNG directory the frames ARE at ``render_fps``
    and must be encoded with a matching ``-framerate`` (printed below).
    """
    # Default a `fps` para llamadas programáticas sin render_fps; nunca por encima de
    # `fps` (renderizar más frames únicos que la salida no aporta nada).
    render_fps = min(render_fps or fps, fps)
    total_frames = max(1, round(duration_seconds * render_fps))
    output = Path(output)
    if output.suffix.lower() in VIDEO_EXTS:
        render_video(scene, df, output, render_fps, fps, offset, total_frames, jobs, codec=codec)
    else:
        render_frames(scene, df, output, render_fps, offset, total_frames, jobs)
        msg = f"Done. {total_frames} frames generated in '{output}'."
        if render_fps != fps:
            msg += (
                f"\nRendered @ {render_fps} fps. Para video a {fps} fps, encodeá con: "
                f"ffmpeg -framerate {render_fps} -i {output}/frame_%06d.png <codec> -r {fps} out.mov"
            )
        print(msg)
