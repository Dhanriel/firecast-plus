"""Baixa da Poly Haven (tudo CC0) os HDRIs, a textura e os modelos usados no trailer 3.

  python -I trailer3/baixar_assets.py

Cada asset vai para a sua propria pasta em trailer3/assets/polyhaven/<id>/. Arquivo que ja existe com o
tamanho certo nao e baixado de novo.
"""
import json, os, sys, urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(AQUI, "assets", "polyhaven")
UA = {"User-Agent": "firecast-plus-trailer/1.0"}

HDRIS = {"warm_restaurant_night": "4k", "rogland_clear_night": "8k", "cobblestone_street_night": "4k",
         "smelting_tower_interior": "4k"}
TEXTURAS = {"dark_wood": "2k"}
MODELOS = {"treasure_chest": "2k", "brass_candleholders": "1k", "brass_goblets": "2k", "binder_notebook": "2k",
           "Lantern_01": "2k", "chess_set": "2k"}


def api(caminho):
    return json.load(urllib.request.urlopen(urllib.request.Request("https://api.polyhaven.com/" + caminho, headers=UA), timeout=60))


def baixar(url, arquivo, tamanho):
    if os.path.exists(arquivo) and os.path.getsize(arquivo) == tamanho:
        return
    os.makedirs(os.path.dirname(arquivo), exist_ok=True)
    tmp = arquivo + ".parcial"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
    if os.path.getsize(tmp) != tamanho:
        os.remove(tmp)
        raise RuntimeError(f"tamanho errado em {url}")
    os.replace(tmp, arquivo)
    print("ok", os.path.relpath(arquivo, DESTINO), round(tamanho / 1e6, 1), "MB", flush=True)


def main():
    for a, res in HDRIS.items():
        d = api(f"files/{a}")["hdri"][res]["hdr"]
        baixar(d["url"], os.path.join(DESTINO, a, f"{a}_{res}.hdr"), d["size"])
    for a, res in TEXTURAS.items():
        f = api(f"files/{a}")
        for mapa in ("Diffuse", "nor_gl", "Rough"):
            d = f[mapa][res]["jpg"] if "jpg" in f[mapa][res] else f[mapa][res]["png"]
            baixar(d["url"], os.path.join(DESTINO, a, os.path.basename(d["url"])), d["size"])
    for a, res in MODELOS.items():
        g = api(f"files/{a}")["gltf"][res]["gltf"]
        pasta = os.path.join(DESTINO, a)
        baixar(g["url"], os.path.join(pasta, os.path.basename(g["url"])), g["size"])
        for rel, inc in g.get("include", {}).items():  # texturas e .bin no caminho relativo que o .gltf espera
            if ".." in rel.replace("\\", "/").split("/"):
                raise RuntimeError(f"caminho suspeito em {a}: {rel}")
            baixar(inc["url"], os.path.join(pasta, *rel.split("/")), inc["size"])
    print("tudo baixado em", DESTINO)


if __name__ == "__main__":
    sys.exit(main())
