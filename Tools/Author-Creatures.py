"""Author stylised-realistic creature meshes: deer, fox, hare, crow, owl, elk, bear, heron.

Run from repo root:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Creatures.py

Writes to ArtSource/Authored/Creatures/:
  <species>.fbx, <species>.glb   one combined mesh, one material slot (Fur / Feather)
  <species>.png                  1024 px painted albedo
  <species>_n.png                1024 px tangent-space normal (OpenGL +Y), fur / feather relief
  <species>_preview.png          side (left) + 3/4 (right) review render on a ground plane
  README.md

Construction: swept elliptical tubes (spine, neck, head, legs, ears, tails, wings, antlers, beaks)
along Catmull-Rom paths with per-point radii, plus ellipsoids (paws, haunches, tufts). The torso,
neck and head of each animal are ONE continuous tube, so topology is smooth. Parts are joined into a
single mesh and triangulated. UV0 = side planar projection (x, z), so painted markings (belly, rump
patch, face, socks, scallop feathers) are authored directly in side-view coordinates.
Metres, Z-up, origin on ground between feet, facing +X. Deterministic (fixed seeds).
"""

import math
import os
import tempfile

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

try:
    _HERE = os.path.abspath(__file__)
except NameError:
    _HERE = os.path.abspath(os.path.join(os.getcwd(), "Tools", "Author-Creatures.py"))
ROOT = os.path.dirname(os.path.dirname(_HERE))
OUT = os.path.join(ROOT, "ArtSource", "Authored", "Creatures")
TRI_MIN, TRI_MAX = 3000, 15000
TEX = 1024
SEGS = 16
DENS = 0.6


# ---------------------------------------------------------------- geometry

def _crom(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def _samples(pts, step):
    """pts: list of (x, y, z, rz, ry). Returns Nx5 array of Catmull-Rom samples."""
    P = np.array(pts, dtype=np.float64)
    n = len(P)
    if n == 1:
        return P
    pad = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(n - 1):
        seg = np.linalg.norm(P[i + 1][:3] - P[i][:3])
        m = max(2, int(math.ceil(seg / step)))
        for j in range(m):
            out.append(_crom(pad[i], pad[i + 1], pad[i + 2], pad[i + 3], j / m))
    out.append(P[-1])
    S = np.array(out)
    S[:, 3:] = np.maximum(S[:, 3:], 0.0004)
    return S


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.tags = {}
        self.dens = 1.0

    def mark(self, name):
        return len(self.bm.verts)

    def tag(self, name, start):
        self.tags.setdefault(name, []).append((start, len(self.bm.verts)))

    def tube(self, pts, step=0.05, ref=(0, 0, 1), segs=SEGS, cap0="round", cap1="round",
             capmul=0.9):
        S = _samples(pts, step * DENS * self.dens)
        ref = Vector(ref)
        n = len(S)
        tans, us, vs = [], [], []
        for i in range(n):
            a = Vector(S[max(i - 1, 0)][:3])
            b = Vector(S[min(i + 1, n - 1)][:3])
            t = (b - a).normalized()
            if i == 0:
                u = ref - t * ref.dot(t)
                if u.length < 1e-4:
                    u = Vector((1, 0, 0)) - t * t.x
            else:
                u = us[-1] - t * us[-1].dot(t)
            u.normalize()
            v = t.cross(u)
            tans.append(t)
            us.append(u)
            vs.append(v)
        bm = self.bm

        def ring(c, u, v, rz, ry):
            return [bm.verts.new(c + u * (rz * math.cos(2 * math.pi * k / segs))
                                 + v * (ry * math.sin(2 * math.pi * k / segs)))
                    for k in range(segs)]

        rings = []
        for i in range(n):
            rings.append(ring(Vector(S[i][:3]), us[i], vs[i], S[i][3], S[i][4]))

        def cap(i, sign, kind):
            c = Vector(S[i][:3])
            rz, ry = S[i][3], S[i][4]
            L = max(rz, ry) * (capmul if kind == "round" else 3.0)
            out = []
            if kind == "round":
                for th in (math.radians(45), math.radians(72)):
                    out.append(ring(c + tans[i] * (sign * L * math.sin(th)), us[i], vs[i],
                                    rz * math.cos(th), ry * math.cos(th)))
            elif kind == "point":
                out.append(ring(c + tans[i] * (sign * L * 0.45), us[i], vs[i], rz * 0.55, ry * 0.55))
            apex = bm.verts.new(c + tans[i] * (sign * L))
            out.append([apex])
            return out

        def link(a, b):
            if len(a) == 1:
                for k in range(segs):
                    bm.faces.new((a[0], b[(k + 1) % segs], b[k]))
            elif len(b) == 1:
                for k in range(segs):
                    bm.faces.new((a[k], a[(k + 1) % segs], b[0]))
            else:
                for k in range(segs):
                    k2 = (k + 1) % segs
                    bm.faces.new((a[k], a[k2], b[k2], b[k]))

        chain = list(rings)
        if cap0 in ("round", "point"):
            chain = list(reversed(cap(0, -1, cap0))) + chain
        elif cap0 == "flat":
            bm.faces.new(rings[0])
        if cap1 in ("round", "point"):
            chain = chain + cap(n - 1, 1, cap1)
        elif cap1 == "flat":
            bm.faces.new(rings[-1])
        for a, b in zip(chain[:-1], chain[1:]):
            link(a, b)

    def ell(self, c, r, rot=None, u=14, v=8):
        m = Matrix.Diagonal(Vector((r[0], r[1], r[2], 1.0)))
        if rot:
            m = Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y") @ \
                Matrix.Rotation(rot[0], 4, "X") @ m
        m = Matrix.Translation(Vector(c)) @ m
        bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=1.0, matrix=m,
                                  calc_uvs=False)


def mirror(pts):
    return [(p[0], -p[1]) + tuple(p[2:]) for p in pts]


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def leg_front(b, x, y, H, rt, rk, rc, foot=True, hoof_len=0.04, step=0.04):
    """Ungulate/canid front leg. H = height of the leg top above ground."""
    pts = [(x, y, 0.95 * H, rt * 1.1, rt), (x + 0.005, y, 0.62 * H, rt * 0.8, rt * 0.75),
           (x + 0.02, y, 0.44 * H, rk * 1.05, rk), (x + 0.015, y, 0.22 * H, rc * 1.1, rc),
           (x + 0.015, y, 0.06 * H, rc * 1.4, rc * 1.15), (x + 0.02, y, 0.012, rc * 1.5, rc * 1.2)]
    b.tube(pts, step=step, ref=(1, 0, 0), segs=10, cap1="flat")
    if foot:
        b.ell((x + 0.03 + hoof_len * 0.3, y, rc * 0.8), (hoof_len, rc * 1.25, rc * 0.85), u=10, v=6)
    return (x + 0.02, y)


def leg_hind(b, x, y, H, rt, rk, rc, foot=True, hoof_len=0.04, step=0.04):
    pts = [(x, y, 0.95 * H, rt * 1.5, rt * 1.1), (x + 0.10 * H, y, 0.66 * H, rt * 1.1, rt),
           (x + 0.02 * H, y, 0.42 * H, rk * 1.2, rk), (x - 0.07 * H, y, 0.32 * H, rk * 1.1, rk),
           (x - 0.05 * H, y, 0.14 * H, rc * 1.1, rc), (x - 0.04 * H, y, 0.05 * H, rc * 1.4, rc * 1.15),
           (x - 0.03 * H, y, 0.012, rc * 1.5, rc * 1.2)]
    b.tube(pts, step=step, ref=(1, 0, 0), segs=10, cap1="flat")
    if foot:
        b.ell((x - 0.01 * H + hoof_len * 0.3, y, rc * 0.8), (hoof_len, rc * 1.25, rc * 0.85), u=10, v=6)
    return (x - 0.03 * H, y)


# ---------------------------------------------------------------- deer / elk

DEER_SPINE = [
    (-0.50, 0.85, 0.10, 0.08), (-0.40, 0.85, 0.17, 0.12), (-0.15, 0.80, 0.17, 0.12),
    (0.10, 0.80, 0.20, 0.13), (0.32, 0.80, 0.21, 0.13), (0.46, 0.90, 0.15, 0.10),
    (0.58, 1.03, 0.125, 0.085), (0.70, 1.16, 0.10, 0.07), (0.79, 1.25, 0.088, 0.068),
    (0.90, 1.255, 0.065, 0.052), (1.00, 1.215, 0.048, 0.042), (1.07, 1.19, 0.038, 0.036),
]


def build_cervid(b, elk=False):
    S = 1.5 if elk else 1.0
    neck_mul = [1, 1, 1, 1.05, 1.1, 1.2, 1.35, 1.45, 1.2, 1.2, 1.15, 1.1] if elk else [1] * 12
    sp = []
    for i, (x, z, rz, ry) in enumerate(DEER_SPINE):
        m = neck_mul[i]
        sp.append((x * S, 0.0, z * S, rz * S * (m if i >= 4 else 1) * (1.08 if elk and i < 5 else 1),
                   ry * S * (m if i >= 4 else 1) * (1.08 if elk and i < 5 else 1)))
    if elk:  # longer, heavier head and muzzle
        sp[-3] = (1.0 * S + 0.04, 0, 1.22 * S, 0.062 * S, 0.052 * S)
        sp[-2] = (1.10 * S + 0.04, 0, 1.17 * S, 0.048 * S, 0.044 * S)
        sp[-1] = (1.20 * S + 0.05, 0, 1.13 * S, 0.042 * S, 0.040 * S)
    b.tube(sp, step=0.05 * S)
    fat = 1.12 if elk else 1.0
    for s in (1, -1):
        b.ell((-0.36 * S, s * 0.10 * S, 0.74 * S), (0.17 * S, 0.07 * S * fat, 0.19 * S), rot=(0, 0.25, 0))
        b.ell((0.27 * S, s * 0.10 * S, 0.74 * S), (0.11 * S, 0.055 * S * fat, 0.15 * S), rot=(0, -0.2, 0))
    lr = 1.0 if not elk else 1.25
    feet = []
    for s in (1, -1):
        feet.append(leg_front(b, 0.30 * S, s * 0.09 * S, 0.74 * S, 0.060 * S * lr * 0.95, 0.034 * S * lr,
                              0.022 * S * lr, hoof_len=0.045 * S, step=0.05 * S))
        feet.append(leg_hind(b, -0.38 * S, s * 0.10 * S, 0.82 * S, 0.075 * S * lr * 0.9, 0.035 * S * lr,
                             0.021 * S * lr, hoof_len=0.045 * S, step=0.05 * S))
    # tail
    b.tube([(-0.50 * S, 0, 0.86 * S, 0.04 * S, 0.035 * S), (-0.57 * S, 0, 0.82 * S, 0.05 * S, 0.04 * S),
            (-0.59 * S, 0, 0.75 * S, 0.035 * S, 0.03 * S)], step=0.04 * S, segs=10, cap1="point")
    # ears
    for s in (1, -1):
        e = [(0.78 * S, s * 0.055 * S, 1.27 * S, 0.020 * S, 0.008 * S),
             (0.75 * S, s * 0.12 * S, 1.32 * S, 0.052 * S, 0.009 * S),
             (0.70 * S, s * 0.19 * S, 1.37 * S, 0.046 * S, 0.008 * S),
             (0.66 * S, s * 0.23 * S, 1.40 * S, 0.016 * S, 0.005 * S)]
        b.tube(e, step=0.03 * S, ref=(1, 0, 0), segs=8, cap1="point")
    # antlers
    for s in (1, -1):
        if not elk:
            beam = [(0.78, s * 0.045, 1.31, 0.013, 0.013), (0.76, s * 0.09, 1.46, 0.011, 0.011),
                    (0.71, s * 0.12, 1.60, 0.009, 0.009), (0.73, s * 0.13, 1.72, 0.005, 0.005)]
            b.tube(beam, step=0.04, segs=7, cap1="point")
            b.tube([(0.76, s * 0.09, 1.46, 0.008, 0.008), (0.84, s * 0.10, 1.55, 0.006, 0.006),
                    (0.90, s * 0.10, 1.63, 0.003, 0.003)], step=0.04, segs=7, cap1="point")
            b.tube([(0.71, s * 0.12, 1.58, 0.007, 0.007), (0.78, s * 0.14, 1.66, 0.005, 0.005),
                    (0.82, s * 0.15, 1.74, 0.003, 0.003)], step=0.04, segs=7, cap1="point")
        else:
            k = 1.5
            sh = 0.84
            bx, by, bz = 0.78 * k, 0.05 * k, 1.31 * k
            beam = [(0.78 * k, s * 0.05 * k, 1.31 * k, 0.026, 0.026),
                    (0.72 * k, s * 0.12 * k, 1.46 * k, 0.024, 0.024),
                    (0.58 * k, s * 0.20 * k, 1.60 * k, 0.020, 0.020),
                    (0.42 * k, s * 0.24 * k, 1.72 * k, 0.016, 0.016),
                    (0.30 * k, s * 0.22 * k, 1.78 * k, 0.012, 0.012),
                    (0.24 * k, s * 0.20 * k, 1.76 * k, 0.005, 0.005)]
            def shr(pts, s=s):
                return [(bx + (p[0] - bx) * sh, s * by + (p[1] - s * by) * sh, bz + (p[2] - bz) * sh, p[3], p[4])
                        for p in pts]
            beam = shr(beam)
            b.tube(beam, step=0.07, segs=9, cap1="point")
            tines = [  # brow, bez, trez, and two more
                [(0.75 * k, s * 0.10 * k, 1.42 * k, 0.017, 0.017), (0.92 * k, s * 0.12 * k, 1.56 * k, 0.012, 0.012),
                 (1.00 * k, s * 0.12 * k, 1.70 * k, 0.005, 0.005)],
                [(0.66 * k, s * 0.17 * k, 1.53 * k, 0.016, 0.016), (0.80 * k, s * 0.20 * k, 1.68 * k, 0.012, 0.012),
                 (0.84 * k, s * 0.21 * k, 1.84 * k, 0.005, 0.005)],
                [(0.52 * k, s * 0.22 * k, 1.66 * k, 0.014, 0.014), (0.58 * k, s * 0.25 * k, 1.84 * k, 0.010, 0.010),
                 (0.56 * k, s * 0.26 * k, 1.97 * k, 0.004, 0.004)],
                [(0.42 * k, s * 0.24 * k, 1.72 * k, 0.012, 0.012), (0.40 * k, s * 0.27 * k, 1.90 * k, 0.008, 0.008),
                 (0.36 * k, s * 0.28 * k, 2.02 * k, 0.003, 0.003)],
            ]
            for t in tines:
                t = shr(t)
                b.tube(t, step=0.07, segs=7, cap1="point")
    return feet


# ---------------------------------------------------------------- bear

def build_bear(b):
    sp = [(-0.72, 0, 0.60, 0.22, 0.22), (-0.58, 0, 0.66, 0.33, 0.32), (-0.30, 0, 0.70, 0.34, 0.33),
          (0.0, 0, 0.76, 0.36, 0.32), (0.20, 0, 0.80, 0.38, 0.31), (0.42, 0, 0.72, 0.31, 0.28),
          (0.58, 0, 0.67, 0.26, 0.25), (0.72, 0, 0.64, 0.23, 0.22), (0.85, 0, 0.60, 0.21, 0.22),
          (0.97, 0, 0.56, 0.155, 0.175), (1.05, 0, 0.53, 0.115, 0.135), (1.10, 0, 0.52, 0.09, 0.11)]
    b.tube(sp, step=0.06)
    feet = []
    for s in (1, -1):
        b.ell((-0.50, s * 0.25, 0.52), (0.22, 0.13, 0.26), rot=(0, 0.2, 0))
        b.ell((0.25, s * 0.18, 0.64), (0.15, 0.10, 0.20), rot=(0, -0.2, 0))
        pts = [(0.30, s * 0.17, 0.62, 0.15, 0.12), (0.32, s * 0.17, 0.38, 0.11, 0.095),
               (0.33, s * 0.17, 0.14, 0.085, 0.08), (0.34, s * 0.17, 0.04, 0.08, 0.08)]
        b.tube(pts, step=0.05, ref=(1, 0, 0), cap1="flat")
        b.ell((0.38, s * 0.17, 0.04), (0.11, 0.08, 0.042))
        feet.append((0.36, s * 0.17))
        pts = [(-0.50, s * 0.21, 0.58, 0.20, 0.15), (-0.45, s * 0.21, 0.40, 0.13, 0.11),
               (-0.46, s * 0.21, 0.16, 0.095, 0.085), (-0.46, s * 0.21, 0.05, 0.085, 0.085)]
        b.tube(pts, step=0.05, ref=(1, 0, 0), cap1="flat")
        b.ell((-0.38, s * 0.21, 0.045), (0.17, 0.085, 0.045))
        feet.append((-0.40, s * 0.21))
        b.ell((0.72, s * 0.15, 0.84), (0.05, 0.06, 0.065), u=10, v=6)
        for dy in (-0.04, 0.0, 0.04):
            b.tube([(0.47, s * 0.17 + dy, 0.03, 0.01, 0.008), (0.52, s * 0.17 + dy, 0.02, 0.004, 0.004)],
                   step=0.03, segs=6, ref=(0, 0, 1), cap1="point")
    b.ell((-0.74, 0, 0.64), (0.07, 0.06, 0.06))
    return feet


# ---------------------------------------------------------------- fox

def build_fox(b):
    sp = [(-0.30, 0, 0.31, 0.075, 0.065), (-0.22, 0, 0.31, 0.095, 0.075), (-0.05, 0, 0.30, 0.10, 0.075),
          (0.10, 0, 0.30, 0.10, 0.075), (0.20, 0, 0.31, 0.095, 0.07), (0.27, 0, 0.35, 0.07, 0.055),
          (0.33, 0, 0.42, 0.06, 0.05), (0.39, 0, 0.445, 0.055, 0.052), (0.47, 0, 0.425, 0.04, 0.04),
          (0.55, 0, 0.40, 0.025, 0.026), (0.60, 0, 0.39, 0.017, 0.018)]
    b.tube(sp, step=0.04, segs=12)
    feet = []
    for s in (1, -1):
        feet.append(leg_front(b, 0.18, s * 0.04, 0.30, 0.030, 0.017, 0.012, hoof_len=0.025, step=0.04))
        feet.append(leg_hind(b, -0.22, s * 0.05, 0.31, 0.04, 0.019, 0.012, hoof_len=0.025, step=0.04))
        b.tube([(0.37, s * 0.035, 0.465, 0.026, 0.008), (0.355, s * 0.06, 0.52, 0.030, 0.008),
                (0.33, s * 0.085, 0.60, 0.014, 0.006)],
               step=0.03, ref=(1, 0, 0), segs=8, cap1="point")
    b.tube([(-0.28, 0, 0.31, 0.04, 0.04), (-0.42, 0, 0.30, 0.075, 0.07), (-0.58, 0, 0.26, 0.10, 0.095),
            (-0.72, 0, 0.22, 0.095, 0.09), (-0.84, 0, 0.19, 0.05, 0.05), (-0.92, 0, 0.185, 0.012, 0.012)],
           step=0.05, segs=12, cap1="point")
    return feet


# ---------------------------------------------------------------- hare

def build_hare(b):
    sp = [(-0.22, 0, 0.17, 0.09, 0.07), (-0.15, 0, 0.22, 0.15, 0.09), (-0.02, 0, 0.20, 0.14, 0.085),
          (0.10, 0, 0.20, 0.10, 0.07), (0.17, 0, 0.22, 0.09, 0.065), (0.23, 0, 0.25, 0.08, 0.062),
          (0.29, 0, 0.275, 0.08, 0.065), (0.35, 0, 0.27, 0.07, 0.058), (0.40, 0, 0.25, 0.05, 0.047),
          (0.435, 0, 0.235, 0.035, 0.036)]
    b.tube(sp, step=0.03, segs=12)
    feet = []
    for s in (1, -1):
        b.tube([(0.14, s * 0.035, 0.18, 0.03, 0.025), (0.145, s * 0.035, 0.09, 0.018, 0.016),
                (0.15, s * 0.035, 0.02, 0.018, 0.016)], step=0.03, ref=(1, 0, 0), segs=8, cap1="flat")
        b.ell((0.17, s * 0.035, 0.012), (0.04, 0.02, 0.014), u=8, v=6)
        feet.append((0.16, s * 0.035))
        b.ell((-0.14, s * 0.07, 0.15), (0.13, 0.05, 0.11), u=12, v=8)
        b.tube([(-0.17, s * 0.075, 0.12, 0.05, 0.03), (-0.22, s * 0.075, 0.06, 0.03, 0.025),
                (-0.20, s * 0.075, 0.03, 0.025, 0.022), (-0.10, s * 0.075, 0.016, 0.022, 0.02),
                (0.0, s * 0.075, 0.012, 0.018, 0.016)], step=0.03, ref=(0, 0, 1), segs=8, cap1="round")
        feet.append((-0.10, s * 0.075))
        b.tube([(0.29, s * 0.03, 0.30, 0.020, 0.006), (0.23, s * 0.05, 0.40, 0.032, 0.007),
                (0.16, s * 0.07, 0.50, 0.026, 0.006), (0.12, s * 0.075, 0.55, 0.008, 0.004)],
               step=0.04, ref=(1, 0, 0), segs=8, cap1="point")
    b.ell((-0.25, 0, 0.19), (0.045, 0.04, 0.045), u=10, v=6)
    return feet


# ---------------------------------------------------------------- birds

def bird_feet(b, x, y, z0, r, toe, step=0.03):
    b.tube([(x, y, z0, r, r), (x, y, 0.012, r * 0.9, r * 0.9)], step=step, ref=(1, 0, 0), segs=6, cap1="round")
    for ang in (-0.45, 0.0, 0.45):
        d = Vector((math.cos(ang), math.sin(ang), 0))
        b.tube([(x, y, 0.008, r * 0.8, r * 0.7), (x + d.x * toe, y + d.y * toe, 0.006, r * 0.5, r * 0.5)],
               step=toe, segs=5, cap1="point")
    b.tube([(x, y, 0.008, r * 0.7, r * 0.6), (x - toe * 0.5, y, 0.006, r * 0.4, r * 0.4)],
           step=toe, segs=5, cap1="point")
    return (x, y)


def build_crow(b):
    sp = [(-0.11, 0, 0.17, 0.025, 0.03), (-0.04, 0, 0.18, 0.06, 0.055), (0.04, 0, 0.20, 0.078, 0.066),
          (0.11, 0, 0.23, 0.066, 0.056), (0.15, 0, 0.265, 0.042, 0.04), (0.175, 0, 0.285, 0.046, 0.042),
          (0.205, 0, 0.29, 0.04, 0.038)]
    b.tube(sp, step=0.03, segs=12)
    feet = []
    for s in (1, -1):
        feet.append(bird_feet(b, 0.03, s * 0.03, 0.13, 0.007, 0.045))
        b.tube([(0.07, s * 0.058, 0.215, 0.045, 0.012), (-0.04, s * 0.062, 0.20, 0.045, 0.014),
                (-0.14, s * 0.052, 0.18, 0.035, 0.012), (-0.22, s * 0.045, 0.16, 0.012, 0.008)],
               step=0.03, ref=(0, 0, 1), segs=10, cap1="point")
    b.tube([(-0.11, 0, 0.17, 0.008, 0.035), (-0.20, 0, 0.158, 0.008, 0.045), (-0.29, 0, 0.145, 0.007, 0.042)],
           step=0.04, ref=(0, 0, 1), segs=10, cap1="round", capmul=1.5)
    b.tube([(0.20, 0, 0.292, 0.021, 0.019), (0.245, 0, 0.283, 0.016, 0.013), (0.285, 0, 0.268, 0.003, 0.003)],
           step=0.02, ref=(0, 0, 1), segs=8, cap1="point")
    return feet


def build_owl(b):
    sp = [(-0.03, 0, 0.05, 0.05, 0.05), (-0.02, 0, 0.14, 0.12, 0.115), (0.0, 0, 0.25, 0.135, 0.13),
          (0.015, 0, 0.34, 0.125, 0.125), (0.03, 0, 0.40, 0.11, 0.12)]
    b.tube(sp, step=0.04, ref=(1, 0, 0), segs=18)
    b.ell((0.04, 0, 0.44), (0.105, 0.12, 0.095), u=18, v=12)
    st = b.mark("front")
    b.ell((0.10, 0, 0.44), (0.045, 0.116, 0.10), u=20, v=12)
    b.tag("front", st)
    b.tube([(0.125, 0, 0.435, 0.014, 0.012), (0.15, 0, 0.415, 0.003, 0.003)], step=0.015, ref=(0, 0, 1),
           segs=8, cap1="point")
    feet = []
    for s in (1, -1):
        b.tube([(0.03, s * 0.075, 0.51, 0.014, 0.014), (0.01, s * 0.095, 0.545, 0.010, 0.010),
                (0.0, s * 0.10, 0.575, 0.002, 0.002)], step=0.02, segs=6, cap1="point")
        b.tube([(0.01, s * 0.118, 0.37, 0.06, 0.02), (-0.04, s * 0.126, 0.24, 0.075, 0.022),
                (-0.09, s * 0.108, 0.10, 0.05, 0.018), (-0.13, s * 0.09, 0.025, 0.01, 0.01)],
               step=0.04, ref=(1, 0, 0), segs=10, cap1="point")
        b.tube([(0.03, s * 0.045, 0.10, 0.03, 0.025), (0.04, s * 0.045, 0.015, 0.026, 0.022)],
               step=0.03, ref=(1, 0, 0), segs=10, cap1="flat")
        feet.append(bird_feet(b, 0.04, s * 0.045, 0.03, 0.012, 0.05))
    b.tube([(-0.04, 0, 0.12, 0.008, 0.05), (-0.10, 0, 0.06, 0.008, 0.055), (-0.15, 0, 0.02, 0.007, 0.05)],
           step=0.04, ref=(1, 0, 0), segs=10, cap1="round")
    return feet


def build_heron(b):
    sp = [(-0.22, 0, 0.55, 0.025, 0.035), (-0.12, 0, 0.58, 0.07, 0.06), (0.0, 0, 0.62, 0.095, 0.07),
          (0.10, 0, 0.66, 0.09, 0.065), (0.15, 0, 0.73, 0.055, 0.05), (0.11, 0, 0.80, 0.034, 0.031),
          (0.12, 0, 0.88, 0.025, 0.023), (0.19, 0, 0.935, 0.025, 0.023), (0.225, 0, 0.965, 0.030, 0.030),
          (0.27, 0, 0.972, 0.027, 0.026)]
    b.tube(sp, step=0.035, segs=12)
    b.tube([(0.27, 0, 0.972, 0.018, 0.016), (0.35, 0, 0.962, 0.013, 0.012), (0.43, 0, 0.945, 0.003, 0.003)],
           step=0.04, ref=(0, 0, 1), segs=8, cap1="point")
    b.tube([(0.21, 0, 0.99, 0.004, 0.004), (0.12, 0, 0.99, 0.004, 0.004), (0.04, 0, 0.965, 0.002, 0.002)],
           step=0.04, segs=5, cap1="point")
    feet = []
    for s in (1, -1):
        b.tube([(0.0, s * 0.035, 0.58, 0.02, 0.02), (0.01, s * 0.035, 0.42, 0.011, 0.011),
                (0.005, s * 0.035, 0.30, 0.010, 0.010), (0.0, s * 0.035, 0.14, 0.008, 0.008),
                (0.0, s * 0.035, 0.012, 0.008, 0.008)],
               step=0.06, ref=(1, 0, 0), segs=7, cap1="round")
        feet.append(bird_feet(b, 0.0, s * 0.035, 0.1, 0.008, 0.08))
        b.tube([(0.10, s * 0.075, 0.675, 0.075, 0.016), (-0.05, s * 0.078, 0.62, 0.075, 0.020),
                (-0.18, s * 0.06, 0.56, 0.05, 0.016), (-0.30, s * 0.05, 0.53, 0.012, 0.008)],
               step=0.04, ref=(0, 0, 1), segs=10, cap1="point")
    b.tube([(-0.22, 0, 0.55, 0.008, 0.03), (-0.30, 0, 0.535, 0.008, 0.035), (-0.36, 0, 0.52, 0.006, 0.03)],
           step=0.04, ref=(0, 0, 1), segs=8, cap1="round", capmul=1.5)
    return feet


# ---------------------------------------------------------------- painting

def sm(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blob(X, Z, cx, cz, rx, rz, soft=0.5):
    d = np.sqrt(((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2)
    return 1.0 - sm(d, 1.0 - soft, 1.0)


def paint(img, col, m):
    m = m[..., None]
    return img * (1 - m) + np.array(col, dtype=np.float32) * m


def noise(rng, cx, cy, size=TEX, wrap=True):
    g = rng.random((cy + 2, cx + 2)).astype(np.float32)
    if wrap:
        g[-1, :] = g[0, :]
        g[:, -1] = g[:, 0]
    xs = np.linspace(0, cx, size, endpoint=False, dtype=np.float32)
    ys = np.linspace(0, cy, size, endpoint=False, dtype=np.float32)
    x0 = xs.astype(int)
    y0 = ys.astype(int)
    fx = xs - x0
    fy = ys - y0
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = g[np.ix_(y0, x0)]
    bq = g[np.ix_(y0, x0 + 1)]
    c = g[np.ix_(y0 + 1, x0)]
    d = g[np.ix_(y0 + 1, x0 + 1)]
    top = a * (1 - fx)[None, :] + bq * fx[None, :]
    bot = c * (1 - fx)[None, :] + d * fx[None, :]
    return top * (1 - fy)[:, None] + bot * fy[:, None]


def fur_height(rng, streak_x=True):
    h = noise(rng, 64, 512) if streak_x else noise(rng, 512, 64)
    h = h * 0.5 + noise(rng, 128, 1024 // 1) * 0.3 + noise(rng, 24, 24) * 0.2
    return h


def feather_height(period_u, period_v):
    """Staggered scallop rows. Returns height (1 at feather centre, 0 at overlap edge)."""
    yy, xx = np.mgrid[0:TEX, 0:TEX].astype(np.float32)
    row = np.floor(yy / period_v)
    lu = ((xx + (row % 2) * period_u * 0.5) / period_u) % 1.0 - 0.5
    lv = (yy / period_v) % 1.0
    d = np.sqrt((lu * 1.0) ** 2 + ((1.0 - lv) * 0.55) ** 2)
    return 1.0 - sm(d, 0.18, 0.55)


def to_normal(h, strength):
    gy, gx = np.gradient(h.astype(np.float32))
    n = np.dstack([-gx * strength, -gy * strength, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def lum(img):
    return float((img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722).mean())


def base_fur(X, Z, rng, c_top, c_bot, z_top, z_bot, var=0.16):
    t = sm(Z, z_bot, z_top)
    img = np.empty(X.shape + (3,), dtype=np.float32)
    for i in range(3):
        img[..., i] = c_bot[i] + (c_top[i] - c_bot[i]) * t
    n = noise(rng, 6, 6) * 0.5 + noise(rng, 16, 16) * 0.3 + noise(rng, 100, 700) * 0.35
    img *= (1.0 + var * (n - 0.58))[..., None]
    return img


def paint_cervid(X, Z, rng, elk):
    # X, Z normalised to deer design (metres, shoulder ~1.0). Returns albedo and fur-height.
    if elk:
        top, belly = (0.60, 0.46, 0.30), (0.78, 0.66, 0.48)
        dark, leg = (0.30, 0.20, 0.14), (0.30, 0.21, 0.15)
    else:
        top, belly = (0.52, 0.35, 0.21), (0.84, 0.77, 0.66)
        dark, leg = (0.42, 0.29, 0.19), (0.40, 0.30, 0.22)
    img = base_fur(X, Z, rng, top, belly, 0.98, 0.64)
    # legs below belly: gradual darker, hooves black
    legm = 1 - sm(Z, 0.34, 0.66)
    img = paint(img, leg, legm * 0.85)
    img = paint(img, (0.78, 0.72, 0.62) if not elk else (0.25, 0.17, 0.12), blob(X, Z, 0.30, 0.16, 0.2, 0.1, 0.9) * 0.0)
    img = paint(img, (0.10, 0.08, 0.07), 1 - sm(Z, 0.02, 0.05))
    if elk:
        front = sm(X, 0.36, 0.52) * sm(Z, 0.78, 0.92)
        img = paint(img, dark, front * 0.95)
        legs_d = (1 - sm(Z, 0.40, 0.66))
        img = paint(img, dark, legs_d * 0.9)
        img = paint(img, (0.80, 0.66, 0.44), blob(X, Z, -0.55, 0.78, 0.17, 0.2, 0.7) * 0.9)
    else:
        img = paint(img, (0.95, 0.93, 0.90), blob(X, Z, -0.50, 0.78, 0.15, 0.2, 0.45) * 0.97)
        # lighter inner thigh/ankle bands
        img = paint(img, (0.62, 0.50, 0.38), blob(X, Z, -0.30, 0.55, 0.12, 0.07, 0.8) * 0.5)
        # throat/cheek/muzzle
        img = paint(img, (0.88, 0.82, 0.72), blob(X, Z, 0.95, 1.20, 0.10, 0.045, 0.6) * 0.8)
        img = paint(img, (0.90, 0.86, 0.80), blob(X, Z, 1.01, 1.215, 0.04, 0.03, 0.6) * 0.9)
    # face detail
    img = paint(img, (0.12, 0.09, 0.08), blob(X, Z, 1.065, 1.2, 0.022, 0.022, 0.5))       # nose
    img = paint(img, (0.15, 0.10, 0.08), blob(X, Z, 0.89, 1.285, 0.045, 0.026, 0.8) * 0.55)  # eye shade
    img = paint(img, (0.04, 0.03, 0.03), blob(X, Z, 0.915, 1.285, 0.012, 0.011, 0.3))     # eye
    img = paint(img, (0.9, 0.85, 0.7), blob(X, Z, 0.919, 1.289, 0.003, 0.003, 0.3))
    # ear inner lighter / dark tip
    ear = blob(X, Z, 0.72, 1.33, 0.07, 0.07, 0.6)
    img = paint(img, (0.62, 0.48, 0.36) if not elk else (0.40, 0.29, 0.21), ear * 0.55)
    # antlers
    ant = sm(Z, 1.445, 1.47) * sm(X, 0.1, 0.2) if not elk else sm(Z, 1.42, 1.46) * sm(X, 0.1, 0.2)
    img = paint(img, (0.80, 0.70, 0.52), ant)
    h = fur_height(rng)
    return img, h


def paint_bear(X, Z, rng, F=None):
    img = base_fur(X, Z, rng, (0.40, 0.28, 0.18), (0.34, 0.24, 0.15), 1.1, 0.3, var=0.34)
    img = paint(img, (0.55, 0.42, 0.29), blob(X, Z, 0.1, 1.0, 0.5, 0.25, 0.9) * 0.45)
    img = paint(img, (0.26, 0.18, 0.12), 1 - sm(Z, 0.12, 0.40))
    img = paint(img, (0.62, 0.48, 0.34), blob(X, Z, 1.03, 0.545, 0.10, 0.065, 0.7))
    img = paint(img, (0.10, 0.07, 0.06), blob(X, Z, 1.105, 0.52, 0.026, 0.024, 0.5))
    img = paint(img, (0.04, 0.03, 0.03), blob(X, Z, 0.91, 0.64, 0.013, 0.012, 0.3))
    img = paint(img, (0.22, 0.15, 0.10), blob(X, Z, 0.90, 0.645, 0.04, 0.028, 0.8) * 0.5)
    img = paint(img, (0.74, 0.68, 0.56), blob(X, Z, 0.50, 0.03, 0.06, 0.03, 0.5) * 0.9)
    return img, fur_height(rng)


def paint_fox(X, Z, rng, F=None):
    img = base_fur(X, Z, rng, (0.80, 0.38, 0.12), (0.88, 0.60, 0.30), 0.40, 0.22, var=0.22)
    belly = (0.95, 0.92, 0.86)
    img = paint(img, belly, blob(X, Z, 0.05, 0.215, 0.38, 0.05, 0.7) * 0.95)
    img = paint(img, belly, blob(X, Z, 0.30, 0.34, 0.07, 0.06, 0.7) * 0.9)                  # chest/throat
    img = paint(img, belly, blob(X, Z, 0.48, 0.40, 0.07, 0.03, 0.7) * 0.9)                  # cheek/muzzle
    img = paint(img, (0.12, 0.09, 0.08), (1 - sm(Z, 0.14, 0.22)) * 0.97)                    # black socks
    img = paint(img, (0.12, 0.09, 0.08), blob(X, Z, 0.596, 0.39, 0.015, 0.014, 0.5))        # nose
    img = paint(img, (0.04, 0.03, 0.02), blob(X, Z, 0.45, 0.44, 0.011, 0.007, 0.3))        # eye
    img = paint(img, (0.12, 0.09, 0.08), blob(X, Z, 0.35, 0.56, 0.03, 0.06, 0.7) * 0.85)    # ear back
    img = paint(img, (0.95, 0.92, 0.86), blob(X, Z, -0.90, 0.19, 0.08, 0.05, 0.7) * 0.97)   # tail tip
    img = paint(img, (0.95, 0.9, 0.84), blob(X, Z, -0.60, 0.20, 0.2, 0.05, 0.7) * 0.4)
    return img, fur_height(rng)


def paint_hare(X, Z, rng, F=None):
    img = base_fur(X, Z, rng, (0.56, 0.44, 0.30), (0.80, 0.72, 0.60), 0.32, 0.10, var=0.22)
    img = paint(img, (0.35, 0.27, 0.19), blob(X, Z, 0.0, 0.31, 0.3, 0.04, 0.8) * 0.5)
    img = paint(img, (0.92, 0.88, 0.80), blob(X, Z, 0.0, 0.07, 0.4, 0.07, 0.8) * 0.9)
    img = paint(img, (0.96, 0.94, 0.9), blob(X, Z, -0.25, 0.19, 0.05, 0.05, 0.6))             # tail
    img = paint(img, (0.88, 0.84, 0.76), blob(X, Z, 0.39, 0.24, 0.06, 0.035, 0.6) * 0.8)
    img = paint(img, (0.10, 0.08, 0.07), blob(X, Z, 0.432, 0.235, 0.014, 0.012, 0.5))
    img = paint(img, (0.35, 0.22, 0.10), blob(X, Z, 0.34, 0.285, 0.026, 0.02, 0.5))           # eye amber
    img = paint(img, (0.04, 0.03, 0.03), blob(X, Z, 0.342, 0.285, 0.012, 0.012, 0.3))
    img = paint(img, (0.12, 0.09, 0.07), sm(Z, 0.47, 0.52) * 0.95)                           # ear tips
    img = paint(img, (0.78, 0.62, 0.55), blob(X, Z, 0.2, 0.42, 0.06, 0.07, 0.8) * 0.3)
    return img, fur_height(rng)


def paint_crow(X, Z, rng, F=None):
    t = sm(Z, 0.12, 0.30)
    img = np.empty(X.shape + (3,), np.float32)
    lo, hi = np.array((0.17, 0.18, 0.21)), np.array((0.26, 0.29, 0.38))
    for i in range(3):
        img[..., i] = lo[i] + (hi[i] - lo[i]) * t
    img *= (1 + 0.2 * (noise(rng, 18, 18) - 0.5))[..., None]
    img = paint(img, (0.22, 0.23, 0.30), blob(X, Z, -0.04, 0.2, 0.22, 0.04, 0.8) * 0.6)
    img = paint(img, (0.13, 0.12, 0.13), (1 - sm(Z, 0.015, 0.14)) * 0.95)                    # legs
    img = paint(img, (0.12, 0.12, 0.13), blob(X, Z, 0.245, 0.282, 0.05, 0.012, 0.5))         # beak
    img = paint(img, (0.03, 0.03, 0.03), blob(X, Z, 0.19, 0.30, 0.009, 0.009, 0.3))
    img = paint(img, (0.60, 0.62, 0.70), blob(X, Z, 0.1925, 0.3035, 0.0025, 0.0025, 0.3))
    img = paint(img, (0.14, 0.14, 0.16), blob(X, Z, -0.20, 0.158, 0.1, 0.02, 0.7) * 0.8)     # tail/wing tips
    h = feather_height(16, 11)
    img *= (0.84 + 0.22 * h)[..., None]
    return img, h


def paint_owl(X, Z, rng, F=None):
    cream, brown = np.array((0.80, 0.68, 0.50)), np.array((0.42, 0.30, 0.19))
    img = np.empty(X.shape + (3,), np.float32)
    t = sm(Z, 0.10, 0.36)
    for i in range(3):
        img[..., i] = cream[i] + (brown[i] - cream[i]) * (t * 0.55 + 0.3)
    bars = 0.5 + 0.5 * np.sin(Z * 170.0 + noise(rng, 20, 20) * 4)
    belly = blob(X, Z, 0.04, 0.22, 0.10, 0.16, 0.6)
    chest = sm(X, 0.04, 0.10) * sm(Z, 0.06, 0.12) * (1 - sm(Z, 0.37, 0.40))
    img = paint(img, (0.84, 0.74, 0.56), chest * 0.9)
    img = paint(img, (0.46, 0.33, 0.21), (belly + chest) * bars * 0.5)
    spots = noise(rng, 40, 80)
    wing = sm(-X, 0.04, 0.07) * sm(Z, 0.04, 0.12) * (1 - sm(Z, 0.36, 0.42))
    img = paint(img, (0.34, 0.24, 0.15), wing * 0.9)
    img = paint(img, (0.74, 0.62, 0.45), wing * (spots > 0.72) * 0.7)
    img *= (1 + 0.2 * (noise(rng, 24, 24) - 0.5))[..., None]
    img = paint(img, (0.50, 0.40, 0.27), (1 - sm(Z, 0.02, 0.09)) * 0.7)
    img = paint(img, (0.34, 0.24, 0.15), blob(X, Z, 0.01, 0.54, 0.05, 0.04, 0.5) * 0.9)
    img = paint(img, (0.16, 0.11, 0.08), blob(X, Z, 0.10, 0.44, 0.06, 0.012, 0.5) * 0.0)
    # side eye shade on head (side UV)
    h = feather_height(24, 16)
    img *= (0.90 + 0.14 * h)[..., None]
    # front face region (front UV, u > 0.62): coordinates Y (lateral), Z
    fr = (F["U"] > 0.62).astype(np.float32)
    Y = np.abs(F["Y"])
    face = np.empty_like(img)
    face[...] = (0.46, 0.33, 0.21)
    face = paint(face, (0.88, 0.80, 0.64), blob(Y, Z, 0.0, 0.44, 0.10, 0.09, 0.35))
    face = paint(face, (0.34, 0.24, 0.15), blob(Y, Z, 0.043, 0.452, 0.034, 0.036, 0.6) * 0.85)
    face = paint(face, (0.80, 0.55, 0.12), blob(Y, Z, 0.043, 0.452, 0.021, 0.023, 0.25))
    face = paint(face, (0.03, 0.03, 0.03), blob(Y, Z, 0.043, 0.452, 0.012, 0.013, 0.2))
    face = paint(face, (0.95, 0.92, 0.85), blob(Y, Z, 0.037, 0.460, 0.004, 0.004, 0.3))
    face = paint(face, (0.72, 0.62, 0.42), blob(Y, Z, 0.0, 0.425, 0.014, 0.022, 0.5))
    face *= (1 + 0.15 * (noise(rng, 60, 60) - 0.5))[..., None]
    img = img * (1 - fr[..., None]) + face * fr[..., None]
    return img, h


def paint_heron(X, Z, rng, F=None):
    img = np.empty(X.shape + (3,), np.float32)
    blue, white = np.array((0.30, 0.36, 0.46)), np.array((0.56, 0.58, 0.58))
    for i in range(3):
        img[..., i] = white[i]
    # back/wings blue-grey
    img = paint(img, tuple(blue), blob(X, Z, -0.08, 0.60, 0.26, 0.08, 0.7) * 0.95)
    img = paint(img, (0.30, 0.34, 0.40), blob(X, Z, -0.2, 0.55, 0.14, 0.04, 0.8) * 0.6)    # flight feathers
    img = paint(img, (0.74, 0.77, 0.82), blob(X, Z, 0.02, 0.60, 0.17, 0.045, 0.8) * 0.0)
    # neck streaks
    img = paint(img, (0.82, 0.83, 0.82), blob(X, Z, 0.14, 0.82, 0.07, 0.17, 0.5) * 0.85)
    streak = np.clip(np.sin(Z * 250.0 + noise(rng, 16, 16) * 5) * 4, 0, 1)
    img = paint(img, (0.30, 0.30, 0.32), blob(X, Z, 0.12, 0.80, 0.06, 0.12, 0.6) * streak * 0.6)
    # head: white cheek, black crown & plume
    img = paint(img, (0.08, 0.08, 0.1), blob(X, Z, 0.17, 0.99, 0.12, 0.025, 0.5) * 0.95)
    img = paint(img, (0.06, 0.06, 0.08), blob(X, Z, 0.24, 0.978, 0.03, 0.02, 0.5) * 0.4)
    img = paint(img, (0.86, 0.66, 0.22), blob(X, Z, 0.35, 0.958, 0.09, 0.016, 0.6))          # bill
    img = paint(img, (0.86, 0.66, 0.22), blob(X, Z, 0.255, 0.964, 0.02, 0.018, 0.4) * 0.0)
    img = paint(img, (0.04, 0.04, 0.04), blob(X, Z, 0.265, 0.975, 0.008, 0.008, 0.3))
    img = paint(img, (0.80, 0.75, 0.20), blob(X, Z, 0.265, 0.975, 0.014, 0.014, 0.4) * 0.8)
    img = paint(img, (0.04, 0.04, 0.04), blob(X, Z, 0.265, 0.975, 0.0075, 0.0075, 0.3))
    # legs
    img = paint(img, (0.46, 0.46, 0.30), (1 - sm(Z, 0.40, 0.58)) * 0.95)
    img = paint(img, (0.28, 0.28, 0.22), (1 - sm(Z, 0.02, 0.1)) * 0.8)
    img *= (1 + 0.16 * (noise(rng, 20, 20) - 0.5))[..., None]
    h = feather_height(14, 10)
    img *= (0.90 + 0.14 * h)[..., None]
    return img, h


# ---------------------------------------------------------------- species table

SPECIES = [
    dict(name="deer", zcap=1.12, kind="shoulder", target=1.00, sx=0.2, slot="Fur", build=lambda b: build_cervid(b, False),
         paint=lambda X, Z, r, F: paint_cervid(X, Z, r, False), ns=1.2, seed=1),
    dict(name="elk", zcap=1.7, kind="shoulder", target=1.50, sx=0.3, slot="Fur", build=lambda b: build_cervid(b, True),
         paint=lambda X, Z, r, F: paint_cervid(X / 1.5, Z / 1.5, r, True), ns=1.2, seed=2),
    dict(name="bear", zcap=1.3, kind="shoulder", target=1.10, sx=0.12, slot="Fur", build=build_bear,
         paint=paint_bear, ns=1.5, seed=3),
    dict(name="fox", zcap=0.5, kind="shoulder", target=0.40, sx=0.05, slot="Fur", build=build_fox,
         paint=paint_fox, ns=1.4, seed=4),
    dict(name="hare", zcap=0.4, kind="shoulder", target=0.30, sx=0.1, slot="Fur", build=build_hare,
         paint=paint_hare, ns=1.4, seed=5),
    dict(name="crow", dens=0.7, kind="length", target=0.45, slot="Feather", build=build_crow, paint=paint_crow,
         ns=2.5, seed=6),
    dict(name="owl", kind="height", target=0.50, slot="Feather", build=build_owl, paint=paint_owl,
         ns=2.5, seed=7),
    dict(name="heron", kind="height", target=1.00, slot="Feather", build=build_heron, paint=paint_heron,
         ns=2.5, seed=8),
]


# ---------------------------------------------------------------- scene helpers

def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras):
        for m in list(coll):
            coll.remove(m)


def save_image(name, arr, path, colourspace):
    img = bpy.data.images.new(name, TEX, TEX, alpha=False)
    img.colorspace_settings.name = colourspace
    a = np.clip(arr, 0, 1).astype(np.float32)
    rgba = np.dstack([a, np.ones(a.shape[:2], np.float32)])
    img.pixels.foreach_set(rgba[::-1].ravel())  # array row 0 = top; image row 0 = bottom
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def make_material(slot, alb, nor):
    mat = bpy.data.materials.new(name=slot)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    t1 = nt.nodes.new("ShaderNodeTexImage")
    t1.image = alb
    nt.links.new(t1.outputs["Color"], bsdf.inputs["Base Color"])
    t2 = nt.nodes.new("ShaderNodeTexImage")
    t2.image = nor
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t2.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.nodes.active = t1
    return mat


def render_preview(obj, name, dims, centre):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 900, 620
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.shadow_intensity = 0.4
    sh.background_type = "VIEWPORT"
    sh.background_color = (0.62, 0.74, 0.86)
    sc.display.render_aa = "8"
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("w") if not bpy.data.worlds else bpy.data.worlds[0]
    world.use_nodes = False
    world.color = (0.62, 0.74, 0.86)
    sc.world = world
    # ground plane
    gm = bpy.data.meshes.new("ground")
    gb = bmesh.new()
    gb.faces.new([gb.verts.new(v) for v in ((-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0))])
    gb.to_mesh(gm)
    gb.free()
    g = bpy.data.objects.new("ground", gm)
    sc.collection.objects.link(g)
    gmat = bpy.data.materials.new("ground")
    gmat.diffuse_color = (0.30, 0.38, 0.18, 1.0)
    gm.materials.append(gmat)
    cam = bpy.data.cameras.new("cam")
    cam.lens = 60
    co = bpy.data.objects.new("cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    R = max(dims[2] * 3.5, dims[0] * 2.5)
    tgt = Vector(centre)
    paths = []
    for tag, d in (("side", Vector((0, -1, 0.06))), ("q34", Vector((0.85, -0.85, 0.30)))):
        co.location = tgt + d.normalized() * R
        co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
        p = os.path.join(tempfile.gettempdir(), "creature_%s_%s.png" % (name, tag))
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    ims = []
    for p in paths:
        im = bpy.data.images.load(p)
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
        ims.append(a)
        bpy.data.images.remove(im)
    both = np.hstack(ims)
    out = bpy.data.images.new(name + "_preview", both.shape[1], both.shape[0], alpha=False)
    out.pixels.foreach_set(both.ravel())
    out.filepath_raw = os.path.join(OUT, name + "_preview.png")
    out.file_format = "PNG"
    out.save()
    bpy.data.objects.remove(g, do_unlink=True)
    bpy.data.objects.remove(co, do_unlink=True)


def build_species(sp):
    clear_scene()
    b = Builder()
    b.dens = sp.get("dens", 1.0)
    feet = sp["build"](b)
    bm = b.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(sp["name"])
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(sp["name"], mesh)
    bpy.context.scene.collection.objects.link(obj)

    co = np.array([v.co[:] for v in mesh.vertices], dtype=np.float64)
    fx = float(np.mean([f[0] for f in feet]))
    fy = float(np.mean([f[1] for f in feet]))
    zmin_d = float(co[:, 2].min())
    # measure for scale
    if sp["kind"] == "shoulder":
        band = co[(np.abs(co[:, 0] - sp["sx"]) <= 0.05) & (co[:, 2] < sp["zcap"])]
        raw = float(band[:, 2].max() - zmin_d)
    elif sp["kind"] == "height":
        raw = float(co[:, 2].max() - zmin_d)
    else:
        raw = float(co[:, 0].max() - co[:, 0].min())
    k = sp["target"] / raw
    new = np.empty_like(co)
    new[:, 0] = (co[:, 0] - fx) * k
    new[:, 1] = (co[:, 1] - fy) * k
    new[:, 2] = (co[:, 2] - zmin_d) * k
    mesh.vertices.foreach_set("co", new.astype(np.float32).ravel())
    mesh.update()
    for p in mesh.polygons:
        p.use_smooth = True

    # UV0: side planar projection, uniform scale
    xmin, zmin = float(new[:, 0].min()), 0.0
    S = float(max(new[:, 0].max() - xmin, new[:, 2].max())) * 1.02
    li = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", li)
    uv = np.stack([(new[li, 0] - xmin) / S, (new[li, 2] - zmin) / S], axis=1).astype(np.float32)
    fmask = np.zeros(len(new), dtype=bool)
    for a, e in b.tags.get("front", []):
        fmask[a:e] = True
    fl = fmask[li]
    uv[fl, 0] = (0.80 + new[li[fl], 1] / S).astype(np.float32)
    layer = mesh.uv_layers.new(name="UV0")
    layer.data.foreach_set("uv", uv.ravel())

    # textures (grid in design coordinates)
    uu = (np.arange(TEX, dtype=np.float32) + 0.5) / TEX
    Xf = xmin + uu * S
    Zf = uu * S
    Xd = np.broadcast_to((Xf / k + fx)[None, :], (TEX, TEX))
    Zd = np.broadcast_to((Zf / k + zmin_d)[::-1][:, None], (TEX, TEX))  # row 0 = top of image
    rng = np.random.default_rng(1000 + sp["seed"])
    Yd = np.broadcast_to(((uu - 0.80) * S / k + fy)[None, :], (TEX, TEX))
    Uu = np.broadcast_to(uu[None, :], (TEX, TEX))
    F = dict(Y=np.ascontiguousarray(Yd), U=np.ascontiguousarray(Uu))
    alb, hgt = sp["paint"](np.ascontiguousarray(Xd), np.ascontiguousarray(Zd), rng, F)
    nrm = to_normal(hgt, sp["ns"] * 12.0 if sp["slot"] == "Fur" else sp["ns"] * 8.0)
    ml = lum(alb)
    alb_img = save_image(sp["name"], alb, os.path.join(OUT, sp["name"] + ".png"), "sRGB")
    nor_img = save_image(sp["name"] + "_n", nrm, os.path.join(OUT, sp["name"] + "_n.png"), "Non-Color")
    mat = make_material(sp["slot"], alb_img, nor_img)
    mesh.materials.append(mat)

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    dims = new.max(axis=0) - new.min(axis=0)
    tris = len(mesh.polygons)

    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, sp["name"] + ".fbx"), use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="X", axis_up="Z", bake_space_transform=False,
        use_mesh_modifiers=False, mesh_smooth_type="FACE",
        path_mode="RELATIVE", embed_textures=False, add_leaf_bones=False, bake_anim=False)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, sp["name"] + ".glb"), export_format="GLB",
                              use_selection=True, export_apply=False)

    centre = ((new[:, 0].max() + new[:, 0].min()) / 2, 0.0, float(new[:, 2].max()) * 0.5)
    render_preview(obj, sp["name"], dims, centre)

    print("SPECIES %-6s tris=%5d dims_m=(%.3f, %.3f, %.3f) %s=%.3f lum=%.3f"
          % (sp["name"], tris, dims[0], dims[1], dims[2], sp["kind"], sp["target"], ml))
    return dict(name=sp["name"], tris=tris, dims=dims, kind=sp["kind"], target=sp["target"],
                slot=sp["slot"], lum=ml)


def write_readme(rows):
    lines = [
        "# Creature meshes (ArtSource/Authored/Creatures)",
        "",
        "Generated by `Tools/Author-Creatures.py` (Blender 5.2 headless, deterministic, run from repo root).",
        "",
        "Conventions: metres, Z-up, origin on the ground between the feet, facing +X.",
        "One combined mesh per species, one material slot (`Fur` mammals / `Feather` birds), smooth shading.",
        "Per species `<s>`:",
        "- `<s>.fbx` (axis forward X, up Z), `<s>.glb` (glTF, Y-up)",
        "- `<s>.png` albedo, 1024 px, painted (gradients, belly/rump/face markings, eyes)",
        "- `<s>_n.png` tangent-space normal, 1024 px, OpenGL (+Y) convention; fur strands or feather scallops",
        "- `<s>_preview.png` review render: side view (left) and 3/4 view (right) on a ground plane",
        "",
        "File names are unchanged from the previous revision except albedo, which is still `<s>.png`",
        "(the old README said `_albedo.png`; the files were always `<s>.png`) and the new `<s>_n.png`.",
        "UV0 is a side planar projection (x, z), uniform scale, shared by left and right sides (mirror-symmetric",
        "markings); not a non-overlapping atlas.",
        "",
        "| Species | Tris | Dims X x Y x Z (m) | Scale measure (m) | Albedo mean lum | Slot |",
        "|---|---|---|---|---|---|",
    ]
    desc = {"shoulder": "shoulder height", "height": "total height", "length": "length (X extent)"}
    for r in rows:
        lines.append("| %s | %d | %.3f x %.3f x %.3f | %s %.2f | %.2f | %s |"
                     % (r["name"], r["tris"], r["dims"][0], r["dims"][1], r["dims"][2],
                        desc[r["kind"]], r["target"], r["lum"], r["slot"]))
    lines += [
        "",
        "Shoulder = top of the withers (band around the shoulder x) above ground.",
        "",
        "## Features",
        "",
        "- deer: slim legs with hocks, white rump patch and tail, small branched antlers, large ears, white belly.",
        "- elk: heavy build, dark mane/neck/head/legs on a light tan body, pale rump patch, large six-tine antlers.",
        "- bear: bulky body, shoulder hump, short thick legs with plantigrade paws and claws, tan muzzle.",
        "- fox: orange body, white belly/cheeks/chest, black socks and ear backs, bushy white-tipped tail.",
        "- hare: crouched, large haunches, long black-tipped ears, white tail and belly.",
        "- crow: charcoal feathers with blue sheen, scalloped feathers, folded wings, wedge tail, strong beak.",
        "- owl: upright, round head with facial disc, ear tufts, big eyes, barred breast, feathered legs.",
        "- heron: S-curved neck, dagger bill, black crown plume, long legs, blue-grey back, white neck.",
        "",
        "## Provenance",
        "",
        "All geometry and textures are procedural (swept tubes and ellipsoids, numpy-painted albedo and normal",
        "maps). Checked `ArtSource/PolyHaven` and `C:\\Misc\\Vivarium`: no CC0 animal models, so nothing was",
        "copied or converted. Crow albedo is a charcoal grey (not black) to keep mean luminance in 0.2 to 0.5.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    import sys
    only = os.environ.get("CREATURES_ONLY")
    os.makedirs(OUT, exist_ok=True)
    rows, bad = [], []
    for sp in SPECIES:
        if only and sp["name"] not in only.split(","):
            continue
        row = build_species(sp)
        rows.append(row)
        if not (TRI_MIN <= row["tris"] <= TRI_MAX):
            bad.append("%s tris=%d outside %d-%d" % (sp["name"], row["tris"], TRI_MIN, TRI_MAX))
        if not (0.2 <= row["lum"] <= 0.5):
            bad.append("%s lum=%.3f outside 0.2-0.5" % (sp["name"], row["lum"]))
    if not only:
        write_readme(rows)
    print("DONE species=%d total_tris=%d out=%s" % (len(rows), sum(r["tris"] for r in rows), OUT))
    if bad:
        for line in bad:
            print("ERR_RANGE:", line)
        sys.exit(1)


main()
