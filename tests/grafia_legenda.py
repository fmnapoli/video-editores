"""Grafia original na legenda quando o glossário muda o número de palavras faladas.

A voz recebe o texto com o glossário aplicado e devolve as fronteiras das palavras FALADAS; a legenda precisa voltar à
grafia do roteiro. Cobre termo de 1 palavra que vira N ("PDV" -> "pê dê vê"), N que vira 1 ("pull request") e termo
repetido na mesma cena, nos dois consumidores: montar_cenas.py (/video-animado) e build.py (/video-docs).
Uso: python3 tests/grafia_legenda.py   (só python3; chamado pelo tests/smoke.sh)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "skills", "video-docs", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "skills", "video-animado", "scripts"))
import build  # noqa: E402
import montar_cenas  # noqa: E402
import pronuncia  # noqa: E402

GLOSS = {"PDV": "pê dê vê", "pdv.dmp": "pê dê vê ponto dê ême pê", "esquema": "esquêma", "pull request": "pulrequést"}
FONETICAS = ("pê", "dê", "vê", "ême", "esquêma", "pulrequést")


def falar(narracao, gloss=GLOSS, passo=0.3):
    """Fronteiras como o edge-tts devolve: palavras faladas sem pontuação, uma a cada `passo` segundos."""
    ws = [re.sub(r"[^\w.]+$|^[^\w]+", "", w) for w in pronuncia.apply(narracao, gloss).split()]
    return [{"t": round(i * passo, 3), "d": round(passo * 0.9, 3), "w": w} for i, w in enumerate(w for w in ws if w)]


def confere(narracao, words, esperado):
    """Tokens da legenda = tokens do roteiro, sem grafia fonética, e cada um com o tempo de suas palavras."""
    out = montar_cenas.com_grafia_original(words, narracao, GLOSS)
    assert [w["w"] for w in out] == list(esperado), [w["w"] for w in out]
    vaz = [w["w"] for w in out if any(f in w["w"].lower().split() or w["w"].lower() == f for f in FONETICAS)]
    assert not vaz, f"grafia fonética na legenda: {vaz}"
    for a, b in zip(out, out[1:]):
        assert a["t"] <= b["t"], (a, b)
    return out


# 1 -> N: "PDV" vira três palavras faladas e "pdv.dmp" vira sete
n1 = "O PDV restaura o pdv.dmp no esquema novo."
out = confere(n1, falar(n1), n1.split())
pdv = out[1]
assert (pdv["t"], round(pdv["t"] + pdv["d"], 3)) == (0.3, 1.17), pdv           # de "pê" (0,3) ao fim de "vê" (0,9 + 0,27)
dmp = out[4]
assert dmp["w"] == "pdv.dmp" and round(dmp["t"], 3) == 1.8 and round(dmp["t"] + dmp["d"], 3) == 3.87, dmp
assert out[5]["w"] == "no" and round(out[5]["t"], 3) == 3.9, out[5]          # o resto da cena não desliza

# N -> 1: "pull request" vira uma palavra falada e volta como um token só
n2 = "Abra o pull request de novo."
out = confere(n2, falar(n2), ["Abra", "o", "pull request", "de", "novo."])
assert round(out[2]["t"], 3) == 0.6 and round(out[3]["t"], 3) == 0.9, out

# termo repetido na mesma cena: cada ocorrência fica com as próprias palavras faladas
n3 = "O PDV fala com o PDV do ERP, e o esquema do PDV muda: PDV, PDV."
out = confere(n3, falar(n3), n3.split())
ini_pdv = [round(w["t"], 3) for w in out if w["w"].startswith("PDV")]
fal = falar(n3)
assert ini_pdv == [round(w["t"], 3) for i, w in enumerate(fal) if w["w"] == "pê"], (ini_pdv, fal)

# a voz juntou "pê dê vê" numa palavra e engoliu um "o": a legenda continua com todos os tokens, na ordem
ws = falar(n3)
ws = [w for i, w in enumerate(ws) if i != 6]                                   # some o segundo "o"
j = next(i for i, w in enumerate(ws) if w["w"] == "pê")
ws[j:j + 3] = [{"t": ws[j]["t"], "d": round(ws[j + 2]["t"] + ws[j + 2]["d"] - ws[j]["t"], 3), "w": "pêdêvê"}]
out = confere(n3, ws, n3.split())
assert out[1]["w"] == "PDV" and out[1]["d"] > 0.5, out[1]
assert out[4]["w"] == "o" and out[4]["d"] == 0, out[4]                         # sem palavra falada: colado, duração zero

# mesmo alinhamento no /video-docs (palavras.transcript.json da legenda palavra a palavra)
lista = [[w["t"], w["d"], w["w"]] for w in falar(n1)]
toks = [tok for _, _, tok in build.com_pontuacao(lista, n1, GLOSS)]
assert toks == n1.split(), toks

print("ok: grafia original na legenda (1 -> N, N -> 1, termo repetido, palavra juntada e engolida, video-docs)")
