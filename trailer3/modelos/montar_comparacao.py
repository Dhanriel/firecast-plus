"""Junta as amostras num arquivo so: bip, "Opcao N", narrador, mestre, aria, kael (mesmo volume).

  .venv-voz/Scripts/python.exe modelos/montar_comparacao.py <pasta das amostras> <ffmpeg>
"""
import os, subprocess, sys

import numpy as np
import soundfile as sf

PASTA, FFMPEG = sys.argv[1], sys.argv[2]
SR = 48000


def carregar(nome):
    x, sr = sf.read(os.path.join(PASTA, nome), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:  # reamostragem linear simples: so para ouvir a comparacao
        t = np.arange(int(len(x) * SR / sr)) * sr / SR
        x = np.interp(t, np.arange(len(x)), x).astype(np.float32)
    return x * (0.1 / (np.sqrt(np.mean(x ** 2)) + 1e-9))


def silencio(s):
    return np.zeros(int(s * SR), np.float32)


def bip():
    t = np.arange(int(0.18 * SR)) / SR
    return (0.25 * np.sin(2 * np.pi * 880 * t) * np.exp(-t * 18)).astype(np.float32)


partes = []
for motor in ("kokoro", "chatterbox"):
    if not os.path.exists(os.path.join(PASTA, f"{motor}_anuncio.wav")):
        continue
    partes += [bip(), silencio(0.25), carregar(f"{motor}_anuncio.wav"), silencio(0.6)]
    for p in ("narrador", "mestre", "aria", "kael"):
        partes += [carregar(f"{motor}_{p}.wav"), silencio(0.7)]
    partes.append(silencio(0.8))
audio = np.clip(np.concatenate(partes), -1, 1)
wav = os.path.join(PASTA, "comparacao_vozes.wav")
sf.write(wav, audio, SR)
mp3 = os.path.join(PASTA, "comparacao_vozes.mp3")
subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-i", wav, "-b:a", "192k", mp3], check=True)
print(mp3, f"{len(audio) / SR:.1f} s")
