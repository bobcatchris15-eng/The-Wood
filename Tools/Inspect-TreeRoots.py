"""Inspect prepared GLB vertex/root coordinates without an engine import."""
import json, pathlib, struct

for path in sorted(pathlib.Path('ArtSource/Prepared').glob('pine*.glb')):
    data = path.read_bytes()
    size = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20+size])
    blob = data[28+size:]
    points = []
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            accessor = doc['accessors'][primitive['attributes']['POSITION']]
            view = doc['bufferViews'][accessor['bufferView']]
            offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            stride = view.get('byteStride', 12)
            points.extend(struct.unpack_from('<3f', blob, offset+i*stride) for i in range(accessor['count']))
    low = min(p[1] for p in points)
    roots = [p for p in points if p[1] < low+0.15]
    print(json.dumps(dict(asset=path.stem, min_height=low,
        root_bounds=[[min(p[i] for p in roots),max(p[i] for p in roots)] for i in range(3)],
        root_vertices=len(roots), nodes=doc.get('nodes', []))))
