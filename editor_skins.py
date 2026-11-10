"""Editor de Skins do Firecast Plus: monta uma skin (cinco cores, fonte, tamanho do chat e imagens), mostra uma previa
e aplica no Firecast. So stdlib (tkinter).

  python editor_skins.py          (ou dois cliques em "Editor de Skins.pyw", ou o atalho na area de trabalho)
  python editor_skins.py --teste  autoteste sem abrir janela

A skin vai para skins/<nome>.json e skins/<nome>/ (imagens copiadas e o frame do chat), no mesmo formato da
skins/cyberpunk.json, e quem aplica e o fcplus.aplicar. Para compartilhar, mande o .json e a pasta.
"""
import json, os, re, shutil, struct, sys, unicodedata

import fcplus

PADRAO = {"nome": "Minha skin", "destaque": "#C5003C", "fundo": "#000000", "texto": "#B8F6ED", "secundaria": "#55EAD4",
          "realce": "#F3E600", "fonte": "Roboto", "tamanho_chat": 14, "login": "", "chat": "", "ajuste": "repetir",
          "intensidade": 100}
PRESETS = {  # destaque, fundo, texto, secundaria, realce
    "Cyberpunk": ("#C5003C", "#000000", "#B8F6ED", "#55EAD4", "#F3E600"),
    "Original": ("#EB3449", "#212121", "#F2F2F2", "#0076A8", "#FFC700"),
    "Roxo": ("#9F34EB", "#1D192F", "#F2F2F2", "#43B8BC", "#FFC700"),
    "Azul": ("#2D8CFF", "#15202B", "#E8F0F8", "#2FBF71", "#FFAE00"),
    "Verde": ("#2FBF71", "#141E18", "#EEF5EF", "#2D8CFF", "#F5A623"),
    "Âmbar": ("#F5A623", "#1E1A14", "#F5EFE6", "#43B8BC", "#EB3449"),
}
CORES = [("destaque", "Destaque", "botões, abas e seleção"), ("fundo", "Fundo", "janelas e painéis"),
         ("texto", "Texto", "letras e ícones"), ("secundaria", "Secundária", "online, \"Há vagas\", cartões"),
         ("realce", "Realce", "avisos, emojis e a linha do chat")]
AJUSTES = {"repetir": "tile", "esticar": "stretch", "centralizar": "center"}
LOGIN = ["themes/flat/frames/disconnectedForm/backgrounds/bkg%d.jpg" % i for i in range(1, 5)]
FRAME_CHAT = "themes/flat/frames/chat/logRichEdit.xml"


def escurecer(cor, f):
    return "#%02X%02X%02X" % tuple(round(int(cor[i:i + 2], 16) * f) for i in (1, 3, 5))


def cores_extras(e):
    """As duas cores a mais da skin, espalhadas pelas chaves da paleta que o "destaque/fundo/texto" nao cobre."""
    d, s, r = e["destaque"], e["secundaria"], e["realce"]
    return {"alt1_card_color": escurecer(d, 0.7), "alt2_card_color": d, "alt3_card_color": escurecer(s, 0.55),
            "alt4_card_color": escurecer(r, 0.5), "preponent_color_background_regular_text_contrasted": escurecer(s, 0.65),
            "online_state_color": s, "color18": d, "color23": d, "yellow_warning_color": r, "premium_gold_color": r,
            "emoji_face_color": r}


def tamanho_imagem(caminho):
    """(largura, altura) de um PNG ou JPG, lendo so o cabecalho."""
    d = open(caminho, "rb").read()
    if d[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", d[16:24])
    if d[:2] == b"\xff\xd8":
        p = 2
        while p + 9 < len(d):
            if d[p] != 0xFF:
                p += 1
                continue
            m = d[p + 1]
            if m in (0xD8, 0x01, 0xFF) or 0xD0 <= m <= 0xD7:
                p += 1 if m == 0xFF else 2
                continue
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):  # inicio do quadro
                h, w = struct.unpack(">HH", d[p + 5:p + 9])
                return w, h
            p += 2 + struct.unpack(">H", d[p + 2:p + 4])[0]
    raise ValueError(f"{os.path.basename(caminho)}: use uma imagem PNG ou JPG")


def frame_chat(imagem, w, h, ajuste, intensidade, realce):
    """Frame do fundo do chat: a imagem, um veu da cor de fundo para o texto continuar legivel e a linha de realce."""
    modo = AJUSTES[ajuste]
    veu = round(1 - intensidade / 100, 2)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<frame width="302" height="270"  >
	<import file="../../consts.xml"/>
	<draw>
		<!-- gerado pelo Editor de Skins do Firecast Plus -->
		<image left="0" top="0" right="302" bottom="270" zOrder="-20" overflowX="{modo}" overflowY="{modo}">
			<anchors left="true" top="true" bottom="true" right="true"/>
			<source url="{imagem}" left="0" top="0" right="{w}" bottom="{h}"/>
		</image>
		<rectangle left="0" top="0" right="302" bottom="270" xradius="0" yradius="0" zOrder="-15">
			<anchors left="true" top="true" bottom="true" right="true"/>
			<fill color="$(bkg_color)" kind="solid" opacity="{veu}"/>
		</rectangle>
		<rectangle left="0" top="0" right="302" bottom="2" xradius="0" yradius="0" zOrder="-10">
			<anchors left="true" top="true" bottom="false" right="true"/>
			<fill color="{realce}" kind="solid" opacity="0.85"/>
		</rectangle>
	</draw>
</frame>
"""


def apelido(nome):
    """Nome da skin -> nome de arquivo (o mesmo formato que o ajudante aceita no pedido da janela /cores)."""
    sem_acento = unicodedata.normalize("NFKD", nome.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sem_acento).strip("_")[:30].strip("_") or "minha_skin"


def montar(e):
    """Grava skins/<apelido>.json e skins/<apelido>/ a partir do estado do editor. Devolve (apelido, cfg)."""
    for k, _, _ in CORES:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", e[k]):
            raise ValueError(f"cor invalida em {k}: {e[k]!r}")
    a = apelido(e["nome"])
    skins = os.path.join(fcplus.HERE, "skins")
    pasta = os.path.join(skins, a)
    os.makedirs(pasta, exist_ok=True)
    arquivos, estado = {}, dict(e)
    if e.get("login"):
        if tamanho_imagem(e["login"]) and open(e["login"], "rb").read(2) != b"\xff\xd8":
            raise ValueError("a imagem da tela de login precisa ser JPG")
        destino = os.path.join(pasta, "login.jpg")
        if os.path.abspath(e["login"]) != os.path.abspath(destino):
            shutil.copyfile(e["login"], destino)
        estado["login"] = destino
        arquivos.update({n: f"{a}/login.jpg" for n in LOGIN})
    if e.get("chat"):
        w, h = tamanho_imagem(e["chat"])
        ext = ".png" if open(e["chat"], "rb").read(4) == b"\x89PNG" else ".jpg"
        destino = os.path.join(pasta, "chat" + ext)
        if os.path.abspath(e["chat"]) != os.path.abspath(destino):
            shutil.copyfile(e["chat"], destino)
        estado["chat"] = destino
        with open(os.path.join(pasta, "logRichEdit.xml"), "w", encoding="utf-8") as f:
            f.write(frame_chat("fcplus_chat" + ext, w, h, e["ajuste"], int(e["intensidade"]), e["realce"]))
        arquivos.update({f"themes/flat/frames/chat/fcplus_chat{ext}": f"{a}/chat{ext}",
                         FRAME_CHAT: f"{a}/logRichEdit.xml", "precompiled/" + FRAME_CHAT: None})
    cfg = {"nome": e["nome"], "base": {k: e[k].upper() for k in ("destaque", "fundo", "texto")},
           "cores": cores_extras(e), "fonte": e["fonte"], "tamanho_chat": int(e["tamanho_chat"]), "arquivos": arquivos,
           "editor": estado}
    with open(os.path.join(skins, a + ".json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    return a, cfg


def cores_derivadas(e):
    """Todas as cores do tema com a skin, para a previa: {chave da paleta: #RRGGBB}."""
    pal = fcplus.carregar_paleta()
    novas = fcplus.derivar(pal, {k: e[k] for k in ("destaque", "fundo", "texto")})
    novas.update(cores_extras(e))
    nomes = {"white": "#FFFFFF", "red": "#FF0000", "black": "#000000"}

    def cor(k):
        for _ in range(10):
            if k in novas:
                return novas[k]
            m = re.fullmatch(r"\$\((\w+)\)\w*", pal[k])
            if not m:
                return nomes.get(pal[k], pal[k])[:7]
            k = m.group(1)
    return cor


# ------------------------------------------------------------------ janela

def janela():
    import tkinter as tk
    from tkinter import colorchooser, filedialog, font as tkfont, messagebox, ttk

    UI_BG, UI_PAINEL, UI_TEXTO, UI_FRACO = "#15161B", "#1E2027", "#E8E9ED", "#8B8E99"
    raiz = tk.Tk()
    raiz.title("Editor de Skins - Firecast Plus")
    raiz.geometry("1240x780")
    raiz.minsize(1100, 660)
    raiz.configure(bg=UI_BG)
    try:
        raiz.iconbitmap(fcplus.EXE)
    except tk.TclError:
        pass
    base_ui = tkfont.nametofont("TkDefaultFont")
    base_ui.configure(family="Segoe UI", size=10)
    titulo_ui = tkfont.Font(family="Segoe UI Semibold", size=11)
    st = ttk.Style(raiz)
    st.theme_use("clam")
    st.configure(".", background=UI_BG, foreground=UI_TEXTO, fieldbackground=UI_PAINEL, bordercolor="#2B2E37",
                 lightcolor=UI_PAINEL, darkcolor=UI_PAINEL, troughcolor=UI_PAINEL, arrowcolor=UI_TEXTO)
    st.configure("Painel.TFrame", background=UI_PAINEL)
    st.configure("TLabel", background=UI_PAINEL, foreground=UI_TEXTO)
    st.configure("Fraco.TLabel", background=UI_PAINEL, foreground=UI_FRACO)
    st.configure("Titulo.TLabel", background=UI_PAINEL, foreground=UI_TEXTO, font=titulo_ui)
    st.configure("TButton", background="#2B2E37", foreground=UI_TEXTO, borderwidth=0, padding=(10, 6))
    st.map("TButton", background=[("active", "#3A3E4A")])
    st.configure("Forte.TButton", padding=(14, 8))
    st.configure("TCombobox", foreground=UI_TEXTO, background="#2B2E37", selectbackground=UI_PAINEL, selectforeground=UI_TEXTO)
    st.map("TCombobox", fieldbackground=[("readonly", UI_PAINEL)], foreground=[("readonly", UI_TEXTO)],
           selectbackground=[("readonly", UI_PAINEL)], selectforeground=[("readonly", UI_TEXTO)])
    raiz.option_add("*TCombobox*Listbox.background", UI_PAINEL)
    raiz.option_add("*TCombobox*Listbox.foreground", UI_TEXTO)
    st.configure("TSpinbox", foreground=UI_TEXTO, background="#2B2E37", arrowsize=12)
    st.configure("Horizontal.TScale", background=UI_PAINEL)

    e = dict(PADRAO)
    variaveis = {}

    esquerda = ttk.Frame(raiz, style="Painel.TFrame", padding=16)
    esquerda.pack(side="left", fill="y")
    tela = tk.Canvas(raiz, bg=UI_BG, highlightthickness=0)
    tela.pack(side="left", fill="both", expand=True, padx=16, pady=16)

    # os botoes de baixo entram primeiro: numa tela baixa, quem perde espaco e o meio, nunca o "Aplicar"
    botoes = ttk.Frame(esquerda, style="Painel.TFrame")
    botoes.pack(side="bottom", fill="x", pady=(8, 0))
    status = ttk.Label(esquerda, text="", style="Fraco.TLabel", wraplength=300)
    status.pack(side="bottom", anchor="w")
    ttk.Button(botoes, text="Abrir...", command=lambda: abrir()).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
    ttk.Button(botoes, text="Salvar", command=lambda: salvar()).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
    ttk.Button(botoes, text="Restaurar original", command=lambda: restaurar()).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
    aplicar_b = tk.Button(botoes, text="Aplicar no Firecast", relief="flat", bd=0, cursor="hand2", font=titulo_ui,
                          command=lambda: aplicar())
    aplicar_b.grid(row=1, column=0, columnspan=3, sticky="ew", padx=2, pady=(6, 2), ipady=7)

    def secao(texto):
        ttk.Label(esquerda, text=texto, style="Titulo.TLabel").pack(anchor="w", pady=(8, 3))

    secao("Nome da skin")
    vnome = tk.StringVar(value=e["nome"])
    ttk.Entry(esquerda, textvariable=vnome, width=34).pack(anchor="w", fill="x")

    secao("Cores")
    amostras = {}
    for chave, nome, dica in CORES:
        linha = ttk.Frame(esquerda, style="Painel.TFrame")
        linha.pack(anchor="w", fill="x", pady=2)
        b = tk.Button(linha, width=4, relief="flat", bd=0, cursor="hand2", activebackground=e[chave])
        b.pack(side="left", padx=(0, 10), ipady=5)
        caixa = ttk.Frame(linha, style="Painel.TFrame")
        caixa.pack(side="left")
        ttk.Label(caixa, text=nome).pack(anchor="w")
        ttk.Label(caixa, text=dica, style="Fraco.TLabel").pack(anchor="w")
        amostras[chave] = b
        b.configure(command=lambda k=chave, n=nome: escolher_cor(k, n))

    presets = ttk.Frame(esquerda, style="Painel.TFrame")
    presets.pack(anchor="w", pady=(8, 0))
    for i, nome in enumerate(PRESETS):
        ttk.Button(presets, text=nome, command=lambda n=nome: usar_preset(n)).grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")

    secao("Texto")
    linha = ttk.Frame(esquerda, style="Painel.TFrame")
    linha.pack(anchor="w", fill="x")
    fontes = sorted({f for f in tkfont.families() if not f.startswith("@")} | {"Roboto"})
    variaveis["fonte"] = tk.StringVar(value=e["fonte"])
    ttk.Combobox(linha, textvariable=variaveis["fonte"], values=fontes, width=22, state="readonly").pack(side="left")
    ttk.Label(linha, text="  chat").pack(side="left")
    variaveis["tamanho_chat"] = tk.IntVar(value=e["tamanho_chat"])
    ttk.Spinbox(linha, from_=10, to=40, textvariable=variaveis["tamanho_chat"], width=4).pack(side="left", padx=4)

    secao("Imagens")
    rotulos = {}
    for chave, nome, tipos in (("login", "Tela de login (JPG)", [("JPG", "*.jpg *.jpeg")]),
                               ("chat", "Fundo do chat (PNG ou JPG)", [("Imagens", "*.png *.jpg *.jpeg")])):
        linha = ttk.Frame(esquerda, style="Painel.TFrame")
        linha.pack(anchor="w", fill="x", pady=2)
        ttk.Label(linha, text=nome).pack(anchor="w")
        rotulos[chave] = ttk.Label(linha, text="nenhuma", style="Fraco.TLabel")
        ttk.Button(linha, text="Escolher", command=lambda k=chave, t=tipos: escolher_imagem(k, t)).pack(side="left")
        ttk.Button(linha, text="Tirar", command=lambda k=chave: (e.__setitem__(k, ""), redesenhar())).pack(side="left", padx=4)
        rotulos[chave].pack(side="left", padx=6)
    linha = ttk.Frame(esquerda, style="Painel.TFrame")
    linha.pack(anchor="w", fill="x", pady=(4, 0))
    variaveis["ajuste"] = tk.StringVar(value=e["ajuste"])
    ttk.Combobox(linha, textvariable=variaveis["ajuste"], values=list(AJUSTES), width=11, state="readonly").pack(side="left")
    ttk.Label(linha, text="  força").pack(side="left")
    variaveis["intensidade"] = tk.IntVar(value=e["intensidade"])
    ttk.Scale(linha, from_=10, to=100, variable=variaveis["intensidade"], length=120,
              command=lambda _v: redesenhar()).pack(side="left", padx=4)

    def ler():
        e["nome"] = vnome.get().strip() or "Minha skin"
        for k, v in variaveis.items():
            try:
                e[k] = v.get()
            except tk.TclError:
                pass
        e["tamanho_chat"] = min(40, max(10, int(e["tamanho_chat"] or 14)))
        e["intensidade"] = int(float(e["intensidade"]))

    def escolher_cor(k, nome):
        r = colorchooser.askcolor(color=e[k], title=f"Cor: {nome}", parent=raiz)
        if r and r[1]:
            e[k] = r[1].upper()
            redesenhar()

    def usar_preset(n):
        for (k, _, _), v in zip(CORES, PRESETS[n]):
            e[k] = v
        if n == "Cyberpunk":
            variaveis["fonte"].set("Bahnschrift" if "Bahnschrift" in fontes else "Roboto")
        redesenhar()

    def escolher_imagem(k, tipos):
        p = filedialog.askopenfilename(parent=raiz, title="Escolha a imagem", filetypes=tipos)
        if not p:
            return
        try:
            tamanho_imagem(p)
            if k == "login" and open(p, "rb").read(2) != b"\xff\xd8":
                raise ValueError("a tela de login aceita só JPG")
        except ValueError as erro:
            messagebox.showerror("Imagem", str(erro), parent=raiz)
            return
        e[k] = p
        redesenhar()

    imagens_tk = {}

    def foto(p):
        if p not in imagens_tk:
            try:
                imagens_tk[p] = tk.PhotoImage(file=p)  # o Tk le PNG e GIF, nao JPG
            except tk.TclError:
                imagens_tk[p] = None
        return imagens_tk[p]

    def redesenhar(*_):
        ler()
        for k, b in amostras.items():
            b.configure(bg=e[k], activebackground=e[k])
        for k in ("login", "chat"):
            if e[k]:
                w, h = tamanho_imagem(e[k])
                rotulos[k].configure(text=f"{os.path.basename(e[k])}  ({w}×{h})")
            else:
                rotulos[k].configure(text="nenhuma")
        aplicar_b.configure(bg=e["destaque"], fg="#FFFFFF", activebackground=escurecer(e["destaque"], 0.8), activeforeground="#FFFFFF")
        desenhar_previa()

    def desenhar_previa():
        c = cores_derivadas(e)
        tela.delete("all")
        W, H = max(tela.winfo_width(), 700), max(tela.winfo_height(), 560)
        f = lambda t, peso="normal": (e["fonte"], t, peso)
        tela.create_rectangle(0, 0, W, H, fill=c("bkg_color"), width=0)
        x0, y0, x1, y1 = 190, 36, W - 170, H - 76  # area do chat
        img = foto(e["chat"]) if e["chat"] else None
        if img:
            if e["ajuste"] == "centralizar":
                tela.create_image((x0 + x1) // 2, (y0 + y1) // 2, image=img)
            else:  # na previa, "esticar" tambem aparece repetido
                for yy in range(y0, y1, img.height()):
                    for xx in range(x0, x1, img.width()):
                        tela.create_image(xx, yy, image=img, anchor="nw")
            veu = 1 - e["intensidade"] / 100
            if veu > 0.05:
                tela.create_rectangle(x0, y0, x1, y1, fill=c("bkg_color"), width=0,
                                      stipple="gray75" if veu > 0.7 else "gray50" if veu > 0.4 else "gray25")
        elif e["chat"]:
            tela.create_text((x0 + x1) // 2, (y0 + y1) // 2, text="(o Tk não mostra JPG aqui; no Firecast aparece)",
                             fill=c("state_text_content_foreground_color"), font=f(10))
        tela.create_rectangle(x0, y0, x1, y0 + 2, fill=e["realce"] if e["chat"] else c("bkg_color"), width=0)
        # barra de abas e laterais (cobrem o que a imagem passou da area do chat)
        tela.create_rectangle(0, 0, W, y0, fill=c("dark_bkg_color"), width=0)
        tela.create_text(46, 18, text="Mesa 1", fill=c("face_color"), font=f(11, "bold"), anchor="w")
        tela.create_rectangle(38, y0 - 4, 120, y0 - 1, fill=c("dominant_color"), width=0)
        tela.create_rectangle(0, y0, 36, H, fill=c("dark_bkg_color"), width=0)
        tela.create_rectangle(36, y0, x0, H, fill=c("sidebar_content_bkg_color"), width=0)
        tela.create_rectangle(46, y0 + 10, x0 - 10, y0 + 36, fill=c("sidebar_search_edit_bkg_color"), width=0)
        tela.create_text(54, y0 + 23, text="Procurar na biblioteca", fill=c("sidebar_toolbar_label_font_color"), font=f(9), anchor="w")
        for i, n in enumerate(["Cenário", "Fichas", "NPCs", "Sistema"]):
            tela.create_text(58, y0 + 58 + i * 26, text=n, fill=c("face_color"), font=f(10, "bold"), anchor="w")
        tela.create_rectangle(x1, y0, W, H, fill=c("sidebar_content_bkg_color"), width=0)
        tela.create_text(x1 + 14, y0 + 16, text="Mestre", fill=c("face_color"), font=f(10, "bold"), anchor="w")
        tela.create_oval(x1 + 14, y0 + 34, x1 + 42, y0 + 62, fill=c("content_bkg_color"), width=0)
        tela.create_oval(x1 + 34, y0 + 52, x1 + 44, y0 + 62, fill=c("online_state_color"), width=0)
        tela.create_text(x1 + 50, y0 + 46, text="Dhanriel", fill=c("face_color"), font=f(10), anchor="w")
        # mensagens
        tam = e["tamanho_chat"]
        y = y0 + 18
        for quem, texto in (("[19:24]", "Dhanriel entrou"), ("Aria", "Gente, era a minha vez? Eu só fui pegar uma água!"),
                            ("Mestre", "Aria... isso foi há três rodadas. Rolem iniciativa!"), ("Kael", "Dhanriel rolou 1d20 + 5 = 23 {18}")):
            if quem.startswith("["):
                tela.create_text(x0 + 16, y, text=quem, fill=c("low_contrast_text_content_foreground_color"), font=f(tam - 4), anchor="nw")
                tela.create_text(x0 + 76, y, text=texto, fill=c("state_text_content_foreground_color"), font=f(tam - 3), anchor="nw")
                y += tam + 18
                continue
            tela.create_text(x0 + 16, y, text=quem, fill=c("high_contrast_text_content_foreground_color"), font=f(tam - 3, "bold"), anchor="nw")
            tela.create_text(x0 + 16, y + tam + 6, text=texto, fill=c("text_content_foreground_color"), font=f(tam - 2), anchor="nw",
                             width=x1 - x0 - 32)
            y += 2 * tam + 26
        # cartoes do inicio, "ha vagas" e o aviso de mencao
        cy = y1 - 98
        for i, (k, n) in enumerate((("alt1_card_color", "Explorar"), ("alt2_card_color", "Criar mesa"),
                                    ("alt3_card_color", "Amigos"), ("alt4_card_color", "Conta"))):
            cx = x0 + 16 + i * 112
            tela.create_rectangle(cx, cy, cx + 104, cy + 70, fill=c(k), width=0)
            tela.create_text(cx + 10, cy + 52, text=n, fill="#FFFFFF", font=f(9, "bold"), anchor="w")
        tela.create_rectangle(x0 + 470, cy, x0 + 540, cy + 20, fill=c("preponent_color_background_regular_text_contrasted"), width=0)
        tela.create_text(x0 + 505, cy + 10, text="Há vagas", fill="#FFFFFF", font=f(8, "bold"))
        tela.create_oval(x0 + 470, cy + 30, x0 + 490, cy + 50, fill=c("listview_notification_badge_color"), width=0)
        tela.create_text(x0 + 480, cy + 40, text="3", fill="#FFFFFF", font=f(8, "bold"))
        tela.create_text(x0 + 500, cy + 40, text="⚠ aviso", fill=c("warning_color"), font=f(9, "bold"), anchor="w")
        # caixa de digitar e botao
        tela.create_rectangle(x0, y1, x1, H, fill=c("short_content_bkg_color"), width=0)
        tela.create_text(x0 + 16, y1 + 18, text="Digite uma mensagem...", fill=c("text_content_deempashized_foreground_color"),
                         font=f(tam - 3), anchor="w")
        tela.create_rectangle(x1 - 150, H - 40, x1 - 12, H - 10, fill=c("dominant_color"), width=0)
        tela.create_text(x1 - 81, H - 25, text="Enviar", fill=c("action_button_text_color"), font=f(10, "bold"))
        tela.create_text(W - 8, H - 8, text="Prévia aproximada", fill=c("low_contrast_text_content_foreground_color"),
                         font=("Segoe UI", 8), anchor="se")

    def salvar():
        ler()
        try:
            a, _ = montar(e)
        except (OSError, ValueError) as erro:
            messagebox.showerror("Salvar", str(erro), parent=raiz)
            return None
        status.configure(text=f"Salva em skins/{a}.json e skins/{a}/. Para compartilhar, mande os dois.")
        return a

    def abrir():
        p = filedialog.askopenfilename(parent=raiz, title="Abrir skin", initialdir=os.path.join(fcplus.HERE, "skins"),
                                       filetypes=[("Skin do Firecast Plus", "*.json")])
        if not p:
            return
        cfg = json.load(open(p, encoding="utf-8"))
        novo = dict(PADRAO)
        if "editor" in cfg:
            novo.update(cfg["editor"])
        else:  # skin feita a mao, como a cyberpunk.json: pega o que da
            novo.update({k: cfg.get("base", {}).get(k, novo[k]) for k in ("destaque", "fundo", "texto")})
            novo["nome"], novo["fonte"] = cfg.get("nome", novo["nome"]), cfg.get("fonte") or novo["fonte"]
            novo["tamanho_chat"] = cfg.get("tamanho_chat", 14)
        e.update(novo)
        vnome.set(e["nome"])
        for k, v in variaveis.items():
            v.set(e[k])
        redesenhar()
        status.configure(text=f"Aberta: {os.path.basename(p)}")

    def aplicar():
        if not messagebox.askyesno("Aplicar no Firecast", "O Firecast vai fechar e abrir de novo com a skin.\n"
                                   "Se você estiver numa mesa ao vivo, espere um intervalo.\n\nContinuar?", parent=raiz):
            return
        a = salvar()
        if not a:
            return
        try:
            fcplus.fechar_firecast()
            fcplus.aplicar(json.load(open(os.path.join(fcplus.HERE, "skins", a + ".json"), encoding="utf-8")))
            os.startfile(fcplus.EXE)
            status.configure(text=f"Skin '{e['nome']}' aplicada. O Firecast está abrindo.")
        except (Exception, SystemExit) as erro:
            messagebox.showerror("Aplicar", str(erro), parent=raiz)

    def restaurar():
        if not messagebox.askyesno("Restaurar original", "O Firecast vai fechar e abrir de novo com o tema original.\n\nContinuar?",
                                   parent=raiz):
            return
        try:
            fcplus.fechar_firecast()
            fcplus.restaurar()
            os.startfile(fcplus.EXE)
            status.configure(text="Tema original restaurado.")
        except (Exception, SystemExit) as erro:
            messagebox.showerror("Restaurar", str(erro), parent=raiz)

    for v in variaveis.values():
        v.trace_add("write", redesenhar)
    tela.bind("<Configure>", redesenhar)
    raiz.after(50, redesenhar)
    raiz.mainloop()


def teste():
    import tempfile
    pasta = os.path.join(fcplus.HERE, "skins", "cyberpunk")
    assert tamanho_imagem(os.path.join(pasta, "chat.png")) == (512, 512)
    assert tamanho_imagem(os.path.join(pasta, "login1.jpg")) == (1920, 1152)
    assert apelido("Neon Árcade 2077!") == "neon_arcade_2077" and apelido("***") == "minha_skin"
    assert re.fullmatch(r"[a-z0-9_]{1,30}", apelido("x" * 50))  # o ajudante so aceita esse formato
    import xml.dom.minidom
    xml.dom.minidom.parseString(frame_chat("fcplus_chat.png", 512, 512, "repetir", 60, "#F3E600"))
    real = fcplus.HERE
    fcplus.HERE = tempfile.mkdtemp()  # montar grava em HERE/skins
    try:
        e = dict(PADRAO, nome="Teste Neon", login=os.path.join(pasta, "login1.jpg"), chat=os.path.join(pasta, "chat.png"))
        a, cfg = montar(e)
        assert a == "teste_neon" and cfg["cores"]["online_state_color"] == "#55EAD4"
        assert set(cfg["arquivos"]) == set(LOGIN) | {"themes/flat/frames/chat/fcplus_chat.png", FRAME_CHAT, "precompiled/" + FRAME_CHAT}
        for origem in filter(None, cfg["arquivos"].values()):
            assert os.path.exists(os.path.join(fcplus.HERE, "skins", origem)), origem
        assert 'opacity="0.0"' in open(os.path.join(fcplus.HERE, "skins", a, "logRichEdit.xml"), encoding="utf-8").read()
        assert cfg_reaberto_igual(a, cfg)
        for ruim in (dict(e, destaque="vermelho"), dict(e, login=os.path.join(pasta, "chat.png"))):
            try:
                montar(ruim)
                raise AssertionError(ruim)
            except ValueError:
                pass
    finally:
        shutil.rmtree(fcplus.HERE)
        fcplus.HERE = real
    cor = cores_derivadas(dict(PADRAO))
    assert cor("dominant_color") == "#C5003C" and cor("bkg_color") == "#000000" and cor("warning_color") == "#F3E600"
    print("ok")


def cfg_reaberto_igual(a, cfg):
    salvo = json.load(open(os.path.join(fcplus.HERE, "skins", a + ".json"), encoding="utf-8"))
    return salvo == json.loads(json.dumps(cfg))


if __name__ == "__main__":
    teste() if "--teste" in sys.argv else janela()
