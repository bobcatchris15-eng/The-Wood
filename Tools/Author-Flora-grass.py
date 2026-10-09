"""Author grass clumps and reeds (solid tapered geometry, wind VC) for The-Wood.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Flora-grass.py

Output (ArtSource/Authored/Flora/grass):
  <species>_v<n>.glb / .fbx   one combined mesh per variant, origin at ground, metres
  previews/<species>_v<n>.png  Cycles preview over a ground plane
  README.md
Wind VC: COLOR_0 red channel = 0 at base -> 1 at tip (first and only colour attribute "wind").
"""

import bpy
import math
import os
import random
from mathutils import Vector

SEED = 7331
TAU = 2.0 * math.pi

try:
    _here = os.path.abspath(__file__)
except NameError:
    _here = os.path.join(os.getcwd(), "Tools", "Author-Flora-grass.py")
REPO = os.path.dirname(os.path.dirname(_here))
OUT = os.path.join(REPO, "ArtSource", "Authored", "Flora", "grass")
PREV = os.path.join(OUT, "previews")

PREVIEW_RES = 640
PREVIEW_SAMPLES = 48

# ---------------------------------------------------------------- helpers

def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    l = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if l < 1e-9:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


class Bld:
    """Accumulates verts (with wind value), faces and per-face material index."""

    def __init__(self):
        self.v = []
        self.w = []
        self.f = []
        self.m = []

    def vert(self, p, wind):
        self.v.append((p[0], p[1], p[2]))
        self.w.append(max(0.0, min(1.0, wind)))
        return len(self.v) - 1

    def quad(self, a, b, c, d, mat):
        self.f.append((a, b, c, d))
        self.m.append(mat)

    def tri(self, a, b, c, mat):
        self.f.append((a, b, c))
        self.m.append(mat)

    def strip(self, ra, rb, mat):
        n = len(ra)
        for k in range(n):
            k2 = (k + 1) % n
            self.quad(ra[k], ra[k2], rb[k2], rb[k], mat)

    def tris(self):
        return sum(2 if len(f) == 4 else 1 for f in self.f)


def blade(bl, base, yaw, H, wd, bend, droop, segs, mat, wbase=0.0, wspan=1.0, lean=(0.0, 0.0)):
    """Tapered curved strip rising from base. bend pushes tip along yaw (fraction of H)."""
    dx, dy = math.cos(yaw), math.sin(yaw)
    sx, sy = -dy, dx
    prev = None
    for i in range(segs + 1):
        t = i / segs
        w = (wd * 0.5 * (1.0 - t) ** 0.8) if i < segs else wd * 0.025
        off = bend * H * t * t
        cx = base[0] + dx * off + lean[0] * t * t
        cy = base[1] + dy * off + lean[1] * t * t
        z = base[2] + H * t - droop * H * t ** 3
        wv = wbase + wspan * t
        L = bl.vert((cx + sx * w, cy + sy * w, z), wv)
        R = bl.vert((cx - sx * w, cy - sy * w, z), wv)
        if prev is not None:
            bl.quad(prev[0], prev[1], R, L, mat)
        prev = (L, R)


def tube(bl, pts, radii, winds, sides, mat):
    rings = []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, len(pts) - 1)]
        b = pts[max(i - 1, 0)]
        tg = unit(sub(a, b))
        ref = (0.0, 0.0, 1.0) if abs(tg[2]) < 0.99 else (1.0, 0.0, 0.0)
        n1 = unit(cross(tg, ref))
        n2 = cross(tg, n1)
        ring = []
        for k in range(sides):
            ang = TAU * k / sides
            off = add(mul(n1, radii[i] * math.cos(ang)), mul(n2, radii[i] * math.sin(ang)))
            ring.append(bl.vert(add(p, off), winds[i]))
        rings.append(ring)
    for i in range(len(rings) - 1):
        bl.strip(rings[i], rings[i + 1], mat)


def pod(bl, c, rx, rz, mat, wind=1.0, rings=4, seg=6):
    top = bl.vert((c[0], c[1], c[2] + rz), wind)
    bot = bl.vert((c[0], c[1], c[2] - rz), wind)
    rows = []
    for i in range(1, rings):
        phi = math.pi * i / rings
        z = c[2] + rz * math.cos(phi)
        r = rx * math.sin(phi)
        rows.append([bl.vert((c[0] + r * math.cos(TAU * k / seg), c[1] + r * math.sin(TAU * k / seg), z), wind)
                     for k in range(seg)])
    for k in range(seg):
        bl.tri(top, rows[0][k], rows[0][(k + 1) % seg], mat)
        bl.tri(bot, rows[-1][(k + 1) % seg], rows[-1][k], mat)
    for i in range(len(rows) - 1):
        bl.strip(rows[i], rows[i + 1], mat)


# ---------------------------------------------------------------- species

# blade mats: indices 0/1 chosen per blade; head mat index 2.
GRASS = {
    "prairie_bunchgrass": dict(kind="bunch", n=95, h=(0.6, 1.2), rad=0.13, wd=0.024, bend=(0.20, 0.45),
                               droop=0.15, segs=4, radial=True, heads=12,
                               cols=[(0.52, 0.56, 0.30), (0.60, 0.56, 0.32)], head=(0.80, 0.68, 0.40)),
    "alpine_tussock": dict(kind="bunch", n=190, h=(0.18, 0.38), rad=0.24, wd=0.026, bend=(0.6, 1.0),
                           droop=0.25, segs=3, radial=True, heads=0,
                           cols=[(0.50, 0.52, 0.36), (0.62, 0.58, 0.40)], head=None),
    "wet_sedge": dict(kind="sedge", n=45, h=(0.35, 0.8), rad=0.09, wd=0.012, bend=(0.02, 0.08),
                      droop=0.0, segs=4, radial=False, heads=10,
                      cols=[(0.20, 0.32, 0.13), (0.28, 0.36, 0.14)], head=(0.45, 0.30, 0.14)),
    "shade_grass": dict(kind="bunch", n=240, h=(0.2, 0.5), rad=0.20, wd=0.010, bend=(0.5, 0.9),
                        droop=0.40, segs=3, radial=True, heads=0,
                        cols=[(0.12, 0.28, 0.20), (0.22, 0.38, 0.16)], head=None),
    "frost_fescue": dict(kind="bunch", n=300, h=(0.1, 0.3), rad=0.10, wd=0.0045, bend=(0.3, 0.8),
                         droop=0.20, segs=2, radial=False, heads=0,
                         cols=[(0.58, 0.64, 0.62), (0.68, 0.72, 0.68)], head=None),
}
GRASS_SCALE = {1: 0.85, 2: 1.00, 3: 1.15}
GRASS_TINT = {1: 0.92, 2: 1.00, 3: 1.08}

REEDS = ["common_reed", "horsetail", "bamboo_stand"]


def build_grass(name, sp, scale, rng):
    bl = Bld()
    n = sp["n"]
    dirs = []
    for k in range(n):
        ang = rng.uniform(0, TAU)
        r = sp["rad"] * math.sqrt(rng.random())
        base = (r * math.cos(ang), r * math.sin(ang), 0.0)
        yaw = ang if sp["radial"] else rng.uniform(0, TAU)
        edge = r / sp["rad"]
        H = rng.uniform(*sp["h"]) * scale
        if sp["radial"]:
            H *= (1.0 - 0.3 * edge)  # rounded mound / domed clump
        bend = rng.uniform(*sp["bend"])
        wd = sp["wd"] * scale * rng.uniform(0.75, 1.25)
        mat = rng.randrange(2)
        if sp["kind"] == "sedge":
            lean = (bend * H * math.cos(yaw), bend * H * math.sin(yaw))
            pts, radii, winds = [], [], []
            for i in range(sp["segs"] + 1):
                t = i / sp["segs"]
                pts.append((base[0] + lean[0] * t * t, base[1] + lean[1] * t * t, H * t))
                radii.append(wd * 0.5 * (1.0 - 0.2 * t))
                winds.append(t)
            tube(bl, pts, radii, winds, 3, mat)
            if k < sp["heads"]:
                top = pts[-1]
                pod(bl, (top[0], top[1], top[2] + 0.012 * scale), 0.0065 * scale, 0.022 * scale, 2)
        else:
            blade(bl, base, yaw + rng.uniform(-0.25, 0.25), H, wd, bend,
                  sp["droop"] * rng.uniform(0.5, 1.2), sp["segs"], mat)
            if k < sp["heads"]:
                # seed stalk parallel to a tall blade, pod at tip
                sh = H * 1.08
                sbend = bend * 0.6
                blade(bl, base, yaw, sh, wd * 0.3, sbend, 0.0, 2, 2)
                tipx = base[0] + math.cos(yaw) * sbend * sh
                tipy = base[1] + math.sin(yaw) * sbend * sh
                pod(bl, (tipx, tipy, sh * 0.97 + 0.01 * scale), 0.0065 * scale, 0.02 * scale, 2)
    return bl, sp["cols"] + ([sp["head"]] if sp["head"] else [])


def build_common_reed(scale, rng, nstems):
    bl = Bld()
    for _ in range(nstems):
        ang = rng.uniform(0, TAU)
        r = 0.35 * math.sqrt(rng.random())
        bx, by = r * math.cos(ang), r * math.sin(ang)
        H = rng.uniform(2.0, 3.5) * scale
        lx, ly = rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25)
        r0 = rng.uniform(0.008, 0.012)
        steps = 10
        pts, radii, winds = [], [], []
        for i in range(steps + 1):
            t = i / steps
            pts.append((bx + lx * t * t, by + ly * t * t, H * t))
            radii.append(r0 * (1.0 - 0.35 * t))
            winds.append(0.85 * t)
        mat = rng.randrange(2)
        tube(bl, pts, radii, winds, 5, mat)
        tip = pts[-1]
        for _ in range(26):
            blade(bl, (tip[0], tip[1], tip[2] - 0.02), rng.uniform(0, TAU), rng.uniform(0.25, 0.45) * scale,
                  0.02, rng.uniform(0.6, 1.0), 0.5, 3, 2, wbase=0.85, wspan=0.15)
    return bl, [(0.36, 0.44, 0.20), (0.42, 0.48, 0.22), (0.55, 0.48, 0.34)]


def build_horsetail(scale, rng, nstems):
    bl = Bld()
    step = 0.06
    for _ in range(nstems):
        ang = rng.uniform(0, TAU)
        r = 0.25 * math.sqrt(rng.random())
        bx, by = r * math.cos(ang), r * math.sin(ang)
        H = rng.uniform(0.4, 1.0) * scale
        r0 = rng.uniform(0.005, 0.008)
        cnt = max(2, int(H / step) + 1)
        zs = [H * i / (cnt - 1) for i in range(cnt)]
        pts = [(bx, by, z) for z in zs]
        radii = [r0] * cnt
        winds = [z / H for z in zs]
        mat = rng.randrange(2)
        tube(bl, pts, radii, winds, 6, mat)
        for z in zs[1:-1]:
            sp_pts = [(bx, by, z - 0.004), (bx, by, z + 0.004)]
            tube(bl, sp_pts, [r0 * 1.18, r0 * 1.18], [z / H, z / H], 6, 2)
    return bl, [(0.25, 0.42, 0.22), (0.30, 0.46, 0.24), (0.20, 0.30, 0.16)]


def build_bamboo(rng, nculm, hrange):
    bl = Bld()
    for _ in range(nculm):
        ang = rng.uniform(0, TAU)
        r = 0.9 * math.sqrt(rng.random())
        bx, by = r * math.cos(ang), r * math.sin(ang)
        H = rng.uniform(*hrange)
        lx, ly = rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35)
        r0 = rng.uniform(0.015, 0.025)
        cnt = max(2, int(H / 0.15) + 1)
        zs = [H * i / (cnt - 1) for i in range(cnt)]
        pts, radii, winds = [], [], []
        for z in zs:
            t = z / H
            pts.append((bx + lx * t * t, by + ly * t * t, z))
            radii.append(r0 * (1.0 - 0.45 * t))
            winds.append(t)
        mat = rng.randrange(2)
        tube(bl, pts, radii, winds, 6, mat)
        # nodes: short darker sleeves, leaf sprays above first 0.8 m
        node_z = [0.45 * k for k in range(1, int(H / 0.45) + 1)]
        for nz in node_z:
            t = nz / H
            px = bx + lx * t * t
            py = by + ly * t * t
            rad = r0 * (1.0 - 0.45 * t)
            tube(bl, [(px, py, nz - 0.01), (px, py, nz + 0.01)], [rad * 1.2, rad * 1.2],
                 [t, t], 6, 2)
            if nz > 0.8:
                for _ in range(2):
                    blade(bl, (px, py, nz), rng.uniform(0, TAU), rng.uniform(0.3, 0.5), 0.05,
                          rng.uniform(0.3, 0.6), 0.4, 4, 3, wbase=t, wspan=1.0 - t)
    return bl, [(0.58, 0.60, 0.24), (0.66, 0.66, 0.30), (0.22, 0.34, 0.14), (0.18, 0.40, 0.18)]


# ---------------------------------------------------------------- blender

def mk_material(name, rgb, rough=0.75):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    lin = tuple(srgb_lin(c) for c in rgb) + (1.0,)
    bsdf.inputs["Base Color"].default_value = lin
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = lin
    try:
        m.use_backface_culling = False
    except Exception:
        pass
    return m


def make_object(name, bl, cols, tint):
    me = bpy.data.meshes.new(name)
    me.from_pydata(bl.v, [], bl.f)
    me.update()
    for i, c in enumerate(cols):
        mat = mk_material("gr_%s_%d" % (name, i), tuple(min(1.0, x * tint) for x in c))
        me.materials.append(mat)
    for poly, mi in zip(me.polygons, bl.m):
        poly.material_index = mi
    ca = me.color_attributes.new(name="wind", type="FLOAT_COLOR", domain="POINT")
    for i, wv in enumerate(bl.w):
        ca.data[i].color = (wv, 0.0, 0.0, 1.0)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for m in list(bpy.data.materials):
        if m.name.startswith("gr_") and m.users == 0:
            bpy.data.materials.remove(m)


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
                             axis_forward="-Z", axis_up="Y")


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.cycles.device = "CPU"
        sc.cycles.samples = PREVIEW_SAMPLES
        sc.cycles.use_denoising = False
    except Exception:
        pass
    sc.render.resolution_x = PREVIEW_RES
    sc.render.resolution_y = PREVIEW_RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("gr_world")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.70, 0.75, 0.80, 1.0)
    bg.inputs[1].default_value = 1.0
    sc.world = w


def preview(ob, path):
    sc = bpy.context.scene
    dims = ob.dimensions
    H = max(dims.z, 0.2)
    R = max(dims.x, dims.y, 0.2)
    ground = None
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.data.materials.append(mk_material("gr_ground", (0.30, 0.27, 0.20), rough=0.95))
    bpy.ops.object.light_add(type="SUN", rotation=(0.9, 0.1, 0.6))
    sun = bpy.context.active_object
    sun.data.energy = 4.0
    cam_d = bpy.data.cameras.new("gr_cam")
    cam = bpy.data.objects.new("gr_cam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    sc.camera = cam
    centre = Vector((0.0, 0.0, H * 0.45))
    dist = max(H, 2.0 * R) * 1.9 + 0.6
    d = Vector((0.75, -0.65, 0.35)).normalized()
    pos = centre + d * dist
    cam.location = pos
    cam.rotation_euler = (centre - pos).to_track_quat("-Z", "Y").to_euler()
    cam_d.lens = 50
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in (cam, sun, ground):
        bpy.data.objects.remove(o, do_unlink=True)


def tri_count(bl):
    return bl.tris()


def main():
    os.makedirs(PREV, exist_ok=True)
    setup_render()
    rows = []
    sp_index = 0
    for sname, sp in GRASS.items():
        sp_index += 1
        for v in (1, 2, 3):
            clear_scene()
            rng = random.Random(SEED * 1000 + sp_index * 17 + v)
            bl, cols = build_grass(sname, sp, GRASS_SCALE[v], rng)
            name = "%s_v%d" % (sname, v)
            ob = make_object(name, bl, cols, GRASS_TINT[v])
            export(ob, name)
            preview(ob, os.path.join(PREV, name + ".png"))
            rows.append((name, "grass", bl.tris(), tuple(ob.dimensions)))
            print("OK %s tris=%d dims=(%.2f,%.2f,%.2f)" % (name, bl.tris(), *ob.dimensions))

    for v in (1, 2):
        clear_scene()
        rng = random.Random(SEED * 1000 + 401 + v)
        name = "common_reed_v%d" % v
        scale = 0.9 if v == 1 else 1.1
        bl, cols = build_common_reed(scale, rng, 26 if v == 1 else 32)
        ob = make_object(name, bl, cols, GRASS_TINT[v])
        export(ob, name)
        preview(ob, os.path.join(PREV, name + ".png"))
        rows.append((name, "reed", bl.tris(), tuple(ob.dimensions)))
        print("OK %s tris=%d dims=(%.2f,%.2f,%.2f)" % (name, bl.tris(), *ob.dimensions))

    for v in (1, 2):
        clear_scene()
        rng = random.Random(SEED * 1000 + 501 + v)
        name = "horsetail_v%d" % v
        scale = 0.9 if v == 1 else 1.1
        bl, cols = build_horsetail(scale, rng, 16 if v == 1 else 20)
        ob = make_object(name, bl, cols, GRASS_TINT[v])
        export(ob, name)
        preview(ob, os.path.join(PREV, name + ".png"))
        rows.append((name, "reed", bl.tris(), tuple(ob.dimensions)))
        print("OK %s tris=%d dims=(%.2f,%.2f,%.2f)" % (name, bl.tris(), *ob.dimensions))

    for v in (1, 2):
        clear_scene()
        rng = random.Random(SEED * 1000 + 601 + v)
        name = "bamboo_stand_v%d" % v
        hr = (3.0, 4.5) if v == 1 else (4.5, 6.0)
        bl, cols = build_bamboo(rng, 10 if v == 1 else 14, hr)
        ob = make_object(name, bl, cols, GRASS_TINT[v])
        export(ob, name)
        preview(ob, os.path.join(PREV, name + ".png"))
        rows.append((name, "reed", bl.tris(), tuple(ob.dimensions)))
        print("OK %s tris=%d dims=(%.2f,%.2f,%.2f)" % (name, bl.tris(), *ob.dimensions))

    write_readme(rows)
    print("PASS: %d grass/reed variants written to %s" % (len(rows), OUT))


def write_readme(rows):
    lines = [
        "# Flora: grass clumps and reeds",
        "",
        "Authored by `Tools/Author-Flora-grass.py` (seed %d). Solid tapered geometry, no textures." % SEED,
        "",
        "- Units: metres. Origin at ground centre, Y-up in GLB, -Z forward / Y-up in FBX.",
        "- One combined mesh per variant, `.glb` and `.fbx`.",
        "- Wind VC: vertex colour `wind` (COLOR_0, red channel) = 0 at base, 1 at tip.",
        "- Previews: `previews/<name>.png` (Cycles, ground plane, 3/4 view).",
        "",
        "| Variant | Kind | Tris | Size (m) x,y,z |",
        "|---|---|---|---|",
    ]
    for name, kind, tris, d in rows:
        lines.append("| %s | %s | %d | %.2f x %.2f x %.2f |" % (name, kind, tris, d[0], d[1], d[2]))
    lines += [
        "",
        "## Species notes",
        "- prairie_bunchgrass: tall upright arching tan-green blades with seed heads (straw pods).",
        "- alpine_tussock: dense rounded mound, short outward-bent straw/grey-green blades.",
        "- wet_sedge: stiff triangular-section stems, dark olive green, brown seed heads.",
        "- shade_grass: fine soft drooping blades, dark blue-green / yellow-green.",
        "- frost_fescue: fine pale blue-grey hair-like tufts.",
        "- common_reed: tall green stems with straw plume heads.",
        "- horsetail: jointed upright segmented stems, darker joint sleeves, no whorl branchlets.",
        "- bamboo_stand: 3-6 m segmented culms, darker nodes, leaf sprays above 0.8 m.",
        "",
        "Catalogue: Docs/FloraCatalog.md. Cattail lives in ArtSource/Authored/Vegetation.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
