"""Diagnostic: walk the BaseColor expression graph of a material, printing node class and inputs."""
import unreal, os
MEL = unreal.MaterialEditingLibrary
mat = unreal.EditorAssetLibrary.load_asset(os.environ['DIAG_MAT'])
seen = set()
def walk(node, depth):
    if node is None or depth > 8: return
    key = node.get_path_name()
    unreal.log('DIAG %s%s %s' % ('  ' * depth, node.get_class().get_name(), getattr(node, 'get_editor_property', lambda x: '')('parameter_name') if hasattr(node, 'parameter_name') else ''))
    if key in seen: return
    seen.add(key)
    if isinstance(node, unreal.MaterialExpressionMaterialFunctionCall):
        unreal.log('DIAG %s  fn=%s' % ('  ' * depth, node.get_editor_property('material_function').get_path_name()))
    for i in MEL.get_inputs_for_material_expression(mat, node):
        walk(i, depth + 1)
walk(MEL.get_material_property_input_node(mat, unreal.MaterialProperty.MP_BASE_COLOR), 0)
