"""As cenas do trailer 3. Cada funcao recebe o tempo local t, a duracao, as marcas e as falas (tempos locais)
e devolve (fundo numpy, camada de interface PIL, extras) — extras: tarjas, flash, tremor, escurecer."""
import functools, json, math, os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from arte import (BRANCO, CIANO, H, OURO, RENDER, ROXO, TEMAS, W, AVATAR_CORES, Brasas, aura_colocar, avatar, aviso,
                  bahn, camera, caminho_cursor, clamp01, cursor, emblema, fonte, foto, graduar, janela, janela_vtt,
                  legenda, lerp, luz_pontual, marca_texto, mix_cor, mola, projetar, quebrar, sai, suave, tema_mix,
                  texto, titulo_fonte, ui_fonte, vidro)

POS = json.load(open(os.path.join(RENDER, "posicoes.json"), encoding="utf-8"))


def nova_ui():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


@functools.lru_cache(None)
def penumbra():
    """Sombra suave no canto superior esquerdo, para a manchete ler bem sobre fundo claro."""
    im = Image.new("RGBA", (1400, 380), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((-200, -200, 1050, 250), 120, fill=(8, 6, 14, 170))
    return im.filter(ImageFilter.GaussianBlur(70))


def manchete(ui, t, titulo, sub=None, x=110, y=64, atraso=0.15):
    a = sai((t - atraso) / 0.6)
    colar(ui, penumbra(), x - 110, 0, a)
    d = ImageDraw.Draw(ui)
    texto(d, (x - 40 * (1 - a), y), titulo, titulo_fonte(78), BRANCO, a)
    if sub:
        b = sai((t - atraso - 0.35) / 0.6)
        texto(d, (x + 4 - 30 * (1 - b), y + 98), sub, ui_fonte(30), (226, 218, 240), b)


@functools.lru_cache(None)
def recorte(nome, caixa, tam, raio=14):
    """Pedaco de uma foto renderizada, com cantos arredondados (para previas e mini-mapas)."""
    im = Image.open(os.path.join(RENDER, nome + ".png")).convert("RGB").crop(caixa).resize(tam, Image.LANCZOS).convert("RGBA")
    m = Image.new("L", tam, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tam[0] - 1, tam[1] - 1), raio, fill=255)
    im.putalpha(m)
    return im


def colar(ui, im, x, y, alfa=1.0):
    if alfa <= 0.01:
        return
    if alfa < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alfa)))
    ui.alpha_composite(im, (int(x), int(y)))


def tremor(t, inicio, dur=0.6, forca=14):
    k = t - inicio
    if not 0 <= k < dur:
        return (0, 0)
    a = forca * (1 - k / dur) ** 2
    return (int(a * math.sin(k * 71)), int(a * math.cos(k * 53)))


# ------------------------------------------------------------------ 1. abertura: a mesa

BRASAS_ABERTURA = Brasas(40, 1, area=(0, W, H * 0.6, H + 40), vel=(25, 70), tam=(1.0, 2.4))


def abertura(t, dur, M, F):
    troca = M["troca_foto"]
    a = camera("d20", clamp01(t / (troca + 1.1)), zoom=(1.0, 1.12), centro=((0.5, 0.53), (0.5, 0.5)), paralaxe=(70, 10))
    mistura = suave((t - troca) / 1.2)
    if mistura > 0:
        b = camera("mesa", clamp01((t - troca) / max(1.0, dur - troca)), zoom=(1.18, 1.0), centro=((0.54, 0.57), (0.5, 0.5)),
                   paralaxe=(-120, 26))
        base = b if mistura >= 1 else a * (1 - mistura) + b * mistura
    else:
        base = a
    vela = 1 + 0.035 * math.sin(t * 13.1) * math.sin(t * 7.7 + 1)
    entrada = suave(t / 1.8)
    base = graduar(base, exposicao=0.98 * vela * entrada, contraste=1.1, saturacao=1.05, tinta=(1.05, 0.98, 0.9))
    BRASAS_ABERTURA.desenhar(base, t, 0.55 * entrada)
    ui = nova_ui()
    d = ImageDraw.Draw(ui)
    s = "Sexta-feira, 21h."
    th = M["hora"]
    n = int(clamp01((t - th) / 1.1) * len(s))
    texto(d, (150, 214), s[:n], fonte("georgiai.ttf", 42), (242, 228, 204), 1 - suave((t - th - 3.8) / 0.8))
    rol = F[2][0]
    return base, ui, dict(tarjas=1.0, tremor=tremor(t, rol + 0.05, 0.5, 8), flash=0.12 * max(0.0, 1 - (t - rol) / 0.3) if t >= rol else 0)


# ------------------------------------------------------------------ 2. caos: o chat sem controle

MSGS_CAOS = [(0.00, "Bruna", "alguém viu o mapa da caverna?"), (0.13, "Teo", "furtividade: 1d20+4 = 7"),
             (0.25, "Kael", "eu ataco o goblin!!"), (0.36, "Teo", "kkkkkk"), (0.46, "Bruna", "pera, de quem é a vez?"),
             (0.56, "Mestre", "Rodada 2. Ordem: Kael, Aria, Bruna."), (0.66, "Kael", "acertei! 17 de dano"),
             (0.75, "Teo", "volto em 5 min"), (0.84, "Mestre", "Aria? Sua vez."), (0.92, "Bruna", "a Aria saiu?"),
             (1.00, "Mestre", "Rodada 3...")]


@functools.lru_cache(None)
def carimbo_img():
    f = bahn(74, "Bold")
    s = "3 RODADAS DEPOIS"
    lw = f.getlength(s)
    im = Image.new("RGBA", (int(lw + 90), 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, im.width - 8, im.height - 8), 18, outline=(232, 64, 64, 235), width=10)
    d.text((im.width / 2, im.height / 2), s, font=f, fill=(232, 64, 64, 235), anchor="mm")
    return im.rotate(9, expand=True, resample=Image.BICUBIC)


def caos(t, dur, M, F):
    congela = M["congela"]
    te = min(t, congela)
    base = camera("mesa", clamp01(te / dur), zoom=(1.2, 1.28), centro=((0.5, 0.52), (0.52, 0.5)), borrar=16)
    base = graduar(base, exposicao=0.42, contraste=1.05, saturacao=0.9)
    ui = nova_ui()
    f1 = F[1][0]
    msgs = [dict(nome=n, texto=s) for k, n, s in MSGS_CAOS if te >= 0.3 + k * (f1 - 0.8)]
    destaque = None
    if te >= f1:
        destaque = dict(nome="Aria", texto="gente, era a minha vez??")
        msgs.append(destaque)
    if te >= F[3][0]:
        msgs.append(dict(nome="Kael", texto="cadê o meu token??"))
    entra = sai(t / 0.6)
    caixa = (230, 96 + 30 * (1 - entra), 1690, 836 + 30 * (1 - entra))
    janela_vtt(base, ui, caixa, TEMAS["Original"], msgs[-9:], alfa=entra, destaque_msg=destaque, t=t)
    d = ImageDraw.Draw(ui)
    nao_lidas = 3 + len(msgs) * 2
    d.rounded_rectangle((caixa[0] + 140, caixa[1] + 136, caixa[0] + 178, caixa[1] + 162), 13, fill=(232, 64, 64, int(255 * entra)))
    texto(d, (caixa[0] + 159, caixa[1] + 149), str(nao_lidas), ui_fonte(17, True), BRANCO, entra, ancora="mm", sombra=False)
    if t >= M["carimbo"]:
        k = mola((t - M["carimbo"]) / 0.35)
        c = carimbo_img()
        esc = lerp(1.8, 1.0, k)
        c2 = c.resize((int(c.width * esc), int(c.height * esc)), Image.BICUBIC)
        colar(ui, c2, 1180 - c2.width / 2, 470 - c2.height / 2, clamp01((t - M["carimbo"]) / 0.12))
    if t >= M["token_sumiu"]:
        a = sai((t - M["token_sumiu"]) / 0.4)
        cx0, cy0 = 1250, 540 + 30 * (1 - a)
        vidro(base, ui, (cx0, cy0, cx0 + 400, cy0 + 270), alfa=a)
        kx, ky = POS["mapa"]["kael"]["base"]
        mini = recorte("mapa", (int(kx - 330), int(ky - 200), int(kx + 330), int(ky + 200)), (360, 218), 12)
        colar(ui, mini, cx0 + 20, cy0 + 32, a)
        d = ImageDraw.Draw(ui)
        texto(d, (cx0 + 20, cy0 + 6), "Mapa", ui_fonte(20, True), BRANCO, a, sombra=False)
        mx, my = cx0 + 200, cy0 + 141
        for k in range(16):  # circulo tracejado onde o token deveria estar
            a0 = k * 22.5
            d.arc((mx - 34, my - 34, mx + 34, my + 34), a0, a0 + 12, fill=(255, 210, 90, int(255 * a)), width=4)
        texto(d, (mx, my), "?", bahn(44, "Bold"), (255, 210, 90), a, ancora="mm")
    escurece = suave((t - congela) / max(0.2, dur - congela))
    if t > congela:
        cinza = base.mean(axis=2, keepdims=True)
        base = base * 0.3 + cinza * 0.7
    return base, ui, dict(tarjas=0.0, escurecer=escurece, congelado=t > congela)


# ------------------------------------------------------------------ 3. revelacao: o titulo

BRASAS_TITULO = Brasas(90, 3, area=(W * 0.3, W * 0.7, H * 0.35, H * 0.75), vel=(60, 170), tam=(1.4, 3.4), cor=(0.72, 0.4, 1.0))
ESTRELAS = [(x, y, f) for x, y, f in zip(*np.random.default_rng(8).uniform([0, 0, 0], [W, H * 0.62, 6.28], (40, 3)).T)]


def revelacao(t, dur, M, F):
    imp = M["impacto"]
    q = t - imp
    base = camera("ceu", clamp01(t / dur), zoom=(1.2, 1.06), centro=((0.5, 0.62), (0.5, 0.47)))
    exp = 0.32 * suave(t / 1.6) if q < 0 else 0.32 + 0.40 * sai(q / 0.9)
    base = graduar(base, exposicao=exp, contraste=1.18, saturacao=1.15, tinta=(0.94, 0.9, 1.12))
    for x, y, f in ESTRELAS:
        luz_pontual(base, x, y, 1.6, (0.9, 0.92, 1.0), 0.35 * (0.5 + 0.5 * math.sin(t * 3.1 + f * 5)) * suave(t / 1.5))
    ui = nova_ui()
    cx, cy = W / 2, 400
    if q >= 0:
        aura_colocar(base, t, (176, 104, 255), cx, cy, 930 * (0.88 + 0.12 * sai(q / 0.7)), forca=sai(q / 0.35))
        aura_colocar(base, t + 0.4, OURO, cx, cy, 700, forca=0.35 * sai(q / 0.8))
        luz_pontual(base, cx, cy, 240, (0.55, 0.32, 1.0), 0.55 * sai(q / 0.4))
        BRASAS_TITULO.desenhar(base, t, sai(q / 0.5))
        esc = lerp(1.4, 1.0, mola(q / 0.7))
        em = emblema(300)
        em2 = em.resize((int(300 * esc), int(300 * esc)), Image.BICUBIC)
        colar(ui, em2, cx - em2.width / 2, cy - em2.height / 2, sai(q / 0.25))
        marca_texto(ui, cx, 666, 96, alfa=sai((q - 0.3) / 0.5), espac_extra=0.55 * (1 - sai((q - 0.3) / 1.3)),
                    sub="um plugin com superpoderes para a sua mesa", alfa_sub=suave((q - 1.5) / 0.7))
    tarja = 1.0 - suave((t - (dur - 0.9)) / 0.9)
    return base, ui, dict(tarjas=tarja, flash=max(0.0, 1 - q / 0.4) if q >= 0 else 0, tremor=tremor(t, imp, 0.8, 18))


# ------------------------------------------------------------------ 4. cores

MSGS_CORES = [dict(nome="Mestre", texto="Bem-vindos de volta às Ruínas de Avalon!"), dict(nome="Aria", texto="trouxe a ficha nova"),
              dict(nome="Kael", texto="bora!"), dict(nome="Bruna", texto="alguém me manda o mapa?")]
CHIPS = ["Original", "Roxo", "Azul", "Verde", "Âmbar"]


def _chips_pos():
    f = ui_fonte(22, True)
    x, y, out = 1262, 606, {}
    for c in CHIPS:
        w = f.getlength(c) + 34
        if x + w > 1782:
            x, y = 1262, y + 54
        out[c] = (x, y, x + w, y + 42)
        x += w + 10
    return out


CHIPS_POS = _chips_pos()
BOTAO_APLICAR = (1262, 718, 1780, 780)


def cores(t, dur, M, F):
    base = camera("taverna", clamp01(t / dur), zoom=(1.06, 1.14), centro=((0.48, 0.5), (0.52, 0.48)), borrar=14)
    base = graduar(base, exposicao=0.5, contraste=1.04, saturacao=0.85, tinta=(0.96, 0.9, 1.06))
    ui = nova_ui()
    manchete(ui, t, "Do seu jeito.", "Escolha as cores do Firecast — ou use um tema pronto.")
    roxo, aplicar, reabre = M["clique_roxo"], M["clique_aplicar"], M["reabre"]
    # app: tema antigo ate reiniciar; depois do reinicio, roxo
    k_app = suave((t - reabre) / 0.5)
    tema_app = tema_mix("Original", "Roxo", k_app)
    reiniciando = janela(t, aplicar + 0.25, reabre + 0.25, 0.25, 0.35)
    entra = sai((t - 0.2) / 0.6)
    janela_vtt(base, ui, (110, 252, 1150, 838), tema_app, MSGS_CORES, alfa=entra * (1 - 0.82 * reiniciando))
    d = ImageDraw.Draw(ui)
    if reiniciando > 0.01:
        cx, cy = 630, 545
        for k in range(10):
            ang = t * 360 + k * 36
            al = (k + 1) / 10 * reiniciando
            d.arc((cx - 38, cy - 38, cx + 38, cy + 38), ang, ang + 22, fill=(255, 255, 255, int(255 * al)), width=6)
        texto(d, (cx, cy + 74), "Reiniciando o Firecast...", ui_fonte(28, True), BRANCO, reiniciando, ancora="mm")
    # janela /cores
    dlg = sai((t - 0.5) / 0.6)
    vidro(base, ui, (1230, 252, 1810, 838), alfa=dlg)
    d = ImageDraw.Draw(ui)
    texto(d, (1262, 290), "Cores do Firecast", ui_fonte(32, True), BRANCO, dlg)
    texto(d, (1262, 336), "/cores", fonte("consola.ttf", 20), (180, 170, 210), dlg)
    k_prev = suave((t - roxo) / 0.35)
    tema_prev = tema_mix("Original", "Roxo", k_prev)
    for i, (rot, chave) in enumerate([("Destaque", "destaque"), ("Fundo", "fundo"), ("Texto", "texto")]):
        y = 386 + 64 * i
        texto(d, (1262, y + 20), rot, ui_fonte(25), (230, 226, 240), dlg, ancora="lm")
        cor = tema_prev[chave]
        d.rounded_rectangle((1530, y, 1780, y + 42), 10, fill=cor + (int(255 * dlg),), outline=(255, 255, 255, int(70 * dlg)), width=2)
        hexa = "#%02X%02X%02X" % cor
        texto(d, (1655, y + 21), hexa, fonte("consola.ttf", 20), BRANCO if sum(cor) < 400 else (20, 20, 20), dlg, ancora="mm", sombra=False)
    texto(d, (1262, 586), "Temas prontos", ui_fonte(20, True), (190, 182, 214), dlg, ancora="lm")
    for c, (x0, y0, x1, y1) in CHIPS_POS.items():
        sel = c == "Roxo" and t >= roxo
        fill = TEMAS[c]["destaque"] + (int((255 if sel else 60) * dlg),)
        d.rounded_rectangle((x0, y0, x1, y1), 21, fill=fill, outline=TEMAS[c]["destaque"] + (int(255 * dlg),), width=2)
        texto(d, ((x0 + x1) / 2, (y0 + y1) / 2), c, ui_fonte(22, True), BRANCO, dlg, ancora="mm", sombra=False)
    x0, y0, x1, y1 = BOTAO_APLICAR
    apertado = 0 <= t - aplicar < 0.15
    d.rounded_rectangle((x0, y0 + (3 if apertado else 0), x1, y1), 14, fill=tema_prev["destaque"] + (int(255 * dlg),))
    texto(d, ((x0 + x1) / 2, (y0 + y1) / 2 + (3 if apertado else 0)), "Aplicar e reiniciar", ui_fonte(26, True), BRANCO, dlg, ancora="mm")
    texto(d, ((x0 + x1) / 2, 808), "Restaurar original", ui_fonte(21), (180, 172, 204), dlg, ancora="mm")
    # cursor
    rx = (CHIPS_POS["Roxo"][0] + CHIPS_POS["Roxo"][2]) / 2
    ry = (CHIPS_POS["Roxo"][1] + CHIPS_POS["Roxo"][3]) / 2
    pts = [(0, 1900, 1040), (roxo - 0.9, 1880, 1000), (roxo - 0.05, rx + 6, ry + 4), (aplicar - 0.7, rx + 6, ry + 4),
           (aplicar - 0.05, (x0 + x1) / 2 + 40, (y0 + y1) / 2 + 6), (reabre + 0.4, (x0 + x1) / 2 + 40, (y0 + y1) / 2 + 6),
           (reabre + 1.4, 1880, 1040)]
    px, py = caminho_cursor(t, pts)
    clique = roxo if abs(t - roxo) < abs(t - aplicar) else aplicar
    cursor(ui, px, py, clique=clique, t=t, alfa=janela(t, roxo - 1.0, reabre + 1.4, 0.3, 0.4))
    aviso(base, ui, 1300, 112, ROXO, "Firecast atualizado", "A sua skin foi reaplicada sozinha", alfa=janela(t, M["atualizou"], M["atualizou"] + 2.8))
    return base, ui, dict(tarjas=0.0)


# ------------------------------------------------------------------ 5. aura no token

COR_AURA = [(176, 104, 255), (255, 186, 72), (90, 212, 255)]


@functools.lru_cache(None)
def mascara_kael():
    a = np.asarray(Image.open(os.path.join(RENDER, "mascara_kael.png")).getchannel("A"), np.float32) / 255
    return np.repeat(a[..., None], 3, axis=2).astype(np.float16)


class BrasasLocais(Brasas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)

    def em(self, arr, t, intensidade, dx, dy, cor):
        self.cor = cor
        x0, y0 = self.x0.copy(), self.y0.copy()
        self.x0, self.y0 = x0 + dx, y0 + dy
        self.desenhar(arr, t, intensidade)
        self.x0, self.y0 = x0, y0


BRASAS_AURA = BrasasLocais(60, 4, area=(-160, 160, -40, 140), vel=(50, 140), tam=(1.2, 3.0))


def aura(t, dur, M, F):
    kx, ky = POS["mapa"]["kael"]["base"]
    fw, fh = foto("mapa").shape[1], foto("mapa").shape[0]
    k = sai(clamp01(t / (M["acende"] + 0.6)))
    z = lerp(1.0, 1.62, k) * (1 + 0.04 * clamp01(t / dur))
    cxy = (lerp(0.5, kx / fw, k), lerp(0.5, ky / fh, k) - 0.03 * k)
    g = lerp(-3.0, 2.0, clamp01(t / dur))
    params = dict(zoom=(z, z), centro=(cxy, cxy), giro=(g, g))
    foto_ = camera("mapa", 0.5, **params)
    escurece = 0.22 * sai((t - M["acende"] + 0.2) / 0.6)  # a magia "apaga a luz" da sala
    base = graduar(foto_, exposicao=0.92 - escurece, contraste=1.08, saturacao=1.05, tinta=(1.02, 0.98, 0.94))
    tx, ty = projetar("mapa", 0.5, kx, ky, **params)
    token_px = 103 * (W / fw) * z
    acende = M["acende"]
    if t >= acende:
        q = t - acende
        # cor e tamanho mudam nas marcas cor1 e cor2
        i = 0 if t < M["cor1"] else (1 if t < M["cor2"] else 2)
        ti = [acende, M["cor1"], M["cor2"]][i]
        mud = suave((t - ti) / 0.45)
        tam = (1.0 if i < 2 else 1.3) if t < M["cor2"] else lerp(1.0, 1.3, mud)
        larg = token_px / 0.34 * 1.15 * tam * (0.6 + 0.4 * sai(q / 0.5))
        forca = sai(q / 0.3)
        if i > 0 and mud < 1:
            aura_colocar(base, t, COR_AURA[i - 1], tx, ty, larg, forca * (1 - mud), tela=True)
        aura_colocar(base, t, COR_AURA[i], tx, ty, larg, forca * (mud if i > 0 else 1), tela=True)
        cor_b = tuple(c / 255 for c in COR_AURA[i])
        BRASAS_AURA.em(base, t, forca, tx, ty - token_px * 0.4, cor_b)
        luz_pontual(base, tx, ty, token_px * 1.6, cor_b, 0.9 * max(0.0, 1 - q / 0.6))
        m = camera("mapa", 0.5, img=mascara_kael(), **params)
        base = base * (1 - m) + graduar(foto_, exposicao=0.92 - escurece * 0.5, contraste=1.08) * m  # cavaleiro na frente
    ui = nova_ui()
    manchete(ui, t, "Aura no mapa.", "Chamas animadas em qualquer token.")
    d = ImageDraw.Draw(ui)
    f2 = F[2][0]
    a = sai((t - f2 + 0.3) / 0.5)
    if a > 0.01:
        cx0, cy0 = 1420, 300
        vidro(base, ui, (cx0, cy0, cx0 + 390, cy0 + 420), alfa=a)
        d = ImageDraw.Draw(ui)
        texto(d, (cx0 + 28, cy0 + 26), "Aura do token", ui_fonte(28, True), BRANCO, a)
        texto(d, (cx0 + 28, cy0 + 96), "Cor", ui_fonte(22), (210, 204, 228), a)
        i = 0 if t < M["cor1"] else (1 if t < M["cor2"] else 2)
        for j, c in enumerate(COR_AURA):
            x = cx0 + 150 + j * 66
            d.ellipse((x, cy0 + 86, x + 44, cy0 + 130), fill=c + (int(255 * a),))
            if j == i:
                d.ellipse((x - 6, cy0 + 80, x + 50, cy0 + 136), outline=(255, 255, 255, int(255 * a)), width=3)
        texto(d, (cx0 + 28, cy0 + 176), "Tamanho", ui_fonte(22), (210, 204, 228), a)
        sel = 1 if t < M["cor2"] else 2
        for j, rot in enumerate(["P", "M", "G", "GG"]):
            x = cx0 + 150 + j * 54
            d.rounded_rectangle((x, cy0 + 164, x + 46, cy0 + 206), 9, fill=(COR_AURA[i] if j == sel else (60, 54, 80)) + (int(255 * a),))
            texto(d, (x + 23, cy0 + 185), rot, ui_fonte(20, True), BRANCO, a, ancora="mm", sombra=False)
        texto(d, (cx0 + 28, cy0 + 252), "Intensidade", ui_fonte(22), (210, 204, 228), a)
        for j in range(3):
            x = cx0 + 190 + j * 40
            hh = 16 + j * 12
            d.rounded_rectangle((x, cy0 + 278 - hh, x + 26, cy0 + 278), 5, fill=(COR_AURA[i] if j <= 1 + (t >= M["cor2"]) else (60, 54, 80)) + (int(255 * a),))
        d.rounded_rectangle((cx0 + 28, cy0 + 324, cx0 + 362, cy0 + 380), 13, fill=COR_AURA[i] + (int(255 * a),))
        texto(d, (cx0 + 195, cy0 + 352), "Aplicar", ui_fonte(25, True), (20, 16, 28), a, ancora="mm", sombra=False)
    b = sai((t - M["todos"]) / 0.45)
    if b > 0.01:
        vidro(base, ui, (1150, 120, 1810, 236), alfa=b)
        d = ImageDraw.Draw(ui)
        for j, n in enumerate(["Mestre", "Aria", "Kael", "Bruna"]):
            x = 1196 + j * 64
            avatar(d, x, 160, 22, n, b)
            d.ellipse((x + 10, 172, x + 30, 192), fill=(70, 200, 110, int(255 * b)))
            d.line((x + 14, 182, x + 19, 187, x + 27, 177), fill=(255, 255, 255, int(255 * b)), width=3)
        texto(d, (1460, 152), "Todo mundo vê", ui_fonte(26, True), BRANCO, b, ancora="lm")
        texto(d, (1460, 186), "até quem não tem o plugin", ui_fonte(21), (210, 204, 228), b, ancora="lm")
    return base, ui, dict(tarjas=0.0, flash=0.25 * max(0.0, 1 - (t - acende) / 0.3) if t >= acende else 0)


# ------------------------------------------------------------------ 6. chat esperto

@functools.lru_cache(None)
def miniatura_video():
    im = recorte("taverna", (300, 250, 2000, 1206), (380, 214), 12).copy()
    d = ImageDraw.Draw(im)
    escuro = Image.new("RGBA", im.size, (0, 0, 0, 70))
    im.alpha_composite(escuro)
    d = ImageDraw.Draw(im)
    cx, cy = im.width / 2, im.height / 2
    d.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=(232, 64, 64, 240))
    d.polygon([(cx - 11, cy - 17), (cx - 11, cy + 17), (cx + 19, cy)], fill=(255, 255, 255, 255))
    d.rounded_rectangle((im.width - 84, im.height - 36, im.width - 10, im.height - 10), 6, fill=(0, 0, 0, 190))
    d.text((im.width - 47, im.height - 23), "1:00:00", font=ui_fonte(17, True), fill=(255, 255, 255, 255), anchor="mm")
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 12, fill=255)
    im.putalpha(m)
    return im


def chat(t, dur, M, F):
    base = camera("rua", clamp01(t / dur), zoom=(1.05, 1.13), centro=((0.5, 0.5), (0.47, 0.5)), borrar=12)
    base = graduar(base, exposicao=0.42, contraste=1.06, saturacao=0.9, tinta=(0.92, 0.98, 1.08))
    ui = nova_ui()
    d = ImageDraw.Draw(ui)
    a = sai((t - 0.15) / 0.6)
    texto(d, (1060 + 40 * (1 - a), 64), "Chat esperto.", titulo_fonte(78), BRANCO, a)
    for i, (ref, s) in enumerate([(F[1][0], "Aviso sonoro quando falam de você"), (F[3][0], "Prévia de imagens e vídeos no chat")]):
        b = sai((t - ref) / 0.5)
        y = 186 + 52 * i
        d.ellipse((1066, y + 10, 1082, y + 26), fill=CIANO + (int(255 * b),))
        texto(d, (1098 - 20 * (1 - b), y + 18), s, ui_fonte(30), (230, 226, 240), b, ancora="lm")
    # painel de chat
    entra = sai(t / 0.6)
    vidro(base, ui, (110, 96, 990, 846), alfa=entra, opac=0.82)
    d = ImageDraw.Draw(ui)
    texto(d, (142, 128), "Chat da mesa", ui_fonte(26, True), BRANCO, entra)
    msgs = [(0.25, "Mestre", "Vocês chegam à entrada da caverna.", None), (0.95, "Bruna", "boa noite, mesa!", None),
            (1.6, "Teo", "trouxe biscoito pra todo mundo", None),
            (M["mencao"], "Kael", "Aria, cura aqui que eu tô caindo!", "mencao"),
            (M["link_img"], "Bruna", "olha o mapa que eu achei: i.imgur.com/caverna.png", "imagem"),
            (M["link_vid"], "Teo", "trilha pra hoje: youtu.be/taverna", "video")]
    blocos = []
    for ta, n, s, tipo in msgs:
        if t < ta:
            continue
        f = ui_fonte(22)
        linhas = quebrar(s, f, 720)
        alt = 40 + 30 * len(linhas) + (236 if tipo in ("imagem", "video") else 0) + 18
        blocos.append((ta, n, s, tipo, linhas, alt))
    total = sum(b[5] for b in blocos)
    y = 172 - max(0, total - 640)  # rola para cima quando enche
    chat_ui = ui
    ui = nova_ui()
    d = ImageDraw.Draw(ui)
    for ta, n, s, tipo, linhas, alt in blocos:
        k = sai((t - ta) / 0.35)
        yy = y + 18 * (1 - k)
        if yy + alt < 160:
            y += alt
            continue
        if tipo == "mencao":
            pulso = 0.5 + 0.5 * math.sin((t - ta) * 8)
            d.rounded_rectangle((128, yy - 6, 972, yy + alt - 18), 12, fill=CIANO + (int(40 + 40 * pulso * k),), outline=CIANO + (int(220 * k),), width=2)
            bx, by = 930, yy + 26
            d.ellipse((bx - 20, by - 20, bx + 20, by + 20), fill=CIANO + (int(255 * k),))
            d.polygon([(bx - 9, by + 7), (bx + 9, by + 7), (bx + 6, by - 8), (bx, by - 12), (bx - 6, by - 8)], fill=(20, 30, 40, int(255 * k)))
        avatar(d, 160, yy + 24, 20, n, k)
        texto(d, (194, yy + 6), n, ui_fonte(21, True), AVATAR_CORES.get(n, BRANCO), k, sombra=False)
        for i, l in enumerate(linhas):
            xx = 194
            if tipo == "mencao" and "Aria" in l:  # realce na palavra-chave
                pre = l.split("Aria")[0]
                fx = ui_fonte(22)
                ax = xx + fx.getlength(pre)
                d.rounded_rectangle((ax - 4, yy + 34 + 30 * i, ax + fx.getlength("Aria") + 4, yy + 64 + 30 * i), 6, fill=CIANO + (int(200 * k),))
            if tipo in ("imagem", "video") and ("imgur" in l or "youtu" in l):
                texto(d, (xx, yy + 36 + 30 * i), l, ui_fonte(22), (130, 190, 255), k, sombra=False)
            else:
                texto(d, (xx, yy + 36 + 30 * i), l, ui_fonte(22), (238, 236, 244), k, sombra=False)
        if tipo == "imagem":
            colar(ui, recorte("torre", (500, 120, 1950, 936), (380, 214), 12), 194, yy + 46 + 30 * len(linhas), k)
        if tipo == "video":
            colar(ui, miniatura_video(), 194, yy + 46 + 30 * len(linhas), k)
            texto(d, (590, yy + 60 + 30 * len(linhas)), "Trilha de taverna", ui_fonte(22, True), BRANCO, k, sombra=False)
            texto(d, (590, yy + 92 + 30 * len(linhas)), "1 hora de música", ui_fonte(20), (190, 186, 210), k, sombra=False)
        y += alt
    janela_msgs = Image.new("L", (W, H), 0)  # so a area de mensagens do painel, com o topo esmaecendo
    jd = ImageDraw.Draw(janela_msgs)
    jd.rectangle((110, 196, 990, 846), fill=255)
    for k2 in range(36):
        jd.line((110, 160 + k2, 990, 160 + k2), fill=int(255 * k2 / 36))
    ui.putalpha(ImageChops.multiply(ui.getchannel("A"), janela_msgs))
    chat_ui.alpha_composite(ui)
    ui = chat_ui
    # palavra-chave sendo cadastrada
    dg = M["digita_nome"]
    c = janela(t, dg - 0.4, M["mencao"] + 2.2, 0.4, 0.5)
    if c > 0.01:
        vidro(base, ui, (1060, 330, 1760, 560), alfa=c)
        d = ImageDraw.Draw(ui)
        texto(d, (1090, 360), "Beep por palavra", ui_fonte(26, True), BRANCO, c)
        d.rounded_rectangle((1090, 410, 1560, 462), 10, fill=(255, 255, 255, int(28 * c)), outline=(255, 255, 255, int(80 * c)), width=2)
        digitado = "Aria"[:int(clamp01((t - dg) / 0.6) * 4)]
        texto(d, (1106, 436), digitado + ("|" if int(t * 3) % 2 == 0 and t < dg + 1.2 else ""), ui_fonte(26), BRANCO, c, ancora="lm", sombra=False)
        d.rounded_rectangle((1576, 410, 1730, 462), 10, fill=CIANO + (int(255 * c),))
        texto(d, (1653, 436), "Adicionar", ui_fonte(22, True), (16, 24, 32), c, ancora="mm", sombra=False)
        chips = ["Heaven"] + (["Aria"] if t > dg + 0.9 else [])
        x = 1090
        for ch in chips:
            w = ui_fonte(22, True).getlength(ch) + 32
            k2 = sai((t - dg - 0.9) / 0.3) if ch == "Aria" else 1
            d.rounded_rectangle((x, 486, x + w, 528), 21, fill=CIANO + (int(200 * c * k2),))
            texto(d, (x + w / 2, 507), ch, ui_fonte(22, True), (16, 24, 32), c * k2, ancora="mm", sombra=False)
            x += w + 10
    aviso(base, ui, 1250, 600, CIANO, "Mencionaram você", "Kael: Aria, cura aqui...", alfa=janela(t, M["mencao"], M["mencao"] + 2.6))
    return base, ui, dict(tarjas=0.0)


# ------------------------------------------------------------------ 7. ferramentas do mestre

TURNOS = [("Kael", 18), ("Aria", 15), ("Bruna", 12), ("Goblin", 9)]
BOTAO_PROX = (140, 712, 590, 784)


def mestre(t, dur, M, F):
    base = camera("torre", clamp01(t / dur), zoom=(1.04, 1.14), centro=((0.5, 0.5), (0.53, 0.47)), borrar=6)
    base = graduar(base, exposicao=0.55, contraste=1.1, saturacao=0.9, tinta=(0.92, 0.95, 1.08))
    ui = nova_ui()
    manchete(ui, t, "Para o mestre.", "Turnos, tokens e avisos — sem bagunça.")
    cp = M["clique_prox"]
    # painel de turnos
    a = sai(t / 0.6)
    vidro(base, ui, (110, 232, 620, 818), alfa=a)
    d = ImageDraw.Draw(ui)
    texto(d, (140, 268), "Ordem de turnos", ui_fonte(30, True), BRANCO, a)
    d.rounded_rectangle((470, 252, 590, 290), 19, fill=ROXO + (int(220 * a),))
    texto(d, (530, 271), "Rodada 3", ui_fonte(19, True), BRANCO, a, ancora="mm", sombra=False)
    sel = lerp(0, 1, sai((t - cp - 0.05) / 0.3))
    yb = 338 + 84 * sel
    d.rounded_rectangle((128, yb - 6, 602, yb + 66), 14, fill=OURO + (int(60 * a),), outline=OURO + (int(230 * a),), width=3)
    for i, (n, ini) in enumerate(TURNOS):
        y = 338 + 84 * i
        avatar(d, 172, y + 30, 24, n, a)
        texto(d, (212, y + 30), n, ui_fonte(28, True), BRANCO, a, ancora="lm")
        texto(d, (575, y + 30), str(ini), bahn(34, "Bold"), (230, 220, 250), a, ancora="rm")
    x0, y0, x1, y1 = BOTAO_PROX
    ap = 0 <= t - cp < 0.15
    d.rounded_rectangle((x0, y0 + (3 if ap else 0), x1, y1), 14, fill=ROXO + (int(255 * a),))
    texto(d, ((x0 + x1) / 2, (y0 + y1) / 2 + (3 if ap else 0)), "Próximo turno", ui_fonte(28, True), BRANCO, a, ancora="mm")
    # mensagem no chat
    b = sai((t - cp - 0.15) / 0.4)
    if b > 0.01:
        vidro(base, ui, (680, 232, 1240, 392), alfa=b)
        d = ImageDraw.Draw(ui)
        texto(d, (708, 258), "Chat da mesa", ui_fonte(22, True), (200, 194, 220), b)
        avatar(d, 728, 330, 22, "Mestre", b)
        texto(d, (764, 312), "Mestre", ui_fonte(22, True), AVATAR_CORES["Mestre"], b, sombra=False)
        texto(d, (764, 342), "Vez de: Aria", ui_fonte(26), BRANCO, b, sombra=False)
    # tela da Aria
    av = M["aviso"]
    c = sai((t - av) / 0.35) * (1 - 0.35 * suave((t - F[3][0]) / 0.6))
    if c > 0.01:
        vidro(base, ui, (1300, 232, 1810, 640), alfa=c)
        d = ImageDraw.Draw(ui)
        texto(d, (1328, 258), "Na tela da Aria", ui_fonte(22, True), (200, 194, 220), c)
        q = t - av
        for k in range(3):
            fase = (q * 0.9 + k / 3) % 1
            r = 60 + 160 * fase
            d.ellipse((1555 - r, 440 - r, 1555 + r, 440 + r), outline=OURO + (int(160 * (1 - fase) * c),), width=3)
        brilho = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        texto(ImageDraw.Draw(brilho), (1555, 440), "É A SUA VEZ!", bahn(66, "Bold"), OURO, c, ancora="mm", sombra=False)
        ui.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(12)))
        esc = 1 + 0.04 * math.sin(q * 7)
        texto(ImageDraw.Draw(ui), (1555, 440), "É A SUA VEZ!", bahn(int(66 * esc), "Bold"), (255, 236, 190), c, ancora="mm")
    # meu token no mini-mapa
    f4 = F[4][0]
    e = janela(t, f4 - 0.3, dur, 0.4, 0.3)
    tk = M["token"]
    if e > 0.01:
        vidro(base, ui, (680, 430, 1240, 818), alfa=e)
        d = ImageDraw.Draw(ui)
        texto(d, (708, 456), "Mapa  ·  Meu token", ui_fonte(22, True), (200, 194, 220), e)
        cx, cy = POS["mapa"]["kael"]["base"]
        mini = recorte("mapa", (int(cx - 560), int(cy - 300), int(cx + 560), int(cy + 340)), (504, 288), 12)
        colar(ui, mini, 708, 500, e)
        mx, my = 1010, 640
        if t >= tk:
            q = t - tk
            k = mola(q / 0.35)
            r = 30 * k
            for j in range(10):
                ang = j * 36
                rr = 30 + 60 * sai(q / 0.5)
                px, py = mx + rr * math.cos(math.radians(ang)), my + rr * math.sin(math.radians(ang))
                d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(220, 210, 190, int(200 * (1 - clamp01(q / 0.5)) * e)))
            d.ellipse((mx - r - 4, my - r - 4, mx + r + 4, my + r + 4), fill=OURO + (int(255 * e),))
            avatar(d, mx, my, max(1, r), "Bruna", e)
        pts = [(f4 - 0.3, 900, 900), (tk - 0.05, mx + 8, my + 6), (tk + 0.8, mx + 8, my + 6), (tk + 1.6, 1260, 900)]
        cursor(ui, *caminho_cursor(t, pts), clique=tk, t=t, alfa=janela(t, f4 - 0.2, tk + 1.6, 0.3, 0.4))
    # barra de tarefas: so a mesa A pisca
    f5 = F[5][0]
    g = sai((t - f5 + 0.2) / 0.4)
    if g > 0.01:
        vidro(base, ui, (1300, 676, 1810, 818), alfa=g)
        d = ImageDraw.Draw(ui)
        pisca = 0.5 + 0.5 * math.sin((t - M["pisca"]) * 8) if t >= M["pisca"] else 0
        for j, n in enumerate(["Mesa A", "Mesa B", "Mesa C"]):
            x = 1340 + j * 156
            cor = mix_cor((70, 64, 90), (255, 150, 40), pisca if j == 0 else 0)
            d.rounded_rectangle((x, 694, x + 64, 758), 14, fill=cor + (int(255 * g),))
            texto(d, (x + 32, 726), "F", bahn(34, "Bold"), BRANCO, g, ancora="mm", sombra=False)
            texto(d, (x + 32, 786), n, ui_fonte(20, True), (220, 214, 236), g, ancora="mm")
            if j:
                d.ellipse((x + 46, 688, x + 74, 716), fill=(40, 36, 56, int(255 * g)), outline=(200, 194, 220, int(255 * g)), width=2)
                d.line((x + 52, 694, x + 68, 710), fill=(255, 120, 120, int(255 * g)), width=3)
    pts = [(0, 900, 1000), (cp - 0.7, 700, 900), (cp - 0.05, (x0 + x1) / 2 + 30, (y0 + y1) / 2 + 6), (cp + 0.6, (x0 + x1) / 2 + 30, (y0 + y1) / 2 + 6), (cp + 1.4, 760, 1040)]
    cursor(ui, *caminho_cursor(t, pts), clique=cp, t=t, alfa=janela(t, cp - 1.0, cp + 1.4, 0.3, 0.4))
    return base, ui, dict(tarjas=0.0)


# ------------------------------------------------------------------ 8. instalar

PASSOS = [("Feche o Firecast", "inclusive o ícone perto do relógio"), ("Rode o instalar.bat", "ele copia o plugin para você"),
          ("Abra pelo atalho", "Firecast Plus, na área de trabalho")]


def icone_passo(ui, d, i, cx, cy, a):
    al = int(255 * a)
    if i == 0:
        d.rounded_rectangle((cx - 56, cy - 40, cx + 56, cy + 40), 10, outline=(230, 226, 240, al), width=5)
        d.line((cx - 56, cy - 22, cx + 56, cy - 22), fill=(230, 226, 240, al), width=5)
        d.line((cx - 18, cy - 8, cx + 18, cy + 28), fill=(255, 110, 110, al), width=7)
        d.line((cx + 18, cy - 8, cx - 18, cy + 28), fill=(255, 110, 110, al), width=7)
    elif i == 1:
        d.polygon([(cx - 40, cy - 52), (cx + 18, cy - 52), (cx + 40, cy - 30), (cx + 40, cy + 52), (cx - 40, cy + 52)], outline=(230, 226, 240, al), width=5)
        d.line((cx + 18, cy - 52, cx + 18, cy - 30, cx + 40, cy - 30), fill=(230, 226, 240, al), width=5)
        texto(d, (cx, cy + 14), ".bat", fonte("consola.ttf", 28), OURO, a, ancora="mm", sombra=False)
    else:
        em = emblema(110)
        if a < 1:
            em = em.copy()
            em.putalpha(em.getchannel("A").point(lambda v: int(v * a)))
        ui.alpha_composite(em, (int(cx - 55), int(cy - 55)))
        d.rounded_rectangle((cx + 18, cy + 18, cx + 54, cy + 54), 8, fill=(255, 255, 255, al))
        d.line((cx + 26, cy + 46, cx + 46, cy + 26), fill=(30, 30, 40, al), width=5)
        d.line((cx + 32, cy + 26, cx + 46, cy + 26, cx + 46, cy + 40), fill=(30, 30, 40, al), width=5)


def instalar(t, dur, M, F):
    base = camera("diario", clamp01(t / dur), zoom=(1.14, 1.02), centro=((0.56, 0.52), (0.5, 0.5)), paralaxe=(100, 24))
    base = graduar(base, exposicao=0.5, contraste=1.05, saturacao=0.95)
    ui = nova_ui()
    manchete(ui, t, "Instalar é simples.", "Três passos e pronto.")
    pronto = M["pronto"]
    for i, (tit, sub) in enumerate(PASSOS):
        ti = M[f"passo{i + 1}"]
        a = sai((t - ti + 0.15) / 0.45)
        if a <= 0.01:
            continue
        x0 = 140 + i * 560
        y0 = 330 + 40 * (1 - a)
        vidro(base, ui, (x0, y0, x0 + 520, y0 + 400), alfa=a)
        d = ImageDraw.Draw(ui)
        d.ellipse((x0 + 26, y0 + 26, x0 + 86, y0 + 86), fill=OURO + (int(255 * a),))
        texto(d, (x0 + 56, y0 + 57), str(i + 1), bahn(38, "Bold"), (30, 20, 10), a, ancora="mm", sombra=False)
        icone_passo(ui, d, i, x0 + 260, y0 + 150, a)
        texto(d, (x0 + 260, y0 + 266), tit, ui_fonte(34, True), BRANCO, a, ancora="mm")
        texto(d, (x0 + 260, y0 + 314), sub, ui_fonte(24), (210, 204, 228), a, ancora="mm")
        if t >= pronto:
            k = mola((t - pronto - i * 0.08) / 0.3)
            if k > 0:
                cx, cy, r = x0 + 470, y0 + 52, 26 * k
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(70, 200, 110, int(255 * a)))
                d.line((cx - 11 * k, cy, cx - 3 * k, cy + 9 * k, cx + 12 * k, cy - 9 * k), fill=(255, 255, 255, int(255 * a)), width=5)
    return base, ui, dict(tarjas=0.0)


# ------------------------------------------------------------------ 9. final

@functools.lru_cache(None)
def degrade_esquerda():
    x = np.linspace(0, 1, W, dtype=np.float32)
    return (1 - 0.78 * np.clip(1 - x / 0.62, 0, 1) ** 1.6)[None, :, None]


BRASAS_FINAL = Brasas(50, 6, area=(150, 800, 300, 700), vel=(40, 110), tam=(1.0, 2.8), cor=(0.72, 0.42, 1.0))
BRASAS_CRIT = Brasas(70, 7, area=(-120, 120, -60, 60), vel=(80, 260), tam=(1.4, 3.6), cor=(1.0, 0.78, 0.3))


def final(t, dur, M, F):
    params = dict(zoom=(1.0, 1.1), centro=((0.52, 0.52), (0.56, 0.5)))
    k = clamp01(t / dur)
    base = camera("final", k, paralaxe=(-130, 10), **params)
    base = graduar(base, exposicao=0.78, contraste=1.12, saturacao=1.05, tinta=(1.02, 0.95, 0.9)) * degrade_esquerda()
    cx, cy = 470, 320
    aura_colocar(base, t, (176, 104, 255), cx, cy, 640, forca=sai((t - 0.2) / 0.8))
    BRASAS_FINAL.desenhar(base, t, sai((t - 0.3) / 0.8))
    p = POS["final"]["d20"]
    dx, dy = projetar("final", k, (p["base"][0] + p["topo"][0]) / 2, (p["base"][1] + p["topo"][1]) / 2, **params)
    crit = M["critico"]
    if t >= crit:
        q = t - crit
        luz_pontual(base, dx, dy - 40, 220, (1.0, 0.75, 0.3), 0.8 * max(0.0, 1 - q / 1.2) + 0.2)
        x0, y0 = BRASAS_CRIT.x0.copy(), BRASAS_CRIT.y0.copy()
        BRASAS_CRIT.x0, BRASAS_CRIT.y0 = x0 + dx, y0 + dy - 60
        BRASAS_CRIT.desenhar(base, q * 2.2, max(0.0, 1 - q / 2.0))
        BRASAS_CRIT.x0, BRASAS_CRIT.y0 = x0, y0
    ui = nova_ui()
    a = sai((t - 0.3) / 0.7)
    em = emblema(240)
    colar(ui, em, cx - 120, cy - 120, a)
    marca_texto(ui, cx, 548, 78, alfa=sai((t - 0.6) / 0.7), espac_extra=0.3 * (1 - sai((t - 0.6) / 1.2)))
    d = ImageDraw.Draw(ui)
    b = sai((t - F[1][0]) / 0.6)
    texto(d, (cx, 630), "Para mestres e jogadores", ui_fonte(32), (232, 226, 244), b, ancora="mm")
    texto(d, (cx, 674), "que querem mais da sua mesa.", ui_fonte(32), (232, 226, 244), b, ancora="mm")
    if t >= crit:
        q = t - crit
        k2 = mola(q / 0.4)
        brilho = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        texto(ImageDraw.Draw(brilho), (dx, dy - 228), "20", titulo_fonte(int(150 * k2) + 1), OURO, 1.0, ancora="mm", sombra=False)
        ui.alpha_composite(brilho.filter(ImageFilter.GaussianBlur(14)))
        d = ImageDraw.Draw(ui)
        texto(d, (dx, dy - 228), "20", titulo_fonte(int(150 * k2) + 1), (255, 228, 160), clamp01(q / 0.15), ancora="mm")
        texto(d, (dx, dy - 338), "CRÍTICO!", bahn(40, "Bold"), OURO, sai((q - 0.2) / 0.4), ancora="mm", espac=6)
    texto(d, (W / 2 + 230, 930), "Boa sessão.", fonte("georgiai.ttf", 64), (246, 236, 214), sai((t - M["boa"]) / 0.8), ancora="mm")
    fim = suave((t - (dur - 1.0)) / 1.0)
    return base, ui, dict(tarjas=suave((t - (dur - 2.6)) / 1.2), flash=0.6 * max(0.0, 1 - (t - crit) / 0.35) if t >= crit else 0,
                          tremor=tremor(t, M["dados"] + 0.2, 1.2, 5), escurecer=fim)


# ------------------------------------------------------------------ 10. creditos

BRASAS_CRED = Brasas(30, 9, area=(0, W, H * 0.7, H + 40), vel=(20, 60), tam=(1.0, 2.2), cor=(0.7, 0.4, 1.0))
CREDITOS = ["Plugin para o Firecast 8, feito com o sistema oficial de plugins",
            "Cena 3D renderizada no Blender  ·  HDRIs e modelos: Poly Haven (CC0)",
            "Vozes sintéticas geradas no PC (Chatterbox + Kokoro)  ·  Trilha e efeitos gerados por código",
            "Plugin por momotorogames"]


def creditos(t, dur, M, F):
    base = np.zeros((H, W, 3), np.float32)
    aparece = suave(t / 0.8) * (1 - suave((t - (dur - 1.0)) / 1.0))
    aura_colocar(base, t, (150, 90, 230), W / 2, 330, 420, forca=0.6 * aparece)
    BRASAS_CRED.desenhar(base, t, 0.6 * aparece)
    ui = nova_ui()
    em = emblema(150)
    colar(ui, em, W / 2 - 75, 330 - 75, aparece)
    marca_texto(ui, W / 2, 490, 58, alfa=aparece)
    d = ImageDraw.Draw(ui)
    for i, s in enumerate(CREDITOS):
        texto(d, (W / 2, 600 + 50 * i), s, ui_fonte(27), (196, 190, 214), aparece * sai((t - 0.3 - 0.15 * i) / 0.6), ancora="mm")
    return base, ui, dict(tarjas=0.0)


CENAS = {"abertura": abertura, "caos": caos, "revelacao": revelacao, "cores": cores, "aura": aura, "chat": chat,
         "mestre": mestre, "instalar": instalar, "final": final, "creditos": creditos}
SEM_FUSAO = {("caos", "revelacao"), ("final", "creditos")}  # cortes secos (a cena anterior ja termina no preto)
