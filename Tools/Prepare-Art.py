"""Blender background normalization of downloaded CC0 model variants for Unreal."""
import bpy
import json
import sys
import struct
import numpy as np
import math
import random
from array import array
from pathlib import Path
from mathutils import Matrix, Vector
import bmesh

root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
output = root / 'ArtSource' / 'Prepared'
output.mkdir(parents=True, exist_ok=True)
reports = []
# Rock sources come from the Poly Haven 2k glTF set (see Fetch-Art.ps1).
ROCK_IDS = ('rock_07', 'boulder_01', 'rock_moss_set_01', 'rock_moss_set_02')
# Species groups for the non-pine canopy (Poly Haven 1k glTF, CC0). Outputs: ArtSource/Prepared/tree_<group>_<nn>.glb.
TREE_GROUPS = {
    'jacaranda_tree': 'broadleaf',
    'tree_small_02': 'broadleaf',
    'fir_tree_01': 'conifer',
    'island_tree_01': 'evergreen',
    'dead_tree_trunk': 'snag',
    'dead_tree_trunk_02': 'snag',
}
tree_counts = {}


def is_tree(name):
    """Pine and group trees share root-flare, root-mask and ground-pivot handling."""
    return name.startswith('pine_') or name in TREE_GROUPS


def needle_canopy(obj, high, index):
    """Replace needle-heavy scan geometry with atlas tufts at source branch sites."""
    mesh=obj.data
    twig=next(i for i,m in enumerate(mesh.materials) if '_twig' in m.name)
    coords=np.empty(len(mesh.vertices)*3,dtype=np.float32)
    mesh.vertices.foreach_get('co',coords)
    coords=coords.reshape((-1,3))
    uv=np.empty(len(mesh.loops)*2,dtype=np.float32)
    mesh.uv_layers[0].data.foreach_get('uv',uv)
    uv=uv.reshape((-1,2))
    ids=np.empty(len(mesh.loops),dtype=np.int32)
    mesh.loops.foreach_get('vertex_index',ids)
    slots=np.empty(len(mesh.polygons),dtype=np.int32)
    counts=np.empty(len(mesh.polygons),dtype=np.int32)
    mesh.polygons.foreach_get('material_index',slots)
    mesh.polygons.foreach_get('loop_total',counts)
    needle=(np.repeat(slots==twig,counts) & (uv[:,0]<0.23) & (uv[:,1]>0.54))
    candidates=np.unique(ids[needle])
    candidates=candidates[coords[candidates,2]>high*0.29]
    if len(candidates)<100:
        raise RuntimeError('No needle atlas sites in source canopy')
    rng=np.random.default_rng(8817+index)
    chosen=rng.choice(candidates,size=min(4200,len(candidates)),replace=False)
    sites=coords[chosen].copy()
    del coords,uv,ids,slots,counts,needle,candidates
    # Preserve bark and trunk at their original scan resolution. Whole-tree
    # collapse had discarded needle cards and reduced the roots to spikes.
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='DESELECT')
    obj.active_material_index=twig
    bpy.ops.object.material_slot_select()
    bpy.ops.mesh.delete(type='FACE')
    bpy.ops.object.mode_set(mode='OBJECT')
    mat=bpy.data.materials.get('PineNeedleCards')
    if mat is None:
        mat=bpy.data.materials.new('PineNeedleCards')
        mat.use_nodes=True
        mat.use_backface_culling=False
        mat.surface_render_method='DITHERED'
        shader=mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Roughness'].default_value=0.82
        folder=root/'ArtSource/PolyHaven/pine_tree_01/textures'
        color=mat.node_tree.nodes.new('ShaderNodeTexImage')
        color.image=bpy.data.images.load(str(folder/'pine_tree_01_twig_diff_1k.jpg'),check_existing=True)
        alpha=mat.node_tree.nodes.new('ShaderNodeTexImage')
        alpha.image=bpy.data.images.load(str(folder/'pine_tree_01_twig_alpha_1k.png'),check_existing=True)
        alpha.image.colorspace_settings.name='Non-Color'
        mat.node_tree.links.new(color.outputs['Color'],shader.inputs['Base Color'])
        mat.node_tree.links.new(alpha.outputs['Color'],shader.inputs['Alpha'])
    verts=[];faces=[]
    for point in sites:
        # Source sampling preserves irregular branch layers and crown taper.
        direction=Vector((float(point[0]),float(point[1]),0.0))
        if direction.length<0.1:
            angle=float(rng.uniform(0,math.tau));direction=Vector((math.cos(angle),math.sin(angle),0))
        direction.normalize()
        direction.z=float(rng.uniform(-0.08,0.35));direction.normalize()
        side=Vector((-direction.y,direction.x,0)).normalized()
        length=float(rng.uniform(0.48,0.88));width=length*0.48
        center=Vector(tuple(float(v) for v in point))
        for cross in (side,direction.cross(side).normalized()):
            start=len(verts)
            for u,v in ((-1,-1),(1,-1),(1,1),(-1,1)):
                verts.append(tuple(center+cross*(u*width/2)+direction*(v*length/2)))
            faces.append((start,start+1,start+2,start+3))
    cards_mesh=bpy.data.meshes.new('SourceNeedleTufts')
    cards_mesh.from_pydata(verts,[],faces)
    cards_mesh.materials.append(mat)
    cards_uv=cards_mesh.uv_layers.new(name='UVMap')
    atlas=((0.005,0.555),(0.225,0.555),(0.225,0.995),(0.005,0.995))
    for polygon in cards_mesh.polygons:
        for corner,loop in enumerate(polygon.loop_indices):
            cards_uv.data[loop].uv=atlas[corner]
    cards=bpy.data.objects.new('SourceNeedleTufts',cards_mesh)
    bpy.context.collection.objects.link(cards)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True);cards.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.join()
    return len(sites)*4


def remove_soil(obj):
    """Delete scanned-soil ground plates around a pine trunk base. Returns face count removed."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    base = min(v.co.z for v in bm.verts)
    trunk = [v.co for v in bm.verts if base + 0.5 <= v.co.z <= base + 1.0]
    if trunk:
        axis_x = sum(p.x for p in trunk) / len(trunk)
        axis_y = sum(p.y for p in trunk) / len(trunk)
    else:
        axis_x = axis_y = 0.0
    # Flare radius: 75th percentile of radial distance in the 0.15-0.4 m band, local frame.
    band = sorted(math.hypot(v.co.x - axis_x, v.co.y - axis_y) for v in bm.verts if base + 0.15 <= v.co.z <= base + 0.4)
    flare_r = band[int(len(band) * 0.75)] if band else 0.25
    limit = flare_r * 1.15
    names = [m.name.lower() if m else '' for m in mesh.materials]
    doomed = []
    for face in bm.faces:
        material = names[face.material_index] if face.material_index < len(names) else ''
        if any(term in material for term in ('soil', 'ground', 'dirt')):
            doomed.append(face)
            continue
        center = face.calc_center_median()
        if center.z - base <= 0.4 and math.hypot(center.x - axis_x, center.y - axis_y) > limit:
            doomed.append(face)
    print(f'flare_r={flare_r:.3f} limit={limit:.3f} axis=({axis_x:.3f},{axis_y:.3f})')
    count = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return count


def wind_uv(path, tree):
    """Write a dedicated UV1 root mask. Vertex colors would tint glTF shading."""
    data = path.read_bytes()
    json_size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + json_size])
    for material in doc.get('materials',[]):
        if 'PineNeedleCards' in material.get('name',''):
            material.update(alphaMode='MASK',alphaCutoff=0.35,doubleSided=True)
    binary = bytearray(data[28 + json_size:])
    positions = []
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            accessor = doc['accessors'][primitive['attributes']['POSITION']]
            view = doc['bufferViews'][accessor['bufferView']]
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            stride = view.get('byteStride', 12)
            heights = [struct.unpack_from('<f', binary, start + i * stride + 4)[0] for i in range(accessor['count'])]
            positions.append((primitive, heights))
    low = min(min(values) for _, values in positions)
    span = max(max(values) for _, values in positions) - low
    if tree:
        roots = []
        for primitive, heights in positions:
            accessor = doc['accessors'][primitive['attributes']['POSITION']]
            view = doc['bufferViews'][accessor['bufferView']]
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            stride = view.get('byteStride', 12)
            roots.extend(struct.unpack_from('<3f', binary, start + i * stride) for i, height in enumerate(heights) if height < low + 0.15)
        shift = ((min(p[0] for p in roots) + max(p[0] for p in roots)) / 2, low,
                 (min(p[2] for p in roots) + max(p[2] for p in roots)) / 2)
        for primitive, heights in positions:
            accessor = doc['accessors'][primitive['attributes']['POSITION']]
            view = doc['bufferViews'][accessor['bufferView']]
            start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            stride = view.get('byteStride', 12)
            for index in range(accessor['count']):
                address = start + index * stride
                point = struct.unpack_from('<3f', binary, address)
                struct.pack_into('<3f', binary, address, *(point[i] - shift[i] for i in range(3)))
            for key in ('min', 'max'):
                if key in accessor:
                    accessor[key] = [accessor[key][i] - shift[i] for i in range(3)]
    for primitive, heights in positions:
        attributes = primitive['attributes']
        for key in list(attributes):
            if key.startswith('COLOR_'):
                del attributes[key]
        values = array('f')
        for height in heights:
            if tree:
                # Smoothstep root blend: 0 at lowest vertex, 1 at 0.6 m above it (post soil removal).
                t = max(0.0, min(1.0, (height - low) / 0.6))
                weight = t * t * (3.0 - 2.0 * t)
            else:
                weight = max(0.0, min(1.0, (height - low - 0.08) / max(span - 0.08, 0.01)))
            values.extend((weight, 0.0))
        while len(binary) % 4:
            binary.append(0)
        view_index = len(doc['bufferViews'])
        raw = values.tobytes()
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(raw), 'target': 34962})
        binary.extend(raw)
        attributes['TEXCOORD_1'] = len(doc['accessors'])
        doc['accessors'].append({'bufferView': view_index, 'componentType': 5126, 'count': len(heights), 'type': 'VEC2'})
    doc['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(doc, separators=(',', ':')).encode('utf-8')
    encoded += b' ' * (-len(encoded) % 4)
    binary.extend(b'\0' * (-len(binary) % 4))
    path.write_bytes(struct.pack('<III', 0x46546c67, 2, 28 + len(encoded) + len(binary)) + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded + struct.pack('<II', len(binary), 0x004e4942) + binary)

for name in ('pine_sapling_small', 'fern_02', 'grass_medium_01', 'grass_bermuda_01', 'grass_medium_02', 'rock_07', 'pine_tree_01', 'boulder_01', 'rock_moss_set_01', 'rock_moss_set_02', 'jacaranda_tree', 'tree_small_02', 'fir_tree_01', 'island_tree_01', 'dead_tree_trunk', 'dead_tree_trunk_02'):
    # Keep the original grounded undergrowth; only rebuild newly requested sources.
    previous = output / 'inspection.json'
    old = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else []
    cached = [record for record in old if record['asset'] == name]
    rock_2k = name in ROCK_IDS
    if cached and (name!='pine_tree_01' or all(record.get('canopy_version')==7 for record in cached)) and (not rock_2k or all(record.get('texture_res')=='2k' for record in cached)) and all((record.get('wind_color_version') == 1 or record.get('wind_uv_version') == 2) and (output / record['file']).exists() for record in cached):
        for record in cached:
            if record.get('wind_uv_version') != 2:
                wind_uv(output / record['file'], is_tree(name))
                record['wind_uv_version'] = 2
                record.pop('wind_color_version', None)
                if is_tree(name):
                    record['pivot'] = 'trunk_ground_center'
        reports.extend(cached)
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(root / 'ArtSource' / 'PolyHaven' / name / (name + '.gltf')))
    meshes = sorted((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: obj.name)
    if not meshes:
        raise RuntimeError('No meshes in ' + name)
    # Source scenes often contain multiple variants side by side. Export them separately.
    for index, obj in enumerate(meshes):
        points = [obj.matrix_world @ Vector(point) for point in obj.bound_box]
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        pivot = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        bpy.ops.object.select_all(action='DESELECT')
        matrix = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = matrix
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for vertex in obj.data.vertices:
            vertex.co -= pivot
        if name in ('boulder_01', 'rock_moss_set_01', 'rock_moss_set_02'):
            # Instance scale directly denotes horizontal boulder span in metres.
            factor = 1.0 / max(high.x - low.x, high.y - low.y)
            for vertex in obj.data.vertices:
                vertex.co *= factor
            high = low + (high - low) * factor
        # A bounded canopy mesh fits the integrated-GPU review machine. Preserve
        # source texture/material assignments and silhouette with collapse reduction.
        obj.data.calc_loop_triangles()
        source_triangles = len(obj.data.loop_triangles)
        if name in TREE_GROUPS:
            group = TREE_GROUPS[name]
            serial = tree_counts.get(group, 0)
            tree_counts[group] = serial + 1
            variant = f'tree_{group}_{serial:02d}'
        else:
            variant = f'{name}_{index:02d}'
        soil_faces = remove_soil(obj) if is_tree(name) else 0
        if is_tree(name):
            print(f'{variant}: removed {soil_faces} soil ground faces')
        canopy_triangles=needle_canopy(obj,high.z-low.z,index) if name=='pine_tree_01' else 0
        obj.name = variant
        obj.data.calc_loop_triangles()
        dims = list(high - low)
        tree_fields = {'height_m': round(dims[2], 3), 'crown_width_m': round(max(dims[0], dims[1]), 3)} if is_tree(name) else {}
        reports.append({'asset': name, 'variant': variant, 'file': variant + '.glb',
                        'dimensions_m': dims,
                        'triangles': len(obj.data.loop_triangles),
                        'materials': len(obj.data.materials), 'pivot': 'trunk_ground_center' if is_tree(name) else 'ground_center',
                        'source_triangles': source_triangles, 'wind_uv_version': 2,
                        'canopy_version': 7 if name=='pine_tree_01' else 0,
                        'soil_faces_removed': soil_faces,
                        'texture_res': '2k' if name in ROCK_IDS else '1k',
                        'needle_card_triangles': canopy_triangles, **tree_fields})
        bpy.ops.export_scene.gltf(filepath=str(output / (variant + '.glb')),
                                  export_format='GLB', use_selection=True)
        wind_uv(output / (variant + '.glb'), is_tree(name))
def build_prairie_clumps():
    """Assemble three seeded prairie clumps from prepared grass variants, each >=0.6m across, 0.5-0.9m tall."""
    pool = [r for r in reports if r['asset'] in ('grass_medium_01', 'grass_medium_02') and 60 <= r['triangles'] <= 2500]
    if len(pool) < 7:
        raise RuntimeError('Prairie clump pool too small: %d' % len(pool))
    for clump in range(3):
        seed = 4100 + clump
        rng = random.Random(seed)
        picks = rng.sample(pool, rng.randint(5, 7))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        parts = []
        for index, record in enumerate(picks):
            before = set(bpy.context.scene.objects.keys())
            bpy.ops.import_scene.gltf(filepath=str(output / record['file']))
            new = [obj for obj in bpy.context.scene.objects if obj.name not in before and obj.type == 'MESH']
            if not new:
                raise RuntimeError('Prairie import produced no mesh: ' + record['variant'])
            for obj in new:
                angle = rng.uniform(0.0, 2.0 * math.pi)
                radius = 0.35 * math.sqrt(rng.random())
                offset = rng.uniform(0.0, 2.0 * math.pi)
                obj.rotation_euler = (0.0, 0.0, angle)
                obj.location = (radius * math.cos(offset), radius * math.sin(offset), 0.0)
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                parts.append(obj)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        # Ground-contact pivot: lowest vertex at z=0 and XY centred on the footprint.
        points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        height = high.z - low.z
        target = rng.uniform(0.5, 0.9)
        factor = target / height
        obj.location = (0.0, 0.0, 0.0)
        for vertex in obj.data.vertices:
            vertex.co -= Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        obj.location = (0.0, 0.0, 0.0)
        obj.scale = (factor, factor, factor)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        footprint = max(high.x - low.x, high.y - low.y)
        if footprint < 0.6:
            raise RuntimeError('Prairie clump %d footprint %.2fm below 0.6m' % (clump, footprint))
        variant = f'prairie_clump_{clump:02d}'
        obj.name = variant
        obj.data.calc_loop_triangles()
        path = output / (variant + '.glb')
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True)
        wind_uv(path, False)
        reports.append({'asset': 'prairie_clump', 'variant': variant, 'file': variant + '.glb',
                        'dimensions_m': [high.x - low.x, high.y - low.y, high.z - low.z],
                        'triangles': len(obj.data.loop_triangles),
                        'materials': len(obj.data.materials), 'pivot': 'ground_center',
                        'seed': seed, 'sources': [r['variant'] for r in picks],
                        'wind_uv_version': 2})


# Gameplay props for the entrance zone (ids 0-3). Source orientation is kept (+Y forward as imported).
# Each prop is scaled uniformly so the named axis matches real-world metres, then origin set to base centre.
PROP_SOURCES = {
    'prop_00': ('standing_chalkboard_01', 'height', 2.0),       # id 0 signboard
    'prop_01': ('wooden_picnic_table', 'none', None),           # id 1 picnic table, already real-world scale
    'prop_02': ('metal_trash_can', 'height', 1.0),              # id 2 bin, one clean can (rust variant dropped)
    'prop_03': ('modular_chainlink_fence', 'horizontal', 4.0),  # id 3 fence segment, longest horizontal span
}
# Source objects kept per prop. metal_trash_can holds two cans (clean at x=+0.5, rust at x=-0.5); keep the clean one.
PROP_KEEP = {
    'metal_trash_can': lambda name: 'rust' not in name,
}


def build_props():
    """Import each prop source, join to one mesh, scale to target metres and export base-centred GLB."""
    for prop, (source, axis, target) in PROP_SOURCES.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(root / 'ArtSource' / 'PolyHaven' / source / (source + '.gltf')))
        keep = PROP_KEEP.get(source, lambda name: True)
        meshes = sorted((obj for obj in bpy.context.scene.objects if obj.type == 'MESH'), key=lambda obj: obj.name)
        for obj in meshes:
            if not keep(obj.name):
                bpy.data.objects.remove(obj, do_unlink=True)
        meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not meshes:
            raise RuntimeError('No meshes in ' + source)
        for obj in meshes:
            matrix = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_world = matrix
        bpy.ops.object.select_all(action='DESELECT')
        for obj in meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        if len(meshes) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        low = Vector(tuple(min(v.co[i] for v in obj.data.vertices) for i in range(3)))
        high = Vector(tuple(max(v.co[i] for v in obj.data.vertices) for i in range(3)))
        measured = (high.z - low.z) if axis == 'height' else max(high.x - low.x, high.y - low.y)
        if axis == 'none':
            measured = 1.0
        factor = 1.0 if axis == 'none' else target / measured
        for vertex in obj.data.vertices:
            vertex.co *= factor
        low = Vector(tuple(min(v.co[i] for v in obj.data.vertices) for i in range(3)))
        high = Vector(tuple(max(v.co[i] for v in obj.data.vertices) for i in range(3)))
        pivot = Vector(((low.x + high.x) / 2, (low.y + high.y) / 2, low.z))
        for vertex in obj.data.vertices:
            vertex.co -= pivot
        obj.location = (0.0, 0.0, 0.0)
        obj.name = prop
        obj.data.calc_loop_triangles()
        dims = [high.x - low.x, high.y - low.y, high.z - low.z]
        path = output / (prop + '.glb')
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True)
        reports.append({'asset': source, 'variant': prop, 'file': prop + '.glb',
                        'dimensions_m': dims,
                        'triangles': len(obj.data.loop_triangles),
                        'materials': len(obj.data.materials), 'pivot': 'base_center',
                        'source_meshes': len(meshes), 'scale_factor': factor,
                        'target_axis': axis, 'target_m': target, 'licence': 'CC0-1.0'})


# Dry-stone and masonry kit for the WoodDiscovery.cpp mesh names. Unit = metres at grammar scale 1.0.
# Length runs along +Y (grammar yaw is the wall tangent / span direction); origin at base centre, Z up.
STONE_KIT_SEED = 7300
TAU = 2.0 * math.pi


def make_stone_material(name, source_id):
    """CC0 Poly Haven 2k set (diffuse, GL normal, roughness) as a Principled material."""
    folder = root / 'ArtSource' / 'PolyHaven' / source_id
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    shader = tree.nodes.get('Principled BSDF')
    base = tree.nodes.new('ShaderNodeTexImage')
    base.image = bpy.data.images.load(str(folder / (source_id + '-Diffuse.jpg')), check_existing=True)
    tree.links.new(base.outputs['Color'], shader.inputs['Base Color'])
    rough = tree.nodes.new('ShaderNodeTexImage')
    rough.image = bpy.data.images.load(str(folder / (source_id + '-Rough.jpg')), check_existing=True)
    rough.image.colorspace_settings.name = 'Non-Color'
    tree.links.new(rough.outputs['Color'], shader.inputs['Roughness'])
    normal_tex = tree.nodes.new('ShaderNodeTexImage')
    normal_tex.image = bpy.data.images.load(str(folder / (source_id + '-nor_gl.jpg')), check_existing=True)
    normal_tex.image.colorspace_settings.name = 'Non-Color'
    normal_map = tree.nodes.new('ShaderNodeNormalMap')
    tree.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
    tree.links.new(normal_map.outputs['Normal'], shader.inputs['Normal'])
    return mat


def kit_block(bm, rng, center, size, yaw=0.0, bevel=0.03, jitter=0.012, taper=None, lean=0.0):
    """One jittered, yawed, bevelled block. size = (thickness X, length Y, height Z).
    lean shears the top of the stone by up to +/-lean metres per metre of height, so no two stones are true boxes."""
    cube = bmesh.ops.create_cube(bm, size=1.0)['verts']
    sx, sy, sz = size
    c, s = math.cos(yaw), math.sin(yaw)
    lean_x = rng.uniform(-lean, lean) if lean else 0.0
    lean_y = rng.uniform(-lean, lean) if lean else 0.0
    for v in cube:
        x = v.co.x * sx + rng.uniform(-jitter, jitter)
        y = v.co.y * sy + rng.uniform(-jitter, jitter)
        z = v.co.z * sz + rng.uniform(-jitter, jitter)
        if taper and z > 0.0:
            x *= taper[0]
            y *= taper[1]
        x += lean_x * z
        y += lean_y * z
        v.co = Vector((x * c - y * s + center[0], x * s + y * c + center[1], z + center[2]))
    edges = list({e for v in cube for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=2, affect='EDGES', clamp_overlap=True)


def kit_wall(bm, rng):
    # Two courses of four blocks, joints offset by independent split weights.
    # Top course is irregular: at most one stone missing, others stepped down (broken top).
    length, thick, course = 2.0, 0.6, 0.5
    for row in range(2):
        weights = [rng.uniform(0.7, 1.3) for _ in range(4)]
        total = sum(weights)
        y = -length / 2.0
        missing = False
        for index, w in enumerate(weights):
            run = length * w / total
            base = row * course + 0.01
            height = course - 0.02
            if row == 1:
                roll = rng.random()
                if roll < 0.2 and not missing and 0 < index < 3:
                    missing = True
                    y += run
                    continue
                if roll < 0.5:
                    height *= rng.uniform(0.45, 0.75)
            kit_block(bm, rng, (rng.uniform(-0.015, 0.015), y + run / 2.0, base + height / 2.0),
                      (thick, run - 0.02, height), yaw=rng.uniform(-0.03, 0.03), lean=0.035)
            y += run


def kit_rubble(bm, rng):
    # 6-12 fallen blocks scattered within 0.9 m of centre, lying flat.
    for _ in range(rng.randint(6, 12)):
        radius = 0.9 * math.sqrt(rng.random())
        angle = rng.uniform(0.0, TAU)
        size = (rng.uniform(0.3, 0.55), rng.uniform(0.2, 0.35), rng.uniform(0.14, 0.22))
        kit_block(bm, rng, (radius * math.cos(angle), radius * math.sin(angle), size[2] / 2.0), size,
                  yaw=rng.uniform(0.0, TAU), bevel=0.02)


def kit_pier(bm, rng):
    # Four courses; top course stepped down on one side, so the cap is not level.
    for row in range(4):
        height = 0.38
        if row == 3:
            height *= rng.uniform(0.55, 0.8)
        kit_block(bm, rng, (0.0, 0.0, row * 0.4 + 0.01 + height / 2.0), (0.8, 0.8, height),
                  yaw=rng.uniform(-0.05, 0.05), bevel=0.03, lean=0.03)


def kit_pier_ruined(bm, rng):
    # Top course gone; one block displaced to the ground beside the base.
    for row in range(2):
        kit_block(bm, rng, (0.0, 0.0, row * 0.4 + 0.2), (0.8, 0.8, 0.38), yaw=rng.uniform(-0.05, 0.05), bevel=0.03)
    kit_block(bm, rng, (0.75, 0.3, 0.13), (0.45, 0.32, 0.26), yaw=0.6, bevel=0.025)


def kit_foundation(bm, rng):
    # One course, two blocks totalling the 1.6 m grammar step.
    kit_block(bm, rng, (0.0, -0.35, 0.225), (0.6, 0.88, 0.45), yaw=rng.uniform(-0.02, 0.02), lean=0.02)
    kit_block(bm, rng, (0.0, 0.45, 0.225), (0.6, 0.68, 0.45), yaw=rng.uniform(-0.02, 0.02), lean=0.02)


def kit_debris(bm, rng):
    for _ in range(rng.randint(5, 8)):
        radius = 0.35 * math.sqrt(rng.random())
        angle = rng.uniform(0.0, TAU)
        size = (rng.uniform(0.12, 0.25), rng.uniform(0.12, 0.25), rng.uniform(0.06, 0.14))
        kit_block(bm, rng, (radius * math.cos(angle), radius * math.sin(angle), size[2] / 2.0), size,
                  yaw=rng.uniform(0.0, TAU), bevel=0.012, jitter=0.01)


def kit_abutment(bm, rng):
    # Three courses of two blocks, capped with an overhanging slab.
    for row in range(3):
        for side in (-1.0, 1.0):
            kit_block(bm, rng, (side * 0.405, 0.0, row * 0.4 + 0.2), (0.79, 1.0, 0.38),
                      yaw=rng.uniform(-0.02, 0.02))
    kit_block(bm, rng, (0.0, 0.0, 1.26), (1.7, 1.1, 0.12), yaw=rng.uniform(-0.01, 0.01), bevel=0.02)


def kit_stepping(bm, rng):
    kit_block(bm, rng, (0.0, 0.0, 0.14), (0.6, 0.7, 0.28), yaw=rng.uniform(-0.2, 0.2), bevel=0.04, jitter=0.02)


def kit_monolith(bm, rng):
    kit_block(bm, rng, (0.0, 0.0, 0.5), (0.7, 0.45, 1.0), bevel=0.02, jitter=0.02, taper=(0.82, 0.9))


def kit_talus(bm, rng):
    # Irregular boulder: icosphere scaled 1.0 x 0.85 x 0.6 m, per-vertex radial noise, flat base.
    verts = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.5)['verts']
    for v in verts:
        k = rng.uniform(0.92, 1.08)
        z = max(v.co.z * 0.6 * k, -0.22)
        v.co = Vector((v.co.x * 1.0 * k, v.co.y * 0.85 * k, z))


def kit_finalize(bm):
    """Base centre to origin, Z up, box-projected UV at 1 m per tile (dominant-normal axis)."""
    bm.normal_update()
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    minz = min(v.co.z for v in bm.verts)
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    for v in bm.verts:
        v.co = v.co - Vector((cx, cy, minz))
    uv_layer = bm.loops.layers.uv.new('UVMap')
    for face in bm.faces:
        n = face.normal
        axis = max(range(3), key=lambda i: abs(n[i]))
        for loop in face.loops:
            p = loop.vert.co
            loop[uv_layer].uv = ((p.y, p.z), (p.x, p.z), (p.x, p.y))[axis]


# Yaw convention (WoodDiscovery.cpp wallYaw = atan2(dy, dx) in degrees; WoodGrounding.cpp FRotator(pitch, yaw, roll),
# UE yaw 0 = +X). A kit mesh placed at yaw therefore has its local +X along (cos yaw, sin yaw).
# Wall-run pieces build their length along Y while kit_block works in (thick X, length Y, height Z), so they are
# rotated 90 deg CCW about Z (x, y) -> (-y, x) before finalize, putting the length on local +X.
# Pieces not listed here are square or radially scattered, so their footprint orientation does not matter.
# SM_BridgeAbutment is NOT rotated: its length is already on X and its yaw is the span direction (see KIT_SPECS).
LENGTH_Y_TO_X = ('SM_DryStone_Wall', 'SM_FoundationCourse')
DAMP_MESHES = ('SM_DryStone_Wall', 'SM_StonePier', 'SM_StonePier_Ruined', 'SM_FoundationCourse', 'SM_BridgeAbutment')
DAMP_TINT = (0.58, 0.56, 0.52)


def add_damp_band(bm):
    """Per-loop vertex colour 'DampBand': darker damp tint at or below 0.25 m, ramping to white by 0.35 m.
    Exported as COLOR_0. The Unreal masonry material must multiply by it to show; until then it is inert."""
    layer = bm.loops.layers.color.new('DampBand')
    for face in bm.faces:
        for loop in face.loops:
            t = max(0.0, min(1.0, (loop.vert.co.z - 0.25) / 0.1))
            loop[layer] = (DAMP_TINT[0] * (1.0 - t) + t, DAMP_TINT[1] * (1.0 - t) + t, DAMP_TINT[2] * (1.0 - t) + t, 1.0)


def build_fern_patch():
    """Three fern_02 variants merged into one patch, placed on a ~1 m footprint."""
    rng = random.Random(STONE_KIT_SEED + 7)
    offsets = ((0.0, 0.0), (0.28, -0.18), (-0.24, 0.2))
    parts = []
    for index, variant in enumerate(('fern_02_00', 'fern_02_01', 'fern_02_02')):
        before = set(bpy.context.scene.objects.keys())
        bpy.ops.import_scene.gltf(filepath=str(output / (variant + '.glb')))
        new = [obj for obj in bpy.context.scene.objects if obj.name not in before]
        for obj in new:
            if obj.type != 'MESH':
                continue
            matrix = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_world = matrix
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            obj.data.transform(Matrix.Rotation(rng.uniform(0.0, TAU), 4, 'Z') @ Matrix.Translation((offsets[index][0], offsets[index][1], 0.0)))
            parts.append(obj)
        for obj in new:
            if obj.type != 'MESH' and obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    verts = [v.co for v in obj.data.vertices]
    cx = (min(v.x for v in verts) + max(v.x for v in verts)) / 2.0
    cy = (min(v.y for v in verts) + max(v.y for v in verts)) / 2.0
    minz = min(v.z for v in verts)
    obj.data.transform(Matrix.Translation((-cx, -cy, -minz)))
    return obj, ['fern_02_00', 'fern_02_01', 'fern_02_02']


# (mesh name, builder, material key, nominal size at scale 1.0, grammar placement and scale)
KIT_SPECS = (
    ('SM_DryStone_Wall', kit_wall, 'masonry', '2.0 L x 0.6 T x 1.0 H (X, Y, Z); 2 courses of 0.5; L on +X = yaw axis',
     'WoodDiscovery shelter ring (generateDryStoneShelter): butt-jointed arc-length runs, scale 0.55-1.0 (breach taper); top course irregular; sunk 0.10-0.25 m'),
    ('SM_DryStone_Rubble', kit_rubble, 'masonry', '2.0 x 2.0 footprint, 0.35 H; 6-12 blocks within 0.9 m radius',
     'shelter ruined wall base 0.77-0.98 (0.85x seg); shelter_rubble scale 0.45-0.75'),
    ('SM_StonePier', kit_pier, 'masonry', '0.8 x 0.8 x 1.6 (4 courses of 0.4)',
     'cottage corner pier base 1.2, mid 1.05, top 0.9'),
    ('SM_StonePier_Ruined', kit_pier_ruined, 'masonry', '0.8 x 0.8 x 0.8 + displaced block to 0.26 H at 0.75 m',
     'cottage corner pier ruined scale 0.95'),
    ('SM_FoundationCourse', kit_foundation, 'masonry', '1.6 L x 0.6 T x 0.45 H (X, Y, Z; two blocks 0.88 + 0.68 L); L on +X = yaw axis',
     'cottage foundation course stepped every wallLen/stepCount (~1.6 m); scale 0.9-1.1; upper wall 0.85x'),
    ('SM_MasonryDebris', kit_debris, 'masonry', '0.7 x 0.7 x 0.2 pile (5-8 chunks 0.12-0.25 m)',
     'cottage internal rubble scale 0.5-0.9'),
    ('SM_FernPatch', None, 'fern', '~1.2 x 1.1 x 0.45 (fern_02 00+01+02 merged)',
     'cottage internal fern scale 0.7-1.1'),
    ('SM_BridgeAbutment', kit_abutment, 'masonry', '1.7 L x 1.1 T x 1.32 H incl. cap (Y across span, X along bank)',
     'stream footbridge abutments scale 1.35 (base) and 1.1 (inward); yaw = span normal'),
    ('SM_RiverSteppingStone', kit_stepping, 'masonry', '0.6 x 0.7 x 0.28 slab',
     'footbridge stepping stones scale 0.75-0.95'),
    ('SM_GraniteMonolith', kit_monolith, 'rock', '0.7 x 0.45 x 1.0 tapered top (1.0 H = 1 m unit)',
     'ridge tor monolith scale 2.4-3.8 (2.4-3.8 m tall)'),
    ('SM_TalusRock', kit_talus, 'rock', '1.0 x 0.85 x 0.6 boulder, flat base',
     'ridge tor talus scale 2*exp(-r/7.5)*(0.85-1.15): ~0.96 at r 5.5, 0.52 at r 9.5, 0.31 at r 14'),
)


def build_stone_kit():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials = {
        'masonry': make_stone_material('M_StoneKit_Masonry', 'stacked_stone_wall'),
        'rock': make_stone_material('M_StoneKit_Rock', 'rustic_stone_wall'),
    }
    for index, (name, build, material_key, nominal, grammar) in enumerate(KIT_SPECS):
        seed = STONE_KIT_SEED + index
        rng = random.Random(seed)
        file_name = 'kit_' + name.lower() + '.glb'
        if build is None:
            obj, sources = build_fern_patch()
        else:
            bm = bmesh.new()
            build(bm, rng)
            if name in LENGTH_Y_TO_X:
                for v in bm.verts:
                    v.co = Vector((-v.co.y, v.co.x, v.co.z))
            kit_finalize(bm)
            if name in DAMP_MESHES:
                add_damp_band(bm)
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            bm.free()
            mesh.materials.append(materials[material_key])
            obj = bpy.data.objects.new(name, mesh)
            bpy.context.collection.objects.link(obj)
            sources = ['stacked_stone_wall' if material_key == 'masonry' else 'rustic_stone_wall', 'procedural']
        obj.name = name
        mesh = obj.data
        mesh.calc_loop_triangles()
        triangles = len(mesh.loop_triangles)
        verts = [v.co for v in mesh.vertices]
        dims = [max(p[i] for p in verts) - min(p[i] for p in verts) for i in range(3)]
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(filepath=str(output / file_name), export_format='GLB', use_selection=True)
        bpy.data.objects.remove(obj, do_unlink=True)
        reports.append({'asset': 'stone_kit', 'variant': name, 'file': file_name,
                        'dimensions_m': dims, 'triangles': triangles, 'materials': 1,
                        'pivot': 'base_center', 'licence': 'CC0-1.0',
                        'nominal_m': nominal, 'grammar': grammar, 'sources': sources,
                        'seed': seed, 'uv': 'box projection, 1.0 m per tile'})


build_prairie_clumps()
build_props()
build_stone_kit()
(output / 'inspection.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
print(f'Prepared {len(reports)} grounded variants. See ArtSource/Prepared/inspection.json')
