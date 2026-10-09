"""Author conifer flora headless: pine_open, spruce_conifer, larch_sparse, krummholz_pine. 3 variants each.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-conifer.py

Writes only under ArtSource/Authored/Flora/conifer/ (and textures/ beneath it).
Per variant: <id>_vNN.glb/.fbx, <id>_vNN_LOD1 (~30%), <id>_vNN_LOD2 (~8%),
<id>_vNN_preview.png (3/4 view, ground plane), <id>_vNN_far.png (30 m silhouette view).

Structure (rewrite 3): a real branch hierarchy, foliage always attached to a branch.
  spruce / larch : trunk -> whorls of primary branches. Each branch carries overlapping needle FRONDS
                   (a frond card is a whole herringbone branch-spray whose rachis lies ON the branch,
                   three planes: flat and two drooping), plus hanging curtains that bridge the whorls.
  pine / krummholz: trunk -> limbs -> secondaries -> twigs. Needle plumes (Poly Haven pine twig spray)
                   start ON the twig axis and run along it, so the twig is visible through the tuft.
                   Krummholz: contorted trunk, foliage and limbs biased to the lee (+X) side.
Needle textures: pine = Poly Haven pine_tree_01 twig alpha + diffuse (CC0), cropped and resampled.
  spruce / larch = frond sprays drawn procedurally with colours sampled from Poly Haven fir_tree_01 twig
  diffuse (the fir twig has no alpha mask, so the mask is drawn).
Bark = Poly Haven pine_tree_01 or fir_tree_01 bark diffuse + normal.
LODs are regrown at lower density (cards and wood simplified), then merged by distance and degenerate-face
cleaned. Decimate collapse on thousands of disjoint cards erodes them, so it is not used.
Metres, Blender Z-up, origin at ground centre (min Z = 0, trunk base on XY origin).
GLB is Y-up per glTF spec. FBX is Blender-native Z-up (identity axes).
Vertex colour "WindWeight": R = wind weight (0 at trunk base, 1 at tips). G = B = 0, A = 1.
Randomness: h01()/hn() integer hash only, keyed on species tag, branch serial and slot. No RNG state.
Dev knobs (env): CONIFER_ONLY=<id,id>, CONIFER_NV=<n variants>, CONIFER_SCRATCH=<dir for montage>.
"""

import math
import os
import sys
import tempfile
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
OUT = os.path.join(ART, "Authored", "Flora", "conifer")
TEX = os.path.join(OUT, "textures")
PH = os.path.join(ART, "PolyHaven")
PINE_TEX = os.path.join(PH, "pine_tree_01", "textures")
FIR_TEX = os.path.join(PH, "fir_tree_01", "textures")
PINE_ALPHA = os.path.join(PINE_TEX, "pine_tree_01_twig_alpha_1k.png")
PINE_TWIG = os.path.join(PINE_TEX, "pine_tree_01_twig_diff_1k.jpg")
FIR_TWIG = os.path.join(FIR_TEX, "fir_tree_01_twig_diff_1k.jpg")
PINE_BARK = os.path.join(PINE_TEX, "pine_tree_01_bark_diff_1k.jpg")
PINE_BARK_NOR = os.path.join(PINE_TEX, "pine_tree_01_bark_nor_gl_1k.jpg")
FIR_BARK = os.path.join(FIR_TEX, "fir_tree_01_bark_diff_1k.jpg")
FIR_BARK_NOR = os.path.join(FIR_TEX, "fir_tree_01_bark_nor_gl_1k.jpg")
LUM_W = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


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


def hn(*keys):
    """Vectorised h01: keys may be scalars or integer arrays. Same mixing, uint64 lanes masked to 32 bits."""
    m = np.uint64(M32)
    x = np.uint64(SEED & M32)
    for k in keys:
        kk = np.asarray(k).astype(np.int64).astype(np.uint64) & m
        x = ((x ^ kk) * np.uint64(0x9E3779B1)) & m
        x = x ^ (x >> np.uint64(15))
    x = (x * np.uint64(0x85EBCA6B)) & m
    x = x ^ (x >> np.uint64(13))
    x = (x * np.uint64(0xC2B2AE35)) & m
    x = x ^ (x >> np.uint64(16))
    return np.asarray(x, dtype=np.float64) / 4294967296.0


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
        self.faces = []

    def v(self, p):
        self.verts.append(p)
        return len(self.verts) - 1

    def quad(self, a, b, c, d, uvs):
        self.faces.append(((a, b, c, d), uvs))

    def tri(self, a, b, c, uvs):
        self.faces.append(((a, b, c), uvs))


def tri_count(part):
    return sum(2 if len(idx) == 4 else 1 for idx, _ in part.faces)


def tube(part, pts, radii, segs, flare=None, caps=True):
    """Sweep a ring of `segs` verts along polyline pts. V follows arc length so bark does not stretch."""
    n = len(pts)
    rings = []
    vs = [0.0]
    for i in range(1, n):
        ds = length(sub(pts[i], pts[i - 1]))
        rr = max(0.012, 0.5 * (radii[i] + radii[i - 1]))
        vs.append(vs[-1] + ds / (TAU * rr))
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
        for j in range(segs):
            j2 = (j + 1) % segs
            u0 = j / segs
            u1 = (j + 1) / segs
            part.quad(rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j],
                      ((u0, vs[i]), (u1, vs[i]), (u1, vs[i + 1]), (u0, vs[i + 1])))
    if caps:
        for ring, idx in ((rings[0], 0), (rings[-1], n - 1)):
            c = part.v(pts[idx])
            for j in range(segs):
                j2 = (j + 1) % segs
                part.tri(c, ring[j], ring[j2], ((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)))


def make_flare(pts, amp):
    def f(i, th):
        z = pts[i][2]
        base = amp * max(0.0, 1.0 - z / 2.5) ** 2
        lobe = 0.35 * amp * (max(0.0, math.cos(4.0 * th)) ** 4) * max(0.0, 1.0 - z / 2.0)
        return 1.0 + base + lobe
    return f


def rot_about(v, axis, ang):
    k = unit(axis)
    c = math.cos(ang)
    s = math.sin(ang)
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1.0 - c)))


class Ctx:
    def __init__(self, T, density, lod):
        self.T = T
        self.density = density
        self.lod = lod
        self.n = 0
        self.wood = Part("wood", "Bark")
        self.leaf = Part("foliage", "Leaves")


def ribbon(ctx, pts, hw, roll=0.0, side0=None, flip=False):
    """Strip along polyline pts, half-width hw, plane rolled about the tangent. U across, V along (0 at pts[0])."""
    n = len(pts)
    ring = []
    for i, p in enumerate(pts):
        if i == 0:
            t = unit(sub(pts[1], pts[0]))
        elif i == n - 1:
            t = unit(sub(pts[-1], pts[-2]))
        else:
            t = unit(sub(pts[i + 1], pts[i - 1]))
        if side0 is not None:
            side = sub(side0, mul(t, dot(side0, t)))
            if length(side) < 1e-4:
                side = cross(t, (1.0, 0.0, 0.0))
            side = unit(side)
            w = side
            if roll != 0.0:
                w = rot_about(side, t, roll)
        else:
            side = cross(t, (0.0, 0.0, 1.0))
            if length(side) < 1e-4:
                side = cross(t, (1.0, 0.0, 0.0))
            side = unit(side)
            perp = unit(cross(side, t))
            w = add(mul(side, math.cos(roll)), mul(perp, math.sin(roll)))
        ring.append((ctx.leaf.v(sub(p, mul(w, hw))), ctx.leaf.v(add(p, mul(w, hw)))))
    u0, u1 = (1.0, 0.0) if flip else (0.0, 1.0)
    for i in range(n - 1):
        v0 = i / (n - 1)
        v1 = (i + 1) / (n - 1)
        ctx.leaf.quad(ring[i][0], ring[i][1], ring[i + 1][1], ring[i + 1][0],
                      ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))


def bpt(p0, d, L, droop, t):
    return (p0[0] + d[0] * L * t, p0[1] + d[1] * L * t, p0[2] + d[2] * L * t + droop * L * t * t)


def btan(d, droop, t):
    return unit((d[0], d[1], d[2] + 2.0 * droop * t))


def trunk_xy(S, H, z):
    t = z / H
    return (S.get("sway", 0.0) * H * math.sin(2.7 * t + 0.6) * t, S.get("sway", 0.0) * H * math.sin(2.1 * t + 2.0) * t)


# ---------------------------------------------------------------- spruce / larch (whorled frond conifers)

def frond_branch(ctx, S, V, p0, d, L, r0, droop):
    ctx.n += 1
    b = ctx.n
    T = ctx.T
    lod = ctx.lod
    dens = ctx.density

    if lod == 0 or (lod == 1 and S["wood_lod1"]) or (lod == 2 and S["wood_lod2"]):
        ns = 4 if lod == 0 else 2
        pts = [bpt(p0, d, L, droop, i / ns) for i in range(ns + 1)]
        radii = [max(0.006, r0 * (1.0 - 0.8 * i / ns)) for i in range(ns + 1)]
        tube(ctx.wood, pts, radii, 4 if lod == 0 else 3, caps=False)

    Lf = min(S["fmax"], max(S["fmin"], S["fl"] * L + 0.35))
    Wf = Lf * S["faspect"]
    spacing = max(0.09, Lf * S["fsp"] / dens)
    k = 3 if lod == 0 else 2
    rolls = S["rolls"]
    t = 0.08
    idx = 0
    while True:
        te = t + Lf / L
        pts = [bpt(p0, d, L, droop, t + (te - t) * i / (k - 1)) for i in range(k)]
        base_roll = (h01(T, b, idx, 45) - 0.5) * 1.0
        for pi, roll in enumerate(rolls):
            keep = 1.0 if pi == 0 else min(1.0, max(0.0, (dens - 0.25) / 0.75))
            if h01(T, b, idx, pi, 41) >= keep:
                continue
            jit = 0.9 + 0.2 * h01(T, b, idx, pi, 42)
            rj = base_roll + roll * (0.85 + 0.3 * h01(T, b, idx, pi, 43))
            ribbon(ctx, pts, 0.5 * Wf * jit, rj, flip=h01(T, b, idx, pi, 44) < 0.5)
        idx += 1
        if t + Lf / L >= 1.0 + 0.12 * Lf / L:
            break
        t += spacing / L
        if t > 1.0:
            break

    # hanging curtains: whole fronds dropping from the branch, break up the whorl tiers
    for ci, ct in enumerate(S["curt_t"]):
        if h01(T, b, ci, 50) > S["curt_p"] * min(1.0, dens):
            continue
        base = bpt(p0, d, L, droop, ct)
        Lc = Lf * S["curt_len"] * (0.85 + 0.3 * h01(T, b, ci, 51))
        out = unit((d[0], d[1], 0.0))
        dn = unit((out[0] * 0.3, out[1] * 0.3, -1.0))
        pts = [add(base, mul(dn, Lc * i / (k - 1))) for i in range(k)]
        az = math.atan2(d[1], d[0]) + math.pi * 0.5 + (h01(T, b, ci, 52) - 0.5) * 1.3
        ribbon(ctx, pts, 0.5 * Lc * S["faspect"], 0.0, side0=(math.cos(az), math.sin(az), 0.0),
               flip=h01(T, b, ci, 53) < 0.5)


def grow_whorled(S, V, ctx):
    T = ctx.T
    H = V["H"]
    R0 = V["R0"]
    lod = ctx.lod
    n = S["tnseg"] if lod == 0 else max(4, S["tnseg"] // 3)
    pts = []
    for i in range(n + 1):
        z = H * i / n
        x, y = trunk_xy(S, H, z)
        pts.append((x, y, z))
    radii = [max(0.02, R0 * (1.0 - S["taper"] * (i / n))) for i in range(n + 1)]
    tube(ctx.wood, pts, radii, (14, 8, 6)[lod], flare=make_flare(pts, S["flare"]) if S["flare"] > 0 else None)

    zb = S["zb"]
    ztop = H * 0.985
    span = ztop - zb
    z = zb
    i = 0
    while z < ztop - 0.4:
        k = S["k"][0] + int(h01(T, i, 700) * (S["k"][1] - S["k"][0] + 1))
        for j in range(k):
            az = TAU * j / k + GOLD * i + 0.35 * (h01(T, i, j, 710) - 0.5)
            zz = min(ztop - 0.3, max(zb * 0.8, z + (h01(T, i, j, 711) - 0.5) * 0.3 * S["spacing"]))
            ux = min(1.0, max(0.0, (zz - zb) / span))
            L = (S["Rfac"] * H * V["cs"] * (1.0 - ux) ** S["lp"] + 0.3) * (0.85 + 0.3 * h01(T, i, j, 730))
            el = S["el0"] + (S["el1"] - S["el0"]) * ux ** 1.6 + (h01(T, i, j, 720) - 0.5) * 0.12
            droop = -(S["dr0"] + (S["dr1"] - S["dr0"]) * ux)
            dvec = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
            tip_z = zz + L * (dvec[2] + droop)
            if tip_z < 0.3:
                droop = -((zz + L * dvec[2] - 0.3) / L)
            x, y = trunk_xy(S, H, zz)
            r0 = max(0.008, 0.035 + 0.010 * L)
            frond_branch(ctx, S, V, (x, y, zz), dvec, L, r0, droop)
        z += S["spacing"] * (0.8 + 0.4 * h01(T, i, 701))
        i += 1

    # leader: upward fronds around the top so the spire is closed
    k = 2 if lod else 3
    tl = S["topl"]
    for q in range(S["topn"]):
        az = TAU * q / S["topn"] + 0.5 * h01(T, q, 760)
        dd = unit((math.cos(az) * 0.30, math.sin(az) * 0.30, 1.0))
        x, y = trunk_xy(S, H, H - tl * 0.9)
        base = (x, y, H - tl * 0.9)
        pts = [add(base, mul(dd, tl * i / (k - 1))) for i in range(k)]
        ribbon(ctx, pts, 0.5 * tl * S["faspect"], 0.0, side0=(-math.sin(az), math.cos(az), 0.0))
        ribbon(ctx, pts, 0.5 * tl * S["faspect"], 0.0, side0=(math.cos(az), math.sin(az), 0.0))


# ---------------------------------------------------------------- pine / krummholz (branch hierarchy + plumes)

def spray(ctx, S, p, dvec, ln, k):
    """Needle plume: two crossed cards, base on the twig at p, running along dvec."""
    d = unit(dvec)
    e = rdir(ctx.T, k, 901)
    a1 = cross(d, e)
    if length(a1) < 1e-6:
        a1 = cross(d, (1.0, 0.0, 0.0))
    a1 = unit(a1)
    a2 = cross(d, a1)
    w = ln * S["sw"] * 0.5
    base = sub(p, mul(d, 0.04 * ln))
    far = add(base, mul(d, ln))
    flip = h01(ctx.T, k, 902) < 0.5
    u0, u1 = (1.0, 0.0) if flip else (0.0, 1.0)
    planes = (a1, a2) if ctx.density >= 0.55 else (a1,)
    for a in planes:
        i0 = ctx.leaf.v(sub(base, mul(a, w)))
        i1 = ctx.leaf.v(add(base, mul(a, w)))
        i2 = ctx.leaf.v(add(far, mul(a, w)))
        i3 = ctx.leaf.v(sub(far, mul(a, w)))
        ctx.leaf.quad(i0, i1, i2, i3, ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)))


def spray_dir(ctx, S, tan, k, fan):
    dv = unit(lerp(tan, rdir(ctx.T, k, 903), fan))
    dv = (dv[0], dv[1], dv[2] + S["upb"])
    if S["wmix"] > 0:
        dv = lerp(unit(dv), S["wind"], S["wsp"])
    return unit(dv)


def twig_sprays(ctx, S, p0, d, L, droop, t0, t1, spacing, tip_n, b):
    n = max(1, int(round((t1 - t0) * L / spacing * ctx.density)))
    for a in range(n):
        t = t0 + (t1 - t0) * (a + h01(ctx.T, b, a, 60)) / n
        p = bpt(p0, d, L, droop, t)
        tan = btan(d, droop, t)
        ctx.n += 1
        ln = S["sl"] * (0.75 + 0.5 * h01(ctx.T, b, a, 61))
        spray(ctx, S, p, spray_dir(ctx, S, tan, ctx.n, S["fan"]), ln, ctx.n)
    if tip_n > 0:
        tip = bpt(p0, d, L, droop, 1.0)
        tan = btan(d, droop, 1.0)
        nt = max(1, int(round(tip_n * min(1.0, ctx.density))))
        for q in range(nt):
            ctx.n += 1
            ln = S["sl"] * (0.95 + 0.3 * h01(ctx.T, b, q, 62))
            spray(ctx, S, tip, spray_dir(ctx, S, tan, ctx.n, 0.45), ln, ctx.n)


def child_dir(T, ang, psi, up_bias):
    ref = (0.0, 0.0, 1.0) if abs(T[2]) < 0.9 else (1.0, 0.0, 0.0)
    side = unit(cross(T, ref))
    perp = cross(T, side)
    lat = add(mul(side, math.cos(psi)), mul(perp, math.sin(psi)))
    d = add(mul(T, math.cos(ang)), mul(lat, math.sin(ang)))
    return unit((d[0], d[1], d[2] + up_bias))


def pine_branch(ctx, S, p0, d, L, r0, depth, droop):
    ctx.n += 1
    b = ctx.n
    T = ctx.T
    lod = ctx.lod
    npts = (6, 4, 3)[depth - 1]
    wob = S["wob"]
    pts = []
    for i in range(npts):
        t = i / (npts - 1)
        q = bpt(p0, d, L, droop, t)
        if i > 0 and wob > 0:
            q = (q[0] + (h01(T, b, i, 10) - 0.5) * wob * L * t,
                 q[1] + (h01(T, b, i, 11) - 0.5) * wob * L * t,
                 q[2] + (h01(T, b, i, 12) - 0.5) * wob * L * t * 0.7)
        pts.append(q)
    radii = [max(0.0045, r0 * (1.0 - 0.8 * i / (npts - 1))) for i in range(npts)]
    # wood LOD: LOD0 everything, LOD1 limbs + secondaries (3 sides), LOD2 limbs only
    if lod == 0 or (lod == 1 and depth <= 2) or (lod == 2 and depth == 1):
        segs = (6, 4, 3)[depth - 1] if lod == 0 else 3
        tube(ctx.wood, pts, radii, segs, caps=(lod == 0))

    twig_sprays(ctx, S, p0, d, L, droop, S["t_out"][depth - 1], 1.0, S["spc"][depth - 1],
                S["tip_n"][depth - 1], b)

    if depth < 3:
        nk = S["kids"][depth - 1]
        nk = max(1, int(round(nk * min(1.0, ctx.density ** 0.5)))) if lod else nk
        for q in range(nk):
            t = S["k0"][depth - 1] + (0.95 - S["k0"][depth - 1]) * (q + 0.5 + 0.35 * (h01(T, b, q, 80) - 0.5)) / nk
            pc = bpt(p0, d, L, droop, t)
            tan = btan(d, droop, t)
            ang = S["kang"][depth - 1] + (h01(T, b, q, 81) - 0.5) * 0.5
            psi = GOLD * q + TAU * 0.3 * h01(T, b, q, 82)
            dn = child_dir(tan, ang, psi, S["kup"][depth - 1])
            if S["wmix"] > 0:
                dn = unit(lerp(dn, S["wind"], S["wmix"]))
            Lc = max(0.3, L * S["kf"][depth - 1] * (1.0 - 0.45 * t) * (0.8 + 0.4 * h01(T, b, q, 83)))
            rc = max(0.005, r0 * (1.0 - 0.8 * t) * 0.55)
            pine_branch(ctx, S, pc, dn, Lc, rc, depth + 1, droop * 0.5)


def grow_pine(S, V, ctx):
    T = ctx.T
    H = V["H"]
    R0 = V["R0"]
    lod = ctx.lod
    n = S["tnseg"] if lod == 0 else max(4, S["tnseg"] // 3)
    ph = TAU * h01(T, 5)
    pts = []
    if S["krum"]:
        # contorted trunk: random-walk heading, pushed progressively toward the lee (+X)
        d = unit((0.15, 0.0, 1.0))
        step = H * 1.25 / n
        pts.append((0.0, 0.0, 0.0))
        for i in range(n):
            bend = 0.25 + 0.55 * i / n
            d = unit(add(add(d, mul(S["wind"], bend)), mul(rdir(T, i, 5), 0.60)))
            if d[2] < 0.12:
                d = unit((d[0], d[1], 0.12))
            pts.append(add(pts[-1], mul(d, step)))
    else:
        for i in range(n + 1):
            t = i / n
            x = S["sway"] * H * math.sin(2.3 * t + ph) * t
            y = S["sway"] * H * math.sin(1.9 * t + 2.0 * ph) * t
            pts.append((x, y, H * t))
    radii = [max(0.025, R0 * (1.0 - S["taper"] * (i / n))) for i in range(n + 1)]
    tube(ctx.wood, pts, radii, (14, 8, 6)[lod], flare=make_flare(pts, S["flare"]) if S["flare"] > 0 else None)

    def trunk_at(t):
        f = t * n
        i = min(n - 1, int(f))
        a = f - i
        return lerp(pts[i], pts[i + 1], a)

    # dead stubs on the bole (windward side only for krummholz)
    if lod == 0:
        for q in range(S["stubs"]):
            t = 0.08 + (S["cb"] - 0.08) * (q + h01(T, q, 770)) / max(1, S["stubs"])
            base = trunk_at(t)
            az = TAU * h01(T, q, 771) if not S["krum"] else math.pi + (h01(T, q, 771) - 0.5) * 2.2
            el = 0.15 + 0.5 * h01(T, q, 772) - (0.5 if not S["krum"] else 0.0) * 0.0
            dd = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
            sl = 0.2 + 0.25 * h01(T, q, 773)
            tube(ctx.wood, [base, add(base, mul(dd, sl))], [0.03, 0.012], 4, caps=False)

    zc = S["cb"]
    nl = S["limbs"]
    order = sorted(range(nl), key=lambda q: h01(T, q, 790))
    for jj in range(nl):
        u = (jj + 0.5) / nl
        t = zc + (0.97 - zc) * u ** S["up"]
        base = trunk_at(t)
        j = order[jj]
        if S["krum"]:
            az = (h01(T, j, 791) - 0.5) * 2.0 * S["azspan"]
        else:
            az = GOLD * jj + 0.5 * (h01(T, j, 791) - 0.5)
        el = S["el"][0] + (S["el"][1] - S["el"][0]) * u + (h01(T, j, 792) - 0.5) * 0.25
        dvec = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
        if S["wmix"] > 0:
            dvec = unit(lerp(dvec, S["wind"], S["wmix"] * 0.6))
        L = max(0.6, S["Lfac"] * H * V["cs"] * (1.0 - S["Ltaper"] * u) * (0.8 + 0.4 * h01(T, j, 793)))
        r0 = max(0.02, 0.012 * L + 0.02)
        pine_branch(ctx, S, base, dvec, L, r0, 1, S["lcurve"])

    # leader tuft so the top is closed
    top = pts[-1]
    for q in range(S["topn"]):
        ctx.n += 1
        dd = unit((math.cos(TAU * q / S["topn"]) * 0.55, math.sin(TAU * q / S["topn"]) * 0.55, 1.0))
        if S["wmix"] > 0:
            dd = unit(lerp(dd, S["wind"], S["wsp"]))
        spray(ctx, S, sub(top, mul(dd, 0.3)), dd, S["sl"] * 1.1, ctx.n)


def build_geometry(S, V, lod, want):
    density = 1.0 if lod == 0 else max(0.15, 1.0 * want / max(1.0, S["want"]))
    ctx = None
    tb = tl = 0
    best = None
    for _ in range(9):
        ctx = Ctx(V["_T"], density, lod)
        if S["kind"] == "whorl":
            grow_whorled(S, V, ctx)
        else:
            grow_pine(S, V, ctx)
        tb = tri_count(ctx.wood)
        tl = tri_count(ctx.leaf)
        tot = tb + tl
        err = abs(tot - want)
        if best is None or err < best[0]:
            best = (err, density, ctx, tb, tl)
        if err <= 0.07 * want:
            break
        density *= min(3.0, max(0.3, (want - tb) / max(1.0, tl)))
        density = min(8.0, max(0.05, density))
    _, density, ctx, tb, tl = best
    return ctx, tb, tl, density


# ---------------------------------------------------------------- species table

_COMMON = dict(lift=1.3, sw=0.505, upb=0.0, wmix=0.0, wsp=0.0, wind=(1.0, 0.0, 0.15), krum=False, stubs=9, sway=0.012)

SPECIES = [
    dict(_COMMON, id="pine_open", T=21, kind="pine", tex="pine", bark=PINE_BARK, bark_nor=PINE_BARK_NOR,
         want=26000, tri=(20000, 80000), cov_min=0.45, pv=(512, 640),
         tnseg=14, taper=0.52, flare=0.35, sway=0.025, cb=0.56, limbs=10, up=0.85, Lfac=0.30, Ltaper=0.5,
         el=(0.30, 0.95), lcurve=0.20, kids=[6, 4], k0=[0.30, 0.30], kf=[0.45, 0.50], kang=[1.15, 0.95],
         kup=[0.30, 0.18], t_out=[0.62, 0.38, 0.12], spc=[0.40, 0.32, 0.28], tip_n=[0, 2, 3],
         sl=0.80, fan=0.60, wob=0.06, topn=7, azspan=0.0),
    dict(_COMMON, id="spruce_conifer", T=24, kind="whorl", tex="fir", bark=FIR_BARK, bark_nor=FIR_BARK_NOR,
         lift=1.0, want=34000, tri=(20000, 80000), cov_min=0.75, pv=(512, 640),
         tnseg=14, taper=0.90, flare=0.30, zb=1.3, spacing=0.40, k=(5, 7), Rfac=0.125, lp=0.9,
         el0=-0.04, el1=0.50, dr0=0.40, dr1=0.10, fmin=0.6, fmax=1.15, fl=0.28, fsp=0.50, faspect=0.80,
         rolls=(0.0, 0.85, -0.85), curt_t=(0.40, 0.68, 0.95), curt_p=0.9, curt_len=1.0, topn=6, topl=1.2,
         wood_lod1=True, wood_lod2=False),
    dict(_COMMON, id="larch_sparse", T=25, kind="whorl", tex="larch", bark=FIR_BARK, bark_nor=FIR_BARK_NOR,
         lift=1.0, want=38000, tri=(20000, 80000), cov_min=0.0, pv=(512, 640),
         tnseg=14, taper=0.85, flare=0.25, zb=2.0, spacing=0.42, k=(5, 7), Rfac=0.15, lp=0.95,
         el0=0.04, el1=0.55, dr0=0.16, dr1=0.06, fmin=0.55, fmax=1.05, fl=0.26, fsp=0.45, faspect=0.80,
         rolls=(0.0, 0.70, -0.70), curt_t=(0.45, 0.75, 1.0), curt_p=0.8, curt_len=0.9, topn=5, topl=1.2,
         wood_lod1=True, wood_lod2=False),
    dict(_COMMON, id="krummholz_pine", T=26, kind="pine", tex="pine", bark=PINE_BARK, bark_nor=PINE_BARK_NOR,
         want=14000, tri=(5000, 20000), cov_min=0.0, pv=(512, 512),
         tnseg=9, taper=0.45, flare=0.0, krum=True, lean=0.95, cb=0.10, limbs=7, up=0.9, Lfac=0.85, Ltaper=0.3,
         el=(-0.05, 0.35), lcurve=0.06, kids=[6, 4], k0=[0.22, 0.25], kf=[0.45, 0.50], kang=[1.1, 0.95],
         kup=[0.20, 0.10], t_out=[0.30, 0.15, 0.05], spc=[0.24, 0.20, 0.18], tip_n=[0, 3, 3],
         sl=0.45, fan=0.50, wob=0.18, topn=5, azspan=1.0, wmix=0.5, wsp=0.55, wind=(1.0, 0.0, 0.10), stubs=7),
]

# per-species variants: H, R0 (trunk base radius, m), leaf tint, lum target (needle mean luminance), bark tint,
# cs = crown size factor
VARIANTS = {
    "pine_open": [
        dict(H=16.0, R0=0.30, leaf=(0.80, 1.00, 0.90), lum=0.30, bark=(0.82, 0.76, 0.68), cs=0.95),
        dict(H=20.0, R0=0.36, leaf=(0.70, 0.95, 0.80), lum=0.28, bark=(0.78, 0.70, 0.60), cs=1.00),
        dict(H=24.0, R0=0.42, leaf=(0.85, 1.00, 0.75), lum=0.32, bark=(0.95, 0.78, 0.48), cs=1.05),
    ],
    "spruce_conifer": [
        dict(H=22.0, R0=0.45, leaf=(0.40, 0.62, 0.50), lum=0.26, bark=(0.42, 0.36, 0.30), cs=0.92),
        dict(H=28.0, R0=0.50, leaf=(0.35, 0.60, 0.40), lum=0.28, bark=(0.38, 0.33, 0.28), cs=1.00),
        dict(H=32.0, R0=0.55, leaf=(0.48, 0.64, 0.56), lum=0.24, bark=(0.46, 0.42, 0.36), cs=1.00),
    ],
    "larch_sparse": [
        dict(H=14.0, R0=0.30, leaf=(0.85, 1.00, 0.45), lum=0.33, bark=(0.50, 0.46, 0.40), cs=0.95),
        dict(H=17.0, R0=0.34, leaf=(0.78, 0.96, 0.42), lum=0.34, bark=(0.46, 0.42, 0.36), cs=1.00),
        dict(H=20.0, R0=0.38, leaf=(0.92, 1.00, 0.50), lum=0.32, bark=(0.52, 0.48, 0.42), cs=1.05),
    ],
    "krummholz_pine": [
        dict(H=1.8, R0=0.09, leaf=(0.45, 0.62, 0.45), lum=0.26, bark=(0.42, 0.38, 0.34), cs=1.00),
        dict(H=2.2, R0=0.10, leaf=(0.38, 0.55, 0.40), lum=0.28, bark=(0.40, 0.36, 0.32), cs=1.05),
        dict(H=2.6, R0=0.12, leaf=(0.50, 0.60, 0.42), lum=0.30, bark=(0.48, 0.44, 0.38), cs=1.10),
    ],
}


# ---------------------------------------------------------------- image helpers

def load_img(path, noncolor=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


def pixels_td(path, size=None):
    """Top-down float32 RGBA (H, W, 4). Optionally scaled to size x size."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=False)
    if size is not None and tuple(img.size) != (size, size):
        img.scale(size, size)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)[::-1].copy()


def write_png(arr_td, path, name):
    """arr_td is top-down (H, W, 4) float."""
    h, w = arr_td.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr_td[::-1], dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def box_mean(a, k):
    p = k // 2
    ap = np.pad(a, p, mode="constant")
    c = np.cumsum(np.cumsum(ap, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / float(k * k)


def resample(a, oh, ow):
    h, w = a.shape[:2]
    ys = (np.arange(oh) + 0.5) * h / oh - 0.5
    xs = (np.arange(ow) + 0.5) * w / ow - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, h - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    x1 = np.clip(x0 + 1, 0, w - 1)
    fy = np.clip(ys - np.floor(ys), 0.0, 1.0)
    fx = np.clip(xs - np.floor(xs), 0.0, 1.0)
    shp = (oh, ow) + (1,) * (a.ndim - 2)
    fy = fy.reshape(oh, 1, *([1] * (a.ndim - 2)))
    fx = fx.reshape(1, ow, *([1] * (a.ndim - 2)))
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


# ---------------------------------------------------------------- needle textures

PINE_CROP = (28, 468, 30, 252)   # y0, y1, x0, x1 in the 1024 px pine twig sheet (top-down)


def spray_extract(m):
    """m: crop of the twig alpha, white needle lines on a black blob inside a white background.
    Needles = white pixels NOT connected to the white background that touches the crop border."""
    white = m > 0.5
    bg = np.zeros_like(white)
    bg[0, :] = white[0, :]
    bg[-1, :] = white[-1, :]
    bg[:, 0] = white[:, 0]
    bg[:, -1] = white[:, -1]
    for _ in range(2000):
        g = bg.copy()
        g[1:, :] |= bg[:-1, :]
        g[:-1, :] |= bg[1:, :]
        g[:, 1:] |= bg[:, :-1]
        g[:, :-1] |= bg[:, 1:]
        g &= white
        if (g == bg).all():
            break
        bg = g
    return (white & ~bg).astype(np.float32)


def splat(A, C, segs, cols, rad):
    """Draw line segments (n,4: x0,y0,x1,y1 in canvas px) into alpha A and colour C. Later calls overwrite."""
    H, W = A.shape
    offs = [(ox, oy) for ox in range(-rad, rad + 1) for oy in range(-rad, rad + 1) if ox * ox + oy * oy <= rad * rad + 0.5]
    for s in range(0, len(segs), 1500):
        sg = segs[s:s + 1500]
        cl = cols[s:s + 1500]
        d = sg[:, 2:4] - sg[:, 0:2]
        steps = int(np.sqrt((d ** 2).sum(1)).max()) + 2
        t = np.linspace(0.0, 1.0, steps)[None, :, None]
        pts = sg[:, None, 0:2] + d[:, None, :] * t
        cc = np.broadcast_to(cl[:, None, :], (len(sg), steps, 3))
        for ox, oy in offs:
            xi = np.rint(pts[..., 0] + ox).astype(np.int64)
            yi = np.rint(pts[..., 1] + oy).astype(np.int64)
            ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
            A[yi[ok], xi[ok]] = 1.0
            C[yi[ok], xi[ok]] = cc[ok]


def fir_palette():
    fd = pixels_td(FIR_TWIG)[..., :3]
    reg = fd[470:800, 330:650].reshape(-1, 3)
    lum = reg @ LUM_W
    lo, hi = np.quantile(lum, 0.08), np.quantile(lum, 0.45)
    sel = (lum >= lo) & (lum <= hi)
    return reg[sel].mean(axis=0)


def draw_frond(kind, T):
    """Herringbone needle spray, base at the bottom, tip at the top. Returns (rgb (H,W,3), alpha (H,W))."""
    W, Hh, ss = 768, 1024, 2
    Wc, Hc = W * ss, Hh * ss
    A = np.zeros((Hc, Wc), np.float32)
    C = np.zeros((Hc, Wc, 3), np.float32)
    pal = fir_palette().astype(np.float32)
    cx = Wc * 0.5
    yb = Hc * 0.975
    yt = Hc * 0.03

    if kind == "fir":
        nb, bang, shapepow = 24, 1.00, 0.75
        needle_len, needle_step, nper, sub_ev = 26.0, 7.0, 3, 0.24
        thick = 2
        reach = 0.47
    else:  # larch: wide-angle sparse twigs, each carrying rosettes of soft needles
        nb, bang, shapepow = 26, 1.15, 0.9
        needle_len, needle_step, nper, sub_ev = 30.0, 26.0, 7, 0.0
        thick = 1
        reach = 0.46

    def shape(s):
        f = np.minimum(1.0, s / 0.12) ** 0.5 * np.maximum(0.0, 1.0 - s ** 2.5) ** shapepow
        return f

    tw_segs = []
    tw_cols = []
    nd_segs = []
    nd_cols = []
    wood = pal * np.array([0.80, 0.68, 0.52], np.float32)

    # rachis
    tw_segs.append([cx, yb, cx, yt])
    tw_cols.append(wood)

    def needles(px, py, tx, ty, s_tip, key):
        """Needles leave a twig point at +-(40..85 deg) from the twig direction plus one forward."""
        for q in range(nper):
            h1 = float(hn(T, key, q, 1))
            h2 = float(hn(T, key, q, 2))
            side = 1.0 if (q % 2 == 0) else -1.0
            if kind == "fir":
                a = side * (0.70 + 0.8 * h1) if q < nper - 1 else (h1 - 0.5) * 0.7
            else:
                a = (q / (nper - 1) - 0.5) * 2.6 + (h1 - 0.5) * 0.4
            ca, sa = math.cos(a), math.sin(a)
            dx, dy = tx * ca - ty * sa, tx * sa + ty * ca
            ln = needle_len * ss * (0.75 + 0.5 * h2)
            nd_segs.append([px, py, px + dx * ln, py + dy * ln])
            shade = (0.78 + 0.30 * s_tip) * (0.88 + 0.24 * float(hn(T, key, q, 3)))
            nd_cols.append(np.clip(pal * shade, 0, 1))

    for side in (-1.0, 1.0):
        for i in range(nb):
            s = 0.05 + 0.93 * (i + (0.5 if side > 0 else 0.0) + 0.25) / (nb + 0.5)
            h = float(hn(T, i, int(side) + 2, 20))
            if float(hn(T, i, int(side) + 2, 21)) < 0.10:
                continue
            lat = Wc * reach * float(shape(s)) * (0.62 + 0.5 * h)
            ang = bang + 0.5 * (h - 0.5)
            ln = lat / math.sin(ang)
            fwd = ln * math.cos(ang)
            sx, sy = cx, yb - s * (yb - yt)
            ex, ey = sx + side * lat, sy - fwd
            dx, dy = side * math.sin(ang), -math.cos(ang)
            tw_segs.append([sx, sy, ex, ey])
            tw_cols.append(wood)
            npts = max(2, int(ln / (needle_step * ss)))
            for j in range(npts + 1):
                u = j / npts
                needles(sx + (ex - sx) * u, sy + (ey - sy) * u, dx, dy, 0.25 + 0.75 * u, i * 977 + j * 13 + int(side + 2))
            if sub_ev > 0:
                k = 1
                while k * sub_ev < 0.95:
                    u = k * sub_ev
                    a2 = math.atan2(dy, dx) + (0.85 if (k % 2) else -0.85)
                    sdx, sdy = math.cos(a2), math.sin(a2)
                    sl = ln * 0.36 * (1.0 - 0.55 * u)
                    bx, by = sx + (ex - sx) * u, sy + (ey - sy) * u
                    tw_segs.append([bx, by, bx + sdx * sl, by + sdy * sl])
                    tw_cols.append(wood)
                    m = max(2, int(sl / (needle_step * ss)))
                    for j in range(m + 1):
                        uu = j / m
                        needles(bx + sdx * sl * uu, by + sdy * sl * uu, sdx, sdy, 0.35 + 0.65 * uu,
                                i * 4001 + k * 131 + j * 7 + int(side + 2))
                    k += 1
            else:
                # larch: rosette at the twig tip
                for q in range(2):
                    needles(ex, ey, dx, dy, 1.0, i * 5003 + q * 17 + int(side + 2))

    splat(A, C, np.array(tw_segs, np.float64), np.array(tw_cols, np.float32), 1)
    splat(A, C, np.array(nd_segs, np.float64), np.array(nd_cols, np.float32), thick)

    # downsample 2x with premultiplied colour
    pre = C * A[..., None]
    a_ds = A.reshape(Hh, ss, W, ss).mean(axis=(1, 3))
    c_ds = pre.reshape(Hh, ss, W, ss, 3).mean(axis=(1, 3))
    rgb = np.where(a_ds[..., None] > 1e-3, c_ds / np.maximum(a_ds[..., None], 1e-3), pal.reshape(1, 1, 3))
    # light morphological closing: fill the pin-holes between needles with shadowed colour so the
    # frond reads as a dense bough with a ragged edge instead of a see-through scribble
    m0 = (a_ds > 0.5).astype(np.float32)
    if CLOSE_R == 0:
        return rgb.astype(np.float32), a_ds.astype(np.float32)
    dil = (box_mean(m0, 2 * CLOSE_R + 1) > 0.0).astype(np.float32)
    ero = box_mean(dil, 2 * CLOSE_R + 1) > 0.999
    added = ero & (m0 < 0.5)
    rgb = np.where(added[..., None], pal.reshape(1, 1, 3) * 0.55, rgb)
    a_ds = np.where(added, 1.0, a_ds)
    return rgb.astype(np.float32), a_ds.astype(np.float32)


CLOSE_R = 0
_BASE_CACHE = {}


def base_needles(kind):
    """Un-tinted needle colour (H,W,3) and alpha (H,W), top-down."""
    if kind in _BASE_CACHE:
        return _BASE_CACHE[kind]
    if kind == "pine":
        al = pixels_td(PINE_ALPHA)
        src = al[..., 3] if al[..., 3].min() < 0.99 else al[..., 0]
        tw = pixels_td(PINE_TWIG)[..., :3]
        y0, y1, x0, x1 = PINE_CROP
        m = spray_extract(np.clip(src[y0:y1, x0:x1], 0.0, 1.0))
        mm = resample(m, 1024, 512)
        cc = resample(tw[y0:y1, x0:x1], 1024, 512)
        # thicken the thin needle lines so they survive mips and read at distance
        mm = np.maximum(mm, (box_mean(mm, 3) > 0.22).astype(np.float32))
        mean = cc[mm > 0.5].mean(axis=0) if (mm > 0.5).any() else cc.reshape(-1, 3).mean(axis=0)
        cc = np.where(mm[..., None] > 0.05, cc, mean.reshape(1, 1, 3))
        out = (cc.astype(np.float32), mm.astype(np.float32))
    else:
        out = draw_frond(kind, {"fir": 31, "larch": 37}[kind])
    _BASE_CACHE[kind] = out
    return out


def make_textures(S, V, name):
    rgb, mask = base_needles(S["tex"])
    sel = mask > 0.5
    tint = np.array(V["leaf"], dtype=np.float32).reshape(1, 1, 3)
    col = rgb * tint
    lum = col @ LUM_W
    m = float(lum[sel].mean()) if sel.any() else float(lum.mean())
    lum_target = min(0.39, V["lum"] * S["lift"])
    col = np.clip(col * (lum_target / max(m, 1e-4)), 0.0, 1.0)
    measured = float((col @ LUM_W)[sel].mean()) if sel.any() else float((col @ LUM_W).mean())
    h, w = mask.shape
    leaf = np.empty((h, w, 4), dtype=np.float32)
    leaf[..., :3] = col
    leaf[..., 3] = mask
    leaf_path = os.path.join(TEX, name + "_needles.png")
    write_png(leaf, leaf_path, name + "_needles")

    bsrc = pixels_td(S["bark"], 1024)[..., :3]
    bt = np.array(V["bark"], dtype=np.float32).reshape(1, 1, 3)
    bark = np.ones((1024, 1024, 4), dtype=np.float32)
    bark[..., :3] = np.clip(bsrc * bt * 1.2, 0.0, 1.0)
    bark_path = os.path.join(TEX, name + "_bark.png")
    write_png(bark, bark_path, name + "_bark")
    return leaf_path, bark_path, measured, float(sel.mean())


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


def build_mats(S, leaf_png, bark_png):
    bark_img = load_img(bark_png)
    nor_img = load_img(S["bark_nor"], noncolor=True)
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
    idx_bark = len(bark.verts)
    leaf_zmin = min(p[2] for p in verts[idx_bark:]) if leaf.verts else 0.0

    scale = 0.5 * H
    wind = np.zeros((len(verts), 4), dtype=np.float32)
    for i, (x, y, z) in enumerate(verts):
        dd = min(1.0, math.sqrt(x * x + y * y + z * z) / scale)
        wind[i, 0] = dd if i < idx_bark else 0.7 + 0.3 * dd
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

    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["leaf_zmin"] = float(leaf_zmin)
    return ob


def clean_mesh(ob):
    """Merge doubles, drop degenerate faces and loose verts, recalc normals. Keeps WindWeight."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bad = [f for f in bm.faces if f.calc_area() < 1e-10]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    ob.data.validate(verbose=False)
    if "WindWeight" not in ob.data.color_attributes:
        raise RuntimeError("WindWeight lost in clean of %s" % ob.name)


def shade_leaves(ob):
    """Smooth bark; point leaf-card normals away from the crown centre so the tree shades as one volume."""
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    nl = len(me.loops)
    nv = len(me.vertices)
    vco = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get("co", vco)
    vco = vco.reshape(nv, 3)
    vidx = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vidx)
    npoly = len(me.polygons)
    midx = np.empty(npoly, np.int32)
    me.polygons.foreach_get("material_index", midx)
    ltot = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_total", ltot)
    lmat = np.repeat(midx, ltot)
    cur = np.empty(nl * 3, np.float32)
    me.corner_normals.foreach_get("vector", cur)
    cur = cur.reshape(nl, 3)
    leafv = np.unique(vidx[lmat == 1])
    if len(leafv) == 0:
        return
    c = vco[leafv].mean(axis=0)
    p = vco[vidx]
    nrm = p - c
    nrm[:, 2] *= LEAF_NZ
    ln = np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
    nrm = nrm / ln
    out = np.where((lmat == 1)[:, None], nrm, cur)
    me.normals_split_custom_set([tuple(float(x) for x in v) for v in out])


LEAF_NZ = 0.30


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


# ---------------------------------------------------------------- renders

def make_ground():
    me = bpy.data.meshes.new("PreviewGround")
    r = 400.0
    me.from_pydata([(-r, -r, 0.0), (r, -r, 0.0), (r, r, 0.0), (-r, r, 0.0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new("PreviewGroundMat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.10, 0.13, 0.05, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    me.materials.append(m)
    ob = bpy.data.objects.new("PreviewGround", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def render_view(path, res, loc, target=None, rot=None, lens=50.0, shift_y=0.0, ortho=None,
                transparent=False, ground=True, samples=40):
    scene = bpy.context.scene
    made = []
    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.sensor_fit = "VERTICAL"
    cam_d.sensor_height = 36.0
    cam_d.shift_y = shift_y
    if ortho:
        cam_d.type = "ORTHO"
        cam_d.ortho_scale = ortho
    else:
        cam_d.lens = lens
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    if rot is not None:
        cam.rotation_euler = rot
    else:
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    made.append(cam)

    sun_d = bpy.data.lights.new("PreviewSun", "SUN")
    sun_d.energy = 4.0
    sun = bpy.data.objects.new("PreviewSun", sun_d)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(35.0))
    made.append(sun)

    if ground:
        made.append(make_ground())

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.50, 0.64, 0.82, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = res[0]
    scene.render.resolution_y = res[1]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

    for o in made:
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if isinstance(data, bpy.types.Camera):
            bpy.data.cameras.remove(data)
        elif isinstance(data, bpy.types.Light):
            bpy.data.lights.remove(data)
        elif isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
    bpy.data.worlds.remove(world)
    scene.world = None
    scene.camera = None


def render_previews(S, name, dims, H0, leaf_zmin, ctr):
    H = dims[2]
    pv = S["pv"]
    half = 0.5 * max(dims[0], dims[1])
    cx, cy, cz = ctr[0], ctr[1], H * 0.48
    dist = 1.75 * max(H, 1.3 * half * 2.0)
    az = math.radians(35.0)
    loc = (cx + math.sin(az) * dist, cy - math.cos(az) * dist, cz + dist * 0.12)
    render_view(os.path.join(OUT, name + "_preview.png"), pv, loc, target=(cx, cy, cz), lens=50.0)

    # near view: camera 5 m outside the crown edge at eye height, aimed at the lower crown
    az2 = math.radians(25.0)
    d2 = half + 5.0
    tz = min(H * 0.6, leaf_zmin + max(2.5, 0.12 * H)) if leaf_zmin > 1.0 else min(H * 0.35, 5.0)
    render_view(os.path.join(OUT, name + "_near.png"), pv, (ctr[0] + math.sin(az2) * d2, ctr[1] - math.cos(az2) * d2, 1.7),
                target=(ctr[0], ctr[1], tz), lens=28.0, samples=40)

    # far view: camera 30 m away at eye height 1.7 m, level, framed by lens shift
    view_h = max(H, 1.2 * half * 2.0 * pv[1] / pv[0]) * 1.2
    lens = 36.0 * 30.0 / view_h
    shift = (H * 0.5 - 1.7) / view_h
    render_view(os.path.join(OUT, name + "_far.png"), pv, (ctr[0], -30.0, 1.7), rot=(math.radians(90.0), 0.0, 0.0),
                lens=lens, shift_y=shift, samples=40)


def hull_pixels(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return None

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
    return lo[:-1] + up[:-1]


def measure_coverage(ob, H, dims):
    """Silhouette alpha (ortho side view) over the crown rows; coverage = opaque px / convex-hull px."""
    res = 1024
    half = 0.5 * max(dims[0], dims[1])
    scale = 1.12 * max(H, 2.0 * half)
    cz = H * 0.5
    path = os.path.join(tempfile.gettempdir(), "conifer_cov_%d.png" % os.getpid())
    render_view(path, (res, res), (0.0, -60.0, cz), rot=(math.radians(90.0), 0.0, 0.0), ortho=scale,
                transparent=True, ground=False, samples=12)
    img = bpy.data.images.load(path)
    buf = np.empty(res * res * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    try:
        os.remove(path)
    except OSError:
        pass
    a = buf.reshape(res, res, 4)[::-1, :, 3] > 0.5
    zc = float(ob["leaf_zmin"])
    row_c = int(round(res * 0.5 - (zc - cz) / scale * res))
    row_c = min(res - 1, max(1, row_c))
    m = a[:row_c, :]
    rows = np.nonzero(m.any(axis=1))[0]
    if len(rows) < 4:
        return 0.0
    pts = []
    for r in rows:
        xs = np.nonzero(m[r])[0]
        pts.append((int(xs[0]), int(r)))
        pts.append((int(xs[-1]), int(r)))
    hull = hull_pixels(pts)
    if hull is None:
        return 0.0
    hp = np.array(hull, dtype=np.float64)
    ys = np.arange(rows[0], rows[-1] + 1)
    area = 0.0
    n = len(hp)
    for y in ys:
        xi = []
        for e in range(n):
            x0, y0 = hp[e]
            x1, y1 = hp[(e + 1) % n]
            if y0 == y1:
                continue
            if min(y0, y1) <= y <= max(y0, y1):
                xi.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
        if len(xi) >= 2:
            area += max(xi) - min(xi) + 1.0
    return float(m[rows[0]:rows[-1] + 1].sum()) / max(1.0, area)


# ---------------------------------------------------------------- per-variant pipeline

def author(S, V, name):
    reset_scene()
    leaf_png, bark_png, lum, mask_fill = make_textures(S, V, name)
    mats = build_mats(S, leaf_png, bark_png)

    ctx, tb, tl, density = build_geometry(S, V, 0, S["want"])
    ob0 = realise(name, ctx.wood, ctx.leaf, mats, V["H"])
    clean_mesh(ob0)
    shade_leaves(ob0)
    tris0 = mesh_tris(ob0.data)
    dims = tuple(ob0.dimensions)
    export_files(ob0, name)
    bb = [ob0.matrix_world @ Vector(c) for c in ob0.bound_box]
    ctr = (0.5 * (min(v.x for v in bb) + max(v.x for v in bb)), 0.5 * (min(v.y for v in bb) + max(v.y for v in bb)))
    render_previews(S, name, dims, V["H"], float(ob0["leaf_zmin"]), ctr)
    cov = measure_coverage(ob0, V["H"], dims)

    lods = []
    for lod, ratio in ((1, 0.30), (2, 0.08)):
        c, _, _, _ = build_geometry(S, V, lod, tris0 * ratio)
        ob = realise("%s_LOD%d" % (name, lod), c.wood, c.leaf, mats, V["H"])
        clean_mesh(ob)
        shade_leaves(ob)
        lods.append(mesh_tris(ob.data))
        export_files(ob, "%s_LOD%d" % (name, lod))

    return dict(name=name, sp=S["id"], tris0=tris0, tris1=lods[0], tris2=lods[1], dims=dims,
                bark_tris=tb, leaf_tris=tl, density=density, lum=lum, cov=cov, fill=mask_fill)


def write_readme(rows):
    lines = [
        "# conifer flora (authored)",
        "",
        "Generated by `Tools/Author-Flora-conifer.py` (headless Blender 5.2). Deterministic: "
        "the same seed and parameters reproduce the same geometry.",
        "",
        "Species (FloraCatalog): pine_open, spruce_conifer, larch_sparse, krummholz_pine. Three variants each "
        "(different branch layouts per variant; krummholz: low, wind-flagged to +X).",
        "",
        "Structure: real branch hierarchy, foliage always attached. spruce/larch = whorls of drooping primary "
        "branches carrying overlapping needle fronds (3 planes) plus hanging curtains between whorls. "
        "pine = bare bole, upswept limbs, secondaries, twigs; needle plumes run along the outer third of each "
        "limb and along the twigs. krummholz = contorted trunk, limbs and foliage on the lee side only.",
        "",
        "Conventions: metres. Blender scene is Z-up. GLB is Y-up (glTF spec). FBX is Blender-native Z-up. "
        "Origin at ground centre (min Z = 0, trunk base on XY origin).",
        "",
        "Vertex colour `WindWeight` (COLOR_0 in GLB): R = wind weight, 0 at trunk base to 1 at tips "
        "(needles 0.7 to 1.0). G = B = 0, A = 1.",
        "",
        "Material slots: `Bark` (opaque, tinted, normal map). `Leaves` (alpha-masked, two-sided). "
        "Alpha mode MASK, cutoff 0.5.",
        "",
        "LOD1 / LOD2 = regrown at ~30% / ~8% of the LOD0 triangle count (lower card density, simpler wood), then "
        "merge-by-distance and degenerate-face clean. Decimate collapse is not used: on disjoint cards it erodes "
        "them. Each LOD is a separate GLB and FBX.",
        "",
        "Previews: `<name>_preview.png` 3/4 view with ground plane; `<name>_far.png` 30 m, eye height 1.7 m, "
        "level camera (silhouette check). Cov = opaque fraction inside the convex hull of the crown in an "
        "orthographic side view (spruce >= 0.75, pine >= 0.45 required).",
        "",
        "## Files",
        "",
        "| Variant | Tris LOD0 | Tris LOD1 | Tris LOD2 | W x D x H (m) | Needle lum | Crown cov |",
        "|---------|-----------|-----------|-----------|---------------|-----------|-----------|",
    ]
    for r in rows:
        w, d, h = r["dims"]
        lines.append("| %s | %d | %d | %d | %.2f x %.2f x %.2f | %.3f | %.2f |" %
                     (r["name"], r["tris0"], r["tris1"], r["tris2"], w, d, h, r["lum"], r["cov"]))
    lines += [
        "",
        "## Provenance",
        "",
        "- Geometry: procedural, generated by `Tools/Author-Flora-conifer.py`. No third-party meshes.",
        "- Pine needle plume: Poly Haven pine_tree_01 twig alpha + diffuse (CC0), "
        "`ArtSource/PolyHaven/pine_tree_01/textures/`. One spray is gated, cropped and resampled to a 512x1024 "
        "card texture, lines thickened slightly.",
        "- Spruce / larch fronds: drawn procedurally (herringbone twigs, needles as line strokes). Needle colours "
        "are sampled from Poly Haven fir_tree_01 twig diffuse (CC0); that sheet has no alpha mask, so the mask "
        "is drawn.",
        "- Bark colour and normal: Poly Haven pine_tree_01 or fir_tree_01 bark (CC0). Read in place, "
        "baked tint into `<name>_bark.png`.",
        "- Poly Haven CC0 status per site licence. Not individually re-verified in this run.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def montage(rows):
    scratch = os.environ.get("CONIFER_SCRATCH")
    if not scratch:
        return
    os.makedirs(scratch, exist_ok=True)
    for sp in sorted({r["sp"] for r in rows}):
        tiles = []
        for r in rows:
            if r["sp"] != sp:
                continue
            for suf in ("_preview", "_near", "_far"):
                p = os.path.join(OUT, r["name"] + suf + ".png")
                if os.path.isfile(p):
                    tiles.append(pixels_td(p))
        if not tiles:
            continue
        hmax = max(t.shape[0] for t in tiles)
        cols = []
        for t in tiles:
            pad = np.ones((hmax - t.shape[0], t.shape[1], 4), np.float32)
            cols.append(np.concatenate([t, pad], axis=0))
        write_png(np.concatenate(cols, axis=1), os.path.join(scratch, sp + "_sheet.png"), sp + "_sheet")


def tex_debug():
    scratch = os.environ["CONIFER_SCRATCH"]
    os.makedirs(scratch, exist_ok=True)
    for kind in ("pine", "fir", "larch"):
        rgb, a = base_needles(kind)
        h, w = a.shape
        bg = np.array([0.55, 0.62, 0.75], np.float32).reshape(1, 1, 3)
        comp = rgb * a[..., None] + bg * (1.0 - a[..., None])
        amask = np.repeat(a[..., None], 3, axis=2)
        sheet = np.concatenate([comp, amask], axis=1)
        out = np.ones((h, w * 2, 4), np.float32)
        out[..., :3] = sheet
        write_png(out, os.path.join(scratch, "tex_%s.png" % kind), "tex_" + kind)
        print("TEX %s fill=%.3f" % (kind, float((a > 0.5).mean())))


def main():
    os.makedirs(TEX, exist_ok=True)
    if os.environ.get("CONIFER_TEXONLY"):
        tex_debug()
        return
    only = [x for x in os.environ.get("CONIFER_ONLY", "").split(",") if x]
    nv = int(os.environ.get("CONIFER_NV", "3"))
    rows = []
    fails = []
    for S in SPECIES:
        if only and S["id"] not in only:
            continue
        for vi, V0 in enumerate(VARIANTS[S["id"]][:nv]):
            name = "%s_v%02d" % (S["id"], vi + 1)
            V = dict(V0)
            V["_T"] = S["T"] * 100 + vi
            rec = author(S, V, name)
            rows.append(rec)
            w, d, h = rec["dims"]
            print("VARIANT %s tris0=%d tris1=%d tris2=%d dims=%.2fx%.2fx%.2f bark_tris=%d leaf_tris=%d "
                  "dens=%.2f lum=%.3f cov=%.3f fill=%.2f" %
                  (name, rec["tris0"], rec["tris1"], rec["tris2"], w, d, h,
                   rec["bark_tris"], rec["leaf_tris"], rec["density"], rec["lum"], rec["cov"], rec["fill"]))
            lo, hi = S["tri"]
            if not (lo <= rec["tris0"] <= hi):
                fails.append("%s tris0 %d outside %d-%d" % (name, rec["tris0"], lo, hi))
            if not (0.2 <= rec["lum"] <= 0.4):
                fails.append("%s needle lum %.3f outside 0.2-0.4" % (name, rec["lum"]))
            if rec["cov"] < S["cov_min"]:
                fails.append("%s crown coverage %.2f < %.2f" % (name, rec["cov"], S["cov_min"]))
            if not (0.18 * rec["tris0"] <= rec["tris1"] <= 0.45 * rec["tris0"]):
                fails.append("%s LOD1 %d not ~30%% of %d" % (name, rec["tris1"], rec["tris0"]))
            if not (0.03 * rec["tris0"] <= rec["tris2"] <= 0.14 * rec["tris0"]):
                fails.append("%s LOD2 %d not ~8%% of %d" % (name, rec["tris2"], rec["tris0"]))
    if not only:
        write_readme(rows)
    montage(rows)
    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d conifer variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
