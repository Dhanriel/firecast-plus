"""Roda dentro do Blender (modo fundo): lista os objetos de cada modelo baixado e gera miniaturas 360 dos HDRIs.

  blender --factory-startup -b -P trailer3/inspecionar_blender.py -- <pasta trailer3>
"""
import os, sys

import bpy

BASE = sys.argv[sys.argv.index("--") + 1]
PH = os.path.join(BASE, "assets", "polyhaven")
SAIDA = os.path.join(BASE, "render", "previas")
os.makedirs(SAIDA, exist_ok=True)

for nome in sorted(os.listdir(PH)):
    gltf = [f for f in os.listdir(os.path.join(PH, nome)) if f.endswith(".gltf")]
    if not gltf:
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PH, nome, gltf[0]))
    print(f"== {nome}")
    for o in bpy.context.scene.objects:
        faces = len(o.data.polygons) if o.type == "MESH" else 0
        print(f"   {o.name:40} {o.type:6} dim={tuple(round(v, 3) for v in o.dimensions)} faces={faces} pai={o.parent.name if o.parent else '-'}")

# miniaturas 360 dos HDRIs, para escolher para onde a camera olha
bpy.ops.wm.read_factory_settings(use_empty=True)
cena = bpy.context.scene
cena.render.engine = "CYCLES"
cena.cycles.samples = 1
cena.render.resolution_x, cena.render.resolution_y = 1024, 512
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cena.collection.objects.link(cam)
cena.camera = cam
cam.data.type = "PANO"
if hasattr(cam.data, "panorama_type"):
    cam.data.panorama_type = "EQUIRECTANGULAR"
else:
    cam.data.cycles.panorama_type = "EQUIRECTANGULAR"
cam.rotation_euler = (1.5708, 0, 0)  # olhando para +Y, horizonte no meio
mundo = bpy.data.worlds.new("mundo")
cena.world = mundo
mundo.use_nodes = True
nos = mundo.node_tree.nodes
fundo = next(n for n in nos if n.type == "BACKGROUND")
amb = nos.new("ShaderNodeTexEnvironment")
mundo.node_tree.links.new(amb.outputs["Color"], fundo.inputs["Color"])
for nome in sorted(os.listdir(PH)):
    hdr = [f for f in os.listdir(os.path.join(PH, nome)) if f.endswith(".hdr")]
    if not hdr:
        continue
    amb.image = bpy.data.images.load(os.path.join(PH, nome, hdr[0]))
    cena.render.filepath = os.path.join(SAIDA, f"{nome}.jpg")
    cena.render.image_settings.file_format = "JPEG"
    bpy.ops.render.render(write_still=True)
    print("previa", nome)
