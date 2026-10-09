"""Author stylised low-poly creature meshes (deer, fox, hare, crow, owl, elk, bear, heron).

Run from repo root:
  blender.exe -b --factory-startup -P Tools/Author-Creatures.py

Writes to ArtSource/Authored/Creatures/:
  <species>.fbx, <species>.glb, <species>_albedo.png (256 px flat albedo), README.md

Deterministic (no RNG). Metres, Z-up, origin at ground between feet, faces +X.
Geometry: shaped primitives (ellipsoids, cones) overlapped, Catmull-Clark x1,
triangulated, smooth normals, smart-project UV0, one material slot
("Fur" for mammals, "Feather" for birds).
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

try:
    _HERE = os.path.abspath(__file__)
except NameError:
    _HERE = os.path.abspath(os.path.join(os.getcwd(), "Tools", "Author-Creatures.py"))
ROOT = os.path.dirname(os.path.dirname(_HERE))
OUT = os.path.join(ROOT, "ArtSource", "Authored", "Creatures")
TRI_MIN, TRI_MAX = 1500, 8000
TEX_SIZE = 256

# Subdivision segments: (u, v, cone). Same for all species.
SEG = (10, 6, 8)

# ---------------------------------------------------------------- primitives


def _mat_ell(c, size):
    # bmesh UV sphere has radius 1; scaling by size/2 gives full extent = size.
    return Matrix.Translation(Vector(c)) @ Matrix.Diagonal(
        Vector((size[0] / 2.0, size[1] / 2.0, size[2] / 2.0, 1.0)))


def _mat_dir(base, d, length, radius):
    # bmesh cone has depth 2 along Z, radius 1; map Z onto d, centre at base + d*len/2.
    d = Vector(d).normalized()
    rot = d.to_track_quat("Z", "X").to_matrix().to_4x4()
    centre = Vector(base) + d * (length / 2.0)
    return Matrix.Translation(centre) @ rot @ Matrix.Diagonal(
        Vector((radius, radius, length / 2.0, 1.0)))


class Builder:
    def __init__(self):
        self.bm = bmesh.new()

    def ell(self, c, size):
        bmesh.ops.create_uvsphere(
            self.bm, u_segments=SEG[0], v_segments=SEG[1], radius=1.0,
            matrix=_mat_ell(c, size), calc_uvs=False)

    def cone(self, base, d, length, radius, taper=1.0):
        bmesh.ops.create_cone(
            self.bm, cap_ends=True, cap_tris=False, segments=SEG[2],
            radius1=1.0, radius2=max(taper, 0.05), depth=2.0,
            matrix=_mat_dir(base, d, length, radius), calc_uvs=False)


# ---------------------------------------------------------------- quadrupeds


def build_quad(b, p):
    L, H, W, Lg, lr = p["L"], p["H"], p["W"], p["Lg"], p["lr"]
    zb = Lg + H * 0.5
    # torso, chest, haunch
    b.ell((0.0, 0.0, zb), (L, W, H))
    b.ell((L * 0.22, 0.0, zb + H * 0.04), (L * 0.45, W * 1.02, H * 1.05))
    b.ell((-L * 0.30, 0.0, zb), (L * 0.40, W * 0.95, H * 0.95))
    # legs with hooves
    for x in (L * 0.32, -L * 0.32):
        for y in (W * 0.30, -W * 0.30):
            b.cone((x, y, 0.0), (0, 0, 1), Lg, lr, taper=0.8)
            b.ell((x, y, 0.0), (lr * 2.6, lr * 2.4, lr * 1.2))
    # neck, head, muzzle
    th, N, nr = p["theta"], p["N"], p["nr"]
    d = Vector((math.sin(th), 0.0, math.cos(th)))
    base = Vector((L * 0.42, 0.0, Lg + H * 0.6))
    b.cone(base, d, N, nr, taper=0.85)
    top = base + d * N
    hl, hw, hh = p["hl"], p["hw"], p["hh"]
    head = top + Vector((hl * 0.3, 0.0, hh * 0.1))
    b.ell(head, (hl, hw, hh))
    b.ell(head + Vector((hl * 0.5, 0.0, -hh * 0.25)), (hl * 0.6, hw * 0.75, hh * 0.6))
    # ears
    for s in (1, -1):
        if p.get("round_ears"):
            e = p["ear"] * 2.0
            b.ell(head + Vector((-hl * 0.1, s * hw * 0.8, hh * 0.7)), (e, e, e))
        else:
            b.cone(head + Vector((-hl * 0.1, s * hw * 0.45, hh * 0.5)),
                   Vector((-0.25, s * 0.25, 1.0)), p["ear"], p["ear_r"], taper=0.2)
    # antlers
    a = p.get("antlers")
    if a:
        for s in (1, -1):
            ab = head + Vector((-hl * 0.1, s * hw * 0.5, hh * 0.6))
            ad = Vector((-0.1, s * 0.25, 1.0)).normalized()
            b.cone(ab, ad, a["length"], a["r"], taper=0.6)
            for i in range(a["tines"]):
                tb = ab + ad * a["length"] * (0.35 + 0.25 * i)
                b.cone(tb, Vector((0.6, s * 0.8, 0.5)), a["length"] * 0.4, a["r"] * 0.7, taper=0.5)
    # tail
    tl, tr = p["tail"]
    b.cone(Vector((-L * 0.5, 0.0, zb + H * 0.2)), Vector((-1.0, 0.0, 0.5)), tl, tr, taper=0.5)


# ---------------------------------------------------------------- birds


def build_bird(b, p):
    legH, bL, bH, bW, hr = p["legH"], p["bL"], p["bH"], p["bW"], p["hr"]
    zb = legH + bH * 0.6
    # body
    b.ell((0.0, 0.0, zb), (bL, bW, bH))
    # legs
    for s in (1, -1):
        b.cone((0.0, s * bW * 0.22, 0.0), (0, 0, 1), legH, p["legs_r"], taper=0.7)
    # wings (flattened, lying along body)
    for s in (1, -1):
        b.ell((-bL * 0.08, s * bW * 0.52, zb + bH * 0.02), (bL * 0.75, bW * 0.3, bH * 0.7))
    # tail
    tl = p["tail"]
    b.ell((-bL * 0.5 - tl * 0.45, 0.0, zb - tl * 0.15), (tl, bW * 0.6, bH * 0.35))
    # neck and head
    nk = p["neck"]
    if nk > 0:
        nd = Vector((0.35, 0.0, 1.0)).normalized()
        base = Vector((bL * 0.3, 0.0, zb + bH * 0.3))
        b.cone(base, nd, nk, p["nr"], taper=0.85)
        top = base + nd * nk
    else:
        top = Vector((bL * 0.35, 0.0, zb + bH * 0.45))
    head = top
    b.ell(head, (hr * 2.0, hr * 2.0, hr * 2.0))
    # beak
    b.cone(head + Vector((hr * 0.8, 0.0, -hr * 0.1)), Vector((1.0, 0.0, -0.05)),
           p["beak"], p["beak_r"], taper=0.1)
    if p.get("owl"):
        # facial disk facing +X
        b.ell(head + Vector((hr * 0.7, 0.0, 0.0)), (hr * 0.25, hr * 2.1, hr * 2.1))
        # ear tufts
        for s in (1, -1):
            b.cone(head + Vector((0.0, s * hr * 0.6, hr * 0.7)),
                   Vector((0.1, s * 0.3, 1.0)), 0.07, 0.015, taper=0.1)


# ---------------------------------------------------------------- species table

SPECIES = [
    dict(name="deer", kind="quad", feather=False, colour=(0.45, 0.32, 0.20),
         measure="shoulder", target=1.00,
         p=dict(L=1.1, H=0.42, W=0.36, Lg=0.60, lr=0.05, theta=0.55, N=0.38, nr=0.08,
                hl=0.30, hw=0.14, hh=0.16, ear=0.12, ear_r=0.03,
                antlers=dict(length=0.30, tines=2, r=0.012), tail=(0.12, 0.05))),
    dict(name="elk", kind="quad", feather=False, colour=(0.36, 0.25, 0.15),
         measure="shoulder", target=1.50,
         p=dict(L=1.7, H=0.55, W=0.45, Lg=0.90, lr=0.06, theta=0.45, N=0.50, nr=0.10,
                hl=0.40, hw=0.18, hh=0.20, ear=0.14, ear_r=0.035,
                antlers=dict(length=0.55, tines=3, r=0.018), tail=(0.14, 0.06))),
    dict(name="bear", kind="quad", feather=False, colour=(0.24, 0.17, 0.11),
         measure="shoulder", target=1.10,
         p=dict(L=1.3, H=0.60, W=0.70, Lg=0.35, lr=0.11, theta=0.35, N=0.30, nr=0.20,
                hl=0.36, hw=0.26, hh=0.26, ear=0.08, round_ears=True, tail=(0.05, 0.05))),
    dict(name="fox", kind="quad", feather=False, colour=(0.75, 0.35, 0.10),
         measure="shoulder", target=0.40,
         p=dict(L=0.72, H=0.22, W=0.20, Lg=0.22, lr=0.03, theta=0.50, N=0.14, nr=0.06,
                hl=0.17, hw=0.09, hh=0.09, ear=0.09, ear_r=0.03, tail=(0.30, 0.09))),
    dict(name="hare", kind="quad", feather=False, colour=(0.60, 0.50, 0.35),
         measure="shoulder", target=0.30,
         p=dict(L=0.50, H=0.16, W=0.14, Lg=0.14, lr=0.016, theta=0.40, N=0.10, nr=0.05,
                hl=0.13, hw=0.07, hh=0.07, ear=0.16, ear_r=0.02, tail=(0.05, 0.05))),
    dict(name="crow", kind="bird", feather=True, colour=(0.05, 0.05, 0.07),
         measure="length", target=0.45,
         p=dict(legH=0.10, bL=0.24, bH=0.14, bW=0.13, hr=0.05, neck=0.03, nr=0.03,
                beak=0.07, beak_r=0.02, tail=0.18, legs_r=0.006)),
    dict(name="owl", kind="bird", feather=True, colour=(0.50, 0.40, 0.25),
         measure="height", target=0.50,
         p=dict(legH=0.05, bL=0.20, bH=0.34, bW=0.20, hr=0.09, neck=0.0, nr=0.0,
                beak=0.03, beak_r=0.012, tail=0.10, legs_r=0.008, owl=True)),
    dict(name="heron", kind="bird", feather=True, colour=(0.55, 0.60, 0.65),
         measure="height", target=1.00,
         p=dict(legH=0.60, bL=0.36, bH=0.20, bW=0.18, hr=0.05, neck=0.35, nr=0.018,
                beak=0.14, beak_r=0.012, tail=0.12, legs_r=0.007)),
]

# ---------------------------------------------------------------- scene helpers


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    for i in list(bpy.data.images):
        bpy.data.images.remove(i)


def make_material(slot, colour):
    img = bpy.data.images.new(slot + "_albedo", TEX_SIZE, TEX_SIZE, alpha=False)
    px = [colour[0], colour[1], colour[2], 1.0] * (TEX_SIZE * TEX_SIZE)
    img.pixels.foreach_set(px)
    tex_path = os.path.join(OUT, img_name_for(slot) + ".png")
    img.filepath_raw = tex_path
    img.file_format = "PNG"
    img.save()
    mat = bpy.data.materials.new(name=slot)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat, tex_path


_IMG_NAMES = {}


def img_name_for(slot):
    return _IMG_NAMES.get(slot, slot)


def measure(cos, kind, sp):
    zmin = min(c.z for c in cos)
    if kind == "shoulder":
        L = sp["p"]["L"]
        return max(c.z for c in cos if abs(c.x) <= 0.2 * L) - zmin, zmin
    if kind == "height":
        return max(c.z for c in cos) - zmin, zmin
    if kind == "length":
        return max(c.x for c in cos) - min(c.x for c in cos), zmin
    raise ValueError(kind)


def extents(cos):
    xs = [c.x for c in cos]
    ys = [c.y for c in cos]
    zs = [c.z for c in cos]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def build_species(sp):
    clear_scene()
    b = Builder()
    if sp["kind"] == "quad":
        build_quad(b, sp["p"])
    else:
        build_bird(b, sp["p"])
    bm = b.bm
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(sp["name"])
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(sp["name"], mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Catmull-Clark x1 then triangulate, baked via evaluated depsgraph.
    sub = obj.modifiers.new("Smooth", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    obj.modifiers.new("Triangulate", "TRIANGULATE")
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tmp = bpy.data.meshes.new_from_object(ev)
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)
    old = obj.data
    obj.data = tmp
    bpy.data.meshes.remove(old)

    # Measure raw, scale to target measure, bake ground-origin.
    cos = [v.co.copy() for v in tmp.vertices]
    raw, zmin = measure(cos, sp["measure"], sp)
    k = sp["target"] / raw
    for v, c in zip(tmp.vertices, cos):
        v.co = Vector((c.x * k, c.y * k, (c.z - zmin) * k))
    tmp.update()
    cos = [v.co.copy() for v in tmp.vertices]
    dims = extents(cos)
    final_val, _ = measure(cos, sp["measure"], sp)

    # Triangles.
    tris = len(tmp.polygons)
    if any(len(p.vertices) != 3 for p in tmp.polygons):
        raise RuntimeError("non-triangle polygon after triangulate: " + sp["name"])

    # Material, smooth shading, UV0.
    slot = "Feather" if sp["feather"] else "Fur"
    _IMG_NAMES[slot] = sp["name"]
    mat, tex_path = make_material(slot, sp["colour"])
    tmp.materials.clear()
    tmp.materials.append(mat)
    for poly in tmp.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Export.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx_path = os.path.join(OUT, sp["name"] + ".fbx")
    glb_path = os.path.join(OUT, sp["name"] + ".glb")
    bpy.ops.export_scene.fbx(
        filepath=fbx_path, use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
        axis_forward="X", axis_up="Z", bake_space_transform=False,
        use_mesh_modifiers=False, mesh_smooth_type="FACE",
        path_mode="RELATIVE", embed_textures=False,
        add_leaf_bones=False, bake_anim=False)
    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format="GLB", use_selection=True,
        export_apply=False)

    print("SPECIES %-6s tris=%5d dims_m=(%.3f, %.3f, %.3f) %s=%.3f"
          % (sp["name"], tris, dims[0], dims[1], dims[2], sp["measure"], final_val))
    return dict(name=sp["name"], tris=tris, dims=dims, measure=sp["measure"],
                value=final_val, target=sp["target"], slot=slot,
                tex=os.path.basename(tex_path))


def write_readme(rows):
    lines = [
        "# Creature meshes (ArtSource/Authored/Creatures)",
        "",
        "Generated by `Tools/Author-Creatures.py` (Blender 5.2 headless, deterministic).",
        "",
        "Conventions: metres, Z-up, origin at ground between feet, facing +X.",
        "Per species: `<species>.fbx` (axis forward X, up Z), `<species>.glb` (glTF Y-up),",
        "`<species>_albedo.png` (256 px flat albedo, referenced by the single material slot).",
        "Material slot: `Fur` (mammals) or `Feather` (birds). UV0 is non-overlapping smart projection.",
        "",
        "| Species | Files | Tris | Dims X x Y x Z (m) | Measure | Target (m) | Slot |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append("| %s | %s.fbx, %s.glb, %s | %d | %.3f x %.3f x %.3f | %s %.3f | %.2f | %s |"
                     % (r["name"], r["name"], r["name"], r["tex"], r["tris"],
                        r["dims"][0], r["dims"][1], r["dims"][2],
                        r["measure"], r["value"], r["target"], r["slot"]))
    lines += [
        "",
        "Measures: `shoulder` = top of torso above ground (vertices with |x| <= 0.2 * body length);",
        "`height` = Z extent; `length` = X extent.",
        "",
        "## Provenance",
        "",
        "All geometry is procedural: shaped UV-sphere ellipsoids and cones built in",
        "`Tools/Author-Creatures.py`, overlapped, Catmull-Clark subdivided once, triangulated.",
        "No third-party meshes are used. Checked `C:\\Misc\\Vivarium`: it contains CC0 surface",
        "textures (ambientCG, Poly Haven) but no creature meshes, so nothing was copied or converted.",
        "Colours are authored flat albedos, not sampled from any source.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    bad = []
    for sp in SPECIES:
        row = build_species(sp)
        rows.append(row)
        if not (TRI_MIN <= row["tris"] <= TRI_MAX):
            bad.append("%s tris=%d outside %d-%d" % (sp["name"], row["tris"], TRI_MIN, TRI_MAX))
    write_readme(rows)
    total = sum(r["tris"] for r in rows)
    print("DONE species=%d total_tris=%d out=%s" % (len(rows), total, OUT))
    if bad:
        for line in bad:
            print("ERR_RANGE:", line)
        raise SystemExit(1)


main()
