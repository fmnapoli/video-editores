"""Glossário de pronúncia: troca termos em inglês (e siglas) pela grafia que a voz pt-BR
lê direito. Só o texto falado muda; a legenda exibida fica com a grafia normal.

A voz padrão (pt-BR-ThalitaMultilingualNeural) já pronuncia inglês: com ela a grafia
fonética atrapalha, então o glossário padrão NÃO é carregado para vozes "Multilingual".

Ordem de carga (o último vence):
  1. glossario-ingles.json da skill (seções "validados" e "nao_validados"), só para voz
     não multilíngue (ex.: pt-BR-FranciscaNeural) ou com "glossary": true no spec;
  2. "glossary" do spec: caminho de um JSON {termo: pronúncia} ou o dicionário inline,
     aplicado com qualquer voz (para o termo que a voz errar).
     Pronúncia "" ou null remove o termo. "glossary": false desliga tudo.

Regras de casamento:
  - palavra inteira; termos com espaço casam com qualquer espaço ("pull request");
  - termos mais longos primeiro ("web app" antes de "app");
  - termo todo em MAIÚSCULAS (sigla: API, URL) casa só em maiúsculas; o resto ignora caixa;
  - plural com "s" no fim herda a pronúncia + "s" ("containers" -> "contêiners");
  - termo colado depois de um ponto é extensão ou nome de arquivo e não é trocado ("arquivo .log",
    "appserver.ini"), a não ser que a própria chave comece com ponto (".bak") ou contenha o nome inteiro.
"""
import difflib, json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "glossario-ingles.json")


def _flat(d):
    out = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            out.update(_flat(v))
        else:
            out[k] = v
    return out


def load(spec_glossary=None, base_dir=".", voice=""):
    if spec_glossary is False:
        return {}
    use_default = spec_glossary is True or "Multilingual" not in voice
    g = _flat(json.load(open(DEFAULT, encoding="utf-8"))) if use_default and os.path.exists(DEFAULT) else {}
    if isinstance(spec_glossary, str):
        p = spec_glossary if os.path.isabs(spec_glossary) else os.path.join(base_dir, spec_glossary)
        spec_glossary = json.load(open(p, encoding="utf-8"))
    if isinstance(spec_glossary, dict):
        g.update(_flat(spec_glossary))
    return {k: v for k, v in g.items() if v}


def _compile(keys, flags):
    if not keys:
        return None
    alt = "|".join(r"\s+".join(map(re.escape, k.split())) for k in sorted(keys, key=len, reverse=True))
    return re.compile(rf"(?<!\w)({alt})(s?)(?!\w)", flags)


def apply(text, gloss):
    if not gloss or not text:
        return text
    acr = {k: v for k, v in gloss.items() if k.isupper() and len(k) > 1}
    low = {k.lower(): v for k, v in gloss.items() if k not in acr}

    def extensao(m):
        return m.start() > 0 and m.string[m.start() - 1] == "." and not m.group(1).startswith(".")

    def sub_low(m):
        if extensao(m):
            return m.group(0)
        key = re.sub(r"\s+", " ", m.group(1)).lower()
        return low[key] + m.group(2)

    def sub_acr(m):
        if extensao(m):
            return m.group(0)
        return acr[re.sub(r"\s+", " ", m.group(1))] + m.group(2)

    r = _compile(low.keys(), re.IGNORECASE)
    if r:
        text = r.sub(sub_low, text)
    r = _compile(acr.keys(), 0)
    if r:
        text = r.sub(sub_acr, text)
    return text


# ---------------------------------------------------------------- grafia original na legenda
def _chave(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(ch for ch in t if ch.isalnum())


def _termos_compostos(text, gloss):
    """Trechos (início, fim) do texto casados por termo do glossário com espaço ("pull request")."""
    acr = [k for k in gloss if k.isupper() and len(k) > 1 and " " in k]
    low = [k for k in gloss if " " in k and k not in acr]
    trechos = []
    for keys, flags in ((low, re.IGNORECASE), (acr, 0)):
        r = _compile(keys, flags)
        if r:
            trechos += [(m.start(), m.end()) for m in r.finditer(text)]
    return trechos


def grupos(narracao, gloss):
    """[(grafia original, [palavras faladas])], um por token da narração; termo do glossário com espaço
    vira um grupo só. As palavras faladas são as que a voz recebe para aquele token (glossário aplicado)."""
    toks = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", narracao or "")]
    trechos = _termos_compostos(narracao or "", gloss) if gloss else []
    out, i = [], 0
    while i < len(toks):
        j = i + 1
        for a, b in trechos:
            if toks[i][0] <= a < toks[i][1]:
                while j < len(toks) and toks[j][0] < b:
                    j += 1
                break
        txt = narracao[toks[i][0]:toks[j - 1][1]]
        out.append((txt, apply(txt, gloss).split()))
        i = j
    return out


def alinhar(faladas, narracao, gloss):
    """Casa as palavras devolvidas pela voz (glossário aplicado, sem pontuação) com os tokens da narração.

    Devolve [(grafia original, [índices em `faladas`])], na ordem da narração e com todos os tokens. Um termo
    que virou várias palavras ("PDV" -> "pê dê vê") junta as N; várias que viraram uma também. O casamento é
    global (difflib), então um termo longo não desliza o resto da cena; palavra falada sem par fica com o
    token do trecho correspondente (ou do vizinho anterior); token sem palavra falada sai com a lista vazia.
    """
    gs = grupos(narracao, gloss)
    esperado, dono = [], []
    for gi, (_, ws) in enumerate(gs):
        for w in ws:
            k = _chave(w)
            if k:
                esperado.append(k)
                dono.append(gi)
    fala = [_chave(w) for w in faladas]
    mapa = [None] * len(faladas)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=fala, b=esperado, autojunk=False).get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                mapa[i1 + k] = dono[j1 + k]
        elif op == "replace":
            for k in range(i2 - i1):
                mapa[i1 + k] = dono[j1 + k * (j2 - j1) // (i2 - i1)]
    ult = next((g for g in mapa if g is not None), 0)
    for i, g in enumerate(mapa):
        if g is None:
            mapa[i] = ult
        ult = mapa[i]
    idx = [[] for _ in gs]
    for i, g in enumerate(mapa):
        if gs:
            idx[g].append(i)
    return [(txt, idx[gi]) for gi, (txt, _) in enumerate(gs)]


def com_grafia(words, narracao, gloss, palavra=lambda w: w["w"], intervalo=lambda w: (w["t"], w["t"] + w["d"])):
    """[(início, fim, grafia original)] para cada token da narração, com o tempo da primeira à última palavra
    falada que ele gerou. Token sem palavra falada fica colado no fim do anterior, com duração zero."""
    out, fim = [], 0.0
    for txt, ids in alinhar([palavra(w) for w in words], narracao, gloss):
        if ids:
            a, b = intervalo(words[ids[0]])[0], max(intervalo(words[i])[1] for i in ids)
        else:
            a = b = fim
        out.append((a, b, txt))
        fim = b
    return out
