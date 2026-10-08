"""Blender background normalization of downloaded CC0 model variants for Unreal."""
import bpy
import json
import sys
import struct
import numpy as np
import math
from array import array
from pathlib import Path
from mathutils import Vector
import bmesh

root = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
output = root / 'ArtSource' / 'Prepared'
output.mkdir(parents=True, exist_ok=True)
reports = []


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
            weight = max(0.0, min(1.0, (height - low - 0.08) / max(span - 0.08, 0.01)))
            values.extend((weight * weight if tree else weight, 0.0))
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

for name in ('pine_sapling_small', 'fern_02', 'grass_medium_01', 'rock_07', 'pine_tree_01', 'boulder_01', 'rock_moss_set_01', 'rock_moss_set_02'):
    # Keep the original grounded undergrowth; only rebuild newly requested sources.
    previous = output / 'inspection.json'
    old = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else []
    cached = [record for record in old if record['asset'] == name]
    if cached and (name!='pine_tree_01' or all(record.get('canopy_version')==6 for record in cached)) and all((record.get('wind_color_version') == 1 or record.get('wind_uv_version') == 2) and (output / record['file']).exists() for record in cached):
        for record in cached:
            if record.get('wind_uv_version') != 2:
                wind_uv(output / record['file'], name.startswith('pine_'))
                record['wind_uv_version'] = 2
                record.pop('wind_color_version', None)
                if name.startswith('pine_'):
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
        variant = f'{name}_{index:02d}'
        soil_faces = remove_soil(obj) if name == 'pine_tree_01' else 0
        if name == 'pine_tree_01':
            print(f'{variant}: removed {soil_faces} soil ground faces')
        canopy_triangles=needle_canopy(obj,high.z-low.z,index) if name=='pine_tree_01' else 0
        obj.name = variant
        obj.data.calc_loop_triangles()
        reports.append({'asset': name, 'variant': variant, 'file': variant + '.glb',
                        'dimensions_m': list(high - low),
                        'triangles': len(obj.data.loop_triangles),
                        'materials': len(obj.data.materials), 'pivot': 'trunk_ground_center' if name.startswith('pine_') else 'ground_center',
                        'source_triangles': source_triangles, 'wind_uv_version': 2,
                        'canopy_version': 6 if name=='pine_tree_01' else 0,
                        'soil_faces_removed': soil_faces,
                        'needle_card_triangles': canopy_triangles})
        bpy.ops.export_scene.gltf(filepath=str(output / (variant + '.glb')),
                                  export_format='GLB', use_selection=True)
        wind_uv(output / (variant + '.glb'), name.startswith('pine_'))
(output / 'inspection.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
print(f'Prepared {len(reports)} grounded variants. See ArtSource/Prepared/inspection.json')
