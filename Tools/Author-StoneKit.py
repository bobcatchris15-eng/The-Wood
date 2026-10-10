"""Blender authoring of the dry-stone and masonry ruin kit (WoodDiscovery mesh names).

Run: blender -b --factory-startup -P Tools/Author-StoneKit.py
Outputs ArtSource/Prepared/kit_sm_*.glb. Names, footprints, pivots (base centre, Z up), wall-run yaw convention
and kit ids match the procedural kit in Prepare-Art.py, which no longer writes these eight files.
Each piece is built from individual irregular stones: bevelled, subdivided and displaced blocks of varied size.
Slot 0 Stone: CC0 AmbientCG Rock064 1K (tileable; desaturated). Slot 1 Moss: CC0 AmbientCG Moss002 1K (ArtSource/AmbientCG/Moss002), desaturated, on upward faces only.
Box-projected UV at 1 tile per 1.25 m for stone, 1 tile per 0.5 m for moss.
"""
import bpy
import bmesh
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1] if '__file__' in globals() else Path.cwd()
OUT = ROOT / 'ArtSource' / 'Prepared'
ROCK = ROOT / 'ArtSource' / 'AmbientCG' / 'Rock064'  # tileable CC0 stacked stone; rock_07 is a one-off boulder UV atlas (the shattered look)
MOSS = ROOT / 'ArtSource' / 'AmbientCG' / 'Moss002'
STONE_AUTHOR_SEED = 9100
TAU = 2.0 * math.pi
UV_SCALE = 1.0 / 1.25
MOSS_UV_SCALE = 1.0 / 0.5
MOSS_SATURATION = 0.45  # fraction of the source chroma kept
MOSS_VALUE = 0.72


def wobble(p):
    """Smooth deterministic field in about [-1, 1] over position; irregularises stone faces."""
    return 0.5 * (math.sin(p.x * 41.7 + p.y * 13.1) * math.cos(p.y * 29.3 - p.z * 17.9 + p.x * 3.7)
                  + math.sin(p.z * 57.3 + p.x * 9.1))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def stone(bm, rng, center, size, yaw=0.0, bevel=0.025, jitter=0.012, lean=0.02, cuts=1):
    """One irregular stone. size = (X thickness, Y length, Z height). Jittered corners, lean, 2-segment bevel,
    then edge subdivision so the displacement pass has surface to work on."""
    before = set(bm.faces)
    cube = bmesh.ops.create_cube(bm, size=1.0)['verts']
    sx, sy, sz = size
    c, s = math.cos(yaw), math.sin(yaw)
    lean_x = rng.uniform(-lean, lean)
    lean_y = rng.uniform(-lean, lean)
    for v in cube:
        x = v.co.x * sx + rng.uniform(-jitter, jitter)
        y = v.co.y * sy + rng.uniform(-jitter, jitter)
        z = v.co.z * sz + rng.uniform(-jitter, jitter)
        x += lean_x * z
        y += lean_y * z
        v.co = Vector((x * c - y * s + center[0], x * s + y * c + center[1], z + center[2]))
    edges = list({e for v in cube for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=2, affect='EDGES', clamp_overlap=True)
    if cuts:
        new_faces = [f for f in bm.faces if f not in before]
        sub = list({e for f in new_faces for e in f.edges})
        bmesh.ops.subdivide_edges(bm, edges=sub, cuts=cuts, use_grid_fill=True)


def tag_axes(bm):
    """Box-projection axis per face from the pre-displacement normal. Displacement makes small bevel and cut faces flip
    axis at random, which shattered the texture into a triangulated patchwork; the axis is fixed before displacement."""
    bm.normal_update()
    layer = bm.faces.layers.int.new('proj_axis')
    for face in bm.faces:
        n = face.normal
        face[layer] = max(range(3), key=lambda i: abs(n[i]))


def displace(bm, amount):
    """Push every vertex along its normal by a smooth field. Base stays flat (ground contact)."""
    bm.normal_update()
    for v in bm.verts:
        k = smooth((v.co.z - 0.01) / 0.05)
        v.co = v.co + v.normal * (amount * wobble(v.co) * k)
    bm.normal_update()


def finalize(bm, rotate_length):
    """Optional length-on-X rotation, base centre to origin, moss on patchy upward faces, box UV."""
    if rotate_length:
        for v in bm.verts:
            v.co = Vector((-v.co.y, v.co.x, v.co.z))
    bm.normal_update()
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    minz = min(v.co.z for v in bm.verts)
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    for v in bm.verts:
        v.co = v.co - Vector((cx, cy, minz))
    for face in bm.faces:
        centre = face.calc_center_median()
        upward = face.normal.z > 0.7 and centre.z > 0.08
        face.material_index = 1 if upward else 0
    layer = bm.loops.layers.uv.new('UVMap')
    axis_layer = bm.faces.layers.int.get('proj_axis')
    for face in bm.faces:
        axis = face[axis_layer]
        if rotate_length and axis < 2:
            axis = 1 - axis  # the length rotation swaps X and Y
        for loop in face.loops:
            p = loop.vert.co
            pair = ((p.y, p.z), (p.x, p.z), (p.x, p.y))[axis]
            scale = MOSS_UV_SCALE if face.material_index == 1 else UV_SCALE
            loop[layer].uv = (pair[0] * scale, pair[1] * scale)


def build_wall(bm, rng):
    # 3 courses of irregular stones spanning 2.0 m; top course broken (one gap, others stepped down).
    thick, length, courses = 0.6, 2.0, 3
    ch = 1.0 / courses
    for row in range(courses):
        weights = [rng.uniform(0.6, 1.4) for _ in range(6)]
        total = sum(weights)
        y = -length / 2.0
        gap_used = False
        for index, w in enumerate(weights):
            run = length * w / total
            z0 = row * ch + 0.005
            h = ch - 0.02
            if row == courses - 1:
                roll = rng.random()
                if roll < 0.18 and not gap_used and 0 < index < len(weights) - 1:
                    gap_used = True
                    y += run
                    continue
                if roll < 0.5:
                    h *= rng.uniform(0.5, 0.8)
            stone(bm, rng, (rng.uniform(-0.012, 0.012), y + run / 2.0, z0 + h / 2.0),
                  (thick - 0.04, run - 0.03, h), yaw=rng.uniform(-0.03, 0.03), lean=0.025)
            y += run


def build_rubble(bm, rng):
    for _ in range(rng.randint(16, 22)):
        radius = 0.85 * math.sqrt(rng.random())
        angle = rng.uniform(0.0, TAU)
        size = (rng.uniform(0.25, 0.5), rng.uniform(0.2, 0.35), rng.uniform(0.12, 0.2))
        stone(bm, rng, (radius * math.cos(angle), radius * math.sin(angle), size[2] / 2.0), size,
              yaw=rng.uniform(0.0, TAU), bevel=0.02, jitter=0.01)


def build_foundation(bm, rng):
    # One course, 1.6 m total length in irregular stones (length on Y before rotation).
    parts = [rng.uniform(0.22, 0.4) for _ in range(6)]
    scale = 1.6 / sum(parts)
    y = -0.8
    for part in parts:
        run = part * scale
        stone(bm, rng, (rng.uniform(-0.01, 0.01), y + run / 2.0, 0.225), (0.57, run - 0.03, 0.43),
              yaw=rng.uniform(-0.02, 0.02), lean=0.015, cuts=2)
        y += run


def build_pier(bm, rng, courses=4, top_chance=0.5):
    # 0.8 x 0.8 footprint: two rows of stones per course (x = -0.2 and +0.2), 0.4 m courses, stepped top.
    for row in range(courses):
        base = row * 0.4 + 0.01
        height = 0.38
        for side in (-0.2, 0.2):
            weights = [rng.uniform(0.7, 1.3) for _ in range(3)]
            total = sum(weights)
            y = -0.4
            for w in weights:
                run = 0.8 * w / total
                h = height
                if row == courses - 1 and rng.random() < top_chance:
                    h *= rng.uniform(0.55, 0.8)
                stone(bm, rng, (side + rng.uniform(-0.01, 0.01), y + run / 2.0, base + h / 2.0),
                      (0.37, run - 0.03, h - 0.02), yaw=rng.uniform(-0.04, 0.04), bevel=0.025, lean=0.02)
                y += run


def build_pier_ruined(bm, rng):
    build_pier(bm, rng, courses=2, top_chance=0.0)
    stone(bm, rng, (0.75, 0.3, 0.13), (0.45, 0.32, 0.26), yaw=0.6, bevel=0.025, cuts=2)


def build_abutment(bm, rng):
    # Three courses of stones on each bank face, capped with one overhanging slab. Length on X before finalize.
    for row in range(3):
        for side in (-0.405, 0.405):
            weights = [rng.uniform(0.7, 1.3) for _ in range(3)]
            total = sum(weights)
            y = -0.5
            for w in weights:
                run = 1.0 * w / total
                stone(bm, rng, (side + rng.uniform(-0.01, 0.01), y + run / 2.0, row * 0.4 + 0.2),
                      (0.76, run - 0.03, 0.36), yaw=rng.uniform(-0.02, 0.02), lean=0.015)
                y += run
    stone(bm, rng, (0.0, 0.0, 1.26), (1.7, 1.1, 0.12), yaw=rng.uniform(-0.01, 0.01), bevel=0.02, cuts=2)


def build_stepping(bm, rng):
    stone(bm, rng, (0.0, 0.0, 0.14), (0.58, 0.68, 0.28), yaw=rng.uniform(-0.2, 0.2), bevel=0.04,
          jitter=0.012, lean=0.01, cuts=5)


def build_debris(bm, rng):
    for _ in range(rng.randint(12, 16)):
        radius = 0.32 * math.sqrt(rng.random())
        angle = rng.uniform(0.0, TAU)
        size = (rng.uniform(0.12, 0.25), rng.uniform(0.12, 0.25), rng.uniform(0.06, 0.14))
        stone(bm, rng, (radius * math.cos(angle), radius * math.sin(angle), size[2] / 2.0), size,
              yaw=rng.uniform(0.0, TAU), bevel=0.012, jitter=0.008, lean=0.0)


def desaturated_moss(source=None, target=None, saturation=MOSS_SATURATION, value=MOSS_VALUE):
    """Soft colour: keep `saturation` of the source chroma and scale value, written beside the prepared kit."""
    import numpy as np
    image = bpy.data.images.load(str(source or MOSS / 'Moss002_1K-JPG_Color.jpg'), check_existing=False)
    width, height = image.size
    px = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    luma = (px[:, 0] * 0.2126 + px[:, 1] * 0.7152 + px[:, 2] * 0.0722)[:, None]
    px[:, :3] = (luma + (px[:, :3] - luma) * saturation) * value
    image.pixels.foreach_set(px.reshape(-1))
    target = target or OUT / 'Moss002_soft_color.png'
    image.filepath_raw = str(target)
    image.file_format = 'PNG'
    image.save()
    return target


def make_surface(name, colour_file, normal_file, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    shader = tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = roughness
    colour = tree.nodes.new('ShaderNodeTexImage')
    colour.image = bpy.data.images.load(str(colour_file), check_existing=True)
    tree.links.new(colour.outputs['Color'], shader.inputs['Base Color'])
    normal_tex = tree.nodes.new('ShaderNodeTexImage')
    normal_tex.image = bpy.data.images.load(str(normal_file), check_existing=True)
    normal_tex.image.colorspace_settings.name = 'Non-Color'
    normal_map = tree.nodes.new('ShaderNodeNormalMap')
    tree.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
    tree.links.new(normal_map.outputs['Normal'], shader.inputs['Normal'])
    return mat


PIECES = (
    ('SM_DryStone_Wall', build_wall, True),
    ('SM_DryStone_Rubble', build_rubble, False),
    ('SM_StonePier', build_pier, False),
    ('SM_StonePier_Ruined', build_pier_ruined, False),
    ('SM_FoundationCourse', build_foundation, True),
    ('SM_MasonryDebris', build_debris, False),
    ('SM_BridgeAbutment', build_abutment, False),
    ('SM_RiverSteppingStone', build_stepping, False),
)
DISPLACE = {'SM_DryStone_Wall': 0.012, 'SM_FoundationCourse': 0.01, 'SM_StonePier': 0.012,
            'SM_StonePier_Ruined': 0.012, 'SM_BridgeAbutment': 0.012}


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OUT.mkdir(parents=True, exist_ok=True)
    stone_mat = make_surface('M_StoneKit_Stone', desaturated_moss(ROCK / 'Rock064_1K-PNG_Color.png', OUT / 'Rock064_soft_color.png', 0.3, 0.95),
                              ROCK / 'Rock064_1K-PNG_NormalGL.png', 0.82)
    moss_mat = make_surface('M_StoneKit_Moss', desaturated_moss(),
                            MOSS / 'Moss002_1K-JPG_NormalGL.jpg', 0.9)
    for index, (name, build, rotate) in enumerate(PIECES):
        rng = random.Random(STONE_AUTHOR_SEED + index)
        bm = bmesh.new()
        build(bm, rng)
        tag_axes(bm)
        displace(bm, DISPLACE.get(name, 0.01))
        finalize(bm, rotate)
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(stone_mat)
        mesh.materials.append(moss_mat)
        mesh.calc_loop_triangles()
        triangles = len(mesh.loop_triangles)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        file_name = 'kit_' + name.lower() + '.glb'
        bpy.ops.export_scene.gltf(filepath=str(OUT / file_name), export_format='GLB', use_selection=True)
        verts = [v.co for v in mesh.vertices]
        dims = [round(max(p[i] for p in verts) - min(p[i] for p in verts), 3) for i in range(3)]
        print(f'{file_name}: tris {triangles} dims {dims}')
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


main()
