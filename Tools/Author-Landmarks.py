"""Author landmark meshes headless in Blender.

Run from repo root:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools/Author-Landmarks.py

Deterministic (fixed per-asset seeds) and idempotent (scene is cleared and
outputs are overwritten on every run). Writes to ArtSource/Authored/Landmarks/:
    <name>.fbx, <name>.glb (+ <name>.fbm/ texture copies for FBX), README.md
Units: metres. Source is Z-up; FBX exported Y-up (-Z forward, Y up) for Unreal.
Origin at ground centre (min Z = 0, bounding-box centre on XY).
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Vector

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.abspath(os.path.join(os.getcwd(), "Tools"))
REPO = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(REPO, "ArtSource", "Authored", "Landmarks")
PH = os.path.join(REPO, "ArtSource", "PolyHaven")

# Slot order is the material index used while building (see SLOTS).
TIMBER, METAL, STONE, TURF = 0, 1, 2, 3
SLOTS = ["Timber", "Metal", "Stone", "Turf"]

# Existing ArtSource textures reused; nothing self-authored.
TEX = {
    "Timber": (os.path.join(PH, "pine_tree_01", "textures", "pine_tree_01_bark_diff_1k.jpg"),
               os.path.join(PH, "pine_tree_01", "textures", "pine_tree_01_bark_nor_gl_1k.jpg")),
    "Stone": (os.path.join(PH, "rock_01", "textures", "rock_01_diff_1k.jpg"),
              os.path.join(PH, "rock_01", "textures", "rock_01_nor_gl_1k.jpg")),
    "Turf": (os.path.join(PH, "grass_medium_01", "textures", "grass_medium_01_diff_1k.jpg"),
             os.path.join(PH, "grass_medium_01", "textures", "grass_medium_01_nor_gl_1k.jpg")),
}
METAL_RGB = (0.36, 0.37, 0.39, 1.0)
UV_M_PER_TILE = 2.0  # texture repeat length in metres


# ---------------------------------------------------------------- helpers

def make_noise3(rng, n=6):
    terms = []
    for _ in range(n):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized()
        terms.append((d, rng.uniform(1.5, 5.0), rng.uniform(0.0, 2 * math.pi), rng.uniform(0.3, 1.0)))
    tot = sum(t[3] for t in terms)

    def f(p):
        return sum(a * math.sin(fr * p.dot(d) + ph) for d, fr, ph, a in terms) / tot
    return f


def quad(bm, vs, mi):
    f = bm.faces.new(vs)
    f.material_index = mi
    return f


def add_beam(bm, p0, p1, w, h, mi):
    """Oriented rectangular beam from p0 to p1, half-width w and half-height h."""
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0).normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    s = d.cross(ref).normalized() * w
    t = s.cross(d).normalized() * h
    ends = []
    for e in (p0, p1):
        ends.append([
            bm.verts.new(e + s + t), bm.verts.new(e - s + t),
            bm.verts.new(e - s - t), bm.verts.new(e + s - t),
        ])
    A, B = ends
    for k in range(4):
        k1 = (k + 1) % 4
        quad(bm, (A[k], A[k1], B[k1], B[k]), mi)
    quad(bm, (A[0], A[1], A[2], A[3]), mi)
    quad(bm, (B[3], B[2], B[1], B[0]), mi)


# ---------------------------------------------------------------- builders

def build_tower(bm, rng):
    H_LEG = 19.5
    corners = [(1, 1), (1, -1), (-1, -1), (-1, 1)]

    def spread(z):
        return 2.0 + (1.4 - 2.0) * (z / H_LEG)

    def cpt(i, z):
        sx, sy = corners[i]
        r = spread(z)
        return (sx * r, sy * r, z)

    for i in range(4):
        add_beam(bm, cpt(i, 0.0), cpt(i, H_LEG), 0.10, 0.10, TIMBER)

    N = 7
    for k in range(N):
        z0 = H_LEG * k / N
        z1 = H_LEG * (k + 1) / N
        for i in range(4):
            j = (i + 1) % 4
            add_beam(bm, cpt(i, z0), cpt(j, z0), 0.06, 0.06, TIMBER)
            add_beam(bm, cpt(i, z0), cpt(j, z1), 0.05, 0.05, TIMBER)
            add_beam(bm, cpt(j, z0), cpt(i, z1), 0.05, 0.05, TIMBER)

    # Platform, posts and rail.
    zp = H_LEG + 0.2
    add_beam(bm, (0.0, 0.0, H_LEG), (0.0, 0.0, zp), 1.5, 1.5, TIMBER)
    rc = [(1.5, 1.5), (1.5, -1.5), (-1.5, -1.5), (-1.5, 1.5)]
    zr = H_LEG + 1.0
    for x, y in rc:
        add_beam(bm, (x, y, zp), (x, y, zr), 0.04, 0.04, TIMBER)
    for i in range(4):
        a, b = rc[i], rc[(i + 1) % 4]
        add_beam(bm, (a[0], a[1], zr), (b[0], b[1], zr), 0.03, 0.03, METAL)

    # Cab: solid timber block with metal pyramid roof.
    zc0, zc1 = zp, H_LEG + 2.2
    add_beam(bm, (0.0, 0.0, zc0), (0.0, 0.0, zc1), 1.1, 1.1, TIMBER)
    apex = bm.verts.new((0.0, 0.0, 22.0))
    base = [bm.verts.new((x, y, zc1)) for x, y in
            [(1.35, 1.35), (-1.35, 1.35), (-1.35, -1.35), (1.35, -1.35)]]
    for k in range(4):
        bm.faces.new((apex, base[k], base[(k + 1) % 4])).material_index = METAL


def build_stone(bm, rng, H, R, sx, sy, lean):
    noise = make_noise3(rng)
    res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for v in res["verts"]:
        p = v.co.normalized()
        k = 1.0 + 0.14 * noise(p) + 0.02 * rng.uniform(-1.0, 1.0)
        z = p.z * k * 0.6 * H + 0.4 * H
        x = p.x * k * R * sx + lean * (z / H) ** 2 * 0.25
        y = p.y * k * R * sy
        v.co = Vector((x, y, z))
    # Keep z >= 0 and cap the cut to give a flat weathered base.
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                           plane_co=(0.0, 0.0, 0.0), plane_no=(0.0, 0.0, -1.0),
                           dist=1e-6, clear_outer=True)
    bm.edges.ensure_lookup_table()
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    for f in bm.faces:
        f.material_index = STONE


def build_spire(bm, rng):
    H, NR, NZ = 35.0, 40, 120
    noise = make_noise3(rng)
    rings = []
    for i in range(NZ + 1):
        t = i / NZ
        z = H * t
        base = 0.25 + 2.95 * (1.0 - t) ** 1.6
        band = 1.0 + 0.025 * math.sin(60.0 * t)
        ring = []
        for j in range(NR):
            th = 2.0 * math.pi * j / NR
            flute = 1.0 - 0.07 * max(0.0, math.cos(8.0 * th + 0.5 * math.sin(9.0 * t))) ** 3
            n = noise(Vector((math.cos(th), math.sin(th), 4.0 * t)))
            r = base * band * flute * (1.0 + 0.10 * n)
            ring.append(bm.verts.new((r * math.cos(th), r * math.sin(th), z)))
        rings.append(ring)
    c0 = bm.verts.new((0.0, 0.0, 0.0))
    c1 = bm.verts.new((0.0, 0.0, H))
    for i in range(NZ):
        a, b = rings[i], rings[i + 1]
        for j in range(NR):
            j2 = (j + 1) % NR
            quad(bm, (a[j], a[j2], b[j2], b[j]), STONE)
    for j in range(NR):
        j2 = (j + 1) % NR
        bm.faces.new((c0, rings[0][j2], rings[0][j])).material_index = STONE
        bm.faces.new((c1, rings[-1][j], rings[-1][j2])).material_index = STONE


def build_ring(bm, rng):
    NA = 96
    radii = [5.0, 5.5, 6.0, 6.5, 7.0]
    noise = make_noise3(rng, n=5)
    grid = []
    for r in radii:
        row = []
        s = math.sin(math.pi * (r - 5.0) / 2.0)  # berm: 0 at rim, peak mid-width
        for j in range(NA):
            th = 2.0 * math.pi * j / NA
            z = 0.08 + 0.22 * s + 0.03 * noise(Vector((math.cos(th), math.sin(th), r * 0.2)))
            row.append(bm.verts.new((r * math.cos(th), r * math.sin(th), z)))
        grid.append(row)
    bot_in = [bm.verts.new((radii[0] * math.cos(2 * math.pi * j / NA),
                            radii[0] * math.sin(2 * math.pi * j / NA), 0.0)) for j in range(NA)]
    bot_out = [bm.verts.new((radii[-1] * math.cos(2 * math.pi * j / NA),
                             radii[-1] * math.sin(2 * math.pi * j / NA), 0.0)) for j in range(NA)]
    for i in range(len(radii) - 1):
        for j in range(NA):
            j2 = (j + 1) % NA
            quad(bm, (grid[i][j], grid[i][j2], grid[i + 1][j2], grid[i + 1][j]), TURF)
    for j in range(NA):
        j2 = (j + 1) % NA
        quad(bm, (grid[0][j], grid[0][j2], bot_in[j2], bot_in[j]), TURF)
        quad(bm, (grid[-1][j], grid[-1][j2], bot_out[j2], bot_out[j]), TURF)
        quad(bm, (bot_in[j], bot_in[j2], bot_out[j2], bot_out[j]), TURF)


# ---------------------------------------------------------------- specs

SPECS = [
    dict(name="fire_lookout_tower", build=build_tower, seed=1101, smooth=False,
         tri_max=25000, dz=(21.9, 22.1), dxy=None),
    dict(name="standing_stone_01",
         build=lambda bm, r: build_stone(bm, r, H=2.8, R=0.62, sx=1.0, sy=0.8, lean=0.10),
         seed=1201, smooth=True, tri_max=4000, dz=(2.5, 4.0), dxy=None),
    dict(name="standing_stone_02",
         build=lambda bm, r: build_stone(bm, r, H=3.3, R=0.55, sx=0.7, sy=1.0, lean=-0.15),
         seed=1202, smooth=True, tri_max=4000, dz=(2.5, 4.0), dxy=None),
    dict(name="standing_stone_03",
         build=lambda bm, r: build_stone(bm, r, H=3.8, R=0.48, sx=0.9, sy=0.75, lean=0.05),
         seed=1203, smooth=True, tri_max=4000, dz=(2.5, 4.0), dxy=None),
    dict(name="rock_spire", build=build_spire, seed=1301, smooth=True,
         tri_max=20000, dz=(34.9, 35.1), dxy=None),
    dict(name="stone_ring_base", build=build_ring, seed=1401, smooth=True,
         tri_max=3000, dz=(0.1, 0.6), dxy=(13.5, 14.5)),
]


# ---------------------------------------------------------------- pipeline

MATS = {}


def get_mat(slot):
    if slot in MATS:
        return MATS[slot]
    mat = bpy.data.materials.new(slot)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if slot == "Metal":
        bsdf.inputs["Base Color"].default_value = METAL_RGB
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.45
    else:
        diff, nor = TEX[slot]
        tc = nodes.new("ShaderNodeTexImage")
        tc.image = bpy.data.images.load(diff, check_existing=True)
        links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
        tn = nodes.new("ShaderNodeTexImage")
        tn.image = bpy.data.images.load(nor, check_existing=True)
        tn.image.colorspace_settings.name = "Non-Color"
        nm = nodes.new("ShaderNodeNormalMap")
        links.new(tn.outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Roughness"].default_value = {"Timber": 0.85, "Stone": 0.8, "Turf": 0.95}[slot]
    MATS[slot] = mat
    return mat


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    MATS.clear()


def unwrap(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.01,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def density_scale(me, target):
    """Uniform UV scale so one texture repeat covers about `target` metres.
    Uniform scale keeps the non-overlapping packing intact."""
    uvl = me.uv_layers.active.data
    world = sum(p.area for p in me.polygons)
    uv_area = 0.0
    for p in me.polygons:
        i0, i1, i2 = p.loop_indices[0], p.loop_indices[1], p.loop_indices[2]
        a, b, c = uvl[i0].uv, uvl[i1].uv, uvl[i2].uv
        uv_area += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5
    if uv_area <= 0.0 or world <= 0.0:
        return
    f = math.sqrt(world / uv_area) / target
    for d in uvl:
        d.uv = (d.uv.x * f, d.uv.y * f)


def make_object(spec):
    rng = random.Random(spec["seed"])
    bm = bmesh.new()
    spec["build"](bm, rng)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cx, cy, minz = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0, min(zs)
    for v in bm.verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= minz

    me = bpy.data.meshes.new(spec["name"])
    bm.to_mesh(me)
    bm.free()

    used = sorted({p.material_index for p in me.polygons})
    remap = {}
    for k, si in enumerate(used):
        me.materials.append(get_mat(SLOTS[si]))
        remap[si] = k
    for p in me.polygons:
        p.material_index = remap[p.material_index]
        p.use_smooth = spec["smooth"]

    obj = bpy.data.objects.new(spec["name"], me)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    unwrap(obj)
    density_scale(me, UV_M_PER_TILE)
    return obj, used


def export(obj, name):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, name + ".fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=False,
        path_mode="COPY",
        embed_textures=False,
        use_mesh_modifiers=True,
        add_leaf_bones=False,
        bake_anim=False,
    )
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT, name + ".glb"),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
    )


def write_readme(rows):
    lines = [
        "# Authored landmarks (Blender headless)",
        "",
        f"Generated by `Tools/Author-Landmarks.py` under Blender {bpy.app.version_string}. "
        "Deterministic (fixed per-asset seeds), idempotent. Regenerate with:",
        "",
        "    \"C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe\" -b -P Tools/Author-Landmarks.py",
        "",
        "Units: metres. Source is Z-up. FBX written with axis_forward -Z, axis_up Y (Unreal convention); "
        "GLB is glTF Y-up. Origin at ground centre (min Z = 0, bounding-box centre on XY).",
        "",
        "## Files",
        "",
        "| File | Tris | Dims X x Y x Z (m) | Material slots |",
        "|------|------|--------------------|----------------|",
    ]
    for r in rows:
        lines.append(f"| {r['name']}.fbx / .glb | {r['tris']} | {r['dims']} | {r['slots']} |")
    lines += [
        "",
        "Asset intent:",
        "- fire_lookout_tower: 22 m timber lattice, 4 legs, X-braced bays, platform with rail, "
        "solid timber cab, metal pyramid roof.",
        "- standing_stone_01/02/03: 2.5 to 4 m weathered stones, flat cut base, noise-displaced icosphere.",
        "- rock_spire: 35 m eroded column, flutes and horizontal erosion bands, tapered to a point-like top.",
        "- stone_ring_base: 14 m diameter low turf berm ring, inner void, outer skirt, open-ring footprint.",
        "",
        "## Materials",
        "",
        "- `Timber`: Principled BSDF, base colour from pine_tree_01_bark_diff_1k.jpg, normal from "
        "pine_tree_01_bark_nor_gl_1k.jpg (Non-Color), roughness 0.85.",
        "- `Metal`: flat colour (0.36, 0.37, 0.39), metallic 1.0, roughness 0.45. No texture.",
        "- `Stone`: Principled BSDF, base colour from rock_01_diff_1k.jpg, normal from "
        "rock_01_nor_gl_1k.jpg (Non-Color), roughness 0.8.",
        "- `Turf`: Principled BSDF, base colour from grass_medium_01_diff_1k.jpg, normal from "
        "grass_medium_01_nor_gl_1k.jpg (Non-Color), roughness 0.95.",
        "",
        "## UV",
        "",
        "One UV set `UVMap` per mesh, from Blender smart project (non-overlapping islands, "
        f"island margin 0.01). Layout is uniformly scaled so one texture repeat is about {UV_M_PER_TILE:.1f} m. "
        "UVs extend beyond 0 to 1 by design; the textures tile.",
        "",
        "## Texture provenance",
        "",
        "- All textures reused from `ArtSource/PolyHaven/` (PolyHaven, CC0): pine_tree_01, rock_01, "
        "grass_medium_01. No self-authored textures were needed.",
        "- FBX export copies the textures into `<name>.fbm/` beside each .fbx. GLB embeds them.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    clear_scene()
    rows = []
    ok = True
    for spec in SPECS:
        obj, used = make_object(spec)
        me = obj.data
        tris = len(me.polygons)
        all_tri = all(len(p.vertices) == 3 for p in me.polygons)
        dx, dy, dz = obj.dimensions
        tri_ok = all_tri and tris <= spec["tri_max"]
        dz_ok = spec["dz"][0] <= dz <= spec["dz"][1]
        dxy_ok = True
        if spec["dxy"] is not None:
            dxy_ok = spec["dxy"][0] <= max(dx, dy) <= spec["dxy"][1]
        ok = ok and tri_ok and dz_ok and dxy_ok
        print(f"TRIS {spec['name']} {tris} tri_ok={tri_ok} dims_ok={dz_ok and dxy_ok} "
              f"dims_m=({dx:.3f}, {dy:.3f}, {dz:.3f})")
        export(obj, spec["name"])
        slots = ", ".join(f"{k} {SLOTS[si]}" for k, si in enumerate(used))
        rows.append(dict(name=spec["name"], tris=tris,
                         dims=f"{dx:.2f} x {dy:.2f} x {dz:.2f}", slots=slots))

    if not ok:
        print("FAIL: tri count or dimension out of range")
        raise SystemExit(1)
    write_readme(rows)
    print(f"PASS: {len(rows)} assets written to {OUT}")


main()
