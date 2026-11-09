"""Monta o trailer 3 do Firecast Plus: vozes -> linha do tempo -> audio -> video (8 processos) -> mp4.

  python trailer3/fazer_trailer.py            trailer completo em dist/trailer_firecast_plus_v3.mp4
  python trailer3/fazer_trailer.py vozes      so gera e confere as falas (build/conferencia_vozes.json)
  python trailer3/fazer_trailer.py quadros    so alguns quadros de conferencia em trailer3/build/quadros/
  python trailer3/fazer_trailer.py audio      refaz so o audio e troca a faixa no mp4 ja pronto

Pre-requisitos ja gerados: trailer3/render/*.png (cena_blender.py), plugin/auras (gerar_aura.py), os ambientes
.venv-chatterbox e .venv-voz e as referencias de timbre assets/vozes_ref (modelos/refs_kokoro.py). Ver README.md.
"""
import hashlib, json, math, os, re, shutil, subprocess, sys, time, wave
from multiprocessing import Pool

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import roteiro  # noqa: E402

BUILD = os.path.join(AQUI, "build")
VOZES = os.path.join(BUILD, "vozes")
REFS = os.path.join(AQUI, "assets", "vozes_ref")
PY_CHATTERBOX = os.path.join(AQUI, ".venv-chatterbox", "Scripts", "python.exe")
PY_WHISPER = os.path.join(AQUI, ".venv-voz", "Scripts", "python.exe")
RODADAS = 4  # tentativas por fala
SAIDA = os.path.join(os.path.dirname(AQUI), "dist", "trailer_firecast_plus_v3.mp4")
FFMPEG = os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "ffmpeg.exe")
FPS = 30
TRANSICAO = 0.5


# ------------------------------------------------------------------ vozes

def _rodar(python, *args):
    """Roda um script em outro ambiente (o Chatterbox precisa do PyTorch com CUDA; o Whisper, do faster-whisper)."""
    with open(os.path.join(BUILD, "vozes.log"), "a", encoding="utf-8") as log:
        subprocess.run([python, *args], check=True, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, TQDM_DISABLE="1", PYTHONIOENCODING="utf-8"))


def _nota(texto, r):
    """0 = perfeita: erro de palavras, mais multa por ruido grudado no fim da fala ou por silencio comprido no meio.
    (Ruido separado da fala por um silencio nao conta: o corte tira.)"""
    n = r["erro"] + (0.3 if r["colado"] else 0.0)
    pausa = re.search(r"\.\.\.|[.!?:]\s", texto.strip())  # reticencias ou fim de frase no meio da fala
    if r["buraco"] > (1.0 if pausa else 0.6):
        n += 0.3
    return round(n, 3)


def _aceita(texto, nota):
    """Fala curta tem de sair perfeita; a partir de 6 palavras tolera uma trocada a cada 6."""
    import conferir_vozes
    n = len(conferir_vozes.palavras(texto))
    return nota <= (n // 6) / max(n, 1) + 1e-3  # a nota vem arredondada em 3 casas


def gerar_vozes():
    """Gera no Chatterbox so as falas que mudaram e confere cada uma pelo Whisper. A que sai com palavra trocada,
    cortada ou repetida, ou com ruido no fim, e refeita com outra semente; depois de RODADAS fica a de melhor nota."""
    os.makedirs(VOZES, exist_ok=True)
    marca_ref = {q: hashlib.sha1(open(os.path.join(REFS, f"ref_{q}.wav"), "rb").read()).hexdigest()[:8]
                 for q in roteiro.PERSONAGENS}
    falas = {}
    for c in roteiro.CENAS:
        for i, (quem, texto, _) in enumerate(c["falas"]):
            p = roteiro.PERSONAGENS[quem]
            falado = roteiro.texto_para_voz(texto)
            chave = hashlib.sha1(f"cb1|{marca_ref[quem]}|{p['exag']}|{p['cfg']}|{falado}".encode()).hexdigest()[:16]
            falas[(c["id"], i)] = dict(base=os.path.join(VOZES, "cb_" + chave), original=texto, texto=falado,
                                      ref=os.path.join(REFS, f"ref_{quem}.wav"), exag=p["exag"], cfg=p["cfg"], feitas=[])
    pendentes = [f for f in falas.values() if not os.path.exists(f["base"] + ".json")]
    lista = os.path.join(BUILD, "falas.json")
    for rodada in range(RODADAS):
        if not pendentes:
            break
        print(f"  vozes: rodada {rodada + 1}, {len(pendentes)} falas", flush=True)
        trabalhos = [dict(arquivo=f"{f['base']}_{rodada}.wav", texto=f["texto"], original=f["original"], ref=f["ref"],
                          exag=f["exag"], cfg=f["cfg"], semente=11 + 101 * rodada) for f in pendentes]
        json.dump(trabalhos, open(lista, "w", encoding="utf-8"), ensure_ascii=False)
        _rodar(PY_CHATTERBOX, os.path.join(AQUI, "vozes_chatterbox.py"), lista)
        _rodar(PY_WHISPER, os.path.join(AQUI, "conferir_vozes.py"), lista, lista)
        for f, r in zip(pendentes, json.load(open(lista, encoding="utf-8"))):
            r["nota"] = _nota(f["original"], r)
            f["feitas"].append(r)
        pendentes = [f for f in pendentes if not _aceita(f["original"], f["feitas"][-1]["nota"])]
    for f in falas.values():
        if f["feitas"]:
            r = min(f["feitas"], key=lambda r: r["nota"])
            r["tentativas"] = len(f["feitas"])
            shutil.copyfile(r["arquivo"], f["base"] + ".wav")
            json.dump(r, open(f["base"] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from scipy import signal
    import conferir_vozes
    import sons
    vozes, relatorio = {}, []
    for k, f in falas.items():
        r = json.load(open(f["base"] + ".json", encoding="utf-8"))
        relatorio.append(dict(cena=k[0], fala=k[1], texto=f["original"], lido=r["lido"], nota=r["nota"],
                              tentativas=r.get("tentativas", 1), arquivo=f["base"] + ".wav"))
        with wave.open(f["base"] + ".wav") as w:
            sr = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        ini, fim = conferir_vozes.corte(x, sr, r["fim_fala"])[:2]  # sem o ruido que o modelo solta depois da fala
        x = x[int(ini * sr):int(fim * sr)].copy()
        rampa = min(len(x), int(0.04 * sr))
        x[len(x) - rampa:] *= np.linspace(1, 0, rampa, dtype=np.float32)
        g = math.gcd(sons.SR, sr)
        vozes[k] = signal.resample_poly(x, sons.SR // g, sr // g).astype(np.float32)
    json.dump(relatorio, open(os.path.join(BUILD, "conferencia_vozes.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ruins = [r for r in relatorio if not _aceita(r["texto"], r["nota"])]
    for r in ruins:
        print(f"  ATENCAO {r['cena']}/{r['fala']} nota {r['nota']}: {r['texto']!r} -> {r['lido']!r}", flush=True)
    return vozes


# ------------------------------------------------------------------ quadros (roda em cada processo)

_L = None  # linha do tempo no processo


def _iniciar(linha):
    global _L
    _L = linha


def _cena_em(t):
    for i, c in enumerate(_L):
        if c["inicio"] <= t < c["fim"]:
            return i
    return len(_L) - 1


def _render_cena(c, t):
    import cenas
    tl = t - c["inicio"]
    M = {k: v - c["inicio"] for k, v in c["marcas"].items()}
    F = [(f["inicio"] - c["inicio"], f["fim"] - c["inicio"]) for f in c["falas"]]
    base, ui, ex = cenas.CENAS[c["id"]](tl, c["fim"] - c["inicio"], M, F)
    return base, ui, ex


def _juntar(base, ui, ex):
    import arte
    dx, dy = ex.get("tremor", (0, 0))
    if dx or dy:
        base = np.roll(base, (dy, dx), axis=(0, 1))
    return arte.compor(base, ui)


def quadro(i):
    import arte
    from PIL import ImageDraw
    t = i / FPS
    k = _cena_em(t)
    c = _L[k]
    base, ui, ex = _render_cena(c, t)
    rgb = _juntar(base, ui, ex)
    # fusao com a cena vizinha perto das trocas
    vizinha = None
    if k > 0 and t - c["inicio"] < TRANSICAO / 2 and (_L[k - 1]["id"], c["id"]) not in __import__("cenas").SEM_FUSAO:
        vizinha, peso = _L[k - 1], 0.5 - (t - c["inicio"]) / TRANSICAO
    elif k + 1 < len(_L) and c["fim"] - t < TRANSICAO / 2 and (c["id"], _L[k + 1]["id"]) not in __import__("cenas").SEM_FUSAO:
        vizinha, peso = _L[k + 1], 0.5 - (c["fim"] - t) / TRANSICAO
    if vizinha is not None:
        b2, u2, e2 = _render_cena(vizinha, t)
        w = arte.suave(peso / 0.5) * 0.5 if peso < 0.5 else 0.5
        rgb = rgb * (1 - w) + _juntar(b2, u2, e2) * w
    rgb = arte.tarjas(rgb, ex.get("tarjas", 0.0))  # antes da legenda, para nao cobri-la
    # legenda de quem esta falando
    ui = arte.Image.new("RGBA", (arte.W, arte.H), (0, 0, 0, 0))
    for f in c["falas"]:
        if f["inicio"] - 0.12 <= t <= f["fim"] + 0.35:
            p = __import__("roteiro").PERSONAGENS[f["quem"]]
            a = arte.suave((t - f["inicio"] + 0.12) / 0.18) * (1 - arte.suave((t - f["fim"] - 0.15) / 0.2))
            arte.legenda(ui, p["nome"], p["cor"], f["texto"], a)
    rgb = arte.compor(rgb, ui)
    # pos: flash, escurecer, vinheta, grao
    if ex.get("flash", 0) > 0:
        rgb = rgb + ex["flash"] * np.array([1.0, 0.95, 0.9], np.float32)
    if ex.get("escurecer", 0) > 0:
        rgb = rgb * (1 - ex["escurecer"])
    rgb = rgb * arte.vinheta(0.42)
    rgb = arte.grao(rgb, i, 0.022)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8).tobytes()


# ------------------------------------------------------------------ principal

def principal():
    os.makedirs(BUILD, exist_ok=True)
    t0 = time.time()
    vozes = gerar_vozes()
    duracoes = {k: len(v) / 48000 for k, v in vozes.items()}
    linha = roteiro.montar_linha_do_tempo(duracoes)
    total = linha[-1]["fim"]
    json.dump(linha, open(os.path.join(BUILD, "linha_do_tempo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"vozes ok ({len(vozes)} falas), duracao {total:.1f} s  [{time.time() - t0:.0f} s]", flush=True)
    if "vozes" in sys.argv:  # so gera e confere as falas; relatorio em build/conferencia_vozes.json
        return

    if "quadros" in sys.argv:
        from PIL import Image
        pasta = os.path.join(BUILD, "quadros")
        os.makedirs(pasta, exist_ok=True)
        _iniciar(linha)
        amostras = []
        for c in linha:
            for frac in (0.2, 0.55, 0.85):
                amostras.append(int((c["inicio"] + frac * (c["fim"] - c["inicio"])) * FPS))
        for m in ("impacto", "acende", "critico", "mencao", "aviso", "token"):
            for c in linha:
                if m in c["marcas"]:
                    amostras.append(int((c["marcas"][m] + 0.5) * FPS))
        for i in sorted(set(amostras)):
            Image.frombytes("RGB", (1920, 1080), quadro(i)).save(os.path.join(pasta, f"q{i:05d}.jpg"), quality=85)
        print("quadros em", pasta)
        return

    import sons
    audio = sons.mixar(total + 0.5, linha, vozes, roteiro.PERSONAGENS)
    wav = os.path.join(BUILD, "audio.wav")
    sons.salvar_wav(wav, audio[:int(total * sons.SR)])
    print(f"audio ok [{time.time() - t0:.0f} s]", flush=True)
    if "audio" in sys.argv:  # so troca a faixa de audio do video ja renderizado
        tmp = SAIDA + ".tmp.mp4"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", SAIDA, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", tmp], check=True)
        os.replace(tmp, SAIDA)
        print("audio trocado em", SAIDA)
        return

    n = int(total * FPS)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    ff = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
                           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", SAIDA],
                          stdin=subprocess.PIPE)
    with Pool(6, initializer=_iniciar, initargs=(linha,)) as pool:
        for k, dados in enumerate(pool.imap(quadro, range(n), chunksize=4)):
            ff.stdin.write(dados)
            if k % 150 == 0:
                print(f"  quadro {k}/{n}  [{time.time() - t0:.0f} s]", flush=True)
    ff.stdin.close()
    assert ff.wait() == 0, "ffmpeg falhou"
    print(f"pronto: {SAIDA}  ({total:.1f} s)  [{time.time() - t0:.0f} s]", flush=True)


if __name__ == "__main__":
    principal()
