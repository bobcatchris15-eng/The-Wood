"""Author flower species clump meshes headless.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-flower.py

Metres, Z-up in Blender (glTF export is Y-up per spec). Origin at ground centre: min Z = 0,
footprint centred on X/Y. Vertex colour 'Col' R = wind weight (0 at ground, 1 at clump top).

Geometry, colour and normal maps are procedural. All variation comes from h01(tag, variant,
index, salt), a stateless integer hash, so reruns reproduce the same output. No RNG state.
Textures are painted in numpy (no GIMP, no Pillow). Species rows follow Docs/FloraCatalog.md.
"""

import json
import math
import os
import struct
import sys
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SEED = 5113
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
TEX_SIZE = 512
PREVIEW_PX = 512
SAMPLES = 32
TRI_MIN = 500
TRI_MAX = 5000

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
OUT = os.path.join(REPO, "ArtSource", "Authored", "Flora", "flower")
TEX = os.path.join(OUT, "textures")
PREV = os.path.join(OUT, "previews")

# name, tag, catalogue height range (m), pick height (m), stems, spread, lean, stem radius,
# head kind, petals, petal length, petal width, leaf kind, leaves per stem, leaf length, leaf width,
# stem colour, leaf colour, variants (colourA, colourB, centre, centre fraction)
SPECIES = [
    dict(name="meadow_flower_mix", tag=1, hlo=0.2, hhi=0.6, h=0.40, stems=7, spread=0.30, lean=0.04,
         stem_r=0.0035, head="daisy", npet=7, L=0.030, W=0.011, leaf="basal", leaf_n=2, leaf_L=0.10, leaf_W=0.025,
         stem_c=(0.30, 0.50, 0.20), leaf_c=(0.28, 0.52, 0.18),
         var=[((0.95, 0.80, 0.12), (0.96, 0.95, 0.90), (0.85, 0.60, 0.10), 0.25),
              ((0.50, 0.30, 0.80), (0.92, 0.50, 0.70), (0.95, 0.80, 0.20), 0.25)]),
    dict(name="lupine", tag=2, hlo=0.6, hhi=1.0, h=0.80, stems=6, spread=0.12, lean=0.03,
         stem_r=0.005, head="spire", npet=5, L=0.024, W=0.016, leaf="basal", leaf_n=5, leaf_L=0.14, leaf_W=0.035,
         stem_c=(0.25, 0.45, 0.20), leaf_c=(0.20, 0.45, 0.25),
         var=[((0.30, 0.40, 0.90), (0.50, 0.30, 0.85), (0.90, 0.90, 0.95), 0.20),
              ((0.90, 0.45, 0.70), (0.80, 0.25, 0.60), (0.95, 0.90, 0.80), 0.20)]),
    dict(name="arctic_poppy", tag=3, hlo=0.1, hhi=0.3, h=0.20, stems=6, spread=0.10, lean=0.01,
         stem_r=0.0025, head="cup", npet=4, L=0.040, W=0.030, leaf="basal", leaf_n=4, leaf_L=0.07, leaf_W=0.02,
         stem_c=(0.40, 0.55, 0.35), leaf_c=(0.35, 0.55, 0.40),
         var=[((0.95, 0.94, 0.90), (0.95, 0.94, 0.90), (0.15, 0.12, 0.10), 0.20),
              ((0.95, 0.45, 0.10), (0.98, 0.80, 0.20), (0.10, 0.08, 0.05), 0.20)]),
    dict(name="swamp_iris", tag=4, hlo=0.5, hhi=1.0, h=0.75, stems=5, spread=0.10, lean=0.02,
         stem_r=0.006, head="iris", npet=6, L=0.050, W=0.025, leaf="sword", leaf_n=5, leaf_L=0.50, leaf_W=0.03,
         stem_c=(0.30, 0.50, 0.30), leaf_c=(0.25, 0.50, 0.35),
         var=[((0.36, 0.30, 0.85), (0.45, 0.40, 0.90), (0.95, 0.85, 0.20), 0.20),
              ((0.98, 0.85, 0.20), (0.97, 0.95, 0.80), (0.40, 0.25, 0.10), 0.20)]),
    dict(name="heliconia_bloom", tag=5, hlo=1.0, hhi=2.0, h=1.50, stems=3, spread=0.12, lean=0.03,
         stem_r=0.010, head="bract", npet=3, L=0.20, W=0.07, leaf="sword", leaf_n=4, leaf_L=0.60, leaf_W=0.14,
         stem_c=(0.25, 0.45, 0.20), leaf_c=(0.20, 0.50, 0.20),
         var=[((0.90, 0.12, 0.10), (0.95, 0.30, 0.10), (0.98, 0.85, 0.20), 0.15),
              ((0.98, 0.50, 0.10), (0.98, 0.85, 0.20), (0.80, 0.12, 0.08), 0.15)]),
    dict(name="forest_anemone", tag=6, hlo=0.1, hhi=0.3, h=0.20, stems=5, spread=0.10, lean=0.01,
         stem_r=0.0022, head="star", npet=5, L=0.020, W=0.011, tilt=0.30, leaf="basal", leaf_n=3, leaf_L=0.05, leaf_W=0.03,
         stem_c=(0.35, 0.50, 0.30), leaf_c=(0.30, 0.50, 0.30),
         var=[((0.97, 0.97, 0.95), (0.97, 0.97, 0.95), (0.95, 0.80, 0.25), 0.20),
              ((0.97, 0.80, 0.85), (0.95, 0.70, 0.80), (0.95, 0.80, 0.25), 0.20)]),
    dict(name="savanna_sunflower", tag=7, hlo=0.6, hhi=1.4, h=1.00, stems=3, spread=0.15, lean=0.05,
         stem_r=0.011, head="daisy", npet=12, L=0.050, W=0.017, leaf="basal", leaf_n=4, leaf_L=0.22, leaf_W=0.05,
         stem_c=(0.45, 0.50, 0.25), leaf_c=(0.40, 0.50, 0.25),
         var=[((0.98, 0.78, 0.08), (0.95, 0.70, 0.05), (0.35, 0.20, 0.07), 0.25),
              ((0.95, 0.45, 0.10), (0.98, 0.60, 0.15), (0.25, 0.15, 0.05), 0.25)]),
    dict(name="cotton_grass", tag=8, hlo=0.3, hhi=0.5, h=0.40, stems=9, spread=0.22, lean=0.04,
         stem_r=0.0022, head="fluff", npet=7, L=0.025, W=0.018, leaf="basal", leaf_n=2, leaf_L=0.20, leaf_W=0.008,
         stem_c=(0.35, 0.45, 0.30), leaf_c=(0.35, 0.45, 0.30),
         var=[((0.97, 0.96, 0.92), (0.93, 0.90, 0.80), (0.80, 0.78, 0.70), 0.20),
              ((0.85, 0.87, 0.85), (0.90, 0.92, 0.88), (0.50, 0.60, 0.45), 0.20)]),
    dict(name="frost_saxifrage", tag=9, hlo=0.05, hhi=0.15, h=0.10, stems=5, spread=0.07, lean=0.005,
         stem_r=0.0015, head="star", npet=5, L=0.010, W=0.007, tilt=0.15, leaf="basal", leaf_n=8, leaf_L=0.03, leaf_W=0.012,
         stem_c=(0.40, 0.50, 0.40), leaf_c=(0.45, 0.55, 0.50),
         var=[((0.98, 0.98, 0.97), (0.98, 0.98, 0.97), (0.90, 0.85, 0.60), 0.20),
              ((0.97, 0.80, 0.85), (0.93, 0.70, 0.80), (0.90, 0.80, 0.50), 0.20)]),
]


# ---------------------------------------------------------------- hashing / vectors

def h01(*keys):
    x = SEED & M32
    for k in keys:
        x = (((x ^ (int(k) & M32)) * 0x9E3779B1) & M32)
        x ^= x >> 15
    x = (x * 0x85EBCA6B) & M32
    x ^= x >> 13
    x = (x * 0xC2B2AE35) & M32
    x ^= x >> 16
    return x / 4294967296.0


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    l = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if l < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


# ---------------------------------------------------------------- geometry parts

class Part:
    def __init__(self, name, mat):
        self.name = name
        self.mat = mat
        self.verts = []
        self.faces = []  # (index tuple, uv tuple)

    def v(self, p):
        self.verts.append(p)
        return len(self.verts) - 1

    def quad(self, a, b, c, d, uvs):
        self.faces.append(((a, b, c, d), uvs))

    def tri(self, a, b, c, uvs):
        self.faces.append(((a, b, c), uvs))


def tube(part, pts, radii, segs, v_scale=1.0):
    """Sweep a ring of `segs` verts along polyline pts with per-point radii, capped at both ends."""
    n = len(pts)
    rings = []
    for i in range(n):
        if i == 0:
            t = unit(sub(pts[1], pts[0]))
        elif i == n - 1:
            t = unit(sub(pts[-1], pts[-2]))
        else:
            t = unit(sub(pts[i + 1], pts[i - 1]))
        ref = (0.0, 0.0, 1.0) if abs(t[2]) < 0.9 else (1.0, 0.0, 0.0)
        a = unit(cross(t, ref))
        b = cross(a, t)
        ring = []
        for j in range(segs):
            th = TAU * j / segs
            r = radii[i]
            off = add(mul(a, r * math.cos(th)), mul(b, r * math.sin(th)))
            ring.append(part.v(add(pts[i], off)))
        rings.append(ring)
    for i in range(n - 1):
        v0 = v_scale * i / (n - 1)
        v1 = v_scale * (i + 1) / (n - 1)
        for j in range(segs):
            j2 = (j + 1) % segs
            u0 = j / segs
            u1 = (j + 1) / segs
            part.quad(rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j],
                      ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))
    for ring, idx in ((rings[0], 0), (rings[-1], n - 1)):
        c = part.v(pts[idx])
        for j in range(segs):
            j2 = (j + 1) % segs
            part.tri(c, ring[j], ring[j2], ((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)))


def ribbon(part, pts, widths, facing):
    """Flat two-sided strip along polyline pts. u across 0..1, v along 0..1 (base 0, tip 1)."""
    n = len(pts)
    left, right = [], []
    for i, p in enumerate(pts):
        if i == 0:
            t = sub(pts[1], pts[0])
        elif i == n - 1:
            t = sub(pts[-1], pts[-2])
        else:
            t = sub(pts[i + 1], pts[i - 1])
        s = unit(cross(unit(t), unit(facing)))
        w = widths[i] * 0.5
        left.append(part.v(add(p, mul(s, -w))))
        right.append(part.v(add(p, mul(s, w))))
    for i in range(n - 1):
        v0 = i / (n - 1)
        v1 = (i + 1) / (n - 1)
        part.quad(left[i], right[i], right[i + 1], left[i + 1],
                  ((0.0, v0), (1.0, v0), (1.0, v1), (0.0, v1)))


def petal(part, top, tdir, L, W, rad):
    """Masked card from top along tdir. Facing chosen so the strip is never degenerate."""
    d = unit(tdir)
    facing = (0.0, 0.0, 1.0) if abs(d[2]) < 0.5 else rad
    pts = [add(top, mul(d, L * s)) for s in (0.0, 0.35, 0.7, 1.0)]
    ribbon(part, pts, [W, W, W, W], facing)


def stem_point(base, ldir, lean, H, t):
    return (base[0] + ldir[0] * lean * t * t, base[1] + ldir[1] * lean * t * t, base[2] + H * t)


def basal_leaves(part, base, ang, sp, T, vi, k):
    n = sp["leaf_n"]
    for j in range(n):
        a = ang + (j - (n - 1) / 2.0) * 0.6 + 0.3 * (h01(T, vi, k, 40 + j) - 0.5)
        dv = (math.cos(a), math.sin(a), 0.0)
        L = sp["leaf_L"] * (0.8 + 0.4 * h01(T, vi, k, 50 + j))
        ts = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)
        if sp["leaf"] == "sword":
            pts = [(base[0] + dv[0] * 0.02 * L * t, base[1] + dv[1] * 0.02 * L * t, base[2] + 0.005 + L * t)
                   for t in ts]
        else:
            pts = [(base[0] + dv[0] * L * t, base[1] + dv[1] * L * t, base[2] + 0.01 + 0.22 * L * t * (2.0 - t))
                   for t in ts]
        d = unit(sub(pts[1], pts[0]))
        facing = (0.0, 0.0, 1.0) if abs(d[2]) < 0.5 else dv
        ribbon(part, pts, [sp["leaf_W"]] * 4, facing)


def head(part, sp, top, curve, T, vi, k):
    kind = sp["head"]
    L, W, npet = sp["L"], sp["W"], sp["npet"]
    off = TAU * h01(T, vi, k, 60)
    if kind in ("daisy", "star", "cup"):
        for p in range(npet):
            a = off + TAU * p / npet
            rad = (math.cos(a), math.sin(a), 0.0)
            if kind == "cup":
                tdir = add(mul(rad, 0.55), (0.0, 0.0, 0.9))
            else:
                tz = 0.12 if kind == "daisy" else sp["tilt"]
                tdir = add(rad, (0.0, 0.0, tz))
            petal(part, top, tdir, L * (1.0 + 0.1 * h01(T, vi, k, 70 + p)), W, rad)
        if kind == "daisy":
            tube(part, [add(top, (0.0, 0.0, -0.002)), add(top, (0.0, 0.0, 0.003))],
                 [L * 0.25, L * 0.25], 8)
    elif kind == "spire":
        for t in (0.62, 0.72, 0.82, 0.92, 1.0):
            c = curve(t)
            for q in range(5):
                a = off + TAU * q / 5 + t
                rad = (math.cos(a), math.sin(a), 0.0)
                petal(part, c, add(mul(rad, 0.8), (0.0, 0.0, 0.5)), L, W, rad)
    elif kind == "iris":
        for p in range(6):
            a = off + TAU * p / 6
            rad = (math.cos(a), math.sin(a), 0.0)
            if p % 2 == 0:
                tdir = add(mul(rad, 0.35), (0.0, 0.0, 1.0))
            else:
                tdir = add(rad, (0.0, 0.0, -0.35))
            petal(part, top, tdir, L * (1.0 + 0.1 * h01(T, vi, k, 80 + p)), W, rad)
    elif kind == "bract":
        for p in range(npet):
            a = off + TAU * p / npet
            rad = (math.cos(a), math.sin(a), 0.0)
            petal(part, top, add(mul(rad, 0.3), (0.0, 0.0, 1.0)), L, W, rad)
            tip = add(top, mul(rad, 0.02))
            tube(part, [tip, add(tip, (0.0, 0.0, 0.05))], [0.012, 0.001], 8)
    elif kind == "fluff":
        for p in range(npet):
            a = off + TAU * p / npet + 0.2 * (h01(T, vi, k, 90 + p) - 0.5)
            rad = (math.cos(a), math.sin(a), 0.0)
            petal(part, top, add(mul(rad, 0.6), (0.0, 0.0, 0.55)), L, W, rad)
    else:
        raise ValueError("unknown head " + kind)


def build_clump(sp, vi):
    T = sp["tag"]
    stem = Part("stems", "Stem")
    leaves = Part("leaves", "Leaves")
    petals = Part("petals", "Petals")
    n = sp["stems"] + vi          # variant 2 carries one extra stem
    f = 0.88 if vi == 1 else 1.0  # variant 2 is the smaller size
    for k in range(n):
        ang = TAU * h01(T, vi, k, 0)
        rr = sp["spread"] * math.sqrt(h01(T, vi, k, 1))
        base = (rr * math.cos(ang), rr * math.sin(ang), 0.0)
        H = sp["h"] * f * (0.85 + 0.25 * h01(T, vi, k, 2))
        ldir = (math.cos(ang), math.sin(ang), 0.0)
        lean = sp["lean"] * (0.5 + h01(T, vi, k, 3))
        pts = [stem_point(base, ldir, lean, H, t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
        r = sp["stem_r"]
        tube(stem, pts, [r * 1.3, r * 1.1, r, r * 0.9, r * 0.7], 8)
        basal_leaves(leaves, base, ang, sp, T, vi, k)
        curve = (lambda b, d, ln, hh: (lambda t: stem_point(b, d, ln, hh, t)))(base, ldir, lean, H)
        head(petals, sp, pts[-1], curve, T, vi, k)
    return [stem, leaves, petals]


# ---------------------------------------------------------------- textures (numpy painted)

def grid(size):
    t = np.linspace(0.0, 1.0, size, dtype=np.float32)
    v, u = np.meshgrid(t, t, indexing="ij")  # axis0 = row = v (0 bottom), axis1 = col = u
    return u.astype(np.float32), v.astype(np.float32)


def shape_mask(u, v, kind):
    vv = np.clip(v, 1e-4, 1.0)
    if kind == "petal":
        w = 0.5 * vv ** 0.4 * (1.0 - vv) ** 0.6 / 0.510
    else:
        w = 0.5 * vv ** 0.6 * (1.0 - vv) ** 0.9 / 0.372
    return np.clip((w - np.abs(u - 0.5)) * 160.0, 0.0, 1.0).astype(np.float32)


def normal_map(h, strength):
    gu = np.gradient(h, axis=1) * strength
    gv = np.gradient(h, axis=0) * strength
    n = np.stack([-gu, -gv, np.ones_like(h)], axis=-1)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    rgb = (n * 0.5 + 0.5).astype(np.float32)
    return np.concatenate([rgb, np.ones(h.shape + (1,), np.float32)], axis=-1)


def petal_maps(colA, colB, colC, cf):
    u, v = grid(TEX_SIZE)
    alpha = shape_mask(u, v, "petal")
    side = (u >= 0.5).astype(np.float32)[..., None]
    base = np.asarray(colA, np.float32) * (1.0 - side) + np.asarray(colB, np.float32) * side
    cen = np.clip(1.0 - v / cf, 0.0, 1.0).astype(np.float32)[..., None]
    rgb = base * (1.0 - cen) + np.asarray(colC, np.float32) * cen
    veins = (0.9 + 0.1 * np.cos(TAU * (u - 0.5) * 4.0)).astype(np.float32)[..., None]
    rgb = np.clip(rgb * veins, 0.0, 1.0)
    alb = np.concatenate([rgb, alpha[..., None]], axis=-1).astype(np.float32)
    h = alpha * (0.6 + 0.4 * np.cos(TAU * (u - 0.5) * 4.0))
    return alb, normal_map(h.astype(np.float32), 80.0)


def leaf_maps(rgb):
    u, v = grid(TEX_SIZE)
    alpha = shape_mask(u, v, "leaf")
    mid = np.exp(-((u - 0.5) / 0.05) ** 2).astype(np.float32)
    shade = (0.85 + 0.15 * np.sin(TAU * v * 3.0)).astype(np.float32)
    rgb_a = np.asarray(rgb, np.float32) * (shade * (1.0 + 0.15 * mid))[..., None]
    alb = np.concatenate([np.clip(rgb_a, 0.0, 1.0), alpha[..., None]], axis=-1).astype(np.float32)
    h = (alpha * (0.5 + 0.5 * mid)).astype(np.float32)
    return alb, normal_map(h, 40.0)


def stem_maps(rgb):
    u, v = grid(TEX_SIZE)
    rib = (0.5 + 0.5 * np.sin(TAU * u * 6.0)).astype(np.float32)
    shade = (0.9 + 0.1 * rib).astype(np.float32)
    rgb_a = np.clip(np.asarray(rgb, np.float32) * shade[..., None], 0.0, 1.0)
    alb = np.concatenate([rgb_a, np.ones((TEX_SIZE, TEX_SIZE, 1), np.float32)], axis=-1)
    return alb.astype(np.float32), normal_map((0.5 * rib).astype(np.float32), 60.0)


def write_png(arr, path, name):
    h, w = arr.shape[0], arr.shape[1]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def load_img(path, noncolor=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def write_species_maps(sp):
    n = sp["name"]
    a, b = stem_maps(sp["stem_c"])
    write_png(a, os.path.join(TEX, n + "_stem_alb.png"), "fl_stem_alb")
    write_png(b, os.path.join(TEX, n + "_stem_nrm.png"), "fl_stem_nrm")
    a, b = leaf_maps(sp["leaf_c"])
    write_png(a, os.path.join(TEX, n + "_leaf_alb.png"), "fl_leaf_alb")
    write_png(b, os.path.join(TEX, n + "_leaf_nrm.png"), "fl_leaf_nrm")


def write_variant_maps(sp, vi):
    colA, colB, colC, cf = sp["var"][vi]
    a, b = petal_maps(colA, colB, colC, cf)
    tag = "%s_v%02d" % (sp["name"], vi + 1)
    write_png(a, os.path.join(TEX, tag + "_petal_alb.png"), "fl_petal_alb")
    write_png(b, os.path.join(TEX, tag + "_petal_nrm.png"), "fl_petal_nrm")


# ---------------------------------------------------------------- materials

def make_material(name, diff_img, nor_img=None, masked=False, two_sided=False, rough=0.7):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = rough
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = diff_img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if masked:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    if nor_img is not None:
        ntex = nt.nodes.new("ShaderNodeTexImage")
        ntex.image = nor_img
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    m.use_backface_culling = not two_sided
    if masked:
        if hasattr(m, "blend_method"):
            m.blend_method = "CLIP"
        if hasattr(m, "alpha_threshold"):
            m.alpha_threshold = 0.5
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"  # exporter maps DITHERED to alphaMode MASK
    return m


def build_mats(sp, vi):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    n = sp["name"]
    tag = "%s_v%02d" % (n, vi + 1)
    return {
        "Stem": make_material("Stem", load_img(os.path.join(TEX, n + "_stem_alb.png")),
                              load_img(os.path.join(TEX, n + "_stem_nrm.png"), True)),
        "Leaves": make_material("Leaves", load_img(os.path.join(TEX, n + "_leaf_alb.png")),
                                load_img(os.path.join(TEX, n + "_leaf_nrm.png"), True),
                                masked=True, two_sided=True),
        "Petals": make_material("Petals", load_img(os.path.join(TEX, tag + "_petal_alb.png")),
                                load_img(os.path.join(TEX, tag + "_petal_nrm.png"), True),
                                masked=True, two_sided=True),
    }


# ---------------------------------------------------------------- realise / export / preview

def realise(asset, parts, mats):
    allv = [p for part in parts for p in part.verts]
    minz = min(p[2] for p in allv)
    cx = 0.5 * (min(p[0] for p in allv) + max(p[0] for p in allv))
    cy = 0.5 * (min(p[1] for p in allv) + max(p[1] for p in allv))
    top = max(p[2] for p in allv) - minz
    slots, verts, faces = [], [], []
    for part in parts:
        if part.mat not in slots:
            slots.append(part.mat)
        slot = slots.index(part.mat)
        base = len(verts)
        for (x, y, z) in part.verts:
            verts.append((x - cx, y - cy, z - minz))
        for idx, uvs in part.faces:
            faces.append((tuple(base + i for i in idx), uvs, slot))

    me = bpy.data.meshes.new(asset)
    me.from_pydata(verts, [], [f[0] for f in faces])
    me.update()
    if len(me.polygons) != len(faces):
        raise RuntimeError("polygon count mismatch in %s" % asset)
    for mat_name in slots:
        me.materials.append(mats[mat_name])
    uvl = me.uv_layers.new(name="UVMap")
    for poly, (idx, uvs, slot) in zip(me.polygons, faces):
        poly.material_index = slot
        for k in range(len(idx)):
            loop = poly.loop_start + k
            if me.loops[loop].vertex_index != idx[k]:
                raise RuntimeError("loop order mismatch in %s" % asset)
            uvl.data[loop].uv = uvs[k]
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()

    col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    flat = []
    for (x, y, z) in verts:
        w = min(1.0, max(0.0, z / top)) ** 1.5 if top > 0.0 else 0.0
        flat.extend((w, 0.0, 0.0, 1.0))
    col.data.foreach_set("color", flat)

    tris = sum(len(poly.vertices) - 2 for poly in me.polygons)
    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(p[2] for p in verts))

    ob = bpy.data.objects.new(asset, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, me, {"tris": tris, "dims": dims, "slots": slots}


def export(ob, asset):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    glb = os.path.join(OUT, asset + ".glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True,
                              export_all_vertex_colors=True)
    fbx = os.path.join(OUT, asset + ".fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
                             axis_forward="-Y", axis_up="Z", path_mode="RELATIVE", embed_textures=False)
    return glb


def glb_materials(path):
    with open(path, "rb") as f:
        data = f.read()
    clen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + clen].decode("utf-8"))
    return [(m.get("name"), m.get("alphaMode", "OPAQUE"), m.get("doubleSided", False))
            for m in doc.get("materials", [])]


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def setup_scene():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = False
    sc.render.resolution_x = PREVIEW_PX
    sc.render.resolution_y = PREVIEW_PX
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.lens = 50.0
    cam_d.sensor_width = 36.0
    cam_d.clip_start = 0.01
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam

    sun_d = bpy.data.lights.new("PreviewSun", "SUN")
    sun_d.energy = 3.0
    sun = bpy.data.objects.new("PreviewSun", sun_d)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(35.0))

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.6, 0.65, 0.7, 1.0)
    bg.inputs[1].default_value = 0.8
    sc.world = world
    return cam


def frame_camera(cam, dims):
    dmax = max(dims[0], dims[1], dims[2], 0.05)
    target = Vector((0.0, 0.0, dims[2] * 0.45))
    d = max(0.25, dmax * 2.2)
    dirv = Vector((0.6, -0.75, 0.45)).normalized()
    cam.location = target + dirv * d
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_preview(cam, dims, asset):
    frame_camera(cam, dims)
    bpy.context.scene.render.filepath = os.path.join(PREV, asset + ".png")
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------- main

def main():
    for d in (TEX, PREV):
        os.makedirs(d, exist_ok=True)
    clear_scene()
    cam = setup_scene()
    rows = []
    fails = []
    for sp in SPECIES:
        write_species_maps(sp)
        for vi in range(2):
            asset = "%s_v%02d" % (sp["name"], vi + 1)
            write_variant_maps(sp, vi)
            mats = build_mats(sp, vi)
            parts = build_clump(sp, vi)
            ob, me, info = realise(asset, parts, mats)
            glb = export(ob, asset)
            render_preview(cam, info["dims"], asset)
            dw, dd, dh = info["dims"]
            print("ASSET %s tris=%d dims_m(W x D x H)=%.3f x %.3f x %.3f" % (asset, info["tris"], dw, dd, dh))
            for mname, mode, ds in glb_materials(glb):
                print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
            if not (sp["hlo"] <= dh <= sp["hhi"]):
                fails.append("%s height %.3f outside %s" % (asset, dh, (sp["hlo"], sp["hhi"])))
            if not (TRI_MIN <= info["tris"] <= TRI_MAX):
                fails.append("%s tris %d outside %d..%d" % (asset, info["tris"], TRI_MIN, TRI_MAX))
            if info["slots"] != ["Stem", "Leaves", "Petals"]:
                fails.append("%s slots %s" % (asset, info["slots"]))
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.meshes.remove(me)
            rows.append((asset, info))

    lines = [
        "# Flower authored meshes",
        "",
        "Generated by `Tools/Author-Flora-flower.py` (headless Blender 5.2). Deterministic: rerun reproduces the same geometry and textures.",
        "",
        "Conventions: metres; Blender scene is Z-up, GLB is Y-up per spec, FBX is Z-up; origin at ground centre (min Z = 0, footprint centred on X/Y).",
        "Vertex colour `Col`: R = wind weight (0 at ground, 1 at clump top), G = B = 0, A = 1.",
        "",
        "| File | Tris (LOD0) | W x D x H (m) | Material slots |",
        "|------|-------------|---------------|----------------|",
    ]
    for asset, info in rows:
        dw, dd, dh = info["dims"]
        lines.append("| %s.glb / .fbx | %d | %.3f x %.3f x %.3f | %s |" %
                     (asset, info["tris"], dw, dd, dh, ", ".join(info["slots"])))
    lines += [
        "",
        "Variants: `<species>_v01` is the full-size colour variant; `<species>_v02` is 88% height, one extra stem, and a second colour.",
        "Each petal material carries a two-colour split (colour A for the u<0.5 half of each petal, colour B for the rest), plus a darker centre where the species has one.",
        "",
        "Materials:",
        "- `Stem`: opaque, two-sided off. Per-species albedo and normal (`textures/<species>_stem_{alb,nrm}.png`, 512 px).",
        "- `Leaves`: alpha-masked, two-sided. Per-species albedo and normal (`textures/<species>_leaf_{alb,nrm}.png`, 512 px RGBA). Blender exports alphaMode BLEND, not MASK; set MASK on import.",
        "- `Petals`: alpha-masked, two-sided masked cards. Per-variant albedo and normal (`textures/<species>_v<NN>_petal_{alb,nrm}.png`, 512 px RGBA). Blender exports alphaMode BLEND, not MASK; set MASK on import.",
        "",
        "Previews: `previews/<species>_v<NN>.png`, 512 px, Cycles CPU, transparent background.",
        "",
        "Provenance:",
        "- Geometry: procedural, generated by this script. No third-party meshes.",
        "- Textures: painted procedurally in numpy by this script. No Poly Haven, Vivarium or other third-party maps used.",
        "- Deviation from the spec wording: petal textures are painted in numpy inside Blender rather than in GIMP or Pillow.",
        "- Species rows: Docs/FloraCatalog.md flower entries (lupine, arctic_poppy, swamp_iris, heliconia_bloom, forest_anemone, savanna_sunflower, cotton_grass, frost_saxifrage, meadow_flower_mix).",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d flower variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
