#!/usr/bin/env python3
"""Confere se o .mp4 e o .srt de cada spec correspondem ao spec atual (pega vídeo velho depois de um lote que falhou).

Uso: python3 confere_saida.py specs/*/spec.json
Para cada spec: o .mp4 e o .srt existem, o texto do .srt é o texto das legendas do spec, e o .mp4 é mais
novo que o spec. Imprime OK/REFAZER/FALTA por slug e sai com 1 se algum precisar ser remontado.
Caminhos relativos do spec (out_dir, srt_dir) valem a partir do diretório atual, como no build.py.
"""
import json
import os
import re
import sys


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def texto_srt(path):
    linhas = open(path, encoding="utf-8").read().splitlines()
    return norm(" ".join(x for x in linhas if x and not re.fullmatch(r"\d+", x) and "-->" not in x))


def confere(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    slug = spec["slug"]
    mp4 = os.path.join(spec["out_dir"], f"{slug}.mp4")
    srt = os.path.join(spec.get("srt_dir", spec["out_dir"]), f"{slug}.srt")
    if not (os.path.exists(mp4) and os.path.exists(srt)):
        return "FALTA", slug, "sem .mp4 ou .srt"
    legenda = norm(" ".join(b.replace("\n", " ") for sc in spec["scenes"] for b in sc.get("legend", [])))
    motivos = []
    if texto_srt(srt) != legenda:
        motivos.append("legenda do .srt difere do spec")
    if os.path.getmtime(mp4) < os.path.getmtime(spec_path):
        motivos.append(".mp4 mais velho que o spec")
    if os.path.getmtime(mp4) < os.path.getmtime(srt) - 5:
        motivos.append(".srt mais novo que o .mp4")
    return ("REFAZER" if motivos else "OK"), slug, "; ".join(motivos)


def main(paths):
    if not paths:
        raise SystemExit(__doc__)
    ruins = []
    for p in paths:
        st, slug, why = confere(p)
        print(f"{st:8} {slug}" + (f"  ({why})" if why else ""))
        if st != "OK":
            ruins.append(slug)
    if ruins:
        print("remontar: " + " ".join(ruins))
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
