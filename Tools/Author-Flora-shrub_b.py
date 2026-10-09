"""Author shrub-b flora headless: bilberry_low, alder_thicket, sagebrush_grey, liana_cluster,
understory_ginger, prickly_pear. Two variants each.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-shrub_b.py

Metres, Z-up in Blender (glTF/FBX output Y-up), origin at ground centre (min Z = 0).
Helpers are copied from Author-Flora-shrub_a.py (hash, tube sweep, branch growth, leaf cards on
the CC0 Poly Haven island_tree_01 leaf sheet, wind VC, preview). New here:
  - bilberry: dark berry cards drawn from a painted patch in the leaf atlas (no extra slot).
  - liana: helical vines up a trunk stub, draped and hanging; leaves along the vines.
  - ginger: upright pseudostem clump, leaves only in the upper part of each stalk.
  - prickly pear: modelled flattened pads (ellipsoid grids) stacked in branching clusters,
    spines as small Bark tubes, solid pad colour, no leaf cards, wind VC zero.
All variation comes from h01(tag, index...), a stateless integer hash. No RNG state.
Per variant: <id>_vNN.glb + .fbx (LOD0), <id>_vNN_LOD1.glb + .fbx, 512 px preview PNG
(LOD0, 3/4 view over a preview-only ground plane, not exported).
Output dir is owned by this script: ArtSource/Authored/Flora/shrub_b/.
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

SEED = 9417
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
LEAF_TEX = 1024
LEAF_MEAN = 0.36  # target mean luminance of leaf albedo over the leaf mask
BERRY_PX = 40     # berry patch size in the leaf atlas (pixels)

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "shrub_b")
TEX = os.path.join(OUT, "textures")
SRC = os.path.join(TEX, "src")
PREV = os.path.join(OUT, "previews")

SRC_LEAF_ORIG = os.path.join(ART, "PolyHaven", "island_tree_01", "textures", "island_tree_01_leaves_diff_1k.jpg")
SRC_BARK_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_diff_1k.jpg")
SRC_NOR_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_nor_gl_1k.jpg")
SRC_LEAF = os.path.join(SRC, "island_tree_01_leaves_diff_1k.jpg")
SRC_BARK = os.path.join(SRC, "dead_tree_trunk_diff_1k.jpg")
SRC_NOR = os.path.join(SRC, "dead_tree_trunk_nor_gl_1k.jpg")

# Heights from docs/FloraCatalog.md (shrub-b rows, last column). H = per-variant height m.
# form: "stems" (branch growth), "liana" (helix + drape on trunk stub), "pads" (cactus pad clusters).
SHRUBS = [
    dict(id="bilberry_low", tag=11, form="stems", H=(0.38, 0.50), hrange=(0.3, 0.6),
         nst=12, sp=0.30, tlen=(0.40, 0.55), lean=1.0, rise=0.25, curve=0.0, grav=0.0,
         kids=2, kang=(20, 40), depth=2, lat=0, shrink=0.6, rad=0.014,
         leaves=True, cards=6000, lmin=0, lf=0.030, lwf=1.0, lflat=0.3, ldroop=0.1,
         berries=700, berry_lf=0.02, zmin=0.0,
         wind=True, tints=[(0.34, 0.50, 0.26), (0.36, 0.48, 0.46)],
         tint_names=["green", "blue-green"], bark=(0.50, 0.42, 0.34),
         silhouette="low wiry mat of small rounded leaves with dark berries"),
    dict(id="alder_thicket", tag=12, form="stems", H=(3.2, 4.4), hrange=(3.0, 6.0),
         nst=7, sp=0.15, tlen=(0.60, 0.75), lean=0.2, rise=1.0, curve=0.08, grav=0.0,
         kids=3, kang=(30, 50), depth=2, lat=1, shrink=0.6, rad=0.020,
         leaves=True, cards=6500, lmin=1, lf=0.16, lwf=1.5, lflat=0.25, ldroop=0.1,
         berries=0, berry_lf=0.0, zmin=0.0,
         wind=True, tints=[(0.30, 0.48, 0.30), (0.42, 0.50, 0.40)],
         tint_names=["dark green", "grey-green"], bark=(0.62, 0.60, 0.56),
         silhouette="dense round-headed multi-stem thicket of broad leaves"),
    dict(id="sagebrush_grey", tag=13, form="stems", H=(0.6, 0.9), hrange=(0.5, 1.2),
         nst=10, sp=0.25, tlen=(0.35, 0.50), lean=0.5, rise=1.0, curve=0.0, grav=0.0,
         kids=2, kang=(25, 45), depth=2, lat=1, shrink=0.55, rad=0.010,
         leaves=True, cards=6000, lmin=0, lf=0.045, lwf=0.9, lflat=0.3, ldroop=0.05,
         berries=0, berry_lf=0.0, zmin=0.0,
         wind=True, tints=[(0.62, 0.66, 0.62), (0.50, 0.56, 0.62)],
         tint_names=["silver grey", "blue-grey"], bark=(0.82, 0.80, 0.74),
         silhouette="silver-grey fine aromatic rounded mound"),
    dict(id="liana_cluster", tag=14, form="liana", H=(1.6, 2.4), hrange=(1.0, 4.0),
         nst=7, stub_frac=0.6, stub_r=0.09, vine_r=0.011, turns=(0.8, 1.4), N=14,
         leaves=True, cards=3600, lmin=0, lf=0.07, lwf=1.1, lflat=0.6, ldroop=0.2,
         berries=0, berry_lf=0.0, zmin=0.0,
         wind=True, tints=[(0.30, 0.48, 0.24), (0.32, 0.36, 0.20)],
         tint_names=["green", "olive"], bark=(0.55, 0.48, 0.40),
         silhouette="ropey vines helixed up a trunk stub, draped over and hanging"),
    dict(id="understory_ginger", tag=15, form="stems", H=(0.9, 1.25), hrange=(0.8, 1.5),
         nst=14, sp=0.12, tlen=(0.70, 0.85), lean=0.25, rise=1.0, curve=0.0, grav=0.0,
         kids=0, kang=(0, 0), depth=0, lat=0, shrink=0.6, rad=0.020,
         leaves=True, cards=3000, lmin=0, lf=0.30, lwf=0.55, lflat=0.15, ldroop=0.25,
         berries=0, berry_lf=0.0, zmin=0.25,
         wind=True, tints=[(0.40, 0.68, 0.30), (0.56, 0.30, 0.30)],
         tint_names=["bright green", "maroon"], bark=(0.50, 0.62, 0.38),
         silhouette="upright leafy pseudostem clump with broad lance leaves"),
    dict(id="prickly_pear", tag=16, form="pads", H=(0.6, 0.85), hrange=(0.5, 1.5),
         roots=3, branch=(2, 3), pdepth=3, A=0.10, B=0.075, C=0.012, spines=3,
         leaves=False, cards=0, berries=0, berry_lf=0.0, lf=0.0, lwf=0.0, lflat=0.0, ldroop=0.0,
         lmin=0, zmin=0.0, wind=False,
         tints=[(0.34, 0.52, 0.46), (0.46, 0.40, 0.46)],
         tint_names=["blue-green", "purple-tinged"], bark=(0.90, 0.86, 0.72),
         silhouette="jointed flat pads in branching clusters, spines on pads"),
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


def pad_mesh(part, cen, L, W, N, A, B, C, nu, nv):
    """Flattened ellipsoid pad: semi-axes A (along L), B (along W), C (along N). Pole fans at ends."""
    def P(u, v):
        s = math.sin(v)
        return add(cen, add(add(mul(L, A * s * math.cos(u)), mul(W, B * s * math.sin(u))),
                            mul(N, C * math.cos(v))))
    top = part.v(P(0.0, 0.0))
    bot = part.v(P(0.0, math.pi))
    rings = []
    for i in range(1, nv):
        vv = math.pi * i / nv
        rings.append([part.v(P(TAU * j / nu, vv)) for j in range(nu)])
    z = (0.0, 0.0)
    for j in range(nu):
        j2 = (j + 1) % nu
        part.tri(top, rings[0][j], rings[0][j2], ((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)))
        part.tri(bot, rings[-1][j2], rings[-1][j], ((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)))
    for i in range(len(rings) - 1):
        for j in range(nu):
            j2 = (j + 1) % nu
            part.quad(rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j],
                      ((z), (z), (z), (z)))


# ---------------------------------------------------------------- skeletons / leaf cards

class Gen:
    def __init__(self, c, var):
        self.c = c
        self.H = c["H"][var]
        self.tag = c["tag"] * 1000 + var * 100
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
        pts.append(cur)
        rads.append(r * (1.0 - 0.3 * (i + 1) / nseg))
    sk["segs"].append((pts, rads, depth))
    if depth >= c["lmin"]:
        for j in range(1, len(pts)):
            sk["cands"].append((pts[j], unit(sub(pts[j], pts[j - 1])), depth))
    if depth >= c["depth"]:
        sk["tips"].append((pts[-1], dv))
        return
    if c["lat"] and depth == 0:
        md = unit(sub(pts[2], pts[1]))
        spawn(g, pts[2], md, L * 0.6, rads[2], depth, sk, c["lat"])
    spawn(g, cur, dv, L, r, depth, sk, c["kids"])


def skeleton_stems(g, c, sk):
    H = g.H
    for i in range(c["nst"]):
        a = TAU * (i + g.rr(-0.3, 0.3)) / c["nst"]
        rb = c["sp"] * H * math.sqrt(g.r())
        base = (math.cos(a) * rb, math.sin(a) * rb, 0.0)
        out = unit((base[0], base[1], 0.0))
        d = unit(add(mul(out, c["lean"] * g.rr(0.8, 1.2)), (0.0, 0.0, c["rise"])))
        L = H * g.rr(c["tlen"][0], c["tlen"][1])
        grow(g, base, d, L, c["rad"] * H, 0, sk)


def skeleton_liana(g, c, sk):
    H = g.H
    Hs = c["stub_frac"] * H
    sk["segs"].append(([(0.0, 0.0, 0.0), (0.0, 0.0, Hs * 0.5), (0.0, 0.0, Hs)],
                       [c["stub_r"], c["stub_r"] * 0.9, c["stub_r"] * 0.7], 0))
    N = c["N"]
    for i in range(c["nst"]):
        a0 = TAU * (i + g.rr(-0.3, 0.3)) / c["nst"]
        turns = g.rr(c["turns"][0], c["turns"][1])
        rh = c["stub_r"] + c["vine_r"] * 1.5 + g.rr(0.0, 0.03)
        top = Hs * g.rr(0.85, 1.0)
        pts = []
        for k in range(N + 1):
            t = k / float(N)
            ang = a0 + turns * TAU * t
            pts.append((math.cos(ang) * rh, math.sin(ang) * rh, top * t))
        ange = a0 + turns * TAU
        ox, oy = math.cos(ange), math.sin(ange)
        reach = H * g.rr(0.35, 0.6)
        drop = H * g.rr(0.5, 0.9)
        tx, ty, tz = pts[-1]
        for k in range(1, 9):
            s = k / 8.0
            pts.append((tx + ox * reach * s, ty + oy * reach * s, max(0.04 * H, tz - drop * s * s)))
        n = len(pts)
        rads = [c["vine_r"] * (1.0 - 0.5 * k / (n - 1)) for k in range(n)]
        sk["segs"].append((pts, rads, 0))
        for k in range(1, n):
            sk["cands"].append((pts[k], unit(sub(pts[k], pts[k - 1])), 0))


def grow_pad(g, c, sk, cen, L, N, A, B, C, depth):
    W = unit(cross(N, L))
    sk["pads"].append((cen, L, W, N, A, B, C))
    plist = []
    for _ in range(c["spines"]):
        base = add(add(cen, mul(L, A * g.rr(-0.6, 0.6))),
                   add(mul(W, B * g.rr(-0.8, 0.8)), mul(N, C * 0.9)))
        dv = unit(add(mul(N, 0.7), add(mul(L, g.rr(-0.4, 0.6)), mul(W, g.rr(-0.4, 0.4)))))
        tip = add(base, mul(dv, g.rr(0.010, 0.018)))
        plist.append(([base, tip], [0.0016, 0.0003]))
    sk["spines"].append(plist)
    if depth >= c["pdepth"]:
        return
    nkid = int(g.rr(c["branch"][0], c["branch"][1] + 0.999))
    top = add(cen, mul(L, A * 0.92))
    Ac, Bc = A * 0.9, B * 0.9
    for k in range(nkid):
        side = g.rr(-0.6, 0.6)
        Lc = unit(add(L, mul(W, side)))
        Nc = add(mul(N, 0.8), mul(W, g.rr(-0.6, 0.6)))
        Nc = unit(sub(Nc, mul(Lc, dot(Nc, Lc))))
        off = mul(W, (k - (nkid - 1) / 2.0) * Bc * 1.1)
        ccen = add(add(top, off), mul(Lc, Ac))
        grow_pad(g, c, sk, ccen, Lc, Nc, Ac, Bc, C, depth + 1)


def skeleton_pads(g, c, sk):
    A, B, C = c["A"], c["B"], c["C"]
    for r in range(c["roots"]):
        a = TAU * (r + g.rr(-0.25, 0.25)) / c["roots"]
        ca, sa = math.cos(a), math.sin(a)
        base = (ca * 0.05, sa * 0.05, 0.0)
        L = unit((ca * 0.35, sa * 0.35, 1.0))
        tang = (-sa, ca, 0.0)
        N = unit(sub(tang, mul(L, dot(tang, L))))
        cen = add(base, mul(L, A))
        grow_pad(g, c, sk, cen, L, N, A, B, C, 0)


def build_skeleton(c, var):
    g = Gen(c, var)
    sk = {"segs": [], "cands": [], "tips": [], "pads": [], "spines": []}
    if c["form"] == "stems":
        skeleton_stems(g, c, sk)
    elif c["form"] == "liana":
        skeleton_liana(g, c, sk)
    elif c["form"] == "pads":
        skeleton_pads(g, c, sk)
    zmin = c["zmin"] * g.H
    sk["cands"] = [x for x in sk["cands"] if x[0][2] >= zmin]
    return g, sk


def runs(flags):
    out = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def leaf_sheet(px):
    """Find the 8 leaves on the CC0 sheet: returns boxes (c0, c1, r0, r1)."""
    mask = px[..., :3].max(axis=2) > 0.10
    boxes = []
    for ra, rb in runs(mask.any(axis=1)):
        for ca, cb in runs(mask[ra:rb].any(axis=0)):
            if cb - ca < 40:
                continue
            rows = np.nonzero(mask[ra:rb, ca:cb].any(axis=1))[0]
            boxes.append((ca, cb, ra + int(rows[0]), ra + int(rows[-1]) + 1))
    if len(boxes) != 8:
        raise RuntimeError("leaf sheet: %d leaves found, expected 8" % len(boxes))
    return boxes


def leaf_cards(g, sk, sheet, n, lf, lwf, lflat, ldroop):
    cands = sk["cands"]
    cards = []
    for _ in range(n):
        pos, t, _dep = cands[min(len(cands) - 1, int(g.r() * len(cands)))]
        o = (pos[0], pos[1], 0.0)
        o = unit(o) if length(o) > 1e-6 else (0.0, 0.0, 1.0)
        radial = unit(add(o, (0.0, 0.0, 0.4)))
        ld = unit(add(mul(t, lflat), mul(radial, 1.0 - lflat)))
        ld = unit(add(add(ld, mul(g.jit(1.0), 0.30)), (0.0, 0.0, -ldroop)))
        box = sheet[min(len(sheet) - 1, int(g.r() * len(sheet)))]
        bw = box[1] - box[0]
        bh = box[3] - box[2]
        h = lf * g.rr(0.8, 1.2)
        w = h * (bw / float(bh)) * lwf
        phi = TAU * g.r()
        cards.append((pos, ld, h, w, box, phi))
    return cards


def leaf_quad(part, card):
    pos, ld, h, w, box, phi = card
    a0, b0 = perp(ld)
    a = add(mul(a0, math.cos(phi)), mul(b0, math.sin(phi)))
    half = mul(a, w * 0.5)
    tip = add(pos, mul(ld, h))
    pts = (sub(pos, half), add(pos, half), add(tip, half), sub(tip, half))
    S = float(LEAF_TEX)
    u0, u1 = box[0] / S, box[1] / S
    v0, v1 = box[2] / S, box[3] / S
    i = [part.v(p) for p in pts]
    part.quad(i[0], i[1], i[2], i[3], ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))


def build_parts(c, var, sk, cards, lod):
    seg = 6 if lod == 0 else 3
    stems_p = Part("stems", "Bark")
    leaf_p = Part("leaves", "Leaves")
    pad_p = Part("pads", "Pads")
    for pts, rads, _depth in sk["segs"]:
        if lod == 1:
            idx = list(range(0, len(pts), 3))
            if idx[-1] != len(pts) - 1:
                idx.append(len(pts) - 1)
            pts = [pts[i] for i in idx]
            rads = [rads[i] for i in idx]
        tube(stems_p, pts, rads, seg, v_scale=2.0)
    for plist in sk["spines"]:
        for si, (pts, rads) in enumerate(plist):
            if lod == 1 and si > 0:
                continue
            tube(stems_p, pts, rads, 4)
    for cen, L, W, N, A, B, C in sk["pads"]:
        if lod == 0:
            pad_mesh(pad_p, cen, L, W, N, A, B, C, 10, 5)
        else:
            pad_mesh(pad_p, cen, L, W, N, A, B, C, 5, 3)
    for i, card in enumerate(cards):
        if lod == 0 or i % 10 < 3:
            leaf_quad(leaf_p, card)
    return [p for p in (stems_p, leaf_p, pad_p) if p.faces]


# ---------------------------------------------------------------- textures / materials

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


def write_png(arr, path, name):
    size = arr.shape[0]
    img = bpy.data.images.new(name, arr.shape[1], size, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def free_block(alpha, n):
    """First n x n block in the leaf atlas with no leaf alpha in it (8 px margin)."""
    solid = alpha > 0.5
    for y in range(8, LEAF_TEX - n - 8, 8):
        for x in range(8, LEAF_TEX - n - 8, 8):
            if not solid[y - 8:y + n + 8, x - 8:x + n + 8].any():
                return x, y
    raise RuntimeError("no free block in leaf atlas for berry patch")


def leaf_tex(c, var, px):
    """Colour-corrected leaf albedo (mean luminance LEAF_MEAN over leaf mask) with alpha cut-out.
    Optional berry patch painted into a free block; returns its pixel box."""
    rgb = px[..., :3]
    alpha = np.clip((rgb.max(axis=2) - 0.05) / 0.05, 0.0, 1.0).astype(np.float32)
    m = alpha > 0.5
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    ln = lum / max(float(lum[m].mean()), 1e-4)
    tint = np.array(c["tints"][var], dtype=np.float32)
    col = ln[..., None] * tint[None, None, :]
    clum = 0.2126 * col[..., 0] + 0.7152 * col[..., 1] + 0.0722 * col[..., 2]
    col = col * (LEAF_MEAN / max(float(clum[m].mean()), 1e-4))
    out = np.empty_like(px)
    out[..., :3] = np.clip(col, 0.0, 1.0)
    out[..., 3] = alpha
    flum = 0.2126 * out[..., 0] + 0.7152 * out[..., 1] + 0.0722 * out[..., 2]
    mean_lum = float(flum[m].mean())
    box = None
    if c["berries"]:
        n = BERRY_PX
        x, y = free_block(out[..., 3], n)
        yy, xx = np.mgrid[0:n, 0:n]
        rad = n / 2.0 - 3.0
        inside = ((xx - (n - 1) / 2.0) ** 2 + (yy - (n - 1) / 2.0) ** 2) <= rad * rad
        out[y:y + n, x:x + n, 0] = 0.10
        out[y:y + n, x:x + n, 1] = 0.08
        out[y:y + n, x:x + n, 2] = 0.20
        out[y:y + n, x:x + n, 3] = inside.astype(np.float32)
        box = (x, x + n, y, y + n)
    path = os.path.join(TEX, "%s_v%02d_leaves.png" % (c["id"], var + 1))
    write_png(out, path, "leaves_%s_%d" % (c["id"], var + 1))
    return load_img(path), mean_lum, box


def bark_tex(c, var, size=1024):
    px = square_pixels(load_img(SRC_BARK), size)
    tint = np.array(c["bark"], dtype=np.float32)
    px[..., :3] = np.clip(px[..., :3] * tint[None, None, :], 0.0, 1.0)
    path = os.path.join(TEX, "%s_v%02d_bark.png" % (c["id"], var + 1))
    write_png(px, path, "bark_%s_%d" % (c["id"], var + 1))
    return load_img(path)


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


def make_solid_material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
            n.inputs["Roughness"].default_value = 0.55
    return m


def make_mats(c, var, leaf_px, leaf_means):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    nor = load_img(SRC_NOR, noncolor=True)
    mats = {"Bark": make_material("Bark", bark_tex(c, var), nor)}
    box = None
    if c["leaves"]:
        leaf_img, mean_lum, box = leaf_tex(c, var, leaf_px)
        leaf_means[c["id"] + "_v%02d" % (var + 1)] = mean_lum
        mats["Leaves"] = make_material("Leaves", leaf_img, masked=True, two_sided=True)
    if c["form"] == "pads":
        mats["Pads"] = make_solid_material("Pads", c["tints"][var])
    return mats, box


# ---------------------------------------------------------------- realise / export / preview

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


def make_object(name, parts, mats, wind=True):
    allz = min(p[2] for part in parts for p in part.verts)
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

    # Wind weight: R = (z / height)^1.2, 0 at base, 1 at tips. Cactus: R = 0 everywhere.
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
    drop_object(ground)


# ---------------------------------------------------------------- main

def main():
    for d in (SRC, TEX, PREV):
        os.makedirs(d, exist_ok=True)
    shutil.copy2(SRC_LEAF_ORIG, SRC_LEAF)
    shutil.copy2(SRC_BARK_ORIG, SRC_BARK)
    shutil.copy2(SRC_NOR_ORIG, SRC_NOR)

    setup_scene()
    leaf_px = square_pixels(load_img(SRC_LEAF), LEAF_TEX)
    sheet = leaf_sheet(leaf_px)
    leaf_means = {}
    rows = []
    fails = []
    for c in SHRUBS:
        for var in (0, 1):
            name = "%s_v%02d" % (c["id"], var + 1)
            H = c["H"][var]
            clear_objects()
            mats, berry_box = make_mats(c, var, leaf_px, leaf_means)
            g, sk = build_skeleton(c, var)
            cards = []
            if c["leaves"]:
                cards = leaf_cards(g, sk, sheet, c["cards"], c["lf"], c["lwf"], c["lflat"], c["ldroop"])
                if berry_box is not None:
                    cards += leaf_cards(g, sk, [berry_box], c["berries"], c["berry_lf"], 1.0, 0.6, 0.0)

            ob, info = make_object(name, build_parts(c, var, sk, cards, 0), mats, c["wind"])
            glb = export(ob, name)
            attrs, gmats = glb_info(glb)
            preview(ob, H, os.path.join(PREV, name + ".png"))
            drop_object(ob)

            ob1, info1 = make_object(name + "_LOD1", build_parts(c, var, sk, cards, 1), mats, c["wind"])
            export(ob1, name + "_LOD1")
            drop_object(ob1)

            dw, dd, dh = info["dims"]
            print("ASSET %s tris=%d lod1=%d dims_m=%.2f x %.2f x %.2f" %
                  (name, info["tris"], info1["tris"], dw, dd, dh))
            for mname, mode, ds in gmats:
                print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
            if "COLOR_0" not in attrs:
                fails.append("%s glb missing COLOR_0 wind attribute" % name)
            if not (c["hrange"][0] <= dh <= c["hrange"][1]):
                fails.append("%s height %.2f outside %s" % (name, dh, c["hrange"]))
            if not (3000 <= info["tris"] <= 20000):
                fails.append("%s tris %d outside 3000-20000" % (name, info["tris"]))
            ratio = info1["tris"] / float(info["tris"])
            if not (0.2 <= ratio <= 0.4):
                fails.append("%s LOD1 ratio %.2f outside 0.2-0.4" % (name, ratio))
            ml = leaf_means.get(name)
            if ml is not None and not (0.25 <= ml <= 0.5):
                fails.append("%s leaf mean luminance %.3f outside 0.25-0.5" % (name, ml))
            rows.append((name, c, var, info, info1, dw, dd, dh, ml))

    lines = [
        "# Flora shrub-b authored meshes",
        "",
        "Generated by `Tools/Author-Flora-shrub_b.py` (headless Blender 5.2, Cycles previews). Deterministic: rerun reproduces the same geometry.",
        "",
        "Method: branch tubes grown by the shrub-a skeleton code (stems), a helix-and-drape vine system on a trunk stub (liana), upright pseudostems (ginger), or stacked flattened pad ellipsoids with spines (prickly pear). Leaf cards attach to branch or vine points, never free-floating.",
        "",
        "Conventions: metres; Blender scene is Z-up, glTF and FBX output Y-up; origin at ground centre (min Z = 0). One combined mesh per file.",
        "Slots: `Bark` (stems, vines, stub, spines), `Leaves` (alpha-masked two-sided cards; absent for prickly pear), `Pads` (prickly pear only, solid colour). Vertex colour `WindWeight` R = (z/height)^1.2 for plants; R = 0 for prickly pear (rigid).",
        "LOD1: 30 % of the leaf cards, stems reduced to 3-sided tubes on every third polyline point; prickly pear pads at 5x3 grid, one spine per pad.",
        "",
        "| File (.glb / .fbx) | Tris LOD0 | Tris LOD1 | W x D x H (m) | Slots | Colour variant | Leaf mean luma |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, c, var, info, info1, dw, dd, dh, ml in rows:
        lines.append("| %s.glb / .fbx | %d | %d | %.2f x %.2f x %.2f | %s | %s | %s |" %
                     (name, info["tris"], info1["tris"], dw, dd, dh,
                      ", ".join(info["slots"]), c["tint_names"][var],
                      "%.3f" % ml if ml is not None else "n/a"))
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
        "Bilberry dark berries: round cards drawn from a painted dark-blue patch in the leaf atlas (no separate berry slot).",
        "Alder catkins: none. Alder rust catkin tint not modelled.",
        "Sagebrush and ginger: leaf shapes from the simple leaf sheet; no separate geometry.",
        "Prickly pear: no glochid tufts, no flowers or fruit; pads are solid colour, no texture.",
        "",
        "Textures (`textures/`):",
        "- `<id>_vNN_leaves.png`: 1024 px RGBA, leaf albedo colour-corrected to mean luminance 0.36 over the leaf mask (bilberry: plus berry patch).",
        "- `<id>_vNN_bark.png`: 1024 px, tinted from the Poly Haven bark diffuse.",
        "- `dead_tree_trunk_nor_gl_1k.jpg`: shared bark normal map.",
        "",
        "Provenance:",
        "- Geometry: procedural, generated by this script. No third-party meshes.",
        "- Leaf and bark sources: Poly Haven island_tree_01 leaves diffuse and dead_tree_trunk diffuse and normal (CC0 per Poly Haven site licence). Copies in `textures/src/`. Not individually re-verified against the licence page.",
        "- C:\\Misc\\Vivarium textures not used.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d shrub-b variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
