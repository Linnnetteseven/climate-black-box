"""Pre-render a rotating Earth as a scroll-scrubbable frame sequence.

Why frames rather than a video or a live 3D render:

  * Scrubbing backwards is exactly as smooth as forwards. Video seeking
    stutters, and a live WebGL globe has to re-render on every scroll event.
    Swapping a decoded image is effectively free.
  * It degrades perfectly: if JavaScript never runs, frame 0 is still a
    beautiful static hero.
  * No WebGL context to lose on a conference laptop with flaky graphics.

The source textures are NASA Blue Marble (daytime surface) and Black Marble
(night lights), both public domain. The projection is orthographic -- what you
actually see looking at a sphere from far away -- computed per pixel with
numpy, which is fast enough to render the whole sequence in a minute.

Credit: NASA Earth Observatory. Public domain.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("cbb.globe")

SRC = Path("/tmp/claude-1000/-home-linnette-projects/92d9af8b-997b-4f3e-b434-94fe0e34a570/scratchpad/nasa")
OUT = Path("apps/web/public/earth")

#: Kenya, so the rotation ends looking at the project sites.
TARGET_LON, TARGET_LAT = 36.0, -0.5


def load_textures(size: int):
    day = Image.open(SRC / "bluemarble.jpg").convert("RGB")
    night = Image.open(SRC / "blackmarble.jpg").convert("RGB")
    # Downsample once: sampling a 5400px texture per frame is wasteful when the
    # globe is never more than ~1200px across.
    w = size * 4
    day = day.resize((w, w // 2), Image.LANCZOS)
    night = night.resize((w, w // 2), Image.LANCZOS)
    return np.asarray(day, dtype=np.float32) / 255.0, np.asarray(night, dtype=np.float32) / 255.0


def render_frame(day_tex, night_tex, size: int, lon0: float, zoom: float) -> Image.Image:
    """Orthographic projection of the textures, lit from the sub-solar point."""
    th, tw, _ = day_tex.shape

    # Normalised device coords; radius shrinks as zoom rises so the globe grows.
    #
    # The span is kept above 1.0 at every zoom so there is always transparent
    # margin between the sphere and the edge of the frame. Without that margin
    # the globe is cut by the image boundary and the page shows two hard
    # vertical lines where the frame ends -- which is exactly what it did.
    # 1.46 clears the atmosphere halo too, which reaches 1.12 radii.
    span = 1.46 / zoom
    xs = np.linspace(-span, span, size, dtype=np.float32)
    ys = np.linspace(span, -span, size, dtype=np.float32)
    x, y = np.meshgrid(xs, ys)

    rho2 = x * x + y * y
    on_globe = rho2 <= 1.0
    z = np.sqrt(np.clip(1.0 - rho2, 0, None))

    # Tilt the pole slightly so it reads as a planet rather than a disc.
    tilt = np.radians(18.0)
    y_t = y * np.cos(tilt) - z * np.sin(tilt)
    z_t = y * np.sin(tilt) + z * np.cos(tilt)

    lat = np.degrees(np.arcsin(np.clip(y_t, -1, 1)))
    lon = np.degrees(np.arctan2(x, z_t)) + lon0
    lon = ((lon + 180.0) % 360.0) - 180.0

    u = np.clip(((lon + 180.0) / 360.0 * tw).astype(np.int32), 0, tw - 1)
    v = np.clip(((90.0 - lat) / 180.0 * th).astype(np.int32), 0, th - 1)

    day = day_tex[v, u]
    night = night_tex[v, u]

    # Lighting: sun somewhat to the left so there is a visible terminator.
    sun = np.array([-0.55, 0.25, 0.80], dtype=np.float32)
    sun /= np.linalg.norm(sun)
    normal = np.dstack([x, y_t, z_t])
    lambert = np.clip((normal * sun).sum(axis=2), 0, 1)

    # Soften the day/night boundary; a hard edge looks like a bug.
    blend = np.clip((lambert - 0.04) / 0.30, 0, 1)[..., None]
    rgb = day * (0.25 + 0.95 * lambert[..., None]) * blend + night * 1.25 * (1 - blend)

    # Atmospheric rim: brightest at the limb, tinted toward the page's teal.
    rim = np.clip((rho2 - 0.55) / 0.45, 0, 1) ** 1.6
    atmos = np.array([0.42, 0.72, 0.86], dtype=np.float32)
    rgb = rgb + rim[..., None] * atmos * 0.42 * np.clip(lambert + 0.35, 0, 1)[..., None]

    rgb = np.clip(rgb, 0, 1)
    rgb[~on_globe] = 0.0

    # Alpha: the globe plus a halo of atmosphere beyond its edge.
    alpha = on_globe.astype(np.float32)
    halo = np.clip(1.0 - (np.sqrt(rho2) - 1.0) / 0.12, 0, 1) * (~on_globe)
    alpha = np.clip(alpha + halo * 0.55, 0, 1)
    glow = np.clip(1.0 - (np.sqrt(rho2) - 1.0) / 0.12, 0, 1)[..., None] * atmos * 0.5
    rgb = np.where(on_globe[..., None], rgb, np.clip(glow, 0, 1))

    rgba = np.dstack([rgb, alpha])
    return Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--size", type=int, default=1100)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    day, night = load_textures(args.size)
    log.info("textures loaded: %s", day.shape)

    # Rotate a little over a third of the way round, finishing on Kenya, while
    # closing in. The viewer should feel they are being flown somewhere
    # specific rather than watching a globe spin.
    # End a little east of Kenya so the final frame sits the Rift Valley and
    # the project sites just left of centre, where the headline is not over it.
    start_lon = TARGET_LON + 135.0 + 12.0
    total = 0
    for i in range(args.frames):
        p = i / (args.frames - 1)
        lon = start_lon - 145.0 * p
        # Framing is deliberately CONSTANT. The approach is done on the client
        # by scaling the drawn frame up past the viewport edges, which crops
        # against the window (invisible) rather than against the image boundary
        # (two hard vertical lines, which is what it used to do).
        zoom = 1.0
        img = render_frame(day, night, args.size, lon, zoom)
        path = OUT / f"earth-{i:03d}.webp"
        img.save(path, "WEBP", quality=76, method=4)
        total += path.stat().st_size
        if i % 12 == 0:
            log.info("  frame %02d  lon %+7.1f  zoom %.2f  %.0f kB", i, lon, zoom,
                     path.stat().st_size / 1024)

    log.info("%d frames, %.1f MB total, %.0f kB average",
             args.frames, total / 1048576, total / args.frames / 1024)
    (OUT / "CREDIT.txt").write_text(
        "Earth frames rendered from NASA Blue Marble (surface) and Black Marble\n"
        "(night lights), both public domain, courtesy NASA Earth Observatory.\n"
        "Orthographic projection and lighting computed by scripts/render_globe.py.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
