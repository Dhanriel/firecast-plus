"""Roteiro do trailer 3: personagens, falas, marcas de tempo e efeitos. So dados + a montagem da linha do tempo.

Cada cena: falas (personagem, texto, pausa antes), marcas nomeadas presas a uma fala ou a cena, e eventos de som.
A duracao de cada cena sai das vozes ja geradas e e arredondada para compassos inteiros da trilha (100 bpm),
assim os cortes caem no tempo forte da musica.
"""
BPM = 100
COMPASSO = 4 * 60 / BPM  # 2.4 s

# vozes: Chatterbox Multilingual (local) clonando timbres sinteticos do Kokoro: assets/vozes_ref/ref_<personagem>.wav.
# exag = intensidade dramatica (0.5 neutro); cfg menor = fala mais solta. Valores das amostras aprovadas.
PERSONAGENS = {
    "narrador": dict(exag=0.45, cfg=0.5, nome="NARRADOR", cor=(232, 176, 74), pan=0.0, fx="narrador"),
    "mestre": dict(exag=0.75, cfg=0.35, nome="MESTRE", cor=(232, 96, 76), pan=0.0, fx="mestre"),
    "aria": dict(exag=0.65, cfg=0.4, nome="ARIA", cor=(92, 204, 238), pan=-0.22, fx="sala"),
    "kael": dict(exag=0.7, cfg=0.4, nome="KAEL", cor=(130, 214, 124), pan=0.22, fx="sala"),
    "sistema": dict(exag=0.3, cfg=0.5, nome="FIRECAST PLUS", cor=(184, 128, 255), pan=0.0, fx="sistema"),
}

# so para a voz ler direito; a legenda mostra o texto original
PRONUNCIA = [("Firecast", "Fáiercast"), ("Plus", "Plâs"), ("plugin", "plúguin"), ("skin", "isquin"),
             ("token", "tôken"), ("on-line", "onláine")]

# marca: (ancora, deslocamento) com ancora = ("fala", i, "inicio"|"fim") ou ("cena", "inicio"|"fim")
CENAS = [
    dict(id="abertura", musica="ambiente", inicio=1.4, fim=0.9, falas=[
        ("narrador", "Toda grande aventura começa do mesmo jeito.", 0.0),
        ("narrador", "Uma mesa, alguns amigos... e um mestre cheio de planos.", 0.5),
        ("mestre", "Rolem iniciativa.", 2.1),
    ], marcas={"hora": (("cena", "inicio"), 0.35), "troca_foto": (("fala", 1, "inicio"), -0.35),
               "dados": (("fala", 2, "inicio"), -1.95)},
       eventos=[("dados", "dados_rolando")]),

    dict(id="caos", musica="pizzicato", inicio=0.5, fim=0.9, falas=[
        ("narrador", "Mas, numa mesa on-line, nem tudo sai como o planejado.", 0.0),
        ("aria", "Gente, era a minha vez? Eu só fui pegar uma água!", 0.4),
        ("mestre", "Aria... isso foi há três rodadas.", 0.35),
        ("kael", "E o meu token? Sumiu do mapa de novo!", 0.35),
    ], marcas={"carimbo": (("fala", 2, "fim"), -0.45), "token_sumiu": (("fala", 3, "inicio"), 0.35),
               "congela": (("cena", "fim"), -0.7)},
       eventos=[("carimbo", "carimbo"), ("token_sumiu", "pop_triste"), ("congela", "freio")]),

    dict(id="revelacao", musica="revelacao", inicio=0.9, fim=1.4, falas=[
        ("narrador", "E se o seu Firecast cuidasse dessas coisas por você?", 0.0),
        ("narrador", "Este é o Firecast Plus: um plugin que dá superpoderes para a sua mesa.", 2.6),
    ], marcas={"impacto": (("fala", 1, "inicio"), -1.7)},
       eventos=[("impacto", "riser_ate"), ("impacto", "impacto"), ("impacto", "braam")]),

    dict(id="cores", musica="tema1", inicio=0.8, fim=0.9, falas=[
        ("narrador", "Comece pelo visual: escolha as suas cores, ou use um tema pronto.", 0.0),
        ("aria", "Roxo. Com certeza, roxo!", 0.35),
        ("narrador", "Um clique, e o Firecast reabre com a sua cara.", 0.35),
        ("narrador", "E, se ele atualizar, a sua skin volta sozinha.", 0.2),
    ], marcas={"clique_roxo": (("fala", 1, "inicio"), 0.25), "clique_aplicar": (("fala", 2, "inicio"), 0.15),
               "reabre": (("fala", 2, "inicio"), 0.9), "atualizou": (("fala", 3, "inicio"), 0.1)},
       eventos=[("clique_roxo", "clique"), ("clique_aplicar", "clique"), ("reabre", "whoosh_curto"),
                ("atualizou", "notificacao")]),

    dict(id="aura", musica="tema2", inicio=0.6, fim=0.9, falas=[
        ("mestre", "Kael, o seu cavaleiro acaba de despertar um poder antigo.", 0.0),
        ("kael", "Sério? Que demais!", 1.0),
        ("narrador", "Com a aura, qualquer token ganha chamas animadas...", 0.4),
        ("narrador", "na cor e no tamanho que você quiser.", 0.05),
        ("narrador", "E todo mundo na mesa vê, até quem não instalou nada.", 0.3),
    ], marcas={"acende": (("fala", 1, "inicio"), -0.85), "cor1": (("fala", 3, "inicio"), 0.15),
               "cor2": (("fala", 3, "inicio"), 0.65), "todos": (("fala", 4, "inicio"), 0.2)},
       eventos=[("acende", "ignicao"), ("cor1", "shimmer"), ("cor2", "shimmer"), ("todos", "ding_suave")]),

    dict(id="chat", musica="tema2", inicio=0.6, fim=0.9, falas=[
        ("narrador", "O chat também ficou mais esperto.", 0.0),
        ("narrador", "Cadastre o seu nome, e ouça um aviso sempre que alguém falar de você.", 0.3),
        ("aria", "Opa! Alguém me chamou?", 0.9),
        ("narrador", "Links de imagem e de vídeo ganham uma prévia logo abaixo da mensagem.", 0.35),
    ], marcas={"digita_nome": (("fala", 1, "inicio"), 0.5), "mencao": (("fala", 2, "inicio"), -0.75),
               "link_img": (("fala", 3, "inicio"), 0.35), "link_vid": (("fala", 3, "inicio"), 1.25)},
       eventos=[("digita_nome", "digitar"), ("mencao", "ping"), ("link_img", "pop"), ("link_vid", "pop")]),

    dict(id="mestre", musica="tema3", inicio=0.6, fim=1.0, falas=[
        ("mestre", "Próximo turno!", 0.0),
        ("sistema", "Vez de: Aria.", 0.45),  # igual ao anuncio do plugin; sem a pausa vira "vez diaria"
        ("aria", "Agora sim! Nunca mais perco a minha vez.", 0.35),
        ("narrador", "O mestre organiza a iniciativa, e o jogador da vez recebe um aviso na hora.", 0.4),
        ("narrador", "Cada jogador cria o próprio token no mapa com um clique.", 0.3),
        ("narrador", "E você escolhe quais mesas podem piscar na barra de tarefas.", 0.25),
    ], marcas={"clique_prox": (("fala", 0, "fim"), 0.05), "aviso": (("fala", 1, "inicio"), -0.2),
               "token": (("fala", 4, "fim"), -0.55), "pisca": (("fala", 5, "fim"), -1.0)},
       eventos=[("clique_prox", "clique"), ("aviso", "chime_vez"), ("token", "pop"), ("pisca", "tique")]),

    dict(id="instalar", musica="tema1", inicio=0.5, fim=1.0, falas=[
        ("narrador", "Instalar é simples:", 0.0),
        ("narrador", "feche o Firecast,", 0.15),
        ("narrador", "rode o instalador...", 0.15),
        ("narrador", "e abra pelo atalho Firecast Plus.", 0.15),
        ("narrador", "Pronto!", 0.3),
    ], marcas={"passo1": (("fala", 1, "inicio"), 0.0), "passo2": (("fala", 2, "inicio"), 0.0),
               "passo3": (("fala", 3, "inicio"), 0.0), "pronto": (("fala", 4, "inicio"), 0.0)},
       eventos=[("passo1", "tique"), ("passo2", "tique"), ("passo3", "tique"), ("pronto", "sucesso")]),

    dict(id="final", musica="final", inicio=0.8, fim=3.8, falas=[
        ("narrador", "Firecast Plus.", 0.0),
        ("narrador", "Para mestres e jogadores que querem mais da sua mesa.", 0.3),
        ("mestre", "Agora sim... rolem iniciativa!", 0.8),
    ], marcas={"dados": (("fala", 2, "fim"), 0.15), "critico": (("fala", 2, "fim"), 1.8), "boa": (("fala", 2, "fim"), 2.5)},
       eventos=[("dados", "dados_rolando"), ("critico", "critico")]),

    dict(id="creditos", musica="cauda", inicio=4.8, fim=0.0, falas=[], marcas={}, eventos=[]),
]


def texto_para_voz(texto):
    for a, b in PRONUNCIA:
        texto = texto.replace(a, b)
    return texto


def montar_linha_do_tempo(duracoes):
    """duracoes[(cena_id, i)] = segundos da fala i. Devolve as cenas com tempos absolutos (s)."""
    import math
    linha, t = [], 0.0
    for c in CENAS:
        falas, tl = [], c["inicio"]
        for i, (quem, texto, pausa) in enumerate(c["falas"]):
            tl += pausa if i else 0.0
            d = duracoes[(c["id"], i)]
            falas.append(dict(quem=quem, texto=texto, inicio=t + tl, fim=t + tl + d))
            tl += d + (0.12 if i < len(c["falas"]) - 1 else 0.0)
        dur = tl + c["fim"]
        if c["id"] != "creditos":
            dur = math.ceil(dur / COMPASSO - 0.15) * COMPASSO  # corte no tempo forte (tolera 0.36 s a menos)
            dur = max(dur, tl + 0.4)

        def resolver(ref, desloc, falas=falas, t0=t, d=dur):
            if ref[0] == "cena":
                return (t0 if ref[1] == "inicio" else t0 + d) + desloc
            f = falas[ref[1]]
            return (f["inicio"] if ref[2] == "inicio" else f["fim"]) + desloc
        marcas = {k: resolver(r, dl) for k, (r, dl) in c["marcas"].items()}
        linha.append(dict(id=c["id"], musica=c["musica"], inicio=t, fim=t + dur, falas=falas, marcas=marcas,
                          eventos=[(marcas[m], som) for m, som in c["eventos"]]))
        t += dur
    return linha


if __name__ == "__main__":  # autoteste com duracoes falsas
    falsas = {(c["id"], i): 2.0 for c in CENAS for i in range(len(c["falas"]))}
    lt = montar_linha_do_tempo(falsas)
    for c in lt:
        assert abs((c["fim"] - c["inicio"]) / COMPASSO - round((c["fim"] - c["inicio"]) / COMPASSO)) < 1e-6 or c["id"] == "creditos"
        assert all(c["inicio"] <= f["inicio"] < f["fim"] <= c["fim"] for f in c["falas"]), c["id"]
        assert all(c["inicio"] - 2.5 <= tm <= c["fim"] for tm in c["marcas"].values()), c["id"]
    print("ok", round(lt[-1]["fim"], 1), "s;", texto_para_voz("Firecast Plus, um plugin com skin e token on-line"))
