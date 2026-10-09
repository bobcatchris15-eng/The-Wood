"""Author the rejected-flora redo batch headless. 3 variants each (poppy 3 colourways, knees 2).

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-redo.py

Writes only under ArtSource/Authored/Flora/redo/ (and textures/ beneath it).
Items: baldcypress (+ baldcypress_knees prop), lady_fern, alpine_tussock, shade_grass, horsetail,
       bracket_fungus, duckweed_mat, arctic_poppy, lupine.
Per variant: <id>_vNN.glb/.fbx, <id>_vNN_LOD1.glb/.fbx where LOD0 > 2000 tris,
<id>_vNN_preview.png, <id>_vNN_near.png (+ _far.png for the tree).

Every item is one combined mesh, several material slots, WindWeight vertex colour (R = weight, A = 1).
Textures are drawn procedurally with numpy (alpha-masked cards where foliage is a card); the baldcypress bark
is Poly Haven fir_tree_01 bark (CC0) tinted. Metres, Blender Z-up, origin at ground centre (min Z = 0);
bracket_fungus has its origin on the attach face (back plane y = 0, lowest tier at z = 0) and
duckweed_mat is a thin plane at z = 3 mm.
GLB is Y-up per glTF. FBX is Blender-native Z-up.
Randomness: h01()/hn() integer hash only. No RNG state.
Dev knobs (env): REDO_ONLY=<id,id>, REDO_NV=<n>, REDO_SCRATCH=<dir for montage sheets>, REDO_NORENDER=1.
"""

import json
import math
import os
import struct
import sys
import tempfile
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Vector

SEED = 9137
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
GOLD = 2.39996322972865332
DEG = math.pi / 180.0

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "redo")
TEX = os.path.join(OUT, "textures")
FIR_TEX = os.path.join(ART, "PolyHaven", "fir_tree_01", "textures")
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
    """Vectorised h01: keys may be scalars or integer arrays."""
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


def lf(a, b, t):
    return a + (b - a) * t


def rot_about(v, axis, ang):
    k = unit(axis)
    c = math.cos(ang)
    s = math.sin(ang)
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1.0 - c)))


def f3(r, g, b):
    return np.array([r, g, b], dtype=np.float32)


# ---------------------------------------------------------------- geometry primitives

class Part:
    def __init__(self, name, mat, fol=False):
        self.name = name
        self.mat = mat
        self.fol = fol
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


def tube(part, pts, radii, segs, flare=None, caps=True, vs=None, uscale=1.0):
    """Sweep a ring of `segs` verts along polyline pts. vs = per-ring V override."""
    n = len(pts)
    rings = []
    vv = [0.0]
    for i in range(1, n):
        ds = length(sub(pts[i], pts[i - 1]))
        rr = max(0.012, 0.5 * (radii[i] + radii[i - 1]))
        vv.append(vv[-1] + ds / (TAU * rr))
    if vs is not None:
        vv = vs
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
            u0 = j / segs * uscale
            u1 = (j + 1) / segs * uscale
            part.quad(rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j],
                      ((u0, vv[i]), (u1, vv[i]), (u1, vv[i + 1]), (u0, vv[i + 1])))
    if caps:
        for ring, idx in ((rings[0], 0), (rings[-1], n - 1)):
            c = part.v(pts[idx])
            for j in range(segs):
                j2 = (j + 1) % segs
                part.tri(c, ring[j], ring[j2], ((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)))


def side_vec(t, roll, side0):
    if side0 is not None:
        side = sub(side0, mul(t, dot(side0, t)))
        if length(side) < 1e-4:
            side = cross(t, (1.0, 0.0, 0.0))
        side = unit(side)
        return rot_about(side, t, roll) if roll != 0.0 else side
    side = cross(t, (0.0, 0.0, 1.0))
    if length(side) < 1e-4:
        side = cross(t, (1.0, 0.0, 0.0))
    side = unit(side)
    perp = unit(cross(side, t))
    return add(mul(side, math.cos(roll)), mul(perp, math.sin(roll)))


def strip(part, pts, hws, roll=0.0, u0=0.0, u1=1.0, side0=None, v0=0.0, v1=1.0, flip=False):
    """Strip along pts with per-point half widths. U across, V along."""
    n = len(pts)
    ring = []
    for i, p in enumerate(pts):
        if i == 0:
            t = unit(sub(pts[1], pts[0]))
        elif i == n - 1:
            t = unit(sub(pts[-1], pts[-2]))
        else:
            t = unit(sub(pts[i + 1], pts[i - 1]))
        w = side_vec(t, roll, side0)
        hw = hws[i] if isinstance(hws, (list, tuple)) else hws
        ring.append((part.v(sub(p, mul(w, hw))), part.v(add(p, mul(w, hw)))))
    if flip:
        u0, u1 = u1, u0
    for i in range(n - 1):
        va = v0 + (v1 - v0) * i / (n - 1)
        vb = v0 + (v1 - v0) * (i + 1) / (n - 1)
        part.quad(ring[i][0], ring[i][1], ring[i + 1][1], ring[i + 1][0],
                  ((u0, va), (u1, va), (u1, vb), (u0, vb)))


def grid(part, P, nu, nv, uv):
    """P(iu, iv) -> xyz; uv(iu, iv) -> (u, v). Quads over an (nu x nv) cell grid."""
    ids = [[part.v(P(iu, iv)) for iu in range(nu + 1)] for iv in range(nv + 1)]
    for iv in range(nv):
        for iu in range(nu):
            part.quad(ids[iv][iu], ids[iv][iu + 1], ids[iv + 1][iu + 1], ids[iv + 1][iu],
                      (uv(iu, iv), uv(iu + 1, iv), uv(iu + 1, iv + 1), uv(iu, iv + 1)))


def arc_path(p0, az, L, el0, bend, n, zmin=None):
    """Polyline of n segments; heading starts at elevation el0 (rad) and bends down by `bend` over the length."""
    pts = [p0]
    ca = math.cos(az)
    sa = math.sin(az)
    x, y, z = p0
    step = L / n
    for i in range(n):
        th = el0 - bend * (i + 0.5) / n
        hh = math.cos(th) * step
        x += ca * hh
        y += sa * hh
        z += math.sin(th) * step
        if zmin is not None and z < zmin:
            z = zmin
        pts.append((x, y, z))
    return pts


# ---------------------------------------------------------------- image helpers

def pixels_td(path, size=None):
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
    h, w = arr_td.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr_td[::-1], dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def save_tex(name, rgb, a=None):
    h, w = rgb.shape[:2]
    arr = np.ones((h, w, 4), dtype=np.float32)
    arr[..., :3] = np.clip(rgb, 0.0, 1.0)
    if a is not None:
        arr[..., 3] = a
    path = os.path.join(TEX, name + ".png")
    write_png(arr, path, name)
    return path


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
    fy = fy.reshape(oh, 1, *([1] * (a.ndim - 2)))
    fx = fx.reshape(1, ow, *([1] * (a.ndim - 2)))
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


def splat(A, C, segs, cols, rad):
    """Draw line segments (n,4: x0,y0,x1,y1 px) into alpha A and colour C. Later calls overwrite."""
    H, W = A.shape
    offs = [(ox, oy) for ox in range(-rad, rad + 1) for oy in range(-rad, rad + 1) if ox * ox + oy * oy <= rad * rad + 0.5]
    for s in range(0, len(segs), 1200):
        sg = segs[s:s + 1200]
        cl = cols[s:s + 1200]
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


class Canvas:
    """Supersampled alpha+colour canvas, top-down pixel coordinates (supersampled px)."""

    def __init__(self, W, H, ss=2):
        self.W = W
        self.H = H
        self.ss = ss
        self.A = np.zeros((H * ss, W * ss), np.float32)
        self.C = np.zeros((H * ss, W * ss, 3), np.float32)

    def lines(self, segs, cols, rad=1):
        if len(segs) == 0:
            return
        splat(self.A, self.C, np.asarray(segs, np.float64), np.asarray(cols, np.float32), rad)

    def ell(self, cx, cy, rx, ry, ang, col, shade=0.0):
        A, C = self.A, self.C
        Hh, Ww = A.shape
        m = int(max(rx, ry)) + 2
        x0, x1 = max(0, int(cx) - m), min(Ww, int(cx) + m + 1)
        y0, y1 = max(0, int(cy) - m), min(Hh, int(cy) + m + 1)
        if x0 >= x1 or y0 >= y1:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1]
        dx = xs - cx
        dy = ys - cy
        ca, sa = math.cos(ang), math.sin(ang)
        u = (dx * ca + dy * sa) / rx
        v = (-dx * sa + dy * ca) / ry
        r2 = u * u + v * v
        mk = r2 <= 1.0
        if not mk.any():
            return
        A[y0:y1, x0:x1][mk] = 1.0
        if shade:
            c = col[None, :] * (1.0 - shade * r2[mk][:, None])
        else:
            c = col
        C[y0:y1, x0:x1][mk] = c

    def finish(self, fill=None):
        ss = self.ss
        h, w = self.H, self.W
        pre = self.C * self.A[..., None]
        if ss > 1:
            a = self.A.reshape(h, ss, w, ss).mean(axis=(1, 3))
            c = pre.reshape(h, ss, w, ss, 3).mean(axis=(1, 3))
        else:
            a, c = self.A, pre
        if fill is None:
            fill = pre.sum(axis=(0, 1)) / max(float(self.A.sum()), 1.0)
        rgb = np.where(a[..., None] > 1e-3, c / np.maximum(a[..., None], 1e-3), np.asarray(fill).reshape(1, 1, 3))
        return rgb.astype(np.float32), a.astype(np.float32)


# ---------------------------------------------------------------- textures

def blade_atlas(name, pal, tag, ncol=8, W=256, H=128, base=0.75, tip=1.1, vein=0.12):
    """Opaque blade/branch strip atlas: ncol tones side by side, base darker, tip lighter, pale midrib."""
    img = np.zeros((H, W, 3), np.float32)
    v = (np.arange(H) + 0.5) / H
    g = (base + (tip - base) * v ** 0.8)[:, None]
    for k in range(ncol):
        c = np.array(pal[k % len(pal)], np.float32) * (0.88 + 0.24 * float(h01(tag, k, 3)))
        x0, x1 = k * W // ncol, (k + 1) * W // ncol
        wd = x1 - x0
        xs = (np.arange(wd) + 0.5) / wd
        prof = 1.0 + vein * np.exp(-((xs - 0.5) / 0.07) ** 2) - 0.06 * (np.abs(xs - 0.5) > 0.4)
        streak = 0.95 + 0.10 * hn(np.arange(wd) + k * 100, tag, 9)
        img[:, x0:x1, :] = (g * (prof * streak)[None, :])[..., None] * c[None, None, :]
    return save_tex(name, np.clip(img[::-1], 0, 1))


def stem_tex(name, col, tag, hairy=0.0, W=64, H=64):
    img = np.ones((H, W, 3), np.float32) * np.array(col, np.float32)
    streak = 0.92 + 0.16 * hn(np.arange(W), tag, 3)[None, :, None]
    img = img * streak
    if hairy > 0:
        n = int(hairy * W * H)
        idx = np.arange(n)
        xs = (hn(idx, tag, 4) * W).astype(int) % W
        ys = (hn(idx, tag, 5) * H).astype(int) % H
        img[ys, xs] = np.array(col, np.float32) * 1.35 + 0.08
    return save_tex(name, np.clip(img, 0, 1))


def bark_tex(name, tint):
    src = pixels_td(FIR_BARK, 1024)[..., :3]
    rgb = np.clip(src * np.array(tint, np.float32) * 1.25, 0.0, 1.0)
    return save_tex(name, rgb)


def horsetail_stem_tex(name, col, tag):
    H, W = 128, 64
    v = ((np.arange(H) + 0.5) / H)[:, None]
    x = ((np.arange(W) + 0.5) / W)[None, :]
    body = np.array(col, np.float32)[None, None, :] * (0.92 + 0.16 * hn(np.arange(W), tag, 3))[None, :, None]
    ridge = np.where(np.sin(TAU * x * 8.0) < -0.75, 0.82, 1.0)[..., None]
    img = np.broadcast_to(body, (H, W, 3)) * ridge
    collar = (v < 0.27)[..., None]
    dark = np.array([0.10, 0.08, 0.05], np.float32).reshape(1, 1, 3)
    tooth = ((np.sin(TAU * x * 8.0) > 0.0) & (v > 0.20))[..., None]
    pale = np.array([0.42, 0.36, 0.24], np.float32).reshape(1, 1, 3)
    img = np.where(collar, np.where(tooth, pale, dark), img)
    return save_tex(name, np.clip(img[::-1], 0, 1))


# ---- feathery spray (baldcypress)

def draw_feather(T, pal):
    cv = Canvas(768, 1024, 2)
    Hc, Wc = cv.A.shape
    cx = Wc * 0.5
    yb = Hc * 0.975
    yt = Hc * 0.03
    nb, bang, reach, shapepow = 34, 1.08, 0.47, 0.80
    needle_len, step, nper = 27.0, 5.5, 2
    wood = pal * np.array([0.70, 0.55, 0.40], np.float32)
    tw_segs, tw_cols, nd_segs, nd_cols = [[cx, yb, cx, yt]], [wood], [], []

    def shape(s):
        return min(1.0, s / 0.12) ** 0.5 * max(0.0, 1.0 - s ** 2.5) ** shapepow

    for side in (-1.0, 1.0):
        for i in range(nb):
            s = 0.05 + 0.93 * (i + (0.5 if side > 0 else 0.0) + 0.25) / (nb + 0.5)
            h = float(hn(T, i, int(side) + 2, 20))
            if float(hn(T, i, int(side) + 2, 21)) < 0.06:
                continue
            lat = Wc * reach * shape(s) * (0.65 + 0.45 * h)
            ang = bang + 0.4 * (h - 0.5)
            ln = lat / math.sin(ang)
            fwd = ln * math.cos(ang)
            sx, sy = cx, yb - s * (yb - yt)
            ex, ey = sx + side * lat, sy - fwd
            dx, dy = side * math.sin(ang), -math.cos(ang)
            tw_segs.append([sx, sy, ex, ey])
            tw_cols.append(wood)
            n = max(2, int(ln / (step * 2)))
            for j in range(n + 1):
                u = j / n
                px, py = sx + (ex - sx) * u, sy + (ey - sy) * u
                for q in range(nper):
                    h2 = float(hn(T, i * 977 + j * 13 + int(side + 2), q, 1))
                    a = (1.0 if q % 2 == 0 else -1.0) * (0.85 + 0.45 * h2)
                    ca, sa = math.cos(a), math.sin(a)
                    ndx, ndy = dx * ca - dy * sa, dx * sa + dy * ca
                    nl = needle_len * 2 * (1.0 - 0.40 * u) * (0.8 + 0.4 * h2)
                    nd_segs.append([px, py, px + ndx * nl, py + ndy * nl])
                    shade = (0.82 + 0.28 * u) * (0.9 + 0.2 * float(hn(T, i, j, q + 5)))
                    nd_cols.append(np.clip(pal * shade, 0, 1))
            # tip needle
            nd_segs.append([ex, ey, ex + dx * needle_len * 2, ey + dy * needle_len * 2])
            nd_cols.append(np.clip(pal * 1.05, 0, 1))
    cv.lines(tw_segs, tw_cols, 1)
    cv.lines(nd_segs, nd_cols, 2)
    return cv.finish(fill=pal)


# ---- lacy bipinnate fern frond (lady fern)

def draw_fern_frond(T, pal):
    cv = Canvas(420, 1024, 2)
    Hc, Wc = cv.A.shape
    cx = Wc * 0.5
    yb = Hc * 0.985
    yt = Hc * 0.02
    rach = pal * np.array([0.62, 0.66, 0.45], np.float32)
    cv.lines([[cx, yb, cx, yt]], [rach], 2)
    npin = 19
    for side in (-1.0, 1.0):
        for i in range(npin):
            s = 0.04 + 0.92 * (i + (0.5 if side > 0 else 0.0)) / (npin + 0.5)
            h = float(hn(T, i, int(side) + 2, 20))
            f = math.sin(math.pi * min(1.0, s ** 0.72)) ** 0.75
            Lp = Wc * 0.47 * max(0.10, f) * (0.88 + 0.24 * h)
            phi = (74.0 - 24.0 * s) * DEG + (h - 0.5) * 0.12
            sx, sy = cx, yb - s * (yb - yt)
            ax, ay = side * math.sin(phi), -math.cos(phi)
            npts = 7
            # slightly curved pinna axis (bends forward toward the tip)
            ptsx, ptsy = [sx], [sy]
            for k in range(npts):
                a = phi - side * 0.16 * (k + 0.5) / npts
                ptsx.append(ptsx[-1] + side * math.sin(a) * Lp / npts)
                ptsy.append(ptsy[-1] - math.cos(a) * Lp / npts)
            segs = [[ptsx[k], ptsy[k], ptsx[k + 1], ptsy[k + 1]] for k in range(npts)]
            cv.lines(segs, [rach * 1.1] * len(segs), 1)
            npn = 9
            for k in range(1, npn + 1):
                p = k / (npn + 0.4)
                fx = p * npts
                k0 = min(npts - 1, int(fx))
                fr = fx - k0
                px = ptsx[k0] + (ptsx[k0 + 1] - ptsx[k0]) * fr
                py = ptsy[k0] + (ptsy[k0 + 1] - ptsy[k0]) * fr
                ba = math.atan2(ptsy[k0 + 1] - ptsy[k0], ptsx[k0 + 1] - ptsx[k0])
                lp = (22.0 + 16.0 * Lp / (Wc * 0.47)) * (1.0 - 0.70 * p) ** 0.8
                for sd in (-1.0, 1.0):
                    a = ba + sd * 0.90
                    hh = float(hn(T, i * 131 + k, int(side) + 2, int(sd) + 2))
                    l2 = lp * (0.85 + 0.3 * hh)
                    col = np.clip(pal * (0.82 + 0.3 * hh), 0, 1)
                    cv.ell(px + math.cos(a) * l2 * 0.92, py + math.sin(a) * l2 * 0.92, l2, l2 * 0.26, a, col, 0.25)
            # terminal pinnule
            ba = math.atan2(ptsy[-1] - ptsy[-2], ptsx[-1] - ptsx[-2])
            cv.ell(ptsx[-1] + math.cos(ba) * 22, ptsy[-1] + math.sin(ba) * 22, 24, 8, ba, np.clip(pal * 0.95, 0, 1), 0.2)
    # frond tip
    cv.ell(cx, yt + 24, 10, 34, math.pi * 0.5, np.clip(pal * 0.95, 0, 1), 0.2)
    return cv.finish(fill=pal)


# ---- palmate leaf (lupine)

def draw_palmate(T, pal):
    cv = Canvas(512, 512, 2)
    Hc, Wc = cv.A.shape
    cx, cy = Wc * 0.5, Hc * 0.80
    cv.lines([[cx, Hc - 1, cx, cy]], [pal * 0.7], 3)
    nl = 9
    for k in range(nl):
        a = (-100.0 + 200.0 * k / (nl - 1)) * DEG
        ln = Wc * (0.62 - 0.22 * abs(a) / (100.0 * DEG)) * (0.94 + 0.12 * float(hn(T, k, 1)))
        dx, dy = math.sin(a), -math.cos(a)
        ex, ey = cx + dx * ln * 0.5, cy + dy * ln * 0.5
        ang = math.atan2(dy, dx)
        col = np.clip(pal * (0.88 + 0.22 * float(hn(T, k, 2))), 0, 1)
        cv.ell(ex, ey, ln * 0.5, ln * 0.11, ang, col, 0.30)
        cv.lines([[cx, cy, cx + dx * ln * 0.92, cy + dy * ln * 0.92]], [np.clip(pal * 1.25, 0, 1)], 1)
    return cv.finish(fill=pal)


# ---- lupine floret atlas: left tile open flower, right tile bud

def draw_floret(T, pal, white):
    cv = Canvas(512, 256, 2)
    S = 512  # one tile in supersampled px
    pal = np.asarray(pal, np.float32)
    pale = np.clip(pal * 1.25 + 0.06, 0, 1)
    dark = np.clip(pal * 0.62, 0, 1)
    ox = 0
    cv.ell(ox + 0.31 * S, 0.66 * S, 0.21 * S, 0.19 * S, 0.5, dark, 0.2)
    cv.ell(ox + 0.69 * S, 0.66 * S, 0.21 * S, 0.19 * S, -0.5, dark, 0.2)
    cv.ell(ox + 0.5 * S, 0.40 * S, 0.33 * S, 0.34 * S, 0.0, pal, 0.30)
    cv.ell(ox + 0.5 * S, 0.50 * S, 0.12 * S, 0.12 * S, 0.0, np.asarray(white, np.float32), 0.1)
    cv.ell(ox + 0.5 * S, 0.84 * S, 0.12 * S, 0.11 * S, 0.0, pale, 0.2)
    cv.ell(ox + 0.5 * S, 0.96 * S, 0.06 * S, 0.05 * S, 0.0, f3(0.25, 0.45, 0.18), 0.0)
    ox = S
    bud = np.clip(pal * 0.7 + f3(0.05, 0.12, 0.02), 0, 1)
    cv.ell(ox + 0.5 * S, 0.55 * S, 0.22 * S, 0.40 * S, 0.0, bud, 0.35)
    cv.ell(ox + 0.5 * S, 0.93 * S, 0.10 * S, 0.07 * S, 0.0, f3(0.25, 0.45, 0.18), 0.0)
    return cv.finish(fill=pal)


# ---- poppy leaf, hair card, petal

def draw_poppy_leaf(T, pal):
    cv = Canvas(512, 512, 2)
    Hc, Wc = cv.A.shape
    cx = Wc * 0.5
    yb, yt = Hc * 0.985, Hc * 0.04
    cv.lines([[cx, yb, cx, yt]], [pal * 0.75], 3)
    nlobe = 4
    for side in (-1.0, 1.0):
        for k in range(nlobe):
            s = 0.18 + 0.66 * k / (nlobe - 1)
            sx, sy = cx, yb - s * (yb - yt)
            ln = Wc * (0.44 - 0.12 * k / (nlobe - 1)) * (0.92 + 0.16 * float(hn(T, k, int(side) + 2)))
            a = -math.pi * 0.5 + side * (60.0 - 12.0 * k) * DEG
            col = np.clip(pal * (0.90 + 0.2 * float(hn(T, k, int(side) + 5))), 0, 1)
            cv.ell(sx + math.cos(a) * ln * 0.5, sy + math.sin(a) * ln * 0.5, ln * 0.5, ln * 0.19, a, col, 0.25)
    cv.ell(cx, yt + 0.12 * Hc, Wc * 0.15, Hc * 0.13, math.pi * 0.5, np.clip(pal * 1.05, 0, 1), 0.2)
    return cv.finish(fill=pal)


def draw_hair(T, pal):
    cv = Canvas(128, 256, 2)
    Hc, Wc = cv.A.shape
    n = 300
    segs, cols = [], []
    for i in range(n):
        x = Wc * (0.5 + 0.16 * (float(hn(T, i, 1)) - 0.5))
        y = Hc * float(hn(T, i, 2))
        side = -1.0 if hn(T, i, 3) < 0.5 else 1.0
        a = (55.0 + 25.0 * float(hn(T, i, 4))) * DEG
        ln = Wc * (0.20 + 0.28 * float(hn(T, i, 5)))
        segs.append([x, y, x + side * math.sin(a) * ln, y - math.cos(a) * ln])
        cols.append(np.clip(pal * (0.85 + 0.3 * float(hn(T, i, 6))), 0, 1))
    cv.lines([[Wc * 0.5, Hc, Wc * 0.5, 0]], [pal * 0.8], 3)
    cv.lines(segs, cols, 1)
    return cv.finish(fill=pal)


def petal_tex(name, base, tip, tag):
    H, W = 256, 128
    v = ((np.arange(H) + 0.5) / H)[:, None, None]
    u = ((np.arange(W) + 0.5) / W)[None, :, None]
    base = np.array(base, np.float32).reshape(1, 1, 3)
    tip = np.array(tip, np.float32).reshape(1, 1, 3)
    img = base + (tip - base) * np.clip(v * 1.4, 0, 1) ** 0.8
    vein = 1.0 - 0.07 * np.clip(np.cos(TAU * (u - 0.5) * 5.0 * (0.4 + 0.8 * v)) * 0.5 + 0.5, 0, 1)
    img = img * vein * (0.97 + 0.06 * hn(np.arange(W), tag, 3)[None, :, None])
    return save_tex(name, np.clip(img[::-1], 0, 1))


# ---- bracket fungus top (concentric zoned bands) and pores

def bracket_tex(name, bands, margin, tag):
    H, W = 512, 1024
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    # image rows are bottom-up here: row 0 = v 0 (attach edge at the bottom-centre)
    dx = xs + 0.5 - 512.0
    dy = ys + 0.5
    rho = np.sqrt(dx * dx + dy * dy) / 512.0
    ang = np.arctan2(dy, dx)
    wob = 0.030 * np.sin(5.0 * ang + 1.7 * tag) + 0.018 * np.sin(11.0 * ang + 0.9 * tag)
    wob += 0.02 * (resample(hn(np.arange(64 * 64), tag, 7).reshape(64, 64).astype(np.float32), H, W) - 0.5)
    nb = len(bands)
    q = np.clip((rho + wob) * nb / 0.92, 0, nb - 1e-3)
    idx = np.floor(q).astype(int)
    frac = q - idx
    bands_a = np.array(bands, np.float32)
    col = bands_a[idx]
    col = col * (0.90 + 0.12 * frac[..., None])
    groove = (frac < 0.07) | (frac > 0.97)
    col = np.where(groove[..., None], col * 0.72, col)
    noise = resample(hn(np.arange(256 * 256), tag, 8).reshape(256, 256).astype(np.float32), H, W)
    col = col * (0.88 + 0.24 * noise[..., None])
    m = np.array(margin, np.float32).reshape(1, 1, 3)
    edge = (rho + wob * 0.5) > 0.925
    col = np.where(edge[..., None], m * (0.9 + 0.15 * noise[..., None]), col)
    return save_tex(name, np.clip(col[::-1], 0, 1))


def pores_tex(name, col, tag):
    H = W = 128
    base = np.array(col, np.float32).reshape(1, 1, 3)
    noise = hn(np.arange(H * W), tag, 11).reshape(H, W).astype(np.float32)
    img = base * (0.9 + 0.2 * noise[..., None])
    dots = noise > 0.93
    img = np.where(dots[..., None], img * 0.78, img)
    return save_tex(name, np.clip(img, 0, 1))


# ---- duckweed mat

def duck_tex(name, V, T):
    N = 2048
    cv = Canvas(N, N, 1)
    f1 = resample(hn(np.arange(40 * 40), T, 1).reshape(40, 40), N, N)
    f2 = resample(hn(np.arange(96 * 96), T, 2).reshape(96, 96), N, N)
    field = 0.65 * f1 + 0.35 * f2
    thr = V["thr"]
    ncand = 26000
    idx = np.arange(ncand)
    px = hn(idx, T, 3) * N
    py = hn(idx, T, 4) * N
    jit = (hn(idx, T, 5) - 0.5) * 0.14
    keep = field[np.clip(py.astype(int), 0, N - 1), np.clip(px.astype(int), 0, N - 1)] + jit > thr
    order = np.argsort(hn(idx, T, 6))
    pal = [np.array(c, np.float32) for c in V["pal"]]
    for i in order:
        if not keep[i]:
            continue
        r = hn(i, T, 7)
        rx = 10.0 + 8.0 * float(hn(i, T, 8))
        ry = rx * (0.55 + 0.30 * float(hn(i, T, 9)))
        ang = TAU * float(hn(i, T, 10))
        if r < V["red"]:
            c = np.array(V["redcol"], np.float32)
        else:
            c = pal[int(float(hn(i, T, 11)) * len(pal)) % len(pal)]
        c = c * (0.82 + 0.36 * float(hn(i, T, 12)))
        cv.ell(float(px[i]), float(py[i]), rx, ry, ang, np.clip(c, 0, 1), 0.28)
    rgb, a = cv.finish(fill=pal[0])
    return save_tex(name, rgb, a), float((a > 0.5).mean())


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


def load_img(path, noncolor=False):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        img.colorspace_settings.name = "Non-Color"
    return img


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
        # Math ROUND on alpha: the glTF exporter reads this as alphaMode MASK (cutoff 0.5); a bare link exports BLEND
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


def mspec(path, masked=False, two=True, nor=None, rough=0.75):
    return dict(path=path, masked=masked, two=two, nor=nor, rough=rough)


def build_mats(specs):
    mats = {}
    for name, sp in specs.items():
        nor = load_img(sp["nor"], noncolor=True) if sp.get("nor") else None
        mats[name] = make_material(name, load_img(sp["path"]), nor, sp["masked"], sp["two"], sp["rough"])
    return mats


def realise(name, parts, mats, H, wind, ground=True):
    """One object, one mesh, one slot per distinct Part.mat, WindWeight vertex colour."""
    slots = []
    for p in parts:
        if p.mat not in slots:
            slots.append(p.mat)
    verts, faces, fol_idx = [], [], []
    for part in parts:
        if not part.verts:
            continue
        base = len(verts)
        verts.extend(part.verts)
        if part.fol:
            fol_idx.extend(range(base, base + len(part.verts)))
        si = slots.index(part.mat)
        for idx, uvs in part.faces:
            faces.append((tuple(base + i for i in idx), uvs, si))
    zmin = min(p[2] for p in verts) if ground else 0.0
    verts = [(x, y, z - zmin) for (x, y, z) in verts]
    zmax = max(p[2] for p in verts)
    fol_zmin = min(verts[i][2] for i in fol_idx) if fol_idx else 0.0
    fol_set = set(fol_idx)

    wt = np.zeros((len(verts), 4), dtype=np.float32)
    if wind == "radial":
        scale = 0.5 * H
        for i, (x, y, z) in enumerate(verts):
            dd = min(1.0, math.sqrt(x * x + y * y + z * z) / scale)
            wt[i, 0] = (0.7 + 0.3 * dd) if i in fol_set else dd
    elif wind == "height":
        for i, (x, y, z) in enumerate(verts):
            wt[i, 0] = min(1.0, max(0.0, z / max(zmax, 1e-6)))
    wt[:, 3] = 1.0

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
    ca.data.foreach_set("color", wt.ravel())
    try:
        me.color_attributes.active_color = ca
    except (AttributeError, TypeError):
        pass
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["leaf_zmin"] = float(fol_zmin)
    return ob


def clean_mesh(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bad = [f for f in bm.faces if f.calc_area() < 1e-11]
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


LEAF_NZ = 0.30


def shade_crown(ob, leaf_slot):
    """Smooth bark; point foliage-card normals away from the crown centre so the tree shades as one volume."""
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
    leafv = np.unique(vidx[lmat == leaf_slot])
    if len(leafv) == 0:
        return
    c = vco[leafv].mean(axis=0)
    nrm = vco[vidx] - c
    nrm[:, 2] *= LEAF_NZ
    ln = np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
    nrm = nrm / ln
    out = np.where((lmat == leaf_slot)[:, None], nrm, cur)
    me.normals_split_custom_set([tuple(float(x) for x in v) for v in out])


def smooth_all(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


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


def check_glb(path, masked_names):
    problems = []
    if not os.path.isfile(path) or os.path.getsize(path) < 100:
        return ["missing glb " + os.path.basename(path)]
    with open(path, "rb") as f:
        data = f.read()
    magic, ver, _ = struct.unpack("<4sII", data[:12])
    clen, ctype = struct.unpack("<II", data[12:20])
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    if magic != b"glTF":
        problems.append("bad magic")
    if len(js.get("meshes", [])) != 1:
        problems.append("meshes != 1")
    for me in js.get("meshes", []):
        for pr in me["primitives"]:
            for need in ("POSITION", "TEXCOORD_0", "COLOR_0"):
                if need not in pr["attributes"]:
                    problems.append("missing " + need)
    for m in js.get("materials", []):
        if m.get("name") in masked_names and m.get("alphaMode") != "MASK":
            problems.append("alphaMode %s on %s" % (m.get("alphaMode"), m.get("name")))
    return problems


# ---------------------------------------------------------------- renders

def make_ground(color):
    me = bpy.data.meshes.new("PreviewGround")
    r = 80.0
    me.from_pydata([(-r, -r, 0.0), (r, -r, 0.0), (r, r, 0.0), (-r, r, 0.0)], [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new("PreviewGroundMat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    me.materials.append(m)
    ob = bpy.data.objects.new("PreviewGround", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_wall(name, base, half_w, height, color):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(base[0] - half_w, base[1], base[2]), (base[0] + half_w, base[1], base[2]),
                    (base[0] + half_w, base[1], base[2] + height), (base[0] - half_w, base[1], base[2] + height)],
                   [], [(0, 1, 2, 3)])
    m = bpy.data.materials.new(name + "Mat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_prism(name, centre, radius, height, color, sides=20):
    me = bpy.data.meshes.new(name)
    vs, fs = [], []
    for k in range(sides):
        a = TAU * k / sides
        vs.append((centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a), centre[2]))
        vs.append((centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a), centre[2] + height))
    for k in range(sides):
        k2 = (k + 1) % sides
        fs.append((2 * k, 2 * k2, 2 * k2 + 1, 2 * k + 1))
    me.from_pydata(vs, [], fs)
    m = bpy.data.materials.new(name + "Mat")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def render_view(path, res, loc, target=None, rot=None, lens=50.0, shift_y=0.0, ortho=None,
                transparent=False, ground=(0.10, 0.13, 0.05), extras=None, samples=48):
    scene = bpy.context.scene
    made = []
    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.sensor_fit = "VERTICAL"
    cam_d.sensor_height = 36.0
    cam_d.shift_y = shift_y
    cam_d.clip_start = 0.005
    cam_d.clip_end = 500.0
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
    sun_d.energy = 3.2
    sun = bpy.data.objects.new("PreviewSun", sun_d)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(35.0))
    made.append(sun)

    if ground is not None:
        made.append(make_ground(ground))
    if extras:
        made.extend(extras)

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


def bbox_of(ob):
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    return mn, mx


def render_views(S, name, ob):
    mn, mx = bbox_of(ob)
    dims = mx - mn
    ctr = (mn + mx) * 0.5
    pv = S["pv"]
    asp = pv[0] / pv[1]
    for spec in S["views"]:
        lens = spec.get("lens", 50.0)
        tz = mn.z + spec.get("tz", 0.5) * dims.z
        fit = 1.15 * max(dims.z, max(dims.x, dims.y) * 1.2 / asp) / (36.0 / lens)
        R = fit * spec["k"]
        az = math.radians(spec.get("az", 35.0))
        el = math.radians(spec.get("el", 20.0))
        loc = (ctr.x + R * math.sin(az) * math.cos(el), ctr.y - R * math.cos(az) * math.cos(el), tz + R * math.sin(el))
        ex = S["backdrop"](mn, mx) if S.get("backdrop") else None
        render_view(os.path.join(OUT, name + spec["suf"] + ".png"), pv, loc, target=(ctr.x, ctr.y, tz), lens=lens,
                    ground=S["ground"], extras=ex)


def render_tree_views(S, name, ob, H):
    mn, mx = bbox_of(ob)
    dims = mx - mn
    ctr = (0.5 * (mn.x + mx.x), 0.5 * (mn.y + mx.y))
    pv = S["pv"]
    half = 0.5 * max(dims.x, dims.y)
    cz = H * 0.48
    dist = 1.75 * max(H, 1.3 * half * 2.0)
    az = math.radians(35.0)
    render_view(os.path.join(OUT, name + "_preview.png"), pv,
                (ctr[0] + math.sin(az) * dist, ctr[1] - math.cos(az) * dist, cz + dist * 0.12),
                target=(ctr[0], ctr[1], cz), lens=50.0, ground=S["ground"])
    lz = float(ob["leaf_zmin"])
    az2 = math.radians(25.0)
    d2 = half + 5.0
    tz = min(H * 0.6, lz + max(2.5, 0.12 * H)) if lz > 1.0 else min(H * 0.35, 5.0)
    render_view(os.path.join(OUT, name + "_near.png"), pv,
                (ctr[0] + math.sin(az2) * d2, ctr[1] - math.cos(az2) * d2, 1.7), target=(ctr[0], ctr[1], tz),
                lens=28.0, ground=S["ground"])
    view_h = max(H, 1.2 * half * 2.0 * pv[1] / pv[0]) * 1.2
    lens = 36.0 * 30.0 / view_h
    shift = (H * 0.5 - 1.7) / view_h
    render_view(os.path.join(OUT, name + "_far.png"), pv, (ctr[0], -30.0, 1.7), rot=(math.radians(90.0), 0.0, 0.0),
                lens=lens, shift_y=shift, ground=S["ground"])


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
    """Silhouette alpha (ortho side view) over the foliage rows; coverage = opaque px / convex-hull px."""
    res = 1024
    half = 0.5 * max(dims[0], dims[1])
    scale = 1.12 * max(H, 2.0 * half)
    cz = H * 0.5
    path = os.path.join(tempfile.gettempdir(), "redo_cov_%d.png" % os.getpid())
    render_view(path, (res, res), (0.0, -60.0, cz), rot=(math.radians(90.0), 0.0, 0.0), ortho=scale,
                transparent=True, ground=None, samples=12)
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


# ---------------------------------------------------------------- baldcypress (whorled feathery conifer)

class Ctx:
    def __init__(self, T, density, lod):
        self.T = T
        self.density = density
        self.lod = lod
        self.n = 0
        self.wood = Part("wood", "Bark")
        self.leaf = Part("foliage", "Leaves", fol=True)


def ribbon(ctx, pts, hw, roll=0.0, side0=None, flip=False):
    strip(ctx.leaf, pts, [hw] * len(pts), roll, 0.0, 1.0, side0, flip=flip)


def bpt(p0, d, L, droop, t):
    return (p0[0] + d[0] * L * t, p0[1] + d[1] * L * t, p0[2] + d[2] * L * t + droop * L * t * t)


def trunk_xy(S, V, z):
    t = z / V["H"]
    return (V["sway"] * V["H"] * math.sin(2.7 * t + 0.6) * t, V["sway"] * V["H"] * math.sin(2.1 * t + 2.0) * t)


def frond_branch(ctx, S, V, p0, d, L, r0, droop):
    ctx.n += 1
    b = ctx.n
    T = ctx.T
    lod = ctx.lod
    dens = ctx.density
    if lod == 0 or (lod == 1 and S["wood_lod1"]):
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


def buttress(pts, amp, hg, lobes, ph):
    def f(i, th):
        z = pts[i][2]
        t = max(0.0, 1.0 - z / hg)
        lobe = max(0.0, math.cos(lobes * th + ph)) ** 2
        return 1.0 + amp * (t ** 2.0) * (0.40 + 1.15 * lobe)
    return f


def build_cypress(S, V, dens, lod):
    ctx = Ctx(V["_T"], dens, lod)
    T = ctx.T
    H = V["H"]
    R0 = V["R0"]
    n = S["tnseg"] if lod == 0 else max(4, S["tnseg"] // 3)
    zs = [0.0, 0.12, 0.3, 0.55, 0.9, 1.4, 2.0, 2.8, 3.8] if lod == 0 else [0.0, 0.3, 0.9, 2.0, 3.8]
    zs += [3.8 + (H - 3.8) * i / n for i in range(1, n + 1)]
    pts = []
    for z in zs:
        x, y = trunk_xy(S, V, z)
        pts.append((x, y, z))
    radii = [max(0.02, R0 * (1.0 - S["taper"] * (z / H))) for z in zs]
    fl = buttress(pts, S["bamp"], 3.4, 5, 0.9 + 0.7 * h01(T, 3))
    tube(ctx.wood, pts, radii, (18, 10, 6)[lod], flare=fl)

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
            x, y = trunk_xy(S, V, zz)
            r0 = max(0.008, 0.035 + 0.010 * L)
            frond_branch(ctx, S, V, (x, y, zz), dvec, L, r0, droop)
        z += S["spacing"] * (0.8 + 0.4 * h01(T, i, 701))
        i += 1
    k = 2 if lod else 3
    tl = S["topl"]
    for q in range(S["topn"]):
        az = TAU * q / S["topn"] + 0.5 * h01(T, q, 760)
        dd = unit((math.cos(az) * 0.30, math.sin(az) * 0.30, 1.0))
        x, y = trunk_xy(S, V, H - tl * 0.9)
        base = (x, y, H - tl * 0.9)
        pts2 = [add(base, mul(dd, tl * i2 / (k - 1))) for i2 in range(k)]
        ribbon(ctx, pts2, 0.5 * tl * S["faspect"], 0.0, side0=(-math.sin(az), math.cos(az), 0.0))
        ribbon(ctx, pts2, 0.5 * tl * S["faspect"], 0.0, side0=(math.cos(az), math.sin(az), 0.0))
    return [ctx.wood, ctx.leaf]


def tex_cypress(S, V, name):
    pal = np.array(V["pal"], np.float32)
    rgb, a = draw_feather(31 + V["_T"] % 7, pal)
    leaf = save_tex(name + "_needles", rgb, a)
    bark = bark_tex(name + "_bark", V["bark"])
    return {"Bark": mspec(bark, two=False, nor=FIR_BARK_NOR), "Leaves": mspec(leaf, masked=True, two=True)}, float((a > 0.5).mean())


def build_knees(S, V, dens, lod):
    T = V["_T"]
    wood = Part("wood", "Bark")
    n = V["n"]
    for i in range(n):
        ang = TAU * h01(T, i, 1)
        rad = V["spread"] * math.sqrt(h01(T, i, 2))
        x, y = rad * math.cos(ang), rad * math.sin(ang)
        hh = V["hmax"] * (0.30 + 0.70 * h01(T, i, 3)) * (1.0 - 0.45 * rad / V["spread"])
        r0 = (0.07 + 0.09 * h01(T, i, 4)) * (0.7 + 0.5 * hh / V["hmax"])
        lean = (h01(T, i, 5) - 0.5) * 0.25
        pts = [(x + lean * hh * t, y + lean * 0.5 * hh * t, -0.05 + (hh + 0.05) * t) for t in (0.0, 0.25, 0.5, 0.75, 0.93, 1.0)]
        radii = [r0 * 1.15, r0, r0 * 0.78, r0 * 0.55, r0 * 0.32, r0 * 0.10]
        tube(wood, pts, radii, 8 if lod == 0 else 6, caps=True)
    return [wood]


def tex_knees(S, V, name):
    bark = bark_tex(name + "_bark", V["bark"])
    return {"Bark": mspec(bark, two=False, nor=FIR_BARK_NOR)}, 0.0


# ---------------------------------------------------------------- lady fern

def build_fern(S, V, dens, lod):
    T = V["_T"]
    stem = Part("stem", "Stem")
    leaf = Part("frond", "Frond", fol=True)
    nf = max(4, int(round(V["nf"] * min(1.0, dens))))
    ns = 7 if lod == 0 else 4
    for j in range(nf):
        u = h01(T, j, 1)
        s = u ** 0.8
        az = GOLD * j + 0.3 * (h01(T, j, 2) - 0.5)
        rr = 0.035 * math.sqrt(h01(T, j, 3))
        base = (rr * math.cos(az), rr * math.sin(az), 0.0)
        el0 = lf(84.0, 56.0, s) * DEG + (h01(T, j, 4) - 0.5) * 0.15
        bend = lf(22.0, 82.0, s) * DEG * (0.85 + 0.3 * h01(T, j, 5))
        L = V["L"] * lf(0.62, 1.0, u) * (0.88 + 0.24 * h01(T, j, 6))
        t0 = 0.17
        pts_all = arc_path(base, az + (h01(T, j, 7) - 0.5) * 0.3, L, el0, bend, 16)
        # stipe up to t0, blade from t0 to 1
        k0 = int(round(t0 * 16))
        tube(stem, pts_all[:k0 + 1], [0.0034 * (1.0 - 0.3 * i / k0) for i in range(k0 + 1)], 4, caps=False)
        bl = pts_all[k0:]
        step = max(1, (len(bl) - 1) // ns)
        bl = bl[::step] if (len(bl) - 1) % step == 0 else bl
        nb = len(bl)
        wmax = 0.5 * 0.41 * L * (1.0 - t0)
        strip(leaf, bl, [wmax] * nb, roll=(h01(T, j, 8) - 0.5) * 0.7, flip=h01(T, j, 9) < 0.5)
    return [stem, leaf]


def tex_fern(S, V, name):
    pal = np.array(V["pal"], np.float32)
    rgb, a = draw_fern_frond(41 + V["_T"] % 5, pal)
    fr = save_tex(name + "_frond", rgb, a)
    st = stem_tex(name + "_stem", np.array(V["pal"], np.float32) * 0.8, V["_T"])
    return {"Stem": mspec(st, two=False), "Frond": mspec(fr, masked=True, two=True, rough=0.6)}, float((a > 0.5).mean())


# ---------------------------------------------------------------- grass tufts (tussock, shade grass)

def build_tuft(S, V, dens, lod):
    T = V["_T"]
    part = Part("blades", "Blade", fol=True)
    n = max(30, int(V["n"] * dens))
    wsc = 1.0 / math.sqrt(max(dens, 0.2))
    segs = V["segs"] if lod == 0 else max(2, V["segs"] - 2)
    ncol = 8
    for j in range(n):
        u = h01(T, j, 1)
        s = u ** V["sp"]
        phi = TAU * h01(T, j, 2)
        rb = V["ring"] * (0.25 + 0.75 * s) * math.sqrt(h01(T, j, 3))
        base = (rb * math.cos(phi), rb * math.sin(phi), 0.0)
        az = phi + (h01(T, j, 4) - 0.5) * 1.0
        el0 = lf(V["el_in"], V["el_out"], s) * DEG + (h01(T, j, 5) - 0.5) * 0.25
        bend = lf(V["b_in"], V["b_out"], s) * DEG * (0.7 + 0.6 * h01(T, j, 6))
        L = V["L"] * lf(1.0, V["lo"], s) * (0.78 + 0.34 * h01(T, j, 7))
        pts = arc_path(base, az, L, el0, bend, segs, zmin=0.003)
        w0 = 0.5 * V["w"] * wsc * (0.8 + 0.4 * h01(T, j, 8))
        hws = []
        for i in range(segs + 1):
            t = i / segs
            hws.append(w0 * (1.0 if t < 0.35 else max(0.03, 1.0 - 0.97 * ((t - 0.35) / 0.65) ** 1.4)))
        col = int(h01(T, j, 9) * ncol) % ncol
        strip(part, pts, hws, roll=(h01(T, j, 10) - 0.5) * 2.4, u0=(col + 0.12) / ncol, u1=(col + 0.88) / ncol)
    return [part]


def tex_tuft(S, V, name):
    p = blade_atlas(name + "_blades", V["pal"], V["_T"], base=V["base"], tip=V["tip"])
    return {"Blade": mspec(p, two=True, rough=0.8)}, 1.0


# ---------------------------------------------------------------- horsetail

def build_horsetail(S, V, dens, lod):
    T = V["_T"]
    stem = Part("stem", "Stem")
    br = Part("branch", "Branch", fol=True)
    ns = max(3, int(round(V["ns"] * min(1.0, dens))))
    nbm = V["nb"] if lod == 0 else max(5, int(V["nb"] * 0.6))
    ncol = 8
    for j in range(ns):
        az = TAU * h01(T, j, 1)
        rr = V["ring"] * math.sqrt(h01(T, j, 2))
        base = (rr * math.cos(az), rr * math.sin(az), 0.0)
        Hs = V["H"] * (0.55 + 0.45 * h01(T, j, 3))
        lean = 0.04 + 0.12 * h01(T, j, 4)
        nn = max(6, int(round(Hs / V["sp"])))
        path = arc_path(base, az + (h01(T, j, 5) - 0.5) * 2.0, Hs, 90.0 * DEG - lean, (h01(T, j, 6) - 0.5) * 0.5, nn)
        r0 = V["r0"] * (0.8 + 0.4 * h01(T, j, 7))
        pts, radii, vs = [], [], []
        fr = ((0.0, 1.0), (0.10, 1.5), (0.27, 1.0)) if lod == 0 else ((0.0, 1.0), (0.14, 1.5))
        for i in range(nn):
            ri = r0 * (1.0 - 0.6 * i / nn)
            for f, m in fr:
                pts.append(lerp(path[i], path[i + 1], f))
                radii.append(ri * m)
                vs.append(i + f)
        pts.append(path[nn])
        radii.append(0.0009)
        vs.append(nn)
        tube(stem, pts, radii, 5 if lod == 0 else 4, caps=True, vs=vs)
        # whorls of fine branches at each node
        for i in range(2, nn):
            tt = i / nn
            nb = max(4, int(round(nbm * (0.85 + 0.3 * h01(T, j, i, 20)))))
            Lb = V["Lb"] * (1.0 - tt) ** 0.9 * (0.75 + 0.5 * h01(T, j, i, 21)) + 0.012
            off = 0.5 * (i % 2) + h01(T, j, i, 22)
            for q in range(nb):
                a = TAU * (q + off) / nb
                el0 = lf(8.0, 58.0, tt) * DEG + (h01(T, j, i, q, 23) - 0.5) * 0.3
                bend = lf(60.0, 18.0, tt) * DEG
                p0 = add(lerp(path[i], path[i + 1], 0.10), (math.cos(a) * r0 * 1.4, math.sin(a) * r0 * 1.4, 0.0))
                bp = arc_path(p0, a, Lb * (0.8 + 0.4 * h01(T, j, i, q, 24)), el0, bend, 1 if lod else 2)
                hw = V["bw"] * 0.5
                col = int(h01(T, j, i, q, 25) * ncol) % ncol
                strip(br, bp, [hw, hw * 0.75, 0.0002][:len(bp) - 1] + [0.0002], roll=TAU * h01(T, j, i, q, 26), u0=(col + 0.12) / ncol,
                      u1=(col + 0.88) / ncol)
    return [stem, br]


def tex_horsetail(S, V, name):
    st = horsetail_stem_tex(name + "_stem", V["stem"], V["_T"])
    bp = blade_atlas(name + "_branch", V["bpal"], V["_T"], base=0.8, tip=1.05, vein=0.0)
    return {"Stem": mspec(st, two=False, rough=0.55), "Branch": mspec(bp, two=True, rough=0.7)}, 1.0


# ---------------------------------------------------------------- bracket fungus

def shelf(top, pores, R, th, ysc, az, tilt, cx, cz, ph, nphi=16, nr=5):
    ca, sa = math.cos(az), math.sin(az)
    ct, st = math.cos(tilt), math.sin(tilt)

    def P(rho, phi, zt):
        wob = 1.0 + (0.07 * math.sin(3.0 * phi + ph) + 0.04 * math.sin(7.0 * phi + 2.0 * ph)) * rho * rho
        rr = rho * R * wob
        x = rr * math.cos(phi)
        y = rr * math.sin(phi) * ysc
        z2 = zt * ct - y * st
        y2 = y * ct + zt * st
        return (cx + x * ca - y2 * sa, x * sa + y2 * ca, cz + z2)

    def zt_of(rho):
        return th * (0.35 + 0.65 * (1.0 - rho ** 2.5))

    def uvt(i, j):
        rho = i / nr
        phi = math.pi * j / nphi
        return (0.5 + 0.5 * rho * math.cos(phi), rho * math.sin(phi))

    tv = [[top.v(P(i / nr, math.pi * j / nphi, zt_of(i / nr))) for j in range(nphi + 1)] for i in range(nr + 1)]
    bv = [[pores.v(P(i / nr, math.pi * j / nphi, 0.0)) for j in range(nphi + 1)] for i in range(nr + 1)]
    for i in range(nr):
        for j in range(nphi):
            top.quad(tv[i][j], tv[i][j + 1], tv[i + 1][j + 1], tv[i + 1][j],
                     (uvt(i, j), uvt(i, j + 1), uvt(i + 1, j + 1), uvt(i + 1, j)))
            pores.quad(bv[i][j], bv[i + 1][j], bv[i + 1][j + 1], bv[i][j + 1],
                       ((j / nphi, i / nr), (j / nphi, (i + 1) / nr), ((j + 1) / nphi, (i + 1) / nr), ((j + 1) / nphi, i / nr)))
    # rim wall (same UVs as the pale margin of the top)
    rt = [top.v(P(1.0, math.pi * j / nphi, zt_of(1.0))) for j in range(nphi + 1)]
    rb = [top.v(P(1.0, math.pi * j / nphi, 0.0)) for j in range(nphi + 1)]
    for j in range(nphi):
        top.quad(rt[j], rt[j + 1], rb[j + 1], rb[j], (uvt(nr, j), uvt(nr, j + 1), uvt(nr, j + 1), uvt(nr, j)))
    # back (attach) wall along the straight edge
    seq = [(i / nr, math.pi) for i in range(nr, 0, -1)] + [(0.0, 0.0)] + [(i / nr, 0.0) for i in range(1, nr + 1)]
    wt = [pores.v(P(r, p, zt_of(r))) for r, p in seq]
    wb = [pores.v(P(r, p, 0.0)) for r, p in seq]
    for k in range(len(seq) - 1):
        pores.quad(wt[k], wt[k + 1], wb[k + 1], wb[k], ((0, 0), (1, 0), (1, 1), (0, 1)))


def build_bracket(S, V, dens, lod):
    T = V["_T"]
    top = Part("top", "Top")
    pores = Part("pores", "Pores")
    for t in range(V["tiers"]):
        R = V["R0"] * (1.0 - 0.13 * t) * (0.92 + 0.16 * h01(T, t, 1))
        th = V["th"] * (0.8 + 0.4 * h01(T, t, 2))
        az = (h01(T, t, 3) - 0.5) * 0.45
        cx = (h01(T, t, 4) - 0.5) * 0.7 * V["R0"]
        cz = 0.012 + t * V["sp"] * (0.9 + 0.2 * h01(T, t, 5))
        tilt = (2.0 + 4.0 * h01(T, t, 6)) * DEG
        shelf(top, pores, R, th, 0.80 + 0.12 * h01(T, t, 7), az, tilt, cx, cz, TAU * h01(T, t, 8))
    return [top, pores]


def tex_bracket(S, V, name):
    t = bracket_tex(name + "_top", V["bands"], V["margin"], V["_T"])
    p = pores_tex(name + "_pores", V["pores"], V["_T"])
    return {"Top": mspec(t, two=False, rough=0.85), "Pores": mspec(p, two=False, rough=0.9)}, 1.0


def backdrop_trunk(mn, mx):
    return [make_wall("PreviewBark", (0.0, -0.004, mn.z - 0.1), 1.2, mx.z - mn.z + 0.5, (0.22, 0.16, 0.11))]


def backdrop_water(mn, mx):
    return []


# ---------------------------------------------------------------- duckweed mat

def build_duck(S, V, dens, lod):
    part = Part("mat", "Duck", fol=True)
    h = 0.5 * V["size"]
    z = 0.003
    a = part.v((-h, -h, z))
    b = part.v((h, -h, z))
    c = part.v((h, h, z))
    d = part.v((-h, h, z))
    part.quad(a, b, c, d, ((0, 0), (1, 0), (1, 1), (0, 1)))
    return [part]


def tex_duck(S, V, name):
    p, fill = duck_tex(name + "_mat", V, V["_T"])
    return {"Duck": mspec(p, masked=True, two=True, rough=0.35)}, fill


# ---------------------------------------------------------------- arctic poppy

def build_poppy(S, V, dens, lod):
    T = V["_T"]
    stem = Part("stem", "Stem")
    leaf = Part("leaf", "Leaf", fol=True)
    hair = Part("hair", "Hair", fol=True)
    pet = Part("petal", "Petal", fol=True)
    sta = Part("stamen", "Stamen", fol=True)
    H = V["H"]
    nl = max(5, int(round(V["nl"] * min(1.0, dens ** 0.5))))
    for j in range(nl):
        az = GOLD * j + 0.3 * h01(T, j, 1)
        el0 = lf(38.0, 14.0, h01(T, j, 2)) * DEG
        Lf = V["lf"] * (0.7 + 0.5 * h01(T, j, 3))
        pts = arc_path((0.0, 0.0, 0.01), az, Lf, el0, 40.0 * DEG, 3 if lod == 0 else 2)
        strip(leaf, pts, [0.20 * Lf] * len(pts), roll=0.0, flip=h01(T, j, 4) < 0.5)
        strip(leaf, pts, [0.20 * Lf] * len(pts), roll=0.5 * math.pi, flip=h01(T, j, 5) < 0.5) if lod == 0 and j % 3 == 0 else None
    nb = max(2, int(round(V["nb"] * min(1.0, dens ** 0.5))))
    npet = V["npet"]
    nu, nv = (10, 7) if lod == 0 else (4, 3)
    for j in range(nb + 1):
        az = GOLD * j + 1.0
        rr = 0.02 * h01(T, j, 11)
        base = (rr * math.cos(az), rr * math.sin(az), 0.01)
        isbud = (j == nb)
        Hb = H * (0.62 + 0.38 * h01(T, j, 12)) - (0.02 if not isbud else 0.05)
        lean = 0.05 + 0.18 * h01(T, j, 13)
        path = arc_path(base, az, Hb, 90.0 * DEG - lean, (h01(T, j, 14) - 0.5) * 0.35 + (0.9 if isbud else 0.0), 6)
        radii = [0.0020 - 0.0006 * i / 6 for i in range(7)]
        tube(stem, path, radii, 4, caps=False)
        nh = len(path)
        hv = Hb / 0.06
        strip(hair, path[1:], [0.0048] * (nh - 1), roll=0.0, side0=(1.0, 0.0, 0.0), v0=0.0, v1=hv)
        strip(hair, path[1:], [0.0048] * (nh - 1), roll=0.0, side0=(0.0, 1.0, 0.0), v0=0.0, v1=hv, flip=True)
        C = path[-1]
        up = unit(sub(path[-1], path[-2]))
        if isbud:
            # nodding bud: hairy teardrop
            bp = [C, add(C, mul(up, 0.006)), add(C, mul(unit(add(up, (0.5, 0.0, -0.6))), 0.015)),
                  add(C, mul(unit(add(up, (0.9, 0.0, -1.0))), 0.022))]
            tube(stem, bp, [0.0012, 0.0045, 0.0048, 0.0012], 6, caps=True)
            continue
        e1 = unit(cross(up, (0.0, 1.0, 0.0)))
        e2 = cross(up, e1)
        ph = TAU * h01(T, j, 15)
        Rb = V["bloom"] * (0.9 + 0.2 * h01(T, j, 16))
        # calyx
        tube(stem, [sub(C, mul(up, 0.012)), C, add(C, mul(up, 0.003))], [0.0022, 0.0055, 0.0060], 6, caps=False)
        # petals: bowl profile
        Ls = 1.15 * Rb
        sp_r, sp_z = [0.0015], [0.0]
        for i in range(1, nv + 1):
            s = (i - 0.5) / nv
            bt = lf(62.0, 14.0, s) * DEG
            sp_r.append(sp_r[-1] + math.cos(bt) * Ls / nv)
            sp_z.append(sp_z[-1] + math.sin(bt) * Ls / nv)
        for k in range(npet):
            phic = ph + TAU * k / npet
            half = (math.pi / npet) * 1.30

            def PP(iu, iv, phic=phic, half=half, Rb=Rb, j=j, k=k):
                s = iv / nv
                u = -1.0 + 2.0 * iu / nu
                f = (0.40 + 0.60 * min(1.0, s / 0.55) ** 0.8) * (1.0 if s < 0.82 else (0.1 + 0.9 * math.sqrt(max(0.0, 1.0 - ((s - 0.82) / 0.18) ** 2))))
                phi = phic + u * half * f
                r = sp_r[iv]
                z = sp_z[iv] + 0.0008 * math.sin(5.0 * u + k) * s * s
                return add(add(C, mul(up, z)), add(mul(e1, r * math.cos(phi)), mul(e2, r * math.sin(phi))))
            grid(pet, PP, nu, nv, lambda iu, iv: (iu / nu, iv / nv))
        # pistil + stamens
        tube(stem, [C, add(C, mul(up, 0.009))], [0.0028, 0.0020], 6, caps=True)
        nst = 18 if lod == 0 else 9
        for q in range(nst):
            a = TAU * q / nst + ph
            rin = 0.0045 + 0.0035 * h01(T, j, q, 17)
            rout = rin + 0.003
            o = add(mul(e1, math.cos(a)), mul(e2, math.sin(a)))
            p0 = add(add(C, mul(up, 0.003)), mul(o, rin))
            p1 = add(add(C, mul(up, 0.011)), mul(o, rout))
            tube(sta, [p0, p1], [0.0007, 0.0005], 3, caps=False)
    return [stem, leaf, hair, pet, sta]


def tex_poppy(S, V, name):
    pal = np.array(V["leafc"], np.float32)
    rgb, a = draw_poppy_leaf(51 + V["_T"] % 5, pal)
    lp = save_tex(name + "_leaf", rgb, a)
    hrgb, ha = draw_hair(61 + V["_T"] % 5, np.array(V["hairc"], np.float32))
    hp = save_tex(name + "_hair", hrgb, ha)
    st = stem_tex(name + "_stem", V["stemc"], V["_T"], hairy=0.10)
    pt = petal_tex(name + "_petal", V["pbase"], V["ptip"], V["_T"])
    sm = stem_tex(name + "_stamen", V["stamen"], V["_T"] + 3)
    return {"Stem": mspec(st, two=False, rough=0.8), "Leaf": mspec(lp, masked=True, two=True, rough=0.7),
            "Hair": mspec(hp, masked=True, two=True, rough=0.9), "Petal": mspec(pt, two=True, rough=0.45),
            "Stamen": mspec(sm, two=False, rough=0.6)}, float((a > 0.5).mean())


# ---------------------------------------------------------------- lupine

def leaf_card(part, tip, az, size, g, ntiles=1):
    """Palmate leaf card: base-centre on `tip`, running outward and up (g = elevation), edges drooping."""
    out = (math.cos(az), math.sin(az), 0.0)
    fwd = unit(add(mul(out, math.cos(g)), (0.0, 0.0, math.sin(g))))
    side = (-math.sin(az), math.cos(az), 0.0)

    def P(iu, iv):
        u = iu / 3.0
        v = iv / 3.0
        return add(add(add(tip, mul(fwd, v * size)), mul(side, (u - 0.5) * size)),
                   (0.0, 0.0, -0.18 * size * (2.0 * u - 1.0) ** 2))
    grid(part, P, 3, 3, lambda iu, iv: (iu / 3.0, iv / 3.0))


def build_lupine(S, V, dens, lod):
    T = V["_T"]
    H = V["H"]
    stem = Part("stem", "Stem")
    leaf = Part("leaf", "Leaf", fol=True)
    flo = Part("floret", "Floret", fol=True)
    nl = max(5, int(round(V["nl"] * min(1.0, dens ** 0.5))))
    for j in range(nl):
        az = GOLD * j + 0.4 * h01(T, j, 1)
        base = (0.03 * math.cos(az), 0.03 * math.sin(az), 0.02)
        Lp = V["Lp"] * (0.65 + 0.5 * h01(T, j, 2))
        pts = arc_path(base, az, Lp, lf(78.0, 52.0, h01(T, j, 3)) * DEG, 38.0 * DEG, 3)
        tube(stem, pts, [0.0036, 0.0031, 0.0027, 0.0022], 4, caps=False)
        leaf_card(leaf, pts[-1], az, V["ls"] * (0.8 + 0.4 * h01(T, j, 4)), lf(14.0, 36.0, h01(T, j, 5)) * DEG)
    ns = max(2, int(round(V["ns"] * min(1.0, dens ** 0.5))))
    for q in range(ns):
        az = GOLD * q * 1.7 + 1.3
        lean = 0.03 + 0.10 * h01(T, q, 11)
        Hq = H * (0.80 + 0.20 * h01(T, q, 12))
        npath = 14
        path = arc_path((0.02 * math.cos(az), 0.02 * math.sin(az), 0.02), az + (h01(T, q, 13) - 0.5) * 1.5, Hq,
                        90.0 * DEG - lean, (h01(T, q, 14) - 0.5) * 0.3, npath)
        slen = V["slen"] * (0.9 + 0.2 * h01(T, q, 15))
        t0 = 1.0 - slen / Hq
        radii = []
        for i in range(npath + 1):
            tt = i / npath
            radii.append(0.0052 - 0.0012 * min(1.0, tt / t0) if tt < t0 else 0.0040 * (1.0 - 0.7 * (tt - t0) / (1.0 - t0)))
        tube(stem, path, radii, 5, caps=True)

        def axis(s):
            f = min(npath - 1e-6, s * npath)
            i = int(f)
            a = f - i
            return lerp(path[i], path[i + 1], a), unit(sub(path[i + 1], path[i]))
        # two small stem leaves
        for c in range(2):
            sc = 0.25 + 0.25 * c
            pc, tn = axis(sc * t0)
            aa = az + 1.5 + 2.2 * c
            tip = add(pc, (0.025 * math.cos(aa), 0.025 * math.sin(aa), 0.012))
            tube(stem, [pc, tip], [0.0025, 0.0018], 3, caps=False)
            leaf_card(leaf, tip, aa, 0.55 * V["ls"], 30.0 * DEG)
        nf = max(30, int(V["nf"] * dens))
        for k in range(nf):
            t = (k + 0.5) / nf
            pos, tn = axis(t0 + (1.0 - t0) * t)
            e1 = unit(cross((0.0, 0.0, 1.0), tn)) if abs(tn[2]) < 0.98 else (1.0, 0.0, 0.0)
            e2 = cross(tn, e1)
            phi = GOLD * k + 0.4 * (h01(T, q, k, 21) - 0.5)
            out = add(mul(e1, math.cos(phi)), mul(e2, math.sin(phi)))
            tg = add(mul(e1, -math.sin(phi)), mul(e2, math.cos(phi)))
            rr = V["rmax"] * (1.0 - t) ** 0.75 + 0.004
            th = (22.0 + 38.0 * t) * DEG + (h01(T, q, k, 22) - 0.5) * 0.3
            dr = unit(add(mul(out, math.cos(th)), mul(tn, math.sin(th))))
            l = min(0.040, max(0.013, 0.85 * rr + 0.010)) * (0.88 + 0.24 * h01(T, q, k, 23))
            wdt = l * 1.05
            B = add(pos, mul(out, 0.003))
            bud = t > 0.90
            u0, u1 = (0.5, 1.0) if bud else (0.0, 0.5)
            fa = add(B, mul(dr, l))
            flo.quad(flo.v(sub(B, mul(tg, wdt * 0.5))), flo.v(add(B, mul(tg, wdt * 0.5))),
                     flo.v(add(fa, mul(tg, wdt * 0.5))), flo.v(sub(fa, mul(tg, wdt * 0.5))),
                     ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)))
            n1 = unit(cross(dr, tg))
            flo.quad(flo.v(sub(B, mul(n1, wdt * 0.42))), flo.v(add(B, mul(n1, wdt * 0.42))),
                     flo.v(add(fa, mul(n1, wdt * 0.42))), flo.v(sub(fa, mul(n1, wdt * 0.42))),
                     ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)))
    return [stem, leaf, flo]


def tex_lupine(S, V, name):
    pal = np.array(V["leafc"], np.float32)
    rgb, a = draw_palmate(71 + V["_T"] % 5, pal)
    lp = save_tex(name + "_leaf", rgb, a)
    frgb, fa = draw_floret(81 + V["_T"] % 5, V["flower"], V["spot"])
    fp = save_tex(name + "_floret", frgb, fa)
    st = stem_tex(name + "_stem", V["stemc"], V["_T"], hairy=0.04)
    return {"Stem": mspec(st, two=False, rough=0.8), "Leaf": mspec(lp, masked=True, two=True, rough=0.65),
            "Floret": mspec(fp, masked=True, two=True, rough=0.55)}, float((fa > 0.5).mean())


# ---------------------------------------------------------------- species table

CYP = dict(id="baldcypress", T=61, build=build_cypress, tex=tex_cypress, wind="radial", shade="crown", tree=True,
           want=30000, fit=True, tri=(15000, 80000), cov_min=0.70, hr=(18.0, 32.0), pv=(512, 640),
           ground=(0.10, 0.13, 0.05), views=[], lod=True,
           tnseg=14, taper=0.88, bamp=1.15, sway=0.012, zb=3.0, spacing=0.40, k=(6, 8), Rfac=0.140, lp=0.95,
           el0=0.10, el1=0.62, dr0=0.50, dr1=0.15, fmin=0.7, fmax=1.2, fl=0.30, fsp=0.45, faspect=0.62,
           rolls=(0.0, 0.85, -0.85), curt_t=(0.35, 0.60, 0.85), curt_p=0.95, curt_len=1.0, topn=6, topl=1.3,
           wood_lod1=True)

SPECIES = [
    CYP,
    dict(id="baldcypress_knees", T=62, build=build_knees, tex=tex_knees, wind="none", shade="smooth", want=None,
         tri=(300, 4000), cov_min=0.0, hr=(0.4, 1.3), pv=(640, 512), ground=(0.12, 0.10, 0.06), lod=True,
         views=[dict(suf="_preview", k=1.0, az=30, el=25, tz=0.4), dict(suf="_near", k=0.55, az=-20, el=15, tz=0.35)]),
    dict(id="lady_fern", T=63, build=build_fern, tex=tex_fern, wind="height", shade="smooth", want=None,
         tri=(300, 8000), cov_min=0.0, hr=(0.30, 1.0), pv=(640, 640), ground=(0.12, 0.10, 0.05), lod=True,
         views=[dict(suf="_preview", k=0.95, az=35, el=28, tz=0.45), dict(suf="_near", k=0.55, az=15, el=38, tz=0.35)]),
    dict(id="alpine_tussock", T=64, build=build_tuft, tex=tex_tuft, wind="height", shade="smooth", want=None,
         tri=(1000, 9000), cov_min=0.50, hr=(0.15, 0.45), pv=(640, 512), ground=(0.16, 0.15, 0.12), lod=True,
         views=[dict(suf="_preview", k=0.95, az=35, el=22, tz=0.45), dict(suf="_near", k=0.5, az=10, el=30, tz=0.4)]),
    dict(id="shade_grass", T=65, build=build_tuft, tex=tex_tuft, wind="height", shade="smooth", want=None,
         tri=(1000, 9000), cov_min=0.50, hr=(0.20, 0.60), pv=(640, 512), ground=(0.07, 0.08, 0.04), lod=True,
         views=[dict(suf="_preview", k=0.95, az=35, el=22, tz=0.45), dict(suf="_near", k=0.5, az=10, el=30, tz=0.4)]),
    dict(id="horsetail", T=66, build=build_horsetail, tex=tex_horsetail, wind="height", shade="smooth", want=None,
         tri=(1500, 16000), cov_min=0.0, hr=(0.25, 1.0), pv=(640, 640), ground=(0.08, 0.09, 0.05), lod=True,
         views=[dict(suf="_preview", k=0.95, az=35, el=14, tz=0.5), dict(suf="_near", k=0.45, az=15, el=10, tz=0.55)]),
    dict(id="bracket_fungus", T=67, build=build_bracket, tex=tex_bracket, wind="none", shade="smooth", want=None,
         tri=(500, 4000), cov_min=0.0, hr=(0.04, 0.40), pv=(640, 640), ground=None, lod=False,
         ground_z=False, backdrop=backdrop_trunk,
         views=[dict(suf="_preview", k=1.0, az=158, el=30, tz=0.5), dict(suf="_near", k=0.6, az=198, el=22, tz=0.5),
                dict(suf="_top", k=0.9, az=172, el=68, tz=0.5)]),
    dict(id="duckweed_mat", T=68, build=build_duck, tex=tex_duck, wind="none", shade="smooth", want=None,
         tri=(2, 20), cov_min=0.0, hr=None, pv=(640, 512), ground=(0.02, 0.05, 0.04), lod=False, ground_z=False,
         views=[dict(suf="_preview", k=1.0, az=20, el=42, tz=0.0), dict(suf="_near", k=0.5, az=0, el=60, tz=0.0)]),
    dict(id="arctic_poppy", T=69, build=build_poppy, tex=tex_poppy, wind="height", shade="smooth", want=None,
         tri=(500, 9000), cov_min=0.0, hr=(0.08, 0.35), pv=(640, 640), ground=(0.17, 0.15, 0.11), lod=True,
         views=[dict(suf="_preview", k=0.95, az=30, el=26, tz=0.55), dict(suf="_near", k=0.45, az=20, el=22, tz=0.75)]),
    dict(id="lupine", T=70, build=build_lupine, tex=tex_lupine, wind="height", shade="smooth", want=None,
         tri=(1500, 14000), cov_min=0.0, hr=(0.5, 1.2), pv=(640, 720), ground=(0.10, 0.12, 0.05), lod=True,
         views=[dict(suf="_preview", k=0.95, az=30, el=16, tz=0.5), dict(suf="_near", k=0.42, az=20, el=14, tz=0.78)]),
]

VARIANTS = {
    "baldcypress": [
        dict(H=22.0, R0=0.50, pal=(0.46, 0.66, 0.26), bark=(0.62, 0.42, 0.34), cs=0.95, sway=0.010),
        dict(H=26.0, R0=0.58, pal=(0.72, 0.38, 0.15), bark=(0.55, 0.40, 0.32), cs=1.00, sway=0.014),
        dict(H=30.0, R0=0.66, pal=(0.50, 0.60, 0.42), bark=(0.66, 0.54, 0.46), cs=1.00, sway=0.012),
    ],
    "baldcypress_knees": [
        dict(H=0.8, n=9, spread=1.6, hmax=0.70, bark=(0.62, 0.42, 0.34)),
        dict(H=1.0, n=13, spread=2.2, hmax=0.95, bark=(0.55, 0.40, 0.32)),
    ],
    "lady_fern": [
        dict(H=0.5, L=0.60, nf=20, pal=(0.46, 0.68, 0.26)),
        dict(H=0.7, L=0.80, nf=22, pal=(0.38, 0.62, 0.40)),
        dict(H=0.9, L=1.00, nf=24, pal=(0.62, 0.76, 0.36)),
    ],
    "alpine_tussock": [
        dict(H=0.25, L=0.26, n=620, ring=0.05, w=0.012, el_in=86, el_out=62, b_in=58, b_out=128, lo=0.80, sp=0.75, segs=4,
             pal=[(0.45, 0.52, 0.42), (0.52, 0.56, 0.45), (0.40, 0.48, 0.38), (0.58, 0.58, 0.46)], base=0.7, tip=1.1),
        dict(H=0.35, L=0.36, n=680, ring=0.06, w=0.013, el_in=86, el_out=62, b_in=58, b_out=128, lo=0.80, sp=0.75, segs=4,
             pal=[(0.80, 0.66, 0.34), (0.72, 0.58, 0.28), (0.86, 0.74, 0.42), (0.62, 0.52, 0.28)], base=0.7, tip=1.15),
        dict(H=0.22, L=0.22, n=600, ring=0.05, w=0.011, el_in=86, el_out=62, b_in=58, b_out=128, lo=0.80, sp=0.75, segs=4,
             pal=[(0.20, 0.25, 0.17), (0.26, 0.30, 0.19), (0.16, 0.20, 0.15), (0.30, 0.32, 0.22)], base=0.75, tip=1.2),
    ],
    "shade_grass": [
        dict(H=0.3, L=0.30, n=720, ring=0.06, w=0.010, el_in=78, el_out=48, b_in=75, b_out=135, lo=0.85, sp=0.75, segs=4,
             pal=[(0.10, 0.27, 0.10), (0.13, 0.31, 0.12), (0.08, 0.22, 0.09), (0.16, 0.34, 0.13)], base=0.8, tip=1.15),
        dict(H=0.4, L=0.40, n=760, ring=0.07, w=0.010, el_in=78, el_out=48, b_in=75, b_out=135, lo=0.85, sp=0.75, segs=4,
             pal=[(0.12, 0.31, 0.26), (0.10, 0.27, 0.24), (0.16, 0.36, 0.30), (0.09, 0.24, 0.21)], base=0.8, tip=1.15),
        dict(H=0.5, L=0.50, n=760, ring=0.07, w=0.011, el_in=78, el_out=48, b_in=75, b_out=135, lo=0.85, sp=0.75, segs=4,
             pal=[(0.40, 0.55, 0.14), (0.34, 0.48, 0.12), (0.46, 0.60, 0.18), (0.28, 0.42, 0.11)], base=0.8, tip=1.15),
    ],
    "horsetail": [
        dict(H=0.35, ns=11, ring=0.07, sp=0.035, r0=0.0030, Lb=0.085, bw=0.0017, nb=13, stem=(0.30, 0.48, 0.18),
             bpal=[(0.30, 0.50, 0.18), (0.26, 0.45, 0.16), (0.34, 0.54, 0.20)]),
        dict(H=0.55, ns=12, ring=0.09, sp=0.040, r0=0.0034, Lb=0.105, bw=0.0018, nb=14, stem=(0.14, 0.32, 0.14),
             bpal=[(0.14, 0.34, 0.14), (0.12, 0.30, 0.12), (0.17, 0.38, 0.16)]),
        dict(H=0.80, ns=13, ring=0.11, sp=0.045, r0=0.0038, Lb=0.13, bw=0.0019, nb=15, stem=(0.42, 0.52, 0.38),
             bpal=[(0.42, 0.54, 0.36), (0.38, 0.50, 0.32), (0.46, 0.58, 0.40)]),
    ],
    "bracket_fungus": [
        dict(H=0.2, tiers=4, R0=0.085, th=0.012, sp=0.036,
             bands=[(0.90, 0.85, 0.70), (0.66, 0.50, 0.32), (0.58, 0.30, 0.12), (0.88, 0.80, 0.62), (0.40, 0.24, 0.12),
                    (0.84, 0.76, 0.58), (0.52, 0.36, 0.20), (0.78, 0.68, 0.50), (0.35, 0.22, 0.12)],
             margin=(0.93, 0.89, 0.76), pores=(0.93, 0.88, 0.74)),
        dict(H=0.26, tiers=5, R0=0.11, th=0.014, sp=0.040,
             bands=[(0.86, 0.42, 0.10), (0.60, 0.25, 0.07), (0.92, 0.62, 0.16), (0.45, 0.20, 0.07), (0.82, 0.46, 0.12),
                    (0.66, 0.30, 0.08), (0.90, 0.58, 0.14), (0.52, 0.24, 0.07), (0.78, 0.40, 0.10)],
             margin=(0.95, 0.80, 0.45), pores=(0.80, 0.66, 0.44)),
        dict(H=0.2, tiers=3, R0=0.14, th=0.016, sp=0.048,
             bands=[(0.58, 0.58, 0.55), (0.36, 0.36, 0.34), (0.72, 0.70, 0.64), (0.26, 0.26, 0.25), (0.52, 0.52, 0.50),
                    (0.68, 0.66, 0.60), (0.30, 0.30, 0.28), (0.60, 0.60, 0.56), (0.42, 0.42, 0.40)],
             margin=(0.88, 0.87, 0.82), pores=(0.80, 0.78, 0.72)),
    ],
    "duckweed_mat": [
        dict(H=0.0, size=1.0, thr=0.50, red=0.0, redcol=(0.5, 0.2, 0.1),
             pal=[(0.22, 0.62, 0.12), (0.28, 0.68, 0.14), (0.18, 0.55, 0.10)]),
        dict(H=0.0, size=1.0, thr=0.48, red=0.0, redcol=(0.5, 0.2, 0.1),
             pal=[(0.52, 0.66, 0.15), (0.58, 0.72, 0.18), (0.46, 0.60, 0.14)]),
        dict(H=0.0, size=1.0, thr=0.50, red=0.32, redcol=(0.62, 0.26, 0.12),
             pal=[(0.30, 0.58, 0.12), (0.38, 0.62, 0.14), (0.24, 0.50, 0.10)]),
    ],
    "arctic_poppy": [
        dict(H=0.18, nl=9, lf=0.09, nb=6, npet=5, bloom=0.030, leafc=(0.30, 0.50, 0.22), hairc=(0.78, 0.68, 0.46),
             stemc=(0.50, 0.58, 0.32), pbase=(0.95, 0.66, 0.04), ptip=(1.0, 0.86, 0.14), stamen=(0.95, 0.65, 0.10)),
        dict(H=0.22, nl=9, lf=0.10, nb=6, npet=5, bloom=0.032, leafc=(0.28, 0.48, 0.22), hairc=(0.80, 0.72, 0.52),
             stemc=(0.52, 0.60, 0.34), pbase=(0.92, 0.88, 0.62), ptip=(0.98, 0.98, 0.96), stamen=(0.95, 0.68, 0.08)),
        dict(H=0.26, nl=10, lf=0.10, nb=7, npet=4, bloom=0.034, leafc=(0.32, 0.50, 0.22), hairc=(0.80, 0.66, 0.44),
             stemc=(0.52, 0.56, 0.30), pbase=(0.96, 0.42, 0.05), ptip=(1.0, 0.66, 0.12), stamen=(0.95, 0.80, 0.12)),
    ],
    "lupine": [
        dict(H=0.65, nl=11, Lp=0.26, ls=0.19, ns=4, slen=0.26, rmax=0.032, nf=140, leafc=(0.20, 0.42, 0.16),
             stemc=(0.30, 0.46, 0.20), flower=(0.22, 0.36, 0.86), spot=(0.92, 0.92, 0.98)),
        dict(H=0.85, nl=12, Lp=0.34, ls=0.22, ns=5, slen=0.32, rmax=0.034, nf=150, leafc=(0.18, 0.40, 0.17),
             stemc=(0.28, 0.44, 0.20), flower=(0.48, 0.24, 0.74), spot=(0.96, 0.92, 0.62)),
        dict(H=1.0, nl=12, Lp=0.40, ls=0.24, ns=5, slen=0.38, rmax=0.036, nf=160, leafc=(0.22, 0.44, 0.18),
             stemc=(0.32, 0.48, 0.22), flower=(0.88, 0.36, 0.62), spot=(0.98, 0.94, 0.92)),
    ],
}

# default views for the tree are rendered by render_tree_views


# ---------------------------------------------------------------- per-variant pipeline

def make_parts(S, V, lod, want):
    """Build parts; for fitted items iterate density to the triangle target."""
    if lod == 0 and not S.get("fit"):
        parts = S["build"](S, V, 1.0, 0)
        return parts, 1.0
    dens = 1.0 if lod == 0 else 0.35
    target = S["want"] if lod == 0 else want
    best = None
    for _ in range(9):
        parts = S["build"](S, V, dens, lod)
        tot = sum(tri_count(p) for p in parts)
        err = abs(tot - target)
        if best is None or err < best[0]:
            best = (err, dens, parts)
        if err <= (0.07 if lod == 0 else 0.12) * target:
            break
        wood = sum(tri_count(p) for p in parts if not p.fol)
        fol = max(1.0, tot - wood)
        dens *= min(3.0, max(0.3, (target - wood) / fol)) if S.get("fit") else min(3.0, max(0.3, target / max(1.0, tot)))
        dens = min(8.0, max(0.05, dens))
    return best[2], best[1]


def finish_obj(S, ob):
    clean_mesh(ob)
    if S["shade"] == "crown":
        names = [m.name for m in ob.data.materials]
        shade_crown(ob, names.index("Leaves") if "Leaves" in names else 1)
    else:
        smooth_all(ob)


def author(S, V0, vi, norender):
    name = "%s_v%02d" % (S["id"], vi + 1)
    V = dict(V0)
    V["_T"] = S["T"] * 100 + vi
    reset_scene()
    tex, fill = S["tex"](S, V, name)
    mats = build_mats(tex)
    masked = {k for k, sp in tex.items() if sp["masked"]}
    parts0, dens0 = make_parts(S, V, 0, None)
    ground = S.get("ground_z", True)
    ob0 = realise(name, parts0, mats, V["H"], S["wind"], ground)
    finish_obj(S, ob0)
    tris0 = mesh_tris(ob0.data)
    mn, mx = bbox_of(ob0)
    dims = (mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    export_files(ob0, name)
    problems = check_glb(os.path.join(OUT, name + ".glb"), masked)
    if not norender:
        if S.get("tree"):
            render_tree_views(S, name, ob0, V["H"])
        else:
            render_views(S, name, ob0)
    cov = measure_coverage(ob0, dims[2], dims) if S["cov_min"] > 0 else 1.0
    tris1 = 0
    if S["lod"] and tris0 > 2000:
        S["_tris0"] = tris0
        parts1, _ = make_parts(S, V, 1, tris0 * 0.30)
        ob1 = realise(name + "_LOD1", parts1, mats, V["H"], S["wind"], ground)
        finish_obj(S, ob1)
        tris1 = mesh_tris(ob1.data)
        export_files(ob1, name + "_LOD1")
        problems += check_glb(os.path.join(OUT, name + "_LOD1.glb"), masked)
    for ext in (".glb", ".fbx"):
        p = os.path.join(OUT, name + ext)
        if not os.path.isfile(p) or os.path.getsize(p) < 100:
            problems.append("missing " + name + ext)
    nviews = 3 if S.get("tree") else len(S["views"])
    return dict(name=name, sp=S["id"], tris0=tris0, tris1=tris1, dims=dims, cov=cov, fill=fill, dens=dens0,
                problems=problems, nviews=nviews)


def write_readme(rows):
    lines = [
        "# redo batch (authored)",
        "",
        "Generated by `Tools/Author-Flora-redo.py` (headless Blender 5.2). Deterministic: same seed and parameters "
        "give the same geometry.",
        "",
        "Redo of rejected items: baldcypress (+ knees prop), lady_fern, alpine_tussock, shade_grass, horsetail, "
        "bracket_fungus, duckweed_mat, arctic_poppy, lupine. Each variant is one combined mesh with several material "
        "slots.",
        "",
        "Conventions: metres. Blender scene Z-up. GLB is Y-up (glTF spec). FBX is Blender-native Z-up. Origin at "
        "ground centre (min Z = 0). Exceptions: `bracket_fungus` origin is on the attach face (back plane y = 0, "
        "shelves grow toward +Y, lowest tier at z = 0); `duckweed_mat` is a thin 1 m plane at z = 3 mm.",
        "",
        "Vertex colour `WindWeight` (COLOR_0 in GLB): R = wind weight (height ratio; radial for the tree), "
        "G = B = 0, A = 1. Fungus, duckweed and knees are all 0.",
        "",
        "Foliage materials are alpha-masked (MASK, cutoff 0.5) and two-sided. LOD1 (about 30% tris, regrown at "
        "lower density) is written only where LOD0 exceeds 2000 triangles.",
        "",
        "Previews: `_preview.png` 3/4 view, `_near.png` close view (baldcypress: eye height 5 m from the crown, plus "
        "`_far.png` at 30 m), bracket also `_top.png`. Cov = opaque fraction inside the convex hull of the "
        "silhouette (side view).",
        "",
        "## Structure notes",
        "",
        "- baldcypress: narrow pyramid of whorled drooping branches carrying overlapping feathery needle sprays "
        "(three planes) plus hanging curtains; trunk has a lobed buttress flare. Knees are a separate prop "
        "(`baldcypress_knees_vNN`).",
        "- lady_fern: 15-19 bipinnate fronds in a vase; frond texture drawn as pinnae divided into separated "
        "pinnules (lacy, gaps).",
        "- alpine_tussock / shade_grass: 300-400 tapered blades per tuft arched into a dense dome; blade atlas tones.",
        "- horsetail: 11-13 jointed stems (collared nodes with dark bands) with whorls of fine needle branches.",
        "- bracket_fungus: flat semicircular shelves with concentric zoned bands (procedural), pale margin, pore "
        "underside, 3-5 stacked tiers.",
        "- duckweed_mat: single plane, irregular tiny ovals in clumps with open gaps, alpha-masked.",
        "- arctic_poppy: cup-shaped 4-5 petal blooms (yellow v01, white v02, orange v03) on hairy stems over a lobed "
        "leaf rosette.",
        "- lupine: palmate basal leaves, dense conical spikes of pea-flower cards (blue v01, violet v02, pink v03).",
        "",
        "## Files",
        "",
        "| Variant | Tris LOD0 | Tris LOD1 | W x D x H (m) | Tex fill | Cov |",
        "|---------|-----------|-----------|---------------|----------|-----|",
    ]
    for r in rows:
        w, d, h = r["dims"]
        lines.append("| %s | %d | %s | %.2f x %.2f x %.2f | %.2f | %.2f |" %
                     (r["name"], r["tris0"], str(r["tris1"]) if r["tris1"] else "-", w, d, h, r["fill"], r["cov"]))
    lines += [
        "",
        "## Provenance",
        "",
        "- Geometry: procedural, generated by `Tools/Author-Flora-redo.py`. No third-party meshes.",
        "- Textures: drawn procedurally (numpy) into `textures/`. Foliage sprays, fern pinnules, fronds, petals, "
        "florets, hair cards, bracket bands and duckweed ovals are all drawn in the script.",
        "- Baldcypress and knees bark: Poly Haven fir_tree_01 bark diffuse and normal (CC0), "
        "`ArtSource/PolyHaven/fir_tree_01/textures/`, tinted into `<name>_bark.png`. CC0 status per site licence, "
        "not individually re-verified in this run.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def montage(rows):
    scratch = os.environ.get("REDO_SCRATCH") or os.path.join(tempfile.gettempdir(), "flora_redo_sheets")
    os.makedirs(scratch, exist_ok=True)
    for sp in sorted({r["sp"] for r in rows}):
        sel = [r for r in rows if r["sp"] == sp]
        sufs = ["_preview", "_near", "_far", "_top"]
        cols = []
        for suf in sufs:
            col_tiles = []
            for r in sel:
                p = os.path.join(OUT, r["name"] + suf + ".png")
                if os.path.isfile(p):
                    col_tiles.append(pixels_td(p))
            if col_tiles:
                hmax = max(t.shape[0] for t in col_tiles)
                wmax = max(t.shape[1] for t in col_tiles)
                padded = []
                for t in col_tiles:
                    pad = np.ones((hmax, wmax, 4), np.float32)
                    pad[:t.shape[0], :t.shape[1]] = t
                    padded.append(pad)
                cols.append(np.concatenate(padded, axis=1))
        if not cols:
            continue
        wmax = max(c.shape[1] for c in cols)
        rws = []
        for c in cols:
            pad = np.ones((c.shape[0], wmax, 4), np.float32)
            pad[:, :c.shape[1]] = c
            rws.append(pad)
        write_png(np.concatenate(rws, axis=0), os.path.join(scratch, sp + "_sheet.png"), sp + "_sheet")
    print("SHEETS " + scratch)


def main():
    os.makedirs(TEX, exist_ok=True)
    only = [x for x in os.environ.get("REDO_ONLY", "").split(",") if x]
    nv = int(os.environ.get("REDO_NV", "3"))
    norender = bool(os.environ.get("REDO_NORENDER"))
    rows = []
    fails = []
    for S in SPECIES:
        if only and S["id"] not in only:
            continue
        for vi, V0 in enumerate(VARIANTS[S["id"]][:nv]):
            rec = author(S, V0, vi, norender)
            rows.append(rec)
            w, d, h = rec["dims"]
            print("VARIANT %s tris0=%d tris1=%d dims=%.2fx%.2fx%.2f dens=%.2f fill=%.2f cov=%.3f" %
                  (rec["name"], rec["tris0"], rec["tris1"], w, d, h, rec["dens"], rec["fill"], rec["cov"]))
            lo, hi = S["tri"]
            if not (lo <= rec["tris0"] <= hi):
                fails.append("%s tris0 %d outside %d-%d" % (rec["name"], rec["tris0"], lo, hi))
            if S["hr"] and not (S["hr"][0] <= h <= S["hr"][1]):
                fails.append("%s height %.2f outside %.2f-%.2f" % (rec["name"], h, S["hr"][0], S["hr"][1]))
            if rec["cov"] < S["cov_min"]:
                fails.append("%s coverage %.2f < %.2f" % (rec["name"], rec["cov"], S["cov_min"]))
            if rec["tris0"] > 2000 and S["lod"]:
                if not (0.15 * rec["tris0"] <= rec["tris1"] <= 0.50 * rec["tris0"]):
                    fails.append("%s LOD1 %d not ~30%% of %d" % (rec["name"], rec["tris1"], rec["tris0"]))
            for p in rec["problems"]:
                fails.append("%s %s" % (rec["name"], p))
    if not only:
        write_readme(rows)
    if not norender:
        montage(rows)
    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d redo variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
