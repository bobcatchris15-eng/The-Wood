"""Author anomaly meshes (unreal-region discoveries) headless in Blender.

Run from repo root:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Author-Anomalies.py

Deterministic (fixed per-asset seeds) and idempotent (scene is cleared and
outputs are overwritten on every run). Writes to ArtSource/Authored/Anomalies/:
    <name>.fbx, <name>.glb, README.md
Units: metres. Source is Z-up; FBX exported Y-up (axis_forward -Z, axis_up Y) for Unreal.
Origin at ground contact (min Z = 0, bounding-box centre on XY).
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.abspath(os.path.join(os.getcwd(), "Tools"))
REPO = os.path.abspath(os.path.join(HERE, ".."))
OUT = os.path.join(REPO, "ArtSource", "Authored", "Anomalies")
PH = os.path.join(REPO, "ArtSource", "PolyHaven")

# Slot order is the material index used while building (see SLOTS).
STONE, METAL = 0, 1
SLOTS = ["Stone", "Metal"]

# Existing ArtSource texture reused; nothing self-authored.
TEX = {
    "Stone": (os.path.join(PH, "rock_01", "textures", "rock_01_diff_1k.jpg"),
              os.path.join(PH, "rock_01", "textures", "rock_01_nor_gl_1k.jpg")),
}
RUST_RGB = (0.42, 0.21, 0.10, 1.0)
UV_M_PER_TILE = 2.0  # texture repeat length in metres
TRI_MAX = 12000


# ---------------------------------------------------------------- helpers

def noise3(rng, n=6):
    terms = []
    for _ in range(n):
        d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized()
        terms.append((d, rng.uniform(1.5, 5.0), rng.uniform(0.0, 2 * math.pi), rng.uniform(0.3, 1.0)))
    tot = sum(t[3] for t in terms)

    def f(p):
        return sum(a * math.sin(fr * p.dot(d) + ph) for d, fr, ph, a in terms) / tot
    return f


def warp_fn(noise, z, amp):
    def f(th):
        return 1.0 + amp * noise(Vector((math.cos(th), math.sin(th), z)))
    return f


def ring_circle(cx, cy, z, r, n, warp=None):
    out = []
    for j in range(n):
        th = 2.0 * math.pi * j / n
        k = r * (warp(th) if warp else 1.0)
        out.append(Vector((cx + k * math.cos(th), cy + k * math.sin(th), z)))
    return out


def loft(bm, rings, mi):
    """Closed-loop rings (equal length) joined by quads; ring 0 and last ring capped."""
    vs = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    for i in range(len(vs) - 1):
        a, b = vs[i], vs[i + 1]
        for j in range(n):
            j1 = (j + 1) % n
            bm.faces.new((a[j], a[j1], b[j1], b[j])).material_index = mi
    bm.faces.new(vs[0][::-1]).material_index = mi
    bm.faces.new(vs[-1]).material_index = mi


def add_box(bm, c, size, yaw, mi, rng, wear=0.01):
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    bmesh.ops.scale(bm, vec=size, verts=verts)
    bmesh.ops.rotate(bm, cent=(0.0, 0.0, 0.0), matrix=Matrix.Rotation(yaw, 3, "Z"), verts=verts)
    bmesh.ops.translate(bm, vec=c, verts=verts)
    for v in verts:
        v.co += Vector([rng.uniform(-wear, wear) for _ in range(3)])
    for f in {f for v in verts for f in v.link_faces}:
        f.material_index = mi


# ---------------------------------------------------------------- builders

def build_stair(bm, rng):
    """Spiral stone stair, 4 m, open top: last tread is a cantilever with no landing."""
    H, PLINTH, N = 4.0, 0.15, 20
    noise = noise3(rng)
    spine = [(0.0, 1.30), (PLINTH, 1.30), (PLINTH, 0.30), (2.0, 0.24), (3.0, 0.22), (3.88, 0.22)]
    loft(bm, [ring_circle(0.0, 0.0, z, r, 12, warp_fn(noise, z, 0.05)) for z, r in spine], STONE)
    rise = (H - PLINTH) / N
    rc, length = (0.25 + 1.15) / 2.0, 0.9
    for i in range(N):
        th = i * 0.45
        z_top = PLINTH + (i + 1) * rise
        c = Vector((rc * math.cos(th), rc * math.sin(th), z_top - 0.06))
        add_box(bm, c, (length, 0.42, 0.12), th, STONE, rng, wear=0.012)


def build_sword(bm, rng):
    """Rusted blade tip-down at ground contact, guard, grip, pommel. 1.1 m."""
    blade = [(0.00, 0.004, 0.0015), (0.10, 0.016, 0.005), (0.40, 0.024, 0.0075),
             (0.72, 0.023, 0.007), (0.75, 0.021, 0.006)]
    rings = []
    for z, hw, ht in blade:
        pts = [(hw, 0.0), (0.0, ht), (-hw, 0.0), (0.0, -ht)]
        rings.append([Vector((x * (1 + rng.uniform(-0.15, 0.15)),
                              y * (1 + rng.uniform(-0.15, 0.15)), z)) for x, y in pts])
    loft(bm, rings, METAL)
    add_box(bm, (0.0, 0.0, 0.765), (0.20, 0.035, 0.03), 0.0, METAL, rng, wear=0.002)
    grip = [(0.78, 0.014), (0.97, 0.014)]
    loft(bm, [ring_circle(0.0, 0.0, z, r, 10, warp_fn(noise3(rng, 3), z, 0.08)) for z, r in grip], METAL)
    pommel = [(0.97, 0.020), (1.00, 0.030), (1.05, 0.030), (1.10, 0.012)]
    loft(bm, [ring_circle(0.0, 0.0, z, r, 10) for z, r in pommel], METAL)


def build_rook(bm, rng):
    """Oversized weathered stone rook, 2.5 m: plinth, tapered shaft, collar, four merlons."""
    noise = noise3(rng)
    prof = [(0.0, 0.62), (0.22, 0.62), (0.25, 0.50), (0.9, 0.44), (2.0, 0.36),
            (2.0, 0.46), (2.2, 0.46), (2.2, 0.40)]
    loft(bm, [ring_circle(0.0, 0.0, z, r, 24, warp_fn(noise, z, 0.07)) for z, r in prof], STONE)
    for k in range(4):
        th = k * math.pi / 2.0
        c = Vector((0.36 * math.cos(th), 0.36 * math.sin(th), 2.35))
        add_box(bm, c, (0.20, 0.20, 0.30), th, STONE, rng, wear=0.005)


def build_crown(bm, rng):
    """Cracked metal ring with five points, 0.6 m dia, lower half sunk (only the visible
    band above ground is built, so the mesh starts at z=0)."""
    R, W, H = 0.265, 0.035, 0.12
    zc, hh = H / 2.0, H / 2.0
    section = [(W, 0.0), (0.7 * W, 0.7 * hh), (0.0, hh), (-0.7 * W, 0.7 * hh),
               (-W, 0.0), (-0.7 * W, -0.7 * hh), (0.0, -hh), (0.7 * W, -0.7 * hh)]
    # Two gaps (cracks) of 0.3 rad each.
    arcs = [(0.55, 2.95), (3.25, 0.25 + 2.0 * math.pi)]
    for a0, a1 in arcs:
        n = max(3, int((a1 - a0) / 0.25))
        rings = []
        for i in range(n + 1):
            th = a0 + (a1 - a0) * i / n
            c = Vector((R * math.cos(th), R * math.sin(th), zc))
            rad = Vector((math.cos(th), math.sin(th), 0.0))
            pts = []
            for dr, dz in section:
                jr = 1.0 + rng.uniform(-0.12, 0.12)
                jz = 1.0 + rng.uniform(-0.12, 0.12)
                pts.append(c + rad * (dr * jr) + Vector((0.0, 0.0, dz * jz)))
            rings.append(pts)
        loft(bm, rings, METAL)
    # Five points on the top edge, clear of the cracks.
    for th, ht in [(0.9, 0.13), (1.7, 0.10), (2.4, 0.15), (4.0, 0.11), (5.2, 0.14)]:
        rad = Vector((math.cos(th), math.sin(th), 0.0))
        tan = Vector((-math.sin(th), math.cos(th), 0.0))
        base = Vector((R * math.cos(th), R * math.sin(th), H - 0.01))
        corners = [base + tan * 0.028 + rad * 0.03, base - tan * 0.028 + rad * 0.03,
                   base - tan * 0.028 - rad * 0.03, base + tan * 0.028 - rad * 0.03]
        bv = [bm.verts.new(p) for p in corners]
        bm.faces.new(bv).material_index = METAL
        apex = bm.verts.new(base + rad * 0.01 + Vector((0.0, 0.0, ht)))
        for k in range(4):
            bm.faces.new((bv[k], bv[(k + 1) % 4], apex)).material_index = METAL


# ---------------------------------------------------------------- specs

SPECS = [
    dict(name="staircase_to_nowhere", build=build_stair, seed=1501, smooth=False,
         tri_max=TRI_MAX, dz=(3.97, 4.03), dxy=None),
    dict(name="rusted_sword", build=build_sword, seed=1502, smooth=True,
         tri_max=TRI_MAX, dz=(1.08, 1.12), dxy=None),
    dict(name="stone_chess_piece", build=build_rook, seed=1503, smooth=True,
         tri_max=TRI_MAX, dz=(2.48, 2.52), dxy=None),
    dict(name="broken_crown", build=build_crown, seed=1504, smooth=True,
         tri_max=TRI_MAX, dz=(0.20, 0.35), dxy=(0.54, 0.66)),
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
        bsdf.inputs["Base Color"].default_value = RUST_RGB
        bsdf.inputs["Metallic"].default_value = 0.55
        bsdf.inputs["Roughness"].default_value = 0.7
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
        bsdf.inputs["Roughness"].default_value = 0.8
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
    """Uniform UV scale so one texture repeat covers about `target` metres."""
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
        "# Authored anomalies (Blender headless)",
        "",
        f"Generated by `Tools/Author-Anomalies.py` under Blender {bpy.app.version_string}. "
        "Deterministic (fixed per-asset seeds), idempotent. Regenerate with:",
        "",
        "    \"C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe\" -b --factory-startup -P Tools/Author-Anomalies.py",
        "",
        "Units: metres. Source is Z-up. FBX written with axis_forward -Z, axis_up Y (Unreal convention); "
        "GLB is glTF Y-up. Origin at ground contact (min Z = 0, bounding-box centre on XY).",
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
        "Asset intent (unreal-region discoveries):",
        "- staircase_to_nowhere: 4 m spiral stone stair, 20 cantilevered treads on a central spine, "
        "open top; the last tread ends in air with no landing.",
        "- rusted_sword: 1.1 m blade set tip-down at ground contact, guard, grip, pommel. Rust on Metal slot.",
        "- stone_chess_piece: 2.5 m weathered stone rook, plinth, tapered shaft, collar, four merlons.",
        "- broken_crown: 0.6 m dia cracked metal ring with five points. Lower half is sunk, so only the "
        "visible band above ground is built (mesh starts at z=0). Two cracks in the band.",
        "",
        "## Materials",
        "",
        "- `Stone`: Principled BSDF, base colour from rock_01_diff_1k.jpg, normal from "
        "rock_01_nor_gl_1k.jpg (Non-Color), roughness 0.8.",
        f"- `Metal`: rust-coloured flat colour {RUST_RGB[:3]}, metallic 0.55, roughness 0.7. No texture.",
        "",
        "## UV",
        "",
        "One UV set `UVMap` per mesh, from Blender smart project (non-overlapping islands, "
        f"island margin 0.01). Layout is uniformly scaled so one texture repeat is about {UV_M_PER_TILE:.1f} m. "
        "UVs extend beyond 0 to 1 by design; the textures tile.",
        "",
        "## Texture provenance",
        "",
        "- Stone reuses `ArtSource/PolyHaven/rock_01/` (PolyHaven, CC0). No self-authored textures "
        "were needed; Metal is a flat rust colour.",
        "- FBX export copies textures into `<name>.fbm/` beside each .fbx when present. GLB embeds them.",
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
