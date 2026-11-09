"""Amostras das vozes Kokoro (pt-BR) para cada personagem do trailer.

  .venv-voz/Scripts/python.exe modelos/amostras_kokoro.py <pasta de saida>

Gera <saida>/kokoro_<personagem>.wav (uma fala por personagem) e referencias para o Chatterbox.
"""
import os, sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = sys.argv[1]
os.makedirs(SAIDA, exist_ok=True)
k = Kokoro(os.path.join(AQUI, "kokoro", "kokoro-v1.0.onnx"), os.path.join(AQUI, "kokoro", "voices-v1.0.bin"))


def mistura(*partes):
    """Voz nova misturando estilos: mistura(("pm_alex", 0.7), ("pf_dora", 0.3))."""
    return sum(k.get_voice_style(v) * p for v, p in partes)


VOZES = {
    "narrador": (mistura(("pm_alex", 1.0)), 0.95),
    "mestre": (mistura(("pm_santa", 1.0)), 0.88),
    "aria": (mistura(("pf_dora", 1.0)), 1.05),
    "kael": (mistura(("pm_alex", 0.65), ("pf_dora", 0.35)), 1.08),
}
FALAS = {
    "narrador": "Toda grande aventura começa do mesmo jeito: uma mesa, alguns amigos, e um mestre cheio de planos.",
    "mestre": "Aria... isso foi há três rodadas. Rolem iniciativa!",
    "aria": "Gente, era a minha vez? Eu só fui pegar uma água!",
    "kael": "Sério? Que demais! E o meu tôken? Sumiu do mapa de novo!",
}

if __name__ == "__main__":
    for nome, (estilo, vel) in VOZES.items():
        a, sr = k.create(FALAS[nome], voice=estilo, speed=vel, lang="pt-br")
        sf.write(os.path.join(SAIDA, f"kokoro_{nome}.wav"), a, sr)
        print(nome, f"{len(a) / sr:.1f} s")
    a, sr = k.create("Opção um.", voice=VOZES["narrador"][0], speed=0.95, lang="pt-br")
    sf.write(os.path.join(SAIDA, "kokoro_anuncio.wav"), a, sr)

    # referencias de ~10 s para o Chatterbox clonar o timbre (vozes sinteticas: nao e a voz de ninguem real)
    REF = {
        "narrador": "Era uma noite tranquila na taverna. Do lado de fora, a chuva caía devagar, e lá dentro os amigos se reuniam em volta da mesa para mais uma aventura.",
        "mestre": "Vocês entram na caverna escura. O ar é frio e úmido. Ao longe, algo se move nas sombras... Façam um teste de percepção.",
        "aria": "Eu adoro essa campanha! Sério, a minha personagem é a melhor curandeira do grupo, e hoje eu vou salvar todo mundo de novo.",
        "kael": "Bora, bora! Eu pego o machado e corro na frente. Se der errado, a culpa é do dado, tá? Eu sou muito sortudo hoje!",
    }
    for nome, texto in REF.items():
        estilo, vel = VOZES[nome]
        a, sr = k.create(texto, voice=estilo, speed=vel, lang="pt-br")
        sf.write(os.path.join(SAIDA, f"ref_{nome}.wav"), a, sr)
        print("ref", nome, f"{len(a) / sr:.1f} s")
