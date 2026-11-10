import fcplus

pal = fcplus.carregar_paleta()

# base igual ao original nao muda nenhuma cor (tolerancia de arredondamento)
same = fcplus.derivar(pal, {"destaque": "#EB3449", "fundo": "#212121", "texto": "#F2F2F2"})
for k, v in same.items():
    o = fcplus.resolver(pal, pal[k])
    assert all(abs(int(v[i:i + 2], 16) - int(o[i:i + 2], 16)) <= 2 for i in (1, 3, 5)), (k, o, v)

# base nova muda a familia toda e mantem o formato #RRGGBB
roxo = fcplus.derivar(pal, {"destaque": "#9F34EB"})
assert roxo["color1"] == "#9F34EB" and len(roxo) > 10
assert all(len(v) == 7 and v.startswith("#") for v in roxo.values())

# fonte e tamanho do chat: sem troca, os binarios saem identicos; com troca, continuam legiveis
import re, zipfile as _z

with _z.ZipFile(fcplus.original()) as z:
    xml, sty = z.read(fcplus.PALETA), z.read("precompiled/themes/flat.style")
assert fcplus.fontes_xml(xml, None, 0) == xml and fcplus.fontes_style(sty, None) == sty
x2 = fcplus.fontes_xml(xml, "Comic Sans MS", 4)
assert fcplus.fontes_xml(x2, None, 0) == x2  # le de ponta a ponta de novo
assert b"\x06\x06Roboto" not in x2 and x2.count(b"\x06\x0dComic Sans MS") == xml.count(b"\x06\x06Roboto") + xml.count(b"\x06\x04Lato")
i = x2.index(b"\x06\x10logRichEditStyle\x06\x10logRichEditStyle")
assert b"\x06\x08fontSize\x06\x0218" in x2[i:i + 2000]  # 14 + 4
s2 = fcplus.fontes_style(sty, "Comic Sans MS")
assert fcplus.fontes_style(s2, None) == s2 and b"Roboto" not in s2 and b"Lato" not in s2

# instalador: a base (o download) nao tem nada do Firecast; o instalar.ps1 completa e chega ao mesmo plugin do Python
import hashlib, os, subprocess, tempfile as _t

base = fcplus.build_plugin(instalar=False)
with _z.ZipFile(base) as z:
    nomes_base = set(z.namelist())
assert not any(n.startswith("sdk/") or n.startswith("sons/") or n == "_rdkCompiledLang.cln" for n in nomes_base)
esperado = {n: d for n, d in fcplus.arquivos_do_firecast().items()}
with _z.ZipFile(base) as z:
    esperado.update({n: z.read(n) for n in z.namelist()})
digest = hashlib.sha1(b"".join(esperado[k] for k in sorted(esperado))).hexdigest()
saida = os.path.join(_t.mkdtemp(), "p.rpk")
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(fcplus.HERE, "instalar.ps1"),
                    "-Base", base, "-Destino", saida], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
with _z.ZipFile(saida) as z:
    assert set(z.namelist()) == set(esperado)
    assert all(z.read(n) == d for n, d in esperado.items() if n != "module.xml")
    assert f'compilationDigest="{digest}"' in z.read("module.xml").decode()

# atualizacao do Firecast: numa copia, o resource.zip muda -> vira o novo original e a skin volta sozinha
import os, shutil, tempfile, zipfile

tmp = tempfile.mkdtemp()
original_real = fcplus.original()
fcplus.RES, fcplus.BAK, fcplus.ESTADO = (os.path.join(tmp, n) for n in ("resource.zip", "resource.zip.original", "estado.json"))
shutil.copyfile(original_real, fcplus.RES)
assert fcplus.verificar_atualizacao(False, lambda: True) == "sem estado"
fcplus.aplicar({"nome": "teste", "base": {"destaque": "#9F34EB"}})
assert fcplus.verificar_atualizacao(False, lambda: True) == "ok"

shutil.copyfile(original_real, fcplus.RES)  # "atualizacao": um original novo, com um arquivo a mais
with zipfile.ZipFile(fcplus.RES, "a") as z:
    z.writestr("novo_na_versao.txt", "x")
assert fcplus.verificar_atualizacao(True, lambda: False) == "adiado"  # Firecast aberto e o usuario disse nao
assert fcplus.verificar_atualizacao(False, lambda: True) == "reaplicada"
with zipfile.ZipFile(fcplus.BAK) as z:
    assert "novo_na_versao.txt" in z.namelist()  # backup e o original novo
with zipfile.ZipFile(fcplus.RES) as z:
    assert "novo_na_versao.txt" in z.namelist()
    assert b"9F34EB" in z.read("precompiled/themes/flat/frames/buttons/actionButton.xml").upper()
assert fcplus.verificar_atualizacao(False, lambda: True) == "ok"

# skin com arquivos (Cyberpunk), do jeito que a janela /cores pede: cores da janela + cores extras e arquivos da skin
import xml.dom.minidom

cfg = fcplus.cfg_do_pedido({"acao": "aplicar", "destaque": "#00FF00FF", "fundo": "#000000", "texto": "#B8F6ED",
                            "fonte": "Roboto", "tamanho_chat": 14, "skin": "cyberpunk"})
assert cfg["base"]["destaque"] == "#00FF00" and cfg["fonte"] == "Roboto" and cfg["cores"]["online_state_color"] == "#55EAD4"  # a base e a da janela
fcplus.aplicar(cfg)
skin_dir = os.path.join(fcplus.HERE, "skins", "cyberpunk")
with zipfile.ZipFile(original_real) as z:
    antes = set(z.namelist())
with zipfile.ZipFile(fcplus.RES) as z:
    nomes = z.namelist()
    assert z.testzip() is None and len(nomes) == len(set(nomes))
    assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())  # o Firecast guarda tudo sem compressao
    pre = "precompiled/themes/flat/frames/chat/logRichEdit.xml"  # sem o precompilado, o Firecast le o XML
    assert set(nomes) == (antes | {"novo_na_versao.txt", "themes/flat/frames/chat/fcplus_chat.png"}) - {pre}
    frame = xml.dom.minidom.parseString(z.read("themes/flat/frames/chat/logRichEdit.xml"))
    fonte_img = frame.getElementsByTagName("image")[0].getElementsByTagName("source")[0].getAttribute("url")
    assert z.read("themes/flat/frames/chat/" + fonte_img) == open(os.path.join(skin_dir, "chat.png"), "rb").read()
    for i, n in enumerate(("login1", "login2", "login1", "login2"), 1):
        assert z.read(f"themes/flat/frames/disconnectedForm/backgrounds/bkg{i}.jpg") == open(os.path.join(skin_dir, n + ".jpg"), "rb").read()
    pal2 = fcplus.ler_paleta(z.read(fcplus.PALETA))
    assert pal2["color1"] == "#00FF00" and pal2["online_state_color"] == "#55EAD4"
    with zipfile.ZipFile(original_real) as zo:  # hash novo: senao o Firecast reusa o frame em cache
        assert z.read(".cache_hash") != zo.read(".cache_hash") and len(z.read(".cache_hash")) == len(zo.read(".cache_hash"))
assert fcplus.verificar_atualizacao(False, lambda: True) == "ok"
shutil.copyfile(original_real, fcplus.RES)  # outra "atualizacao": a skin com arquivos tambem volta sozinha
assert fcplus.verificar_atualizacao(False, lambda: True) == "reaplicada"
with zipfile.ZipFile(fcplus.RES) as z:
    assert "themes/flat/frames/chat/fcplus_chat.png" in z.namelist() and pre not in z.namelist()
for ruim in ("../roxo", "Cyberpunk", "a b"):  # o nome da skin vira nome de arquivo
    try:
        fcplus.cfg_do_pedido({"skin": ruim})
        raise AssertionError(ruim)
    except ValueError:
        pass
assert "arquivos" not in fcplus.cfg_do_pedido({"destaque": "#112233"})
# o seletor do Firecast manda nome em vez de hex nas cores com nome (o preto da Cyberpunk chegou como "Black")
assert fcplus.cfg_do_pedido({"fundo": "Black", "texto": "White", "destaque": "#c5003cff"})["base"] == {
    "destaque": "#C5003C", "fundo": "#000000", "texto": "#FFFFFF"}
shutil.rmtree(tmp)
print("ok", len(same), "cores; atualizacao reaplica a skin")
