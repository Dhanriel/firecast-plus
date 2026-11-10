"""Firecast Plus: monta/instala o plugin e aplica skins no Firecast 8.

  python fcplus.py plugin            monta plugin/ em dist/ e instala em %APPDATA%\\Firecast\\Plugins
  python fcplus.py paleta            mostra as cores do tema original
  python fcplus.py skin skins/X.json aplica uma skin (feche o Firecast antes)
  python fcplus.py restaurar         volta o tema original
  python fcplus.py iniciar           abre o Firecast e fica ouvindo o plugin (cores e piscar)
  python fcplus.py piscar            pisca o Firecast na barra de tarefas (teste)
  python fcplus.py atalho            cria o atalho "Firecast Plus" na area de trabalho
  python fcplus.py pacote            monta o plugin e o zip de distribuicao em dist/
"""
import colorsys, ctypes, hashlib, json, os, re, secrets, shutil, socket, struct, subprocess, sys, time, zipfile
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "Firecast.exe")
RES = os.path.join(os.environ["LOCALAPPDATA"], "Firecast", "resource.zip")
BAK = RES + ".original"
ESTADO = RES + ".fcplus.json"  # ultima skin aplicada e o hash do resource.zip que ficou depois dela
PLUGINS = os.path.join(os.environ["APPDATA"], "Firecast", "Plugins")
VHD = os.path.join(PLUGINS, "momotoro.firecast.plus_vhd")  # pasta de arquivos do plugin
PEDIDO = os.path.join(VHD, "pedido.json")
PISCAR = os.path.join(VHD, "piscar.txt")
LOG = os.path.join(HERE, "fcplus.log")
PALETA = "precompiled/themes/flat.xml.bin"
TEMAS = ("precompiled/themes/", "temas/")
FONTES_TEMA = (b"Roboto", b"Lato")  # fonte do texto e dos titulos do tema flat
CHAT = ("logRichEditStyle", "chatInputRichEditStyle", "transparentChatInputRichEditStyle")
TAMANHO_CHAT = 14  # tamanho original do texto das mensagens

# cada cor base puxa a sua familia de tons; a primeira chave e a referencia
FAMILIAS = {
    "destaque": ["color1", "color1_*", "action_button_2_background_down_color", "action_button_2_background_hover_color",
                 "action_button_focused_color", "small_action_button_background_color_dark",
                 "small_action_button_background_color_even_darker", "radiocard_selected_focused_color"],
    "fundo": ["color2", "color3", "color4", "color5", "color6", "color7", "color13", "color15", "color16",
              "color19", "color21", "color22", "color24", "color25"],
    "texto": ["color0", "color0_*", "color8", "color8_deemphasized", "color9", "color11", "color12", "color14",
              "color17", "color20"],
}


def original():
    return BAK if os.path.exists(BAK) else RES


def arquivos_do_firecast():
    """SDK Lua e som de mencao, tirados do Firecast instalado: nada do Firecast vai no repositorio nem no download.
    O instalar.ps1 faz o mesmo no PC de quem instala."""
    out = {}
    with zipfile.ZipFile(original()) as res:
        out["sons/highlight.mp3"] = res.read("sons/highlight.mp3")
        # o Firecast nao fornece o SDK Lua aos plugins: todo .rpk leva sdk/ e a tabela de textos de um plugin padrao
        with zipfile.ZipFile(res.open("complementosPadroes/AutoUpdater.rpk")) as au:
            for n in au.namelist():
                if n.startswith("sdk/") or n == "_rdkCompiledLang.cln":
                    out[n] = au.read(n)
    return out


def build_plugin(instalar=True):
    """instalar=False monta so a base (o que vai no download); senao completa com o Firecast daqui e instala."""
    src = os.path.join(HERE, "plugin")
    files = {}
    for root, _, names in os.walk(src):
        for n in names:
            p = os.path.join(root, n)
            files[os.path.relpath(p, src).replace("\\", "/")] = open(p, "rb").read()
    xml = files["module.xml"].decode("utf-8")
    pid = re.search(r"<id>(.+?)</id>", xml).group(1)
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", pid + ".rpk")
    if instalar:
        files.update(arquivos_do_firecast())
        digest = hashlib.sha1(b"".join(files[k] for k in sorted(files))).hexdigest()
        attrs = f' compilationDate="{time.strftime("%d%m%Y%H%M%S")}" compilationDigest="{digest}" compilationUniqueID="{secrets.token_hex(12)}"'
        files["module.xml"] = xml.replace("<module ", "<module" + attrs + " ", 1).encode("utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    if not instalar:
        return out
    dest = os.path.join(PLUGINS, pid.lower() + ".rpk")
    try:
        shutil.copyfile(out, dest)
    except PermissionError:
        sys.exit(f"montado em {out}, mas o Firecast esta aberto e trava o plugin: feche e rode de novo")
    print(f"ok: {out}\ninstalado: {dest}\nreinicie o Firecast e digite /fc numa mesa")


def pacote():
    """dist/FirecastPlus-<versao>.zip: o que um usuario precisa para instalar (plugin montado, instalador e ajudante)."""
    build_plugin(instalar=False)
    versao = re.search(r"<version>(.+?)</version>", open(os.path.join(HERE, "plugin", "module.xml"), encoding="utf-8").read()).group(1)
    out = os.path.join(HERE, "dist", f"FirecastPlus-{versao}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("dist/momotoro.firecast.plus.rpk", "instalar.bat", "instalar.ps1", "fcplus.py", "Firecast Plus.pyw", "README.md", "LICENSE",
                  "skins/roxo.json"):
            z.write(os.path.join(HERE, n), "FirecastPlus/" + n)
    print("pacote:", out)


def ler_paleta(b):
    # formato: versao(1) contagem(u16) e pares de strings [0x06, tamanho(1), bytes]
    assert b[0] == 3, "formato de paleta desconhecido"
    n, p, out = struct.unpack("<H", b[1:3])[0], 3, {}

    def s(p):
        assert b[p] == 6, f"string esperada no byte {p}"
        return b[p + 2:p + 2 + b[p + 1]].decode("utf-8"), p + 2 + b[p + 1]

    for _ in range(n):
        k, p = s(p)
        out[k], p = s(p)
    return out


def _tok(d, p):
    """Le um valor no formato binario do Delphi (TPF0) a partir do byte p: devolve (valor, posicao seguinte)."""
    t = d[p]
    if t == 6:
        return d[p + 2:p + 2 + d[p + 1]].decode("utf-8"), p + 2 + d[p + 1]
    if t in (2, 3, 4):
        n = {2: 1, 3: 2, 4: 4}[t]
        return int.from_bytes(d[p + 1:p + 1 + n], "little", signed=True), p + 1 + n
    if t == 0x12:
        n = struct.unpack("<i", d[p + 1:p + 5])[0]
        return d[p + 5:p + 5 + 2 * n].decode("utf-16le"), p + 5 + 2 * n
    raise ValueError(f"tipo {t:#x} desconhecido no byte {p}")


def _str(s):
    b = s.encode("utf-8")
    return b"\x06" + bytes([len(b)]) + b


def _int(n):
    for t, k in ((2, 1), (3, 2), (4, 4)):
        if -(1 << (8 * k - 1)) <= n < 1 << (8 * k - 1):
            return bytes([t]) + n.to_bytes(k, "little", signed=True)


def _emendar(d, trocas):
    out, ult = [], 0
    for a, b, novo in trocas:
        out += [d[ult:a], novo]
        ult = b
    return b"".join(out + [d[ult:]])


def fontes_xml(d, fonte, delta):
    """flat.xml.bin = paleta + classes de estilo (nome, nome, atributos proprios, atributos herdados, pais).
    Troca a familia Roboto/Lato e soma delta ao tamanho do texto das classes do chat."""
    trocas = []

    def s(p):
        q = _tok(d, p)[1]
        if fonte and d[p] == 6 and d[p + 2:q] in FONTES_TEMA:
            trocas.append((p, q, _str(fonte)))
        return q

    n, p = struct.unpack("<H", d[1:3])[0], 3
    for _ in range(2 * n):
        p = s(p)
    nc, p = _tok(d, p)
    for _ in range(nc):
        nome, p = _tok(d, p)
        p = _tok(d, p)[1]
        for _ in range(2):
            k, p = _tok(d, p)
            for _ in range(k):
                chave, p = _tok(d, p)
                v, q = _tok(d, p)
                if delta and nome in CHAT and chave in ("fontSize", "textPrompt_fontSize"):
                    trocas.append((p, q, _str(str(int(v) + delta))))
                p = s(p)
        k, p = _tok(d, p)
        for _ in range(k):
            p = _tok(d, p)[1]
    assert p == len(d), "formato do flat.xml.bin mudou"
    return _emendar(d, trocas)


def fontes_style(d, fonte):
    """flat*.style = cabecalho, indice (nome, tamanho em bytes) e os estilos TPF0 em sequencia. A troca de fonte muda
    o tamanho dos estilos, entao o indice e refeito."""
    cab = b"FMX_STYLE 2.5\x01"
    assert d.startswith(cab), "formato do .style mudou"
    p, idx = len(cab), []
    while d[p] == 6:
        nome, p = _tok(d, p)
        t, p = _tok(d, p)
        idx.append((nome, t))
    assert d[p] == 0 and sum(t for _, t in idx) == len(d) - p - 1, "indice do .style nao bate"
    p += 1
    novo = fonte and _str(fonte)
    out_idx, blocos = [], []
    for nome, t in idx:
        b = d[p:p + t]
        p += t
        if fonte:
            b = re.sub(rb"\x06\x06Roboto|\x06\x04Lato", lambda m: novo, b)
        out_idx.append(_str(nome) + _int(len(b)))
        blocos.append(b)
    return cab + b"".join(out_idx) + b"\x00" + b"".join(blocos)


def fontes(nome, d, fonte, delta):
    if nome == PALETA:
        return fontes_xml(d, fonte, delta)
    if fonte and d.startswith(b"FMX_STYLE"):
        return fontes_style(d, fonte)
    if fonte and nome.endswith(".style"):  # temas/FC8Base.style, em texto
        return re.sub(rb"'(Roboto|Lato)'", b"'" + fonte.encode() + b"'", d)
    return d


def carregar_paleta():
    with zipfile.ZipFile(original()) as z:
        return ler_paleta(z.read(PALETA))


def resolver(pal, v):
    for _ in range(10):
        m = re.fullmatch(r"\$\((\w+)\)(\w*)", v)
        if not m:
            return v
        v = pal[m.group(1)] + m.group(2)
    return v


def paleta():
    pal = carregar_paleta()
    for k, v in pal.items():
        r = resolver(pal, v)
        print(f"{k:55} {r}" + (f"   ({v})" if r != v else ""))


def hls(h):
    return colorsys.rgb_to_hls(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def derivar(pal, base):
    """Da cor base de cada familia, recalcula os outros tons mantendo a diferenca de luz/saturacao do original."""
    cores = {}
    for fam, novo in base.items():
        chaves = FAMILIAS[fam]
        nh, nl, ns = hls(novo)
        rh, rl, rs = hls(resolver(pal, pal[chaves[0]]))
        for k in pal:
            if not any(k == c or (c.endswith("*") and k.startswith(c[:-1])) for c in chaves):
                continue
            v = resolver(pal, pal[k])
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
                continue
            h, l, s = hls(v)
            if rs < 0.05:  # referencia cinza: a familia ganha a saturacao nova (e o matiz, se a nova nao for cinza)
                h, s = (nh if ns >= 0.05 else h), min(1, s + ns)
            else:
                h, s = (h + nh - rh) % 1, min(1, s * ns / rs)
            l = min(1, max(0, l + nl - rl))
            cores[k] = "#%02X%02X%02X" % tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, l, s))
    return cores


def aplicar(cfg):
    pal = carregar_paleta()
    cores = derivar(pal, cfg.get("base", {}))
    cores.update(cfg.get("cores", {}))
    troca = {}
    for k, novo in cores.items():
        if k not in pal:
            sys.exit(f"cor '{k}' nao existe na paleta (veja: python fcplus.py paleta)")
        velho = resolver(pal, pal[k])
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", velho) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", novo):
            sys.exit(f"{k}: so da para trocar cores #RRGGBB ({velho} -> {novo})")
        troca[velho[1:].upper()] = novo[1:].upper().encode()
    fonte = cfg.get("fonte") or None
    if fonte == "Roboto":
        fonte = None
    if fonte and not re.fullmatch(r"[A-Za-z0-9 \-]{1,40}", fonte):
        sys.exit(f"nome de fonte invalido: {fonte!r}")
    tam = int(cfg.get("tamanho_chat") or TAMANHO_CHAT)
    if not 10 <= tam <= 40:
        sys.exit(f"tamanho do chat fora de 10..40: {tam}")
    delta = tam - TAMANHO_CHAT

    # mesmo tamanho de texto, entao os arquivos binarios do Delphi continuam validos
    pat = re.compile(rb"(#|x[0-9A-Fa-f]{2})([0-9A-Fa-f]{6})")
    sub = lambda m: m.group(1) + troca.get(m.group(2).decode().upper(), m.group(2))

    if not os.path.exists(BAK):
        shutil.copyfile(RES, BAK)
    tmp = RES + ".tmp"
    with zipfile.ZipFile(BAK) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            d = zin.read(info)
            if info.filename.startswith(TEMAS) and not info.filename.endswith((".png", ".jpg", ".ttf")):
                d = pat.sub(sub, d)
                if fonte or delta:
                    d = fontes(info.filename, d, fonte, delta)
            zout.writestr(info, d)
    try:
        os.replace(tmp, RES)
    except PermissionError:
        os.remove(tmp)
        sys.exit("resource.zip em uso: feche o Firecast e rode de novo")
    salvar_estado(cfg)
    print(f"skin '{cfg.get('nome', 'sem nome')}' aplicada ({len(troca)} cores). Abra o Firecast.")


def _sha1(caminho):
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def salvar_estado(cfg):
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump({"skin": cfg, "sha1": _sha1(RES)}, f)


def verificar_atualizacao(aberto, perguntar):
    """Se uma atualizacao do Firecast trocou o resource.zip, ele vira o novo original e a ultima skin volta."""
    try:
        est = json.load(open(ESTADO, encoding="utf-8"))
    except (OSError, ValueError):
        return "sem estado"
    if _sha1(RES) == est.get("sha1"):
        return "ok"
    skin_ = est.get("skin")
    if skin_ and aberto:
        if not perguntar():
            return "adiado"  # o backup antigo fica; pergunta de novo na proxima vez
        fechar_firecast()
    shutil.copyfile(RES, BAK)  # nunca recolorir a partir do original da versao velha
    if skin_:
        aplicar(skin_)
        return "reaplicada"
    salvar_estado(None)
    return "novo original"


def perguntar_reiniciar():
    MB_YESNO, MB_ICONQUESTION, MB_TOPMOST, IDYES = 0x4, 0x20, 0x40000, 6
    return ctypes.windll.user32.MessageBoxW(
        None, "O Firecast foi atualizado e voltou ao tema original.\nReaplicar a sua skin agora? (o Firecast vai reiniciar)",
        "Firecast Plus", MB_YESNO | MB_ICONQUESTION | MB_TOPMOST) == IDYES


def skin(path):
    aplicar(json.load(open(path, encoding="utf-8")))


def restaurar():
    if not os.path.exists(BAK):
        sys.exit("nada para restaurar")
    try:
        shutil.copyfile(BAK, RES)
    except PermissionError:
        sys.exit("resource.zip em uso: feche o Firecast e rode de novo")
    salvar_estado(None)
    print("tema original restaurado")


def atalho():
    """Cria o atalho "Firecast Plus" na area de trabalho: abre o Firecast junto com o ajudante."""
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    alvo = os.path.join(HERE, "Firecast Plus.pyw")
    # shortcut: caminhos com aspas simples quebram o comando; trocar por arquivo .ps1 se aparecer o caso
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\Firecast Plus.lnk');"
          f"$s.TargetPath='{pyw}';$s.Arguments='\"{alvo}\"';$s.WorkingDirectory='{HERE}';$s.IconLocation='{EXE},0';$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print("atalho 'Firecast Plus' criado na area de trabalho")


def firecast_aberto():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Firecast.exe", "/NH"], capture_output=True, text=True).stdout
    return "Firecast.exe" in out


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%d/%m %H:%M:%S ") + msg + "\n")


def fechar_firecast():
    subprocess.run(["taskkill", "/IM", "Firecast.exe", "/F"], capture_output=True)
    for _ in range(40):  # espera o Firecast soltar o resource.zip
        if not firecast_aberto():
            break
        time.sleep(0.5)


def atender(pedido):
    fechar_firecast()
    try:
        if pedido.get("acao") == "restaurar":
            restaurar()
        else:
            # o seletor de cor do Firecast devolve #RRGGBB ou #RRGGBBAA
            aplicar({"nome": "do plugin", "base": {k: pedido[k][:7].upper() for k in FAMILIAS if k in pedido},
                     "fonte": pedido.get("fonte"), "tamanho_chat": pedido.get("tamanho_chat")})
        log(f"ok: {pedido}")
    except (Exception, SystemExit) as e:
        log(f"erro em {pedido}: {e}")
    os.startfile(EXE)


class FLASHWINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]


def _user32():
    u = ctypes.WinDLL("user32")
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindow.restype = wintypes.HWND
    u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.FlashWindowEx.argtypes = [ctypes.POINTER(FLASHWINFO)]
    return u


def _exe_do_pid(pid):
    k = ctypes.WinDLL("kernel32")
    k.OpenProcess.restype = wintypes.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf, n = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
    ok = k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k.CloseHandle(h)
    return buf.value if ok else ""


def _pid(u, hwnd):
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def piscar():
    """Pisca o botao do Firecast na barra de tarefas, como o "Piscar" nativo, se ele nao estiver em foco."""
    u = _user32()
    pids, janelas = {}, []

    def eh_firecast(pid):
        if pid not in pids:
            pids[pid] = _exe_do_pid(pid).lower().endswith("\\firecast.exe")
        return pids[pid]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        # janela com botao na barra: visivel, sem WS_EX_TOOLWINDOW e sem dono ou com WS_EX_APPWINDOW (caso do Delphi)
        ex = u.GetWindowLongPtrW(hwnd, -20)
        if u.IsWindowVisible(hwnd) and not ex & 0x80 and (ex & 0x40000 or not u.GetWindow(hwnd, 4)):
            if eh_firecast(_pid(u, hwnd)):
                janelas.append(hwnd)
        return True

    u.EnumWindows(cada, 0)
    frente = u.GetForegroundWindow()
    if frente and eh_firecast(_pid(u, frente)):
        return 0
    for hwnd in janelas:  # FLASHW_TRAY | FLASHW_TIMERNOFG: pisca ate o usuario abrir a janela
        u.FlashWindowEx(ctypes.byref(FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x0E, 0, 0)))
    return len(janelas)


def iniciar():
    try:  # porta local como trava: so um ajudante por vez
        trava = socket.socket()
        trava.bind(("127.0.0.1", 47821))
    except OSError:
        sys.exit("o ajudante ja esta rodando")
    try:
        log("resource.zip: " + verificar_atualizacao(firecast_aberto(), perguntar_reiniciar))
    except (Exception, SystemExit) as e:
        log(f"erro ao verificar o resource.zip: {e}")
    if not firecast_aberto():
        os.startfile(EXE)
    log("ajudante iniciado")
    while True:
        time.sleep(0.3)
        try:  # sem console (pythonw), um erro nao tratado mataria o ajudante em silencio
            if os.path.exists(PISCAR):
                os.remove(PISCAR)
                piscar()
            if not os.path.exists(PEDIDO):
                continue
            try:
                pedido = json.load(open(PEDIDO, encoding="utf-8"))
            except (OSError, ValueError):
                continue  # o plugin ainda esta escrevendo
            os.remove(PEDIDO)
            atender(pedido)
        except Exception:
            import traceback
            log("erro no ajudante: " + traceback.format_exc().replace("\n", " | "))


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"plugin": build_plugin, "paleta": paleta, "restaurar": restaurar, "iniciar": iniciar, "atalho": atalho,
            "piscar": lambda: print(f"piscou {piscar()} janela(s)"), "pacote": pacote}
    if a and a[0] in cmds and len(a) == 1:
        cmds[a[0]]()
    elif len(a) == 2 and a[0] == "skin":
        skin(a[1])
    else:
        print(__doc__)
