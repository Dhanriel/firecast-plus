"""Referencias de timbre (~8 s) para o Chatterbox clonar, geradas com as vozes pt-BR do Kokoro.

  .venv-voz/Scripts/python.exe trailer3/modelos/refs_kokoro.py   -> trailer3/assets/vozes_ref/ref_<personagem>.wav

Sao vozes sinteticas (Apache-2.0): nenhuma pessoa real e imitada.
"""
import os

import soundfile as sf
from kokoro_onnx import Kokoro

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), "assets", "vozes_ref")
os.makedirs(SAIDA, exist_ok=True)
k = Kokoro(os.path.join(AQUI, "kokoro", "kokoro-v1.0.onnx"), os.path.join(AQUI, "kokoro", "voices-v1.0.bin"))


def mistura(*partes):
    return sum(k.get_voice_style(v) * p for v, p in partes)


REFS = {
    "narrador": ((("pm_alex", 1.0),), 0.95, "Era uma noite tranquila na taverna. Do lado de fora, a chuva caía devagar, e lá dentro os amigos se reuniam em volta da mesa para mais uma aventura."),
    "mestre": ((("pm_santa", 1.0),), 0.88, "Vocês entram na caverna escura. O ar é frio e úmido. Ao longe, algo se move nas sombras... Façam um teste de percepção."),
    "aria": ((("pf_dora", 1.0),), 1.05, "Eu adoro essa campanha! Sério, a minha personagem é a melhor curandeira do grupo, e hoje eu vou salvar todo mundo de novo."),
    "kael": ((("pm_alex", 0.65), ("pf_dora", 0.35)), 1.08, "Bora, bora! Eu pego o machado e corro na frente. Se der errado, a culpa é do dado, tá? Eu sou muito sortudo hoje!"),
    "sistema": ((("pf_dora", 0.5), ("pm_alex", 0.5)), 1.0, "Atenção. Rodada três iniciada. Próximo da fila: Aria. Aviso enviado para todos os jogadores da mesa."),
}

for nome, (partes, vel, texto) in REFS.items():
    a, sr = k.create(texto, voice=mistura(*partes), speed=vel, lang="pt-br")
    sf.write(os.path.join(SAIDA, f"ref_{nome}.wav"), a, sr)
    print(nome, f"{len(a) / sr:.1f} s")
