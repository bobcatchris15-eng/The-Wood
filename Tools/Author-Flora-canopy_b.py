"""Author canopy-b and subcanopy flora headless: 6 species x 3 variants.

Species: acacia_flat, baldcypress, cottonwood_river, emergent_fig (canopy-b);
birch_pale, understory_laurel (subcanopy).

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-canopy_b.py

Writes only under ArtSource/Authored/Flora/canopy_b/ (and textures/ beneath it).
Per variant: <id>_vNN.glb/.fbx, <id>_vNN_LOD1 (~30%), <id>_vNN_LOD2 (~8%), <id>_vNN_preview.png (512 px).
Metres, Blender Z-up, origin at ground centre (min Z = 0, trunk base on XY origin).
GLB is Y-up per glTF spec. FBX is Blender-native Z-up (identity axes).
Vertex colour "WindWeight": R = wind weight (0 at trunk base, 1 at tips/leaves). G = B = 0, A = 1.
Randomness: h01() integer hash only, keyed on species id, branch serial and slot. No RNG state.
"""

import math
import os
import shutil
import sys
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SEED = 7741
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
GOLD = 2.39996322972865332

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "canopy_b")
TEX = os.path.join(OUT, "textures")
VIV = r"C:\Misc\Vivarium\game\Textures"

# (source, staged name in TEX). Staged copies are what the script reads.
STAGE = [
    (os.path.join(VIV, "Bark013_1K-JPG_Color.jpg"), "Bark013_1K-JPG_Color.jpg"),
    (os.path.join(VIV, "Bark013_1K-JPG_NormalGL.jpg"), "Bark013_1K-JPG_NormalGL.jpg"),
    (os.path.join(ART, "PolyHaven", "island_tree_01", "textures", "island_tree_01_leaves_diff_1k.jpg"),
     "island_tree_01_leaves_diff_1k.jpg"),
]
BARK_SRC = os.path.join(TEX, "Bark013_1K-JPG_Color.jpg")
BARK_NOR = os.path.join(TEX, "Bark013_1K-JPG_NormalGL.jpg")
LEAF_SRC = os.path.join(TEX, "island_tree_01_leaves_diff_1k.jpg")
TEX_SIZE = 1024


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


def lerp(a, b, t):
    return add(mul(a, 1.0 - t), mul(b, t))


def rdir(tag, k, s):
    z = 2.0 * h01(tag, k, s, 0) - 1.0
    ph = TAU * h01(tag, k, s, 1)
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return (r * math.cos(ph), r * math.sin(ph), z)


# ---------------------------------------------------------------- geometry primitives

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


def tri_count(part):
    return sum(2 if len(idx) == 4 else 1 for idx, _ in part.faces)


def tube(part, pts, radii, segs, flare=None, v_scale=1.0):
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
            if flare is not None:
                r *= flare(i, th)
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


def card(part, c, d, w, h, tag, k):
    """Quad centred at c, height along d, width along a random perpendicular. Two-sided by material."""
    d = unit(d)
    e = rdir(tag, k, 900)
    a = cross(d, e)
    if length(a) < 1e-6:
        a = cross(d, (1.0, 0.0, 0.0))
    a = unit(a)
    wa = mul(a, w * 0.5)
    hb = mul(d, h * 0.5)
    i0 = part.v(sub(sub(c, wa), hb))
    i1 = part.v(sub(add(c, wa), hb))
    i2 = part.v(add(add(c, wa), hb))
    i3 = part.v(add(sub(c, wa), hb))
    part.quad(i0, i1, i2, i3, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))


def make_flare(pts, amp):
    def f(i, th):
        z = pts[i][2]
        base = amp * max(0.0, 1.0 - z / 2.5) ** 2
        lobe = 0.35 * amp * (max(0.0, math.cos(4.0 * th)) ** 4) * max(0.0, 1.0 - z / 2.0)
        return 1.0 + base + lobe
    return f


# ---------------------------------------------------------------- recursive branching

class Ctx:
    def __init__(self, T, density):
        self.T = T
        self.density = density
        self.n = 0
        self.wood = Part("wood", "Bark")
        self.leaf = Part("foliage", "Leaves")


def squash(off, P):
    # P["sq"] < 1 flattens a crown (acacia umbrella); > 1 would elongate it.
    return (off[0], off[1], off[2] * P.get("sq", 1.0))


def leaf_card(ctx, c, dvec, w, h, jit):
    ctx.n += 1
    s = 0.8 + 0.4 * jit
    card(ctx.leaf, c, dvec, w * s, h * s, ctx.T, ctx.n)


def grow(ctx, P, p0, d, L, r0, depth):
    ctx.n += 1
    b = ctx.n
    T = ctx.T

    def rr(slot):
        return h01(T, b, slot)

    trunk = depth == 0
    nseg = P["trunk_nseg"] if trunk else 4
    segs = P["trunk_segs"] if trunk else 6
    droop = 0.0 if trunk else P["droop"]

    pts = []
    for i in range(nseg + 1):
        t = i / nseg
        wx = (rr(10000 + i) - 0.5) * P["wobble"] * L * t
        wy = (rr(20000 + i) - 0.5) * P["wobble"] * L * t
        pts.append((p0[0] + d[0] * L * t + wx,
                    p0[1] + d[1] * L * t + wy,
                    p0[2] + d[2] * L * t + droop * L * t * t))
    radii = [max(0.006, r0 * (1.0 - P["taper"] * (i / nseg))) for i in range(nseg + 1)]
    flare = make_flare(pts, P["flare"]) if (trunk and P["flare"] > 0) else None
    tube(ctx.wood, pts, radii, segs, flare=flare)

    # foliage strung along interior branches (not the trunk)
    if depth >= 1 and P["along"] > 0:
        n_along = int(round(L * P["along"] * ctx.density))
        for a in range(n_along):
            t = min(1.0, (a + rr(30000 + a)) / n_along)
            cx = p0[0] + d[0] * L * t
            cy = p0[1] + d[1] * L * t
            cz = p0[2] + d[2] * L * t + droop * L * t * t
            off = squash(mul(rdir(T, b, 40000 + a), P["along_r"] * rr(50000 + a) ** 0.5), P)
            leaf_card(ctx, add((cx, cy, cz), off), rdir(T, b, 60000 + a),
                      P["cw"], P["ch"], rr(70000 + a))

    if depth < len(P["kids"]):
        K = P["kids"][depth]
        lo, hi = P["spawn"][depth]
        for c in range(K):
            t = lo + (hi - lo) * (c + 0.15 + 0.7 * rr(80000 + c)) / K
            px = p0[0] + d[0] * L * t
            py = p0[1] + d[1] * L * t
            pz = p0[2] + d[2] * L * t + droop * L * t * t
            az = GOLD * (c + 0.37 * depth) + TAU * 0.2 * (rr(81000 + c) - 0.5)
            el = P["elev"][depth] + (rr(82000 + c) - 0.5) * P["elev_jit"]
            dc = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
            dn = unit(lerp(d, dc, P["mix"][depth]))
            Lc = L * P["lenf"][depth] * (0.8 + 0.4 * rr(83000 + c))
            Lc *= max(0.15, 1.0 - P["taper_kids"] * t)
            rt = max(0.006, r0 * (1.0 - P["taper"] * t))
            rc = max(0.006, rt * P["rf"][depth] * (0.9 + 0.2 * rr(84000 + c)))
            grow(ctx, P, (px, py, pz), dn, Lc, rc, depth + 1)
    else:
        tip = (p0[0] + d[0] * L, p0[1] + d[1] * L, p0[2] + d[2] * L + droop * L)
        n = int(round(P["cl"] * ctx.density))
        for q in range(n):
            off = squash(mul(rdir(T, b, 90000 + q), P["clr"] * rr(100000 + q) ** (1.0 / 3.0)), P)
            leaf_card(ctx, add(tip, off), rdir(T, b, 110000 + q), P["cw"], P["ch"], rr(120000 + q))


def build_geometry(sp, var):
    """Grow the tree, tuning card density until LOD0 lands near P['want'] tris."""
    P = dict(sp["P"])
    P["lenf"] = [x * var["cs"] for x in sp["P"]["lenf"]]
    density = 1.0
    ctx = None
    tb = tl = 0
    for _ in range(8):
        ctx = Ctx(sp["T"], density)
        grow(ctx, P, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), var["H"], var["R0"], 0)
        tb = tri_count(ctx.wood)
        tl = tri_count(ctx.leaf)
        tot = tb + tl
        if abs(tot - P["want"]) <= 0.06 * P["want"]:
            break
        density *= min(4.0, max(0.25, (P["want"] - tb) / max(1.0, tl)))
    return ctx, tb, tl, density


# ---------------------------------------------------------------- species table (canopy-b / subcanopy)

SPECIES = [
    dict(id="acacia_flat", T=21, lo=20000, hi=80000, P=dict(
        kids=[4, 3, 3], spawn=[(0.45, 0.95), (0.30, 0.95), (0.30, 0.90)],
        elev=[0.30, 0.22, 0.15], elev_jit=0.25, mix=[0.85, 0.70, 0.60],
        lenf=[0.55, 0.50, 0.45], rf=[0.50, 0.50, 0.50], taper=0.35, taper_kids=0.20,
        droop=0.0, wobble=0.12, trunk_nseg=8, trunk_segs=12, flare=0.0,
        along=0.8, along_r=0.5, cw=0.6, ch=0.5, cl=70, clr=1.0, sq=0.45, want=32000),
     variants=[
         dict(H=7.5, R0=0.22, cs=0.95, leaf=(0.50, 0.60, 0.42), bark=(0.46, 0.40, 0.34)),
         dict(H=8.5, R0=0.26, cs=1.00, leaf=(0.42, 0.52, 0.30), bark=(0.42, 0.36, 0.30)),
         dict(H=9.0, R0=0.28, cs=1.05, leaf=(0.58, 0.62, 0.36), bark=(0.50, 0.44, 0.36)),
     ]),
    dict(id="baldcypress", T=22, lo=20000, hi=80000, P=dict(
        kids=[8, 4, 3], spawn=[(0.22, 0.97), (0.30, 0.95), (0.30, 0.95)],
        elev=[0.75, 0.55, 0.40], elev_jit=0.30, mix=[0.55, 0.45, 0.35],
        lenf=[0.40, 0.45, 0.45], rf=[0.50, 0.50, 0.50], taper=0.45, taper_kids=0.55,
        droop=-0.12, wobble=0.02, trunk_nseg=16, trunk_segs=18, flare=1.5,
        along=14.0, along_r=0.22, cw=0.46, ch=0.60, cl=50, clr=0.35, sq=1.0, want=42000),
     variants=[
         dict(H=24.0, R0=0.55, cs=1.00, leaf=(0.36, 0.56, 0.26), bark=(0.52, 0.44, 0.36)),
         dict(H=26.0, R0=0.60, cs=1.05, leaf=(0.42, 0.60, 0.30), bark=(0.46, 0.38, 0.30)),
         dict(H=28.0, R0=0.62, cs=1.00, leaf=(0.62, 0.44, 0.18), bark=(0.50, 0.42, 0.34)),
     ]),
    dict(id="cottonwood_river", T=23, lo=20000, hi=80000, P=dict(
        kids=[5, 4, 3], spawn=[(0.35, 0.90), (0.30, 0.90), (0.30, 0.90)],
        elev=[0.50, 0.32, 0.15], elev_jit=0.60, mix=[0.50, 0.40, 0.30],
        lenf=[0.55, 0.50, 0.50], rf=[0.50, 0.55, 0.55], taper=0.40, taper_kids=0.35,
        droop=-0.06, wobble=0.05, trunk_nseg=14, trunk_segs=20, flare=0.4,
        along=0.6, along_r=0.9, cw=1.0, ch=0.9, cl=120, clr=2.2, sq=0.8, want=40000),
     variants=[
         dict(H=24.0, R0=0.55, cs=1.00, leaf=(0.50, 0.70, 0.26), bark=(0.80, 0.78, 0.72)),
         dict(H=26.0, R0=0.60, cs=1.05, leaf=(0.60, 0.74, 0.30), bark=(0.72, 0.70, 0.64)),
         dict(H=28.0, R0=0.62, cs=1.10, leaf=(0.80, 0.68, 0.22), bark=(0.84, 0.82, 0.76)),
     ]),
    dict(id="emergent_fig", T=24, lo=20000, hi=80000, P=dict(
        kids=[5, 4, 3], spawn=[(0.40, 0.90), (0.30, 0.90), (0.30, 0.90)],
        elev=[0.55, 0.35, 0.20], elev_jit=0.50, mix=[0.50, 0.40, 0.30],
        lenf=[0.60, 0.60, 0.55], rf=[0.60, 0.60, 0.60], taper=0.40, taper_kids=0.20,
        droop=-0.12, wobble=0.03, trunk_nseg=14, trunk_segs=28, flare=1.6,
        along=1.0, along_r=1.0, cw=1.3, ch=1.0, cl=120, clr=2.6, sq=0.9, want=60000),
     variants=[
         dict(H=28.0, R0=0.95, cs=1.00, leaf=(0.16, 0.32, 0.14), bark=(0.36, 0.34, 0.30)),
         dict(H=30.0, R0=1.05, cs=1.05, leaf=(0.20, 0.36, 0.16), bark=(0.40, 0.38, 0.32)),
         dict(H=32.0, R0=1.10, cs=1.10, leaf=(0.24, 0.30, 0.12), bark=(0.30, 0.28, 0.25)),
     ]),
    dict(id="birch_pale", T=25, lo=10000, hi=40000, bark="white", P=dict(
        kids=[5, 3, 2], spawn=[(0.40, 0.90), (0.35, 0.90), (0.40, 0.90)],
        elev=[0.50, 0.35, 0.20], elev_jit=0.40, mix=[0.50, 0.40, 0.30],
        lenf=[0.50, 0.55, 0.50], rf=[0.50, 0.50, 0.50], taper=0.35, taper_kids=0.30,
        droop=-0.08, wobble=0.03, trunk_nseg=12, trunk_segs=12, flare=0.0,
        along=0.8, along_r=0.8, cw=0.38, ch=0.32, cl=50, clr=1.6, sq=0.8, want=18000),
     variants=[
         dict(H=11.0, R0=0.17, cs=1.00, leaf=(0.60, 0.78, 0.34), bark=(0.92, 0.90, 0.86)),
         dict(H=13.0, R0=0.19, cs=1.05, leaf=(0.80, 0.70, 0.26), bark=(0.94, 0.92, 0.88)),
         dict(H=14.5, R0=0.20, cs=1.10, leaf=(0.46, 0.70, 0.36), bark=(0.90, 0.88, 0.84)),
     ]),
    dict(id="understory_laurel", T=26, lo=10000, hi=40000, P=dict(
        kids=[5, 4, 3], spawn=[(0.05, 0.35), (0.40, 0.90), (0.40, 0.90)],
        elev=[0.75, 0.50, 0.30], elev_jit=0.40, mix=[0.70, 0.50, 0.40],
        lenf=[0.60, 0.55, 0.50], rf=[0.60, 0.60, 0.60], taper=0.50, taper_kids=0.40,
        droop=-0.15, wobble=0.03, trunk_nseg=8, trunk_segs=14, flare=0.3,
        along=2.0, along_r=0.8, cw=0.9, ch=0.7, cl=90, clr=1.8, sq=0.9, want=24000),
     variants=[
         dict(H=5.5, R0=0.20, cs=1.00, leaf=(0.14, 0.30, 0.12), bark=(0.30, 0.28, 0.24)),
         dict(H=6.5, R0=0.22, cs=1.05, leaf=(0.20, 0.34, 0.14), bark=(0.34, 0.30, 0.26)),
         dict(H=6.0, R0=0.22, cs=1.00, leaf=(0.42, 0.36, 0.14), bark=(0.36, 0.32, 0.28)),
     ]),
]


# ---------------------------------------------------------------- textures

def load_img(path, noncolor=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def square_pixels(path, size):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=False)
    if tuple(img.size) != (size, size):
        img.scale(size, size)
    buf = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(size, size, 4).copy()


def write_png(arr, path, name):
    size = arr.shape[0]
    img = bpy.data.images.new(name, size, size, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def cluster_mask(size, T):
    """Alpha for a leaf-cluster card: 16 ovate leaflets radiating at hashed positions and angles."""
    t = np.linspace(0.0, 1.0, size, dtype=np.float32)
    v, u = np.meshgrid(t, t, indexing="ij")
    m = np.zeros((size, size), dtype=np.float32)
    for j in range(16):
        cx = 0.2 + 0.6 * h01(T, j, 500)
        cy = 0.2 + 0.6 * h01(T, j, 501)
        ang = TAU * h01(T, j, 502)
        L = 0.22 + 0.16 * h01(T, j, 503)
        hw = L * 0.26 * (0.8 + 0.4 * h01(T, j, 504))
        dx = u - cx
        dy = v - cy
        xl = dx * math.cos(ang) + dy * math.sin(ang)
        yl = -dx * math.sin(ang) + dy * math.cos(ang)
        xn = xl / (L * 0.5)
        inside = np.clip(1.0 - xn * xn, 0.0, None)
        halfw = hw * inside ** 0.6
        val = np.clip((halfw - np.abs(yl)) / 0.004, 0.0, 1.0) * (np.abs(xn) <= 1.0)
        m = np.maximum(m, val.astype(np.float32))
    return m


def birch_marks(size, T):
    """Dark horizontal lenticel dashes on a hashed 48 px grid, multiplicative (1.0 = clean)."""
    marks = np.ones((size, size), dtype=np.float32)
    cell = 48
    for gy in range(size // cell):
        for gx in range(size // cell):
            if h01(T, gx, gy, 600) < 0.55:
                continue
            y0 = gy * cell + int(h01(T, gx, gy, 601) * (cell - 6))
            x0 = gx * cell + int(h01(T, gx, gy, 602) * (cell - 20))
            ln = 14 + int(h01(T, gx, gy, 603) * 22)
            th = 3 + int(h01(T, gx, gy, 604) * 3)
            marks[y0:y0 + th, x0:x0 + ln] = 0.16
    return marks


def make_textures(sp, var, name):
    size = TEX_SIZE
    T = sp["T"]
    leaf_src = square_pixels(LEAF_SRC, size)
    bark_src = square_pixels(BARK_SRC, size)

    lt = np.array(var["leaf"], dtype=np.float32).reshape(1, 1, 3)
    leaf = np.empty((size, size, 4), dtype=np.float32)
    tinted = leaf_src[..., :3] * lt
    # Normalise mean luminance to a natural foliage level so dark-tinted species do not render black.
    gain = float(np.clip(0.34 / max(1e-4, float(tinted.mean())), 1.5, 6.0))
    leaf[..., :3] = np.clip(tinted * gain, 0.0, 1.0)
    leaf[..., 3] = cluster_mask(size, T)
    leaf_path = os.path.join(TEX, name + "_leaves.png")
    write_png(leaf, leaf_path, name + "_leaves")

    bt = np.array(var["bark"], dtype=np.float32).reshape(1, 1, 3)
    bark = np.ones((size, size, 4), dtype=np.float32)
    if sp.get("bark") == "white":
        # Birch: pale ground from the bark luminance, grain kept, dark lenticel dashes overlaid.
        lum = bark_src[..., :3].mean(axis=2, keepdims=True)
        col = np.clip(bt * (0.75 + 1.0 * lum), 0.0, 1.0)
        col = col * birch_marks(size, T)[..., None]
        bark[..., :3] = np.clip(col, 0.0, 1.0)
    else:
        bark[..., :3] = np.clip(bark_src[..., :3] * bt * 1.2, 0.0, 1.0)
    bark_path = os.path.join(TEX, name + "_bark.png")
    write_png(bark, bark_path, name + "_bark")
    return leaf_path, bark_path


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
            m.surface_render_method = "DITHERED"  # exporter maps DITHERED to alphaMode MASK
    return m


def build_mats(leaf_png, bark_png):
    bark_img = load_img(bark_png)
    nor_img = load_img(BARK_NOR, noncolor=True)
    leaf_img = load_img(leaf_png)
    return {
        "Bark": make_material("Bark", bark_img, nor_img),
        "Leaves": make_material("Leaves", leaf_img, masked=True, two_sided=True),
    }


# ---------------------------------------------------------------- scene / realise / export

def reset_scene():
    scene = bpy.context.scene
    scene.camera = None
    scene.world = None
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                 bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for x in list(coll):
            if x.name in ("Render Result", "Viewer Node"):
                continue
            coll.remove(x)


def select_only(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def mesh_tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def realise(name, bark, leaf, mats, H):
    """One object, one mesh: Bark slot 0, Leaves slot 1, WindWeight vertex colour."""
    parts = [(bark, "Bark"), (leaf, "Leaves")]
    slots = ["Bark", "Leaves"]
    verts = []
    faces = []
    for si, (part, _) in enumerate(parts):
        base = len(verts)
        verts.extend(part.verts)
        for idx, uvs in part.faces:
            faces.append((tuple(base + i for i in idx), uvs, si))

    zmin = min(p[2] for p in verts)
    verts = [(x, y, z - zmin) for (x, y, z) in verts]

    scale = 0.5 * H
    wind = np.zeros((len(verts), 4), dtype=np.float32)
    idx_bark = len(bark.verts)
    for i, (x, y, z) in enumerate(verts):
        dd = min(1.0, math.sqrt(x * x + y * y + z * z) / scale)
        if i < idx_bark:
            wind[i, 0] = dd
        else:
            wind[i, 0] = 0.7 + 0.3 * dd
    wind[:, 3] = 1.0

    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [f[0] for f in faces])
    me.update()
    if len(me.polygons) != len(faces):
        raise RuntimeError("polygon count mismatch in %s" % name)
    for s in slots:
        me.materials.append(mats[s])
    uvl = me.uv_layers.new(name="UVMap")
    for poly, (idx, uvs, si) in zip(me.polygons, faces):
        poly.material_index = si
        for k in range(len(idx)):
            loop = poly.loop_start + k
            if me.loops[loop].vertex_index != idx[k]:
                raise RuntimeError("loop order mismatch in %s" % name)
            uvl.data[loop].uv = uvs[k]

    ca = me.color_attributes.new(name="WindWeight", type="FLOAT_COLOR", domain="POINT")
    ca.data.foreach_set("color", wind.ravel())
    try:
        me.color_attributes.active_color = ca
    except (AttributeError, TypeError):
        pass

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()

    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def decimate_copy(src, name, ratio):
    me = src.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    select_only(ob)
    mod = ob.modifiers.new("Decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    clean_mesh(ob.data)
    return ob


def clean_mesh(me):
    """Post-decimate repair: weld near-duplicates, drop zero-area faces and loose verts, fix normals."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    degen = [f for f in bm.faces if f.calc_area() < 1e-10]
    if degen:
        bmesh.ops.delete(bm, geom=degen, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    me.update()
    me.validate(verbose=False)


def export_files(ob, base):
    select_only(ob)
    gprops = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kw = dict(export_format="GLB", use_selection=True, export_yup=True)
    if "export_vertex_color" in gprops:
        kw["export_vertex_color"] = "ACTIVE"
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, base + ".glb"), **kw)
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, base + ".fbx"),
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="Y",
        axis_up="Z",
        bake_space_transform=False,
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        path_mode="AUTO",
    )


def render_preview(path, dims):
    scene = bpy.context.scene
    H = dims[2]
    half = 0.5 * max(dims[0], dims[1])
    target = Vector((0.0, 0.0, H * 0.45))
    dist = max(1.9 * H, 3.0 * half)

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.lens = 50.0
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    scene.collection.objects.link(cam)
    cam.location = Vector((0.0, -dist * 0.97, target.z + dist * 0.2))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    sun_d = bpy.data.lights.new("PreviewSun", "SUN")
    sun_d.energy = 3.0
    sun = bpy.data.objects.new("PreviewSun", sun_d)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(35.0))

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.62, 0.70, 0.78, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def stage_sources():
    os.makedirs(TEX, exist_ok=True)
    for src, staged in STAGE:
        if not os.path.isfile(src):
            raise FileNotFoundError(src)
        shutil.copyfile(src, os.path.join(TEX, staged))


def author(sp, var, name):
    reset_scene()
    ctx, tb, tl, density = build_geometry(sp, var)
    leaf_png, bark_png = make_textures(sp, var, name)
    mats = build_mats(leaf_png, bark_png)

    ob0 = realise(name, ctx.wood, ctx.leaf, mats, var["H"])
    tris0 = mesh_tris(ob0.data)
    dims = tuple(ob0.dimensions)
    export_files(ob0, name)
    render_preview(os.path.join(OUT, name + "_preview.png"), dims)

    ob1 = decimate_copy(ob0, name + "_LOD1", 0.30)
    tris1 = mesh_tris(ob1.data)
    export_files(ob1, name + "_LOD1")

    ob2 = decimate_copy(ob0, name + "_LOD2", 0.08)
    tris2 = mesh_tris(ob2.data)
    export_files(ob2, name + "_LOD2")

    return dict(name=name, sp=sp["id"], tris0=tris0, tris1=tris1, tris2=tris2,
                dims=dims, bark_tris=tb, leaf_tris=tl, density=density,
                lo=sp["lo"], hi=sp["hi"], kind="subcanopy" if sp["hi"] == 40000 else "canopy")


def write_readme(rows):
    lines = [
        "# canopy-b flora (authored)",
        "",
        "Generated by `Tools/Author-Flora-canopy_b.py` (headless Blender 5.2). Deterministic: "
        "the same seed and parameters reproduce the same geometry.",
        "",
        "Species (FloraCatalog canopy-b and subcanopy): acacia_flat, baldcypress, cottonwood_river, "
        "emergent_fig (canopy-b, LOD0 20k-80k); birch_pale, understory_laurel (subcanopy, LOD0 10k-40k). "
        "Three variants each (size, shape, colour).",
        "",
        "Conventions: metres. Blender scene is Z-up. GLB is Y-up (glTF spec). FBX is Blender-native Z-up "
        "(identity axes). Origin at ground centre (min Z = 0, trunk base on XY origin).",
        "",
        "Vertex colour `WindWeight` (COLOR_0 in GLB): R = wind weight, 0 at trunk base to 1 at tips and "
        "leaves (leaves 0.7 to 1.0). G = B = 0, A = 1.",
        "",
        "Material slots: `Bark` (opaque, baked tint + normal map). `Leaves` (alpha-masked, two-sided, "
        "leaf-cluster cards). Alpha mode MASK, cutoff 0.5.",
        "",
        "LOD1 = Decimate collapse, ratio 0.30 of LOD0. LOD2 = Decimate collapse, ratio 0.08 of LOD0. "
        "Each LOD is a separate file, GLB and FBX.",
        "",
        "## Files",
        "",
        "| Variant | Tris LOD0 | Tris LOD1 | Tris LOD2 | W x D x H (m) | Slots |",
        "|---------|-----------|-----------|-----------|---------------|-------|",
    ]
    for r in rows:
        w, d, h = r["dims"]
        lines.append("| %s | %d | %d | %d | %.2f x %.2f x %.2f | Bark, Leaves |" %
                     (r["name"], r["tris0"], r["tris1"], r["tris2"], w, d, h))
    lines += [
        "",
        "Per variant: `<name>.glb`, `<name>.fbx`, `<name>_LOD1.glb/.fbx`, `<name>_LOD2.glb/.fbx`, "
        "`<name>_preview.png` (512 px Cycles render, LOD0), `textures/<name>_bark.png`, "
        "`textures/<name>_leaves.png` (1024 px RGBA).",
        "",
        "birch_pale: bark is a pale ground with dark horizontal lenticel dashes (procedural, hashed grid) "
        "over the Bark013 grain.",
        "",
        "emergent_fig: buttress flare 1.6 (four lobes at the base); crown droops; no vine geometry.",
        "",
        "## Provenance",
        "",
        "- Geometry: procedural, generated by `Tools/Author-Flora-canopy_b.py`. No third-party meshes.",
        "- Bark colour and normal: ambientCG Bark013 (CC0), from `C:\\Misc\\Vivarium\\game\\Textures\\` "
        "(`Bark013_1K-JPG_Color.jpg`, `Bark013_1K-JPG_NormalGL.jpg`). Copied to `textures/`. Colour tinted per "
        "variant into `<name>_bark.png`.",
        "- Leaf colour: Poly Haven island_tree_01 leaves diffuse (CC0), from "
        "`ArtSource/PolyHaven/island_tree_01/textures/island_tree_01_leaves_diff_1k.jpg`. Copied to "
        "`textures/`. Tinted per variant. Alpha is a procedural 16-leaflet cluster mask baked into "
        "`<name>_leaves.png`.",
        "- Poly Haven and ambientCG CC0 status per site licence. Not individually re-verified in this run.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    stage_sources()
    rows = []
    fails = []
    for sp in SPECIES:
        for vi, var in enumerate(sp["variants"]):
            name = "%s_v%02d" % (sp["id"], vi + 1)
            rec = author(sp, var, name)
            rows.append(rec)
            w, d, h = rec["dims"]
            print("VARIANT %s tris0=%d tris1=%d tris2=%d dims=%.2fx%.2fx%.2f bark_tris=%d leaf_tris=%d dens=%.2f" %
                  (name, rec["tris0"], rec["tris1"], rec["tris2"], w, d, h,
                   rec["bark_tris"], rec["leaf_tris"], rec["density"]))
            if not (rec["lo"] <= rec["tris0"] <= rec["hi"]):
                fails.append("%s tris0 %d outside %d-%d" % (name, rec["tris0"], rec["lo"], rec["hi"]))
            if rec["tris1"] <= 0 or rec["tris2"] <= 0:
                fails.append("%s LOD collapsed to zero tris" % name)
    write_readme(rows)
    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d canopy-b variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
