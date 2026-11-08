#!/usr/bin/env python3
"""SRT final da videoaula: frases da transcrição ORIGINAL (texto inteiro, não palavras soltas) com tempos
remapeados para o corte e deslocados pelas cartelas inseridas. Frases que perderam pedaço num corte manual
são trocadas ou removidas por um JSON de ajustes.

Uso: legenda_aula.py aula.json CORTE.v1.json VIDEO.transcript.json SAIDA.srt [--ajustes ajustes.json]
ajustes.json: {"fixes": {"231.58": "texto final da frase", "937.93": null}, "corr": [["\\\\bidei\\\\b", "dei"]]}
  (chave = início da frase no original, em segundos; null = remover a frase; corr = regex -> substituição)
Só biblioteca padrão.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from remap_tempos import Remap  # noqa: E402
from montar_aula import Aula  # noqa: E402


def ts(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aula"); ap.add_argument("v1"); ap.add_argument("transcript"); ap.add_argument("out")
    ap.add_argument("--ajustes", default=None)
    a = ap.parse_args()
    out = os.path.abspath(a.out); v1 = os.path.abspath(a.v1); tr_p = os.path.abspath(a.transcript)
    aj = json.load(open(a.ajustes, encoding="utf-8")) if a.ajustes else {}
    aula = Aula(a.aula)  # muda para a pasta do aula.json
    rm = Remap(v1)
    fixes = {float(k): v for k, v in aj.get("fixes", {}).items()}
    corr = [(re.compile(p), r) for p, r in aj.get("corr", [])]
    cues = []
    for s in json.load(open(tr_p, encoding="utf-8"))["segments"]:
        a0, b0 = s["start"], s["end"]
        if rm.kept(a0, b0) < 0.3: continue
        text = s["text"].strip()
        key = next((k for k in fixes if abs(k - a0) < 0.3 or (a0 < k < b0)), None)
        if key is not None:
            if fixes[key] is None and rm.kept(a0, b0) < 0.6 * (b0 - a0): continue
            if fixes[key]: text = fixes[key]
        for pat, rep in corr: text = pat.sub(rep, text)
        ca = rm.to_cut(a0); cb = ca + rm.kept(a0, b0)
        fa, fb = aula.map_time(ca), aula.map_time(cb)
        cues.append([fa, max(fb, fa + 0.8), text])
    for i in range(1, len(cues)):
        if cues[i][0] < cues[i - 1][1]: cues[i - 1][1] = cues[i][0] - 0.05
    with open(out, "w", encoding="utf-8") as f:
        for i, (x, y, t) in enumerate(cues, 1): f.write(f"{i}\n{ts(x)} --> {ts(y)}\n{t}\n\n")
    print(f"{len(cues)} legendas -> {out}")


if __name__ == "__main__":
    main()
