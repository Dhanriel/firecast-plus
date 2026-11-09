"""Pecas visuais do trailer 3: fotos com movimento 3D, pos-producao, vidro fosco, texto, logo e telas simuladas.

Convencao: o fundo de cada quadro e um array numpy float32 (H, W, 3) em 0..1; a interface e desenhada numa
camada PIL RGBA por cima e juntada no fim com compor().
"""
import functools, math, os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
AQUI = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(AQUI, "render")
FONTES = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

OURO = (236, 184, 84)
ROXO = (168, 92, 255)
CIANO = (84, 204, 240)
BRANCO = (255, 255, 255)


# ------------------------------------------------------------------ tempo e curvas

def clamp01(x):
    return max(0.0, min(1.0, x))


def suave(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def sai(x):  # ease-out cubico
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def mola(x):  # ease-out com leve passada (pop)
    x = clamp01(x)
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1.0


def lerp(a, b, t):
    return a + (b - a) * t


def janela(t, a, b, sobe=0.3, desce=0.3):
    """1 dentro de [a, b], com rampas suaves nas bordas."""
    return suave((t - a) / sobe) * (1 - suave((t - (b - desce)) / desce))


# ------------------------------------------------------------------ fontes e texto

@functools.lru_cache(None)
def fonte(nome, tam, var=None):
    f = ImageFont.truetype(os.path.join(FONTES, nome), int(tam))
    if var:
        f.set_variation_by_name(var)
    return f


def bahn(tam, var="Bold"):
    return fonte("bahnschrift.ttf", tam, var)


def ui_fonte(tam, negrito=False):
    return fonte("seguisb.ttf" if negrito else "segoeui.ttf", tam)


def titulo_fonte(tam):
    return fonte("constanb.ttf", tam)


def texto(d, xy, s, f, cor, alfa=1.0, ancora="la", sombra=True, espac=0):
    if alfa <= 0.01:
        return
    a = int(255 * alfa)
    if espac:
        x, y = xy
        larg = largura(s, f, espac)
        if ancora[0] == "m":
            x -= larg / 2
        elif ancora[0] == "r":
            x -= larg
        for ch in s:
            if sombra:
                d.text((x + 2, y + 3), ch, font=f, fill=(0, 0, 0, int(a * 0.55)), anchor="l" + ancora[1])
            d.text((x, y), ch, font=f, fill=cor[:3] + (a,), anchor="l" + ancora[1])
            x += d.textlength(ch, font=f) + espac
        return
    if sombra:
        d.text((xy[0] + 2, xy[1] + 3), s, font=f, fill=(0, 0, 0, int(a * 0.55)), anchor=ancora)
    d.text(xy, s, font=f, fill=cor[:3] + (a,), anchor=ancora)


def largura(s, f, espac=0):
    return sum(f.getlength(ch) + espac for ch in s) - espac if espac else f.getlength(s)


def quebrar(s, f, maximo):
    linhas, atual = [], ""
    for p in s.split():
        teste = (atual + " " + p).strip()
        if f.getlength(teste) > maximo and atual:
            linhas.append(atual)
            atual = p
        else:
            atual = teste
    return linhas + [atual]


# ------------------------------------------------------------------ fotos com movimento 3D

@functools.lru_cache(None)
def foto(nome):
    """Foto em meia precisao (metade da memoria por processo; as contas saem em float32)."""
    return (np.asarray(Image.open(os.path.join(RENDER, nome + ".png")).convert("RGB"), np.float32) / 255).astype(np.float16)


@functools.lru_cache(None)
def foto_borrada(nome, sigma):
    """Foto ja desfocada, para fundos: borrar uma vez em vez de a cada quadro."""
    im = Image.open(os.path.join(RENDER, nome + ".png")).convert("RGB")
    im = im.resize((im.width // 2, im.height // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(sigma / 2))
    im = im.resize((im.width * 2, im.height * 2), Image.BILINEAR)
    return (np.asarray(im, np.float32) / 255).astype(np.float16)


@functools.lru_cache(None)
def prof(nome):
    a = np.asarray(Image.open(os.path.join(RENDER, nome + "_prof.png")), np.float32) / 65535
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).astype(np.float16)  # PNG sai em sRGB


@functools.lru_cache(None)
def _grade_saida():
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    return u - W / 2 + 0.5, v - H / 2 + 0.5


def amostrar(img, sx, sy):
    """Bilinear vetorizado (bem mais rapido que map_coordinates canal por canal)."""
    h, w = img.shape[:2]
    sx = np.clip(sx, 0, w - 1.001)
    sy = np.clip(sy, 0, h - 1.001)
    x0, y0 = sx.astype(np.int32), sy.astype(np.int32)
    fx, fy = (sx - x0)[..., None], (sy - y0)[..., None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def camera(nome, t, zoom=(1.0, 1.08), centro=((0.5, 0.5), (0.5, 0.5)), paralaxe=(0.0, 0.0), giro=(0.0, 0.0), borrar=0,
           img=None):
    """Movimento de camera sobre uma foto: zoom e pan, mais paralaxe pela profundidade (perto anda mais).

    t em 0..1; paralaxe em pixels da foto entre o comeco e o fim do movimento; giro em graus."""
    if img is None:
        img = foto_borrada(nome, borrar) if borrar else foto(nome)
    h, w = img.shape[:2]
    z = lerp(zoom[0], zoom[1], t)
    cx, cy = lerp(centro[0][0], centro[1][0], t) * w, lerp(centro[0][1], centro[1][1], t) * h
    esc = (w / W) / z
    u, v = _grade_saida()
    ang = math.radians(lerp(giro[0], giro[1], t))
    ca, sa = math.cos(ang), math.sin(ang)
    sx = cx + (u * ca - v * sa) * esc
    sy = cy + (u * sa + v * ca) * esc
    if paralaxe != (0.0, 0.0) and os.path.exists(os.path.join(RENDER, nome + "_prof.png")):
        p = prof(nome)
        dd = p[np.clip(sy, 0, h - 1).astype(np.int32), np.clip(sx, 0, w - 1).astype(np.int32)].astype(np.float32) - 0.5
        k = t - 0.5
        sx = sx + paralaxe[0] * k * dd
        sy = sy + paralaxe[1] * k * dd
    return amostrar(img, sx, sy).astype(np.float32)


def projetar(nome, t, px, py, zoom=(1.0, 1.08), centro=((0.5, 0.5), (0.5, 0.5)), giro=(0.0, 0.0)):
    """Inverso de camera(): onde um pixel (px, py) da foto aparece no quadro (sem paralaxe)."""
    h, w = foto(nome).shape[:2]
    z = lerp(zoom[0], zoom[1], t)
    cx, cy = lerp(centro[0][0], centro[1][0], t) * w, lerp(centro[0][1], centro[1][1], t) * h
    esc = (w / W) / z
    ang = math.radians(lerp(giro[0], giro[1], t))
    dx, dy = (px - cx) / esc, (py - cy) / esc
    return dx * math.cos(ang) + dy * math.sin(ang) + W / 2, -dx * math.sin(ang) + dy * math.cos(ang) + H / 2


# ------------------------------------------------------------------ pos-producao

def para_pil(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def de_pil(im):
    return np.asarray(im.convert("RGB"), np.float32) / 255


def desfoque(arr, sigma):
    """Desfoque forte e barato: reduz, borra, amplia."""
    h, w = arr.shape[:2]
    f = 4 if sigma >= 8 else 2
    im = para_pil(arr).resize((max(1, w // f), max(1, h // f)), Image.BILINEAR)
    im = im.filter(ImageFilter.GaussianBlur(sigma / f)).resize((w, h), Image.BILINEAR)
    return de_pil(im)


def graduar(arr, exposicao=1.0, contraste=1.0, saturacao=1.0, tinta=(1.0, 1.0, 1.0), sombras=(0.0, 0.0, 0.0)):
    x = arr * exposicao
    if contraste != 1.0:
        x = (x - 0.45) * contraste + 0.45
    if saturacao != 1.0:
        cinza = x.mean(axis=2, keepdims=True)
        x = cinza + (x - cinza) * saturacao
    x = x * np.array(tinta, np.float32)
    if any(sombras):
        x = x + np.array(sombras, np.float32) * (1 - np.clip(x.mean(axis=2, keepdims=True) * 2.2, 0, 1))
    return np.clip(x, 0, 1.5)


@functools.lru_cache(None)
def vinheta(forca=0.5):
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((u - W / 2) / (W / 2)) ** 2 + ((v - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    return (1 - forca * np.clip(r, 0, 1) ** 2.2)[..., None].astype(np.float32)


@functools.lru_cache(None)
def _graos():
    rng = np.random.default_rng(5)
    out = []
    for _ in range(6):
        g = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
        g = np.asarray(Image.fromarray(g).resize((W, H), Image.BILINEAR), np.float32)
        out.append(g[..., None].astype(np.float16))
    return out


def grao(arr, quadro, forca=0.028):
    return arr + _graos()[quadro % 6].astype(np.float32) * forca


@functools.lru_cache(None)
def _brilho(raio):
    s = int(raio * 7) + 1  # 3.5 desvios para cada lado: a borda do sprite ja e ~0 (sem quadrado visivel)
    v, u = np.mgrid[0:s, 0:s].astype(np.float32) - s / 2
    return np.exp(-(u * u + v * v) / (2 * raio * raio)).astype(np.float32)


def luz_pontual(arr, x, y, raio, cor, forca):
    """Soma um brilho gaussiano (luz aditiva) no array."""
    g = _brilho(round(raio, 1))
    s = g.shape[0]
    x0, y0 = int(x - s / 2), int(y - s / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + s), min(H, y0 + s)
    if xb <= xa or yb <= ya:
        return
    arr[ya:yb, xa:xb] += g[ya - y0:yb - y0, xa - x0:xb - x0, None] * (np.array(cor, np.float32) * forca)


class Brasas:
    """Faiscas subindo e balancando, com brilho aditivo (fogueira/aura)."""

    def __init__(self, n, semente, area=(0, W, H * 0.55, H + 60), cor=(1.0, 0.52, 0.18), vel=(40, 120), tam=(1.2, 3.2)):
        r = np.random.default_rng(semente)
        self.n, self.cor = n, cor
        self.x0 = r.uniform(area[0], area[1], n)
        self.y0 = r.uniform(area[2], area[3], n)
        self.v = r.uniform(*vel, n)
        self.vida = r.uniform(2.5, 6.0, n)
        self.fase = r.uniform(0, 100, n)
        self.balanco = r.uniform(8, 40, n)
        self.freq = r.uniform(0.4, 1.4, n)
        self.tam = r.uniform(*tam, n)

    def desenhar(self, arr, t, intensidade=1.0):
        if intensidade <= 0.01:
            return
        for i in range(self.n):
            p = ((t + self.fase[i]) % self.vida[i]) / self.vida[i]
            y = self.y0[i] - self.v[i] * p * self.vida[i]
            x = self.x0[i] + self.balanco[i] * math.sin(self.freq[i] * t * 6.28 + self.fase[i])
            a = math.sin(math.pi * p) * intensidade * (0.6 + 0.4 * math.sin(t * 9 + self.fase[i]))
            if a > 0.02:
                luz_pontual(arr, x, y, self.tam[i] * 2.4, self.cor, a * 0.9)
                luz_pontual(arr, x, y, self.tam[i] * 0.7, (1.0, 0.9, 0.7), a * 1.4)


def compor(base, camada):
    """Junta a camada PIL RGBA (interface) sobre o fundo numpy."""
    c = np.asarray(camada, np.float32) / 255
    a = c[..., 3:4]
    return base * (1 - a) + c[..., :3] * a


def tarjas(arr, quanto):
    """Tarjas pretas de cinema 2.39:1 (quanto 0..1)."""
    if quanto <= 0:
        return arr
    alt = int((H - W / 2.39) / 2 * quanto)
    if alt > 0:
        arr[:alt] = 0
        arr[H - alt:] = 0
    return arr


# ------------------------------------------------------------------ interface: vidro, cursor, avisos

def caixa_arredondada(tam, raio):
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), raio, fill=255)
    return m


def sombra(ui, caixa, raio=22, forca=150, espalha=22, desloc=(0, 14)):
    x0, y0, x1, y1 = [int(v) for v in caixa]
    m = espalha * 2
    tam = (x1 - x0 + 2 * m, y1 - y0 + 2 * m)
    s = Image.new("RGBA", tam, (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((m, m, tam[0] - m, tam[1] - m), raio, fill=(0, 0, 0, forca))
    s = s.filter(ImageFilter.GaussianBlur(espalha / 2))
    ui.alpha_composite(s, (x0 - m + desloc[0], y0 - m + desloc[1]))


def vidro(base, ui, caixa, raio=22, tinta=(16, 13, 28), opac=0.74, alfa=1.0, borda=36, sombra_forca=150):
    """Cartao de vidro fosco: o fundo de tras borrado, tingido, com borda fina e sombra."""
    if alfa <= 0.01:
        return
    x0, y0, x1, y1 = [int(v) for v in caixa]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    sombra(ui, (x0, y0, x1, y1), raio, int(sombra_forca * alfa))
    reg = desfoque(base[y0:y1, x0:x1], 18)
    reg = reg * (1 - opac) + np.array(tinta, np.float32) / 255 * opac
    card = para_pil(reg).convert("RGBA")
    mascara = caixa_arredondada((x1 - x0, y1 - y0), raio)
    if alfa < 1:
        mascara = mascara.point(lambda v: int(v * alfa))
    card.putalpha(mascara)
    ui.alpha_composite(card, (x0, y0))
    ImageDraw.Draw(ui).rounded_rectangle((x0, y0, x1 - 1, y1 - 1), raio, outline=(255, 255, 255, int(borda * alfa)), width=2)


@functools.lru_cache(None)
def _cursor(escala=1.0):
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    s = 4
    im = Image.new("RGBA", (int(48 * s * escala), int(56 * s * escala)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    p = [(x * s * escala + 6 * s, y * s * escala + 6 * s) for x, y in pts]
    sombra_p = [(x + 3 * s, y + 4 * s) for x, y in p]
    d.polygon(sombra_p, fill=(0, 0, 0, 90))
    im = im.filter(ImageFilter.GaussianBlur(3 * s))
    d = ImageDraw.Draw(im)
    d.polygon(p, fill=(255, 255, 255, 255), outline=(20, 20, 20, 255))
    d.line(p + [p[0]], fill=(20, 20, 20, 255), width=int(2 * s))
    return im.resize((im.width // s, im.height // s), Image.LANCZOS)


def cursor(ui, x, y, clique=None, t=0.0, alfa=1.0):
    """Cursor do mouse; 'clique' = instante do clique (s) para o anel e o aperto."""
    if alfa <= 0.01:
        return
    esc = 1.0
    if clique is not None and 0 <= t - clique < 0.6:
        k = (t - clique) / 0.6
        d = ImageDraw.Draw(ui)
        r = 10 + 46 * sai(k)
        d.ellipse((x - r, y - r, x + r, y + r), outline=(255, 255, 255, int(200 * (1 - k))), width=3)
        if t - clique < 0.12:
            esc = 0.88
    c = _cursor(round(esc, 2))
    if alfa < 1:
        c = c.copy()
        c.putalpha(c.getchannel("A").point(lambda v: int(v * alfa)))
    ui.alpha_composite(c, (int(x - 6), int(y - 6)))


def caminho_cursor(t, pontos):
    """pontos: lista de (tempo, x, y). Interpola com ease entre eles."""
    if t <= pontos[0][0]:
        return pontos[0][1:]
    for (ta, xa, ya), (tb, xb, yb) in zip(pontos, pontos[1:]):
        if t <= tb:
            k = suave((t - ta) / max(1e-3, tb - ta))
            return lerp(xa, xb, k), lerp(ya, yb, k)
    return pontos[-1][1:]


def aviso(base, ui, x, y, icone_cor, linha1, linha2="", alfa=1.0, larg=470):
    """Notificacao flutuante (toast): bolinha colorida + duas linhas."""
    if alfa <= 0.01:
        return
    dy = (1 - sai(alfa)) * 24
    caixa = (x, y + dy, x + larg, y + dy + (96 if linha2 else 70))
    vidro(base, ui, caixa, raio=18, alfa=alfa, opac=0.8)
    d = ImageDraw.Draw(ui)
    cx, cy = x + 46, caixa[1] + (48 if linha2 else 35)
    d.ellipse((cx - 20, cy - 20, cx + 20, cy + 20), fill=icone_cor + (int(255 * alfa),))
    texto(d, (x + 82, caixa[1] + (22 if linha2 else 20)), linha1, ui_fonte(26, True), BRANCO, alfa)
    if linha2:
        texto(d, (x + 82, caixa[1] + 56), linha2, ui_fonte(22), (200, 196, 220), alfa)


def legenda(ui, quem_nome, quem_cor, s, alfa):
    """Legenda de cinema: etiqueta com o nome de quem fala + a fala, numa faixa escura."""
    if alfa <= 0.01:
        return
    f = ui_fonte(34, True)
    linhas = quebrar(s, f, 1320)[:3]
    alt = 30 + 46 * len(linhas)
    y0 = H - 64 - alt
    larg = max(f.getlength(l) for l in linhas) + 80
    larg = max(larg, 360)
    x0 = (W - larg) / 2
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(camada).rounded_rectangle((x0, y0, x0 + larg, y0 + alt), 16, fill=(6, 5, 12, int(165 * alfa)))
    ui.alpha_composite(camada)
    d = ImageDraw.Draw(ui)
    fe = bahn(22, "Bold")
    tag = quem_nome
    lt = fe.getlength(tag) + 28
    d.rounded_rectangle((W / 2 - lt / 2, y0 - 19, W / 2 + lt / 2, y0 + 15), 10, fill=quem_cor + (int(240 * alfa),))
    texto(d, (W / 2, y0 - 2), tag, fe, (18, 14, 24), alfa, ancora="mm", sombra=False)
    for i, l in enumerate(linhas):
        texto(d, (W / 2, y0 + 38 + 46 * i), l, f, BRANCO, alfa, ancora="mm")


# ------------------------------------------------------------------ logo

@functools.lru_cache(None)
def emblema(tam):
    """Icone de d20 dourado (hexagono + triangulo interno + raios) com um '+' no centro. RGBA."""
    s = 4
    T = tam * s
    im = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = T / 2
    R = T * 0.46
    hexa = [(c + R * math.cos(math.radians(90 + 60 * k)), c - R * math.sin(math.radians(90 + 60 * k))) for k in range(6)]
    r2 = R * 0.62
    tri = [(c + r2 * math.cos(math.radians(90 + 120 * k)), c - r2 * math.sin(math.radians(90 + 120 * k)) + R * 0.08) for k in range(3)]
    larg = int(T * 0.028)
    d.polygon(hexa, fill=(30, 20, 46, 235))
    faces = [(hexa[0], hexa[1], tri[0]), (hexa[0], hexa[5], tri[0])]
    for f_ in faces:
        d.polygon(f_, fill=(52, 34, 78, 235))
    for i in range(6):
        d.line([hexa[i], hexa[(i + 1) % 6]], fill=OURO + (255,), width=larg)
    for i in range(3):
        d.line([tri[i], tri[(i + 1) % 3]], fill=OURO + (255,), width=larg)
    # icone classico de d20: cada vertice de fora liga aos vertices de dentro mais proximos
    for hi, ti in [(0, 0), (1, 0), (1, 1), (2, 1), (3, 1), (3, 2), (4, 2), (5, 2), (5, 0)]:
        d.line([hexa[hi], tri[ti]], fill=OURO + (200,), width=int(larg * 0.7))
    cc = (c, c + R * 0.12)
    b = R * 0.2
    e = int(T * 0.05)
    d.rounded_rectangle((cc[0] - b, cc[1] - e / 2, cc[0] + b, cc[1] + e / 2), e // 2, fill=(255, 236, 190, 255))
    d.rounded_rectangle((cc[0] - e / 2, cc[1] - b, cc[0] + e / 2, cc[1] + b), e // 2, fill=(255, 236, 190, 255))
    im = im.resize((tam, tam), Image.LANCZOS)
    brilho = im.filter(ImageFilter.GaussianBlur(tam * 0.04))
    out = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    out.alpha_composite(brilho)
    out.alpha_composite(im)
    return out


def marca_texto(ui, cx, cy, tam, alfa=1.0, espac_extra=0.0, sub=None, alfa_sub=0.0):
    """FIRECAST (branco, espacado) + PLUS (dourado)."""
    d = ImageDraw.Draw(ui)
    f = bahn(tam, "Bold")
    esp = tam * (0.10 + espac_extra)
    a, b = "FIRECAST", "PLUS"
    la, lb = largura(a, f, esp), largura(b, f, esp)
    gap = tam * 0.45
    x = cx - (la + gap + lb) / 2
    if alfa > 0.01:
        brilho = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        texto(ImageDraw.Draw(brilho), (x + la + gap, cy), b, f, OURO, alfa * 0.9, ancora="lm", sombra=False, espac=esp)
        ui.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(tam * 0.18)))
    texto(d, (x, cy), a, f, BRANCO, alfa, ancora="lm", espac=esp)
    texto(d, (x + la + gap, cy), b, f, OURO, alfa, ancora="lm", espac=esp)
    if sub and alfa_sub > 0.01:
        texto(d, (cx, cy + tam * 0.95), sub, ui_fonte(tam * 0.36), (226, 220, 240), alfa_sub, ancora="mm")


# ------------------------------------------------------------------ aura (frames do gerar_aura tingidos)

@functools.lru_cache(None)
def _aura_bruta():
    import sys
    sys.path.insert(0, os.path.dirname(AQUI))
    import gerar_aura
    return [(a.astype(np.float32), b.astype(np.float32)) for a, b in gerar_aura.quadros()], gerar_aura


@functools.lru_cache(None)
def aura_quadro(i, cor, largura_px):
    """Quadro i da aura, tingido e redimensionado: devolve (rgb*alfa pre-multiplicado, alfa)."""
    fr, ga = _aura_bruta()
    a, b = fr[i % len(fr)]
    alt = int(largura_px * ga.H / ga.W)
    al = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((largura_px, alt), Image.BILINEAR), np.float32) / 255
    br = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).resize((largura_px, alt), Image.BILINEAR), np.float32) / 255
    rgb = br[..., None] * (np.array(cor, np.float32) / 255)[None, None, :]
    return rgb * al[..., None], al


def aura_colocar(arr, t, cor, cx, cy_token, largura_px, forca=1.0, tela=False):
    """Aura centrada no token (cy_token = centro do token, que fica no buraco da aura).

    Soma de luz em fundo escuro; tela=True usa mistura "screen", que nao estoura para branco em fundo claro."""
    _, ga = _aura_bruta()
    rgb, al = aura_quadro(int(t * 16) % 14, cor, int(largura_px))
    h, w = al.shape
    x0 = int(cx - w * ga.TOKEN_CX)
    y0 = int(cy_token - h * ga.TOKEN_CY)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return
    pedaco = rgb[ya - y0:yb - y0, xa - x0:xb - x0] * forca * 1.25
    if tela:
        reg = arr[ya:yb, xa:xb]
        arr[ya:yb, xa:xb] = 1 - (1 - np.clip(reg, 0, 1)) * (1 - np.clip(pedaco, 0, 1))
    else:
        arr[ya:yb, xa:xb] += pedaco


# ------------------------------------------------------------------ telas simuladas

def mix_cor(a, b, k):
    return tuple(int(lerp(x, y, k)) for x, y in zip(a, b))


AVATAR_CORES = {"Aria": (92, 204, 238), "Kael": (130, 214, 124), "Mestre": (232, 96, 76), "Bruna": (240, 150, 210),
                "Teo": (250, 190, 90), "Goblin": (150, 170, 90)}


def avatar(d, cx, cy, r, nome, alfa=1.0):
    cor = AVATAR_CORES.get(nome, (180, 180, 200))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=cor + (int(255 * alfa),))
    texto(d, (cx, cy + 1), nome[0], ui_fonte(int(r * 1.05), True), (20, 16, 28), alfa, ancora="mm", sombra=False)


def janela_vtt(base, ui, caixa, tema, mensagens, alfa=1.0, titulo="Ruínas de Avalon", destaque_msg=None, t=0.0):
    """Um app de mesa virtual generico: barra de titulo, lista de mesas, chat e jogadores.

    tema: dict(fundo, painel, destaque, texto). mensagens: lista de dict(nome, texto, extra) de cima para baixo."""
    if alfa <= 0.01:
        return
    x0, y0, x1, y1 = [int(v) for v in caixa]
    a = int(255 * alfa)
    sombra(ui, caixa, 18, int(170 * alfa), 28, (0, 20))
    d = ImageDraw.Draw(ui)
    d.rounded_rectangle((x0, y0, x1, y1), 16, fill=tema["fundo"] + (a,))
    d.rounded_rectangle((x0, y0, x1, y0 + 46), 16, fill=tema["painel"] + (a,))
    d.rectangle((x0, y0 + 30, x1, y0 + 46), fill=tema["painel"] + (a,))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((x0 + 18 + i * 22, y0 + 16, x0 + 32 + i * 22, y0 + 30), fill=c + (a,))
    texto(d, ((x0 + x1) / 2, y0 + 23), titulo, ui_fonte(20, True), tema["texto"], alfa, ancora="mm", sombra=False)
    # abas
    lx = x0 + 200
    for i, aba in enumerate(["Chat da mesa", "Mapa", "Fichas"]):
        on = i == 0
        f = ui_fonte(19, on)
        lw = f.getlength(aba) + 34
        if on:
            d.rectangle((lx, y0 + 50, lx + lw, y0 + 86), fill=tema["fundo"] + (a,))
            d.rectangle((lx, y0 + 83, lx + lw, y0 + 86), fill=tema["destaque"] + (a,))
        texto(d, (lx + lw / 2, y0 + 68), aba, f, tema["texto"] if on else mix_cor(tema["texto"], tema["fundo"], 0.45), alfa, ancora="mm", sombra=False)
        lx += lw + 6
    # lateral: mesas
    d.rectangle((x0, y0 + 46, x0 + 186, y1 - 16), fill=tema["painel"] + (a,))
    d.rounded_rectangle((x0, y1 - 32, x0 + 186, y1), 16, fill=tema["painel"] + (a,))
    texto(d, (x0 + 18, y0 + 70), "MESAS", bahn(16, "SemiBold"), mix_cor(tema["texto"], tema["painel"], 0.4), alfa, sombra=False)
    for i, m in enumerate(["Ruínas de Avalon", "Noite em Kraven", "Oficina de Fichas"]):
        yy = y0 + 104 + i * 46
        if i == 0:
            d.rounded_rectangle((x0 + 10, yy - 18, x0 + 176, yy + 18), 9, fill=tema["destaque"] + (int(a * 0.28),))
        d.ellipse((x0 + 20, yy - 7, x0 + 34, yy + 7), fill=(tema["destaque"] if i == 0 else mix_cor(tema["texto"], tema["painel"], 0.5)) + (a,))
        texto(d, (x0 + 44, yy), m, ui_fonte(17, i == 0), tema["texto"], alfa, ancora="lm", sombra=False)
    # direita: jogadores
    xr = x1 - 170
    d.rectangle((xr, y0 + 90, x1 - 12, y1 - 16), fill=tema["painel"] + (int(a * 0.6),))
    texto(d, (xr + 16, y0 + 112), "NA MESA", bahn(16, "SemiBold"), mix_cor(tema["texto"], tema["painel"], 0.4), alfa, sombra=False)
    for i, n in enumerate(["Mestre", "Aria", "Kael", "Bruna"]):
        yy = y0 + 150 + i * 50
        avatar(d, xr + 34, yy, 16, n, alfa)
        texto(d, (xr + 60, yy), n, ui_fonte(18, True), tema["texto"], alfa, ancora="lm", sombra=False)
    # chat
    cx0, cx1 = x0 + 206, xr - 16
    y = y0 + 106
    for m in mensagens:
        hl = destaque_msg is not None and m is destaque_msg
        f = ui_fonte(20)
        linhas = quebrar(m["texto"], f, cx1 - cx0 - 70)
        alt = 34 + 26 * len(linhas) + (m.get("extra_alt", 0))
        if hl:
            pulso = 0.55 + 0.45 * math.sin(t * 9)
            d.rounded_rectangle((cx0 - 6, y - 8, cx1, y + alt - 6), 10, fill=tema["destaque"] + (int(a * 0.22 * pulso + a * 0.1),),
                                outline=tema["destaque"] + (int(a * 0.9),), width=2)
        avatar(d, cx0 + 22, y + 18, 18, m["nome"], alfa)
        texto(d, (cx0 + 52, y + 2), m["nome"], ui_fonte(19, True), AVATAR_CORES.get(m["nome"], tema["texto"]), alfa, sombra=False)
        for i, l in enumerate(linhas):
            texto(d, (cx0 + 52, y + 28 + 26 * i), l, f, tema["texto"], alfa, sombra=False)
        if m.get("extra"):
            m["extra"](ui, d, cx0 + 52, y + 34 + 26 * len(linhas), alfa)
        y += alt
        if y > y1 - 40:
            break


TEMAS = {
    "Original": dict(fundo=(30, 30, 33), painel=(22, 22, 25), destaque=(235, 52, 73), texto=(236, 236, 240)),
    "Roxo": dict(fundo=(29, 25, 47), painel=(21, 18, 36), destaque=(159, 52, 235), texto=(242, 240, 250)),
    "Azul": dict(fundo=(21, 32, 43), painel=(15, 24, 33), destaque=(45, 140, 255), texto=(232, 240, 248)),
    "Verde": dict(fundo=(20, 30, 24), painel=(14, 22, 18), destaque=(47, 191, 113), texto=(238, 245, 239)),
    "Âmbar": dict(fundo=(30, 26, 20), painel=(22, 19, 14), destaque=(245, 166, 35), texto=(245, 239, 230)),
}


def tema_mix(a, b, k):
    return {c: mix_cor(TEMAS[a][c], TEMAS[b][c], k) for c in TEMAS[a]}
