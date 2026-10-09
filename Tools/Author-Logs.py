"""Author fallen-log and deadwood meshes headless in Blender.

Run from repo root:
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools/Author-Logs.py

Deterministic (fixed per-variant seeds) and idempotent (scene is cleared and
outputs are overwritten on every run). Writes to ArtSource/Authored/Logs/:
    <name>.fbx, <name>.glb (+ <name>.fbm/ texture copies for FBX), README.md
Units: metres. Source is Z-up; FBX exported Y-up (-Z forward, Y up) for Unreal.
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
OUT = os.path.join(REPO, "ArtSource", "Authored", "Logs")
TEX_DIR = os.path.join(REPO, "ArtSource", "PolyHaven", "pine_tree_01", "textures")
DIFF = os.path.join(TEX_DIR, "pine_tree_01_bark_diff_1k.jpg")
NOR = os.path.join(TEX_DIR, "pine_tree_01_bark_nor_gl_1k.jpg")

TRI_MIN, TRI_MAX = 2000, 15000

VARIANTS = [
    dict(name="log_long", kind="log", length=6.0, radius=0.225,
         radial=40, lseg=80, seed=101, moss=False, rotten=False),
    dict(name="log_short", kind="log", length=3.0, radius=0.175,
         radial=32, lseg=40, seed=202, moss=False, rotten=False),
    dict(name="log_mossy_rotten", kind="log", length=4.0, radius=0.225,
         radial=36, lseg=64, seed=303, moss=True, rotten=True),
    dict(name="stump_snag", kind="stump", height=1.2, radius=0.22,
         radial=32, lseg=32, seed=404, moss=False, rotten=False),
]


def smooth(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a)))
    return x * x * (3.0 - 2.0 * x)


def make_noise(rng, n=5):
    terms = [(rng.uniform(0.5, 4.0), rng.randint(1, 6),
              rng.uniform(0.0, 2 * math.pi), rng.uniform(0.01, 0.035))
             for _ in range(n)]

    def f(t, th):
        return sum(a * math.sin(ft * t * 2 * math.pi + k * th + p)
                   for ft, k, p, a in terms)
    return f


def build_log(v, rng):
    L, R, n, m = v["length"], v["radius"], v["radial"], v["lseg"]
    noise = make_noise(rng)
    bm = bmesh.new()
    vmeta = {}
    rings = []
    for i in range(m + 1):
        t = i / m
        ring = []
        for j in range(n):
            th = 2 * math.pi * j / n
            f = 1.0 + noise(t, th) - 0.08 * math.sin(math.pi * t) ** 2
            if v["rotten"]:
                top = max(0.0, math.sin(th))
                f *= 1.0 - 0.5 * smooth(0.55, 0.75, t) * top ** 2
                crev = math.exp(-((th - math.pi / 2) / 0.18) ** 2)
                f *= 1.0 - 0.35 * crev * smooth(0.1, 0.3, t) * (1.0 - smooth(0.6, 0.8, t))
            rr = R * f
            vt = bm.verts.new((L * t, rr * math.cos(th), R + rr * math.sin(th)))
            ring.append(vt)
            vmeta[vt] = (j / n, t)
        rings.append(ring)
    c0 = bm.verts.new((0.0, 0.0, R))
    c1 = bm.verts.new((L, 0.0, R))
    for i in range(m):
        a, b = rings[i], rings[i + 1]
        for j in range(n):
            j2 = (j + 1) % n
            bm.faces.new((a[j], a[j2], b[j2], b[j]))
    for j in range(n):
        j2 = (j + 1) % n
        bm.faces.new((c0, rings[0][j2], rings[0][j]))
        bm.faces.new((c1, rings[-1][j], rings[-1][j2]))
    return bm, vmeta, (1.0, 0.0, 0.0), R


def build_stump(v, rng):
    H, R, n, m = v["height"], v["radius"], v["radial"], v["lseg"]
    noise = make_noise(rng)
    jag = [rng.uniform(0.0, 0.25) for _ in range(n)]
    bm = bmesh.new()
    vmeta = {}
    rings = []
    for i in range(m + 1):
        t = i / m
        ring = []
        for j in range(n):
            th = 2 * math.pi * j / n
            rr = R * (1.0 + noise(t, th)) * (1.0 - 0.3 * t)
            vt = bm.verts.new((rr * math.cos(th), rr * math.sin(th), t * (H - jag[j])))
            ring.append(vt)
            vmeta[vt] = (j / n, t)
        rings.append(ring)
    c_bot = bm.verts.new((0.0, 0.0, 0.0))
    c_top = bm.verts.new((0.0, 0.0, H - sum(jag) / n))
    for i in range(m):
        a, b = rings[i], rings[i + 1]
        for j in range(n):
            j2 = (j + 1) % n
            bm.faces.new((a[j], a[j2], b[j2], b[j]))
    for j in range(n):
        j2 = (j + 1) % n
        bm.faces.new((c_bot, rings[0][j2], rings[0][j]))
        bm.faces.new((c_top, rings[-1][j], rings[-1][j2]))
    return bm, vmeta, (0.0, 0.0, 1.0), R


def finalize(bm, vmeta, axis, R, v):
    ax = Vector(axis)
    bm.verts.index_update()
    minz = min(vv.co.z for vv in bm.verts)
    for vv in bm.verts:
        vv.co.z -= minz
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    mid = max(vv.co.dot(ax) for vv in bm.verts) / 2.0
    uv = bm.loops.layers.uv.new("UVMap")
    flags = []
    for f in bm.faces:
        # Cap faces are exactly the fan triangles that touch a centre vertex
        # (not in vmeta). Normal test misclassifies steep jagged-stump fan tris.
        cap = any(lp.vert not in vmeta for lp in f.loops)
        f.material_index = 0
        if cap:
            ci = 1 if f.calc_center_median().dot(ax) > mid else 0
            for lp in f.loops:
                p = lp.vert.co
                if v["kind"] == "log":
                    a, b = p.y, p.z - R
                else:
                    a, b = p.x, p.y
                a = max(-1.0, min(1.0, a / R))
                b = max(-1.0, min(1.0, b / R))
                lp[uv].uv = (0.05 + 0.1 * ci + 0.04 * a, 1.09 + 0.04 * b)
        else:
            for lp in f.loops:
                lp[uv].uv = vmeta[lp.vert]
            if v["moss"] and f.normal.z > 0.55:
                f.material_index = 1
        flags.append(not cap)
    me = bpy.data.meshes.new(v["name"])
    bm.to_mesh(me)
    bm.free()
    for p, s in zip(me.polygons, flags):
        p.use_smooth = s
    return me


def make_bark_mat():
    mat = bpy.data.materials.new("Bark")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tc = nodes.new("ShaderNodeTexImage")
    tc.image = bpy.data.images.load(DIFF, check_existing=True)
    links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
    tn = nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(NOR, check_existing=True)
    tn.image.colorspace_settings.name = "Non-Color"
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(tn.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def make_moss_mat():
    mat = bpy.data.materials.new("Moss")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (0.16, 0.34, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.95
    return mat


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


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
        "# Authored logs (Blender headless)",
        "",
        f"Generated by `Tools/Author-Logs.py` under Blender {bpy.app.version_string}. "
        "Deterministic (fixed per-variant seeds), idempotent. Regenerate with:",
        "",
        "    \"C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe\" -b -P Tools/Author-Logs.py",
        "",
        "Units: metres. Source is Z-up. FBX written with axis_forward -Z, axis_up Y (Unreal convention); "
        "GLB is glTF Y-up. Origin at base centre on the ground (min Z = 0). "
        "Logs lie along +X from x = 0 to x = L.",
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
        "Variant intent:",
        "- log_long: 6 m, 0.45 m dia nominal.",
        "- log_short: 3 m, 0.35 m dia nominal.",
        "- log_mossy_rotten: 4 m, 0.45 m dia nominal, partly collapsed and split along the top.",
        "- stump_snag: 1.2 m nominal height, broken top (about 0.95 to 1.2 m), 0.44 m dia nominal.",
        "",
        "## Materials",
        "",
        "- Slot 0 `Bark`: Principled BSDF, base colour from pine_tree_01_bark_diff_1k.jpg, "
        "normal from pine_tree_01_bark_nor_gl_1k.jpg (Non-Color), roughness 0.85.",
        "- Slot 1 `Moss` (log_mossy_rotten only): flat colour (0.16, 0.34, 0.09), roughness 0.95. "
        "Assigned to upward-facing faces (normal Z > 0.55), " + str(rows[2]["moss_tris"]) + " tris.",
        "",
        "## UV",
        "",
        "One UV set `UVMap`. Sides: u = angle / 2 pi, v = 0 to 1 along length. Texel density is "
        "anisotropic and not tiling-correct; no tiling is applied. Caps sit in separate islands at "
        "v 1.05 to 1.13, so they do not overlap the sides.",
        "",
        "## Texture provenance",
        "",
        "- Bark diffuse and GL normal are reused from `ArtSource/PolyHaven/pine_tree_01/textures/` "
        "(PolyHaven, CC0). No self-authored textures.",
        "- FBX export copies the textures into `<name>.fbm/` beside each .fbx. GLB embeds them.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    clear_scene()
    bark = make_bark_mat()
    moss = make_moss_mat()
    rows = []
    ok = True
    for v in VARIANTS:
        rng = random.Random(v["seed"])
        if v["kind"] == "log":
            bm, vmeta, axis, R = build_log(v, rng)
        else:
            bm, vmeta, axis, R = build_stump(v, rng)
        me = finalize(bm, vmeta, axis, R, v)
        me.materials.append(bark)
        slots = "0 Bark"
        if v["moss"]:
            me.materials.append(moss)
            slots = "0 Bark, 1 Moss"
        obj = bpy.data.objects.new(v["name"], me)
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.update()

        tris = len(me.polygons)
        all_tri = all(len(p.vertices) == 3 for p in me.polygons)
        dims = obj.dimensions
        in_range = TRI_MIN <= tris <= TRI_MAX and all_tri
        if v["kind"] == "log":
            len_ok = abs(dims.x - v["length"]) < 0.01
        else:
            len_ok = 0.9 <= dims.z <= 1.25
        moss_tris = sum(1 for p in me.polygons if p.material_index == 1)
        ok = ok and in_range and len_ok
        print(f"TRIS {v['name']} {tris} range_ok={in_range} dims_ok={len_ok} "
              f"dims_m=({dims.x:.3f}, {dims.y:.3f}, {dims.z:.3f})")
        export(obj, v["name"])
        rows.append(dict(name=v["name"], tris=tris,
                         dims=f"{dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}",
                         slots=slots, moss_tris=moss_tris))

    if not ok:
        print("FAIL: tri count or dimension out of range")
        raise SystemExit(1)
    write_readme(rows)
    print(f"PASS: {len(rows)} variants written to {OUT}")


main()
