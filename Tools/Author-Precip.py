#!/usr/bin/env python3
"""Deterministically author precipitation and wet-ground textures for The-Wood.

Writes to ArtSource/Authored/Precip/:
  rain_streak_atlas.png/.svg     512x512, 4x4 cells of 128
  snowflake_atlas.png/.svg       512x512, 4x4 cells of 128 (dendritic + soft)
  rain_splash_flipbook.png/.svg  1024x256, 8 frames of 128x256 in one row
  ripple_normal_flipbook.png     1024x1024, 4x4 frames of 256 (tangent space)
  README.md

Requires: Pillow, numpy. All randomness is seeded; re-running yields the same
pixels. Self-authored procedural art, CC0 1.0. No third-party inputs.
"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ArtSource" / "Authored" / "Precip"
FEATHER = 1.0  # antialias falloff width in px


def clamp01(a):
    return np.clip(a, 0.0, 1.0)


def seg_dist(X, Y, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        t = np.zeros_like(X)
    else:
        t = clamp01(((X - x0) * dx + (Y - y0) * dy) / L2)
    px = x0 + t * dx
    py = y0 + t * dy
    return np.hypot(X - px, Y - py), t


# Primitives (cell-local px):
#   ('line', x0, y0, x1, y1, width, a0, a1)  round-capped, alpha ramps a0->a1 along length
#   ('ring', cx, cy, rx, ry, width, a)       elliptical stroke
#   ('blob', cx, cy, sigma, a)               gaussian soft dot
def render_cell(prims, w, h, feather=FEATHER):
    X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    A = np.zeros((h, w))
    for p in prims:
        k = p[0]
        if k == "line":
            _, x0, y0, x1, y1, width, a0, a1 = p
            d, t = seg_dist(X, Y, x0, y0, x1, y1)
            a = (a0 + (a1 - a0) * t) * clamp01(1 - (d - width / 2) / feather)
        elif k == "ring":
            _, cx, cy, rx, ry, width, a = p
            e = np.hypot((X - cx) / rx, (Y - cy) / ry)
            dist = np.abs(e - 1) * min(rx, ry)
            a = a * clamp01(1 - (dist - width / 2) / feather)
        elif k == "blob":
            _, cx, cy, sigma, a = p
            a = a * np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (sigma * sigma))
        else:
            raise ValueError(k)
        A = np.maximum(A, a)
    return A


def save_rgba(A, path):
    """White RGB everywhere (no dark fringe), coverage in alpha, straight alpha."""
    rgba = np.zeros(A.shape + (4,), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = np.round(clamp01(A) * 255).astype(np.uint8)
    Image.fromarray(rgba).save(path)


def svg_doc(cells, cw, ch, cols, rows):
    W, H = cols * cw, rows * ch
    defs = [
        '<radialGradient id="soft">'
        '<stop offset="0" stop-color="#fff" stop-opacity="1"/>'
        '<stop offset="0.4" stop-color="#fff" stop-opacity="0.368"/>'
        '<stop offset="0.8" stop-color="#fff" stop-opacity="0.018"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        "</radialGradient>"
    ]
    body = []
    gid = 0
    for i, prims in enumerate(cells):
        r, c = divmod(i, cols)
        ox, oy = c * cw, r * ch
        defs.append(
            f'<clipPath id="cell{i}"><rect x="{ox}" y="{oy}" width="{cw}" height="{ch}"/></clipPath>'
        )
        body.append(f'<g clip-path="url(#cell{i})"><g transform="translate({ox} {oy})">')
        for p in prims:
            k = p[0]
            if k == "line":
                _, x0, y0, x1, y1, width, a0, a1 = p
                if a0 == a1:
                    stroke = "#fff"
                    extra = f'stroke-opacity="{a0:.3f}"'
                else:
                    gid += 1
                    defs.append(
                        f'<linearGradient id="g{gid}" gradientUnits="userSpaceOnUse" '
                        f'x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}">'
                        f'<stop offset="0" stop-color="#fff" stop-opacity="{a0:.3f}"/>'
                        f'<stop offset="1" stop-color="#fff" stop-opacity="{a1:.3f}"/>'
                        "</linearGradient>"
                    )
                    stroke = f"url(#g{gid})"
                    extra = ""
                body.append(
                    f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" '
                    f'stroke="{stroke}" stroke-width="{width:.2f}" stroke-linecap="round" {extra}/>'
                )
            elif k == "ring":
                _, cx, cy, rx, ry, width, a = p
                body.append(
                    f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" fill="none" '
                    f'stroke="#fff" stroke-width="{width:.2f}" stroke-opacity="{a:.3f}"/>'
                )
            elif k == "blob":
                _, cx, cy, sigma, a = p
                body.append(
                    f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{2.5 * sigma:.2f}" '
                    f'fill="url(#soft)" opacity="{a:.3f}"/>'
                )
        body.append("</g></g>")
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<!-- Self-authored, CC0 1.0. Generated by Tools/Author-Precip.py; PNG is the raster of record. -->\n"
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
        f"<defs>{''.join(defs)}</defs>\n" + "\n".join(body) + "\n</svg>\n"
    )


def write_atlas(name, cw, ch, cols, rows, cell_prims):
    A = np.zeros((rows * ch, cols * cw))
    cells = []
    for i in range(cols * rows):
        prims = cell_prims(i)
        cells.append(prims)
        r, c = divmod(i, cols)
        A[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = render_cell(prims, cw, ch)
    save_rgba(A, OUT / f"{name}.png")
    (OUT / f"{name}.svg").write_text(svg_doc(cells, cw, ch, cols, rows), encoding="utf-8", newline="\n")


# ---------- rain streaks: 4x4 of 128, index = row*4+col ----------
def rain_cell(i):
    rng = random.Random(1000 + i)
    cx = 64 + rng.uniform(-22, 22)
    y0 = rng.uniform(-8, 12)
    y1 = rng.uniform(96, 122)
    slant = rng.uniform(-0.10, 0.10) * (y1 - y0)
    w = rng.uniform(1.0, 2.2)
    prims = [("line", cx, y0, cx + slant, y1, w, rng.uniform(0.15, 0.4), rng.uniform(0.7, 0.95))]
    if i % 3 == 0:
        ox = cx + rng.uniform(-30, 30)
        oy = rng.uniform(0, 70)
        ln = rng.uniform(25, 45)
        prims.append(("line", ox, oy, ox + slant * 0.5, oy + ln, w * 0.7, 0.2, 0.5))
    return prims


# ---------- snowflakes: 4x4 of 128; 0-5 dendritic, 6-15 soft ----------
def flake_cell(i):
    rng = random.Random(2000 + i)
    if i < 6:
        R = rng.uniform(44, 54)
        rot = rng.uniform(0, 60)
        w = rng.uniform(1.4, 2.0)
        prims = []
        for k in range(6):
            ang = math.radians(rot + 60 * k)
            ux, uy = math.cos(ang), math.sin(ang)
            prims.append(("line", 64, 64, 64 + ux * R, 64 + uy * R, w, 0.9, 0.9))
            for f in (0.45, 0.7):
                bx, by = 64 + ux * R * f, 64 + uy * R * f
                bl = R * rng.uniform(0.25, 0.35)
                for s in (-1, 1):
                    ba = ang + s * math.radians(60)
                    prims.append(("line", bx, by, bx + math.cos(ba) * bl, by + math.sin(ba) * bl,
                                  w * 0.7, 0.8, 0.8))
        prims.append(("blob", 64, 64, 5.0, 0.9))
        return prims
    sigma = rng.uniform(9, 16)
    return [
        ("blob", 64 + rng.uniform(-3, 3), 64 + rng.uniform(-3, 3), sigma, rng.uniform(0.7, 0.95)),
        ("blob", 64 + rng.uniform(-8, 8), 64 + rng.uniform(-8, 8), 0.5 * sigma, rng.uniform(0.3, 0.5)),
    ]


# ---------- splash: 8 frames of 128x256, one row, base at (64,236) ----------
def splash_frame(f, n=8):
    t = f / (n - 1)
    base_x, base_y = 64.0, 236.0
    prims = []
    rx = 6 + 48 * t ** 0.7
    ry = rx * 0.28
    a = 0.9 * (1 - t) ** 0.8
    if a > 0.02:
        prims.append(("ring", base_x, base_y, rx, ry, 2.2 + 1.5 * (1 - t), a))
    if t > 0.15:
        prims.append(("ring", base_x, base_y, rx * 0.6, ry * 0.6, 1.4, a * 0.6))
    rng = random.Random(3000)
    for _ in range(7):
        vx = rng.uniform(-30, 30)
        vy = rng.uniform(90, 150)
        x = base_x + vx * t
        y = base_y - vy * t + 90 * t * t
        da = 0.9 * (1 - t) ** 0.5
        if da > 0.02 and 0 <= y <= 256 and 0 <= x <= 128:
            prims.append(("line", x, y, x, y, 2.6, da, da))
    return prims


# ---------- ripple normals: 4x4 of 256, integer wavevectors -> seamless tile + seamless loop ----------
def ripple_normals():
    N, GRID, FRAMES = 256, 4, 16
    rng = random.Random(4000)
    waves = []
    while len(waves) < 10:
        kx, ky = rng.randint(-6, 6), rng.randint(-6, 6)
        if kx == 0 and ky == 0:
            continue
        amp = rng.uniform(0.5, 1.0) / math.hypot(kx, ky)
        wt = rng.randint(-2, 2)
        ph = rng.uniform(0, 2 * math.pi)
        waves.append((kx, ky, amp, wt, ph))
    xs = np.arange(N) / N
    X, Y = np.meshgrid(xs, xs)
    grads = []
    for f in range(GRID * GRID):
        gx = np.zeros((N, N))
        gy = np.zeros((N, N))
        for kx, ky, amp, wt, ph in waves:
            c = np.cos(2 * np.pi * (kx * X + ky * Y) + 2 * np.pi * wt * f / FRAMES + ph)
            gx += amp * 2 * np.pi * kx * c
            gy += amp * 2 * np.pi * ky * c
        grads.append((gx, gy))
    S = 0.5 / max(np.max(np.hypot(gx, gy)) for gx, gy in grads)  # peak slope 0.5
    atlas = np.zeros((GRID * N, GRID * N, 3), np.uint8)
    for f, (gx, gy) in enumerate(grads):
        nx, ny, nz = -S * gx, -S * gy, np.ones_like(gx)
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
        rgb = np.stack([nx * inv, ny * inv, nz * inv], -1) * 0.5 + 0.5
        r, c = divmod(f, GRID)
        atlas[r * N:(r + 1) * N, c * N:(c + 1) * N] = np.round(rgb * 255).astype(np.uint8)
    Image.fromarray(atlas).save(OUT / "ripple_normal_flipbook.png")


def check_sizes():
    expect = {
        "rain_streak_atlas.png": (512, 512),
        "snowflake_atlas.png": (512, 512),
        "rain_splash_flipbook.png": (1024, 256),
        "ripple_normal_flipbook.png": (1024, 1024),
    }
    for name, size in expect.items():
        with Image.open(OUT / name) as im:
            assert im.size == size, f"{name} {im.size} != {size}"


README = """# Precipitation and wet-ground textures

Self-authored procedural art by `Tools/Author-Precip.py`. CC0 1.0. No third-party
inputs. Regenerate with `python Tools/Author-Precip.py` (needs Pillow, numpy).
Output is deterministic (seeded).

| File | Size | Layout | Notes |
|---|---|---|---|
| rain_streak_atlas.png / .svg | 512x512 | 4x4 grid of 128x128, index = row*4+col (16 variants) | White RGB, alpha = streak coverage. Straight alpha, no dark fringe. Premultiply on import if the material expects it. |
| snowflake_atlas.png / .svg | 512x512 | 4x4 grid of 128x128 (0-5 dendritic, 6-15 soft) | White RGB, straight alpha. Dendritic = 6 arms with 2 branch pairs. |
| rain_splash_flipbook.png / .svg | 1024x256 | 8 frames in one row, each 128x256, frame 0 = impact, frame 7 = dissipated | Ground contact at (64,236) in each frame. Ring plus droplets. |
| ripple_normal_flipbook.png | 1024x1024 | 4x4 grid of 256x256, index = row*4+col, 16 frames loop | Tangent-space normals, flat = (128,128,255). Seamless tile (integer wavevectors). Seamless loop over 16 frames. Peak slope 0.5. No SVG: procedural. |

SVG files are editable layout sources. Their PNG is the raster of record; the
script renders PNGs analytically from the same primitives, so edges may differ
by sub-pixel antialiasing if the SVG is edited and re-rasterised elsewhere.

Provenance: generated here from seeded random parameters. No external images,
fonts, or traced artwork.
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_atlas("rain_streak_atlas", 128, 128, 4, 4, rain_cell)
    write_atlas("snowflake_atlas", 128, 128, 4, 4, flake_cell)
    write_atlas("rain_splash_flipbook", 128, 256, 8, 1, splash_frame)
    ripple_normals()
    (OUT / "README.md").write_text(README, encoding="utf-8", newline="\n")
    check_sizes()
    print("OK: Precip textures written to", OUT)


if __name__ == "__main__":
    main()
