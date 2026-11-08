#!/usr/bin/env python3
"""Classifica as cenas do PySceneDetect pelo modo visual de uma videoaula gravada:
`locutor` (pessoa em tela cheia), `quadro` (quadro branco/Excalidraw, fundo claro) ou `codigo` (IDE escura).

Uso: uv run --with pillow --with numpy python cenas_modo.py CENAS.csv PASTA_FRAMES cenas.json
     [--branco 0.55] [--pele 0.12] [--regiao-quadro 100,150,1300,600] [--regiao-rosto 700,250,1250,750]
As regiões são em px numa referência 1920x1080 (escaladas para o frame real).
Confira o resultado numa grade de frames: a heurística é simples de propósito; corrija o JSON à mão se precisar.
"""
import argparse, csv, glob, json

import numpy as np
from PIL import Image


def classify(img, rq, rr, lim_branco, lim_pele):
    a = np.asarray(img.convert("RGB")).astype(int)
    h, w, _ = a.shape
    sx, sy = w / 1920, h / 1080
    def reg(x0, y0, x1, y1):
        return a[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)]
    canvas = reg(*rq)
    branco = float((canvas > 225).all(axis=2).mean())
    c = reg(*rr); r, g, b = c[..., 0], c[..., 1], c[..., 2]
    pele = float(((r > 110) & (r > g) & (g > b) & (r - b > 25) & (r - g > 8)).mean())
    kind = "quadro" if branco > lim_branco else ("locutor" if pele > lim_pele else "codigo")
    return kind, round(branco, 2), round(pele, 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv"); ap.add_argument("frames"); ap.add_argument("out")
    ap.add_argument("--branco", type=float, default=0.55); ap.add_argument("--pele", type=float, default=0.12)
    ap.add_argument("--regiao-quadro", default="100,150,1300,600"); ap.add_argument("--regiao-rosto", default="700,250,1250,750")
    a = ap.parse_args()
    rq = [int(x) for x in a.regiao_quadro.split(",")]; rr = [int(x) for x in a.regiao_rosto.split(",")]
    with open(a.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader([ln for ln in f if not ln.startswith("Timecode List")]))
    scenes = []
    for r in rows:
        n = int(r["Scene Number"])
        imgs = sorted(glob.glob(f"{a.frames}/*Scene-{n:03d}*"))
        if not imgs:
            print("sem frame para a cena", n); continue
        kind, branco, pele = classify(Image.open(imgs[0]), rq, rr, a.branco, a.pele)
        scenes.append({"n": n, "start": float(r["Start Time (seconds)"]), "end": float(r["End Time (seconds)"]),
                       "len": float(r["Length (seconds)"]), "kind": kind, "branco": branco, "pele": pele, "frame": imgs[0]})
    json.dump(scenes, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    tot = {}
    for s in scenes:
        print(f"{s['n']:3d} {s['start']:8.1f} -> {s['end']:8.1f} ({s['len']:6.1f}s) {s['kind']:8s} branco={s['branco']} pele={s['pele']}")
        tot[s["kind"]] = tot.get(s["kind"], 0) + s["len"]
    print("total por modo (s):", {k: round(v) for k, v in tot.items()})


if __name__ == "__main__":
    main()
