"""Versioned forest art bootstrap; run only after compiling TheWood module.
Creates project-local materials and imports CC0 prepared meshes. No runtime instances.
"""
import unreal
import json
import struct
from pathlib import Path

LIB = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
SMES = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
ROOT = Path(__file__).resolve().parent.parent
VERSION = 'CanopyV4'


def expr(mat, cls, **properties):
    node = MEL.create_material_expression(mat, cls)
    for name, value in properties.items():
        node.set_editor_property(name, value)
    return node


def constant(mat, value):
    return expr(mat, unreal.MaterialExpressionConstant, r=value)


def vector(mat, color):
    return expr(mat, unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*color))


def link(source, output, target, input_name):
    if not MEL.connect_material_expressions(source, output, target, input_name):
        raise RuntimeError('Material connection failed: ' + input_name)


def prop(node, output, material_property):
    if not MEL.connect_material_property(node, output, material_property):
        raise RuntimeError('Material output connection failed: ' + str(material_property))


def custom(mat, code, inputs, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    node = expr(mat, unreal.MaterialExpressionCustom, code=code, output_type=output_type)
    entries = []
    for name in inputs:
        entry = unreal.CustomInput()
        entry.set_editor_property('input_name', name)
        entries.append(entry)
    node.set_editor_property('inputs', entries)
    for name, (source, output) in inputs.items():
        link(source, output, node, name)
    return node


def fresh(name):
    path = '/Game/Wood/' + name
    if LIB.does_asset_exist(path):
        mat=LIB.load_asset(path)
        MEL.delete_all_material_expressions(mat)
        return mat, True
    return TOOLS.create_asset(name, '/Game/Wood', unreal.Material, unreal.MaterialFactoryNew()), True


def finish(mat):
    MEL.set_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    MEL.recompile_material(mat)
    LIB.save_loaded_asset(mat)
    return mat


def texture(asset, map_name):
    name = asset + '_' + map_name + '_2k'
    path = '/Game/Art/Ground/' + name
    if not LIB.does_asset_exist(path):
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(ROOT / 'ArtSource/PolyHaven' / asset / (asset + '-' + map_name + '.jpg')))
        task.set_editor_property('destination_path', '/Game/Art/Ground')
        task.set_editor_property('destination_name', name)
        task.set_editor_property('automated', True)
        task.set_editor_property('save', True)
        TOOLS.import_asset_tasks([task])
    tex = LIB.load_asset(path)
    if tex is None:
        raise RuntimeError('Texture import failed: ' + path)
    if map_name != 'Diffuse':
        tex.set_editor_property('srgb', False)
        tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP if map_name == 'nor_dx' else unreal.TextureCompressionSettings.TC_GRAYSCALE)
    LIB.save_loaded_asset(tex)
    return tex


def sample(mat, tex, uv, normal=False):
    node = expr(mat, unreal.MaterialExpressionTextureSample, texture=tex,
                sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if normal else (unreal.MaterialSamplerType.SAMPLERTYPE_COLOR if tex.get_editor_property('srgb') else unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE))
    link(uv, '', node, '')
    return node


GROUND_VERSION='BiomeV2'
ground, build = fresh('M_Ground_' + GROUND_VERSION)
if build:
    # Runtime contract: Vertex RGBA = temperate/dry/highlands/taiga weights;
    # mesh UV0 = moisture/slope. All texture coordinates use world position.
    ground.set_editor_property('tangent_space_normal',False)
    pos=expr(ground,unreal.MaterialExpressionWorldPosition)
    vertex=expr(ground,unreal.MaterialExpressionVertexColor)
    weights=expr(ground,unreal.MaterialExpressionComponentMask,r=True,g=True,b=True,a=False)
    link(vertex,'',weights,'')
    habitat=expr(ground,unreal.MaterialExpressionTextureCoordinate,coordinate_index=0)
    common={'W':(weights,''),'T':(vertex,'A'),'H':(habitat,'')}
    weight_code='''float4 b=max(float4(W,T),0.0);float total=dot(b,float4(1,1,1,1));
    b=total>0.0001?b/total:float4(1,0,0,0);
    float moisture=saturate(H.x);float slope=saturate(H.y);
    float exposed=smoothstep(0.30,0.65,slope)*(1.0-b.z)*0.38;
    b*=1.0-exposed;b.z+=exposed;
    float wet=smoothstep(0.94,0.99,moisture);
    float riparianGravel=smoothstep(0.95,0.995,moisture)*0.85;
    b=lerp(b,float4(0,0,1,0),riparianGravel);'''
    configs=[('forest_floor','return P.xy/270.0;'),
             ('withered_grass','return float2(P.x*0.940-P.y*0.342,P.x*0.342+P.y*0.940)/220.0;'),
             ('gravel_ground_01','return float2(P.x*0.760-P.y*0.650,P.x*0.650+P.y*0.760)/360.0;'),
             ('forest_ground_04','return float2(P.x*0.707+P.y*0.707,-P.x*0.707+P.y*0.707)/230.0;')]
    samples=[]
    for asset,uv_code in configs:
        uv=custom(ground,uv_code,{'P':(pos,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
        samples.append((sample(ground,texture(asset,'Diffuse'),uv),sample(ground,texture(asset,'nor_dx'),uv,True),sample(ground,texture(asset,'Rough'),uv)))
    color_inputs=dict(common,P=(pos,''))
    color_inputs.update({name:(samples[index][0],'RGB') for index,name in enumerate(('A','B','C','D'))})
    color=custom(ground,weight_code+'''
    float3 temperate=A*float3(0.60,0.70,0.49);
    float3 grassland=B*float3(0.66,0.74,0.40);
    float mineral=dot(C,float3(0.2126,0.7152,0.0722));
    float3 highlands=lerp(C,float3(mineral,mineral,mineral),0.65)*float3(0.78,0.82,0.86);
    float3 taiga=D*float3(0.48,0.62,0.54);
    float variation=0.5+0.5*sin(P.x/1400.0+sin(P.y/1800.0));
    taiga*=lerp(float3(0.90,0.92,0.94),float3(0.78,0.94,0.80),variation*moisture);
    float3 color=temperate*b.x+grassland*b.y+highlands*b.z+taiga*b.w;
    color*=lerp(float3(1,1,1),float3(0.66,0.73,0.65),wet);
    float macro=0.91+0.09*sin(P.x/1300.0)*sin(P.y/1700.0);
    return color*macro;''',color_inputs)
    prop(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    normal_inputs=dict(common,P=(pos,''))
    normal_inputs.update({name:(samples[index][1],'RGB') for index,name in enumerate(('A','B','C','D'))})
    normal=custom(ground,weight_code+'''
    float3 n0=A;
    float3 n1=float3(B.x*0.940+B.y*0.342,-B.x*0.342+B.y*0.940,B.z);
    float3 n2=float3(C.x*0.760+C.y*0.650,-C.x*0.650+C.y*0.760,C.z);
    float3 n3=float3(D.x*0.707-D.y*0.707,D.x*0.707+D.y*0.707,D.z);
    float3 detail=normalize(n0*b.x+n1*b.y+n2*b.z+n3*b.w);
    // UV0 is habitat data, so derive a world-space surface basis rather than
    // relying on texture tangents generated from moisture/slope coordinates.
    float3 surface=normalize(cross(ddx(P),ddy(P)));if(surface.z<0)surface=-surface;
    float3 tx=normalize(float3(surface.z,0,-surface.x));float3 ty=normalize(cross(surface,tx));
    float strength=lerp(0.55,0.32,wet);
    return normalize(tx*detail.x*strength+ty*detail.y*strength+surface*max(detail.z,0.2));''',normal_inputs)
    prop(normal,'',unreal.MaterialProperty.MP_NORMAL)
    rough_inputs=dict(common)
    rough_inputs.update({name:(samples[index][2],'R') for index,name in enumerate(('A','B','C','D'))})
    rough=custom(ground,weight_code+'''
    float base=clamp(A*b.x+B*b.y+C*b.z+D*b.w,0.79,1.0);
    return lerp(base,0.30,wet*0.85);''',rough_inputs,unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    prop(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    prop(constant(ground,0.22),'',unreal.MaterialProperty.MP_SPECULAR)
    finish(ground)

water, build = fresh('M_Water_' + VERSION)
if build:
    pos = expr(water, unreal.MaterialExpressionWorldPosition)
    time = expr(water, unreal.MaterialExpressionTime, ignore_pause=False)
    ripples = custom(water, '''float2 p1=float2(P.x*0.042,(P.y-T*65.0)*0.038);
float2 p2=float2((P.x+T*18.0)*0.08,(P.y-T*95.0)*0.07);
float a=cos(p1.x+sin(p1.y*0.8))*0.14+sin(p2.x*1.3)*0.09;
float b=sin(p1.y+cos(p1.x*0.7))*0.18+cos(p2.y*1.1)*0.11;
return normalize(float3(a,b,1.0));''', {'P':(pos,''),'T':(time,'')})
    # Downstream flow: ribbon UV0 is (across channel, Y/4); scroll V along the flow.
    uv=expr(water,unreal.MaterialExpressionTextureCoordinate,coordinate_index=0)
    flow_tex=texture('forest_ground_04','nor_dx')
    scroll_a=expr(water,unreal.MaterialExpressionPanner,speed_x=0.0,speed_y=0.35)
    link(uv,'',scroll_a,'Coordinate')
    link(time,'',scroll_a,'Time')
    tiled=custom(water,'return UV*1.7;',{'UV':(uv,'')},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    scroll_b=expr(water,unreal.MaterialExpressionPanner,speed_x=0.0,speed_y=0.21)
    link(tiled,'',scroll_b,'Coordinate')
    link(time,'',scroll_b,'Time')
    flow_a=sample(water,flow_tex,scroll_a,True)
    flow_b=sample(water,flow_tex,scroll_b,True)
    flow=custom(water,'''float3 f=normalize(A*0.5+B*0.5);
float3 r=normalize(R);
return normalize(float3(r.xy*0.6+f.xy,r.z*f.z));''',{'A':(flow_a,'RGB'),'B':(flow_b,'RGB'),'R':(ripples,'')})
    prop(flow,'',unreal.MaterialProperty.MP_NORMAL)
    color=custom(water,'float shimmer=0.5+0.5*sin(P.x/140.0+(P.y-T*60.0)/180.0); return lerp(float3(0.015,0.040,0.038),float3(0.028,0.072,0.064),shimmer);',{'P':(pos,''),'T':(time,'')})
    prop(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    prop(constant(water,0.12),'',unreal.MaterialProperty.MP_ROUGHNESS)
    prop(constant(water,0.45),'',unreal.MaterialProperty.MP_SPECULAR)
    finish(water)

# Keep the fixed asset path used by the runtime sky sphere; rebuild the owned
# project material once. A two-sided unlit altitude gradient works from inside.
sky_path='/Game/Wood/M_Sky'
if LIB.does_asset_exist(sky_path):
    sky=LIB.load_asset(sky_path)
else:
    sky=TOOLS.create_asset('M_Sky','/Game/Wood',unreal.Material,unreal.MaterialFactoryNew())
MEL.delete_all_material_expressions(sky)
sky.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
sky.set_editor_property('two_sided',True)
sky.set_editor_property('is_sky',False)
pos=expr(sky,unreal.MaterialExpressionWorldPosition)
camera=expr(sky,unreal.MaterialExpressionCameraPositionWS)
brightness=expr(sky,unreal.MaterialExpressionScalarParameter,parameter_name='SkyBrightness',default_value=1.0)
cloud_cover=expr(sky,unreal.MaterialExpressionScalarParameter,parameter_name='CloudCover',default_value=0.5)
sky_time=expr(sky,unreal.MaterialExpressionTime,ignore_pause=False)
gradient=custom(sky,'''float3 dir=normalize(P-C);float h=saturate(dir.z);
float3 base=lerp(float3(0.52,0.59,0.64),float3(0.12,0.24,0.38),pow(h,0.55));
float2 q=dir.xy/max(h+0.22,0.22)*3.0+float2(T*0.006,T*0.003);
float field=0.5+0.22*sin(q.x+0.45*sin(q.y))+0.17*cos(q.y*1.4)+0.1*sin(q.x*2.3+q.y*0.8);
float cover=saturate(Cov);float clouds=smoothstep(1.0-cover,1.18-cover,field)*saturate(cover*1.5)*smoothstep(0.01,0.18,h);
return lerp(base,float3(0.70,0.74,0.76),clouds*0.65)*S;''',{'P':(pos,''),'C':(camera,''),'S':(brightness,''),'Cov':(cloud_cover,''),'T':(sky_time,'')})
prop(gradient,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
finish(sky)


def explicit_needles():
    """Bypass glTF master blend overrides with a direct project MASK material."""
    source=ROOT/'ArtSource/Prepared/pine_tree_01_00.glb'
    data=source.read_bytes()
    size=struct.unpack_from('<I',data,12)[0]
    doc=json.loads(data[20:20+size])
    leaf=next(m for m in doc['materials'] if 'PineNeedleCards' in m.get('name',''))
    texture_index=leaf['pbrMetallicRoughness']['baseColorTexture']['index']
    image=doc['images'][doc['textures'][texture_index]['source']]
    view=doc['bufferViews'][image['bufferView']]
    start=28+size+view.get('byteOffset',0)
    atlas=ROOT/'ArtSource/Prepared/PineNeedlesRGBA.png'
    atlas.write_bytes(data[start:start+view['byteLength']])
    path='/Game/Art/Ground/T_PineNeedlesRGBA_'+VERSION
    if not LIB.does_asset_exist(path):
        task=unreal.AssetImportTask()
        task.set_editor_property('filename',str(atlas))
        task.set_editor_property('destination_path','/Game/Art/Ground')
        task.set_editor_property('destination_name','T_PineNeedlesRGBA_'+VERSION)
        task.set_editor_property('automated',True)
        task.set_editor_property('save',True)
        TOOLS.import_asset_tasks([task])
    tex=LIB.load_asset(path)
    if tex is None:
        raise RuntimeError('Could not import RGBA needle atlas')
    tex.set_editor_property('compression_no_alpha',False)
    tex.set_editor_property('srgb',True)
    LIB.save_loaded_asset(tex)
    mat,_=fresh('M_Needles_'+VERSION+'_Masked1')
    mat.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property('two_sided',True)
    mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    mat.set_editor_property('opacity_mask_clip_value',0.35)
    uv=expr(mat,unreal.MaterialExpressionTextureCoordinate,coordinate_index=0)
    atlas_sample=sample(mat,tex,uv)
    prop(atlas_sample,'RGB',unreal.MaterialProperty.MP_BASE_COLOR)
    prop(atlas_sample,'A',unreal.MaterialProperty.MP_OPACITY_MASK)
    transmission=custom(mat,'return C*0.35;',{'C':(atlas_sample,'RGB')})
    prop(transmission,'',unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    prop(constant(mat,0.82),'',unreal.MaterialProperty.MP_ROUGHNESS)
    prop(constant(mat,0.12),'',unreal.MaterialProperty.MP_SPECULAR)
    weight=expr(mat,unreal.MaterialExpressionTextureCoordinate,coordinate_index=1)
    time=expr(mat,unreal.MaterialExpressionTime,ignore_pause=False)
    pos=expr(mat,unreal.MaterialExpressionWorldPosition)
    strength=expr(mat,unreal.MaterialExpressionScalarParameter,parameter_name='WindStrength',default_value=1.0)
    offset=custom(mat,'''float phase=P.x*0.0017+P.y*0.0012;
float gust=0.58+0.42*sin(T*0.37+phase*0.15);
return float3(sin(T*1.1+phase),cos(T*0.83+phase)*0.38,0)*16.0*W.x*gust*S;''',{'W':(weight,''),'T':(time,''),'P':(pos,''),'S':(strength,'')})
    prop(offset,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mat.set_editor_property('max_world_position_offset_displacement',16.0)
    return finish(mat)


needles=explicit_needles()


def with_wind(interface, strength):
    """Copy each project import parent; preserve alpha, textures and shading."""
    name=interface.get_name() + '_' + VERSION + '_Wind' + str(int(strength))
    dest='/Game/Wood/FoliageWind/' + name
    if LIB.does_asset_exist(dest):
        return LIB.load_asset(dest)
    if isinstance(interface,unreal.MaterialInstanceConstant):
        parent=interface.get_editor_property('parent')
        animated_parent=with_wind(parent,strength)
        copy=LIB.duplicate_asset(interface.get_path_name(),dest)
        MEL.set_material_instance_parent(copy,animated_parent)
        LIB.save_loaded_asset(copy)
        return copy
    if not isinstance(interface,unreal.Material):
        raise RuntimeError('Unsupported foliage material: '+interface.get_path_name())
    copy=LIB.duplicate_asset(interface.get_path_name(),dest)
    color=expr(copy,unreal.MaterialExpressionTextureCoordinate,coordinate_index=1)
    time=expr(copy,unreal.MaterialExpressionTime,ignore_pause=False)
    pos=expr(copy,unreal.MaterialExpressionWorldPosition)
    amplitude=constant(copy,strength)
    weather_strength=expr(copy,unreal.MaterialExpressionScalarParameter,parameter_name='WindStrength',default_value=1.0)
    offset=custom(copy,'''float phase=P.x*0.0017+P.y*0.0012;
float gust=0.58+0.42*sin(T*0.37+phase*0.15);
return float3(sin(T*1.1+phase),cos(T*0.83+phase)*0.38,0)*A*W.x*gust*S;''',{'W':(color,''),'T':(time,''),'P':(pos,''),'A':(amplitude,''),'S':(weather_strength,'')})
    prop(offset,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    copy.set_editor_property('max_world_position_offset_displacement',strength)
    return finish(copy)

def with_instancing(interface):
    """Compile local rock parents for HISM without changing plugin masters."""
    # _2K suffix: rock re-imports from the 2k source must not reuse 1k-era copies.
    dest='/Game/Wood/RockMaterials/'+interface.get_name()+'_'+VERSION+'_2K'
    if LIB.does_asset_exist(dest):
        return LIB.load_asset(dest)
    copy=LIB.duplicate_asset(interface.get_path_name(),dest)
    if isinstance(copy,unreal.MaterialInstanceConstant):
        parent=with_instancing(interface.get_editor_property('parent'))
        MEL.set_material_instance_parent(copy,parent)
        MEL.set_material_usage_override(copy,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES,True,True)
        LIB.save_loaded_asset(copy)
        return copy
    if isinstance(copy,unreal.Material):
        return finish(copy)
    raise RuntimeError('Unsupported rock material: '+interface.get_path_name())


def author_lods(mesh, slot):
    """Keep LOD0 intact; reduce only distant geometry, once per import version."""
    lod_version=VERSION+'_ConservativeLOD1'
    if LIB.get_metadata_tag(mesh,'WoodLODVersion') == lod_version:
        return
    if slot == 'trees':
        levels=[(1.0,1.0),(0.65,0.45),(0.35,0.18),(0.18,0.065)]
    elif slot in ('grasses','ferns'):
        levels=[(1.0,1.0),(0.5,0.08),(0.2,0.018)]
    else:
        levels=[(1.0,1.0),(0.5,0.15),(0.2,0.04)]
    # UE5 names supersede deprecated EditorScripting aliases. The subsystem
    # copies LOD0 build settings, retaining authored UV1 wind masks.
    reductions=[unreal.StaticMeshReductionSettings(percent_triangles=ratio,screen_size=screen) for ratio,screen in levels]
    options=unreal.StaticMeshReductionOptions(auto_compute_lod_screen_size=False,reduction_settings=reductions)
    try:
        count=SMES.set_lods(mesh,options)
        if count != len(levels):
            unreal.log_warning('LOD generation partial count on: '+mesh.get_name())
    except Exception as e:
        unreal.log_warning('LOD generation skipped for: '+mesh.get_name()+': '+str(e))
    LIB.set_metadata_tag(mesh,'WoodLODVersion',lod_version)


def gravel_texture(map_name, file_name, normal=False, srgb=False):
    """Gravel022 1K source textures; normal map is OpenGL (green-up) and flipped in-material."""
    path = '/Game/Art/Ground/Gravel022_' + map_name + '_1k'
    if not LIB.does_asset_exist(path):
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(ROOT / 'ArtSource/Textures/Gravel022' / file_name))
        task.set_editor_property('destination_path', '/Game/Art/Ground')
        task.set_editor_property('destination_name', 'Gravel022_' + map_name + '_1k')
        task.set_editor_property('automated', True)
        task.set_editor_property('save', True)
        TOOLS.import_asset_tasks([task])
    tex = LIB.load_asset(path)
    if tex is None:
        raise RuntimeError('Gravel texture import failed: ' + path)
    tex.set_editor_property('srgb', srgb)
    if normal:
        compression = unreal.TextureCompressionSettings.TC_NORMALMAP
    elif srgb:
        compression = unreal.TextureCompressionSettings.TC_DEFAULT
    else:
        compression = unreal.TextureCompressionSettings.TC_GRAYSCALE
    tex.set_editor_property('compression_settings', compression)
    LIB.save_loaded_asset(tex)
    return tex


# Trailhead lot gravel: world-aligned 2 m tiling; vertex alpha (1 pad, 0 skirt edge) is the opacity.
lot, build = fresh('M_Gravel_Lot')
if build:
    lot.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    lot.set_editor_property('two_sided', True)
    lot_pos = expr(lot, unreal.MaterialExpressionWorldPosition)
    lot_uv = custom(lot, 'return P.xy/200.0;', {'P': (lot_pos, '')}, unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    lot_color = sample(lot, gravel_texture('Color', 'Gravel022_1K-JPG_Color.jpg', srgb=True), lot_uv)
    lot_normal = sample(lot, gravel_texture('NormalGL', 'Gravel022_1K-JPG_NormalGL.jpg', normal=True), lot_uv, True)
    lot_rough = sample(lot, gravel_texture('Roughness', 'Gravel022_1K-JPG_Roughness.jpg'), lot_uv)
    lot_flipped = custom(lot, 'return float3(N.x,-N.y,N.z);', {'N': (lot_normal, 'RGB')})
    prop(lot_color, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    prop(lot_flipped, '', unreal.MaterialProperty.MP_NORMAL)
    prop(lot_rough, 'R', unreal.MaterialProperty.MP_ROUGHNESS)
    lot_vertex = expr(lot, unreal.MaterialExpressionVertexColor)
    prop(lot_vertex, 'A', unreal.MaterialProperty.MP_OPACITY)
    finish(lot)

palette_path='/Game/Wood/DA_BenchmarkPalette'
if not LIB.does_asset_exist(palette_path):
    factory=unreal.DataAssetFactory()
    factory.set_editor_property('data_asset_class',unreal.WoodPalette)
    TOOLS.create_asset('DA_BenchmarkPalette','/Game/Wood',unreal.WoodPalette,factory)
palette=LIB.load_asset(palette_path)
palette.set_editor_property('ground_material',ground)
palette.set_editor_property('water_material',water)
palette.set_editor_property('lot_material',lot)
prepared=ROOT/'ArtSource/Prepared'
records=json.loads((prepared/'inspection.json').read_text(encoding='utf-8'))
groups={'trees':[],'saplings':[],'ferns':[],'grasses':[],'rocks':[],'prairie':[]}
slots={'pine_tree_01':'trees','pine_sapling_small':'saplings','fern_02':'ferns','grass_medium_01':'grasses','boulder_01':'rocks','rock_moss_set_01':'rocks','rock_moss_set_02':'rocks','rock_07':'rocks','prairie_clump':'prairie'}
for record in records:
    # Versioned destinations migrate old imports with wind masks.
    if record['asset']=='grass_medium_01' and record['triangles']<60:
        continue
    # Source grasses feed prairie clumps only; they are not palette slots.
    if record['asset'] in ('grass_bermuda_01','grass_medium_02'):
        continue
    # Records outside the palette slot map (e.g. E2a trailhead props) are not palette slots.
    if record['asset'] not in slots:
        continue
    destination='/Game/Art/PolyHaven/' + VERSION + '/' + record['variant']
    existing=LIB.list_assets(destination,recursive=True)
    if not existing or record['asset'] in ('pine_tree_01','prairie_clump','rock_07','boulder_01','rock_moss_set_01','rock_moss_set_02'):
        # Pine, prairie clump and 2k rock meshes change with every Prepare-Art revision; re-import over the version.
        task=unreal.AssetImportTask()
        task.set_editor_property('filename',str(prepared/record['file']))
        task.set_editor_property('destination_path',destination)
        task.set_editor_property('automated',True)
        task.set_editor_property('save',True)
        task.set_editor_property('replace_existing',True)
        TOOLS.import_asset_tasks([task])
        existing=LIB.list_assets(destination,recursive=True)
    meshes=[LIB.load_asset(path) for path in existing]
    meshes=[mesh for mesh in meshes if isinstance(mesh,unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError('Import produced no mesh: '+record['variant'])
    slot=slots[record['asset']]
    for mesh in meshes:
        if slot in ('trees','saplings'):
            mesh.set_editor_property('allow_cpu_access',True)
        # All lighting is dynamic; UV1 is the authored root wind mask. Keep
        # automatic lightmap generation from replacing it during mesh builds.
        settings=SMES.get_lod_build_settings(mesh,0)
        settings.set_editor_property('generate_lightmap_u_vs',False)
        SMES.set_lod_build_settings(mesh,0,settings)
        author_lods(mesh,slot)
        if slot != 'rocks':
            strength=16.0 if slot=='trees' else (4.0 if slot=='ferns' else 3.0)
            for i,item in enumerate(mesh.get_editor_property('static_materials')):
                interface=item.get_editor_property('material_interface')
                if interface is not None and slot=='trees' and ('PineNeedleCards' in interface.get_name() or interface.get_name().startswith('M_Needles_')):
                    mesh.set_material(i,needles)
                elif interface is not None and '/Game/Wood/FoliageWind/' not in interface.get_path_name():
                    mesh.set_material(i,with_wind(interface,strength))
        else:
            for i,item in enumerate(mesh.get_editor_property('static_materials')):
                interface=item.get_editor_property('material_interface')
                if interface is not None and '/Game/Wood/RockMaterials/' not in interface.get_path_name():
                    mesh.set_material(i,with_instancing(interface))
        LIB.save_loaded_asset(mesh)
    groups[slot].extend(meshes)
    if slot == 'rocks':
        # Verification log: rock textures should report max dimension 2048 (2k source set).
        for path in LIB.list_assets(destination,recursive=True):
            asset=LIB.load_asset(path)
            if isinstance(asset,unreal.Texture2D):
                unreal.log('ROCK_TEX %s %dx%d' % (path,asset.blueprint_get_size_x(),asset.blueprint_get_size_y()))
for slot,meshes in groups.items():
    if not meshes:
        raise RuntimeError('Empty required palette slot: '+slot)
    # Explicit library migration: never preserve obsolete sapling-only slots.
    palette.set_editor_property(slot,meshes)
# Props (E2): palette index equals propId. Forced replace-reimport, one simple
# box collision per mesh, and instancing-usable materials as for rocks.
props=[]
for index in range(4):
    name='prop_%02d' % index
    source=prepared/(name+'.glb')
    if not source.exists():
        raise RuntimeError('Missing prop source: '+str(source))
    destination='/Game/Art/Props/'+VERSION
    task=unreal.AssetImportTask()
    task.set_editor_property('filename',str(source))
    task.set_editor_property('destination_path',destination)
    task.set_editor_property('automated',True)
    task.set_editor_property('save',True)
    task.set_editor_property('replace_existing',True)
    TOOLS.import_asset_tasks([task])
    found=[LIB.load_asset(path) for path in LIB.list_assets(destination,recursive=True)]
    found=[mesh for mesh in found if isinstance(mesh,unreal.StaticMesh) and mesh.get_name()==name]
    if len(found)!=1:
        raise RuntimeError('Prop import produced no unique mesh: '+name)
    mesh=found[0]
    SMES.remove_collisions(mesh)
    SMES.add_simple_collisions(mesh,unreal.ScriptingCollisionShapeType.BOX)
    for i,item in enumerate(mesh.get_editor_property('static_materials')):
        interface=item.get_editor_property('material_interface')
        if interface is not None and '/Game/Wood/RockMaterials/' not in interface.get_path_name():
            mesh.set_material(i,with_instancing(interface))
    LIB.save_loaded_asset(mesh)
    props.append(mesh)
palette.set_editor_property('props',props)
# Masonry kit (discovery pieces): palette index equals kitId from Source/TheWood/Public/Generation/WoodKit.h.
# Forced replace-reimport; stone materials stay as imported from the GLB textures.
# Box collision only for walls, piers, abutments and boulders; none for rubble, debris, fern patch, foundation and stepping stones.
KIT_FILES=[
 ('kit_sm_drystone_wall',True),
 ('kit_sm_drystone_rubble',False),
 ('kit_sm_stonepier',True),
 ('kit_sm_stonepier_ruined',True),
 ('kit_sm_foundationcourse',False),
 ('kit_sm_masonrydebris',False),
 ('kit_sm_fernpatch',False),
 ('kit_sm_bridgeabutment',True),
 ('kit_sm_riversteppingstone',False),
 ('kit_sm_granitemonolith',True),
 ('kit_sm_talusrock',True),
]
kit=[]
for index,(name,solid) in enumerate(KIT_FILES):
    source=prepared/(name+'.glb')
    if not source.exists():
        raise RuntimeError('Missing kit source: '+str(source))
    destination='/Game/Art/Kit/'+VERSION
    task=unreal.AssetImportTask()
    task.set_editor_property('filename',str(source))
    task.set_editor_property('destination_path',destination)
    task.set_editor_property('automated',True)
    task.set_editor_property('save',True)
    task.set_editor_property('replace_existing',True)
    TOOLS.import_asset_tasks([task])
    found=[LIB.load_asset(path) for path in LIB.list_assets(destination,recursive=True)]
    found=[mesh for mesh in found if isinstance(mesh,unreal.StaticMesh) and mesh.get_name()==name]
    if len(found)!=1:
        raise RuntimeError('Kit import produced no unique mesh: '+name)
    mesh=found[0]
    SMES.remove_collisions(mesh)
    if solid:
        SMES.add_simple_collisions(mesh,unreal.ScriptingCollisionShapeType.BOX)
    for i,item in enumerate(mesh.get_editor_property('static_materials')):
        interface=item.get_editor_property('material_interface')
        if interface is not None and '/Game/Wood/RockMaterials/' not in interface.get_path_name():
            mesh.set_material(i,with_instancing(interface))
    LIB.save_loaded_asset(mesh)
    kit.append(mesh)
palette.set_editor_property('kit',kit)
LIB.save_loaded_asset(palette)

# Preserve low-root vertex data on older sapling assets too, for packaged
# grounding if they are selected later. This does not alter pivots or geometry.
for record in records:
    if record['asset']!='pine_sapling_small':
        continue
    for folder in ('', 'ForestV2/', 'CanopyV3/'):
        destination='/Game/Art/PolyHaven/'+folder+record['variant']
        for path in LIB.list_assets(destination,recursive=True):
            mesh=LIB.load_asset(path)
            if isinstance(mesh,unreal.StaticMesh) and not mesh.get_editor_property('allow_cpu_access'):
                mesh.set_editor_property('allow_cpu_access',True)
                LIB.save_loaded_asset(mesh)

map_path='/Game/Maps/VisualBenchmark'
if not LIB.does_asset_exist(map_path):
    subsystem=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not subsystem.new_level(map_path) or not subsystem.save_current_level():
        raise RuntimeError('Could not create benchmark map')
unreal.log('The Wood forest art initialized: mature canopy, textured ground, flowing ripples and anchored foliage wind.')


