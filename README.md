# Firecast Plus

Plugin + ajudante para o **RRPG Firecast 8**: mais funções, skins de cores, aura animada nos tokens e mais.
Usa só o SDK oficial de plugins e arquivos locais. Não mexe no protocolo nem no servidor.

![Aura animada atrás do token](docs/aura.gif)

## Instalar

1. Baixe o `FirecastPlus-<versão>.zip` na página **Releases** e extraia.
2. Feche o Firecast (inclusive o ícone perto do relógio).
3. Dê dois cliques em `instalar.bat`. Ele copia o plugin para `%APPDATA%\Firecast\Plugins`.
4. O instalador pergunta se você quer o **ajudante**, que exige Python 3. Se responder sim, ele cria o atalho
   **Firecast Plus** na área de trabalho. Abra o Firecast sempre por esse atalho.

O ajudante é necessário para:
- trocar as cores e a fonte do Firecast e aumentar o texto do chat;
- piscar o ícone por mesa ou aba;
- reaplicar a skin depois de uma atualização do Firecast.

As outras funções funcionam só com o plugin.

## Comandos e botões

| Onde | O quê |
|---|---|
| `/fc` | lista os comandos |
| `/cores` ou botão no chat | cores do Firecast (destaque, fundo e texto, com presets), fonte do programa e tamanho do texto do chat. **Aplicar e reiniciar** reinicia o Firecast já com tudo novo |
| `/beep` ou botão no chat | palavras que tocam um beep quando alguém as escreve. Ignora maiúsculas e acentos, e as suas próprias mensagens |
| `/piscar` ou botão no chat | escolhe por mesa e por aba quem faz o ícone piscar na barra de tarefas. Desligue antes o "Piscar" nativo em Configurações > Notificações |
| `/previa` ou botão no chat | liga ou desliga a prévia de imagens e de vídeos do YouTube logo abaixo das mensagens. Só quem tem o plugin vê |
| `/turno` | rastreador de iniciativa. O mestre monta a ordem e avança o turno; o jogador da vez recebe beep e um aviso |
| `/multi N rolagem [texto]` | rola a mesma rolagem N vezes |
| `/sorteio [texto]` | sorteia um jogador da mesa |
| `/timer segundos [texto]` | lembrete que só você vê |
| Mapa > Firecast Plus > **Meu token** | cria o seu token (avatar e nick) onde você clicar. Um por pessoa |
| Mapa > Firecast Plus > **Remover meu token** | remove o token criado pelo plugin |
| Mapa > Firecast Plus > **Aura** | aura animada em chamas atrás do token selecionado, com cor, tamanho e intensidade. Todos veem, até quem não tem o plugin |

**Token e aura:**
- O jogador só mexe no próprio token. O mestre mexe em qualquer um.
- Quando o Firecast não deixa o jogador agir direto, o pedido vai ao plugin do mestre. Para isso, o mestre precisa ter o plugin e estar no mapa.

## Linha de comando (`fcplus.py`)

```
python fcplus.py plugin            monta plugin/ em dist/ e instala
python fcplus.py skin skins/X.json aplica uma skin (Firecast fechado)
python fcplus.py restaurar         volta o tema original
python fcplus.py paleta            mostra as cores do tema
python fcplus.py iniciar           abre o Firecast com o ajudante (é o que o atalho faz)
python fcplus.py atalho            cria o atalho na área de trabalho
python fcplus.py pacote            monta o zip de distribuição em dist/ (sem instalar)
python gerar_aura.py               gera o GIF da aura (precisa de Pillow e numpy)
```

Uma skin é um JSON com `base` (`destaque`, `fundo`, `texto`), de onde os tons são derivados, e/ou `cores`
(chaves da paleta para `#RRGGBB`). Opcionais: `fonte` (o nome de uma fonte instalada no Windows, no lugar de Roboto e Lato) e
`tamanho_chat` (10 a 40; o normal é 14). Veja `skins/roxo.json`.

## Testes

```
python test_fcplus.py      skins e reaplicação após atualização (numa cópia do resource.zip)
python test_modulos.py     autotestes da prévia de links e do turno, na Lua do próprio Firecast
python check_lua.py        sintaxe de todos os .lua/.dlua do plugin
```
