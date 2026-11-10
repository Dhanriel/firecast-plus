"""Gera a aura animada do token (branca; o mapa tinge com colorMask) em plugin/auras/luz.gif.

  python gerar_aura.py   -> plugin/auras/luz.gif e docs/aura.gif (previa colorida num mapa, para o README)

O mapa e visto de cima, entao a aura e um circulo de luz no chao em volta do token, no estilo das auras de MMO:
um aro forte colado no token, um brilho que pulsa, um anel de runas e um de pontos girando em sentidos opostos,
ondas que se abrem e faiscas que saem em espiral. Tracos grossos: no mapa o GIF fica com uns 200 px. Tudo fecha o ciclo sem emenda (frequencias inteiras).
GIF so tem transparencia liga/desliga: a parte suave vira pontilhado (dither), e a opacidade do mapa suaviza.
O plugin precisa das medidas abaixo (TOKEN_*) para centralizar o token no meio da aura (aura.dlua).
"""
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 320                  # quadrado: o token fica no centro
N = 30                       # quadros do loop (50 ms cada = 1,5 s)
TOKEN_CX, TOKEN_CY = 0.5, 0.5
TOKEN_R = 0.2                # raio do token, em fracao de W
SS = 2                       # superamostragem: desenha no dobro e reduz
FIM = 0.485                  # raio onde a aura acaba


def anel(r, centro, largura):
    return np.clip(1 - np.abs(r - centro) / largura, 0, 1)


def quadros():
    n = W * SS
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    dx, dy = (x + 0.5) / n - TOKEN_CX, (y + 0.5) / n - TOKEN_CY
    r = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx)
    rng = np.random.default_rng(7)
    faiscas = [(rng.uniform(0, 2 * np.pi), rng.uniform(0, 1), int(rng.choice([1, 1, 2])), rng.uniform(0.7, 1.3))
               for _ in range(22)]
    borda = np.clip((FIM - r) / 0.035, 0, 1)            # some antes de bater na borda do quadro
    dentro = np.clip((r - (TOKEN_R - 0.012)) / 0.01, 0, 1)  # o meio fica vazio: o token cobre
    for k in range(N):
        t = k / N
        pulso = 0.5 + 0.5 * np.sin(2 * np.pi * t)
        camadas = []  # (alfa, brilho)
        # aro colado no token e o brilho que sai dele, pulsando
        camadas.append((anel(r, TOKEN_R + 0.008, 0.02), 0.92 + 0.08 * pulso))
        fora = np.clip(r - TOKEN_R - 0.012, 0, None)
        camadas.append((np.clip(1.25 * np.exp(-fora / (0.022 + 0.014 * pulso)), 0, 1) * (r > TOKEN_R - 0.004), 0.7))
        # anel de runas: tracos que giram um "dente" por ciclo
        rot_a = ang - 2 * np.pi * t / 8
        tracos = np.clip((np.sin(8 * rot_a) - 0.1) * 6, 0, 1) * anel(r, 0.37, 0.016)
        marcas = (np.cos(16 * rot_a + np.pi / 2) > 0.96) * anel(r, 0.37, 0.034)  # risquinhos que atravessam o anel
        camadas.append((np.maximum(np.maximum(tracos, marcas), anel(r, 0.37, 0.006) * 0.8), 0.95))
        # anel de pontos girando ao contrario
        rot_b = ang + 2 * np.pi * t / 24
        fase = (rot_b * 24 / (2 * np.pi)) % 1 - 0.5          # posicao dentro do intervalo entre dois pontos
        pontos = np.clip((1 - np.hypot(fase * (2 * np.pi * 0.29 / 24), r - 0.29) / 0.012) * 2, 0, 1)
        camadas.append((pontos, 1.0))
        # ondas que se abrem do token ate a borda
        for j in range(2):
            p = (t + j / 2) % 1
            camadas.append((anel(r, TOKEN_R + 0.03 + (FIM - TOKEN_R - 0.05) * p, 0.012) * (1 - p) ** 1.2, 0.9))
        # faiscas: estrelinhas de quatro pontas que saem do aro em espiral e somem
        fa = np.zeros_like(r)
        for teta, fi, vel, tam in faiscas:
            p = (vel * t + fi) % 1
            raio, a = TOKEN_R + 0.025 + 0.25 * p, teta + 0.6 * p
            cx, cy = TOKEN_CX + raio * np.cos(a), TOKEN_CY + raio * np.sin(a)
            s = 0.028 * tam * np.sin(np.pi * p) ** 0.7 * (0.75 + 0.25 * np.sin(2 * np.pi * (3 * t + fi)))
            if s < 0.002:
                continue
            x0, x1 = max(0, int((cx - s) * n) - 1), min(n, int((cx + s) * n) + 2)
            y0, y1 = max(0, int((cy - s) * n) - 1), min(n, int((cy + s) * n) + 2)
            ex, ey = dx[y0:y1, x0:x1] + TOKEN_CX - cx, dy[y0:y1, x0:x1] + TOKEN_CY - cy
            fino = s * 0.16
            estrela = np.maximum(np.exp(-(ex / fino) ** 2 - (ey / s) ** 2), np.exp(-(ey / fino) ** 2 - (ex / s) ** 2))
            estrela = np.maximum(estrela, np.exp(-(ex ** 2 + ey ** 2) / (s * 0.3) ** 2))
            fa[y0:y1, x0:x1] = np.maximum(fa[y0:y1, x0:x1], np.clip(estrela * 1.6, 0, 1))
        camadas.append((fa, 1.0))

        alfa = np.zeros_like(r)
        soma_b = np.zeros_like(r)
        soma_a = np.full_like(r, 1e-6)
        for a, b in camadas:
            alfa = np.maximum(alfa, a)
            soma_b += a * b
            soma_a += a
        alfa = np.clip(alfa * borda * dentro, 0, 1)
        brilho = np.clip(soma_b / soma_a, 0, 1)
        reduz = lambda m: m.reshape(H, SS, W, SS).mean(axis=(1, 3))
        yield reduz(alfa), reduz(brilho)


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16 + 1 / 32


def gif_pontilhado(alfa, brilho):
    """Quadro em tons de cinza (o mapa tinge) com o indice 255 transparente; o suave vira pontilhado."""
    visivel = alfa > np.tile(BAYER, (H // 4, W // 4))
    idx = np.where(visivel, np.round(brilho * 254), 255).astype(np.uint8)
    out = Image.fromarray(idx, "P")
    out.putpalette([v for i in range(255) for v in (i, i, i)] + [0, 0, 0])
    return out, visivel


def mapa(w, h):
    """Fundo de previa: piso de pedra com o quadriculado de um mapa de batalha."""
    rng = np.random.default_rng(3)
    base = np.array([58, 62, 56], np.float32) + rng.normal(0, 6, (h, w, 1))
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 48):
        d.line([x, 0, x, h], fill=(40, 43, 38))
    for y in range(0, h, 48):
        d.line([0, y, w, y], fill=(40, 43, 38))
    return img


def token(d, cx, cy, raio, cor):
    """Um token redondo de exemplo: borda clara e um rosto simples."""
    d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=cor, outline=(235, 235, 235), width=3)
    d.ellipse([cx - raio * 0.45, cy - raio * 0.55, cx + raio * 0.45, cy + raio * 0.25], fill=(240, 210, 180))
    d.ellipse([cx - raio * 0.75, cy + raio * 0.2, cx + raio * 0.75, cy + raio * 1.2], fill=(240, 210, 180))


def previa(fr, caminho):
    """Tres tokens no mapa, cada um com uma cor de aura, com a opacidade "Media" do plugin (0,75)."""
    lado = 220
    cores = [(255, 200, 60), (70, 220, 255), (190, 90, 255)]
    fundo = mapa(3 * lado + 40, lado + 20)
    saida = []
    for alfa, brilho in fr:
        quadro = fundo.copy()
        _, vis = gif_pontilhado(alfa, brilho)
        for i, cor in enumerate(cores):
            rgba = np.dstack([brilho[..., None] * np.array(cor, np.float32), vis * 0.75 * 255]).astype(np.uint8)
            quadro.paste(Image.fromarray(rgba, "RGBA").resize((lado, lado), Image.BILINEAR), (20 + i * lado, 10),
                         Image.fromarray(rgba, "RGBA").resize((lado, lado), Image.BILINEAR))
        d = ImageDraw.Draw(quadro)
        for i, cor in enumerate([(120, 70, 50), (50, 80, 120), (90, 50, 110)]):
            token(d, 20 + i * lado + lado // 2, 10 + lado // 2, int(lado * TOKEN_R), cor)
        saida.append(quadro.quantize(255, dither=Image.Dither.NONE))
    # um quadro sim, um nao: a previa do README fica com metade do tamanho
    saida[0].save(caminho, save_all=True, append_images=saida[2::2], duration=100, loop=0, optimize=True)


def main():
    pasta = os.path.join(HERE, "plugin", "auras")
    os.makedirs(pasta, exist_ok=True)
    fr = list(quadros())
    g = [gif_pontilhado(a, b)[0] for a, b in fr]
    destino = os.path.join(pasta, "luz.gif")
    g[0].save(destino, save_all=True, append_images=g[1:], duration=50, loop=0, transparency=255, disposal=2, optimize=False)
    # o loop fecha: o quadro seguinte ao ultimo e o primeiro (frequencias inteiras no tempo)
    assert len(g) == N and Image.open(destino).n_frames == N
    previa(fr, os.path.join(HERE, "docs", "aura.gif"))
    print("luz.gif", os.path.getsize(destino) // 1024, "KB; docs/aura.gif", os.path.getsize(os.path.join(HERE, "docs", "aura.gif")) // 1024, "KB")


if __name__ == "__main__":
    main()
