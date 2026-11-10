"""Gera as imagens da skin Cyberpunk em skins/cyberpunk/. Arte original, toda feita por codigo.

  python gerar_cyberpunk.py   -> login1.jpg e login2.jpg (fundos da tela de login) e chat.png (padrao do chat)

Paleta da skin: preto, vermelho, vinho, amarelo e verde-agua.
Precisa de Pillow e numpy. As imagens vao no repositorio: o ajudante (so stdlib) apenas as copia para o tema.
O chat.png e transparente e se repete lado a lado (overflow "tile"), entao serve para qualquer cor de fundo.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(HERE, "skins", "cyberpunk")
W, H = 1920, 1152  # mesma proporcao dos fundos originais da tela de login
VERMELHO, VINHO, AMARELO, AGUA, CLARO = (197, 0, 60), (136, 4, 37), (243, 230, 0), (85, 234, 212), (226, 250, 245)


def gradiente(paradas):
    """Degrade vertical. paradas = [(fracao da altura, (r, g, b)), ...]"""
    ys = np.linspace(0, 1, H)
    canais = [np.interp(ys, [p for p, _ in paradas], [c[i] for _, c in paradas]) for i in range(3)]
    return np.repeat(np.stack(canais, 1)[:, None, :], W, 1).astype(np.float32)


def neon(base, luz):
    """Soma a camada de luz e copias borradas dela: e o brilho em volta do neon."""
    out = base + np.asarray(luz, np.float32)
    for raio, forca in ((3, 0.8), (14, 0.6), (50, 0.45)):
        out += np.asarray(luz.filter(ImageFilter.GaussianBlur(raio)), np.float32) * forca
    return out


def acabamento(img, rng, grao=2.0):
    """Falha de sinal (faixas que escorregam para o lado, vermelho descolado), vinheta e grao; vira imagem de 8 bits."""
    for _ in range(9):
        y0, h = int(rng.integers(0, H - 40)), int(rng.integers(3, 22))
        img[y0:y0 + h] = np.roll(img[y0:y0 + h], int(rng.integers(-60, 60)), axis=1)
    img[..., 0] = np.roll(img[..., 0], 4, axis=1)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r2 = ((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2
    img = img * (1 - 0.32 * np.clip(r2, 0, 1.6))[..., None] + rng.normal(0, grao, (H, W, 1))
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def fileira(rng, d, dl, y_base, alturas, larguras, cor, p_janela, forca):
    """Uma fileira de predios de y_base para cima. As janelas acesas e os letreiros vao para a camada de luz (dl)."""
    x = -int(rng.integers(0, larguras[1]))
    while x < W:
        w, h = int(rng.integers(*larguras)), int(rng.integers(*alturas))
        topo = y_base - h
        d.rectangle([x, topo, x + w, H], fill=cor)
        if rng.random() < 0.4:  # recuo no topo
            topo2 = topo - int(h * rng.uniform(0.05, 0.16))
            d.rectangle([x + w * 0.25, topo2, x + w * 0.75, topo], fill=cor)
        if rng.random() < 0.3:  # antena com luz na ponta
            ax, ay = x + w // 2, topo - int(rng.integers(30, 110))
            d.line([ax, ay, ax, topo], fill=cor, width=2)
            dl.ellipse([ax - 2, ay - 2, ax + 2, ay + 2], fill=tuple(int(c * forca) for c in VERMELHO))
        tinta = [AGUA, AMARELO, VERMELHO, CLARO][int(rng.choice(4, p=[0.4, 0.3, 0.2, 0.1]))]
        for jy in range(topo + 10, y_base - 6, 13):
            andar = rng.random() < 0.12  # um andar inteiro aceso
            for jx in range(x + 6, x + w - 8, 10):
                if andar or rng.random() < p_janela:
                    f = forca * rng.uniform(0.35, 1.0)
                    dl.rectangle([jx, jy, jx + 5, jy + 5], fill=tuple(int(c * f) for c in tinta))
        if w > 70 and rng.random() < 0.45:  # letreiro vertical, com blocos no lugar de letras
            cor_l = [AMARELO, VERMELHO, AGUA][int(rng.choice(3, p=[0.4, 0.35, 0.25]))]
            lx, ly, lh = x + int(rng.integers(8, w - 30)), topo + int(rng.integers(20, 60)), int(rng.integers(70, 170))
            cl = tuple(int(c * forca) for c in cor_l)
            dl.rectangle([lx, ly, lx + 20, ly + lh], outline=cl, width=2)
            for by in range(ly + 8, ly + lh - 10, 16):
                dl.rectangle([lx + 5, by, lx + 15, by + int(rng.integers(4, 11))], fill=cl)
        x += w + int(rng.integers(-3, 12))


def cidade(seed=7):
    """Fundo 1: cidade a noite sob um sol amarelo, com neon, chuva e o reflexo no chao molhado."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    ceu = gradiente([(0, (0, 0, 0)), (0.3, (16, 1, 5)), (0.55, (62, 3, 18)), (0.68, VINHO), (1, VINHO)])
    r = np.hypot(x - 0.69 * W, y - 0.30 * H)
    ceu += np.clip((150 - r) / 3, 0, 1)[..., None] * np.array(AMARELO, np.float32) * 0.95            # sol
    ceu += np.exp(-r / 240)[..., None] * np.array(AMARELO, np.float32) * 0.16                         # halo
    ceu *= (1 - 0.5 * np.clip(np.sin(y / 9 + np.sin(x / 300) * 1.5), 0.55, 1))[..., None] ** 0.4      # faixas de nuvem
    base, luz = Image.fromarray(np.clip(ceu, 0, 255).astype(np.uint8)), Image.new("RGB", (W, H))
    d, dl = ImageDraw.Draw(base, "RGBA"), ImageDraw.Draw(luz)
    chao = int(0.80 * H)
    for y_base, alturas, larguras, cor, p, forca, nevoa in (
            (chao - 30, (140, 430), (28, 80), (72, 5, 24), 0.07, 0.30, 70),
            (chao - 10, (170, 560), (46, 120), (30, 3, 11), 0.16, 0.65, 45),
            (chao, (110, 400), (80, 190), (5, 1, 2), 0.24, 1.0, 0)):
        fileira(rng, d, dl, y_base, alturas, larguras, cor, p, forca)
        for i in range(0, 260, 4):  # nevoa avermelhada entre as fileiras, mais densa perto do chao
            a = int(nevoa * (1 - i / 260) ** 2)
            d.rectangle([0, y_base - i - 4, W, y_base - i], fill=(176, 6, 52, a))
    img = neon(np.asarray(base, np.float32), luz)
    # chao molhado: a cidade de cabeca para baixo, borrada na vertical e escurecida
    alt = H - chao
    refl = img[chao - alt:chao][::-1]
    k = 28
    c = np.cumsum(np.concatenate([np.repeat(refl[:1], k, 0), refl]), 0)
    refl = (c[k:] - c[:-k]) / k
    refl = refl * np.linspace(0.62, 0.2, alt)[:, None, None] + np.array([5, 0, 2], np.float32)
    refl *= (1 - 0.35 * (rng.random((alt, 1, 1)) < 0.18))  # ondinhas
    img[chao:] = refl
    chuva = Image.new("RGBA", (W, H))
    dc = ImageDraw.Draw(chuva)
    for _ in range(1500):
        cx, cy, n = rng.integers(0, W + 200), rng.integers(-50, H), rng.integers(14, 46)
        dc.line([cx, cy, cx - n * 0.22, cy + n], fill=(200, 240, 232, int(rng.integers(14, 46))), width=1)
    pronto = acabamento(img, rng).convert("RGBA")
    return Image.alpha_composite(pronto, chuva).convert("RGB")


def grade(seed=11):
    """Fundo 2: grade de neon ate o horizonte, com um anel de luz atras da cidade."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    hy, cx = int(0.60 * H), W / 2
    ceu = gradiente([(0, (0, 0, 0)), (0.4, (12, 1, 4)), (0.6, (110, 4, 32)), (0.601, (10, 0, 3)), (1, (0, 0, 0))])
    estrelas = (rng.random((H, W)) < 0.0007) * (y < hy - 40) * rng.uniform(60, 200, (H, W))
    ceu += estrelas[..., None]
    luz = Image.new("RGB", (W, H))
    dl = ImageDraw.Draw(luz)
    # anel: amarelo em cima, vermelho embaixo
    raio, ay = 250, hy - 170
    r = np.hypot(x - cx, y - ay)
    anel = np.exp(-((r - raio) / 5.5) ** 2)[..., None]
    mistura = np.clip((y - (ay - raio)) / (2 * raio), 0, 1)[..., None]
    luz_anel = anel * (np.array(AMARELO, np.float32) * (1 - mistura) + np.array(VERMELHO, np.float32) * mistura)
    ceu *= np.clip((r - raio + 6) / 12, 0.25, 1)[..., None]  # dentro do anel fica mais escuro
    # grade no chao: linhas horizontais cada vez mais juntas e linhas que correm para o ponto de fuga
    z = 1.0
    while z < 26:
        gy = hy + (H - hy) / z
        dl.line([0, gy, W, gy], fill=tuple(min(255, int(c * (0.45 + 0.8 / z))) for c in VERMELHO), width=3 if z < 2 else 2 if z < 5 else 1)
        z *= 1.17
    for k in range(-34, 35):
        dl.line([cx + k * 190, H, cx + k * 5.5, hy], fill=tuple(int(c * 0.7) for c in AGUA), width=2)
    base = Image.fromarray(np.clip(ceu, 0, 255).astype(np.uint8))
    img = neon(np.asarray(base, np.float32) + luz_anel * 0.9, luz)
    img += np.asarray(Image.fromarray(np.clip(luz_anel, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(40)), np.float32) * 0.9
    # cidade distante no horizonte, escura, com poucas luzes
    cid, lz = Image.new("RGBA", (W, H)), Image.new("RGB", (W, H))
    dci, dlz = ImageDraw.Draw(cid), ImageDraw.Draw(lz)
    px = 0
    while px < W:
        w = int(rng.integers(14, 60))
        h = int(rng.integers(8, 44) + 150 * np.exp(-((px - cx) / 330) ** 2) * rng.uniform(0.3, 1))
        dci.rectangle([px, hy - h, px + w, hy + 1], fill=(3, 0, 1, 255))
        for _ in range(h * w // 260):
            jx, jy = px + int(rng.integers(2, w - 1)), hy - int(rng.integers(3, max(4, h - 2)))
            dlz.rectangle([jx, jy, jx + 2, jy + 2], fill=[AGUA, VERMELHO, AMARELO, CLARO][int(rng.integers(0, 4))])
        px += w
    img = np.asarray(Image.alpha_composite(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA"), cid).convert("RGB"), np.float32)
    img = neon(img, lz)
    img += np.exp(-np.abs(y - hy) / 26)[..., None] * np.array(VERMELHO, np.float32) * 0.4  # brilho no horizonte
    return acabamento(img, rng)


def circuito(seed=3, lado=512, passo=32):
    """Padrao do chat: trilhas de circuito bem fracas, transparente, que emenda nas quatro bordas."""
    rng = np.random.default_rng(seed)
    e = 2  # desenha no dobro e reduz, para suavizar as linhas
    tela = Image.new("RGBA", (3 * lado * e, 3 * lado * e))
    d = ImageDraw.Draw(tela)
    n = lado // passo

    def nove(fn):  # desenha nas 9 copias: o que sai por um lado entra pelo outro
        for oy in range(3):
            for ox in range(3):
                fn(ox * lado * e, oy * lado * e)

    for gy in range(n):
        for gx in range(n):
            nove(lambda ox, oy: d.rectangle([ox + gx * passo * e - 1, oy + gy * passo * e - 1, ox + gx * passo * e + 1, oy + gy * passo * e + 1],
                                            fill=AGUA + (16,)))
    direcoes = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    for _ in range(15):
        sorte = rng.random()  # o vermelho da paleta e escuro: precisa de mais opacidade para aparecer
        cor = AMARELO + (int(rng.integers(24, 38)),) if sorte < 0.22 else VERMELHO + (int(rng.integers(70, 100)),) if sorte < 0.5 \
            else AGUA + (int(rng.integers(30, 48)),)
        px, py, di = int(rng.integers(0, n)), int(rng.integers(0, n)), int(rng.integers(0, 4)) * 2
        pontos = [(px, py)]
        for _ in range(int(rng.integers(3, 6))):  # no maximo 15 casas: a trilha nao passa de um ladrilho de distancia
            comp = int(rng.integers(1, 4))
            px, py = px + direcoes[di][0] * comp, py + direcoes[di][1] * comp
            pontos.append((px, py))
            di = (di + int(rng.choice([-1, 1]))) % 8  # curva de 45 graus
        xy = [(p[0] * passo * e, p[1] * passo * e) for p in pontos]
        nove(lambda ox, oy: d.line([(a + ox, b + oy) for a, b in xy], fill=cor, width=e))
        for (a, b) in (xy[0], xy[-1]):  # ilha de solda nas pontas
            nove(lambda ox, oy: d.ellipse([a + ox - 3 * e, b + oy - 3 * e, a + ox + 3 * e, b + oy + 3 * e], outline=cor[:3] + (cor[3] + 22,), width=e))
    for _ in range(7):  # marcas de tres riscos inclinados, em amarelo
        a, b = int(rng.integers(0, n)) * passo * e + 10 * e, int(rng.integers(0, n)) * passo * e + 12 * e
        for i in range(3):
            nove(lambda ox, oy: d.line([a + ox + i * 7 * e, b + oy + 8 * e, a + ox + i * 7 * e + 6 * e, b + oy], fill=AMARELO + (38,), width=e))
    tela = np.asarray(tela.resize((3 * lado, 3 * lado), Image.LANCZOS))
    meio = tela[lado:2 * lado, lado:2 * lado]
    # emenda: o que vem logo depois da borda direita/de baixo tem de ser igual ao comeco do ladrilho
    assert (tela[lado + 16:2 * lado + 16, lado + 16:2 * lado + 16] == np.roll(meio, (-16, -16), (0, 1))).all()
    return Image.fromarray(meio)


if __name__ == "__main__":
    os.makedirs(SAIDA, exist_ok=True)
    cidade().save(os.path.join(SAIDA, "login1.jpg"), quality=84, optimize=True)
    grade().save(os.path.join(SAIDA, "login2.jpg"), quality=84, optimize=True)
    circuito().save(os.path.join(SAIDA, "chat.png"), optimize=True)
    for n in sorted(os.listdir(SAIDA)):
        print(n, os.path.getsize(os.path.join(SAIDA, n)) // 1024, "KB")
