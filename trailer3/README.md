# Trailer 3 do Firecast Plus

Trailer narrado, feito do zero por código: fotos de uma mesa de RPG em 3D (Blender), vozes neurais geradas no
próprio PC (Chatterbox), trilha e efeitos sintetizados, e montagem em Python.
Saída: `dist/trailer_firecast_plus_v3.mp4` (1080p, 30 fps).

## Como refazer

Depois do trailer pronto, os ambientes, modelos, assets, renders e `build/` foram apagados para liberar espaço
(uns 14 GB). Para refazer, rode tudo abaixo, incluindo a seção "Vozes".

```
python -I trailer3/baixar_assets.py                       # HDRIs, textura e modelos CC0 da Poly Haven
python -I trailer3/texturas.py                            # o mapa de batalha em pergaminho
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --factory-startup -b -P trailer3/cena_blender.py -- C:/ersk/firecast-plus/trailer3
python trailer3/fazer_trailer.py vozes                    # só gera e confere as falas
python trailer3/fazer_trailer.py quadros                  # vozes + uns quadros de conferência (build/quadros)
python trailer3/fazer_trailer.py                          # o trailer completo
python trailer3/fazer_trailer.py audio                    # só refaz o áudio e troca a faixa do mp4 pronto
python trailer3/analisar_audio.py                         # níveis e espectrograma do áudio
```

O Blender aceita `previa` (25% e poucas amostras) e nomes de tomadas (`d20 mesa mapa final diario ceu rua torre
taverna`) depois do `--`.

### Vozes (uma vez só)

Dois ambientes separados dentro de `trailer3/`, porque o PyTorch do Chatterbox e o faster-whisper pedem versões
diferentes das mesmas bibliotecas:

```
python -m venv .venv-chatterbox
.venv-chatterbox/Scripts/python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.venv-chatterbox/Scripts/python.exe -m pip install chatterbox-tts
python -m venv .venv-voz
.venv-voz/Scripts/python.exe -m pip install kokoro-onnx soundfile faster-whisper
```

`modelos/kokoro/` precisa de `kokoro-v1.0.onnx` e `voices-v1.0.bin`
(github.com/thewh1teagle/kokoro-onnx, release `model-files-v1.0`). Depois,
`.venv-voz/Scripts/python.exe modelos/refs_kokoro.py` grava os timbres de referência em `assets/vozes_ref/`.
O Chatterbox e o Whisper large-v3-turbo baixam os próprios pesos do Hugging Face no primeiro uso (cerca de 5 GB).

## Peças

| Arquivo | O quê |
|---|---|
| `roteiro.py` | personagens (timbre, intensidade), falas, pausas, marcas de tempo e efeitos; cenas fecham em compassos |
| `modelos/refs_kokoro.py` | um timbre de referência de ~8 s por personagem, com as vozes pt-BR do Kokoro e misturas delas |
| `vozes_chatterbox.py` | gera cada fala no Chatterbox Multilingual (GPU), clonando o timbre de referência |
| `conferir_vozes.py` | transcreve cada fala com o Whisper, mede o erro de palavras e acha o corte (`--teste` = autoteste) |
| `sons.py` | tratamento das vozes, trilha (100 bpm, Ré menor), efeitos e mix com ducking e limitador |
| `cena_blender.py` | a mesa 3D: d20 com números, d6, velas, baú, mapa, peças de xadrez como miniaturas |
| `arte.py` / `cenas.py` | movimento 3D das fotos pela profundidade, vidro fosco, logo, telas simuladas, as 10 cenas |
| `fazer_trailer.py` | junta tudo e renderiza em 6 processos direto para o ffmpeg do Firecast |

## Notas

- Cada fala tem até 4 tentativas, com sementes diferentes. Ela é refeita quando o Whisper (large-v3-turbo, na
  CPU, uns 12 s por fala) acha uma palavra trocada, cortada ou repetida, quando há ruído grudado no fim da fala
  ou quando há um silêncio comprido no meio. Fica a tentativa de melhor nota. O resultado vai para
  `build/conferencia_vozes.json`, e as falas ficam em cache por texto, timbre e intensidade em `build/vozes/cb_*`.
- O Chatterbox às vezes solta um balbucio ou uma respiração depois da frase. Quando há silêncio entre a fala e
  esse ruído, o corte tira o ruído e o Whisper confere de novo o trecho que ficou. O corte segue os trechos de som,
  e não o tempo de palavra do Whisper, que erra uns 0,2 s e cortaria o fim de "Plus".
- O Chatterbox precisa de uns 6 GB de RAM e 3 GB de memória de vídeo livres. Com um jogo aberto, ele fecha com
  "access violation" ao ler `t3_mtl23ls_v2.safetensors`.
- O Whisper small errava demais em frase curta ("Rolem" virava "Halling", "token" virava "Tolkien"). Por isso o
  conferidor usa o turbo.
- Os nomes em inglês são escritos do jeito que se falam (`Fáiercast`, `Plâs`, `tôken`, em `PRONUNCIA`). A legenda
  mostra o texto original.
- As referências são vozes sintéticas do Kokoro, e nenhuma pessoa real é imitada. O Chatterbox grava uma marca
  d'água inaudível (Perth) em tudo o que gera.
- O mapa de profundidade sai em PNG 16 bits com curva sRGB, e `arte.prof()` desfaz a curva.
- Licenças: Chatterbox (MIT) e Kokoro (Apache-2.0), rodando localmente. HDRIs, textura e modelos vêm da Poly
  Haven (CC0). A trilha e os efeitos são sintetizados por código, sem amostras de terceiros.
