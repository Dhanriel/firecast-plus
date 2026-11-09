"""Amostras do Chatterbox Multilingual (MIT) em pt-BR, clonando o timbre das referencias sinteticas do Kokoro.

  .venv-chatterbox/Scripts/python.exe modelos/amostras_chatterbox.py <pasta das amostras>

exaggeration = intensidade dramatica (0.5 neutro); cfg_weight menor = fala mais solta e expressiva.
"""
import os, sys, time

import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

PASTA = sys.argv[1]
dev = "cuda" if torch.cuda.is_available() else "cpu"
t0 = time.time()
modelo = ChatterboxMultilingualTTS.from_pretrained(device=dev)
print(f"modelo carregado em {dev} [{time.time() - t0:.0f} s]", flush=True)

PERS = {
    "narrador": (0.45, 0.5, "Toda grande aventura começa do mesmo jeito: uma mesa, alguns amigos, e um mestre cheio de planos."),
    "mestre": (0.75, 0.35, "Aria... isso foi há três rodadas. Rolem iniciativa!"),
    "aria": (0.65, 0.4, "Gente, era a minha vez? Eu só fui pegar uma água!"),
    "kael": (0.7, 0.4, "Sério? Que demais! E o meu tôken? Sumiu do mapa de novo!"),
}
for nome, (exag, cfg, texto) in PERS.items():
    t1 = time.time()
    wav = modelo.generate(texto, language_id="pt", audio_prompt_path=os.path.join(PASTA, f"ref_{nome}.wav"),
                          exaggeration=exag, cfg_weight=cfg)
    ta.save(os.path.join(PASTA, f"chatterbox_{nome}.wav"), wav, modelo.sr)
    print(nome, f"{wav.shape[-1] / modelo.sr:.1f} s de audio em {time.time() - t1:.0f} s", flush=True)
wav = modelo.generate("Opção dois.", language_id="pt", audio_prompt_path=os.path.join(PASTA, "ref_narrador.wav"), exaggeration=0.45, cfg_weight=0.5)
ta.save(os.path.join(PASTA, "chatterbox_anuncio.wav"), wav, modelo.sr)
