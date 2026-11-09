"""Audio do trailer 3, todo sintetizado aqui (numpy/scipy): tratamento das vozes, trilha original, efeitos e mix.

Nada de amostras de terceiros: instrumentos sao osciladores, ruido filtrado e Karplus-Strong (corda dedilhada).
Tudo em 48 kHz, estereo, arrays float32 de forma (n, 2).
"""
import math

import numpy as np
from scipy import signal

SR = 48000
RNG = np.random.default_rng(2026)


# ------------------------------------------------------------------ basicos

def seg(s):
    return int(round(s * SR))


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def nota(nome):
    """'D4' -> midi. Sustenido com #, bemol com b."""
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[nome[0]]
    resto = nome[1:]
    if resto.startswith("#"):
        base, resto = base + 1, resto[1:]
    elif resto.startswith("b"):
        base, resto = base - 1, resto[1:]
    return 12 * (int(resto) + 1) + base


def filtro(x, tipo, corte, ordem=2):
    sos = signal.butter(ordem, corte, btype=tipo, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0).astype(np.float32)


def biquad(x, tipo, f0, ganho_db, q=0.8):
    """Equalizador RBJ: 'pico', 'grave' (low shelf) ou 'agudo' (high shelf)."""
    a = 10 ** (ganho_db / 40)
    w = 2 * math.pi * f0 / SR
    al = math.sin(w) / (2 * q)
    c = math.cos(w)
    if tipo == "pico":
        b = [1 + al * a, -2 * c, 1 - al * a]
        d = [1 + al / a, -2 * c, 1 - al / a]
    else:
        s = 1 if tipo == "grave" else -1
        sq = 2 * math.sqrt(a) * al
        b = [a * ((a + 1) - s * (a - 1) * c + sq), s * 2 * a * ((a - 1) - s * (a + 1) * c), a * ((a + 1) - s * (a - 1) * c - sq)]
        d = [(a + 1) + s * (a - 1) * c + sq, -s * 2 * ((a - 1) + s * (a + 1) * c), (a + 1) + s * (a - 1) * c - sq]
    return signal.lfilter(np.array(b) / d[0], np.array(d) / d[0], x, axis=0).astype(np.float32)


def estereo(mono, pan=0.0):
    """Pan de potencia constante: -1 esquerda, 1 direita."""
    ang = (pan + 1) * math.pi / 4
    return np.stack([mono * math.cos(ang), mono * math.sin(ang)], axis=1).astype(np.float32)


def env(n, ataque, queda, nivel=1.0, soltura=None):
    """Envelope: ataque linear, queda exponencial ate 'nivel'; soltura opcional no fim."""
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(ataque, 1e-4))
    if queda:
        e = e * (nivel + (1 - nivel) * np.exp(-np.maximum(0, t - ataque) / queda))
    if soltura:
        r = seg(soltura)
        if 0 < r < n:
            e[-r:] *= np.linspace(1, 0, r) ** 1.5
    return e.astype(np.float32)


def ruido(n):
    return RNG.standard_normal(n).astype(np.float32)


def serra(freq, n, fase=0.0):
    """Dente de serra por acumulo de fase (o filtro passa-baixa depois esconde o aliasing)."""
    f = np.broadcast_to(np.asarray(freq, np.float64), (n,))
    ph = (fase + np.cumsum(f) / SR) % 1.0
    return (2 * ph - 1).astype(np.float32)


def seno(freq, n, fase=0.0):
    f = np.broadcast_to(np.asarray(freq, np.float64), (n,))
    return np.sin(2 * np.pi * (fase + np.cumsum(f) / SR)).astype(np.float32)


def somar(destino, som, inicio):
    """Soma 'som' (n,2) em 'destino' a partir de 'inicio' segundos, cortando o que sobra."""
    a = seg(inicio)
    if a < 0:
        som, a = som[-a:], 0
    b = min(len(destino), a + len(som))
    if b > a:
        destino[a:b] += som[:b - a]


def reverb(x, rt60=1.6, mistura=0.2, pre=0.02, brilho=6000, semente=1):
    """Reverb por convolucao com resposta ao impulso sintetica (ruido com queda exponencial, estereo)."""
    n = seg(rt60 * 1.1)
    rng = np.random.default_rng(semente)
    t = np.arange(n) / SR
    queda = np.exp(-6.91 * t / rt60).astype(np.float32)
    ir = rng.standard_normal((n, 2)).astype(np.float32) * queda[:, None]
    ir = filtro(ir, "low", brilho)
    ir = np.concatenate([np.zeros((seg(pre), 2), np.float32), ir])
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True)) + 1e-9
    if x.ndim == 1:
        x = estereo(x)
    molhado = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1).astype(np.float32)
    seco = np.zeros_like(molhado)
    seco[:len(x)] = x
    return seco * (1 - mistura) + molhado * mistura * 1.8


# ------------------------------------------------------------------ vozes

def tratar_voz(mono, fx, pan):
    """Cadeia de estudio: limpeza, presenca, brilho, compressao, ambiencia do personagem."""
    x = filtro(mono, "high", 85)
    x *= 0.1 / (np.sqrt(np.mean(x ** 2)) + 1e-9)  # nivelado em -20 dBFS RMS
    x = biquad(x, "pico", 3200, 2.5, q=0.9)
    agudo = filtro(x, "high", 3500)
    x = x + 0.1 * filtro(np.tanh(agudo * 5) / 5, "high", 7000)  # exciter leve: a voz vem em 24 kHz (ate 12 kHz)
    x = comprimir(x, -24, 3.0)
    if fx == "narrador":
        x = biquad(x, "grave", 170, 1.5)
        return reverb(estereo(x, pan), rt60=1.1, mistura=0.10, brilho=7000, semente=11)
    if fx == "mestre":
        x = biquad(x, "grave", 140, 3.0)
        return reverb(estereo(x, pan), rt60=2.6, mistura=0.22, pre=0.03, brilho=5000, semente=12)
    if fx == "sistema":
        x = filtro(filtro(x, "high", 350), "low", 4200)
        x = np.tanh(x * 2.2) / 2.2
        eco = np.zeros(len(x) + seg(0.09), np.float32)
        eco[:len(x)] += x
        eco[seg(0.09):] += 0.25 * x
        return reverb(estereo(eco, pan), rt60=0.4, mistura=0.06, semente=13)
    return reverb(estereo(x, pan), rt60=0.5, mistura=0.08, semente=14)


def comprimir(x, limiar_db, razao, ataque=0.005, soltura=0.12):
    nivel = np.abs(x)
    a, r = math.exp(-1 / (ataque * SR)), math.exp(-1 / (soltura * SR))
    # seguidor de envelope de pico (ataque rapido, soltura lenta) em C via lfilter nos dois regimes
    lento = signal.lfilter([1 - r], [1, -r], nivel)
    rapido = signal.lfilter([1 - a], [1, -a], nivel)
    envl = np.maximum(lento, rapido) + 1e-9
    db = 20 * np.log10(envl)
    reducao = np.minimum(0, (limiar_db - db) * (1 - 1 / razao))
    return (x * 10 ** (reducao / 20) * 10 ** ((-limiar_db * (1 - 1 / razao)) / 40)).astype(np.float32)


# ------------------------------------------------------------------ instrumentos

def pad(midis, dur, corte=2200, brilho_final=None, volume=0.06):
    """Supersaw: 5 osciladores levemente desafinados por nota, abertos no estereo."""
    n = seg(dur)
    out = np.zeros((n, 2), np.float32)
    for m in midis:
        for k, det in enumerate((-0.14, -0.07, 0.0, 0.07, 0.14)):
            o = serra(hz(m + det), n, RNG.random())
            out[:, k % 2] += o * (0.8 if det else 1.0)
    out = filtro(out, "low", corte, ordem=2)
    if brilho_final:
        out = filtro(out, "low", brilho_final, ordem=1)
    return out * volume * env(n, 0.35, 0, soltura=0.45)[:, None]


def pluck(midi, dur=0.7, brilho=0.6, volume=0.25):
    """Corda dedilhada (Karplus-Strong) feita com lfilter: y[n] = x[n] + g/2 (y[n-N] + y[n-N-1])."""
    n = seg(dur)
    periodo = max(2, int(round(SR / hz(midi))))
    exc = np.zeros(n, np.float32)
    exc[:periodo] = filtro(ruido(periodo), "low", 1500 + 7000 * brilho)
    a = np.zeros(periodo + 2)
    a[0], a[periodo], a[periodo + 1] = 1.0, -0.4975, -0.4975
    y = signal.lfilter([1.0], a, exc).astype(np.float32)
    return y * volume * env(n, 0.001, 0, soltura=0.08)


def sino(midi, dur=1.2, volume=0.2, parciais=((1, 1.0), (2.0, 0.45), (3.0, 0.25), (4.2, 0.12))):
    n = seg(dur)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for mult, amp in parciais:
        out += amp * np.sin(2 * np.pi * hz(midi) * mult * t) * np.exp(-t * (2.2 + mult * 1.6))
    return (out * volume * env(n, 0.002, 0)).astype(np.float32)


def baixo(midi, dur, volume=0.22):
    n = seg(dur)
    x = 0.7 * seno(hz(midi), n) + 0.3 * filtro(serra(hz(midi), n), "low", 500)
    return x * volume * env(n, 0.005, dur * 0.6, nivel=0.3, soltura=0.05)


def bumbo(volume=0.9, grave=48.0, cauda=0.35):
    n = seg(cauda * 2.2)
    t = np.arange(n) / SR
    f = grave + 95 * np.exp(-t * 28)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / cauda)
    x[:seg(0.004)] += filtro(ruido(seg(0.004)), "high", 2000) * 0.5
    return (x * volume).astype(np.float32)


def taiko(volume=0.9):
    x = bumbo(volume, grave=62, cauda=0.55)
    x[:seg(0.06)] += filtro(ruido(seg(0.06)), "band", [150, 900]) * np.exp(-np.arange(seg(0.06)) / seg(0.02)) * 0.6
    return x


def caixa(volume=0.4):
    n = seg(0.3)
    t = np.arange(n) / SR
    x = filtro(ruido(n), "band", [1200, 7000]) * np.exp(-t / 0.07) + 0.6 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return (x * volume).astype(np.float32)


def chimbal(volume=0.12, aberto=False):
    n = seg(0.35 if aberto else 0.06)
    t = np.arange(n) / SR
    return (filtro(ruido(n), "high", 8000) * np.exp(-t / (0.12 if aberto else 0.015)) * volume).astype(np.float32)


def prato(volume=0.25, dur=2.4):
    n = seg(dur)
    t = np.arange(n) / SR
    x = filtro(ruido(n), "high", 4500) * np.exp(-t / (dur * 0.35))
    for f in (3300, 4730, 6120, 7310):
        x += 0.08 * np.sin(2 * np.pi * f * t) * np.exp(-t / (dur * 0.25))
    return (x * volume).astype(np.float32)


def coral(midis, dur, volume=0.05):
    """'Aaah' de coral: serra filtrada nas formantes da vogal A."""
    n = seg(dur)
    fonte = np.zeros(n, np.float32)
    for m in midis:
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * np.arange(n) / SR + RNG.random() * 6)
        fonte += serra(hz(m) * vib, n)
    x = sum(g * filtro(fonte, "band", [f * 0.9, f * 1.1]) for f, g in ((700, 1.0), (1220, 0.6), (2600, 0.25)))
    return estereo(x * volume * env(n, 0.6, 0, soltura=0.8), 0.0) + estereo(x * volume * 0.5 * env(n, 0.8, 0, soltura=0.8), 0.6)


def melodia(notas, inicio_compasso, compasso, volume=0.07):
    """notas: lista de (nome, batida_inicio, batidas_duracao). Serra com vibrato, filtrada (cordas/sopro)."""
    batida = compasso / 4
    total = max(b + d for _, b, d in notas) * batida + 1.0
    out = np.zeros((seg(total), 2), np.float32)
    for nome, b, d in notas:
        n = seg(d * batida + 0.25)
        f = hz(nota(nome)) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * np.arange(n) / SR) * np.minimum(1, np.arange(n) / seg(0.3)))
        x = 0.6 * serra(f, n) + 0.4 * serra(f * 2.003, n) * 0.4
        x = filtro(x, "low", 2600) * env(n, 0.06, 0, soltura=0.22) * volume
        somar(out, estereo(x, -0.15) + estereo(x * 0.7, 0.35), b * batida)
    return out


# ------------------------------------------------------------------ trilha por secoes

PROG = [("D3", "F3", "A3", "D4"), ("Bb2", "D3", "F3", "Bb3"), ("F2", "A2", "C3", "F3"), ("C3", "E3", "G3", "C4")]
ARPEJO = [0, 1, 2, 3, 2, 1, 2, 3]


def secao(tipo, dur, compasso, compasso0):
    """Uma secao da trilha. compasso0 = indice global do primeiro compasso (para seguir a progressao)."""
    n = seg(dur)
    out = np.zeros((n + seg(3.0), 2), np.float32)
    batida = compasso / 4
    ncomp = int(round(dur / compasso))

    if tipo == "ambiente":
        dr = 0.05 * (seno(hz(nota("D2")), n) + 0.6 * seno(hz(nota("A2")), n) + 0.35 * seno(hz(nota("D3")) * 1.002, n))
        dr *= env(n, 2.5, 0, soltura=1.0) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.11 * np.arange(n) / SR))
        somar(out, estereo(dr), 0)
        vento = filtro(ruido(n), "band", [200, 900]) * 0.02 * env(n, 3.0, 0, soltura=1.5)
        somar(out, estereo(vento, -0.3) + estereo(np.roll(vento, 4000), 0.3), 0)
        for _ in range(int(dur * 7)):  # estalos da vela
            p = RNG.uniform(0, dur - 0.05)
            c = filtro(ruido(seg(0.01)), "band", [900, 5000]) * np.exp(-np.arange(seg(0.01)) / 80) * RNG.uniform(0.01, 0.04)
            somar(out, estereo(c, RNG.uniform(-0.6, 0.6)), p)
        for i, m in enumerate(["D5", "F5", "A5", "E5", "D5", "C5", "A4", "D5"]):  # caixinha de musica
            tt = 1.2 + i * batida * 2
            if tt < dur - 1:
                somar(out, reverb(estereo(sino(nota(m), 2.0, 0.07), 0.2 * (-1) ** i), rt60=2.5, mistura=0.4, semente=i), tt)

    elif tipo == "pizzicato":
        linha = ["D4", "A3", "F4", "A3", "E4", "A3", "G4", "A3", "F4", "A3", "D4", "A3", "C#4", "A3", "E4", "A3"]
        for k in range(ncomp * 8):
            tt = k * batida / 2
            somar(out, estereo(pluck(nota(linha[k % 16]), 0.45, 0.5, 0.22), 0.25 if k % 2 else -0.25), tt)
            if k % 4 == 0:
                somar(out, estereo(pluck(nota(linha[k % 16]) - 12, 0.6, 0.3, 0.18)), tt)
            somar(out, estereo(filtro(ruido(seg(0.04)), "band", [5000, 11000]) * np.exp(-np.arange(seg(0.04)) / 250) * 0.04, 0.4), tt)
            if k % 8 == 4:
                somar(out, estereo(caixa(0.12)), tt)
        out = reverb(out, rt60=0.8, mistura=0.12, semente=21)

    else:
        intensidade = {"revelacao": 0, "tema1": 1, "tema2": 2, "tema3": 3, "final": 4, "cauda": 0}[tipo]
        for k in range(ncomp + (1 if tipo == "cauda" else 0)):
            acorde = PROG[(compasso0 + k) % 4]
            t0 = k * compasso
            if t0 >= dur + (2.0 if tipo == "cauda" else 0):
                break
            corte = 1400 + 450 * intensidade
            somar(out, pad([nota(x) for x in acorde], compasso + 0.5, corte=corte, volume=0.035 + 0.006 * intensidade), t0)
            if tipo == "cauda":
                continue
            if intensidade >= 1:
                for i in range(8):
                    m = nota(acorde[ARPEJO[i] % 4]) + 12
                    somar(out, estereo(pluck(m, 0.55, 0.7, 0.11), (-0.5, 0.5)[i % 2]), t0 + i * batida / 2)
                somar(out, estereo(bumbo(0.55)), t0)
                somar(out, estereo(bumbo(0.45)), t0 + 2 * batida)
                for i in range(8):
                    somar(out, estereo(chimbal(0.05 + 0.02 * (i % 2 == 0)), 0.35), t0 + i * batida / 2)
            if intensidade >= 2:
                for i in range(8):
                    somar(out, estereo(baixo(nota(acorde[0]) - 12 + (12 if i % 4 == 3 else 0), batida * 0.45, 0.16)), t0 + i * batida / 2)
                somar(out, estereo(taiko(0.5), -0.2), t0 + 3.5 * batida)
            if intensidade >= 3:
                somar(out, estereo(caixa(0.22), 0.1), t0 + batida)
                somar(out, estereo(caixa(0.24), 0.1), t0 + 3 * batida)
                somar(out, coral([nota(x) + 12 for x in acorde[1:3]], compasso + 0.6, 0.02), t0)
            if intensidade >= 4:
                for b in (0, 1.5, 2.5):
                    somar(out, estereo(taiko(0.7), 0.15), t0 + b * batida)
            if tipo == "revelacao":
                somar(out, estereo(seno(hz(nota("D1")), seg(compasso)) * 0.12 * env(seg(compasso), 0.8, 0, soltura=0.5)), t0)
        if intensidade >= 3:  # melodia heroica por cima, 4 compassos que se repetem
            motivo = [("D5", 0, 2), ("F5", 2, 1), ("A5", 3, 1), ("G5", 4, 3), ("F5", 7, 1), ("E5", 8, 2), ("F5", 10, 1),
                      ("D5", 11, 1), ("C5", 12, 3), ("A4", 15, 1)]
            for rep in range(0, ncomp, 4):
                somar(out, melodia(motivo, rep, compasso, 0.05 if intensidade == 3 else 0.065), rep * compasso)
        out = reverb(out, rt60=2.2, mistura=0.18, semente=22)
    return out


# ------------------------------------------------------------------ efeitos

def efeito(nome):
    if nome == "dados_rolando":
        n = seg(1.9)
        out = np.zeros((n, 2), np.float32)
        t, passo, amp = 0.0, 0.11, 0.55
        while t < 1.5 and amp > 0.02:
            for dado in range(2):
                tt = t + dado * passo * RNG.uniform(0.3, 0.6)
                m = seg(0.06)
                tq = np.arange(m) / SR
                golpe = filtro(ruido(m), "band", [1800, 7500]) * np.exp(-tq / 0.006) * 0.8
                madeira = sum(np.sin(2 * np.pi * f * tq) * np.exp(-tq / 0.03) for f in (240, 520, 930)) * 0.25
                somar(out, estereo((golpe + madeira) * amp * RNG.uniform(0.6, 1.0), RNG.uniform(-0.4, 0.4)), tt)
            t += passo * RNG.uniform(0.75, 1.15)
            passo *= 0.86
            amp *= 0.88
        return reverb(out, rt60=0.5, mistura=0.12, semente=31)
    if nome in ("clique", "tique"):
        m = seg(0.05)
        tq = np.arange(m) / SR
        x = filtro(ruido(m), "high", 3000) * np.exp(-tq / 0.002) * 0.3 + np.sin(2 * np.pi * (1800 if nome == "clique" else 2600) * tq) * np.exp(-tq / 0.012) * 0.18
        return estereo(x, 0.1)
    if nome == "digitar":
        out = np.zeros((seg(1.0), 2), np.float32)
        for i in range(9):
            somar(out, efeito("clique") * 0.5, i * 0.1 + RNG.uniform(0, 0.03))
        return out
    if nome in ("whoosh", "whoosh_curto"):
        d = 1.0 if nome == "whoosh" else 0.55
        n = seg(d)
        tq = np.linspace(0, 1, n)
        x = ruido(n)
        bandas = np.stack([filtro(x, "band", [f, f * 2.2]) for f in (300, 700, 1500, 3000)], axis=1)
        pos = tq * 3
        pesos = np.clip(1 - np.abs(pos[:, None] - np.arange(4)[None, :]), 0, 1)
        y = (bandas * pesos).sum(axis=1) * np.sin(np.pi * tq) ** 2 * 0.35
        return np.stack([y * (1 - tq), y * tq], axis=1).astype(np.float32) * 1.4
    if nome == "notificacao":
        out = np.zeros((seg(1.4), 2), np.float32)
        somar(out, estereo(sino(nota("G5"), 1.0, 0.12)), 0)
        somar(out, estereo(sino(nota("C6"), 1.2, 0.12)), 0.12)
        return reverb(out, rt60=1.0, mistura=0.25, semente=32)
    if nome == "ping":
        out = estereo(sino(nota("E6"), 1.4, 0.22) + sino(nota("B6"), 1.4, 0.08), 0.0)
        return reverb(out, rt60=1.2, mistura=0.3, semente=33)
    if nome == "chime_vez":
        out = np.zeros((seg(1.6), 2), np.float32)
        for i, m in enumerate(["A5", "C#6", "E6"]):
            somar(out, estereo(sino(nota(m), 1.2, 0.16), -0.2 + 0.2 * i), i * 0.09)
        return reverb(out, rt60=1.4, mistura=0.3, semente=34)
    if nome == "pop":
        m = seg(0.12)
        tq = np.arange(m) / SR
        return estereo(np.sin(2 * np.pi * np.cumsum(300 + 900 * tq / tq[-1]) / SR) * np.exp(-tq / 0.04) * 0.3)
    if nome == "pop_triste":
        m = seg(0.7)
        tq = np.arange(m) / SR
        f = 620 - 380 * (tq / tq[-1]) ** 0.7
        x = filtro(serra(f, m), "low", 1500) * env(m, 0.02, 0, soltura=0.2) * 0.18
        return reverb(estereo(x), rt60=0.5, mistura=0.1, semente=35)
    if nome == "carimbo":
        m = seg(0.4)
        tq = np.arange(m) / SR
        x = np.sin(2 * np.pi * 70 * tq) * np.exp(-tq / 0.08) * 0.8 + filtro(ruido(m), "band", [300, 3000]) * np.exp(-tq / 0.03) * 0.5
        return reverb(estereo(x), rt60=0.4, mistura=0.1, semente=36)
    if nome == "freio":  # disco arranhando
        m = seg(0.45)
        tq = np.linspace(0, 1, m)
        x = ruido(m)
        y = np.zeros(m, np.float32)
        for f in (900, 1600, 2600):
            y += filtro(x, "band", [f * 0.7, f * 1.3]) * np.sin(np.pi * tq * 3) ** 2
        return estereo(y * 0.25 * (1 - tq))
    if nome == "riser_ate":
        d = 3.4
        n = seg(d)
        tq = np.linspace(0, 1, n)
        x = filtro(ruido(n), "high", 400) * tq ** 2.2 * 0.22
        x = x + 0.06 * tq ** 2 * (serra(220 + 900 * tq ** 2, n) + seno(440 + 1800 * tq ** 2, n))
        return reverb(estereo(x), rt60=1.5, mistura=0.25, semente=37)[:n]
    if nome == "impacto":
        m = seg(2.5)
        tq = np.arange(m) / SR
        x = np.sin(2 * np.pi * np.cumsum(55 - 22 * (1 - np.exp(-tq * 2))) / SR) * np.exp(-tq / 0.7) * 0.95
        x += filtro(ruido(m), "low", 1200) * np.exp(-tq / 0.15) * 0.7
        return reverb(estereo(x), rt60=3.0, mistura=0.35, semente=38)
    if nome in ("braam", "braam_final"):
        m = seg(4.0)
        tq = np.arange(m) / SR
        x = sum(serra(hz(nota(n_)), m) * a for n_, a in (("D1", 1.0), ("D2", 0.8), ("A2", 0.6), ("D3", 0.3)))
        corte = 180 + 1400 * np.exp(-tq / 0.6) * np.minimum(1, tq / 0.12)
        y = np.zeros(m, np.float32)
        for i in range(0, m, 2400):  # filtro variando no tempo, em blocos de 50 ms
            y[i:i + 2400] = filtro(x[max(0, i - 4800):i + 2400], "low", float(corte[i]))[-len(x[i:i + 2400]):]
        y = np.tanh(y * 1.6) * env(m, 0.03, 0, soltura=1.5) * 0.35
        return reverb(estereo(y), rt60=3.5, mistura=0.3, semente=39)
    if nome == "ignicao":
        m = seg(4.0)
        tq = np.arange(m) / SR
        sopro = filtro(ruido(m), "low", 900) * np.exp(-tq / 0.5) * 0.6 * np.minimum(1, tq / 0.08)
        out = estereo(sopro)
        for _ in range(60):
            p = RNG.uniform(0.05, 3.8)
            c = filtro(ruido(seg(0.008)), "band", [1500, 6000]) * RNG.uniform(0.02, 0.09)
            somar(out, estereo(c, RNG.uniform(-0.7, 0.7)), p)
        somar(out, efeito("shimmer") * 0.7, 0.05)
        return reverb(out, rt60=1.2, mistura=0.2, semente=40)
    if nome == "shimmer":
        out = np.zeros((seg(1.6), 2), np.float32)
        for i in range(14):
            somar(out, estereo(sino(nota(["D6", "F6", "A6", "C7", "D7", "E7"][i % 6]), 0.6, 0.04), RNG.uniform(-0.8, 0.8)), i * 0.045)
        return reverb(out, rt60=1.6, mistura=0.4, semente=41)
    if nome == "ding_suave":
        return reverb(estereo(sino(nota("A5"), 1.5, 0.14)), rt60=1.5, mistura=0.35, semente=42)
    if nome == "sucesso":
        out = np.zeros((seg(1.6), 2), np.float32)
        for i, m in enumerate(["C6", "E6", "G6", "C7"]):
            somar(out, estereo(sino(nota(m), 1.0, 0.12), -0.3 + 0.2 * i), i * 0.07)
        return reverb(out, rt60=1.3, mistura=0.3, semente=43)
    if nome == "critico":
        out = np.zeros((seg(5.0), 2), np.float32)
        somar(out, efeito("shimmer"), 0)
        somar(out, efeito("braam_final") * 0.8, 0.0)
        somar(out, estereo(prato(0.35, 3.5)), 0.0)
        somar(out, coral([nota("D4"), nota("A4"), nota("D5"), nota("F5")], 4.0, 0.035), 0.0)
        for i, m in enumerate(["D5", "A5", "D6", "F6", "A6"]):
            somar(out, estereo(sino(nota(m), 2.2, 0.1), -0.4 + 0.2 * i), 0.05 + i * 0.06)
        return reverb(out, rt60=2.5, mistura=0.3, semente=44)
    raise KeyError(nome)


# ------------------------------------------------------------------ mix final

def mixar(duracao, linha, vozes, personagens):
    """linha: cenas da linha do tempo; vozes[(cena, i)] = mono 48 kHz. Devolve (n, 2) pronto para salvar."""
    n = seg(duracao)
    voz, mus, sfx = (np.zeros((n, 2), np.float32) for _ in range(3))
    from roteiro import COMPASSO
    for c in linha:
        for i, f in enumerate(c["falas"]):
            p = personagens[f["quem"]]
            somar(voz, tratar_voz(vozes[(c["id"], i)], p["fx"], p["pan"]), f["inicio"])
        comp0 = int(round(c["inicio"] / COMPASSO))
        trecho = secao(c["musica"], c["fim"] - c["inicio"], COMPASSO, comp0)
        if c["id"] == "caos":  # fita parando na marca "congela": pitch cai e o som some
            a = seg(c["marcas"]["congela"] - c["inicio"])
            b = min(len(trecho), a + seg(0.7))
            idx = a + np.cumsum(np.linspace(1.0, 0.0, b - a))
            for ch in range(2):
                trecho[a:b, ch] = np.interp(idx, np.arange(len(trecho)), trecho[:, ch]) * np.linspace(1, 0, b - a)
            trecho[b:] = 0
        if c["id"] == "revelacao":  # silencio dramatico antes do impacto, depois a musica entra cheia
            a = seg(c["marcas"]["impacto"] - c["inicio"])
            trecho[:a] *= np.linspace(0.6, 0.15, a)[:, None]
        somar(mus, trecho * (0.7 if c["musica"] == "final" else 1.0), c["inicio"])  # no final a trilha competia com a voz
        for t, som in c["eventos"]:
            x = efeito(som)
            somar(sfx, x, t - (len(x) / SR if som == "riser_ate" else 0.0))
    for a, b in zip(linha, linha[1:]):  # whoosh em cada troca de cena (menos no corte seco da revelacao)
        if b["id"] not in ("revelacao", "creditos"):
            somar(sfx, efeito("whoosh") * 0.6, b["inicio"] - 0.55)

    # ducking: a musica abaixa quando alguem fala
    nivel = np.abs(voz).max(axis=1)
    a, r = math.exp(-1 / (0.02 * SR)), math.exp(-1 / (0.45 * SR))
    envl = np.maximum(signal.lfilter([1 - r], [1, -r], nivel), signal.lfilter([1 - a], [1, -a], nivel))
    duck = 1 - 0.55 * np.clip(envl / 0.05, 0, 1)
    mix = mus * duck[:, None] * 0.9 + sfx * 0.85 + voz * 1.0
    mix = filtro(mix, "high", 28) * 1.25  # um pouco mais alto; o limitador segura os picos
    # limitador: ganho de -1 dBFS seguindo o pico (ataque instantaneo, soltura de 80 ms), depois saturacao leve
    pico = np.abs(mix).max(axis=1)
    rr = math.exp(-1 / (0.08 * SR))
    seguido = signal.lfilter([1 - rr], [1, -rr], pico)
    seguido = np.maximum(seguido, pico)
    ganho = np.minimum(1.0, 0.85 / (seguido + 1e-9))
    ganho = signal.lfilter([0.02], [1, -0.98], ganho)  # suaviza sem atrasar demais
    mix = np.tanh(mix * ganho[:, None] * 1.05) / math.tanh(1.05)
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    return mix.astype(np.float32)


def salvar_wav(caminho, x):
    import wave
    with wave.open(caminho, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":  # autoteste rapido: cada efeito e cada secao saem finitos e com som
    for nome in ["dados_rolando", "clique", "tique", "digitar", "whoosh", "whoosh_curto", "notificacao", "ping", "chime_vez",
                 "pop", "pop_triste", "carimbo", "freio", "riser_ate", "impacto", "braam", "ignicao", "shimmer",
                 "ding_suave", "sucesso", "critico"]:
        x = efeito(nome)
        assert x.ndim == 2 and x.shape[1] == 2 and np.isfinite(x).all() and np.abs(x).max() > 1e-3, nome
    for tipo in ["ambiente", "pizzicato", "revelacao", "tema1", "tema2", "tema3", "final", "cauda"]:
        x = secao(tipo, 4.8, 2.4, 0)
        assert np.isfinite(x).all() and np.abs(x).max() > 1e-3, tipo
    v = tratar_voz(np.sin(np.linspace(0, 400, SR)).astype(np.float32) * 0.3, "mestre", 0.0)
    assert np.isfinite(v).all()
    print("ok: efeitos, secoes e cadeia de voz")
