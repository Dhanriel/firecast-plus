"""Gera a aura animada (branca, o mapa tinge com colorMask) em plugin/auras/chamas.gif.

  python gerar_aura.py   -> plugin/auras/chamas.gif e dist/previa_aura_roxa.gif (so para conferir)

Estilo de aura de anime: um leque de chamas que nasce embaixo do token e sobe em pontas finas,
com faixas de energia correndo de baixo para cima e um brilho forte colado no corpo.
GIF so tem transparencia liga/desliga: a borda suave vira pontilhado (dither).
O plugin precisa das medidas abaixo (TOKEN_*) para centralizar o token no buraco da aura.
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, N = 256, 400, 14          # largura, altura e quadros do loop
TOKEN_CX, TOKEN_CY = 0.5, 0.68  # centro do token, em fracao de W e H
TOKEN_R = 0.17                  # raio do token, em fracao de W


def quadros():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy, rt = TOKEN_CX * W, TOKEN_CY * H, TOKEN_R * W
    ox, oy = cx, cy + rt * 0.9                     # as chamas nascem embaixo do token
    dx, dy = (x - ox) / W, (oy - y) / W            # dy positivo = para cima
    rho = np.sqrt(dx ** 2 + dy ** 2)
    phi = np.arctan2(dx, dy)                       # 0 = reto para cima
    r_tok = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / rt

    borda = np.minimum.reduce([x, W - 1 - x, y, H - 1 - y])
    some_na_borda = np.clip(borda / 24, 0, 1)      # raios longos somem antes de serem cortados pela borda
    leque = np.clip(np.cos(np.clip(phi * 0.95, -1.55, 1.55)), 0, 1) ** 1.4  # mais alto no meio
    rng = np.random.default_rng(11)
    # pontas: picos estreitos no angulo; frequencias inteiras no tempo => loop sem emenda
    pontas = [(m, rng.uniform(0, 6.3), j, w) for m, j, w in [(9, 1, 1.0), (14, 2, 0.8), (23, 3, 0.6), (37, 4, 0.4)]]
    for k in range(N):
        t = k / N
        pico = np.zeros_like(rho)
        for m, fi, j, w in pontas:
            pico += w * (0.5 + 0.5 * np.sin(m * phi + fi + 2 * np.pi * j * t)) ** 6
        pico /= sum(p[3] for p in pontas)
        comprimento = (0.26 + 0.70 * leque) * (0.68 + 0.62 * pico)       # ate onde cada raio chega
        ao_longo = np.clip(1 - rho / np.maximum(comprimento, 1e-3), 0, 1)
        # faixas de energia correndo para cima ao longo dos raios
        faixa = 0.5 + 0.5 * np.sin(2 * np.pi * (7 * rho - 2 * t) + 9 * phi + 2 * np.sin(2 * np.pi * t + 5 * phi))
        corpo = (dy > -0.02) | (rho < 0.12)        # nada abaixo do ponto de onde as chamas nascem
        chama = ao_longo ** 0.8 * (0.55 + 0.45 * faixa) * corpo
        halo = np.exp(-((r_tok - 1.0) / 0.35) ** 2) * 0.9      # brilho colado no token
        alfa = np.clip(np.maximum(chama * 1.25, halo * (dy > -0.12)), 0, 1)
        alfa *= np.clip((r_tok - 0.75) / 0.2, 0, 1) * some_na_borda  # o meio fica vazio (o token cobre)
        brilho = np.clip(0.5 + 0.5 * np.maximum(ao_longo, halo), 0, 1)
        yield alfa, brilho


def rgba(alfa, brilho, cor=(255, 255, 255)):
    c = np.stack([brilho * cor[0], brilho * cor[1], brilho * cor[2], alfa * 255], -1)
    return Image.fromarray(c.astype(np.uint8), "RGBA")


def gif_pontilhado(alfa, brilho, cor=(255, 255, 255)):
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16 + 1 / 32
    visivel = alfa > np.tile(bayer, (H // 4, W // 4))
    p = rgba(np.where(visivel, 1.0, 0.0), brilho, cor).convert("RGB").quantize(255, dither=Image.Dither.NONE)
    idx = np.array(p, dtype=np.uint8)
    idx[~visivel] = 255  # indice 255 = transparente
    out = Image.fromarray(idx, "P")
    out.putpalette(p.getpalette()[:765] + [0, 0, 0])
    return out


def salvar(caminho, fr, cor):
    g = [gif_pontilhado(a, b, cor) for a, b in fr]
    g[0].save(caminho, save_all=True, append_images=g[1:], duration=60, loop=0, transparency=255, disposal=2)


def main():
    pasta = os.path.join(HERE, "plugin", "auras")
    os.makedirs(pasta, exist_ok=True)
    fr = list(quadros())
    salvar(os.path.join(pasta, "chamas.gif"), fr, (255, 255, 255))
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    salvar(os.path.join(HERE, "dist", "previa_aura_roxa.gif"), fr, (170, 70, 255))
    print("chamas.gif", os.path.getsize(os.path.join(pasta, "chamas.gif")) // 1024, "KB")


if __name__ == "__main__":
    main()
