import sys, time
import soundfile as sf
from kokoro_onnx import Kokoro
pasta = sys.argv[1]
k = Kokoro(f"{pasta}/kokoro/kokoro-v1.0.onnx", f"{pasta}/kokoro/voices-v1.0.bin")
vozes = k.get_voices()
print("vozes pt:", [v for v in vozes if v.startswith(("pf_", "pm_"))], "| total", len(vozes))
t0 = time.time()
a, sr = k.create("Toda grande aventura começa do mesmo jeito: uma mesa, alguns amigos, e um mestre cheio de planos.", voice="pm_alex", speed=1.0, lang="pt-br")
sf.write(f"{pasta}/teste_kokoro.wav", a, sr)
print(f"ok {len(a) / sr:.2f} s de audio em {time.time() - t0:.1f} s, sr={sr}")
