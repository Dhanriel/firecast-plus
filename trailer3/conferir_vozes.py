"""Confere as falas geradas sem precisar ouvir: transcreve com o Whisper large-v3-turbo (local, CPU), mede o erro
de palavras e acha onde cortar a fala.

  .venv-voz/Scripts/python.exe trailer3/conferir_vozes.py trabalhos.json resultado.json
  .venv-voz/Scripts/python.exe trailer3/conferir_vozes.py --teste

trabalhos.json: lista de {"arquivo", "original"}. resultado.json: o mesmo, mais
  lido       o que o Whisper entendeu do trecho que fica depois do corte
  erro       erro de palavras (0 = perfeito)
  fim_fala   fim da ultima palavra no audio inteiro (s)
  buraco     o maior silencio entre os trechos que ficam (s)
  sobra      segundos de som jogados fora depois da fala (respiracao ou balbucio do modelo)
  colado     havia ruido grudado na ultima palavra, sem silencio para separar
Os nomes de pronuncia adaptada (Firecast, Plus, plugin, skin, token, on-line) ficam fora da conta.
O fazer_trailer.py usa corte() para recortar a fala do mesmo jeito.
"""
import json, os, re, sys, unicodedata

# o Whisper escreve os nomes em ingles de varios jeitos; nenhum deles entra na conta
IGNORAR = {"fire", "cast", "faier", "fayer", "plus", "plas", "plaz", "plos", "pluss", "plugin", "pluguin", "plugim",
           "plugins", "plug", "skin", "skins", "isquin", "isquim", "esquin", "esquim", "squin", "skim", "token", "tokens",
           "tokem", "toquen", "toquem", "toque", "tolken", "tolkien", "talking", "online", "onlaine", "on", "line", "laine"}
MARCA = re.compile(r"\bf\w{0,6} ?[ck]\w{0,3}st\w?\b")  # Firecast, Fire Cast, Faiercast, Faia Caste...
NUMEROS = ["zero", "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
           "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove", "vinte"]
# grafias diferentes para o mesmo som: "ha tres rodadas" / "a tres rodadas", "Kael" / "Cael", "Aria" / "area"
IGUAIS = {"ha": "a", "cael": "kael", "area": "aria"}


def palavras(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\d+", lambda m: f" {NUMEROS[int(m.group())]} " if int(m.group()) <= 20 else m.group(), s)
    s = MARCA.sub(" ", " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split()))
    return [IGUAIS.get(p, p) for p in s.split() if p not in IGNORAR]


def parecidas(a, b):
    """Iguais, ou uma e a outra com uma letra a mais no fim: o "m" mudo de "rolem", um plural. Vogal trocada no
    meio ("turno"/"torno") ou no fim ("feche"/"fecho") conta como erro."""
    if len(a) > len(b):
        a, b = b, a
    return a == b or (len(a) >= 4 and len(b) == len(a) + 1 and b.startswith(a))


def erro(ref, hip):
    """Taxa de erro de palavras (distancia de edicao / tamanho da referencia)."""
    if not ref:  # fala so com nomes ("Firecast Plus."): basta nao sobrar palavra estranha
        return 0.0 if len(hip) <= 2 else 1.0
    d = list(range(len(hip) + 1))
    for i, r in enumerate(ref, 1):
        ant, d[0] = d[0], i
        for j, h in enumerate(hip, 1):
            ant, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, ant + (not parecidas(r, h)))
    return d[-1] / len(ref)


def regioes(x, sr, junta=0.25):
    """Trechos com som (janelas de 20 ms acima de -30 dB do pico), juntando silencios menores que `junta` s."""
    import numpy as np
    n = sr // 50
    q = len(x) // n
    rms = np.sqrt(np.mean(np.asarray(x[:q * n], np.float64).reshape(q, n) ** 2, axis=1))
    trechos = []
    for i in np.nonzero(rms > np.percentile(rms, 95) * 0.0316)[0]:
        if trechos and i * 0.02 - trechos[-1][1] < junta:
            trechos[-1][1] = (i + 1) * 0.02
        else:
            trechos.append([i * 0.02, (i + 1) * 0.02])
    return trechos


def corte(x, sr, fim_fala):
    """Onde cortar: do primeiro som ate o fim do trecho da ultima palavra. Trecho que comeca mais de 0.3 s depois da
    ultima palavra e ruido do modelo e fica de fora; o tempo do Whisper erra uns 0.2 s, por isso a folga.
    Devolve (ini, fim, maior silencio entre trechos, segundos de som jogados fora, ruido colado na fala)."""
    dur = len(x) / sr
    rs = regioes(x, sr)
    if not rs:
        return 0.0, dur, 0.0, 0.0, False
    fica = [r for r in rs if r[0] <= fim_fala + 0.3] or rs[:1]
    sobra = sum(b - a for a, b in rs[len(fica):])
    fim = fica[-1][1]
    colado = fim > fim_fala + 0.6
    if colado:
        sobra += fim - (fim_fala + 0.4)
        fim = fim_fala + 0.4
    buraco = max((b[0] - a[1] for a, b in zip(fica, fica[1:])), default=0.0)
    return max(0.0, fica[0][0] - 0.03), min(dur, fim + 0.06), round(buraco, 2), round(sobra, 2), colado


def teste():
    import numpy as np
    assert erro(palavras("Rolem iniciativa!"), palavras("rolem iniciativa")) == 0
    assert erro(palavras("Este é o Firecast Plus"), palavras("Este é o Fire Cast plus")) == 0
    assert abs(erro(palavras("um dois tres quatro"), palavras("um dois quatro")) - 0.25) < 1e-9
    assert erro(palavras("Pronto!"), palavras("Pronto pronto pronto")) == 2.0
    assert erro(palavras("Aria... isso foi há três rodadas. Rolem iniciativa!"), palavras("ARIA. Isso foi a 3 rodadas. Role iniciativa.")) == 0
    assert erro(palavras("Opção dois."), palavras("Opção 2.")) == 0
    assert erro(palavras("feche o Firecast"), palavras("feche o fogo")) > 0
    assert erro(palavras("feche o Firecast,"), palavras("Feche o Fáiercast.")) == 0
    assert erro(palavras("feche o Firecast,"), palavras("Fecho o Firecast.")) > 0
    assert erro(palavras("Próximo turno!"), palavras("Próximo torno.")) > 0
    assert erro(palavras("Vez de: Aria."), palavras("Vez de área.")) == 0
    assert erro(palavras("Kael, o seu cavaleiro"), palavras("Cael, o seu cavaleiro")) == 0
    assert erro(palavras("e abra pelo atalho Firecast Plus."), palavras("E abra pelo atalho Faia Caste Plus.")) == 0
    assert erro(palavras("Firecast Plus."), palavras("Fire, cast plus.")) == 0
    assert erro(palavras("Firecast Plus."), palavras("Fire Cast Plus. Obrigado por assistir o video")) == 1.0
    assert palavras("Cadastre o seu nome, e ouça um aviso sempre que alguém falar de você.")[-3:] == ["falar", "de", "voce"]
    sr = 16000
    tom = lambda s: 0.5 * np.sin(np.arange(int(s * sr)) * 0.2)
    nada = lambda s: np.zeros(int(s * sr))
    # fala de 0.5 a 1.5 s, silencio, balbucio de 2.3 a 2.8 s: o balbucio sai
    x = np.concatenate([nada(0.5), tom(1.0), nada(0.8), tom(0.5), nada(0.3)])
    assert [[round(a, 2), round(b, 2)] for a, b in regioes(x, sr)] == [[0.5, 1.5], [2.3, 2.8]]
    ini, fim, buraco, sobra, colado = corte(x, sr, fim_fala=1.45)
    assert abs(ini - 0.47) < 0.01 and abs(fim - 1.56) < 0.01 and buraco == 0 and abs(sobra - 0.5) < 0.01 and not colado
    # o Whisper marcou o fim da ultima palavra antes de o som dela comecar: o trecho fica
    ini, fim, buraco, sobra, colado = corte(x, sr, fim_fala=2.25)
    assert abs(fim - 2.86) < 0.01 and abs(buraco - 0.8) < 0.01 and sobra == 0 and not colado
    # ruido grudado na fala: corta 0.4 s depois da ultima palavra
    ini, fim, buraco, sobra, colado = corte(np.concatenate([nada(0.5), tom(2.0), nada(0.3)]), sr, fim_fala=1.5)
    assert colado and abs(fim - 1.96) < 0.01 and abs(sobra - 0.6) < 0.01
    print("ok")


if __name__ == "__main__":
    if sys.argv[1] == "--teste":
        teste()
        sys.exit()
    import numpy as np
    import soundfile as sf
    from faster_whisper import WhisperModel
    trabalhos = json.load(open(sys.argv[1], encoding="utf-8"))
    modelo = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=os.cpu_count())

    def ouvir(x):
        segs, _ = modelo.transcribe(x, language="pt", beam_size=5, condition_on_previous_text=False, word_timestamps=True)
        segs = list(segs)
        return " ".join(s.text.strip() for s in segs), [w for s in segs for w in (s.words or [])]

    for t in trabalhos:
        x, sr = sf.read(t["arquivo"], dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        # o audio vai pronto em 16 kHz: o decodificador do faster-whisper briga com a versao instalada do PyAV
        x = np.interp(np.arange(int(len(x) * 16000 / sr)) * sr / 16000, np.arange(len(x)), x).astype(np.float32)
        lido, ditas = ouvir(x)
        fim_fala = round(float(ditas[-1].end), 2) if ditas else len(x) / 16000
        ini, fim, buraco, sobra, colado = corte(x, 16000, fim_fala)
        if sobra > 0.05:  # o corte jogou som fora: confere de novo so o que fica
            lido, _ = ouvir(x[int(ini * 16000):int(fim * 16000)])
        t.update(lido=lido, erro=round(erro(palavras(t["original"]), palavras(lido)), 3), fim_fala=fim_fala,
                 buraco=buraco, sobra=sobra, colado=bool(colado))
        print(f"{t['erro']:.2f}  sobra {sobra:.2f}{' colado' if colado else ''}  buraco {buraco:.2f}  {lido}", flush=True)
    json.dump(trabalhos, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
