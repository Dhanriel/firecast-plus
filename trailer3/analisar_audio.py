"""Confere o audio do trailer sem precisar ouvir: picos, nivel por cena e imagem com onda + espectrograma.

  python trailer3/analisar_audio.py   -> numeros no terminal e trailer3/build/audio_analise.png
"""
import json, os, wave

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(AQUI, "build")

with wave.open(os.path.join(B, "audio.wav")) as w:
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
linha = json.load(open(os.path.join(B, "linha_do_tempo.json"), encoding="utf-8"))
mono = x.mean(axis=1)
db = lambda v: 20 * np.log10(v + 1e-9)
print(f"duracao {len(x) / sr:.1f} s, pico {db(np.abs(x).max()):.1f} dBFS, RMS total {db(np.sqrt(np.mean(mono ** 2))):.1f} dBFS")
print(f"amostras cortadas (|x|>=0.999): {(np.abs(x) >= 0.999).sum()}")
falando = np.zeros(len(mono), bool)
for c in linha:
    for f in c["falas"]:
        falando[int(f["inicio"] * sr):int(f["fim"] * sr)] = True
for c in linha:
    a, b = int(c["inicio"] * sr), int(c["fim"] * sr)
    seg = mono[a:b]
    fala = seg[falando[a:b]]
    resto = seg[~falando[a:b]]
    print(f"  {c['id']:10} RMS {db(np.sqrt(np.mean(seg ** 2))):6.1f} dB  com fala {db(np.sqrt(np.mean(fala ** 2))) if len(fala) else float('nan'):6.1f}"
          f"  sem fala {db(np.sqrt(np.mean(resto ** 2))) if len(resto) else float('nan'):6.1f}")

fig, ax = plt.subplots(2, 1, figsize=(22, 8), sharex=True)
t = np.arange(len(mono)) / sr
passo = max(1, len(mono) // 20000)
ax[0].plot(t[::passo], mono[::passo], lw=0.4, color="#7a5cff")
ax[0].fill_between(t, -1, 1, where=falando, color="#ffcc66", alpha=0.18, step="pre")
for c in linha:
    ax[0].axvline(c["inicio"], color="k", lw=0.6)
    ax[0].text(c["inicio"] + 0.3, 0.85, c["id"], fontsize=9)
    for tm, som in c["eventos"]:
        ax[0].plot([tm], [-0.9], "v", color="#e05050", ms=5)
ax[0].set_ylim(-1, 1)
ax[0].set_title("onda (faixas amarelas = falas, triangulos = efeitos)")
ax[1].specgram(mono, NFFT=2048, Fs=sr, noverlap=1024, cmap="magma", vmin=-120)
ax[1].set_ylim(0, 12000)
ax[1].set_title("espectrograma")
plt.tight_layout()
plt.savefig(os.path.join(B, "audio_analise.png"), dpi=70)
print("imagem:", os.path.join(B, "audio_analise.png"))
