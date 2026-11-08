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
  - plural com "s" no fim herda a pronúncia + "s" ("containers" -> "contêiners").
"""
import json, os, re

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

    def sub_low(m):
        key = re.sub(r"\s+", " ", m.group(1)).lower()
        return low[key] + m.group(2)

    def sub_acr(m):
        return acr[re.sub(r"\s+", " ", m.group(1))] + m.group(2)

    r = _compile(low.keys(), re.IGNORECASE)
    if r:
        text = r.sub(sub_low, text)
    r = _compile(acr.keys(), 0)
    if r:
        text = r.sub(sub_acr, text)
    return text
