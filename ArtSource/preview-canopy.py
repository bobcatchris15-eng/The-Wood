import bpy
from mathutils import Vector
from pathlib import Path
root=Path('C:/Misc/The-Wood')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(root/'ArtSource/Prepared/pine_tree_01_00.glb'))
for obj in bpy.context.scene.objects:
 if obj.type=='MESH':
  for mat in obj.data.materials:
   mat.diffuse_color=(0.08,0.18,0.08,1) if 'twig' in mat.name.lower() else (0.18,0.12,0.07,1)
bpy.ops.object.camera_add(location=(22,-32,13))
cam=bpy.context.object
cam.rotation_euler=(Vector((0,0,10))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=24
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.device='CPU';scene.world=bpy.data.worlds.new('PreviewWorld');scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(0.5,0.6,0.75,1);scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0.6; bpy.ops.object.light_add(type='SUN',rotation=(0.6,-0.3,-0.4));bpy.context.object.data.energy=3.0
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True
scene.display.shading.background_type='VIEWPORT';scene.display.shading.background_color=(0.6,0.65,0.7)
scene.render.resolution_x=512;scene.render.resolution_y=640;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'ArtSource/Prepared/canopy-preview.png')
bpy.ops.render.render(write_still=True)


