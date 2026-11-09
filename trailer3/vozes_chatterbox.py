"""Gera falas com o Chatterbox Multilingual (MIT). Roda no ambiente .venv-chatterbox (PyTorch com CUDA).

  .venv-chatterbox/Scripts/python.exe trailer3/vozes_chatterbox.py trabalhos.json

trabalhos.json: lista de {"arquivo", "texto", "ref", "exag", "cfg", "semente"}.
ref = audio de ~8 s com o timbre (aqui sempre vozes sinteticas do Kokoro, nunca a voz de uma pessoa real);
exag = intensidade dramatica (0.5 neutro); cfg menor = fala mais solta. Semente fixa = resultado reproduzivel.
Sai WAV 16 bits, 24 kHz, que o fazer_trailer.py le com o modulo wave.
"""
import json, os, sys, time

import soundfile as sf
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

trabalhos = json.load(open(sys.argv[1], encoding="utf-8"))
dev = "cuda" if torch.cuda.is_available() else "cpu"
t0 = time.time()
modelo = ChatterboxMultilingualTTS.from_pretrained(device=dev)
print(f"chatterbox carregado em {dev} [{time.time() - t0:.0f} s]", flush=True)
for j in trabalhos:
    torch.manual_seed(j["semente"])
    if dev == "cuda":
        torch.cuda.manual_seed_all(j["semente"])
    t1 = time.time()
    wav = modelo.generate(j["texto"], language_id="pt", audio_prompt_path=j["ref"], exaggeration=j["exag"],
                          cfg_weight=j["cfg"])
    sf.write(j["arquivo"], wav.squeeze(0).clamp(-1, 1).cpu().numpy(), modelo.sr, subtype="PCM_16")
    print(f"ok {os.path.basename(j['arquivo'])}  {wav.shape[-1] / modelo.sr:.1f} s  [{time.time() - t1:.0f} s]", flush=True)
