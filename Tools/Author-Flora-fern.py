"""Author fern and moss/lichen flora headless.

Ferns: bracken, tree_fern, royal_fern, lady_fern, rock_fern. Two variants each, LOD0 + LOD1.
Moss/lichen: feather_moss, sphagnum_hummock, ground_moss_carpet, rock_moss_patch, lichen_crust.
Two variants each, single LOD0.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-fern.py

Metres, Z-up in Blender (glTF/FBX output Y-up). Ferns: origin at ground under the crown.
Moss/lichen: origin at lowest vertex (min Z = 0).
Fern geometry: rachis polyline grown from a crown with gravity arch. Pinnae are alpha-cut
cards along the rachis; each card UVs a procedural pinna atlas (lanceolate mask, serrated
edge) whose colour anchor is the green frond pixels of the CC0 Poly Haven fern_02 diffuse.
Tree-fern trunk and rachis stems use the CC0 Poly Haven dead_tree_trunk diffuse (tinted).
Moss and lichen are displaced polar discs using Vivarium Moss002 and LichenThallus textures.
All variation comes from h01(), a stateless integer hash, so reruns reproduce the geometry.
Output dir is owned by this script: ArtSource/Authored/Flora/fern/.
"""

import json
import math
import os
import shutil
import struct
import sys
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SEED = 4417
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
Z = (0.0, 0.0, 1.0)
XAX = (1.0, 0.0, 0.0)
PIN_TEX = 256
STEM_TEX = 512
MOSS_TEX = 1024
LICHEN_TEX = 512
FROND_TARGET_LUM = 0.27
GRID = 17

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "fern")
TEX = os.path.join(OUT, "textures")
SRC = os.path.join(TEX, "src")
PREV = os.path.join(OUT, "previews")

POLY = os.path.join(ART, "PolyHaven")
VIV = r"C:\Misc\Vivarium\game\Textures"

SRC_FROND_ORIG = os.path.join(POLY, "fern_02", "textures", "fern_02_diff_1k.jpg")
SRC_BARK_ORIG = os.path.join(POLY, "dead_tree_trunk", "textures", "dead_tree_trunk_diff_1k.jpg")
SRC_NOR_ORIG = os.path.join(POLY, "dead_tree_trunk", "textures", "dead_tree_trunk_nor_gl_1k.jpg")
SRC_MOSS_ORIG = os.path.join(VIV, "Moss002_1K-JPG_Color.jpg")
SRC_MOSSN_ORIG = os.path.join(VIV, "Moss002_1K-JPG_NormalGL.jpg")
SRC_LICHEN_ORIG = os.path.join(VIV, "LichenThallus.png")

SRC_FROND = os.path.join(SRC, "fern_02_diff_1k.jpg")
SRC_BARK = os.path.join(SRC, "dead_tree_trunk_diff_1k.jpg")
SRC_NOR = os.path.join(SRC, "dead_tree_trunk_nor_gl_1k.jpg")
SRC_MOSS = os.path.join(SRC, "Moss002_1K-JPG_Color.jpg")
SRC_MOSSN = os.path.join(SRC, "Moss002_1K-JPG_NormalGL.jpg")
SRC_LICHEN = os.path.join(SRC, "LichenThallus.png")

# Catalogue rows: Docs/FloraCatalog.md (fern rows; moss rows).
# Fern: nfr fronds per clump, elev deg initial frond angle, Lf frond length m per variant,
# grav arch (total downward bend ~0.9*grav), nsteps rachis segments, P pinnae per side,
# fold = second card per pinna, pmax pinna length as fraction of Lf, pe taper exponent,
# pw pinna width fraction of pinna length, palpha pinna angle from rachis, pdroop pinna droop.
FERNS = [
    dict(id="bracken", tag=21, nfr=12, elev=60.0, Lf=(1.35, 1.60), grav=0.55, nsteps=40,
         P=24, fold=True, tstart=0.10, pmax=0.22, pe=0.9, pw=0.30, palpha=58.0, pdroop=0.10,
         rstem=0.006, clumps=1, offs=[(0.0, 0.0)], tassel=False, trunk=None,
         stem_tint=(0.62, 0.66, 0.38), hrange=(0.8, 2.0), tints=[(0.95, 1.00, 0.80), (1.00, 0.88, 0.55)],
         tint_names=["green", "ochre-yellow"],
         silhouette="tall triangular branched fronds, dense stand, longest pinnae low"),
    dict(id="tree_fern", tag=22, nfr=16, elev=30.0, Lf=(1.50, 1.70), grav=0.9, nsteps=40,
         P=34, fold=True, tstart=0.12, pmax=0.20, pe=0.45, pw=0.25, palpha=62.0, pdroop=0.05,
         rstem=0.008, clumps=1, offs=[(0.0, 0.0)], tassel=False, trunk=(2.7, 3.8), trunk_r=0.11,
         stem_tint=(0.72, 0.64, 0.52), hrange=(3.0, 7.0), tmax=30000,
         tints=[(0.85, 1.00, 0.90), (0.70, 0.85, 0.95)], tint_names=["green", "blue-green"],
         silhouette="single upright trunk, umbrella crown of arching fronds"),
    dict(id="royal_fern", tag=23, nfr=9, elev=70.0, Lf=(1.10, 1.35), grav=0.15, nsteps=40,
         P=26, fold=False, tstart=0.08, pmax=0.15, pe=0.35, pw=0.28, palpha=65.0, pdroop=0.02,
         rstem=0.007, clumps=1, offs=[(0.0, 0.0)], tassel=True, trunk=None,
         stem_tint=(0.72, 0.66, 0.40), hrange=(1.0, 2.0),
         tints=[(0.90, 1.00, 0.85), (1.00, 0.80, 0.60)], tint_names=["green", "rust"],
         silhouette="upright clustered fronds with tassel tips"),
    dict(id="lady_fern", tag=24, nfr=18, elev=45.0, Lf=(0.70, 0.80), grav=0.8, nsteps=30,
         P=30, fold=True, tstart=0.10, pmax=0.11, pe=0.7, pw=0.30, palpha=60.0, pdroop=0.05,
         rstem=0.002, clumps=1, offs=[(0.0, 0.0)], tassel=False, trunk=None,
         stem_tint=(0.60, 0.66, 0.45), hrange=(0.4, 0.9),
         tints=[(0.92, 1.00, 0.92), (0.80, 0.95, 0.90)], tint_names=["pale green", "blue-green"],
         silhouette="lacy fine fronds in tight vase clump"),
    dict(id="rock_fern", tag=25, nfr=8, elev=50.0, Lf=(0.14, 0.18), grav=0.5, nsteps=16,
         P=9, fold=True, tstart=0.10, pmax=0.30, pe=0.5, pw=0.40, palpha=50.0, pdroop=0.05,
         rstem=0.0012, clumps=3, offs=[(0.0, 0.0), (0.07, 0.03), (-0.06, 0.05)], tassel=False,
         trunk=None, stem_tint=(0.55, 0.58, 0.50), hrange=(0.1, 0.3),
         tints=[(0.80, 0.90, 0.80), (0.70, 0.80, 0.66)], tint_names=["grey-green", "silver-green"],
         silhouette="tiny rosettes clinging to stone"),
]

# Moss/lichen: H = mound peak m per variant (lichen: edge lift m), R radius m, edge = outline wobble,
# hum = hummock bumps, tile = texture repeats across diameter.
MOSS = [
    dict(id="feather_moss", tag=31, kind="moss", R=0.38, H=(0.03, 0.045), edge=0.18, hum=0, tile=2.0,
         tints=[(0.62, 0.82, 0.42), (0.46, 0.66, 0.30)], tint_names=["green", "dark green"],
         silhouette="soft feathery carpet on ground, low"),
    dict(id="sphagnum_hummock", tag=32, kind="moss", R=0.30, H=(0.10, 0.16), edge=0.20, hum=3, tile=2.0,
         tints=[(0.82, 0.90, 0.66), (0.95, 0.66, 0.55)], tint_names=["pale green", "rust-red"],
         silhouette="puffy hummocks mixing pale and red moss"),
    dict(id="ground_moss_carpet", tag=33, kind="moss", R=0.50, H=(0.025, 0.045), edge=0.15, hum=0, tile=2.0,
         tints=[(0.70, 1.00, 0.45), (0.45, 0.60, 0.30)], tint_names=["bright green", "dark olive"],
         silhouette="tight cushion over roots and soil"),
    dict(id="rock_moss_patch", tag=34, kind="moss", R=0.30, H=(0.07, 0.13), edge=0.22, hum=2, tile=1.5,
         tints=[(0.70, 0.90, 0.55), (0.62, 0.72, 0.62)], tint_names=["green", "grey-green"],
         silhouette="green cushion draped over stone, mound form"),
    dict(id="lichen_crust", tag=35, kind="lichen", R=0.22, H=(0.015, 0.035), edge=0.25, hum=0, tile=1.0,
         tints=[(0.70, 0.78, 0.68), (0.98, 0.80, 0.50)], tint_names=["grey-green", "orange-brown pale"],
         silhouette="flat crust on stone with lobed leafy edge"),
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


def length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def unit(a):
    l = length(a)
    if l < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def lerp(a, b, f):
    return add(mul(a, 1.0 - f), mul(b, f))


def perp(d):
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    a = unit(cross(d, ref))
    b = unit(cross(a, d))
    return a, b


def lat_of(d):
    """Unit vector perpendicular to d, horizontal-ish when d is not vertical."""
    return unit(cross(d, Z)) if abs(d[2]) < 0.95 else unit(cross(d, XAX))


# ---------------------------------------------------------------- value noise (hash grid)

def make_grid(tag):
    return np.array([[h01(tag, i, j, 3) for i in range(GRID)] for j in range(GRID)], dtype=np.float64)


def vnoise(grid, x, y):
    """Bilinear value noise. grid[y, x]; x, y in grid cell units [0, GRID-1]. Scalar or array."""
    g = grid.shape[0] - 1
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, g - 1e-6)
    y = np.clip(np.asarray(y, dtype=np.float64), 0.0, g - 1e-6)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    top = grid[y0, x0] * (1.0 - fx) + grid[y0, x0 + 1] * fx
    bot = grid[y0 + 1, x0] * (1.0 - fx) + grid[y0 + 1, x0 + 1] * fx
    return top * (1.0 - fy) + bot * fy


# ---------------------------------------------------------------- geometry parts

class Part:
    def __init__(self, name, mat):
        self.name = name
        self.mat = mat
        self.verts = []
        self.faces = []

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
        a, b = perp(t)
        ring = []
        for j in range(segs):
            th = TAU * j / segs
            off = add(mul(a, radii[i] * math.cos(th)), mul(b, radii[i] * math.sin(th)))
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


# ---------------------------------------------------------------- fern geometry

def frond_points(sp, base, az, el, Lf, key):
    """Rachis polyline: starts at base, arches under gravity increasing toward the tip."""
    nst = sp["nsteps"]
    d = unit((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
    pts = [base]
    cur = base
    ds = Lf / nst
    for i in range(nst):
        bend = 1.8 * sp["grav"] * ((i + 1) / nst) / nst
        wx = (h01(key, i, 1) - 0.5) * 0.06
        wy = (h01(key, i, 2) - 0.5) * 0.06
        d = unit((d[0] + wx, d[1] + wy, d[2] - bend))
        cur = add(cur, mul(d, ds))
        pts.append(cur)
    return pts


def add_card(part, P0, Dv, W, Lp, w):
    tip = add(P0, mul(Dv, Lp))
    hw = mul(W, w * 0.5)
    i0 = part.v(sub(P0, hw))
    i1 = part.v(add(P0, hw))
    i2 = part.v(add(tip, hw))
    i3 = part.v(sub(tip, hw))
    part.quad(i0, i1, i2, i3, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))


def rachis_frame(pts, t):
    M = len(pts) - 1
    x = min(max(t, 0.0), 1.0) * M
    i0 = min(M - 1, int(x))
    f = x - i0
    P0 = lerp(pts[i0], pts[i0 + 1], f)
    T = unit(sub(pts[i0 + 1], pts[i0]))
    S = lat_of(T)
    Nf = unit(cross(T, S))
    return P0, T, S, Nf


def pinna(part, sp, Lf, P0, T, S, Nf, side, t, fold, key):
    a = math.radians(sp["palpha"])
    Dv = unit(add(add(mul(T, math.cos(a)), mul(S, side * math.sin(a))), (0.0, 0.0, -sp["pdroop"])))
    Lp = sp["pmax"] * Lf * ((1.0 - t) ** sp["pe"]) * (0.85 + 0.30 * h01(key, 1))
    w = Lp * sp["pw"]
    W = unit(cross(Nf, Dv))
    add_card(part, P0, Dv, W, Lp, w)
    if fold:
        fa = math.radians(38.0)
        W2 = unit(add(mul(W, math.cos(fa)), mul(Nf, math.sin(fa))))
        add_card(part, P0, Dv, W2, Lp, w)


def build_frond(sp, lod, leaf, stem, base, az, el, Lf, key):
    pts = frond_points(sp, base, az, el, Lf, key)
    n = len(pts)
    radii = [sp["rstem"] * (1.0 - 0.7 * i / (n - 1)) for i in range(n)]
    tube(stem, pts, radii, 3 if lod == 0 else 2, v_scale=1.0)
    P = sp["P"]
    fold = sp["fold"] and lod == 0
    step = 1 if lod == 0 else 2
    for si, side in enumerate((1.0, -1.0)):
        for j in range(0, P, step):
            jit = (h01(key, 50 + j, 9 + si) - 0.5) * 0.6
            t = sp["tstart"] + (1.0 - sp["tstart"]) * (j + 0.5 + jit) / P
            if t >= 0.995 or t <= 0.0:
                continue
            P0, T, S, Nf = rachis_frame(pts, t)
            pinna(leaf, sp, Lf, P0, T, S, Nf, side, t, fold, key * 1000 + j * 2 + si)
    if sp["tassel"] and lod == 0:
        tip = pts[-1]
        Dt = unit(sub(pts[-1], pts[-2]))
        Lat = lat_of(Dt)
        Nt = unit(cross(Dt, Lat))
        for q in range(4):
            ang = TAU * q / 4.0 + 0.4
            side_v = add(mul(Lat, math.cos(ang)), mul(Nt, math.sin(ang)))
            D = unit(add(Dt, mul(side_v, 0.6)))
            Lp = sp["pmax"] * Lf * 0.6
            W = unit(cross(Nt, D))
            add_card(leaf, tip, D, W, Lp, Lp * 0.6)


def trunk_part(stem, Ht, r0, lod, key):
    K = 24 if lod == 0 else 12
    pts = [(0.0, 0.0, Ht * k / K) for k in range(K + 1)]
    radii = []
    for k, p in enumerate(pts):
        taper = 1.0 - 0.22 * p[2] / Ht
        bump = 1.0 + 0.05 * (h01(key, k, 3) - 0.5) * 2.0
        radii.append(r0 * taper * bump)
    tube(stem, pts, radii, 16 if lod == 0 else 8, v_scale=Ht * 1.2)


def build_fern(sp, var, lod):
    leaf = Part("fronds", "Fronds")
    stem = Part("stems", "Stem")
    Lf = sp["Lf"][var]
    el = math.radians(sp["elev"])
    if sp["trunk"] is not None:
        Ht = sp["trunk"][var]
        trunk_part(stem, Ht, sp["trunk_r"], lod, sp["tag"] * 100 + var)
        crown = (0.0, 0.0, Ht - 0.02)
    else:
        crown = (0.0, 0.0, 0.02)
    for ci, (ox, oy) in enumerate(sp["offs"]):
        base = add(crown, (ox, oy, 0.0))
        for i in range(sp["nfr"]):
            key = (sp["tag"] * 10 + var) * 10000 + ci * 100 + i
            az = TAU * (i + (h01(key, 7) - 0.5) * 0.8) / sp["nfr"]
            e = el * (1.0 + (h01(key, 8) - 0.5) * 0.2)
            L = Lf * (0.9 + 0.2 * h01(key, 9))
            build_frond(sp, lod, leaf, stem, base, az, e, L, key)
    return [leaf, stem]


# ---------------------------------------------------------------- moss / lichen geometry

def build_mound(sp, var):
    part = Part("moss", "Moss")
    R = sp["R"]
    Hm = sp["H"][var]
    lichen = sp["kind"] == "lichen"
    M = 8 if lichen else 14
    S = 36 if lichen else 40
    tag = sp["tag"] * 10
    gE = make_grid(tag + 1)
    gB = make_grid(tag + 2)
    gL = make_grid(tag + 3)
    bumps = []
    for k in range(sp["hum"]):
        cx = (h01(tag, k, 4) - 0.5) * R
        cy = (h01(tag, k, 5) - 0.5) * R
        sg = R * (0.22 + 0.10 * h01(tag, k, 6))
        amp = 0.5 + 0.5 * h01(tag, k, 7)
        bumps.append((cx, cy, sg, amp))
    g = GRID - 1

    def height(x, y, rho, th):
        if lichen:
            lobe = float(vnoise(gL, (math.cos(th) * 0.5 + 0.5) * g, (math.sin(th) * 0.5 + 0.5) * g))
            return 0.002 + Hm * (rho ** 4) * (0.35 + 0.65 * lobe)
        shape = max(0.0, 1.0 - rho * rho) ** 0.9
        bump = 0.80 + 0.45 * float(vnoise(gB, (x / R * 0.5 + 0.5) * g, (y / R * 0.5 + 0.5) * g))
        for (cx, cy, sg, amp) in bumps:
            bump += amp * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * sg * sg))
        return Hm * shape * bump

    tile = sp["tile"]

    def uv_of(p):
        return (0.5 + p[0] / (2.0 * R) * tile, 0.5 + p[1] / (2.0 * R) * tile)

    centre = part.v((0.0, 0.0, height(0.0, 0.0, 0.0, 0.0)))
    rings = []
    for k in range(1, M + 1):
        rho = k / M
        ring = []
        for j in range(S):
            th = TAU * j / S
            e = 1.0 + sp["edge"] * (float(vnoise(gE, (math.cos(th) * 0.5 + 0.5) * g,
                                                  (math.sin(th) * 0.5 + 0.5) * g)) - 0.5) * 2.0
            r = R * rho * e
            x = r * math.cos(th)
            y = r * math.sin(th)
            ring.append(part.v((x, y, height(x, y, rho, th))))
        rings.append(ring)
    for j in range(S):
        j2 = (j + 1) % S
        a, b = rings[0][j], rings[0][j2]
        part.tri(centre, a, b, (uv_of(part.verts[centre]), uv_of(part.verts[a]), uv_of(part.verts[b])))
    for k in range(M - 1):
        for j in range(S):
            j2 = (j + 1) % S
            a, b = rings[k][j], rings[k][j2]
            c, d = rings[k + 1][j2], rings[k + 1][j]
            part.quad(a, b, c, d, tuple(uv_of(part.verts[i]) for i in (a, b, c, d)))
    return part


# ---------------------------------------------------------------- textures / materials

def load_img(path, noncolor=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def square_pixels_from(path, size):
    """Fresh load (no cache, no mutation of shared images), resampled to size x size RGBA."""
    img = bpy.data.images.load(path, check_existing=False)
    if tuple(img.size) != (size, size):
        img.scale(size, size)
    buf = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(size, size, 4).copy()


def write_png(arr, path, name):
    size = arr.shape[0]
    img = bpy.data.images.new(name, arr.shape[1], size, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def frond_anchor():
    """Green frond colour from the CC0 fern_02 diffuse, normalised to unit luminance."""
    px = square_pixels_from(SRC_FROND, 512)[..., :3]
    green = px[..., 1] - np.maximum(px[..., 0], px[..., 2])
    m = green > 0.03
    if int(m.sum()) < 200:
        col = np.array([0.25, 0.42, 0.12])
    else:
        col = px[m].mean(axis=0)
    print("ANCHOR fern_02 frond px=%d mean=(%.3f %.3f %.3f)" % (int(m.sum()), col[0], col[1], col[2]))
    lum = 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]
    return col / max(float(lum), 1e-4)


ANCHOR = None


def pinna_atlas(sp, var):
    n = PIN_TEX
    a = (np.arange(n) + 0.5) / n
    c = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    A = np.broadcast_to(a[:, None], (n, n))
    C = np.broadcast_to(c[None, :], (n, n))
    f = np.power(A, 0.5) * np.power(np.maximum(1.0 - A, 0.0), 0.8)
    f = f / f.max()
    half = 0.92 * f * (1.0 + 0.05 * np.sin(A * 120.0))
    alpha = np.clip((half - np.abs(C)) * (n / 2.0) + 0.5, 0.0, 1.0)
    grid = make_grid(sp["tag"] * 100 + var + 40)
    noise = vnoise(grid, (C + 1.0) / 2.0 * (GRID - 1), A * (GRID - 1))
    mid = 1.0 + 0.10 * np.exp(-(C / 0.06) ** 2)
    shade = 0.80 + 0.40 * noise
    col = np.array(ANCHOR) * FROND_TARGET_LUM * np.array(sp["tints"][var], dtype=np.float64)
    rgb = col[None, None, :] * (shade * mid * (1.0 - 0.2 * A))[..., None]
    out = np.empty((n, n, 4), dtype=np.float32)
    out[..., :3] = np.clip(rgb, 0.0, 1.0)
    out[..., 3] = alpha
    return out


def fern_mats(sp, var):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    pin_path = os.path.join(TEX, "%s_v%02d_pinna.png" % (sp["id"], var + 1))
    write_png(pinna_atlas(sp, var), pin_path, "pinna_%s_%d" % (sp["id"], var + 1))
    bark = square_pixels_from(SRC_BARK, STEM_TEX)
    bark[..., :3] = np.clip(bark[..., :3] * np.array(sp["stem_tint"], dtype=np.float32)[None, None, :], 0.0, 1.0)
    stem_path = os.path.join(TEX, "%s_v%02d_stem.png" % (sp["id"], var + 1))
    write_png(bark, stem_path, "stem_%s_%d" % (sp["id"], var + 1))
    nor = load_img(SRC_NOR, noncolor=True)
    return {
        "Fronds": make_material("Fronds", load_img(pin_path), masked=True, two_sided=True, rough=0.55),
        "Stem": make_material("Stem", load_img(stem_path), nor, rough=0.8),
    }


def moss_mats(sp, var):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    tint = np.array(sp["tints"][var], dtype=np.float32)[None, None, :]
    if sp["kind"] == "lichen":
        px = square_pixels_from(SRC_LICHEN, LICHEN_TEX)
        px[..., :3] = np.clip(px[..., :3] * tint, 0.0, 1.0)
        px[..., 3] = 1.0
        path = os.path.join(TEX, "%s_v%02d_colour.png" % (sp["id"], var + 1))
        write_png(px, path, "lichen_%s_%d" % (sp["id"], var + 1))
        return {"Moss": make_material("Moss", load_img(path), None, rough=0.9)}
    px = square_pixels_from(SRC_MOSS, MOSS_TEX)
    px[..., :3] = np.clip(px[..., :3] * tint, 0.0, 1.0)
    path = os.path.join(TEX, "%s_v%02d_colour.png" % (sp["id"], var + 1))
    write_png(px, path, "moss_%s_%d" % (sp["id"], var + 1))
    nor = load_img(SRC_MOSSN, noncolor=True)
    return {"Moss": make_material("Moss", load_img(path), nor, rough=1.0)}


def make_material(name, diff_img, nor_img=None, masked=False, two_sided=False, rough=0.8):
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
            m.surface_render_method = "DITHERED"
    return m


# ---------------------------------------------------------------- realise / export / preview

def clear_objects():
    for ob in list(bpy.data.objects):
        if ob.type == "MESH":
            bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def make_object(name, parts, mats, wind=True, floor_z=None):
    allz = floor_z if floor_z is not None else min(p[2] for part in parts for p in part.verts)
    lo = [1e18, 1e18, 1e18]
    hi = [-1e18, -1e18, -1e18]
    slots = []
    verts = []
    faces = []
    for part in parts:
        if part.mat not in slots:
            slots.append(part.mat)
        slot = slots.index(part.mat)
        base = len(verts)
        for (x, y, z) in part.verts:
            vv = (x, y, z - allz)
            for a in range(3):
                lo[a] = min(lo[a], vv[a])
                hi[a] = max(hi[a], vv[a])
            verts.append(vv)
        for idx, uvs in part.faces:
            faces.append((tuple(base + i for i in idx), uvs, slot))

    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [f[0] for f in faces])
    me.update()
    if len(me.polygons) != len(faces):
        raise RuntimeError("polygon count mismatch in %s" % name)
    for mat_name in slots:
        me.materials.append(mats[mat_name])
    uvl = me.uv_layers.new(name="UVMap")
    for poly, (idx, uvs, slot) in zip(me.polygons, faces):
        poly.material_index = slot
        for k in range(len(idx)):
            loop = poly.loop_start + k
            if me.loops[loop].vertex_index != idx[k]:
                raise RuntimeError("loop order mismatch in %s" % name)
            uvl.data[loop].uv = uvs[k]
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    tris = sum(len(poly.vertices) - 2 for poly in me.polygons)

    if wind:
        # Wind weight: R = (z / height)^1.2, 0 at base, 1 at tips. Linear values.
        dh = max(hi[2] - lo[2], 1e-6)
        attr = me.color_attributes.new(name="WindWeight", type="FLOAT_COLOR", domain="POINT")
        flat = []
        for vtx in me.vertices:
            w = min(1.0, max(0.0, (vtx.co.z - lo[2]) / dh)) ** 1.2
            flat.extend((w, 0.0, 0.0, 1.0))
        attr.data.foreach_set("color", flat)

    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    dims = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    return ob, {"tris": tris, "dims": dims, "slots": slots}


def select_only(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def export(ob, base):
    select_only(ob)
    glb = os.path.join(OUT, base + ".glb")
    fbx = os.path.join(OUT, base + ".fbx")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True)
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", bake_space_transform=False)
    return glb


def glb_info(path):
    with open(path, "rb") as f:
        data = f.read()
    clen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + clen].decode("utf-8"))
    attrs = set()
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs.update(prim.get("attributes", {}).keys())
    mats = [(m.get("name"), m.get("alphaMode", "OPAQUE"), m.get("doubleSided", False))
            for m in doc.get("materials", [])]
    return attrs, mats


def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    if hasattr(sc.cycles, "use_denoising"):
        sc.cycles.use_denoising = False
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"

    cam_data = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    sun_data = bpy.data.lights.new("PrevSun", "SUN")
    sun_data.energy = 4.0
    sun = bpy.data.objects.new("PrevSun", sun_data)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (0.8, 0.2, 0.6)

    world = bpy.data.worlds.new("PrevWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.60, 0.62, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    sc.world = world


def add_ground(size):
    """Preview-only ground plane. Never exported."""
    s = size
    me = bpy.data.meshes.new("PrevGround")
    me.from_pydata([(-s, -s, -0.002), (s, -s, -0.002), (s, s, -0.002), (-s, s, -0.002)], [], [(0, 1, 2, 3)])
    me.update()
    mat = bpy.data.materials.new("PrevGround")
    mat.use_nodes = True
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (0.20, 0.19, 0.13, 1.0)
            n.inputs["Roughness"].default_value = 1.0
    me.materials.append(mat)
    ob = bpy.data.objects.new("PrevGround", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def remove_ground(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)


def preview(ob, H, path):
    sc = bpy.context.scene
    cam = sc.camera
    dx, dy, _ = ob.dimensions
    R = max(H, dx, dy)
    ground = add_ground(1.5 * R + 0.5)
    d = 1.9 * R + 0.6
    cam.location = (d * 0.72, -d * 0.69, H * 0.5 + 0.25)
    target = Vector((0.0, 0.0, H * 0.40))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    remove_ground(ground)


# ---------------------------------------------------------------- main

def copy_sources():
    pairs = [
        (SRC_FROND_ORIG, SRC_FROND),
        (SRC_BARK_ORIG, SRC_BARK),
        (SRC_NOR_ORIG, SRC_NOR),
        (SRC_MOSS_ORIG, SRC_MOSS),
        (SRC_MOSSN_ORIG, SRC_MOSSN),
        (SRC_LICHEN_ORIG, SRC_LICHEN),
    ]
    for orig, dst in pairs:
        if not os.path.isfile(orig):
            raise FileNotFoundError(orig)
        shutil.copy2(orig, dst)


def main():
    global ANCHOR
    for d in (SRC, TEX, PREV):
        os.makedirs(d, exist_ok=True)
    copy_sources()
    setup_scene()
    ANCHOR = frond_anchor()

    rows = []
    fails = []

    for sp in FERNS:
        for var in (0, 1):
            name = "%s_v%02d" % (sp["id"], var + 1)
            clear_objects()
            mats = fern_mats(sp, var)

            ob, info = make_object(name, build_fern(sp, var, 0), mats, wind=True, floor_z=0.0)
            glb = export(ob, name)
            attrs, gmats = glb_info(glb)
            dw, dd, dh = info["dims"]
            preview(ob, dh, os.path.join(PREV, name + ".png"))
            me0 = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.meshes.remove(me0)

            ob1, info1 = make_object(name + "_LOD1", build_fern(sp, var, 1), mats, wind=True, floor_z=0.0)
            export(ob1, name + "_LOD1")
            me1 = ob1.data
            bpy.data.objects.remove(ob1, do_unlink=True)
            bpy.data.meshes.remove(me1)

            print("ASSET %s tris=%d lod1=%d dims_m=%.2f x %.2f x %.2f" %
                  (name, info["tris"], info1["tris"], dw, dd, dh))
            for mname, mode, ds in gmats:
                print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
            if "COLOR_0" not in attrs:
                fails.append("%s glb missing COLOR_0 wind attribute" % name)
            if not (sp["hrange"][0] <= dh <= sp["hrange"][1]):
                fails.append("%s height %.2f outside %s" % (name, dh, sp["hrange"]))
            tmax = sp.get("tmax", 15000)
            if not (2000 <= info["tris"] <= tmax):
                fails.append("%s tris %d outside 2000-%d" % (name, info["tris"], tmax))
            rows.append((name, sp, var, info, info1, dw, dd, dh))

    for sp in MOSS:
        for var in (0, 1):
            name = "%s_v%02d" % (sp["id"], var + 1)
            clear_objects()
            mats = moss_mats(sp, var)
            ob, info = make_object(name, [build_mound(sp, var)], mats, wind=False, floor_z=None)
            export(ob, name)
            attrs, gmats = glb_info(os.path.join(OUT, name + ".glb"))
            dw, dd, dh = info["dims"]
            preview(ob, dh, os.path.join(PREV, name + ".png"))
            me0 = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.meshes.remove(me0)
            print("ASSET %s tris=%d dims_m=%.3f x %.3f x %.3f" % (name, info["tris"], dw, dd, dh))
            for mname, mode, ds in gmats:
                print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
            if info["tris"] > 2000:
                fails.append("%s tris %d over 2000" % (name, info["tris"]))
            rows.append((name, sp, var, info, None, dw, dd, dh))

    lines = [
        "# Flora fern and moss/lichen authored meshes",
        "",
        "Generated by `Tools/Author-Flora-fern.py` (headless Blender 5.2, Cycles previews). Deterministic: rerun reproduces the same geometry.",
        "",
        "## Ferns",
        "",
        "Method: rachis polylines grown from a crown with gravity arch. Pinnae are alpha-cut two-sided cards along each rachis, alternating sides, tapering toward the tip. Cards UV a procedural pinna atlas (lanceolate mask with serrated edge) whose green is anchored to the CC0 fern_02 frond pixels. Tree-fern trunk and rachis use the CC0 dead_tree_trunk bark.",
        "",
        "Conventions: metres; Blender scene is Z-up, glTF and FBX output Y-up; origin at ground under the crown (min Z = 0 for the crown base). One combined mesh per file.",
        "Slots: `Fronds` (pinnae cards), `Stem` (rachis, tree-fern trunk). Vertex colour `WindWeight` R = (z/height)^1.2, 0 base to 1 tips, linear values, alpha 1.",
        "LOD1: every second pinna, no fold cards, 2-sided rachis.",
        "",
        "| File (.glb / .fbx) | Tris LOD0 | Tris LOD1 | W x D x H (m) | Slots | Colour variant |",
        "|---|---|---|---|---|---|",
    ]
    for name, sp, var, info, info1, dw, dd, dh in rows:
        if "kind" in sp:
            continue
        lines.append("| %s.glb / .fbx | %d | %d | %.2f x %.2f x %.2f | %s | %s |" %
                     (name, info["tris"], info1["tris"], dw, dd, dh,
                      ", ".join(info["slots"]), sp["tint_names"][var]))
    lines += [
        "",
        "Ferns:",
    ]
    for sp in FERNS:
        lines.append("- `%s`: %s. Height range %s m. Variants: %s." %
                     (sp["id"], sp["silhouette"], "%g-%g" % sp["hrange"],
                      "; ".join("v%02d %s" % (i + 1, sp["tint_names"][i]) for i in range(2))))
    lines += [
        "- Not authored here: `fern_02` (existing ArtSource asset, Prepared fern_02_00 to _03) and `glassfinger` (Unreal-only, deferred).",
        "- Tree-fern crown is 16 fronds on a 2.7 to 3.8 m trunk; trunk is a tapered tube with bark, no separate root or scar geometry.",
        "",
        "## Moss and lichen",
        "",
        "Polar displaced discs (one combined mesh, slot `Moss`), zero height at the outline so they sit on the ground. Mounds use value-noise bumps and sphagnum uses three extra hummocks. Lichen is a flat crust with a lobed, lifted edge. No wind attribute.",
        "",
        "| File (.glb / .fbx) | Tris | W x D x H (m) | Colour variant |",
        "|---|---|---|---|",
    ]
    for name, sp, var, info, info1, dw, dd, dh in rows:
        if "kind" not in sp:
            continue
        lines.append("| %s.glb / .fbx | %d | %.3f x %.3f x %.3f | %s |" %
                     (name, info["tris"], dw, dd, dh, sp["tint_names"][var]))
    lines += [
        "",
        "Moss and lichen:",
    ]
    for sp in MOSS:
        lines.append("- `%s`: %s. Catalogue height %s m. Variants: %s." %
                     (sp["id"], sp["silhouette"], "see catalogue", "; ".join("v%02d %s" % (i + 1, sp["tint_names"][i]) for i in range(2))))
    lines += [
        "",
        "Previews: `previews/<name>.png`, 512 px, LOD0, 3/4 view over a preview-only ground plane (not exported).",
        "",
        "## Textures (`textures/`)",
        "",
        "- `<id>_vNN_pinna.png`: 256 px RGBA pinna atlas. Alpha is the procedural pinna mask. Colour is the fern_02 frond green, tinted per variant.",
        "- `<id>_vNN_stem.png`: 512 px bark, tinted from dead_tree_trunk diffuse.",
        "- `<id>_vNN_colour.png`: Moss002 (1024 px) or LichenThallus (512 px) tinted per variant.",
        "- `src/`: copies of the source textures used, see provenance.",
        "",
        "## Provenance",
        "",
        "- Geometry: procedural, generated by this script. No third-party meshes.",
        "- `src/fern_02_diff_1k.jpg`: Poly Haven fern_02 diffuse (CC0 per Poly Haven site licence). Used as colour anchor only. Not individually re-verified against the licence page.",
        "- `src/dead_tree_trunk_diff_1k.jpg`, `src/dead_tree_trunk_nor_gl_1k.jpg`: Poly Haven dead_tree_trunk (CC0 per Poly Haven site licence).",
        "- `src/Moss002_1K-JPG_Color.jpg`, `src/Moss002_1K-JPG_NormalGL.jpg`: copied from C:\\Misc\\Vivarium\\game\\Textures (Vivarium project asset, CC0 status as recorded there; not re-verified).",
        "- `src/LichenThallus.png`: copied from C:\\Misc\\Vivarium\\game\\Textures (Vivarium project asset; not re-verified).",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d fern/moss variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
