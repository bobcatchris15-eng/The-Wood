"""Author shrub-c flora headless (redo of rejected shrub-a/shrub-b species): willow_shrub,
thorn_scrub, juniper_low, bilberry_low, alder_thicket, sagebrush_grey, prickly_pear. Two variants each.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-shrub_c.py

Metres, Z-up in Blender (glTF/FBX output Y-up), origin at ground centre (min Z = 0).
Why the earlier versions were rejected: single leaf cards from a generic leaf sheet, placed on a
few twig points, left sparse twig frames. Here:
  - Each species gets its own procedurally painted spray atlas (numpy raster, no third-party art):
    a whole leafy twig / frond per sprite (willow wands, thorn twigs, juniper scale fronds,
    bilberry sprigs, alder leaf sprays, sagebrush tufts). One card = one spray.
  - Cards are sampled along ALL twig polylines at fixed spacing (not tips), so interior is filled.
  - Silhouette coverage is MEASURED from a rendered orthographic alpha mask (front + side) as
    mask pixels / convex-hull pixels; card count (then card size) is raised until the minimum of
    the two views reaches COV_TARGET, within the 20k tri budget. Hard gate: COV_MIN (0.60).
  - Prickly pear: modelled flattened obovate pads (4 cm thick) in jointed chains from a woody
    base, painted areole/spine texture, red fruits and yellow flowers as solid-colour parts.
  - Final uniform scale puts every asset at its nominal height (clamp into the catalogue range).
All variation comes from h01(tag, index...), a stateless integer hash. No RNG state.
Per variant: <id>_vNN.glb + .fbx (LOD0), <id>_vNN_LOD1.glb + .fbx, 512 px preview PNG
(LOD0, 3/4 view over a preview-only ground plane, not exported).
Output dir is owned by this script: ArtSource/Authored/Flora/shrub_c/.
Dev filter: env SHRUBC_ONLY=id1,id2 builds only those species and skips the README.
"""

import json
import math
import os
import shutil
import struct
import sys
import tempfile
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SEED = 9533
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
ATLAS = 1024
TRI_MAX = 19500
COV_TARGET = 0.68   # autotune goal (min of front/side)
COV_MIN = 0.60      # hard gate

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "shrub_c")
TEX = os.path.join(OUT, "textures")
SRC = os.path.join(TEX, "src")
PREV = os.path.join(OUT, "previews")

SRC_BARK_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_diff_1k.jpg")
SRC_NOR_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_nor_gl_1k.jpg")
SRC_BARK = os.path.join(SRC, "dead_tree_trunk_diff_1k.jpg")
SRC_NOR = os.path.join(SRC, "dead_tree_trunk_nor_gl_1k.jpg")

# Heights from Docs/FloraCatalog.md (last numeric column = hrange). H = nominal per-variant height (m).
# Skeleton params as in shrub_a/b: nst stems, sp base spread (x H), tlen main length (x H), lean/rise
# initial direction, curve outward bend, grav droop, kids/kang/depth/lat/shrink branching, rad base radius (x H).
# Cards: cards = start count, lf = card height (m), lflat = along-twig vs outward blend, ldroop = hang,
# zmin = no cards below this fraction of H, step = spacing of candidate points along twigs (m).
SHRUBS = [
    dict(id="willow_shrub", tag=21, form="stems", sprite="willow", cells=(2, 2),
         H=(3.2, 4.2), hrange=(2.0, 6.0),
         nst=18, sp=0.12, tlen=(0.70, 0.95), lean=0.22, rise=1.0, curve=0.05, grav=0.04,
         kids=2, kang=(10, 24), depth=2, lat=1, shrink=0.55, rad=0.011,
         cards=6500, lf=0.20, lflat=0.50, ldroop=0.45, zmin=0.10, step=0.05, zfill=0.92,
         tints=[(0.46, 0.56, 0.28), (0.66, 0.72, 0.60)], tint_names=["grey-green", "silver"],
         bark=(0.78, 0.76, 0.66), thorns=0,
         silhouette="arching upright wands densely clothed in narrow drooping leaves"),
    dict(id="thorn_scrub", tag=22, form="stems", sprite="thorn", cells=(4, 2),
         H=(1.5, 2.0), hrange=(1.0, 3.0),
         nst=8, sp=0.20, tlen=(0.65, 0.90), lean=0.60, rise=0.85, curve=0.0, grav=0.0,
         kids=3, kang=(40, 75), depth=2, lat=1, shrink=0.62, rad=0.013,
         cards=3600, lf=0.28, lflat=0.30, ldroop=0.0, zmin=0.04, step=0.05, zfill=0.92,
         tints=[(0.38, 0.46, 0.26), (0.46, 0.46, 0.22)], tint_names=["grey-green", "olive"],
         bark=(0.55, 0.50, 0.46), thorns=110,
         silhouette="dense twiggy thorny tangle with small leaves"),
    dict(id="juniper_low", tag=23, form="stems", sprite="juniper", cells=(2, 2),
         H=(0.80, 1.00), hrange=(0.5, 1.5),
         nst=10, sp=0.22, tlen=(1.4, 1.9), lean=1.0, rise=0.55, curve=0.0, grav=0.0,
         kids=3, kang=(30, 60), depth=2, lat=1, shrink=0.60, rad=0.020,
         cards=2400, lf=0.22, lflat=0.45, ldroop=0.0, zmin=0.0, step=0.06, zfill=0.88,
         tints=[(0.29, 0.38, 0.33), (0.30, 0.38, 0.22)], tint_names=["blue-green", "dull green"],
         bark=(0.70, 0.58, 0.50), thorns=0,
         silhouette="low spreading mat of dense scale-leaf sprays"),
    dict(id="bilberry_low", tag=24, form="stems", sprite="bilberry", cells=(2, 2),
         H=(0.38, 0.50), hrange=(0.3, 0.6),
         nst=14, sp=0.55, tlen=(1.0, 1.4), lean=1.0, rise=0.55, curve=0.0, grav=0.0,
         kids=2, kang=(25, 50), depth=2, lat=1, shrink=0.60, rad=0.012,
         cards=3000, lf=0.15, lflat=0.40, ldroop=0.05, zmin=0.0, step=0.04, zfill=0.90, ztop=0.55, bias="shell",
         tints=[(0.36, 0.54, 0.24), (0.34, 0.52, 0.40)], tint_names=["green", "blue-green"],
         bark=(0.62, 0.40, 0.34), thorns=0,
         silhouette="low wiry mat of small rounded leaves with dark berries"),
    dict(id="alder_thicket", tag=25, form="stems", sprite="alder", cells=(2, 2),
         H=(3.4, 4.4), hrange=(3.0, 6.0),
         nst=8, sp=0.12, tlen=(0.65, 0.85), lean=0.35, rise=1.0, curve=0.05, grav=0.0,
         kids=3, kang=(30, 50), depth=2, lat=1, shrink=0.60, rad=0.016,
         cards=2400, lf=0.42, lflat=0.30, ldroop=0.05, zmin=0.18, step=0.10, zfill=0.92,
         tints=[(0.22, 0.36, 0.17), (0.34, 0.46, 0.28)], tint_names=["dark green", "grey-green"],
         bark=(0.66, 0.62, 0.58), thorns=0,
         silhouette="dense round-headed multi-stem thicket of broad serrated leaves"),
    dict(id="sagebrush_grey", tag=26, form="stems", sprite="sage", cells=(4, 2),
         H=(0.65, 0.85), hrange=(0.5, 1.2),
         nst=11, sp=0.25, tlen=(0.85, 1.15), lean=0.50, rise=1.0, curve=0.0, grav=0.0,
         kids=3, kang=(25, 45), depth=2, lat=1, shrink=0.60, rad=0.010,
         cards=2800, lf=0.22, lflat=0.30, ldroop=0.0, zmin=0.0, step=0.04, zfill=0.90, ztop=0.6,
         tints=[(0.56, 0.60, 0.52), (0.46, 0.53, 0.54)], tint_names=["silver grey", "blue-grey"],
         bark=(0.82, 0.78, 0.70), thorns=0,
         silhouette="silver-grey fine-textured rounded mound"),
    dict(id="prickly_pear", tag=27, form="pads", sprite="pads", cells=(1, 1),
         H=(0.65, 0.85), hrange=(0.5, 1.5),
         roots=3, branch=(1, 2), pdepth=3, A=0.115, B=0.088, C=0.020, shrinkp=0.93,
         cards=0, lf=0.0, zmin=0.0, step=0.1, zfill=1.0,
         tints=[(0.15, 0.46, 0.16), (0.20, 0.44, 0.30)], tint_names=["saturated green", "blue-green, purple-tinged"],
         bark=(0.78, 0.66, 0.54), thorns=0,
         silhouette="jointed flat oval pads in chains from a woody base, spines, yellow flowers, red fruit"),
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


class Rn:
    """Sequential hash stream: Rn(tag...).r() -> [0,1)."""
    def __init__(self, *tag):
        self.tag = tag
        self.k = 0

    def r(self):
        self.k += 1
        return h01(*self.tag, self.k)

    def rr(self, lo, hi):
        return lo + (hi - lo) * self.r()


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def unit(a):
    l = length(a)
    if l < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def perp(d):
    ref = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    a = unit(cross(d, ref))
    b = unit(cross(a, d))
    return a, b


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

    def tris(self):
        return sum(len(f[0]) - 2 for f in self.faces)


Z2 = (0.0, 0.0)


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


# ---------------------------------------------------------------- atlas painting (numpy raster)
# Images are (rgb[h,w,3], a[h,w]) views; row 0 = bottom (Blender v = 0). Colours are sRGB-encoded
# values written straight into a byte PNG.

def comp(rgb, a, ya, yb, xa, xb, cov, col):
    sa = a[ya:yb, xa:xb]
    sc = rgb[ya:yb, xa:xb]
    oa = sa + cov * (1.0 - sa)
    den = np.maximum(oa, 1e-6)[..., None]
    sc[:] = (sc * (sa * (1.0 - cov))[..., None] + col * cov[..., None]) / den
    sa[:] = oa


def _prof(kind, t):
    if kind == "lance":
        return np.sin(np.pi * t ** 0.7) ** 0.85
    if kind == "ovate":
        return np.sin(np.pi * t ** 0.85) ** 0.7
    if kind == "serr":
        base = np.sin(np.pi * t ** 0.85) ** 0.7
        return base * (1.0 + 0.11 * (((t * 11.0) % 1.0) - 0.5) * 2.0)
    if kind == "round":
        return np.sin(np.pi * t) ** 0.55
    if kind == "spike":
        return (1.0 - t) * np.minimum(1.0, t * 10.0 + 0.2)
    return np.sin(np.pi * t)


def leaf(cv, x0, y0, ang, L, W, kind, col, br=1.0, vein=0.16):
    rgb, a = cv
    hh, ww = a.shape
    ca, sa_ = math.cos(ang), math.sin(ang)
    m = 3.0 + 0.5 * W
    lmax = 1e9
    if ca > 1e-3:
        lmax = min(lmax, (ww - m - x0) / ca)
    if ca < -1e-3:
        lmax = min(lmax, (m - x0) / ca)
    if sa_ > 1e-3:
        lmax = min(lmax, (hh - m - y0) / sa_)
    if sa_ < -1e-3:
        lmax = min(lmax, (m - y0) / sa_)
    if lmax < L:
        W *= max(lmax, 0.0) / L
        L = lmax
    if L < 3.0 or W < 0.8:
        return
    pad = W * 0.5 + 2.0
    xa = max(0, int(min(x0, x0 + ca * L) - pad))
    xb = min(ww, int(max(x0, x0 + ca * L) + pad) + 1)
    ya = max(0, int(min(y0, y0 + sa_ * L) - pad))
    yb = min(hh, int(max(y0, y0 + sa_ * L) + pad) + 1)
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.mgrid[ya:yb, xa:xb]
    dx = xx + 0.5 - x0
    dy = yy + 0.5 - y0
    u = dx * ca + dy * sa_
    v = -dx * sa_ + dy * ca
    t = np.clip(u / L, 0.0, 1.0)
    prof = _prof(kind, t) * W * 0.5
    cov = np.clip(prof - np.abs(v) + 0.5, 0.0, 1.0) * ((u >= 0.0) & (u <= L))
    if not cov.any():
        return
    edge = np.abs(v) / np.maximum(prof, 0.5)
    shade = br * (1.0 - 0.22 * np.clip(edge, 0.0, 1.0) ** 2 + 0.10 * (0.5 - t))
    shade = shade + np.exp(-(v / max(1.0, W * 0.045)) ** 2) * vein
    c = np.asarray(col, dtype=np.float32)[None, None, :] * shade[..., None]
    comp(rgb, a, ya, yb, xa, xb, cov.astype(np.float32), np.clip(c, 0.0, 1.0))


def seg(cv, p0, p1, r0, r1, col, br=1.0):
    rgb, a = cv
    hh, ww = a.shape
    x0, y0 = p0
    x1, y1 = p1
    pad = max(r0, r1) + 2.0
    xa = max(0, int(min(x0, x1) - pad))
    xb = min(ww, int(max(x0, x1) + pad) + 1)
    ya = max(0, int(min(y0, y1) - pad))
    yb = min(hh, int(max(y0, y1) + pad) + 1)
    if xb <= xa or yb <= ya:
        return
    yy, xx = np.mgrid[ya:yb, xa:xb]
    px = xx + 0.5 - x0
    py = yy + 0.5 - y0
    dx, dy = x1 - x0, y1 - y0
    l2 = max(dx * dx + dy * dy, 1e-6)
    t = np.clip((px * dx + py * dy) / l2, 0.0, 1.0)
    d = np.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2)
    r = r0 + (r1 - r0) * t
    cov = np.clip(r - d + 0.5, 0.0, 1.0).astype(np.float32)
    if not cov.any():
        return
    c = np.clip(np.asarray(col, dtype=np.float32) * br, 0.0, 1.0)
    comp(rgb, a, ya, yb, xa, xb, cov, c[None, None, :] * np.ones((yb - ya, xb - xa, 1), np.float32))


def jcol(tint, R, amp=0.14):
    f = 1.0 + (R.r() - 0.5) * 2.0 * amp
    hs = (R.r() - 0.5) * 0.10
    return np.array([tint[0] * f * (1.0 + hs), tint[1] * f, tint[2] * f * (1.0 - hs)], np.float32)


def spr_willow(cv, tint, R):
    """Short drooping sprig: slender curved wand, narrow lance leaves alternate, hanging."""
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    stem = (0.42, 0.38, 0.22)
    bend = R.rr(-60, 60)

    def wp(t):
        return (cx - 30 + bend * math.sin(t * 2.4) + 60 * t, 6 + t * (h - 24))

    ts = np.linspace(0, 1, 14)
    for t0, t1 in zip(ts[:-1], ts[1:]):
        seg(cv, wp(t0), wp(t1), 3.2, 2.4, stem)
    n = 11
    for k in range(n):
        t = (k + 0.7) / n
        x, y = wp(t)
        side = 1 if k % 2 == 0 else -1
        ang = math.pi / 2 - side * math.radians(R.rr(40, 68))
        L = (235 - 70 * t) * R.rr(0.88, 1.12)
        leaf(cv, x, y, ang, L, L * 0.125, "lance", jcol(tint, R), br=R.rr(0.9, 1.1), vein=0.2)
    x, y = wp(1.0)
    leaf(cv, x, y, math.pi / 2 - 0.25, 170, 21, "lance", jcol(tint, R), vein=0.2)


def spr_thorn(cv, tint, R):
    """Zigzag twig, paired cream-grey thorns at every node, small leaf fascicles."""
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    n = 7
    nodes = []
    for i in range(n + 1):
        y = 6 + i * (h - 60) / n
        x = cx + (18 if i % 2 else -18) * R.rr(0.6, 1.3)
        nodes.append((x, y))
    twig = (0.50, 0.44, 0.36)
    thorn = (0.80, 0.76, 0.64)
    for p, q in zip(nodes[:-1], nodes[1:]):
        seg(cv, p, q, 4.6, 3.4, twig)
    for i in range(1, len(nodes)):
        x, y = nodes[i]
        px, py = nodes[i - 1]
        for side in (1, -1):
            ang = math.pi / 2 - side * math.radians(R.rr(50, 80))
            Lt = R.rr(52, 78)
            ex, ey = x + math.cos(ang) * Lt, y + math.sin(ang) * Lt
            hook = math.radians(R.rr(-25, 25))
            mx, my = x + math.cos(ang) * Lt * 0.55, y + math.sin(ang) * Lt * 0.55
            seg(cv, (x, y), (mx, my), 4.6, 2.6, thorn)
            seg(cv, (mx, my), (mx + math.cos(ang + hook) * Lt * 0.5, my + math.sin(ang + hook) * Lt * 0.5), 2.6, 0.4, thorn)
        for (cx_, cy_), nl in (((x, y), 4), (((x + px) * 0.5, (y + py) * 0.5), 3)):
            for j in range(nl):
                ang = math.radians(R.rr(15, 165))
                L = R.rr(30, 46)
                leaf(cv, cx_, cy_, ang, L, L * R.rr(0.5, 0.66), "round", jcol(tint, R), br=R.rr(0.9, 1.1))
    x, y = nodes[-1]
    for j in range(5):
        ang = math.radians(R.rr(40, 140))
        L = R.rr(36, 52)
        leaf(cv, x, y, ang, L, L * 0.55, "round", jcol(tint, R))


def spr_juniper(cv, tint, R):
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    axis = [(cx + 14 * math.sin(i * 0.7 + R.rr(0, 2)), 8 + i * (h - 24) / 12) for i in range(13)]
    wood = (0.34, 0.27, 0.22)
    for p, q in zip(axis[:-1], axis[1:]):
        seg(cv, p, q, 5, 3.8, wood)

    def branchlet(x, y, ang, Lb, rl, dens):
        dxu, dyu = math.cos(ang), math.sin(ang)
        seg(cv, (x, y), (x + dxu * Lb, y + dyu * Lb), 3.4, 1.6, wood)
        steps = max(3, int(Lb / dens))
        for s in range(steps):
            f = (s + 0.5) / steps
            px, py = x + dxu * Lb * f, y + dyu * Lb * f
            for side in (1, -1):
                la = ang + side * math.radians(R.rr(28, 52))
                L = rl * R.rr(0.8, 1.2) * (1.0 - 0.3 * f)
                leaf(cv, px, py, la, L, L * 0.42, "lance", jcol(tint, R, 0.16) * (1.0 + 0.18 * f),
                     br=R.rr(0.85, 1.1), vein=0.12)
        leaf(cv, x + dxu * Lb * 0.9, y + dyu * Lb * 0.9, ang, rl * 1.2, rl * 0.5, "lance",
             jcol(tint, R) * 1.15, vein=0.12)

    nb = 17
    for i in range(nb):
        t = (i + 0.5) / nb
        ax, ay = axis[min(11, int(t * 12))]
        side = 1 if i % 2 == 0 else -1
        ang = math.pi / 2 - side * math.radians(R.rr(46, 60))
        Lb = (215 - 120 * t) * R.rr(0.9, 1.1)
        branchlet(ax, ay, ang, Lb, 34, 6.5)
        for f in (0.35, 0.65):
            sx, sy = ax + math.cos(ang) * Lb * f, ay + math.sin(ang) * Lb * f
            for s2 in (1, -1):
                ang2 = ang + s2 * math.radians(R.rr(40, 60))
                branchlet(sx, sy, ang2, Lb * 0.34, 28, 6.5)
    branchlet(axis[-2][0], axis[-2][1], math.pi / 2, 70, 30, 6.5)


def spr_bilberry(cv, tint, R):
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    stem = (0.45, 0.30, 0.22)
    pts = [(cx - 40 + 70 * (i / 10.0) + 12 * math.sin(i * 0.9), 8 + i * (h - 60) / 10) for i in range(11)]
    for p, q in zip(pts[:-1], pts[1:]):
        seg(cv, p, q, 3.2, 2.4, stem)
    berries = R.r() < 0.85

    def sprig(p, ang, Lb, nl, Lleaf):
        x, y = p
        dxu, dyu = math.cos(ang), math.sin(ang)
        seg(cv, (x, y), (x + dxu * Lb, y + dyu * Lb), 2.6, 1.6, stem)
        for k in range(nl):
            f = (k + 0.6) / nl
            px, py = x + dxu * Lb * f, y + dyu * Lb * f
            side = 1 if k % 2 == 0 else -1
            la = ang + side * math.radians(R.rr(42, 66))
            L = Lleaf * R.rr(0.85, 1.15)
            leaf(cv, px, py, la, L, L * R.rr(0.62, 0.74), "round", jcol(tint, R), br=R.rr(0.9, 1.1), vein=0.18)
        leaf(cv, x + dxu * Lb, y + dyu * Lb, ang, Lleaf * 0.9, Lleaf * 0.6, "round", jcol(tint, R))
        if berries and R.r() < 0.9:
            bx, by = x + dxu * Lb * 0.5, y + dyu * Lb * 0.5 - 14
            seg(cv, (x + dxu * Lb * 0.5, y + dyu * Lb * 0.5), (bx, by), 1.2, 1.0, stem)
            seg(cv, (bx, by), (bx, by - 2), 17, 17, (0.13, 0.12, 0.30))
            seg(cv, (bx - 5, by + 5), (bx - 5, by + 5), 4.0, 4.0, (0.45, 0.47, 0.68))

    for k in range(10):
        f = (k + 0.5) / 10
        i = int(f * 10)
        p = pts[i]
        side = 1 if k % 2 == 0 else -1
        la = math.pi / 2 - side * math.radians(R.rr(40, 62))
        L = 105 * R.rr(0.85, 1.1) * (1.0 - 0.3 * f)
        leaf(cv, p[0], p[1], la, L, L * 0.68, "round", jcol(tint, R), br=R.rr(0.9, 1.1), vein=0.18)
    for f, side in ((0.25, 1), (0.45, -1), (0.65, 1), (0.8, -1)):
        p = pts[int(f * 10)]
        sprig(p, math.pi / 2 - side * math.radians(R.rr(40, 60)), 150 * (1.1 - f), 5, 88)
    sprig(pts[-1], math.pi / 2, 50, 3, 88)


def spr_alder(cv, tint, R):
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    stem = (0.36, 0.30, 0.22)
    pts = [(cx + 16 * math.sin(i * 0.8 + R.rr(0, 1)), 6 + i * (h - 40) / 8) for i in range(9)]
    for p, q in zip(pts[:-1], pts[1:]):
        seg(cv, p, q, 4.4, 3.2, stem)
    n = 6

    def one_leaf(x, y, ang, L):
        col = jcol(tint, R)
        leaf(cv, x, y, ang, L, L * R.rr(0.68, 0.78), "serr", col, br=R.rr(0.9, 1.08), vein=0.2)
        ca, sa_ = math.cos(ang), math.sin(ang)
        lt = np.clip(col * 1.35, 0, 1)
        for kv in range(5):
            f = 0.18 + kv * 0.14
            ox, oy = x + ca * L * f, y + sa_ * L * f
            for sd in (1, -1):
                va = ang + sd * math.radians(58)
                Lv = L * 0.30 * (1.0 - 0.4 * f)
                seg(cv, (ox, oy), (ox + math.cos(va) * Lv, oy + math.sin(va) * Lv), 1.1, 0.5, lt, 0.8)

    for k in range(n):
        t = (k + 0.5) / n
        p = pts[int(t * 8)]
        side = 1 if k % 2 == 0 else -1
        ang = math.pi / 2 - side * math.radians(R.rr(38, 58))
        L = (200 - 40 * t) * R.rr(0.88, 1.08)
        one_leaf(p[0], p[1], ang, L)
    one_leaf(pts[-1][0], pts[-1][1], math.pi / 2, 170)


def spr_sage(cv, tint, R):
    _, a = cv
    h, w = a.shape
    cx = w * 0.5
    stem = (0.55, 0.52, 0.45)
    pts = [(cx + 8 * math.sin(i * 0.6 + R.rr(0, 1)), 4 + i * (h - 70) / 10) for i in range(11)]
    for p, q in zip(pts[:-1], pts[1:]):
        seg(cv, p, q, 2.6, 2.0, stem)

    def tuft(x, y, ang, L0, n):
        for k in range(n):
            t = k / max(1, n - 1)
            side = 1 if k % 2 == 0 else -1
            la = ang - side * math.radians(R.rr(20, 58))
            L = L0 * (1.0 - 0.35 * t) * R.rr(0.8, 1.15)
            leaf(cv, x, y, la, L, L * R.rr(0.16, 0.24), "lance", jcol(tint, R, 0.12), br=R.rr(0.9, 1.1), vein=0.1)

    for i in range(1, 11):
        x, y = pts[i]
        tuft(x, y, math.pi / 2, 95 - 5 * i, 3)
        if i > 1:
            px, py = pts[i - 1]
            tuft((x + px) * 0.5, (y + py) * 0.5, math.pi / 2, 90 - 5 * i, 2)
    for f, side in ((0.25, 1), (0.40, -1), (0.55, 1), (0.7, -1)):
        x, y = pts[int(f * 10)]
        ang = math.pi / 2 - side * math.radians(R.rr(32, 50))
        dxu, dyu = math.cos(ang), math.sin(ang)
        Lb = 190 * (1.0 - 0.7 * f) + 40
        seg(cv, (x, y), (x + dxu * Lb, y + dyu * Lb), 2.0, 1.2, stem)
        for k in range(1, 7):
            ff = k / 7.0
            tuft(x + dxu * Lb * ff, y + dyu * Lb * ff, ang, 66 * (1.0 - 0.4 * ff), 3)
    tuft(pts[-1][0], pts[-1][1], math.pi / 2, 80, 5)


SPRITES = {"willow": spr_willow, "thorn": spr_thorn, "juniper": spr_juniper,
           "bilberry": spr_bilberry, "alder": spr_alder, "sage": spr_sage}


def write_png(arr, path, name):
    size_y, size_x = arr.shape[0], arr.shape[1]
    img = bpy.data.images.new(name, size_x, size_y, alpha=True)
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


def square_pixels(img, size):
    if tuple(img.size) != (size, size):
        img.scale(size, size)
    buf = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(size, size, 4).copy()


def build_atlas(c, var):
    cols, rows = c["cells"]
    rgb = np.zeros((ATLAS, ATLAS, 3), np.float32)
    a = np.zeros((ATLAS, ATLAS), np.float32)
    cw, ch = ATLAS // cols, ATLAS // rows
    fn = SPRITES[c["sprite"]]
    cells = []
    for j in range(rows):
        for i in range(cols):
            y0, x0 = j * ch, i * cw
            cv = (rgb[y0:y0 + ch, x0:x0 + cw], a[y0:y0 + ch, x0:x0 + cw])
            fn(cv, c["tints"][var], Rn(c["tag"], var, j * cols + i))
            cells.append((x0 / float(ATLAS), (x0 + cw) / float(ATLAS), y0 / float(ATLAS), (y0 + ch) / float(ATLAS)))
    m = a > 0.5
    mean_col = rgb[m].mean(axis=0)
    rgb[a < 0.02] = mean_col[None, :]
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    mean_lum = float(lum[m].mean())
    out = np.empty((ATLAS, ATLAS, 4), np.float32)
    out[..., :3] = np.clip(rgb, 0.0, 1.0)
    out[..., 3] = np.clip(a * 1.0, 0.0, 1.0)
    # near-binary alpha keeps cutout edges crisp in MASK mode
    out[..., 3] = np.clip((out[..., 3] - 0.15) / 0.7, 0.0, 1.0)
    path = os.path.join(TEX, "%s_v%02d_leaves.png" % (c["id"], var + 1))
    write_png(out, path, "leaves_%s_%d" % (c["id"], var + 1))
    return load_img(path), mean_lum, cells, cw / float(ch)


def bark_tex(c, var, size=1024):
    px = square_pixels(load_img(SRC_BARK), size)
    tint = np.array(c["bark"], dtype=np.float32)
    px[..., :3] = np.clip(px[..., :3] * tint[None, None, :] * 2.2, 0.0, 1.0)  # source bark is very dark; gain lifts it
    path = os.path.join(TEX, "%s_v%02d_bark.png" % (c["id"], var + 1))
    write_png(px, path, "bark_%s_%d" % (c["id"], var + 1))
    return load_img(path)


def pad_tex(c, var, size=512):
    """Opuntia pad: saturated green, soft blotches, diamond lattice of areoles with cream spines."""
    R = Rn(c["tag"], var, 77)
    base = np.array(c["tints"][var], np.float32)
    rgb = np.ones((size, size, 3), np.float32) * base[None, None, :]
    a = np.ones((size, size), np.float32)
    # smooth blotches
    coarse = np.array([[R.r() for _ in range(12)] for _ in range(12)], np.float32)
    big = np.kron(coarse, np.ones((size // 12 + 1, size // 12 + 1), np.float32))[:size, :size]
    k = 15
    ker = np.ones(k, np.float32) / k
    big = np.apply_along_axis(lambda r: np.convolve(r, ker, mode="same"), 1, big)
    big = np.apply_along_axis(lambda r: np.convolve(r, ker, mode="same"), 0, big)
    rgb *= (0.82 + 0.36 * big)[..., None]
    if var == 1:
        yy, xx = np.mgrid[0:size, 0:size]
        pur = np.clip((xx / float(size) - 0.45) * 1.6, 0.0, 1.0) * 0.40
        pcol = np.array([0.46, 0.24, 0.34], np.float32)
        rgb = rgb * (1.0 - pur[..., None]) + pcol[None, None, :] * pur[..., None]
    cv = (rgb, a)
    cream = (0.92, 0.86, 0.62)
    nx, ny = 8, 7
    for j in range(ny):
        for i in range(nx):
            u = (i + 0.5 + 0.5 * (j % 2)) / (nx + 0.5)
            v = (j + 0.5) / ny
            x = (0.08 + 0.84 * u) * size + R.rr(-6, 6)
            y = (0.08 + 0.84 * v) * size + R.rr(-6, 6)
            seg(cv, (x, y), (x, y), 6.5, 6.5, (0.30, 0.22, 0.12))
            for s in range(7):
                ang = TAU * (s + R.rr(-0.2, 0.2)) / 7
                Ls = R.rr(18, 32)
                seg(cv, (x, y), (x + math.cos(ang) * Ls, y + math.sin(ang) * Ls), 1.6, 0.4, cream)
    out = np.ones((size, size, 4), np.float32)
    out[..., :3] = np.clip(rgb, 0.0, 1.0)
    path = os.path.join(TEX, "%s_v%02d_pad.png" % (c["id"], var + 1))
    write_png(out, path, "pad_%s_%d" % (c["id"], var + 1))
    return load_img(path)


# ---------------------------------------------------------------- skeletons / cards (stems form)

class Gen:
    def __init__(self, c, var, salt=0):
        self.c = c
        self.H = c["H"][var]
        self.tag = c["tag"] * 1000 + var * 100 + salt * 10
        self.k = 0

    def r(self):
        self.k += 1
        return h01(self.tag, self.k)

    def rr(self, lo, hi):
        return lo + (hi - lo) * self.r()

    def jit(self, amp):
        return (self.rr(-1.0, 1.0) * amp, self.rr(-1.0, 1.0) * amp, self.rr(-1.0, 1.0) * amp)


def spawn(g, p, dv, L, r, depth, sk, n):
    c = g.c
    lo, hi = c["kang"]
    u, v = perp(dv)
    for _ in range(n):
        ang = math.radians(g.rr(lo, hi))
        phi = TAU * g.r()
        side = add(mul(u, math.cos(phi)), mul(v, math.sin(phi)))
        cd = unit(add(mul(dv, math.cos(ang)), mul(side, math.sin(ang))))
        cL = L * c["shrink"] * g.rr(0.85, 1.15)
        grow(g, p, cd, cL, max(r * 0.66, 0.0015), depth + 1, sk)


def grow(g, p, d, L, r, depth, sk):
    c = g.c
    nseg = 4 if depth == 0 else 3
    pts = [p]
    rads = [r]
    cur = p
    dv = d
    dt = L / nseg
    for i in range(nseg):
        ho = (cur[0], cur[1], 0.0)
        out = unit(ho) if length(ho) > 1e-6 else (0.0, 0.0, 0.0)
        dv = unit(add(add(dv, mul(out, c["curve"])), add((0.0, 0.0, -c["grav"]), mul(g.jit(1.0), 0.10))))
        cur = add(cur, mul(dv, dt))
        # keep twigs above ground
        cur = (cur[0], cur[1], max(cur[2], 0.0))
        pts.append(cur)
        rads.append(r * (1.0 - 0.3 * (i + 1) / nseg))
    sk["segs"].append((pts, rads, depth))
    if depth >= c["depth"]:
        return
    if c["lat"] and depth == 0:
        md = unit(sub(pts[2], pts[1]))
        spawn(g, pts[2], md, L * 0.6, rads[2], depth, sk, c["lat"])
    spawn(g, cur, dv, L, r, depth, sk, c["kids"])


def build_skeleton(c, var, zf=None):
    zf = c["zfill"] if zf is None else zf
    g = Gen(c, var)
    sk = {"segs": []}
    H = g.H
    for i in range(c["nst"]):
        a = TAU * (i + g.rr(-0.3, 0.3)) / c["nst"]
        rb = c["sp"] * H * math.sqrt(g.r())
        base = (math.cos(a) * rb, math.sin(a) * rb, 0.0)
        out = unit((base[0], base[1], 0.0))
        d = unit(add(mul(out, c["lean"] * g.rr(0.8, 1.2)), (0.0, 0.0, c["rise"])))
        L = H * g.rr(c["tlen"][0], c["tlen"][1])
        grow(g, base, d, L, c["rad"] * H, 0, sk)
    zmax = max(p[2] for pts, _, _ in sk["segs"] for p in pts)
    k = H * zf / max(zmax, 1e-6)
    segs = []
    for pts, rads, depth in sk["segs"]:
        segs.append(([mul(p, k) for p in pts], [r * k for r in rads], depth))
    sk["segs"] = segs
    sk["k"] = k
    sk["zf"] = zf
    return g, sk


def sample_points(sk, step):
    out = []
    for pts, _rads, depth in sk["segs"]:
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            d = sub(q, p)
            L = length(d)
            if L < 1e-6:
                continue
            t = unit(d)
            n = max(1, int(round(L / step)))
            for j in range(n):
                f = (j + 0.5) / n
                out.append((add(p, mul(d, f)), t, depth))
    return out


def make_cards(c, var, cands, n, lf, cells, aspect):
    g = Gen(c, var, salt=7)
    H = g.H
    zmin = c["zmin"] * H
    use = [x for x in cands if x[0][2] >= zmin] or cands
    zb = c.get("ztop", 1.0)
    if zb != 1.0:
        if c.get("bias") == "shell":
            zc = 0.35 * H
            use = sorted(use, key=lambda x: x[0][0] ** 2 + x[0][1] ** 2 + (x[0][2] - zc) ** 2)
        else:
            use = sorted(use, key=lambda x: x[0][2])
    cards = []
    for _ in range(n):
        pos, t, _dep = use[min(len(use) - 1, int((g.r() ** zb) * len(use)))]
        o = (pos[0], pos[1], 0.0)
        o = unit(o) if length(o) > 1e-6 else (0.0, 0.0, 1.0)
        radial = unit(add(o, (0.0, 0.0, 0.4)))
        ld = unit(add(mul(t, c["lflat"]), mul(radial, 1.0 - c["lflat"])))
        ld = unit(add(add(ld, mul(g.jit(1.0), 0.32)), (0.0, 0.0, -c["ldroop"])))
        cell = cells[min(len(cells) - 1, int(g.r() * len(cells)))]
        h = lf * g.rr(0.8, 1.2)
        w = h * aspect
        phi = TAU * g.r()
        cards.append((sub(pos, mul(ld, 0.06 * h)), ld, h, w, cell, phi))
    return cards


def leaf_quad(part, card):
    pos, ld, h, w, cell, phi = card
    a0, b0 = perp(ld)
    a = add(mul(a0, math.cos(phi)), mul(b0, math.sin(phi)))
    half = mul(a, w * 0.5)
    tip = add(pos, mul(ld, h))
    pts = (sub(pos, half), add(pos, half), add(tip, half), sub(tip, half))
    u0, u1, v0, v1 = cell
    i = [part.v(p) for p in pts]
    part.quad(i[0], i[1], i[2], i[3], ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))


def thorn_parts(c, var, cands, n, lod):
    """Hooked thorns: curved 3-sided tubes on thin twigs. Returns list of (pts, rads)."""
    if not n:
        return []
    g = Gen(c, var, salt=5)
    H = g.H
    use = [x for x in cands if x[2] >= 1]
    out = []
    cnt = n if lod == 0 else n // 3
    for _ in range(cnt):
        pos, t, _d = use[min(len(use) - 1, int(g.r() * len(use)))]
        a, b = perp(t)
        phi = TAU * g.r()
        side = unit(add(mul(a, math.cos(phi)), mul(b, math.sin(phi))))
        d0 = unit(add(mul(side, 0.8), mul(t, 0.4)))
        Lt = 0.045 * H * g.rr(0.8, 1.3)
        p1 = add(pos, mul(d0, Lt * 0.6))
        d1 = unit(add(d0, mul(t, 0.9)))
        p2 = add(p1, mul(d1, Lt * 0.5))
        out.append(([pos, p1, p2], [0.0035 * H * 0.5 + 0.0015, 0.0010, 0.0002]))
    return out


# ---------------------------------------------------------------- prickly pear

def horiz_normal(L, twist):
    n0 = cross(L, (0.0, 0.0, 1.0))
    if length(n0) < 1e-4:
        n0 = (1.0, 0.0, 0.0)
    n0 = unit(n0)
    n1 = cross(L, n0)
    return unit(add(mul(n0, math.cos(twist)), mul(n1, math.sin(twist))))


def pad_point(P, rho, th, side):
    A, B, C = P["A"], P["B"], P["C"]
    x = A * rho * math.cos(th)
    y = B * rho * math.sin(th) * (1.0 + 0.22 * rho * math.cos(th))
    z = side * C * math.sqrt(max(0.0, 1.0 - rho ** 4))
    p = add(P["cen"], add(add(mul(P["L"], x), mul(P["W"], y)), mul(P["N"], z)))
    u = 0.5 + x / (2.0 * A * 1.05)
    v = 0.5 + y / (2.0 * B * 1.30)
    return p, (u, v)


def pad_mesh(part, P, nu, rhos):
    top0, uv0 = pad_point(P, 0.0, 0.0, 1.0)
    bot0, _ = pad_point(P, 0.0, 0.0, -1.0)
    ic_t = part.v(top0)
    ic_b = part.v(bot0)
    nr = len(rhos)  # rhos[0] = 0 ignored, last = 1.0 (rim)
    top = []
    bot = []
    for k in range(1, nr - 1):
        tr, br_, tu, bu = [], [], [], []
        for j in range(nu):
            th = TAU * j / nu
            p, uv = pad_point(P, rhos[k], th, 1.0)
            tr.append(part.v(p))
            tu.append(uv)
            p, uv = pad_point(P, rhos[k], th, -1.0)
            br_.append(part.v(p))
            bu.append(uv)
        top.append((tr, tu))
        bot.append((br_, bu))
    rim = []
    rim_uv = []
    for j in range(nu):
        th = TAU * j / nu
        p, uv = pad_point(P, 1.0, th, 1.0)
        rim.append(part.v(p))
        rim_uv.append(uv)
    c_uv = (0.5, 0.5)
    for j in range(nu):
        j2 = (j + 1) % nu
        part.tri(ic_t, top[0][0][j], top[0][0][j2], (c_uv, top[0][1][j], top[0][1][j2]))
        part.tri(ic_b, bot[0][0][j2], bot[0][0][j], (c_uv, bot[0][1][j2], bot[0][1][j]))
    for k in range(len(top) - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            part.quad(top[k][0][j], top[k][0][j2], top[k + 1][0][j2], top[k + 1][0][j],
                      (top[k][1][j], top[k][1][j2], top[k + 1][1][j2], top[k + 1][1][j]))
            part.quad(bot[k][0][j2], bot[k][0][j], bot[k + 1][0][j], bot[k + 1][0][j2],
                      (bot[k][1][j2], bot[k][1][j], bot[k + 1][1][j], bot[k + 1][1][j2]))
    for j in range(nu):
        j2 = (j + 1) % nu
        part.quad(top[-1][0][j], top[-1][0][j2], rim[j2], rim[j],
                  (top[-1][1][j], top[-1][1][j2], rim_uv[j2], rim_uv[j]))
        part.quad(bot[-1][0][j2], bot[-1][0][j], rim[j], rim[j2],
                  (bot[-1][1][j2], bot[-1][1][j], rim_uv[j], rim_uv[j2]))


def ellipsoid(part, cen, axis, a, b, nu, nv):
    u, v = perp(axis)
    top = part.v(add(cen, mul(axis, a)))
    bot = part.v(sub(cen, mul(axis, a)))
    rings = []
    for i in range(1, nv):
        ph = math.pi * i / nv
        ring = []
        for j in range(nu):
            th = TAU * j / nu
            off = add(mul(u, b * math.sin(ph) * math.cos(th)), mul(v, b * math.sin(ph) * math.sin(th)))
            ring.append(part.v(add(cen, add(mul(axis, a * math.cos(ph)), off))))
        rings.append(ring)
    for j in range(nu):
        j2 = (j + 1) % nu
        part.tri(top, rings[0][j], rings[0][j2], (Z2, Z2, Z2))
        part.tri(bot, rings[-1][j2], rings[-1][j], (Z2, Z2, Z2))
    for i in range(len(rings) - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            part.quad(rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j], (Z2, Z2, Z2, Z2))


def flower_mesh(part, cen, axis, rad=0.032, hgt=0.028, npet=7):
    u, v = perp(axis)
    for k in range(npet):
        th = TAU * k / npet
        d = add(mul(u, math.cos(th)), mul(v, math.sin(th)))
        t = add(mul(u, -math.sin(th)), mul(v, math.cos(th)))
        base = add(cen, mul(d, 0.004))
        tip = add(add(cen, mul(d, rad)), mul(axis, hgt))
        wb = rad * 0.28
        wt = rad * 0.42
        i0 = part.v(sub(base, mul(t, wb * 0.5)))
        i1 = part.v(add(base, mul(t, wb * 0.5)))
        i2 = part.v(add(tip, mul(t, wt * 0.5)))
        i3 = part.v(sub(tip, mul(t, wt * 0.5)))
        part.quad(i0, i1, i2, i3, (Z2, Z2, Z2, Z2))
    ellipsoid(part, add(cen, mul(axis, 0.006)), axis, 0.008, 0.007, 6, 3)


def build_pp(c, var):
    g = Gen(c, var)
    A, B, C = c["A"], c["B"], c["C"]
    sk = {"pads": [], "woody": [], "fruit": [], "flower": []}

    def grow_pad(cen, L, N, A_, B_, C_, depth):
        W = unit(cross(N, L))
        P = dict(cen=cen, L=L, W=W, N=N, A=A_, B=B_, C=C_, depth=depth)
        sk["pads"].append(P)
        if depth >= 2:
            u = g.r()
            th = g.rr(0.7, 1.2) * (1 if g.r() < 0.5 else -1)
            rim, _ = pad_point(P, 1.0, th, 1.0)
            od = unit(sub(rim, cen))
            if u < 0.40:
                fa = unit(add(od, (0.0, 0.0, 0.7)))
                sk["fruit"].append((add(rim, mul(fa, 0.012)), fa))
            elif u < 0.55:
                sk["flower"].append((add(rim, (0.0, 0.0, 0.004)), unit(add(od, (0.0, 0.0, 1.6)))))
        if depth >= c["pdepth"]:
            return
        nkid = int(g.rr(c["branch"][0], c["branch"][1] + 0.999))
        for k in range(nkid):
            th = (k - (nkid - 1) / 2.0) * 0.95 + g.rr(-0.3, 0.3)
            rim, _ = pad_point(P, 1.0, th, 1.0)
            od = unit(sub(rim, cen))
            Ld = unit(add(od, (0.0, 0.0, 0.4)))
            s = g.rr(c["shrinkp"] - 0.05, c["shrinkp"] + 0.04)
            Ac, Bc = A_ * s, B_ * s
            Nc = horiz_normal(Ld, g.rr(-1.0, 1.0))
            ccen = add(rim, mul(Ld, Ac * 0.82))
            grow_pad(ccen, Ld, Nc, Ac, Bc, C_, depth + 1)

    for r in range(c["roots"]):
        a = TAU * (r + g.rr(-0.2, 0.2)) / c["roots"]
        ca, sa = math.cos(a), math.sin(a)
        b0 = (ca * 0.02, sa * 0.02, 0.0)
        b1 = (ca * 0.045, sa * 0.045, 0.07)
        b2 = (ca * 0.075, sa * 0.075, 0.125)
        sk["woody"].append(([b0, b1, b2], [0.034, 0.027, 0.021]))
        L = unit((ca * g.rr(0.55, 0.9), sa * g.rr(0.55, 0.9), 1.0))
        N = horiz_normal(L, g.rr(-0.6, 0.6))
        grow_pad(add(b2, mul(L, A * 0.8)), L, N, A, B, C, 0)
    return g, sk


def build_parts_pp(c, sk, lod):
    bark = Part("woody", "Bark")
    pads = Part("pads", "Pads")
    fruit = Part("fruit", "Fruit")
    flow = Part("flowers", "Flower")
    for pts, rads in sk["woody"]:
        tube(bark, pts, rads, 6 if lod == 0 else 4)
    if lod == 0:
        nu, rhos = 16, [0.0, 0.45, 0.75, 0.92, 0.985, 1.0]
    else:
        nu, rhos = 8, [0.0, 0.7, 0.95, 1.0]
    for P in sk["pads"]:
        pad_mesh(pads, P, nu, rhos)
    for cen, ax in sk["fruit"]:
        ellipsoid(fruit, cen, ax, 0.034, 0.021, 8 if lod == 0 else 5, 5 if lod == 0 else 3)
    for cen, ax in sk["flower"]:
        if lod == 0:
            flower_mesh(flow, cen, ax)
        else:
            flower_mesh(flow, cen, ax, npet=4)
    return [p for p in (bark, pads, fruit, flow) if p.faces]


# ---------------------------------------------------------------- parts / materials / object

def build_parts(c, sk, cards, thorns, lod):
    stems_p = Part("stems", "Bark")
    leaf_p = Part("leaves", "Leaves")
    for pts, rads, depth in sk["segs"]:
        sides = max(3, [6, 5, 4, 3][min(depth, 3)] - (1 if lod else 0))
        if lod == 1:
            idx = list(range(0, len(pts), 3))
            if idx[-1] != len(pts) - 1:
                idx.append(len(pts) - 1)
            pts = [pts[i] for i in idx]
            rads = [rads[i] for i in idx]
        tube(stems_p, pts, rads, sides, v_scale=2.0)
    for pts, rads in thorns:
        tube(stems_p, pts, rads, 3)
    for i, card in enumerate(cards):
        if lod == 0 or i % 10 < 3:
            leaf_quad(leaf_p, card)
    return [p for p in (stems_p, leaf_p) if p.faces]


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
        # Math:Round on alpha -> glTF exporter writes alphaMode MASK (cutoff 0.5)
        rnd = nt.nodes.new("ShaderNodeMath")
        rnd.operation = "ROUND"
        nt.links.new(tex.outputs["Alpha"], rnd.inputs[0])
        nt.links.new(rnd.outputs["Value"], bsdf.inputs["Alpha"])
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


def make_solid_material(name, rgb, rough=0.5, two_sided=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
            n.inputs["Roughness"].default_value = rough
    m.use_backface_culling = not two_sided
    return m


def make_mats(c, var):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    nor = load_img(SRC_NOR, noncolor=True)
    mats = {"Bark": make_material("Bark", bark_tex(c, var), nor)}
    info = {}
    if c["form"] == "stems":
        leaf_img, mean_lum, cells, aspect = build_atlas(c, var)
        mats["Leaves"] = make_material("Leaves", leaf_img, masked=True, two_sided=True)
        info = dict(lum=mean_lum, cells=cells, aspect=aspect)
    else:
        mats["Pads"] = make_material("Pads", pad_tex(c, var), rough=0.45)
        mats["Fruit"] = make_solid_material("Fruit", (0.50, 0.05, 0.10), rough=0.4)
        mats["Flower"] = make_solid_material("Flower", (0.92, 0.72, 0.06), rough=0.6, two_sided=True)
    return mats, info


def clear_objects():
    for ob in list(bpy.data.objects):
        if ob.type == "MESH":
            bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def drop_object(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)


def make_object(name, parts, mats, wind, target_h):
    """Combine parts into one mesh; shift min z to 0 and scale uniformly to height target_h."""
    allz = min(p[2] for part in parts for p in part.verts)
    topz = max(p[2] for part in parts for p in part.verts)
    s = target_h / max(topz - allz, 1e-6)
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
            vv = (x * s, y * s, (z - allz) * s)
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

    # Wind weight: R = (z / height)^1.2, 0 at base, 1 at tips. Cactus: R = 0 everywhere (rigid).
    dh = max(hi[2] - lo[2], 1e-6)
    attr = me.color_attributes.new(name="WindWeight", type="FLOAT_COLOR", domain="POINT")
    flat = []
    for vtx in me.vertices:
        w = (min(1.0, max(0.0, (vtx.co.z - lo[2]) / dh)) ** 1.2) if wind else 0.0
        flat.extend((w, 0.0, 0.0, 1.0))
    attr.data.foreach_set("color", flat)

    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    dims = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    return ob, {"tris": tris, "dims": dims, "slots": slots, "scale": s, "lo": lo, "hi": hi}


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
    nprim = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs.update(prim.get("attributes", {}).keys())
            nprim += 1
    mats = [(m.get("name"), m.get("alphaMode", "OPAQUE"), m.get("doubleSided", False))
            for m in doc.get("materials", [])]
    return attrs, mats, len(doc.get("meshes", []))


# ---------------------------------------------------------------- scene / render / coverage

def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.cycles.transparent_max_bounces = 256  # dense stacks of alpha cards: default 8 turns deep rays black
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

    cdata = bpy.data.cameras.new("CovCam")
    cdata.type = "ORTHO"
    ccam = bpy.data.objects.new("CovCam", cdata)
    sc.collection.objects.link(ccam)

    sun_data = bpy.data.lights.new("PrevSun", "SUN")
    sun_data.energy = 4.0
    sun = bpy.data.objects.new("PrevSun", sun_data)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (0.8, 0.2, 0.6)

    world = bpy.data.worlds.new("PrevWorld")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.60, 0.62, 1.0)
    bg.inputs["Strength"].default_value = 1.9
    bg2 = nt.nodes.new("ShaderNodeBackground")
    bg2.inputs["Color"].default_value = (0.55, 0.60, 0.62, 1.0)
    bg2.inputs["Strength"].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    wout = nt.nodes.get("World Output")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(bg2.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], wout.inputs["Surface"])
    sc.world = world


def add_ground(size):
    """Preview-only ground plane. Never exported."""
    s = size
    me = bpy.data.meshes.new("PrevGround")
    me.from_pydata([(-s, -s, 0.0), (s, -s, 0.0), (s, s, 0.0), (-s, s, 0.0)], [], [(0, 1, 2, 3)])
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


def preview(ob, H, path):
    sc = bpy.context.scene
    cam = bpy.data.objects["PrevCam"]
    sc.camera = cam
    dx, dy, _ = ob.dimensions
    R = max(H, 0.9 * max(dx, dy))
    ground = add_ground(1.6 * R + 0.5)
    d = 2.0 * R + 0.5
    target = Vector((0.0, 0.0, 0.42 * H))
    cam.location = (d * 0.72 * 0.93, -d * 0.69 * 0.93, 0.42 * H + d * 0.42)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.film_transparent = False
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.cycles.samples = 48
    sc.render.image_settings.color_mode = "RGB"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    drop_object(ground)


def hull_area(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return 0.0

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    hull = lo[:-1] + up[:-1]
    area = 0.0
    for i in range(len(hull)):
        x0, y0 = hull[i]
        x1, y1 = hull[(i + 1) % len(hull)]
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def measure_coverage(ob):
    """Render orthographic alpha masks (front, side); coverage = mask px / convex-hull px. Returns (min, front, side)."""
    sc = bpy.context.scene
    cam = bpy.data.objects["CovCam"]
    xs = [v.co.x for v in ob.data.vertices]
    ys = [v.co.y for v in ob.data.vertices]
    zs = [v.co.z for v in ob.data.vertices]
    cxy = ((max(xs) + min(xs)) * 0.5, (max(ys) + min(ys)) * 0.5)
    cz = (max(zs) + min(zs)) * 0.5
    ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) * 1.12 + 0.05
    cam.data.ortho_scale = ext
    sc.camera = cam
    sc.render.film_transparent = True
    sc.render.resolution_x = 320
    sc.render.resolution_y = 320
    sc.cycles.samples = 12
    sc.render.image_settings.color_mode = "RGBA"
    tmp = os.path.join(tempfile.gettempdir(), "shrubc_cov.png")
    res = []
    views = (((cxy[0], -40.0, cz), (math.pi / 2, 0.0, 0.0)),
             ((40.0, cxy[1], cz), (math.pi / 2, 0.0, math.pi / 2)))
    for loc, rot in views:
        cam.location = loc
        cam.rotation_euler = rot
        sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(tmp, check_existing=False)
        buf = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        bpy.data.images.remove(img)
        arr = buf.reshape(320, 320, 4)[..., 3] > 0.5
        n = int(arr.sum())
        pts = []
        for y in np.nonzero(arr.any(axis=1))[0]:
            xx = np.nonzero(arr[y])[0]
            pts.append((int(xx[0]), int(y)))
            pts.append((int(xx[-1]) + 1, int(y)))
            pts.append((int(xx[0]), int(y) + 1))
            pts.append((int(xx[-1]) + 1, int(y) + 1))
        ha = hull_area(pts)
        res.append(min(1.0, n / ha) if ha > 0 else 0.0)
    sc.camera = bpy.data.objects["PrevCam"]
    return min(res), res[0], res[1]


# ---------------------------------------------------------------- per-variant build

def build_stems_variant(c, var, name, mats, ainfo):
    H = c["H"][var]
    n = c["cards"]
    lf = c["lf"]
    zf = c["zfill"]
    for _ in range(4):
        g, sk = build_skeleton(c, var, zf)
        cands = sample_points(sk, c["step"])
        cds = make_cards(c, var, cands, n, lf, ainfo["cells"], ainfo["aspect"])
        top = max(max(p[2] for pts, _, _ in sk["segs"] for p in pts),
                  max(cd[0][2] + cd[1][2] * cd[2] + 0.25 * cd[3] for cd in cds))
        bot = min(0.0, min(cd[0][2] + cd[1][2] * cd[2] - 0.25 * cd[3] for cd in cds))
        tot = top - bot
        if abs(tot - H) < 0.03 * H:
            break
        zf = max(0.25, zf - (tot - H) / H)
    ob = None
    thorns0 = thorn_parts(c, var, cands, c["thorns"], 0)
    for it in range(8):
        cards = make_cards(c, var, cands, n, lf, ainfo["cells"], ainfo["aspect"])
        parts = build_parts(c, sk, cards, thorns0, 0)
        ob, info = make_object(name, parts, mats, True, H)
        cov, cf, cs = measure_coverage(ob)
        stem_tris = parts[0].tris()
        print("  iter %d: cards=%d lf=%.3f tris=%d cov=%.3f (front %.3f side %.3f) k=%.2f scale=%.3f dims=%.1fx%.1fx%.1f" %
              (it, n, lf, info["tris"], cov, cf, cs, sk["k"], info["scale"], *info["dims"]))
        if cov >= COV_TARGET:
            break
        nmax = int((TRI_MAX - stem_tris) / 2)
        drop_object(ob)
        ob = None
        if n < nmax:
            n = min(nmax, int(n * 1.3))
        else:
            lf *= 1.10
    if ob is None:
        cards = make_cards(c, var, cands, n, lf, ainfo["cells"], ainfo["aspect"])
        parts = build_parts(c, sk, cards, thorns0, 0)
        ob, info = make_object(name, parts, mats, True, H)
        cov, cf, cs = measure_coverage(ob)
    info["cov"] = cov
    info["cov_views"] = (cf, cs)
    info["cards"] = n
    info["card_h"] = lf

    def lod1():
        th1 = thorn_parts(c, var, cands, c["thorns"], 1)
        p1 = build_parts(c, sk, cards, th1, 1)
        return make_object(name + "_LOD1", p1, mats, True, H)
    return ob, info, lod1


def build_pp_variant(c, var, name, mats):
    H = c["H"][var]
    g, sk = build_pp(c, var)
    parts = build_parts_pp(c, sk, 0)
    ob, info = make_object(name, parts, mats, False, H)
    info["cov"] = None
    info["pads"] = len(sk["pads"])
    info["fruit"] = len(sk["fruit"])
    info["flower"] = len(sk["flower"])

    def lod1():
        p1 = build_parts_pp(c, sk, 1)
        return make_object(name + "_LOD1", p1, mats, False, H)
    return ob, info, lod1


# ---------------------------------------------------------------- main

def main():
    for d in (SRC, TEX, PREV):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(SRC_BARK_ORIG, SRC_BARK)
    shutil.copy2(SRC_NOR_ORIG, SRC_NOR)

    only = os.environ.get("SHRUBC_ONLY")
    only = [s for s in only.split(",") if s] if only else None
    setup_scene()
    rows = []
    fails = []
    for c in SHRUBS:
        if only and c["id"] not in only:
            continue
        for var in (0, 1):
            name = "%s_v%02d" % (c["id"], var + 1)
            H = c["H"][var]
            clear_objects()
            mats, ainfo = make_mats(c, var)
            print("BUILD %s" % name)
            if c["form"] == "stems":
                ob, info, lod1 = build_stems_variant(c, var, name, mats, ainfo)
            else:
                ob, info, lod1 = build_pp_variant(c, var, name, mats)
            glb = export(ob, name)
            attrs, gmats, nmesh = glb_info(glb)
            preview(ob, H, os.path.join(PREV, name + ".png"))
            drop_object(ob)

            ob1, info1 = lod1()
            export(ob1, name + "_LOD1")
            drop_object(ob1)

            dw, dd, dh = info["dims"]
            extra = ""
            if info["cov"] is not None:
                extra = " cards=%d cov=%.3f (front %.3f side %.3f)" % (info["cards"], info["cov"], *info["cov_views"])
            else:
                extra = " pads=%d fruit=%d flowers=%d" % (info["pads"], info["fruit"], info["flower"])
            print("ASSET %s tris=%d lod1=%d dims_m=%.2f x %.2f x %.2f%s" %
                  (name, info["tris"], info1["tris"], dw, dd, dh, extra))
            for mname, mode, ds in gmats:
                print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
            if "COLOR_0" not in attrs:
                fails.append("%s glb missing COLOR_0 wind attribute" % name)
            if nmesh != 1:
                fails.append("%s glb has %d meshes (want 1)" % (name, nmesh))
            if not (c["hrange"][0] <= dh <= c["hrange"][1]):
                fails.append("%s height %.2f outside %s" % (name, dh, c["hrange"]))
            if not (3000 <= info["tris"] <= 20000):
                fails.append("%s tris %d outside 3000-20000" % (name, info["tris"]))
            ratio = info1["tris"] / float(info["tris"])
            if not (0.2 <= ratio <= 0.4):
                fails.append("%s LOD1 ratio %.2f outside 0.2-0.4" % (name, ratio))
            ml = ainfo.get("lum")
            if ml is not None and not (0.15 <= ml <= 0.75):
                fails.append("%s leaf mean luminance %.3f outside 0.15-0.75" % (name, ml))
            if info["cov"] is not None and info["cov"] < COV_MIN:
                fails.append("%s silhouette coverage %.3f < %.2f" % (name, info["cov"], COV_MIN))
            rows.append((name, c, var, info, info1, dw, dd, dh, ml))

    if not only:
        write_readme(rows)

    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d shrub-c variants written to %s" % (len(rows), OUT))


def write_readme(rows):
    lines = [
        "# Flora shrub-c authored meshes",
        "",
        "Generated by `Tools/Author-Flora-shrub_c.py` (headless Blender 5.2, Cycles previews). Deterministic: rerun reproduces the same geometry.",
        "Redo of the species rejected from shrub-a and shrub-b (willow_shrub, thorn_scrub, juniper_low, bilberry_low, alder_thicket, sagebrush_grey, prickly_pear).",
        "",
        "Method: branch tubes grown by the shrub-a skeleton code. Foliage is one painted spray per card (whole leafy twig or frond drawn procedurally into a per-species atlas), cards sampled along every twig polyline at a fixed spacing (not tips only), so the interior is filled. Card count, then card size, is raised until the measured silhouette coverage reaches the target within the 20k tri budget. Prickly pear is modelled flattened obovate pads (4 cm thick) in jointed chains from a woody base, with a painted areole and spine texture, red fruits and yellow flowers.",
        "",
        "Silhouette coverage = opaque pixels / convex-hull pixels of an orthographic alpha render (320 px), minimum of front and side views. Gate 0.60, target 0.68.",
        "",
        "Conventions: metres; Blender scene is Z-up, glTF and FBX output Y-up; origin at ground centre (min Z = 0). One combined mesh per file. Each variant is uniformly scaled to its nominal height inside the catalogue range.",
        "Slots: `Bark`, `Leaves` (alpha-masked two-sided spray cards; stems species), `Pads` / `Fruit` / `Flower` (prickly pear). Vertex colour `WindWeight` R = (z/height)^1.2 for plants; R = 0 for prickly pear (rigid).",
        "LOD1: 30 % of the leaf cards, stems on every third polyline point with fewer sides, thorns thinned; prickly pear pads at 8x3 grid.",
        "",
        "| File (.glb / .fbx) | Tris LOD0 | Tris LOD1 | W x D x H (m) | Slots | Colour variant | Leaf mean luma | Silhouette coverage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, c, var, info, info1, dw, dd, dh, ml in rows:
        cov = "%.2f" % info["cov"] if info["cov"] is not None else "n/a"
        lines.append("| %s.glb / .fbx | %d | %d | %.2f x %.2f x %.2f | %s | %s | %s | %s |" %
                     (name, info["tris"], info1["tris"], dw, dd, dh,
                      ", ".join(info["slots"]), c["tint_names"][var],
                      "%.3f" % ml if ml is not None else "n/a", cov))
    lines += [
        "",
        "Previews: `previews/<name>.png`, 512 px, LOD0, 3/4 view over a preview-only ground plane (not exported).",
        "",
        "Species (catalogue rows in `Docs/FloraCatalog.md`):",
    ]
    for c in SHRUBS:
        lines.append("- `%s`: %s. Height range %s m. Variants: %s." %
                     (c["id"], c["silhouette"], "%g-%g" % c["hrange"],
                      "; ".join("v%02d %s" % (i + 1, c["tint_names"][i]) for i in range(2))))
    lines += [
        "",
        "Textures (`textures/`):",
        "- `<id>_vNN_leaves.png`: 1024 px RGBA spray atlas, painted by this script (no third-party art).",
        "- `prickly_pear_vNN_pad.png`: 512 px pad albedo with areoles and spines, painted by this script.",
        "- `<id>_vNN_bark.png`: 1024 px, tinted from the Poly Haven dead_tree_trunk diffuse.",
        "- `src/dead_tree_trunk_*`: shared bark diffuse and normal map copies.",
        "",
        "Provenance:",
        "- Geometry and spray/pad textures: procedural, generated by this script. No third-party meshes.",
        "- Bark source: Poly Haven dead_tree_trunk (CC0 per Poly Haven site licence). Not individually re-verified against the licence page.",
        "- C:\\Misc\\Vivarium textures not used.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
