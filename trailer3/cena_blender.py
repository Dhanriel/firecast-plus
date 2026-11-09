"""Monta a mesa de RPG em 3D e renderiza as "fotos" do trailer 3. Roda dentro do Blender, em modo fundo:

  blender --factory-startup -b -P trailer3/cena_blender.py -- <pasta trailer3> [previa] [tomadas...]

  previa   -> 25% da resolucao e poucas amostras, para acertar enquadramento rapido
  tomadas  -> d20 mesa mapa final diario ceu rua torre taverna (padrao: todas)

Saidas em trailer3/render/: <tomada>.png, <tomada>_prof.png (profundidade, 16 bits, perto = claro),
mascara_kael.png e posicoes.json (pixels dos objetos que o compositor anima por cima).
"""
import json, math, os, random, sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
BASE = ARGS[0]
PREVIA = "previa" in ARGS[1:]
TOMADAS = [a for a in ARGS[1:] if a != "previa"]
PH = os.path.join(BASE, "assets", "polyhaven")
GER = os.path.join(BASE, "assets", "gerados")
OUT = os.path.join(BASE, "render", "previa" if PREVIA else "")
os.makedirs(OUT, exist_ok=True)
RES = (2304, 1296)  # 20% acima de 1080p: folga para o movimento de camera no compositor
FONTE = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "georgiab.ttf")
random.seed(7)


# ---------------------------------------------------------------- utilidades

def entrada(no, *nomes):
    """Primeira entrada do no que existir (os nomes mudaram entre versoes do Blender)."""
    for n in nomes:
        if n in no.inputs:
            return no.inputs[n]
    return None


def setp(no, valor, *nomes):
    e = entrada(no, *nomes)
    if e is not None:
        e.default_value = valor


def novo_material(nome):
    m = bpy.data.materials.new(nome)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    return m, m.node_tree.nodes, m.node_tree.links, next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def imagem(caminho, dados=False):
    im = bpy.data.images.load(caminho, check_existing=True)
    if dados:
        im.colorspace_settings.is_data = True
    return im


def mat_pbr(nome, pasta, escala):
    """Material PBR da Poly Haven (diffuse, normal GL, rough) com repeticao em metros."""
    m, nos, ln, b = novo_material(nome)
    arq = {f.split("_")[-2] if f.count("_") >= 2 else f: f for f in os.listdir(pasta)}
    def tex(chave, dados):
        f = next(v for k, v in arq.items() if chave in v.lower())
        t = nos.new("ShaderNodeTexImage")
        t.image = imagem(os.path.join(pasta, f), dados)
        ln.new(mapa.outputs["Vector"], t.inputs["Vector"])
        return t
    coord = nos.new("ShaderNodeTexCoord")
    mapa = nos.new("ShaderNodeMapping")
    mapa.inputs["Scale"].default_value = escala
    ln.new(coord.outputs["UV"], mapa.inputs["Vector"])
    ln.new(tex("diff", False).outputs["Color"], entrada(b, "Base Color"))
    ln.new(tex("rough", True).outputs["Color"], entrada(b, "Roughness"))
    nm = nos.new("ShaderNodeNormalMap")
    ln.new(tex("nor_gl", True).outputs["Color"], nm.inputs["Color"])
    ln.new(nm.outputs["Normal"], entrada(b, "Normal"))
    return m


def mat_simples(nome, cor, rough=0.4, metal=0.0, **extra):
    m, nos, ln, b = novo_material(nome)
    setp(b, (*cor, 1.0), "Base Color")
    setp(b, rough, "Roughness")
    setp(b, metal, "Metallic")
    for k, v in extra.items():
        setp(b, v, *k.split("|"))
    return m


def mat_resina(nome, cor_vidro, cor_volume, densidade):
    """Dado de resina: superficie transparente + absorcao de volume (cor profunda no miolo)."""
    m, nos, ln, b = novo_material(nome)
    setp(b, (*cor_vidro, 1.0), "Base Color")
    setp(b, 0.06, "Roughness")
    setp(b, 1.0, "Transmission Weight", "Transmission")
    setp(b, 1.52, "IOR")
    vol = nos.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (*cor_volume, 1.0)
    vol.inputs["Density"].default_value = densidade
    saida = next(n for n in nos if n.type == "OUTPUT_MATERIAL")
    ln.new(vol.outputs[0], saida.inputs["Volume"])
    return m


def mat_emissao(nome, cor, forca):
    m, nos, ln, b = novo_material(nome)
    setp(b, (0, 0, 0, 1), "Base Color")
    setp(b, (*cor, 1.0), "Emission Color", "Emission")
    setp(b, forca, "Emission Strength")
    return m


def objeto_malha(nome, me, local=(0, 0, 0)):
    o = bpy.data.objects.new(nome, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = local
    return o


def caixa_mundo(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), \
        Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))


def importar(nome_asset, pegar=None):
    pasta = os.path.join(PH, nome_asset)
    gltf = next(f for f in os.listdir(pasta) if f.endswith(".gltf"))
    antes = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(pasta, gltf))
    novos = [o for o in bpy.context.scene.objects if o not in antes]
    if pegar is not None:
        for o in novos:
            if o.name not in pegar:
                bpy.data.objects.remove(o, do_unlink=True)
        novos = [bpy.data.objects[n] for n in pegar]
    return novos


def posicionar(objs, centro_xy, rot_z=0.0, escala=1.0, z=0.0):
    """Gira/escala um grupo em torno do proprio centro e apoia a base em z."""
    for o in objs:
        o.parent = None
    vazio = bpy.data.objects.new("grupo", None)
    bpy.context.scene.collection.objects.link(vazio)
    lo, hi = caixa_mundo(objs)
    vazio.location = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)
    bpy.context.view_layer.update()
    for o in objs:
        mw = o.matrix_world.copy()
        o.parent = vazio
        o.matrix_parent_inverse = vazio.matrix_world.inverted()
        o.matrix_world = mw
    vazio.location = (centro_xy[0], centro_xy[1], z)
    vazio.rotation_euler = (0, 0, math.radians(rot_z))
    vazio.scale = (escala, escala, escala)
    bpy.context.view_layer.update()
    return vazio


# ---------------------------------------------------------------- dados (d20 com numeros, d6 com pintas)

def d20(nome, raio, mat_corpo, mat_numero, local, giro):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=raio)
    bm.faces.ensure_lookup_table()
    topo = max(bm.faces, key=lambda f: f.normal.z)
    rot = topo.normal.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Rotation(giro, 4, "Z") @ rot, verts=bm.verts)  # uma face para cima
    bm.normal_update()
    faces = sorted(bm.faces, key=lambda f: -f.normal.z)
    # numeracao de d20 de verdade: faces opostas somam 21; a de cima e o 20
    numeros, livres = {}, list(faces)
    proximo = 20
    while livres:
        f = livres.pop(0)
        oposta = min(livres, key=lambda g: (g.normal + f.normal).length)
        livres.remove(oposta)
        numeros[f.index], numeros[oposta.index] = proximo, 21 - proximo
        proximo -= 1
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    corpo = objeto_malha(nome, me)
    corpo.data.materials.append(mat_corpo)
    bev = corpo.modifiers.new("chanfro", "BEVEL")
    bev.width, bev.segments, bev.limit_method = raio * 0.06, 3, "ANGLE"
    fonte = bpy.data.fonts.load(FONTE, check_existing=True)
    partes = []
    for f in faces:
        n = numeros[f.index]
        cu = bpy.data.curves.new(f"n{n}", "FONT")
        cu.body = str(n) + ("." if n in (6, 9) else "")
        cu.font, cu.size, cu.align_x, cu.align_y, cu.extrude = fonte, raio * 0.45, "CENTER", "CENTER", raio * 0.012
        t = bpy.data.objects.new(f"n{n}", cu)
        bpy.context.scene.collection.objects.link(t)
        c = f.calc_center_median()
        # texto "em pe" na face: eixo Y do texto aponta para o primeiro vertice da face
        y = (f.verts[0].co - c).normalized()
        z = f.normal.normalized()
        x = y.cross(z).normalized()
        m = Matrix((x, y, z)).transposed().to_4x4()
        m.translation = c + z * (raio * 0.004)
        t.matrix_world = m
        partes.append(t)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    bmn = bmesh.new()
    for t in partes:
        tmp = bpy.data.meshes.new_from_object(t.evaluated_get(deps))
        tmp.transform(t.matrix_world)
        bmn.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bpy.data.objects.remove(t, do_unlink=True)
    men = bpy.data.meshes.new(nome + "_numeros")
    bmn.to_mesh(men)
    nums = objeto_malha(nome + "_numeros", men)
    nums.data.materials.append(mat_numero)
    nums.parent = corpo
    lo = min(v.co.z for v in me.vertices)
    corpo.location = (local[0], local[1], -lo)
    return corpo


def d6(nome, lado, mat_corpo, mat_pinta, local, giro_z, cima=6):
    bpy.ops.mesh.primitive_cube_add(size=lado, location=(0, 0, 0))
    corpo = bpy.context.active_object
    corpo.name = nome
    corpo.data.materials.append(mat_corpo)
    bev = corpo.modifiers.new("chanfro", "BEVEL")
    bev.width, bev.segments = lado * 0.12, 4
    sub = corpo.modifiers.new("suave", "SUBSURF")
    sub.levels = sub.render_levels = 1
    # faces opostas somam 7; padrao classico das pintas em coordenadas da face (-1..1)
    padrao = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (-1, 1), (1, -1), (1, 1)],
              5: [(-1, -1), (-1, 1), (0, 0), (1, -1), (1, 1)], 6: [(-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)]}
    faces = {(0, 0, 1): cima, (0, 0, -1): 7 - cima, (1, 0, 0): 2 if cima != 2 else 3, (-1, 0, 0): 5 if cima != 2 else 4,
             (0, 1, 0): 3 if cima != 2 else 1, (0, -1, 0): 4 if cima != 2 else 6}
    bm = bmesh.new()
    for normal, n in faces.items():
        nv = Vector(normal)
        u = Vector((0, 0, 1)).cross(nv) if abs(nv.z) < 0.5 else Vector((1, 0, 0))
        u.normalize()
        v = nv.cross(u)
        for a, b in padrao[n]:
            p = nv * (lado * 0.5) + u * (a * lado * 0.24) + v * (b * lado * 0.24)
            m = Matrix.Translation(p) @ nv.to_track_quat("Z", "Y").to_matrix().to_4x4() @ Matrix.Diagonal((1, 1, 0.35, 1))
            bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=lado * 0.085, matrix=m)
    me = bpy.data.meshes.new(nome + "_pintas")
    bm.to_mesh(me)
    pintas = objeto_malha(nome + "_pintas", me)
    pintas.data.materials.append(mat_pinta)
    pintas.parent = corpo
    corpo.location = (local[0], local[1], lado / 2)
    corpo.rotation_euler = (0, 0, giro_z)
    return corpo


# ---------------------------------------------------------------- a cena

def montar_mesa():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cena = bpy.context.scene
    pos = {}

    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.3, 0))
    mesa = bpy.context.active_object
    mesa.scale = (3.4, 2.6, 1)
    mesa.data.materials.append(mat_pbr("madeira", os.path.join(PH, "dark_wood"), (2.4, 1.8, 1)))

    m_papel, nos, ln, b = novo_material("pergaminho")
    t = nos.new("ShaderNodeTexImage")
    t.image = imagem(os.path.join(GER, "mapa.png"))
    ln.new(t.outputs["Color"], entrada(b, "Base Color"))
    setp(b, 0.82, "Roughness")
    relevo = nos.new("ShaderNodeBump")
    relevo.inputs["Strength"].default_value = 0.08
    ln.new(t.outputs["Color"], relevo.inputs["Height"])
    ln.new(relevo.outputs["Normal"], entrada(b, "Normal"))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0.0006))
    mapa = bpy.context.active_object
    mapa.name = "mapa"
    mapa.scale = (0.9, 0.6, 1)
    mapa.rotation_euler = (0, 0, math.radians(-2))
    mapa.data.materials.append(m_papel)
    bpy.context.view_layer.update()

    def casa(col, lin):  # centro de uma casa da grade do mapa (24 x 16 casas de 3,75 cm)
        local = Vector((-0.45 + (col + 0.5) * 0.0375, 0.30 - (lin + 0.5) * 0.0375, 0))
        return mapa.matrix_world @ Vector((local.x / 0.9, local.y / 0.6, 0))

    # miniaturas: pecas de xadrez nas casas do mapa
    pecas = {"piece_knight_white_01": ("kael", 12, 7, 150), "piece_queen_white": ("aria", 9, 10, 0),
             "piece_bishop_white_01": ("clerigo", 10, 8, 0), "piece_pawn_black_01": ("goblin1", 18, 10, 0),
             "piece_pawn_black_02": ("goblin2", 19, 11, 0), "piece_pawn_black_03": ("goblin3", 20, 9, 0),
             "piece_rook_black_01": ("golem", 21, 12, 0), "piece_king_black": ("chefe", 20, 6, 0)}
    for o in importar("chess_set", pegar=list(pecas)):
        apelido, c, l, giro = pecas[o.name]
        p = casa(c, l)
        lo, _ = caixa_mundo([o])
        o.location = (p.x, p.y, o.location.z - lo.z + 0.0006)
        o.rotation_euler.z += math.radians(giro + random.uniform(-8, 8))
        o.name = apelido
        pos[apelido] = o

    # dados
    ouro = mat_simples("ouro", (1.0, 0.74, 0.32), rough=0.22, metal=1.0)
    rubi = mat_resina("resina_rubi", (1.0, 0.82, 0.82), (0.85, 0.06, 0.08), 38.0)
    ametista = mat_resina("resina_ametista", (0.92, 0.85, 1.0), (0.45, 0.12, 0.85), 34.0)
    marfim = mat_simples("marfim", (0.93, 0.88, 0.78), rough=0.32, **{"Subsurface Weight|Subsurface": 0.15})
    pinta = mat_simples("pinta", (0.02, 0.015, 0.012), rough=0.5)
    pos["d20"] = d20("d20_rubi", 0.0115, rubi, ouro, (-0.16, -0.37), 0.4)
    pos["d20b"] = d20("d20_ametista", 0.0115, ametista, ouro, (0.04, -0.42), 1.9)
    d6("d6_a", 0.016, marfim, pinta, (-0.31, -0.40), 0.5, cima=6)
    d6("d6_b", 0.016, marfim, pinta, (-0.255, -0.455), 1.2, cima=4)

    # moedas espalhadas na frente do bau
    moeda_me = None
    for i in range(16):
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.0105, depth=0.0022)
        mo = bpy.context.active_object
        mo.data.materials.append(ouro)
        mo.location = (-0.60 + random.uniform(-0.09, 0.12), 0.06 + random.uniform(-0.08, 0.07), 0.0011 + 0.0022 * (i % 3 == 0))
        mo.rotation_euler = (random.uniform(-0.12, 0.12), random.uniform(-0.12, 0.12), random.uniform(0, 6.3))

    # bau, caliceis, caderno, lanterna, castiçais
    posicionar(importar("treasure_chest"), (-0.70, 0.30), rot_z=24, escala=0.34)
    gob = importar("brass_goblets", pegar=["brass_goblet_01", "brass_goblet_03"])
    posicionar([gob[0]], (-0.40, 0.42), rot_z=10, escala=0.72)
    posicionar([gob[1]], (-0.30, 0.52), rot_z=40, escala=0.72)
    posicionar(importar("binder_notebook", pegar=["binder_notebook"]), (0.55, -0.27), rot_z=-14, escala=1.0)
    lant = importar("Lantern_01")
    posicionar(lant, (0.40, 0.48), rot_z=-20, escala=1.0)
    lo, hi = caixa_mundo(lant)
    luz("lanterna", ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + (hi.z - lo.z) * 0.38), 7.0, (1.0, 0.62, 0.30), 0.012)

    cera = mat_simples("cera", (0.94, 0.89, 0.78), rough=0.45, **{"Subsurface Weight|Subsurface": 0.6})
    chama = mat_emissao("chama", (1.0, 0.56, 0.18), 40.0)
    pos["chamas"] = []
    for nome, centro, giro in [("brass_candleholder_01", (0.66, 0.30), 0), ("brass_candleholder_02", (0.92, 0.10), 30)]:
        obj = importar("brass_candleholders", pegar=[nome])
        posicionar(obj, centro, rot_z=giro)
        for topo in topos_dos_copinhos(obj[0]):
            h = random.uniform(0.09, 0.14)
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.0105, depth=h, location=(topo.x, topo.y, topo.z + h / 2 - 0.004))
            bpy.context.active_object.data.materials.append(cera)
            pf = Vector((topo.x, topo.y, topo.z + h + 0.012))
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.006, location=pf)
            fl = bpy.context.active_object
            fl.scale = (0.75, 0.75, 1.9)
            fl.data.materials.append(chama)
            fl.visible_shadow = False
            luz("vela", (pf.x, pf.y, pf.z + 0.004), 5.0, (1.0, 0.58, 0.24), 0.004)
            pos["chamas"].append(fl)

    # velinhas de rechaud na mesa: viram bolas de luz desfocadas atras dos dados
    aluminio = mat_simples("aluminio", (0.86, 0.87, 0.89), rough=0.28, metal=1.0)
    for tx, ty in [(0.52, 0.16), (0.61, -0.03), (0.46, 0.33), (-0.44, 0.19), (-0.38, 0.27)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.019, depth=0.016, location=(tx, ty, 0.008))
        bpy.context.active_object.data.materials.append(aluminio)
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.0175, depth=0.002, location=(tx, ty, 0.0152))
        bpy.context.active_object.data.materials.append(cera)
        pf = Vector((tx, ty, 0.026))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.004, location=pf)
        fl = bpy.context.active_object
        fl.scale = (0.7, 0.7, 1.8)
        fl.data.materials.append(chama)
        fl.visible_shadow = False
        luz("velinha", (tx, ty, 0.031), 2.2, (1.0, 0.55, 0.22), 0.003)
        pos["chamas"].append(fl)

    # luz de cinema: chave quente suave, recorte frio por tras
    area("chave", (-1.1, -0.9, 1.5), (0, 0, 0), 14, 1.2, (1.0, 0.78, 0.58))
    area("recorte", (0.9, 1.4, 0.55), (0, 0.1, 0.05), 25, 0.6, (0.50, 0.62, 1.0))
    mundo_hdri("warm_restaurant_night", 0.16, rot_z=math.radians(150))
    return pos


def topos_dos_copinhos(obj):
    """Centros dos copinhos onde vao as velas: vertices mais altos do castical, agrupados."""
    mw = obj.matrix_world
    pts = [mw @ v.co for v in obj.data.vertices]
    zmax = max(p.z for p in pts)
    altos = [p for p in pts if p.z > zmax - 0.012]
    grupos = []
    for p in sorted(altos, key=lambda q: q.x):
        if grupos and (p.xy - grupos[-1][-1].xy).length < 0.07:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    return [Vector((sum(q.x for q in g) / len(g), sum(q.y for q in g) / len(g), zmax)) for g in grupos]


def luz(nome, local, watts, cor, raio):
    l = bpy.data.lights.new(nome, "POINT")
    l.energy, l.color, l.shadow_soft_size = watts, cor, raio
    o = bpy.data.objects.new(nome, l)
    bpy.context.scene.collection.objects.link(o)
    o.location = local
    return o


def area(nome, local, alvo, watts, tamanho, cor):
    l = bpy.data.lights.new(nome, "AREA")
    l.energy, l.size, l.color = watts, tamanho, cor
    o = bpy.data.objects.new(nome, l)
    bpy.context.scene.collection.objects.link(o)
    o.location = local
    o.rotation_euler = (Vector(alvo) - Vector(local)).to_track_quat("-Z", "Y").to_euler()
    return o


def mundo_hdri(nome, forca, rot_z=0.0):
    cena = bpy.context.scene
    w = cena.world or bpy.data.worlds.new("mundo")
    cena.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    nos, ln = w.node_tree.nodes, w.node_tree.links
    for n in list(nos):
        if n.type not in ("BACKGROUND", "OUTPUT_WORLD"):
            nos.remove(n)
    fundo = next(n for n in nos if n.type == "BACKGROUND")
    hdr = next(f for f in os.listdir(os.path.join(PH, nome)) if f.endswith(".hdr"))
    env = nos.new("ShaderNodeTexEnvironment")
    env.image = imagem(os.path.join(PH, nome, hdr))
    coord, mp = nos.new("ShaderNodeTexCoord"), nos.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, rot_z)
    ln.new(coord.outputs["Generated"], mp.inputs["Vector"])
    ln.new(mp.outputs["Vector"], env.inputs["Vector"])
    ln.new(env.outputs["Color"], fundo.inputs["Color"])
    fundo.inputs["Strength"].default_value = forca


# ---------------------------------------------------------------- render

def configurar(amostras, exposicao=0.0):
    c = bpy.context.scene
    c.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for tipo in ("CUDA", "OPTIX"):
        try:
            prefs.compute_device_type = tipo
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == tipo for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == tipo
            break
    c.cycles.device = "GPU" if any(d.use for d in prefs.devices) else "CPU"
    c.cycles.samples = 16 if PREVIA else amostras
    c.cycles.use_adaptive_sampling = True
    c.cycles.adaptive_threshold = 0.02
    c.cycles.use_denoising = True
    try:
        c.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    c.cycles.max_bounces, c.cycles.transmission_bounces, c.cycles.volume_bounces = 12, 12, 2
    c.cycles.caustics_reflective = c.cycles.caustics_refractive = False
    c.render.resolution_x, c.render.resolution_y = RES
    c.render.resolution_percentage = 25 if PREVIA else 100
    c.render.film_transparent = False
    c.render.image_settings.file_format = "PNG"
    c.render.image_settings.color_mode = "RGB"
    c.render.image_settings.color_depth = "8"
    for vt in ("AgX", "Filmic"):
        try:
            c.view_settings.view_transform = vt
            break
        except TypeError:
            continue
    looks = [i.identifier for i in c.view_settings.bl_rna.properties["look"].enum_items]
    look = next((l for l in looks if "Medium High Contrast" in l), "None")
    c.view_settings.look = look
    c.view_settings.exposure = exposicao
    bpy.context.view_layer.material_override = None


def camera(local, alvo, lente, fstop=None, foco=None):
    c = bpy.context.scene
    cam = c.camera
    if cam is None:
        cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
        c.collection.objects.link(cam)
        c.camera = cam
    cam.data.type = "PERSP"
    cam.data.sensor_width = 36
    cam.location = local
    cam.rotation_euler = (Vector(alvo) - Vector(local)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lente
    cam.data.dof.use_dof = fstop is not None
    if fstop is not None:
        cam.data.dof.aperture_fstop = fstop
        if isinstance(foco, bpy.types.Object):
            cam.data.dof.focus_object = foco
        else:
            cam.data.dof.focus_object = None
            cam.data.dof.focus_distance = (Vector(foco or alvo) - Vector(local)).length
    bpy.context.view_layer.update()
    return cam


def renderizar(nome):
    c = bpy.context.scene
    c.render.filepath = os.path.join(OUT, nome + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", nome, flush=True)


def renderizar_profundidade(nome, perto, longe):
    """Profundidade como imagem: emissao = distancia da camera mapeada em perto..longe (claro = perto)."""
    c = bpy.context.scene
    m, nos, ln, b = novo_material("profundidade")
    for n in list(nos):
        if n.type != "OUTPUT_MATERIAL":
            nos.remove(n)
    cd, mr, em = nos.new("ShaderNodeCameraData"), nos.new("ShaderNodeMapRange"), nos.new("ShaderNodeEmission")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = perto, longe
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0
    ln.new(cd.outputs["View Distance"], mr.inputs["Value"])
    ln.new(mr.outputs["Result"], em.inputs["Color"])
    ln.new(em.outputs[0], next(n for n in nos if n.type == "OUTPUT_MATERIAL").inputs["Surface"])
    vl = bpy.context.view_layer
    vl.material_override = m
    luzes = [o for o in c.objects if o.type == "LIGHT"]
    for o in luzes:
        o.hide_render = True
    forca_mundo = c.world.node_tree.nodes["Background"].inputs["Strength"].default_value
    c.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    dof = c.camera.data.dof.use_dof
    c.camera.data.dof.use_dof = False
    vt, look, amostras, den = c.view_settings.view_transform, c.view_settings.look, c.cycles.samples, c.cycles.use_denoising
    c.view_settings.view_transform, c.view_settings.look = "Standard", "None"
    c.cycles.samples, c.cycles.use_denoising = 8, False
    c.render.image_settings.color_mode, c.render.image_settings.color_depth = "BW", "16"
    renderizar(nome + "_prof")
    c.render.image_settings.color_mode, c.render.image_settings.color_depth = "RGB", "8"
    c.view_settings.view_transform, c.view_settings.look = vt, look
    c.cycles.samples, c.cycles.use_denoising = amostras, den
    c.camera.data.dof.use_dof = dof
    c.world.node_tree.nodes["Background"].inputs["Strength"].default_value = forca_mundo
    for o in luzes:
        o.hide_render = False
    vl.material_override = None


def pixels(objs):
    c = bpy.context.scene
    w = c.render.resolution_x * c.render.resolution_percentage / 100
    h = c.render.resolution_y * c.render.resolution_percentage / 100
    out = {}
    for nome, o in objs.items():
        if isinstance(o, list):
            continue
        lo, hi = caixa_mundo([o] + list(o.children_recursive))
        base = world_to_camera_view(c, c.camera, Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)))
        topo = world_to_camera_view(c, c.camera, Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z)))
        out[nome] = {"base": [base.x * w, (1 - base.y) * h], "topo": [topo.x * w, (1 - topo.y) * h]}
    return out


def mascara(nome, so_estes):
    """Alfa so dos objetos pedidos (para o compositor desenhar efeitos atras deles)."""
    c = bpy.context.scene
    escondidos = [o for o in c.objects if o.type in ("MESH", "CURVE", "FONT") and o not in so_estes and not o.hide_render]
    for o in escondidos:
        o.hide_render = True
    c.render.film_transparent = True
    c.render.image_settings.color_mode = "RGBA"
    dof = c.camera.data.dof.use_dof
    c.camera.data.dof.use_dof = False
    amostras = c.cycles.samples
    c.cycles.samples = 8
    renderizar(nome)
    c.cycles.samples = amostras
    c.camera.data.dof.use_dof = dof
    c.render.image_settings.color_mode = "RGB"
    c.render.film_transparent = False
    for o in escondidos:
        o.hide_render = False


def tomadas_mesa(pos):
    quais = TOMADAS or ["d20", "mesa", "mapa", "final", "diario"]
    posicoes = {}
    if "d20" in quais:
        configurar(192, exposicao=-0.2)
        d = pos["d20"].location
        v = Vector((-0.63, 0.78, 0.0))                # do dado para o bau e os calices
        cam_pos = d - v * 0.24 + Vector((0, 0, 0.05))
        frente = d + (cam_pos - d).normalized() * 0.0095  # foco na face da frente, nao no centro do dado
        camera(cam_pos, d + Vector((0, 0, 0.002)), 100, fstop=5.0, foco=frente)
        renderizar("d20")
        renderizar_profundidade("d20", 0.15, 1.8)
    if "mesa" in quais:
        configurar(160)
        camera((0.05, -1.25, 0.62), (0.0, 0.05, 0.0), 30, fstop=2.8, foco=(0, -0.05, 0))
        renderizar("mesa")
        renderizar_profundidade("mesa", 0.6, 3.5)
        posicoes["mesa"] = pixels({k: v for k, v in pos.items()})
    if "mapa" in quais:
        configurar(128, exposicao=0.25)
        camera((0.0, -0.02, 1.02), (0.0, 0.0, 0.0), 42, fstop=11.0, foco=(0, 0, 0))
        renderizar("mapa")
        renderizar_profundidade("mapa", 0.85, 1.15)
        posicoes["mapa"] = pixels({k: v for k, v in pos.items()})
        mascara("mascara_kael", [pos["kael"]] + list(pos["kael"].children_recursive))
    if "final" in quais:
        configurar(192, exposicao=-0.2)
        d = pos["d20"].location
        v = Vector((0.77, 0.63, 0.0))                 # da camera para as velas, passando pelo dado
        esq = Vector((-0.63, 0.77, 0.0))
        camera(d - v * 0.28 + Vector((0, 0, 0.03)), d + v * 0.10 + esq * 0.03, 85, fstop=2.0, foco=pos["d20"])
        renderizar("final")
        renderizar_profundidade("final", 0.15, 2.5)
        posicoes["final"] = pixels({"d20": pos["d20"]})
    if "diario" in quais:
        configurar(160)
        camera((0.86, -0.58, 0.34), (0.56, -0.26, 0.02), 50, fstop=2.8, foco=(0.55, -0.27, 0.02))
        renderizar("diario")
        renderizar_profundidade("diario", 0.25, 2.5)
    arq = os.path.join(OUT, "posicoes.json")
    antigo = json.load(open(arq, encoding="utf-8")) if os.path.exists(arq) else {}
    antigo.update(posicoes)
    json.dump(antigo, open(arq, "w", encoding="utf-8"), indent=1)


def tomadas_hdri():
    """Fotos reais (HDRIs CC0 da Poly Haven) vistas por uma camera comum."""
    vistas = {"ceu": ("rogland_clear_night", -85, 22, 18, -1.6), "rua": ("cobblestone_street_night", -52, 6, 28, -0.6),
              "torre": ("smelting_tower_interior", 180, 4, 22, -0.4), "taverna": ("warm_restaurant_night", 120, 2, 26, -0.4)}
    for nome, (hdri, yaw, pitch, lente, ev) in vistas.items():
        if TOMADAS and nome not in TOMADAS:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mundo_hdri(hdri, 1.0)
        configurar(24, exposicao=ev)
        c = bpy.context.scene
        c.cycles.use_denoising = False
        cam = camera((0, 0, 0), (0, 1, 0), lente)
        cam.rotation_euler = (math.radians(90 + pitch), 0, math.radians(yaw))
        renderizar(nome)


if not TOMADAS or set(TOMADAS) & {"d20", "mesa", "mapa", "final", "diario"}:
    tomadas_mesa(montar_mesa())
if not TOMADAS or set(TOMADAS) & {"ceu", "rua", "torre", "taverna"}:
    tomadas_hdri()
print("PRONTO", flush=True)
