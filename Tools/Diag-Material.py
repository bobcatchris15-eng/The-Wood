"""Diagnostic: dump parent chain, parameters and textures of the materials named in DIAG_ASSETS (comma list env) or defaults."""
import unreal, os
MEL = unreal.MaterialEditingLibrary
names = os.environ.get('DIAG_ASSETS', '/Game/Wood/FoliageWind/Bark_CanopyV4_Wind16_2S_Tint,/Game/Art/Flora/oak_broadleaf/oak_broadleaf_v01/Materials/Bark,/Game/Art/Flora/birch_pale/birch_pale_v01/Materials/Bark').split(',')
def dump(a, depth=0):
    pad = '  ' * depth
    if a is None: unreal.log('DIAG %sNone' % pad); return
    unreal.log('DIAG %s%s (%s)' % (pad, a.get_path_name(), a.get_class().get_name()))
    if isinstance(a, unreal.MaterialInstanceConstant):
        for p in a.get_editor_property('texture_parameter_values'):
            t = p.get_editor_property('parameter_value')
            info = p.get_editor_property('parameter_info').get_editor_property('name')
            unreal.log('DIAG %s  tex %s = %s srgb=%s comp=%s' % (pad, info, t.get_path_name() if t else None, t.get_editor_property('srgb') if t else '', t.get_editor_property('compression_settings') if t else ''))
        for p in a.get_editor_property('vector_parameter_values'):
            unreal.log('DIAG %s  vec %s = %s' % (pad, p.get_editor_property('parameter_info').get_editor_property('name'), p.get_editor_property('parameter_value')))
        for p in a.get_editor_property('scalar_parameter_values'):
            unreal.log('DIAG %s  scalar %s = %s' % (pad, p.get_editor_property('parameter_info').get_editor_property('name'), p.get_editor_property('parameter_value')))
        dump(a.get_editor_property('parent'), depth + 1)
    elif isinstance(a, unreal.Material):
        unreal.log('DIAG %s  blend=%s twosided=%s' % (pad, a.get_editor_property('blend_mode'), a.get_editor_property('two_sided')))
        for e in MEL.get_used_textures(a) if hasattr(MEL, 'get_used_textures') else []:
            unreal.log('DIAG %s  usedtex %s' % (pad, e.get_path_name()))
        try:
            node = MEL.get_material_property_input_node(a, unreal.MaterialProperty.MP_BASE_COLOR)
            unreal.log('DIAG %s  basecolor node=%s' % (pad, node.get_name() if node else None))
        except Exception as e:
            unreal.log('DIAG %s  basecolor err %s' % (pad, e))
for n in names:
    a = unreal.EditorAssetLibrary.load_asset(n)
    if isinstance(a, unreal.StaticMesh):
        for slot in a.get_editor_property('static_materials'):
            unreal.log('DIAG slot %s' % slot.get_editor_property('material_slot_name'))
            dump(slot.get_editor_property('material_interface'))
    else:
        dump(a)
