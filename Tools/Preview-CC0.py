"""Preview Poly Haven CC0 plant/rock/nature glTF models.

Run from repo root (headless):
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup -P Tools/Preview-CC0.py

For each ArtSource/PolyHaven/<id>/<id>.gltf (minus skip list): import, frame,
render 512px 3/4 view with ground plane (Workbench), print dims (m) and tri count.
Outputs: ArtSource/Previews/CC0/<id>.png and ArtSource/Previews/CC0/summary.csv
"""

import csv
import math
import os
import sys
import traceback

import bpy
from mathutils import Matrix, Vector

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "ArtSource", "PolyHaven")
OUT = os.path.join(REPO, "ArtSource", "Previews", "CC0")
RES = 512

SKIP_EXACT = {
    "metal_trash_can",
    "modular_chainlink_fence",
    "lambis_shell",
    "street_rat",
    "wooden_picnic_table",
    "standing_chalkboard_01",
}
SKIP_PREFIX = ("food_", "garden_hose_", "standing_chalkboard_")


def should_skip(asset_id):
    if asset_id in SKIP_EXACT:
        return True
    return asset_id.startswith(SKIP_PREFIX)


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                  bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def import_gltf(path):
    bpy.ops.import_scene.gltf(filepath=path)


def measure():
    """Return (min Vector, max Vector, tri count) over all imported mesh objects, world space."""
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    tris = 0
    found = False
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        found = True
        mw = obj.matrix_world
        for corner in obj.bound_box:
            w = mw @ Vector(corner)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        for poly in obj.data.polygons:
            tris += max(len(poly.vertices) - 2, 1)
    if not found:
        raise RuntimeError("no mesh objects imported")
    return lo, hi, tris


def add_ground(lo, hi):
    size = max(hi.x - lo.x, hi.y - lo.y) * 3.0 + 0.5
    cx = (lo.x + hi.x) * 0.5
    cy = (lo.y + hi.y) * 0.5
    bpy.ops.mesh.primitive_plane_add(size=size, location=(cx, cy, lo.z))
    plane = bpy.context.active_object
    mat = bpy.data.materials.new("PreviewGround")
    mat.diffuse_color = (0.33, 0.31, 0.27, 1.0)
    plane.data.materials.append(mat)
    return plane


def add_camera_and_light(lo, hi):
    center = (lo + hi) * 0.5
    radius = max((hi - lo).length * 0.5, 0.05)
    fov = math.radians(35.0)
    dist = radius / math.sin(fov * 0.5) * 1.05
    direction = Vector((1.0, -1.0, 0.6)).normalized()  # 3/4 view from front-right, above

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.angle = fov
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = center + direction * dist
    forward = (center - cam.location).normalized()
    right = forward.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(forward)
    # camera looks down its local -Z; rows are the camera X/Y/-Z axes in world space
    basis = Matrix((right, up, -forward)).transposed()
    cam.rotation_euler = basis.to_4x4().to_euler()
    bpy.context.scene.camera = cam

    sun_data = bpy.data.lights.new("PreviewSun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("PreviewSun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(55), 0.0, math.radians(35))


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "TEXTURE"
    shading.background_type = "WORLD"
    shading.show_object_outline = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.color = (0.62, 0.66, 0.70)


def render_one(asset_id, path):
    clear_scene()
    import_gltf(path)
    lo, hi, tris = measure()
    add_ground(lo, hi)
    add_camera_and_light(lo, hi)
    bpy.context.scene.render.filepath = os.path.join(OUT, asset_id + ".png")
    bpy.ops.render.render(write_still=True)
    return hi - lo, tris


def main():
    os.makedirs(OUT, exist_ok=True)
    setup_render()

    ids = sorted(
        d for d in os.listdir(SRC)
        if os.path.isdir(os.path.join(SRC, d))
    )
    rows = []
    ok = 0
    fail = 0
    skipped = 0
    for asset_id in ids:
        if should_skip(asset_id):
            skipped += 1
            continue
        gltf = os.path.join(SRC, asset_id, asset_id + ".gltf")
        if not os.path.isfile(gltf):
            fail += 1
            rows.append([asset_id, "", "", "", "", "MISSING_GLTF"])
            print("FAIL %s: MISSING_GLTF" % asset_id)
            continue
        try:
            dims, tris = render_one(asset_id, gltf)
            ok += 1
            rows.append([asset_id, "%.3f" % dims.x, "%.3f" % dims.y, "%.3f" % dims.z, tris, "OK"])
            print("OK %s dims_m=%.3fx%.3fx%.3f tris=%d" % (asset_id, dims.x, dims.y, dims.z, tris))
        except Exception as exc:  # keep going; one bad asset must not stop the batch
            fail += 1
            rows.append([asset_id, "", "", "", "", "ERR:" + type(exc).__name__])
            print("FAIL %s: %s" % (asset_id, exc))
            traceback.print_exc(file=sys.stdout)

    csv_path = os.path.join(OUT, "summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "dim_x_m", "dim_y_m", "dim_z_m", "tris", "status"])
        writer.writerows(rows)

    print("DONE ok=%d fail=%d skipped=%d csv=%s" % (ok, fail, skipped, csv_path))


main()
