"""Author vegetation meshes headless.

Run: "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Vegetation.py

Metres, Z-up in Blender (glTF export is Y-up per spec), origin at ground centre.
Geometry is procedural. All variation comes from h01(tag, index, salt), a stateless
integer hash, so reruns reproduce the same geometry. No RNG state is used.

Colour maps reuse Poly Haven CC0 textures already in ArtSource/PolyHaven. Alpha masks
for leaves and blades are authored here as 1024 px PNGs in textures/.
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

SEED = 4217
M32 = 0xFFFFFFFF
TAU = 2.0 * math.pi

_here = globals().get("__file__")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(_here))) if _here else os.getcwd()
ART = os.path.join(REPO, "ArtSource")
OUT = os.path.join(ART, "Authored", "Vegetation")
TEX = os.path.join(OUT, "textures")

SRC_BARK_DIFF = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_diff_1k.jpg")
SRC_BARK_NOR = os.path.join(ART, "PolyHaven", "dead_tree_trunk", "textures", "dead_tree_trunk_nor_gl_1k.jpg")
SRC_LEAF_DIFF = os.path.join(ART, "PolyHaven", "island_tree_01", "textures", "island_tree_01_leaves_diff_1k.jpg")
SRC_BLADE_DIFF = os.path.join(ART, "PolyHaven", "grass_medium_01", "textures", "grass_medium_01_diff_1k.jpg")


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


def ribbon(part, pts, widths, facing):
    """Flat two-sided strip along polyline pts. u across 0..1, v along 0..1."""
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


# ---------------------------------------------------------------- asset builders

def build_acacia():
    T = 101
    trunk = Part("trunk", "Bark")
    pts = [(0.0, 0.0, 0.0), (0.04, 0.0, 1.2), (0.10, 0.03, 2.4), (0.20, 0.10, 4.0)]
    tube(trunk, pts, [0.20, 0.16, 0.12, 0.08], 10, v_scale=3.0)

    br = Part("branches", "Bark")
    for j in range(5):
        phi = TAU * j / 5 + 0.6 * (h01(T, j, 0) - 0.5)
        R = 3.0 + 1.2 * h01(T, j, 1)
        zE = 5.6 + 0.6 * h01(T, j, 2)
        s = (0.12, 0.05, 3.0)
        e = (math.cos(phi) * R, math.sin(phi) * R, zE)
        mid = add(lerp(s, e, 0.5), (0.0, 0.0, 0.4))
        tube(br, [s, mid, e], [0.09, 0.06, 0.025], 6, v_scale=2.0)

    crown = Part("crown", "Leaves")
    for k in range(700):
        r = 4.6 * math.sqrt(h01(T, k, 10))
        th = TAU * h01(T, k, 11)
        z = 5.8 + (h01(T, k, 12) - 0.5) * 0.9
        c = (r * math.cos(th), r * math.sin(th), z)
        e = rdir(T, k, 13)
        d = unit((e[0], e[1], 0.35 * e[2]))  # flat crown: cards lie mostly horizontal
        card(crown, c, d, 0.7, 0.45, T, k)
    return [trunk, br, crown]


def build_cypress():
    T = 202
    H = 19.5
    n = 40
    pts = []
    radii = []
    for i in range(n + 1):
        z = H * i / n
        pts.append((0.25 * math.sin(z / 7.0), 0.0, z))
        radii.append(1.05 * max(0.0, 1.0 - z / 24.0) ** 1.4 + 0.12)

    def flare(i, th):
        z = pts[i][2]
        amp = 0.8 * max(0.0, 1.0 - z / 4.0) ** 1.5
        return 1.0 + amp * max(0.0, math.cos(5.0 * th)) ** 6  # five buttress ridges

    trunk = Part("trunk", "Bark")
    tube(trunk, pts, radii, 14, flare=flare, v_scale=6.0)

    crown = Part("foliage", "Leaves")
    for k in range(1800):
        z = 8.5 + 11.0 * h01(T, k, 0)
        R = 0.5 + 3.4 * (1.0 - (z - 8.5) / 11.6)
        r = R * math.sqrt(h01(T, k, 1))
        th = TAU * h01(T, k, 2)
        c = (r * math.cos(th), r * math.sin(th), z)
        out = (math.cos(th), math.sin(th), 0.0)
        d = unit(add(mul(out, 0.8), mul(rdir(T, k, 3), 0.5)))
        card(crown, c, d, 0.9, 0.55, T, k)
    return [trunk, crown]


def build_knees():
    T = 303
    parts = []
    for k in range(5):
        x0 = -3.2 + 1.6 * k
        y0 = 0.3 * (k % 2)
        H = 0.9 + 0.6 * h01(T, k, 0)
        b = (x0, y0, 0.0)
        pts = [b, add(b, (0.0, 0.0, 0.45 * H)), add(b, (0.03, 0.0, 0.8 * H)), add(b, (0.05, 0.0, H))]
        p = Part("knee_%02d" % k, "Bark")
        tube(p, pts, [0.20 + 0.05 * h01(T, k, 1), 0.14, 0.08, 0.03], 8, v_scale=1.0)
        parts.append(p)
    return parts


def build_reed():
    T = 404
    stalks = Part("stalks", "Blades")
    heads = Part("cattail_heads", "Bark")
    leaves = Part("leaves", "Blades")
    for k in range(36):
        r = 0.25 * math.sqrt(h01(T, k, 0))
        th = TAU * h01(T, k, 1)
        base = (r * math.cos(th), r * math.sin(th), 0.0)
        H = 1.0 + 0.75 * h01(T, k, 2)
        lean = 0.08 + 0.15 * h01(T, k, 3)
        dh = (math.cos(th), math.sin(th), 0.0)
        pts = [base,
               add(base, (dh[0] * lean * 0.5, dh[1] * lean * 0.5, H * 0.5)),
               add(base, (dh[0] * lean, dh[1] * lean, H))]
        phi = TAU * h01(T, k, 4)
        ribbon(stalks, pts, [0.03, 0.025, 0.01], (math.cos(phi), math.sin(phi), 0.0))
        if k % 9 == 0:
            tip = pts[-1]
            head_pts = [add(tip, (0.0, 0.0, -0.16)), add(tip, (0.0, 0.0, -0.07)), tip]
            tube(heads, head_pts, [0.018, 0.022, 0.016], 6, v_scale=1.0)
    for k in range(14):
        th = TAU * h01(T, k, 20)
        r = 0.2 * math.sqrt(h01(T, k, 21))
        base = (r * math.cos(th), r * math.sin(th), 0.0)
        L = 0.9 + 0.5 * h01(T, k, 22)
        bend = 0.25 + 0.2 * h01(T, k, 23)
        dh = (math.cos(th), math.sin(th), 0.0)
        pts = [add(base, (dh[0] * bend * t * t, dh[1] * bend * t * t, L * t))
               for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
        phi = TAU * h01(T, k, 24)
        ribbon(leaves, pts, [0.05] * 5, (math.cos(phi), math.sin(phi), 0.0))
    return [stalks, heads, leaves]


def build_grass():
    T = 505
    blades = Part("blades", "Blades")
    for k in range(80):
        r = 0.22 * math.sqrt(h01(T, k, 0))
        th = TAU * h01(T, k, 1)
        base = (r * math.cos(th), r * math.sin(th), 0.0)
        H = 0.7 + 0.45 * h01(T, k, 2)
        bend = 0.08 + 0.3 * h01(T, k, 3)
        dh = (math.cos(th), math.sin(th), 0.0)
        pts = [(base[0] + dh[0] * bend * t * t, base[1] + dh[1] * bend * t * t, base[2] + H * t)
               for t in (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)]
        phi = TAU * h01(T, k, 4)
        ribbon(blades, pts, [0.05] * 4, (math.cos(phi), math.sin(phi), 0.0))
    return [blades]


def build_krummholz():
    T = 606
    trunk = Part("trunk", "Bark")
    br = Part("branches", "Bark")
    fol = Part("foliage", "Leaves")
    zs = [0.0, 0.5, 1.0, 1.5, 2.0, 2.4]
    xs = [0.0, 0.10, 0.22, 0.12, 0.28, 0.35]
    pts = [(xs[i], 0.04 * math.sin(zs[i] * 2.1), zs[i]) for i in range(6)]
    tube(trunk, pts, [0.12, 0.10, 0.085, 0.07, 0.05, 0.025], 8, v_scale=2.0)
    for j in range(10):
        s = pts[1 + j % 4]
        phi = TAU * h01(T, j, 0)
        L = 0.6 + 0.5 * h01(T, j, 1)
        e = add(s, (math.cos(phi) * L, math.sin(phi) * L, 0.2 + 0.5 * h01(T, j, 2)))
        tube(br, [s, e], [0.035, 0.008], 4)
    ctr = (0.1, 0.0, 1.6)
    for k in range(800):
        e = rdir(T, k, 0)
        r = h01(T, k, 1) ** (1.0 / 3.0)
        c = (ctr[0] + e[0] * r * 0.9, ctr[1] + e[1] * r * 0.85, ctr[2] + e[2] * r * 0.7)
        card(fol, c, rdir(T, k, 2), 0.3, 0.12, T, k)
    return [trunk, br, fol]


# (name, builder, height range m, tri limit LOD0)
ASSETS = [
    ("acacia_savannah_01", build_acacia, (6.0, 8.0), 60000),
    ("bald_cypress_01", build_cypress, (18.0, 22.0), 60000),
    ("bald_cypress_knees", build_knees, (0.8, 1.6), 6000),
    ("cattail_reed_clump_01", build_reed, (1.6, 1.9), 6000),
    ("prairie_grass_clump_01", build_grass, (1.0, 1.2), 6000),
    ("krummholz_conifer_01", build_krummholz, (2.0, 3.0), 60000),
]


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
    img = bpy.data.images.new(name, size, size, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def leaf_texture(size=1024):
    px = square_pixels(load_img(SRC_LEAF_DIFF), size)
    t = np.linspace(0.0, 1.0, size, dtype=np.float32)
    v, u = np.meshgrid(t, t, indexing="ij")  # axis0 = row = v
    x = (u - 0.5) * 2.0
    y = (v - 0.5) * 2.0
    w = 0.92 * np.clip(1.0 - x * x, 0.0, None) ** 0.6  # pointed ovate leaflet
    px[..., 3] = np.clip((w - np.abs(y)) * 60.0, 0.0, 1.0)
    path = os.path.join(TEX, "leaves_1024.png")
    write_png(px, path, "veg_leaves_1024")
    return load_img(path)


def blade_texture(size=1024):
    px = square_pixels(load_img(SRC_BLADE_DIFF), size)
    t = np.linspace(0.0, 1.0, size, dtype=np.float32)
    v, u = np.meshgrid(t, t, indexing="ij")  # v along blade (base 0 to tip 1), u across
    hw = 0.48 * np.clip(1.0 - v ** 1.5, 0.0, None) ** 0.7
    px[..., 3] = np.clip((hw - np.abs(u - 0.5)) * 200.0, 0.0, 1.0)
    path = os.path.join(TEX, "blades_1024.png")
    write_png(px, path, "veg_blades_1024")
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
            m.surface_render_method = "DITHERED"  # exporter maps DITHERED to alphaMode MASK
    return m


def build_materials():
    bark_d = load_img(SRC_BARK_DIFF)
    bark_n = load_img(SRC_BARK_NOR, noncolor=True)
    return {
        "Bark": make_material("Bark", bark_d, bark_n),
        "Leaves": make_material("Leaves", leaf_texture(), masked=True, two_sided=True),
        "Blades": make_material("Blades", blade_texture(), masked=True, two_sided=True),
    }


# ---------------------------------------------------------------- realise / export

def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)


def realise(asset, parts, mats):
    # One object, one mesh per asset: parts become material slots (one per material name).
    # Single StaticMesh on UE import, named after the asset.
    allz = min(p[2] for part in parts for p in part.verts)
    tris = 0
    lo = [1e18, 1e18, 1e18]
    hi = [-1e18, -1e18, -1e18]
    slots = []
    verts = []
    faces = []  # (index tuple, uv tuple, material slot index)
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
    tris = sum(len(poly.vertices) - 2 for poly in me.polygons)

    ob = bpy.data.objects.new(asset, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, asset + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True)

    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)

    dims = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    return {"tris": tris, "dims": dims, "slots": slots, "path": path, "minz": lo[2]}


def glb_materials(path):
    with open(path, "rb") as f:
        data = f.read()
    clen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + clen].decode("utf-8"))
    return [(m.get("name"), m.get("alphaMode", "OPAQUE"), m.get("doubleSided", False))
            for m in doc.get("materials", [])]


def main():
    os.makedirs(TEX, exist_ok=True)
    clear_scene()
    mats = build_materials()
    rows = []
    fails = []
    for name, builder, (hlo, hhi), tri_max in ASSETS:
        info = realise(name, builder(), mats)
        dw, dd, dh = info["dims"]
        print("ASSET %s tris=%d dims_m(W x D x H)=%.2f x %.2f x %.2f minz=%.4f" %
              (name, info["tris"], dw, dd, dh, info["minz"]))
        for mname, mode, ds in glb_materials(info["path"]):
            print("  material %s alphaMode=%s doubleSided=%s" % (mname, mode, ds))
        if not (hlo <= dh <= hhi):
            fails.append("%s height %.2f outside %s" % (name, dh, (hlo, hhi)))
        if info["tris"] > tri_max:
            fails.append("%s tris %d > %d" % (name, info["tris"], tri_max))
        if abs(info["minz"]) > 1e-6:
            pass  # shifted to ground in realise(); minz is the pre-shift value
        rows.append((name, info))

    lines = [
        "# Vegetation authored meshes",
        "",
        "Generated by `Tools/Author-Vegetation.py` (headless Blender 5.2). Deterministic: rerun reproduces the same geometry.",
        "",
        "Conventions: metres; Blender scene is Z-up, glTF output is Y-up per spec; origin at ground centre (min Z = 0).",
        "",
        "| File | Tris (LOD0) | W x D x H (m) | Material slots |",
        "|------|-------------|---------------|----------------|",
    ]
    for name, info in rows:
        dw, dd, dh = info["dims"]
        lines.append("| %s.glb | %d | %.2f x %.2f x %.2f | %s |" %
                     (name, info["tris"], dw, dd, dh, ", ".join(info["slots"])))
    lines += [
        "",
        "Files:",
        "- `acacia_savannah_01.glb`: acacia, flat crown, 6-8 m. Trunk and five branches (Bark), crown of two-sided leaf cards (Leaves).",
        "- `bald_cypress_01.glb`: bald cypress, 18-22 m, five-ridge buttressed trunk (Bark) and two-sided foliage cards (Leaves).",
        "- `bald_cypress_knees.glb`: five knee meshes as separate objects in one file, 0.9-1.5 m (Bark).",
        "- `cattail_reed_clump_01.glb`: reed clump, 1.8 m. Stalks and leaves as two-sided blade cards (Blades), cattail heads (Bark).",
        "- `prairie_grass_clump_01.glb`: prairie grass clump, 1.2 m, two-sided blade cards (Blades).",
        "- `krummholz_conifer_01.glb`: frost-stunted krummholz, 2-3 m. Crooked trunk and branches (Bark), dense two-sided needle cards (Leaves).",
        "",
        "Materials:",
        "- `Bark`: Poly Haven dead_tree_trunk, colour `ArtSource/PolyHaven/dead_tree_trunk/textures/dead_tree_trunk_diff_1k.jpg` and normal `..._nor_gl_1k.jpg` (embedded in GLB).",
        "- `Leaves`: alpha-masked, two-sided. Colour from Poly Haven island_tree_01 leaves diffuse (`ArtSource/PolyHaven/island_tree_01/textures/island_tree_01_leaves_diff_1k.jpg`). Alpha authored here as `textures/leaves_1024.png` (1024 px RGBA, ovate leaflet mask).",
        "- `Blades`: alpha-masked, two-sided, used for grass and reed (not in the original slot list; added for blade cards). Colour from Poly Haven grass_medium_01 diffuse (`ArtSource/PolyHaven/grass_medium_01/textures/grass_medium_01_diff_1k.jpg`). Alpha authored here as `textures/blades_1024.png`.",
        "",
        "Provenance:",
        "- Geometry: procedural, generated by this script. No third-party meshes.",
        "- Poly Haven maps: CC0 (site licence). Not individually re-verified against the licence page.",
        "- C:\\Misc\\Vivarium scanned: no usable CC0 vegetation meshes found. Its CC0 texture sets (ambientCG Bark001/Bark013/Bark014, ScatteredLeaves007; Poly Haven leaf maps) were not used. Poly Haven maps already in ArtSource were preferred.",
        "",
        "Alpha mode: masked materials request CLIP/MASK via blend_method where Blender exposes it. The alphaMode each GLB actually carries is printed at export time and should be checked on import.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    if fails:
        for line in fails:
            print("FAIL: " + line)
        sys.exit(1)
    print("PASS: %d vegetation assets written to %s" % (len(rows), OUT))


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
