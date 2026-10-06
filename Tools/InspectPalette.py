import unreal
from pathlib import Path
lib = unreal.EditorAssetLibrary
palette = lib.load_asset('/Game/Wood/DA_BenchmarkPalette')
lines = []
lines.append('=== PALETTE INSPECTION ===')
gm = palette.get_editor_property('ground_material')
lines.append(f'Ground material: {gm.get_path_name() if gm else "None"}')
wm = palette.get_editor_property('water_material')
lines.append(f'Water material: {wm.get_path_name() if wm else "None"}')

trees = palette.get_editor_property('trees')
lines.append(f'Trees count: {len(trees)}')
for t in trees:
    lines.append(f'  Tree: {t.get_path_name()}')

saplings = palette.get_editor_property('saplings')
lines.append(f'Saplings count: {len(saplings)}')
for s in saplings:
    lines.append(f'  Sapling: {s.get_path_name()}')

grasses = palette.get_editor_property('grasses')
lines.append(f'Grasses count: {len(grasses)}')
for g in grasses:
    lines.append(f'  Grass: {g.get_path_name()}')

ferns = palette.get_editor_property('ferns')
lines.append(f'Ferns count: {len(ferns)}')
for f in ferns:
    lines.append(f'  Fern: {f.get_path_name()}')

rocks = palette.get_editor_property('rocks')
lines.append(f'Rocks count: {len(rocks)}')
for r in rocks:
    lines.append(f'  Rock: {r.get_path_name()}')

Path('C:/Misc/The-Wood/Saved/Logs/PaletteReport.txt').write_text('\n'.join(lines), encoding='utf-8')
