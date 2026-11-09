"""Texturas desenhadas por codigo para a cena 3D do trailer 3.

  python trailer3/texturas.py   -> trailer3/assets/gerados/mapa.png (mapa de batalha em pergaminho)
"""
import math, os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "assets", "gerados")
W, H = 3072, 2048          # 0.9 m x 0.6 m na mesa
GRADE = 128                # uma casa = 128 px (~3.75 cm, como uma miniatura de 1 polegada e meia)
FONTES = os.path.join(os.environ["WINDIR"], "Fonts")


def ruido(w, h, escala, semente, oitavas=5):
    """Ruido fractal suave em [0, 1]."""
    rng = np.random.default_rng(semente)
    soma, amp, total = np.zeros((h, w), np.float32), 1.0, 0.0
    for o in range(oitavas):
        gw, gh = max(2, int(w / escala * 2 ** o)), max(2, int(h / escala * 2 ** o))
        g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        soma += amp * np.asarray(g, np.float32) / 255
        total += amp
        amp *= 0.5
    soma /= total
    return (soma - soma.min()) / (soma.max() - soma.min() + 1e-6)


def mistura(base, cor, mascara):
    m = mascara[..., None]
    return base * (1 - m) + np.array(cor, np.float32)[None, None, :] * m


def mapa():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    n1, n2, n3 = ruido(W, H, 900, 1), ruido(W, H, 250, 2), ruido(W, H, 60, 3, 3)

    # pergaminho: bege com manchas e bordas queimadas
    papel = np.array([214, 190, 146], np.float32)
    img = papel[None, None, :] * (0.86 + 0.18 * n1[..., None]) - 22 * (n3[..., None] - 0.5)
    borda = np.minimum.reduce([x, W - x, y, H - y]) / 220
    queimado = np.clip(1 - borda + (n2 - 0.5) * 0.9, 0, 1) ** 2
    img = mistura(img, (92, 60, 32), queimado * 0.85)

    # terreno: grama clara, floresta escura em manchas, rio serpenteando, rochas
    grama = np.clip((n1 - 0.30) * 2.2, 0, 1) * 0.35
    img = mistura(img, (148, 160, 96), grama)
    floresta = np.clip((ruido(W, H, 380, 4) - 0.58) * 6, 0, 1) * np.clip((W * 0.46 - x) / (W * 0.10), 0, 1)
    img = mistura(img, (70, 92, 54), floresta * 0.75)
    rio_x = W * 0.70 + 180 * np.sin(y / 260) + 90 * np.sin(y / 97 + 1.3)
    largura = 70 + 25 * np.sin(y / 180)
    rio = np.clip(1 - np.abs(x - rio_x) / largura, 0, 1) ** 0.6
    img = mistura(img, (74, 112, 138), rio * 0.85)
    img = mistura(img, (52, 82, 110), np.clip(1 - np.abs(x - rio_x) / (largura * 0.45), 0, 1) * 0.6)
    rochas = np.clip((ruido(W, H, 140, 5) - 0.70) * 8, 0, 1) * (y > H * 0.62) * (x > W * 0.30) * (x < W * 0.62)
    img = mistura(img, (132, 124, 112), rochas * 0.7)

    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im, "RGBA")
    rng = np.random.default_rng(9)

    # arvores em tinta: copa redonda com sombra, so dentro das manchas de floresta
    for _ in range(420):
        px, py = int(rng.uniform(80, W * 0.42)), int(rng.uniform(80, H - 80))
        if floresta[py, px] < 0.5:
            continue
        r = int(rng.uniform(22, 40))
        d.ellipse((px - r + 6, py - r + 8, px + r + 6, py + r + 8), fill=(40, 52, 30, 110))
        d.ellipse((px - r, py - r, px + r, py + r), fill=(78, 104, 58, 255), outline=(38, 46, 28, 255), width=3)
        d.arc((px - r * 0.6, py - r * 0.6, px + r * 0.3, py + r * 0.3), 200, 300, fill=(120, 146, 88, 255), width=3)

    # ruinas: muros de pedra em L e uma torre redonda (cada bloco alinhado a grade)
    def muro(c0, l0, c1, l1):
        x0, y0, x1, y1 = c0 * GRADE, l0 * GRADE, c1 * GRADE, l1 * GRADE
        d.rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), fill=(50, 40, 30, 120))
        d.rectangle((x0, y0, x1, y1), fill=(150, 142, 128, 255), outline=(60, 54, 46, 255), width=4)
        for k in range(int((x1 - x0) / 40) + 1):  # juntas das pedras
            d.line((x0 + 40 * k, y0, x0 + 40 * k, y1), fill=(96, 88, 76, 255), width=2)
    muro(11, 5, 16, 5.35)
    muro(11, 5, 11.35, 9)
    muro(14, 9, 17, 9.35)
    cx, cy, r = 15.5 * GRADE, 7 * GRADE, 0.9 * GRADE
    d.ellipse((cx - r + 8, cy - r + 10, cx + r + 8, cy + r + 10), fill=(50, 40, 30, 120))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(158, 150, 134, 255), outline=(60, 54, 46, 255), width=5)
    d.ellipse((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), outline=(90, 82, 70, 255), width=4)

    # estrada pontilhada e ponte sobre o rio
    pts = [(0, H * 0.78), (W * 0.25, H * 0.72), (W * 0.45, H * 0.80), (W * 0.62, H * 0.68), (W * 0.9, H * 0.55), (W, H * 0.5)]
    for (a, b), (c, e) in zip(pts, pts[1:]):
        n = int(math.hypot(c - a, e - b) / 36)
        for k in range(n):
            if k % 2 == 0:
                t0, t1 = k / n, (k + 0.6) / n
                d.line((a + (c - a) * t0, b + (e - b) * t0, a + (c - a) * t1, b + (e - b) * t1), fill=(110, 78, 44, 230), width=9)
    py = int(H * 0.62)
    px = int(W * 0.70 + 180 * math.sin(py / 260) + 90 * math.sin(py / 97 + 1.3))
    d.rectangle((px - 160, py - 34, px + 160, py + 34), fill=(132, 96, 58, 255), outline=(70, 48, 28, 255), width=4)
    for k in range(-150, 160, 30):
        d.line((px + k, py - 34, px + k, py + 34), fill=(88, 62, 36, 255), width=3)

    # grade de batalha
    for gx in range(0, W, GRADE):
        d.line((gx, 0, gx, H), fill=(60, 44, 28, 70), width=3)
    for gy in range(0, H, GRADE):
        d.line((0, gy, W, gy), fill=(60, 44, 28, 70), width=3)

    # rosa dos ventos e titulo em tinta
    cx, cy = W - 300, 300
    for ang, comp in [(0, 170), (90, 120), (180, 120), (270, 120), (45, 70), (135, 70), (225, 70), (315, 70)]:
        a = math.radians(ang - 90)
        tip = (cx + comp * math.cos(a), cy + comp * math.sin(a))
        l = (cx + 24 * math.cos(a + 1.57), cy + 24 * math.sin(a + 1.57))
        r_ = (cx + 24 * math.cos(a - 1.57), cy + 24 * math.sin(a - 1.57))
        d.polygon([tip, l, (cx, cy)], fill=(60, 40, 24, 255))
        d.polygon([tip, r_, (cx, cy)], fill=(170, 130, 80, 255), outline=(60, 40, 24, 255))
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), outline=(60, 40, 24, 255), width=5)
    fonte = ImageFont.truetype(os.path.join(FONTES, "georgiaz.ttf"), 64)
    d.text((cx - 18, cy - 250), "N", font=fonte, fill=(60, 40, 24, 255))
    titulo = ImageFont.truetype(os.path.join(FONTES, "georgiaz.ttf"), 120)
    d.text((170, 120), "Ruínas de Avalon", font=titulo, fill=(58, 36, 20, 235))

    # envelhece tudo: um pouco de desfoque e manchas de cafe por cima
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    arr = np.asarray(im, np.float32)
    manchas = np.clip((ruido(W, H, 300, 7) - 0.62) * 4, 0, 1)
    arr[..., :3] = mistura(arr[..., :3], (120, 86, 48), manchas * 0.35)
    os.makedirs(SAIDA, exist_ok=True)
    caminho = os.path.join(SAIDA, "mapa.png")
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB").save(caminho)
    print(caminho)


if __name__ == "__main__":
    mapa()
