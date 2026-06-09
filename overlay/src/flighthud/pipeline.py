import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from .render import Renderer

VIDEO_EXTS = {".mov", ".webm"}

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


def _ffmpeg_encode_cmd(frames_dir, fps, out_path):
    ext = out_path.suffix.lower()
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(Path(frames_dir) / "frame_%06d.png")]
    if ext == ".mov":
        # ProRes 4444 carries an alpha channel and is widely supported by editors.
        cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    elif ext == ".webm":
        cmd += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p"]
    else:
        raise ValueError(f"Unsupported video extension '{ext}'. Use .mov or .webm for alpha.")
    cmd.append(str(out_path))
    return cmd


def render_video(scene, df, out_path, fps, offset, total_frames, jobs):
    """Render frames to a temp dir, then mux into an alpha video with ffmpeg."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH; install it or output to a frames directory.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flighthud-") as tmp:
        render_frames(scene, df, tmp, fps, offset, total_frames, jobs)
        cmd = _ffmpeg_encode_cmd(tmp, fps, out_path)
        print(f"Encoding {out_path} ...")
        subprocess.run(cmd, check=True)
    print(f"Done. Wrote {out_path}.")


def generate(scene, df, output, fps, offset, duration_seconds, jobs):
    """Render to either a PNG directory or an alpha video, by output extension."""
    total_frames = int(duration_seconds * fps)
    output = Path(output)
    if output.suffix.lower() in VIDEO_EXTS:
        render_video(scene, df, output, fps, offset, total_frames, jobs)
    else:
        render_frames(scene, df, output, fps, offset, total_frames, jobs)
        print(f"Done. Frames generated in '{output}'.")
