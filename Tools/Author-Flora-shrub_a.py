"""Author shrub-a flora headless: juniper_low, heather_dwarf, hazel_coppice, thorn_scrub,
willow_shrub, sumac_scrub, salal_understory. Two variants each.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-shrub_a.py

Metres, Z-up in Blender (glTF/FBX output Y-up), origin at ground centre (min Z = 0).
Sapling Tree Gen is not bundled with Blender 5.2 (no add_curve_sapling module), so the
branching is generated here: recursive tapered branch polylines, each branch a tube.
Leaves are alpha-cut cards. Each card's UVs frame one leaf from the CC0 Poly Haven
island_tree_01 leaf sheet, and the card base sits on a branch point, so foliage hangs
off the branch network instead of floating in a sphere.
All variation comes from h01(tag, index...), a stateless integer hash, so reruns
reproduce the same geometry. No RNG state is used.

Per variant: <id>_vNN.glb + .fbx (LOD0), <id>_vNN_LOD1.glb + .fbx (~30 % cards),
512 px preview PNG (LOD0, 3/4 view over a preview-only ground plane, not exported).
One combined mesh per file, slots Bark and Leaves.
Vertex colour 'WindWeight' R = (z / height)^1.2 (0 base to 1 tips).
Leaf and bark colour variants are tinted textures written to textures/.
Output dir is owned by this script: ArtSource/Authored/Flora/shrub_a/.
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

SEED = 7331
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi
LEAF_TEX = 1024
LEAF_MEAN = 0.36  # target mean luminance of leaf albedo over the leaf mask

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Flora", "shrub_a")
TEX = os.path.join(OUT, "textures")
SRC = os.path.join(TEX, "src")
PREV = os.path.join(OUT, "previews")

SRC_LEAF_ORIG = os.path.join(ART, "PolyHaven", "island_tree_01", "textures", "island_tree_01_leaves_diff_1k.jpg")
SRC_BARK_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_diff_1k.jpg")
SRC_NOR_ORIG = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_nor_gl_1k.jpg")
SRC_LEAF = os.path.join(SRC, "island_tree_01_leaves_diff_1k.jpg")
SRC_BARK = os.path.join(SRC, "dead_tree_trunk_diff_1k.jpg")
SRC_NOR = os.path.join(SRC, "dead_tree_trunk_nor_gl_1k.jpg")

# Catalogue rows: docs/FloraCatalog.md (shrub rows). H = per-variant height m, hrange = catalogue height m.
# Skeleton: nst trunks from a ground ring (sp), length tlen*H, lean/rise set initial dir,
# curve/grav bend growth (grav = droop), kids children per branch end (angle kang, length
# shrink), depth = branch generations, lat = lateral children off each trunk.
# Cards: cards total leaf cards on branch points with depth >= lmin; lf length (m),
# lwf width factor on atlas aspect, lflat 1 = leaves along twig, 0 = radial out.
SHRUBS = [
    dict(id="juniper_low", tag=1, H=(0.9, 1.2), hrange=(0.5, 1.5), nst=7, sp=0.10, tlen=(0.25, 0.35),
         lean=1.0, rise=0.45, curve=0.0, grav=0.0, kids=3, kang=(35, 60), depth=2, lat=1, shrink=0.55,
         rad=0.022, cards=3000, lmin=0, lf=0.07, lwf=0.6, lflat=0.7, ldroop=0.0, hooks=False,
         tints=[(0.42, 0.58, 0.50), (0.36, 0.50, 0.30)], tint_names=["blue-green", "dull green"],
         bark=(0.80, 0.74, 0.68),
         silhouette="sprawling low mound, spiky needle tufts, stems from ground"),
    dict(id="heather_dwarf", tag=2, H=(0.42, 0.60), hrange=(0.3, 0.8), nst=6, sp=0.12, tlen=(0.28, 0.38),
         lean=0.8, rise=1.1, curve=0.0, grav=0.0, kids=3, kang=(25, 50), depth=2, lat=1, shrink=0.6,
         rad=0.015, cards=2600, lmin=0, lf=0.035, lwf=0.7, lflat=0.4, ldroop=0.0, hooks=False,
         tints=[(0.62, 0.36, 0.70), (0.46, 0.52, 0.36)], tint_names=["purple", "dull green"],
         bark=(0.62, 0.52, 0.42),
         silhouette="dense low cushion of tiny leaves, upward tufts"),
    dict(id="hazel_coppice", tag=3, H=(2.6, 4.0), hrange=(2.0, 5.0), nst=10, sp=0.10, tlen=(0.50, 0.62),
         lean=0.25, rise=1.0, curve=0.0, grav=0.0, kids=2, kang=(15, 30), depth=3, lat=0, shrink=0.5,
         rad=0.014, cards=2600, lmin=1, lf=0.15, lwf=2.0, lflat=0.25, ldroop=0.0, hooks=False,
         tints=[(0.55, 0.75, 0.35), (0.72, 0.80, 0.36)], tint_names=["green", "yellow-green"],
         bark=(0.85, 0.72, 0.55),
         silhouette="many thin stems from one clump, round leaves"),
    dict(id="thorn_scrub", tag=4, H=(1.3, 2.2), hrange=(1.0, 3.0), nst=9, sp=0.14, tlen=(0.40, 0.60),
         lean=0.55, rise=0.85, curve=0.0, grav=0.0, kids=3, kang=(40, 75), depth=2, lat=1, shrink=0.6,
         rad=0.013, cards=2600, lmin=0, lf=0.10, lwf=0.9, lflat=0.3, ldroop=0.0, hooks=True,
         tints=[(0.60, 0.68, 0.55), (0.55, 0.58, 0.30)], tint_names=["grey-green", "olive"],
         bark=(0.60, 0.58, 0.55),
         silhouette="dense thorny clump with hooked branch tips"),
    dict(id="willow_shrub", tag=5, H=(2.8, 4.5), hrange=(2.0, 6.0), nst=7, sp=0.06, tlen=(0.55, 0.65),
         lean=0.35, rise=1.0, curve=0.10, grav=0.15, kids=2, kang=(15, 30), depth=3, lat=0, shrink=0.6,
         rad=0.012, cards=3200, lmin=0, lf=0.24, lwf=0.8, lflat=0.85, ldroop=0.45, hooks=False,
         tints=[(0.58, 0.70, 0.60), (0.78, 0.84, 0.82)], tint_names=["grey-green", "silver"],
         bark=(0.80, 0.80, 0.74),
         silhouette="drooping thin stems in an arching clump, hanging leaves"),
    dict(id="sumac_scrub", tag=6, H=(1.4, 2.4), hrange=(1.0, 3.0), nst=6, sp=0.14, tlen=(0.40, 0.58),
         lean=0.6, rise=0.85, curve=0.0, grav=0.0, kids=3, kang=(30, 55), depth=2, lat=1, shrink=0.6,
         rad=0.015, cards=2600, lmin=0, lf=0.16, lwf=0.8, lflat=0.35, ldroop=0.0, hooks=False,
         tints=[(0.45, 0.72, 0.32), (0.85, 0.36, 0.20)], tint_names=["green", "red autumn"],
         bark=(0.75, 0.55, 0.45),
         silhouette="rounded multi-stem thicket, feathery compound leaves"),
    dict(id="salal_understory", tag=7, H=(0.9, 1.2), hrange=(0.5, 1.5), nst=8, sp=0.14, tlen=(0.35, 0.50),
         lean=0.6, rise=0.60, curve=0.0, grav=0.12, kids=3, kang=(25, 45), depth=2, lat=1, shrink=0.6,
         rad=0.015, cards=2600, lmin=0, lf=0.12, lwf=0.9, lflat=0.5, ldroop=0.15, hooks=False,
         tints=[(0.20, 0.42, 0.22), (0.52, 0.36, 0.26)], tint_names=["dark glossy green", "reddish"],
         bark=(0.60, 0.50, 0.40),
         silhouette="low arching leafy mound of waxy leaves"),
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


# ---------------------------------------------------------------- skeleton / leaf cards

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


def skeleton(c, var):
    g = Gen(c, var)
    H = g.H
    sk = {"segs": [], "cands": [], "tips": []}
    for i in range(c["nst"]):
        a = TAU * (i + g.rr(-0.3, 0.3)) / c["nst"]
        rb = c["sp"] * H * math.sqrt(g.r())
        base = (math.cos(a) * rb, math.sin(a) * rb, 0.0)
        out = unit((base[0], base[1], 0.0))
        d = unit(add(mul(out, c["lean"] * g.rr(0.8, 1.2)), (0.0, 0.0, c["rise"])))
        L = H * g.rr(c["tlen"][0], c["tlen"][1])
        grow(g, base, d, L, c["rad"] * H, 0, sk)
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
    """Find the 8 leaves on the CC0 sheet: returns boxes (c0, c1, r0, r1), arr coords, r0 = leaf base row."""
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


def leaf_cards(g, sk, sheet):
    c = g.c
    cands = sk["cands"]
    cards = []
    for _ in range(c["cards"]):
        pos, t, _dep = cands[min(len(cands) - 1, int(g.r() * len(cands)))]
        o = (pos[0], pos[1], 0.0)
        o = unit(o) if length(o) > 1e-6 else (0.0, 0.0, 1.0)
        radial = unit(add(o, (0.0, 0.0, 0.4)))
        ld = unit(add(mul(t, c["lflat"]), mul(radial, 1.0 - c["lflat"])))
        ld = unit(add(add(ld, mul(g.jit(1.0), 0.30)), (0.0, 0.0, -c["ldroop"])))
        box = sheet[min(len(sheet) - 1, int(g.r() * len(sheet)))]
        bw = box[1] - box[0]
        bh = box[3] - box[2]
        h = c["lf"] * g.rr(0.8, 1.2)
        w = h * (bw / float(bh)) * c["lwf"]
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
    H = c["H"][var]
    seg = 6 if lod == 0 else 3
    ncard = len(cards) if lod == 0 else int(round(0.3 * len(cards)))
    stems_p = Part("stems", "Bark")
    hooks_p = Part("hooks", "Bark")
    leaf_p = Part("leaves", "Leaves")
    for pts, rads, _depth in sk["segs"]:
        if lod == 1:
            # LOD1: 3-point polyline (base, mid, tip) keeps the silhouette, cuts tube quads.
            m = len(pts) // 2
            pts, rads = [pts[0], pts[m], pts[-1]], [rads[0], rads[m], rads[-1]]
        tube(stems_p, pts, rads, seg, v_scale=2.0)
    if c["hooks"] and lod == 0:
        sr = c["rad"] * H * 0.7
        for idx, (tip, dv) in enumerate(sk["tips"]):
            if h01(c["tag"], idx, 77) < 0.7:
                t1 = add(tip, add(mul(dv, 0.05 * H), (0.0, 0.0, 0.02 * H)))
                t2 = add(tip, add(mul(dv, 0.08 * H), (0.0, 0.0, 0.06 * H)))
                tube(hooks_p, [tip, t1, t2], [sr, sr * 0.5, sr * 0.1], 4)
    for card in cards[:ncard]:
        leaf_quad(leaf_p, card)
    return [stems_p, hooks_p, leaf_p]


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


def leaf_tex(c, var, px):
    """Colour-corrected leaf albedo (mean luminance LEAF_MEAN over leaf mask) with alpha cut-out."""
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
    path = os.path.join(TEX, "%s_v%02d_leaves.png" % (c["id"], var + 1))
    write_png(out, path, "leaves_%s_%d" % (c["id"], var + 1))
    return load_img(path), mean_lum


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


def make_mats(c, var, leaf_px, leaf_means):
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    nor = load_img(SRC_NOR, noncolor=True)
    leaf_img, mean_lum = leaf_tex(c, var, leaf_px)
    leaf_means[c["id"] + "_v%02d" % (var + 1)] = mean_lum
    return {
        "Bark": make_material("Bark", bark_tex(c, var), nor),
        "Leaves": make_material("Leaves", leaf_img, masked=True, two_sided=True),
    }


# ---------------------------------------------------------------- realise / export / preview

def clear_objects():
    for ob in list(bpy.data.objects):
        if ob.type == "MESH":
            bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def make_object(name, parts, mats):
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

    # Wind weight: R = (z / height)^1.2, 0 at base, 1 at tips. Linear values, no gamma.
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
    """Preview-only ground plane. Never exported: added after export, removed after render."""
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

def main():
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(TEX, exist_ok=True)
    os.makedirs(PREV, exist_ok=True)
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
            mats = make_mats(c, var, leaf_px, leaf_means)
            g, sk = skeleton(c, var)
            cards = leaf_cards(g, sk, sheet)

            ob, info = make_object(name, build_parts(c, var, sk, cards, 0), mats)
            glb = export(ob, name)
            attrs, gmats = glb_info(glb)
            preview(ob, H, os.path.join(PREV, name + ".png"))
            me0 = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.meshes.remove(me0)

            ob1, info1 = make_object(name + "_LOD1", build_parts(c, var, sk, cards, 1), mats)
            export(ob1, name + "_LOD1")
            me1 = ob1.data
            bpy.data.objects.remove(ob1, do_unlink=True)
            bpy.data.meshes.remove(me1)

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
            ml = leaf_means[name]
            if not (0.25 <= ml <= 0.5):
                fails.append("%s leaf mean luminance %.3f outside 0.25-0.5" % (name, ml))
            rows.append((name, c, var, info, info1, dw, dd, dh, ml))

    lines = [
        "# Flora shrub-a authored meshes",
        "",
        "Generated by `Tools/Author-Flora-shrub_a.py` (headless Blender 5.2, Cycles previews). Deterministic: rerun reproduces the same geometry.",
        "",
        "Method: Sapling Tree Gen is not bundled with Blender 5.2, so the script grows its own branching: recursive tapered branch tubes from a ground clump, each species with its own lean, droop, branch angle and depth. Leaf cards are attached at branch points (base on the branch), never free-floating. Leaves are alpha-cut cards, each framing one leaf of the CC0 Poly Haven island_tree_01 leaf sheet.",
        "",
        "Conventions: metres; Blender scene is Z-up, glTF and FBX output Y-up; origin at ground centre (min Z = 0). One combined mesh per file.",
        "Slots: `Bark` (stems, thorn hooks), `Leaves` (alpha-masked two-sided leaf cards). Vertex colour `WindWeight` R = (z/height)^1.2, 0 base to 1 tips, stored as linear values; alpha 1.",
        "LOD1: 30 % of the leaf cards, same branch skeleton with 3-sided tubes.",
        "",
        "| File (.glb / .fbx) | Tris LOD0 | Tris LOD1 | W x D x H (m) | Slots | Colour variant | Leaf mean luma |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, c, var, info, info1, dw, dd, dh, ml in rows:
        lines.append("| %s.glb / .fbx | %d | %d | %.2f x %.2f x %.2f | %s | %s | %.3f |" %
                     (name, info["tris"], info1["tris"], dw, dd, dh,
                      ", ".join(info["slots"]), c["tint_names"][var], ml))
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
        "Flower and berry cards: none. The shrub-a silhouettes in the catalogue list no separate flowers or berries; heather purple and sumac red come from the colour tint only.",
        "Sumac pinnate leaves are approximated by the simple leaf sheet; no separate compound-leaf geometry.",
        "",
        "Textures (`textures/`):",
        "- `<id>_vNN_leaves.png`: 1024 px RGBA, leaf albedo colour-corrected to mean luminance 0.36 over the leaf mask, alpha is the leaf cut-out from the sheet.",
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
    print("PASS: %d shrub-a variants written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
