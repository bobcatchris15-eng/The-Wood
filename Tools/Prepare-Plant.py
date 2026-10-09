"""Blender background preparation of a source plant mesh for Unreal foliage.

Emits, per source plant: a ground-contact pivot at the true rooted base rather
than the object origin, a wind-weight attribute that holds the base still and
moves the canopy, alpha-ready material naming, and a distance LOD stage. Every
stage is verified and recorded so Specification.md section 10's pipeline checks
(scale, ground contact, normals, alpha masking, wind weights, collision,
instancing compatibility, distance detail) have machine-readable evidence.

Run headless:
    blender --background --python Tools/Prepare-Plant.py -- \
        ArtSource/PolyHaven/<asset>/<asset>.gltf --asset <asset> [options]

    --asset NAME         report/output stem (defaults to the source file stem)
    --kind KIND          plant | canopy | shrub | fern | grass (default plant)
    --target-height M    rescale so the prepared plant is M metres tall
    --base-band M        height of the rooted base band used for the pivot
    --lods N             number of distance LOD stages, 2-3 (default 3)
    --output DIR         destination directory (default ArtSource/Prepared/Plants)

Exits 0 when every Specification.md section 10 check passes and 2 when any check
fails, so a caller can trust the exit code instead of reading the traceback.
No engine work is performed or required by this script.
"""
import bpy
import json
import struct
import sys
import math
import numpy as np
from array import array
from pathlib import Path
from mathutils import Vector

ALPHA_CUTOFF = 0.35
WIND_ATTRIBUTE = '_WIND'
WIND_UV = 'WindMask'
# Understory ratios match Tools/BootstrapEditor.py author_lods grasses/ferns.
LOD_RATIOS = (1.0, 0.5, 0.2)
# A LOD must retain at least this much of the readable silhouette, and must keep
# the rooted base band so distance detail thins the canopy without making a
# standing plant look shrinking or floating. The base band is protected from
# collapse outright, so its measured retention should sit at 1.0.
LOD_SILHOUETTE_MINIMUM = 0.75
LOD_BASE_FRACTION = 0.95
# Height slabs used to compare a LOD's outline against LOD0's.
LOD_SLABS = 12
# A slab may lose this fraction of the plant's widest reach without counting as
# a silhouette loss. A leaf card's outermost tip is a single vertex, and losing
# it is not a readability change; a slab that halves its reach is.
LOD_SLAB_TOLERANCE = 0.15
# A prepared plant outside this height range is a unit mismatch, not a plant.
PLANT_HEIGHT_RANGE_M = (0.01, 50.0)


class PlantError(RuntimeError):
    """Preparation refused to continue; the source mesh is not usable as-is."""


USAGE = """Usage: blender --background --python Tools/Prepare-Plant.py -- <mesh> [options]
  --asset NAME       report and output stem (default: source file stem)
  --kind KIND        plant | canopy | shrub | fern | grass (default: plant)
  --target-height M  rescale the prepared plant to M metres tall
  --base-band M      height of the rooted base band used for the pivot
  --lods N           distance LOD stages to emit, 2-3 (default: 3)
  --output DIR       destination (default: ArtSource/Prepared/Plants)"""


def parse_arguments(argv):
    """Read flags after the blender '--' separator, then one source mesh path."""
    if '--' not in argv:
        raise PlantError('Pass arguments after "--", e.g. '
                         'blender --background --python Tools/Prepare-Plant.py -- <mesh> --asset <name>')
    tail = argv[argv.index('--') + 1:]
    if '--help' in tail or '-h' in tail:
        print(USAGE)
        raise SystemExit(0)
    options = {'asset': None, 'target_height': None, 'output': None,
               'kind': 'plant', 'base_band': None, 'lods': len(LOD_RATIOS)}
    named = {'--asset': 'asset', '--target-height': 'target_height',
             '--output': 'output', '--kind': 'kind', '--base-band': 'base_band',
             '--lods': 'lods'}
    sources = []
    index = 0
    while index < len(tail):
        token = tail[index]
        if token in named:
            if index + 1 >= len(tail):
                raise PlantError('Missing value for ' + token)
            value = tail[index + 1]
            index += 2
            key = named[token]
            if key in ('target_height', 'base_band', 'lods'):
                try:
                    value = float(value)
                except ValueError:
                    raise PlantError('Numeric value expected for ' + token + ': ' + str(value))
                if key == 'lods':
                    value = int(value)
                    if not 2 <= value <= len(LOD_RATIOS):
                        raise PlantError('--lods must be between 2 and ' + str(len(LOD_RATIOS)))
            options[key] = value
        elif token.startswith('--'):
            raise PlantError('Unknown option: ' + token)
        else:
            sources.append(token)
            index += 1
    if len(sources) != 1:
        raise PlantError('Exactly one source mesh path is required, got ' + str(len(sources)))
    source = Path(sources[0])
    if not source.exists():
        raise PlantError('Source mesh not found: ' + str(source))
    options['source'] = source.resolve()
    if options['asset'] is None:
        options['asset'] = source.stem
    if options['asset'] != Path(options['asset']).stem:
        raise PlantError('--asset must be a plain name, not a path: ' + str(options['asset']))
    if options['output'] is None:
        options['output'] = source.parents[2] / 'Prepared' / 'Plants'
    else:
        options['output'] = Path(options['output'])
    if options['target_height'] is not None and options['target_height'] <= 0:
        raise PlantError('--target-height must be positive')
    if options['kind'] not in ('plant', 'canopy', 'shrub', 'fern', 'grass'):
        raise PlantError('Unsupported --kind: ' + str(options['kind']))
    return options


def import_source(path):
    """Load a source mesh by extension, mirroring Prepare-Art.py's glTF import."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = path.suffix.lower()
    if suffix in ('.gltf', '.glb'):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == '.stl':
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == '.ply':
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise PlantError('Unsupported source mesh extension: ' + str(suffix))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        raise PlantError('No meshes in ' + str(path))
    return meshes


def merge_meshes(objects, label):
    """Join source variants into one mesh so the pivot and wind ramp are global.

    Source plant files often carry several pieces (trunk, fronds, seed head).
    Per-object bounds would give each piece its own false base.
    """
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = label
    merged.data.name = label
    return merged


def world_positions(mesh):
    """Vertex coordinates in the object's own space, after transform apply."""
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', coords)
    return coords.reshape((-1, 3))


def ground_contact_pivot(coords, base_band):
    """Pivot at the rooted base: band centroid in X/Y, lowest contact in Z.

    The object origin and the bounding-box centre are both wrong for plants:
    exported scans commonly sit their origin at the canopy or at the file's
    first vertex, which leaves instances hovering above the ground.
    """
    low = coords[:, 2].min()
    height = float(coords[:, 2].max() - low)
    if height <= 1e-6:
        raise PlantError('Source mesh is flat in Z; cannot locate a rooted base')
    band = min(base_band if base_band else max(0.02, height * 0.08), height)
    contact = coords[coords[:, 2] <= low + band]
    if len(contact) < 3:
        # A plant whose lowest band holds fewer than a triangle has no readable
        # root footprint; widen to 25% of height rather than guess a centre.
        contact = coords[coords[:, 2] <= low + height * 0.25]
        if len(contact) < 3:
            raise PlantError('No vertex cluster at the base to derive ground contact')
    pivot = Vector((float(contact[:, 0].mean()), float(contact[:, 1].mean()), float(low)))
    radius = float(np.hypot(contact[:, 0] - pivot.x, contact[:, 1] - pivot.y).max())
    spread = float(np.ptp(coords[:, 0]) + np.ptp(coords[:, 1]))
    if radius > spread * 0.5 + 1e-6:
        raise PlantError('Base band does not describe a single rooted cluster')
    return pivot, radius, len(contact), height


def wind_weights(coords, height, low, kind):
    """Per-vertex wind weight: 0 through the rooted base, 1 at the canopy.

    Held in a named _WIND attribute for the engine to read directly, and
    mirrored into a WindMask UV1 because the existing foliage wind material in
    Tools/BootstrapEditor.py samples TexCoord coordinate_index=1. Both carry the
    same ramp so no shader change is needed to animate these plants.
    """
    base = np.clip((coords[:, 2] - low) / max(height, 1e-6), 0.0, 1.0)
    # Quadruped-style quadratic ramp only suits a tall woody trunk; a grass
    # blade's mass is distributed along its length, so it stays linear.
    weights = base * base if kind in ('canopy', 'shrub') else base
    weights[coords[:, 2] <= low + max(0.02, height * 0.04)] = 0.0
    return weights


def write_wind_attribute(mesh, weights):
    """Store the ramp as a _WIND attribute and as a second UV set.

    The attribute is per-vertex and the UV set is per-loop, so the ramp is
    expanded through the loop-to-vertex map rather than written at equal length.
    UV0 is reserved for the source texture projection, so the mask has to be
    the layer after it; that is the layer the engine wind material samples.
    """
    if len(weights) != len(mesh.vertices):
        raise PlantError('Wind ramp covers %d of %d vertices' % (len(weights), len(mesh.vertices)))
    if WIND_ATTRIBUTE not in mesh.attributes:
        mesh.attributes.new(WIND_ATTRIBUTE, 'FLOAT', 'POINT')
    mesh.attributes[WIND_ATTRIBUTE].data.foreach_set('value', weights.astype(np.float32))
    if mesh.uv_layers.get('UVMap') is None:
        mesh.uv_layers.new(name='UVMap')
    uv = mesh.uv_layers.get(WIND_UV) or mesh.uv_layers.new(name=WIND_UV)
    corners = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', corners)
    packed = np.zeros((len(mesh.loops), 2), dtype=np.float32)
    packed[:, 0] = weights[corners]
    uv.data.foreach_set('uv', packed.ravel())


def normalize_materials(mesh, asset, cutoff):
    """Rename materials to a stable alpha-ready convention and mask their render.

    Names must survive the engine's material replacement step, which matches on
    substring, so the family prefix and the _Masked suffix are both load-bearing.
    """
    renamed = []
    for index, slot in enumerate(mesh.materials):
        source_name = slot.name if slot else ''
        slot = slot or bpy.data.materials.new(asset + '_slot' + str(index))
        family = ''.join(character for character in source_name
                         if character.isalnum())[:24] or ('Slot' + str(index))
        slot.name = 'M_Plant_%s_%s_Masked' % (asset, family)
        slot.use_nodes = True
        # DITHERED keeps the glTF alpha path but exports as alphaMode BLEND;
        # the MASK alphaMode is patched into the GLB after export instead.
        slot.surface_render_method = 'DITHERED'
        slot.use_backface_culling = False
        shader = slot.node_tree.nodes.get('Principled BSDF')
        if shader is None:
            raise PlantError('Material lacks a Principled BSDF: ' + source_name)
        if shader.inputs['Alpha'].is_linked or float(shader.inputs['Alpha'].default_value) < 1.0:
            slot['wood_alpha_cutoff'] = float(cutoff)
        renamed.append(slot.name)
    return renamed


def normalize_normals(obj):
    """Recalculate outward normals, then re-smooth above the fold angle."""
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(50.0))
    mesh = obj.data
    if len(mesh.polygons) == 0:
        raise PlantError('Source mesh has no faces after normal repair')
    degenerate = sum(1 for polygon in mesh.polygons if polygon.area <= 1e-9)
    used = np.zeros(len(mesh.vertices), dtype=bool)
    corners = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', corners)
    used[corners] = True
    loose = int((~used).sum())
    if loose:
        # Loose vertices export as unreferenced points and inflate the engine's
        # vertex buffer for nothing; drop them before anything is written.
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type='VERT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    return {'faces': len(mesh.polygons), 'degenerate_faces': degenerate,
            'loose_vertices_removed': loose,
            'smooth_angle_degrees': 50.0,
            'outward': True}


def export_glb(obj, path, asset, cutoff, materials):
    """Export one GLB, then force MASK alpha and double-sided shading.

    Blender's exporter reports DITHERED surfaces as alphaMode BLEND, which the
    engine imports as a transparent material and which sorts badly against
    other foliage. MASK plus a cutoff is what Tools/BootstrapEditor.py's
    M_Needles_CanopyV3_Masked1 material expects.
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB',
                              use_selection=True, export_attributes=True,
                              export_materials='EXPORT')
    data = path.read_bytes()
    json_size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_size])
    patched = []
    for material in doc.get('materials', []):
        material.update(alphaMode='MASK', alphaCutoff=cutoff, doubleSided=True)
        patched.append(material.get('name'))
    missing = [name for name in materials if name not in patched]
    if missing:
        raise PlantError('Exported GLB lost materials: ' + ', '.join(sorted(missing)))
    encoded = json.dumps(doc, separators=(',', ':')).encode('utf-8')
    encoded += b' ' * (-len(encoded) % 4)
    blob = data[28 + json_size:]
    blob += b'\0' * (-len(blob) % 4)
    path.write_bytes(struct.pack('<III', 0x46546c67, 2, 28 + len(encoded) + len(blob))
                     + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded
                     + struct.pack('<II', len(blob), 0x004e4942) + blob)
    return read_glb(path)


def read_glb(path):
    """Read back what was actually written, so the report reflects the file."""
    data = path.read_bytes()
    json_size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_size])
    blob = data[28 + json_size:]
    points = []
    normals = 0
    wind = []
    uvsets = -1
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            attributes = primitive['attributes']
            if 'NORMAL' in attributes:
                normals += 1
            uvsets = max(uvsets, max([-1] + [int(key.rsplit('_', 1)[1]) for key in attributes
                                              if key.startswith('TEXCOORD_')]))
            if WIND_ATTRIBUTE in attributes:
                accessor = doc['accessors'][attributes[WIND_ATTRIBUTE]]
                view = doc['bufferViews'][accessor['bufferView']]
                start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                stride = view.get('byteStride', 4)
                wind.extend(struct.unpack_from('<f', blob, start + i * stride)[0]
                            for i in range(accessor['count']))
            if 'POSITION' in attributes:
                accessor = doc['accessors'][attributes['POSITION']]
                view = doc['bufferViews'][accessor['bufferView']]
                start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                stride = view.get('byteStride', 12)
                points.extend(struct.unpack_from('<3f', blob, start + i * stride)
                              for i in range(accessor['count']))
    triangles = 0
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            indices = primitive.get('indices')
            accessor = doc['accessors'][indices] if indices is not None else doc['accessors'][primitive['attributes']['POSITION']]
            triangles += accessor['count'] // 3
    return {'vertices': len(points), 'triangles': triangles, 'wind': wind,
            'uv_channels': uvsets + 1, 'normals_primitives': normals,
            'materials': [material.get('name') for material in doc.get('materials', [])],
            'alpha_modes': [(material.get('name'), material.get('alphaMode'),
                             material.get('alphaCutoff')) for material in doc.get('materials', [])]}


def outline_by_slab(points, low, high):
    """Widest horizontal reach of a plant at each height slab, root-relative.

    A plant reads at distance as its outline, so this is the shape that has to
    survive simplification: how far the foliage spreads at each height.
    """
    span = max(high - low, 1e-9)
    heights = np.clip(((points[:, 2] - low) / span * LOD_SLABS).astype(np.int64),
                      0, LOD_SLABS - 1)
    reaches = np.zeros(LOD_SLABS, dtype=np.float64)
    for slab in range(LOD_SLABS):
        in_slab = points[heights == slab]
        if len(in_slab):
            reaches[slab] = float(np.hypot(in_slab[:, 0], in_slab[:, 1]).max())
    return reaches


def verify_lod(source_points, lod_points, source_weights, lod_weights):
    """Reject a LOD that loses the silhouette or the rooted base.

    Specification.md section 10 requires distance simplification to preserve
    recognizable silhouettes, and this plant's wind mask depends on the base
    staying put. A decimated LOD whose lowest vertices moved upward would make
    a rooted plant appear to sway at its feet, and one that loses its reach at
    mid height reads as a different, thinner plant.
    """
    if not lod_points:
        raise PlantError('LOD stage produced no geometry')
    source = np.asarray(source_points, dtype=np.float64)
    reduced = np.asarray(lod_points, dtype=np.float64)
    low = float(source[:, 2].min())
    high = float(source[:, 2].max())
    height = max(high - low, 1e-9)
    source_outline = outline_by_slab(source, low, high)
    reduced_outline = outline_by_slab(reduced, low, high)
    width = float(source_outline.max()) if source_outline.size else 0.0
    tolerance = width * LOD_SLAB_TOLERANCE
    occupied = source_outline > 1e-9
    # Compare only slabs LOD0 actually occupies; a slab that is empty in the
    # source carries no silhouette to preserve. A slab whose reach shrank by no
    # more than the tolerance counts as fully retained.
    ratios = np.clip((reduced_outline[occupied] + tolerance) /
                     np.maximum(source_outline[occupied], tolerance), 0.0, 1.0)
    silhouette = float(ratios.mean()) if len(ratios) else 0.0
    lowest = float(reduced[:, 2].min())
    base_retained = 1.0 - (lowest - low) / height
    still = sum(1 for value in lod_weights if value <= 1e-6)
    problems = []
    if base_retained < LOD_BASE_FRACTION:
        problems.append('lowest vertex rose %.0f%% of plant height' % ((1.0 - base_retained) * 100))
    if silhouette < LOD_SILHOUETTE_MINIMUM:
        problems.append('outline retained only %.0f%% of the LOD0 silhouette' % (silhouette * 100))
    return {'base_height_retained': round(base_retained, 4),
            'silhouette_retention': round(silhouette, 4),
            'still_vertices': still, 'problems': problems}


def lod_stage(obj, mesh, source_points, source_weights, asset, output, cutoff, materials, levels):
    """Emit a distance LOD ladder beside LOD0 and verify each reduction."""
    stages = []
    for level in range(1, levels):
        ratio = LOD_RATIOS[level]
        copy = obj.copy()
        copy.data = mesh.copy()
        bpy.context.collection.objects.link(copy)
        copy.name = asset + '_LOD' + str(level)
        copy.data.name = copy.name
        reduce_mesh(copy, ratio)
        path = output / (copy.name + '.glb')
        record = export_glb(copy, path, asset, cutoff, materials)
        weights = [value for value in record['wind']] or list(source_weights)
        check = verify_lod(source_points, read_points(path), source_weights, weights)
        if check['problems']:
            raise PlantError('LOD' + str(level) + ' rejected for ' + asset + ': '
                             + '; '.join(check['problems']))
        stages.append({'lod': level, 'file': copy.name + '.glb',
                       'target_ratio': ratio, 'triangles': record['triangles'],
                       'uv_channels': record['uv_channels'],
                       'wind_min': round(min(weights), 4) if weights else 0.0,
                       'wind_max': round(max(weights), 4) if weights else 0.0,
                       'wind_static_vertices': check['still_vertices'],
                       'base_height_retained': check['base_height_retained'],
                       'silhouette_retention': check['silhouette_retention']})
        bpy.data.objects.remove(copy, do_unlink=True)
    return stages


def read_points(path):
    """Positions from a written GLB, converted back to Blender's Z-up axes.

    glTF stores Y-up, so exported height lives on the file's Y axis. Reading
    these straight into a Z-up comparison silently measures the wrong axis;
    Tools/Inspect-TreeRoots.py reads min height from p[1] for the same reason.
    Undoing the swap here keeps every comparison in the source mesh's frame.
    """
    data = path.read_bytes()
    json_size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_size])
    blob = data[28 + json_size:]
    points = []
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            accessor = doc['accessors'][primitive['attributes']['POSITION']]
            view = doc['bufferViews'][accessor['bufferView']]
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            stride = view.get('byteStride', 12)
            for index in range(accessor['count']):
                x, up, depth = struct.unpack_from('<3f', blob, start + index * stride)
                points.append((x, -depth, up))
    return points


def reduce_mesh(obj, ratio):
    """Collapse geometry for distance, preserving material, UV and crease edges.

    Delimiting on NORMAL, MATERIAL, SEAM, SHARP and UV keeps thin foliage cards
    from fusing into a solid sheet, which is what produces the unstable thin
    foliage that Specification.md section 10 rules out.
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Weight the reduction to the canopy and zero the rooted base. Collapse
    # treats weight as a protection value, so the base band survives intact and
    # a distant plant keeps its ground contact instead of lifting off the soil.
    coords = world_positions(obj.data)
    low = float(coords[:, 2].min())
    guard = np.where(coords[:, 2] <= low + max(0.02, float(coords[:, 2].max() - low) * 0.08),
                     0.0, 1.0)
    group = obj.vertex_groups.new(name='WoodCanopyOnly')
    group.add(np.flatnonzero(guard > 0.5).tolist(), 1.0, 'REPLACE')
    modifier = obj.modifiers.new('WoodLOD' + str(int(ratio * 100)), 'DECIMATE')
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    modifier.delimit = {'NORMAL', 'MATERIAL', 'SEAM', 'SHARP', 'UV'}
    modifier.vertex_group = group.name
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    if len(obj.data.polygons) == 0:
        raise PlantError('Distance reduction collapsed the mesh entirely')
    # Collapse can flip faces, so rebuild outward normals on the reduced mesh
    # with the same edit-mode path the LOD0 pass uses.
    normalize_normals(obj)


def main():
    """Prepare one source plant and return its report, or refuse."""
    options = parse_arguments(sys.argv)
    source = options['source']
    output = options['output'].resolve()
    output.mkdir(parents=True, exist_ok=True)
    asset = options['asset']
    variant = asset
    reports = []

    objects = import_source(source)
    prepared = merge_meshes(objects, variant)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = prepared
    prepared.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    mesh = prepared.data

    mesh.calc_loop_triangles()
    source_triangles = len(mesh.loop_triangles)
    if source_triangles == 0:
        raise PlantError('Source mesh has no triangles')

    coords = world_positions(mesh)
    low = float(coords[:, 2].min())
    pivot, base_radius, base_vertices, height = ground_contact_pivot(coords, options['base_band'])
    raw_height = float(coords[:, 2].max() - low)
    raw_span = [float(np.ptp(coords[:, axis])) for axis in range(3)]

    scale = 1.0
    if options['target_height'] is not None and raw_height > 1e-6:
        scale = float(options['target_height']) / raw_height
        prepared.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        coords = world_positions(mesh)
        low = float(coords[:, 2].min())
        pivot, base_radius, base_vertices, height = ground_contact_pivot(coords, options['base_band'])

    weights = wind_weights(coords, height, low, options['kind'])
    write_wind_attribute(mesh, weights)

    # Apply the ground-contact pivot as geometry, then leave the object at the
    # origin so every exported node shares one grounded local frame.
    for index, vertex in enumerate(mesh.vertices):
        vertex.co -= pivot
    grounded = world_positions(mesh)
    if abs(float(grounded[:, 2].min())) > 1e-4:
        raise PlantError('Ground-contact pivot did not seat the base at Z=0')
    # The pivot is the base band's XY centroid, so the band's own centre must land
    # on the origin. Comparing the band centre (not its outermost vertex) is what
    # actually proves the instance sits on its root rather than beside it.
    seated = grounded[grounded[:, 2] <= float(grounded[:, 2].min()) + max(1e-6, height * 0.08)]
    if abs(float(seated[:, 0].mean())) > 1e-4 or abs(float(seated[:, 1].mean())) > 1e-4:
        raise PlantError('Ground-contact pivot is not inside the rooted base footprint')

    materials = normalize_materials(mesh, asset, ALPHA_CUTOFF)
    normals = normalize_normals(prepared)
    # Normal repair can delete loose vertices, so the ramp is rebuilt from the
    # mesh that is about to be exported rather than reused from before the pass.
    coords = world_positions(mesh)
    low = float(coords[:, 2].min())
    height = float(coords[:, 2].max() - low)
    weights = wind_weights(coords, height, low, options['kind'])
    write_wind_attribute(mesh, weights)
    grounded = world_positions(mesh)
    # Ground contact is re-asserted here because deleting loose vertices can
    # remove a stray point that was sitting below the real base.
    if abs(float(grounded[:, 2].min())) > 1e-4:
        raise PlantError('Loose vertex removal lifted the plant off the ground')

    # Scale is verified, not assumed: a source authored in centimetres or
    # kilometres survives this stage only as a recorded dimension, because the
    # engine places these instances in metres.
    if not PLANT_HEIGHT_RANGE_M[0] <= height <= PLANT_HEIGHT_RANGE_M[1]:
        raise PlantError('Prepared height %.3f m is outside the plausible plant '
                         'range %s m; the source is probably in the wrong units '
                         '(pass --target-height to rescale)'
                         % (height, str(PLANT_HEIGHT_RANGE_M)))

    lod0_path = output / (variant + '.glb')
    lod0 = export_glb(prepared, lod0_path, asset, ALPHA_CUTOFF, materials)
    if lod0['uv_channels'] < 2:
        raise PlantError('Exported GLB has no UV1 for the existing wind material')
    if not lod0['wind']:
        raise PlantError('Exported GLB lost the ' + WIND_ATTRIBUTE + ' wind weight attribute')
    if min(lod0['wind']) > 0.0:
        raise PlantError('No vertex is fully still; the rooted base must carry zero wind')
    if max(lod0['wind']) < 0.05:
        raise PlantError('Canopy never reaches wind weight 1; the plant would not move')
    if lod0['normals_primitives'] == 0:
        raise PlantError('Exported GLB has no vertex normals')
    if any(mode != 'MASK' for _, mode, _ in lod0['alpha_modes']):
        raise PlantError('A material did not export as alphaMode MASK')

    lods = lod_stage(prepared, mesh, grounded, weights, asset, output,
                     ALPHA_CUTOFF, materials, options['lods'])

    mesh.calc_loop_triangles()
    triangles = len(mesh.loop_triangles)
    # One shared material set with a fixed name family is what makes HISM
    # instancing viable; per-face unique materials would force a material instance
    # per instance and break the instanced draw.
    instancing_ok = (len(set(lod0['materials'])) == len(lod0['materials'])
                      and all(name.startswith('M_Plant_' + asset + '_') for name in lod0['materials']))
    if not instancing_ok:
        raise PlantError('Material names are not instancing safe for ' + asset)
    if not normals['faces'] or normals['degenerate_faces'] > normals['faces'] * 0.05:
        raise PlantError('Normals pass left %d degenerate of %d faces'
                         % (normals['degenerate_faces'], normals['faces']))
    reports.append({
        'asset': asset,
        'variant': variant,
        'source': str(source),
        'file': lod0_path.name,
        'kind': options['kind'],
        'pivot': 'rooted_base_ground_center',
        # Every measurement below is taken after any rescale, so none of them is
        # multiplied by scale_factor again; source_dimensions_m is untouched.
        'pivot_offset_m': [round(pivot.x, 6), round(pivot.y, 6), round(pivot.z, 6)],
        'base_contact_vertices': base_vertices,
        'base_footprint_radius_m': round(base_radius, 6),
        'dimensions_m': [round(float(np.ptp(grounded[:, axis])), 6) for axis in range(3)],
        'source_dimensions_m': [round(value, 6) for value in raw_span],
        'scale_factor': round(scale, 6),
        'scale_check': {'unit': 'm', 'height_m': round(height, 6),
                        'plausible_range_m': list(PLANT_HEIGHT_RANGE_M),
                        'passed': True},
        'triangles': triangles,
        'source_triangles': source_triangles,
        'materials': len(lod0['materials']),
        'material_names': lod0['materials'],
        'alpha_modes': [{'name': name, 'alphaMode': mode, 'alphaCutoff': cutoff}
                        for name, mode, cutoff in lod0['alpha_modes']],
        'alpha_cutoff': ALPHA_CUTOFF,
        'uv_channels': lod0['uv_channels'],
        'wind_attribute': WIND_ATTRIBUTE,
        'wind_uv': WIND_UV,
        'wind_min': round(min(lod0['wind']), 4),
        'wind_max': round(max(lod0['wind']), 4),
        'wind_static_vertices': sum(1 for value in lod0['wind'] if value <= 1e-6),
        'collision': 'none_by_design',
        'collision_note': 'Thin foliage is placed, not walked on. The world adapter '
                          'supplies trunk collision for woody assets; this plant '
                          'needs no hull and must import with collision disabled.',
        'instancing_compatible': instancing_ok,
        'normals': normals,
        'lods': lods,
        'prepared_by': 'Tools/Prepare-Plant.py',
    })
    (output / 'plant-inspection.json').write_text(
        json.dumps(reports, indent=2), encoding='utf-8')
    print('Prepared %s: %d triangles, %d materials, %d LOD stages, pivot at rooted '
          'base (%.1f cm radius). See %s'
          % (variant, triangles, len(lod0['materials']), len(lods),
             base_radius * 100, output / 'plant-inspection.json'))
    return 0


if __name__ == '__main__':
    # Blender exits 0 even when a --python script raises, so the refusal has to
    # exit explicitly or a caller would record a failed preparation as a pass.
    try:
        raise SystemExit(main())
    except PlantError as error:
        print('Prepare-Plant refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
