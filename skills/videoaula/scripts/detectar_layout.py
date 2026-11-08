#!/usr/bin/env python3
"""Medições automáticas para o aula.json: círculo da webcam (centro e raio) num frame de quadro, e régua de layout
da IDE (grade com linhas a cada 100 px) para definir os `crop` de `codigo_grupos`.

Uso: uv run --with pillow --with numpy python detectar_layout.py VIDEO cenas.json [--saida trabalho/<slug>/layout]
  - escolhe a cena de quadro mais longa, extrai um frame e acha o maior blob não branco no quadrante inferior direito
    (a webcam circular); imprime {"cx","cy","r"} para colar em aula.json;
  - para cada cena de código, extrai 2 frames, estima onde o editor começa (coluna onde a densidade de texto sobe depois
    de um vão) e agrupa cenas com a mesma estimativa; gera <saida>/regua_<grupo>.jpg com régua de 100 px e um rascunho de
    `codigo_grupos` (crop sugerido: [x_editor, 150, x_editor + 830, 1040]) para conferir no frame antes de usar.
"""
import argparse, json, os, subprocess

import numpy as np
from PIL import Image, ImageDraw


def frame(video, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3).astype(int)


def circulo(a):
    reg = a[540:1080, 960:1920]
    mask = (np.abs(reg - 255).sum(axis=2) > 60)
    mask[-60:, :] = False                      # barra de status/sistema no rodapé
    ys, xs = np.where(mask)
    if len(xs) < 1000: return None
    x0, x1 = np.percentile(xs, 0.2), np.percentile(xs, 99.8); y0, y1 = np.percentile(ys, 0.2), np.percentile(ys, 99.8)
    return {"cx": int((x0 + x1) / 2 + 960), "cy": int((y0 + y1) / 2 + 540), "r": int(((x1 - x0) + (y1 - y0)) / 4)}


def x_editor(a):
    """Coluna onde começa o painel de código: depois do último vão sem texto à esquerda da metade da tela."""
    band = a[150:1000]
    text = (band.max(axis=2) > 110).mean(axis=0)   # densidade de pixels claros por coluna
    gaps = text[:960] < 0.004
    # último vão de >= 25 colunas antes de x=960 cuja direita tem texto sustentado
    x = 0; i = 0
    while i < 940:
        if gaps[i]:
            j = i
            while j < 960 and gaps[j]: j += 1
            if j - i >= 25 and text[j:j + 120].mean() > 0.01: x = j
            i = j
        else: i += 1
    return int(x)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("cenas"); ap.add_argument("--saida", default="layout")
    ap.add_argument("--quadro", default="quadro"); ap.add_argument("--codigo", default="codigo")
    a = ap.parse_args(); os.makedirs(a.saida, exist_ok=True)
    cenas = json.load(open(a.cenas, encoding="utf-8"))
    q = max((c for c in cenas if c["kind"] == a.quadro), key=lambda c: c["end"] - c["start"], default=None)
    if q:
        c = circulo(frame(a.video, (q["start"] + q["end"]) / 2))
        print("circulo:", json.dumps(c) if c else "não encontrado (fundo do quadro não é claro?)")
    cods = [c for c in cenas if c["kind"] == a.codigo]
    est = {}
    for c in cods:
        if c["end"] - c["start"] < 15: continue           # cena curta: herda o grupo da vizinha longa
        xs = [x_editor(frame(a.video, c["start"] + (c["end"] - c["start"]) * f)) for f in (0.3, 0.7)]
        est[id(c)] = int(np.median(xs))
    for c in cods:
        if id(c) not in est:
            longas = [k for k in cods if id(k) in est]
            viz = min(longas, key=lambda k: abs(k["start"] - c["start"]), default=None)
            est[id(c)] = est[id(viz)] if viz else 0
    grupos = {}
    for c in cods:                                        # chaves a 60 px; grupos vizinhos (<= 60 px) se fundem
        key = int(round(est[id(c)] / 60) * 60)
        k2 = next((k for k in grupos if abs(k - key) <= 60), key)
        grupos.setdefault(k2, []).append(c)
    draft = []
    for gi, (key, cs) in enumerate(sorted(grupos.items())):
        g = chr(ord("A") + gi); c0 = cs[0]
        img = Image.fromarray(frame(a.video, (c0["start"] + c0["end"]) / 2).astype(np.uint8)); d = ImageDraw.Draw(img)
        for x in range(0, 1920, 100): d.line((x, 0, x, 1080), fill=(255, 0, 0), width=1); d.text((x + 2, 540), str(x), fill=(255, 255, 0))
        for y in range(0, 1080, 100): d.line((0, y, 1920, y), fill=(0, 255, 255), width=1); d.text((4, y + 2), str(y), fill=(0, 255, 255))
        d.rectangle((key, 150, key + 830, 1040), outline=(255, 212, 59), width=3)
        img.save(f"{a.saida}/regua_{g}.jpg", quality=88)
        draft.append({"grupo": g, "orig_ini": int(min(c["start"] for c in cs)), "orig_fim": int(max(c["end"] for c in cs)),
                      "crop": [key, 150, key + 830, 1040], "cenas": [c["n"] for c in cs if "n" in c]})
    print("codigo_grupos (rascunho — confira as réguas em", a.saida + "):")
    print(json.dumps(draft, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
