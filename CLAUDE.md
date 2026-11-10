# Firecast Plus: notas para quem mexe no código

Plugin Lua para o RRPG Firecast 8 (`plugin/`) + ajudante Python (`fcplus.py`, só stdlib).
Regras do projeto:
- Nada de engenharia reversa do protocolo nem cliente alternativo (risco de ban).
- O dono joga em mesas ao vivo: **perguntar antes de reiniciar o Firecast** e não entrar em mesas de outras pessoas.
- Nada de prefixo tipo `[FC+]` nas mensagens, nem nas enviadas nem nas locais: o dono acha estranho. O anúncio de turno é só `Vez de: Nome`.

## Como o .rpk é montado (sem o rdk)
- O `.rpk` é um zip. `fcplus.py plugin` coloca nele:
  - os arquivos de `plugin/`;
  - o `sdk/*` e o `_rdkCompiledLang.cln`, copiados de `resource.zip/complementosPadroes/AutoUpdater.rpk`. O Firecast **não** fornece o SDK: sem eles, o erro é `firecast.lua` não encontrado;
  - um `module.xml` com `compilationDate`, `compilationDigest` (sha1 dos arquivos) e `compilationUniqueID`.
- Os `.lua` da raiz rodam ao carregar. Os módulos usam `.dlua` e só rodam via `require`.
- Não há `.lfm` compilado: as janelas são montadas em Lua puro com `ui.dlua` (`ui.novo`, `ui.janela`).
- Nenhum arquivo do Firecast vai no repositório nem no download (Termos 4.2a). `fcplus.py pacote` leva só a base
  (`build_plugin(instalar=False)`); o `instalar.ps1` completa no PC do usuário com o SDK e `sons/highlight.mp3` do
  `resource.zip` e calcula o mesmo `compilationDigest`. O `test_fcplus.py` compara os dois caminhos.
- A instalação copia o arquivo para `%APPDATA%\Firecast\Plugins\momotoro.firecast.plus.rpk`. O Firecast **trava o .rpk aberto**: feche e espere o processo sair antes de copiar.
- Os dados do plugin (`NDB.load`, `VHD.openFile`) ficam em `%APPDATA%\Firecast\Plugins\momotoro.firecast.plus_vhd\`.
- Para validar sem o Firecast: `check_lua.py` compila com a `lua54x64.dll` do Firecast, e `test_modulos.py` executa os autotestes dos módulos com o SDK simulado.

## Skins: recoloração hex do mesmo tamanho
- O tema principal é `precompiled/themes/flat.*` dentro de `%LOCALAPPDATA%\Firecast\resource.zip`.
- A paleta fica em `flat.xml.bin`: versão(1), contagem(u16) e pares de strings `[0x06, len, bytes]`, com valores `#RRGGBB` ou `$(var)`.
- As cores também aparecem resolvidas, como texto `#RRGGBB` ou `xAARRGGBB`, em cerca de 220 arquivos DFM binários de `frames/`. Por isso a troca é **byte a byte com o mesmo tamanho**, e os arquivos binários continuam válidos.
- Sempre parte de `resource.zip.original`, o backup feito na primeira skin.
- `resource.zip.fcplus.json` guarda a última skin e o sha1 do zip gerado. Ao iniciar, o ajudante compara: se o zip mudou (atualização do Firecast), ele vira o novo original e a skin é reaplicada, perguntando antes de reiniciar.
- **Fonte e tamanho do chat** mudam de tamanho de texto, então não seguem a regra acima. `fontes_xml` lê o `flat.xml.bin`
  inteiro (paleta, depois classes: nome, nome, atributos próprios, atributos herdados, pais) e troca Roboto/Lato e o
  `fontSize` de `logRichEditStyle`/`chatInputRichEditStyle`. `fontes_style` refaz o índice (nome, tamanho) dos `.style`.
  Sem troca, os dois devolvem o arquivo idêntico, e o `test_fcplus.py` confere isso.
- **Arquivos da skin** (`arquivos` no JSON; `skins/cyberpunk.json` é o exemplo):
  - As entradas do `resource.zip` são guardadas **sem compressão**; os arquivos novos entram igual (`ZipInfo`).
  - 57 frames de `themes/` não têm versão em `precompiled/`, e o Firecast os lê do XML. Para trocar um frame, a skin
    põe o XML em `themes/...` e apaga o precompilado dele.
  - Num frame, `<image overflowX/overflowY>` aceita `none`, `tile`, `stretch`, `center` e `9slice`, e o `<source url>` é
    relativo à pasta do frame. Imagens também entram por atributo de classe (os `backImage0..3` da tela de login).
  - **Visto no Firecast (10/11/2026):** o `<image>` aceita PNG com transparência em `tile`, e o JPG da tela de login troca.
  - O Firecast guarda o frame lido do XML num cache amarrado ao `.cache_hash` do zip. Sem trocar o hash, ele reusa o
    frame antigo (a linha do chat ficou da cor da skin anterior). Por isso `aplicar` grava um hash novo quando há arquivos.
  - O `colorComboBox` devolve nome nas cores com nome (`Black`, `White`); `_hex` converte.
- **Editor de Skins** (`editor_skins.py`, tkinter, só stdlib): o estado da janela vai junto no JSON (`editor`), e
  `montar()` gera uma skin no mesmo formato da Cyberpunk. Secundária e realce viram chaves da paleta em
  `cores_extras`. O fundo do chat ganha um véu da cor de fundo (`opacity` = 1 - força). O Tk não mostra JPG, então
  a prévia só desenha imagem PNG. A tela de login só aceita JPG porque as entradas se chamam `bkgN.jpg`.
- O texto dos botões usa a mesma cor do texto geral (a troca é por valor), então o destaque tem de ser escuro o
  bastante para texto claro. Por isso, na Cyberpunk, o destaque é o vermelho, e o amarelo fica nos detalhes.
- O Firecast trava o `resource.zip` enquanto roda, e o tema só é lido na abertura. **Não existe troca de cores ao vivo nem por mesa.**

## Fluxo plugin -> ajudante
O plugin não reinicia o Firecast nem chama APIs do Windows, então escreve arquivos na pasta `_vhd`, e o ajudante (`iniciar`) lê a cada 0,3 s:
- `pedido.json` (janela /cores): o ajudante fecha o Firecast, aplica ou restaura a skin e abre o Firecast de novo.
- `piscar.txt` (função piscar): o ajudante chama `FlashWindowEx` na janela do Firecast quando ela não está em foco. A janela Delphi tem dono e `WS_EX_APPWINDOW`.
- Se o pedido continuar lá depois de 4 s, a janela avisa que o ajudante está fechado.
- Os erros do ajudante vão para `fcplus.log`, porque ele roda com pythonw, sem console.
- O ajudante fica aberto por dias. Depois de mudar o `fcplus.py`, feche o `pythonw` antigo e abra de novo (o
  `instalar.bat` fecha), senão ele segue com o código velho e ignora o que é novo no pedido.

## Logs
Os erros de plugin ficam em `%LOCALAPPDATA%\Firecast\LogErrors\Firecast-debugLog.txt`. Procure por `ELuaAtPanic` ou `momotoro`. Os ícones carregados aparecem como `plugin://momotoro.firecast.plus/...`, o que prova que o plugin carregou.

## O que o SDK permite (descoberto testando)
- **Chat:** só texto (`chat:escrever`, local). Aceita Talemark: `[§K..]` cor, `[§B]`, `[§R]` e **`[§I url]` para imagem** (desenhada reduzida). Não dá para pôr controles no chat.
- **Controles disponíveis:** sem navegador, web ou vídeo. Existe `image`, mas não player.
- **Nicks:** vêm com códigos de cor (`[§K24]Zera[§K27]khiel`). Limpe com `ChatInfo.nick`.
- **Eventos de mesa:** só `MesaJoined` e `MesaParted`. Não há evento de "aba ativa mudou".
- **Piscar:** não existe API no SDK. A opção nativa é global e fica em Configurações > Notificações.
- **Som:** `Audio.play("/sons/x.mp3")` toca arquivos do plugin. O beep do Windows não é acessível.
- **Mapa (Scene 3):**
  - `items:addToken`, `ownerUserID`, `userData` (marcas próprias), `viewport:addToolButton` e `viewport.onMouseUp` para capturar o clique;
  - `scene:broadcastMessage` / `newBroadcastListener`, onde o `sender` é o login do remetente e é confiável para permissões;
  - a camada `canvas:addBitmap` com `colorMask` tinge uma imagem branca, e `outOfOrderMode = "beforeOwnerLayer"` desenha atrás do token.
- **Imagens no mapa:** o mapa **anima GIF**, mas **não anima WebP**. O `filterEx = "glow"` nativo não ficou como o dono queria.
- **FireDrive:** `FireDrive.uploadFile` devolve `item.url` público. A aura sobe o GIF uma vez por usuário (cache em `aura.xml`; ao gerar um GIF novo, mude a `VERSAO` em `aura.dlua`).

## Limitações conhecidas
- **Token e aura de jogador:** dependem de o mestre ter o plugin quando o Firecast recusa a ação direta. Não foi testado com um jogador real.
- **Prévia de links:** ela aparece depois que o pedido HEAD termina, e pode ficar abaixo de outra mensagem. O limite é de 8 MB, e no máximo 4 prévias a cada 10 s.
- **Aura em GIF:** a transparência é só liga/desliga, então a borda suave vira pontilhado (dither).
- **Aviso de versão nova:** não implementado, porque não há Release pública para consultar.

## Trailer (trailer3/, só local: fora do repositório)
Trailer narrado gerado por código: mesa 3D no Blender em modo fundo (`cena_blender.py`), vozes neurais locais
(Chatterbox Multilingual na GPU, clonando timbres sintéticos do Kokoro, em `trailer3/.venv-chatterbox`; cada fala é
conferida pelo Whisper em `trailer3/.venv-voz` e refeita se sair errada), trilha e efeitos sintetizados (`sons.py`)
e montagem em Python (`fazer_trailer.py`). As vozes do Windows foram descartadas porque o dono achou ruins.
Detalhes e comandos em `trailer3/README.md`.
Assets da Poly Haven (CC0) ficam em `trailer3/assets/polyhaven/` e não fazem parte do plugin.
