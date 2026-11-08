"""Folha de contato por cena: um quadro de cada cena no instante pedido (fração da duração).

Uso: python3 folha_cenas.py cenas/<slug>.json <pasta dos mp4> [--fracao 0.9] [--saida trabalho/<slug>/folha_0.9.png]
     [--colunas 4] [--largura 480] [--cenas B1,B2]

Use 0,5 para ver o meio da animação e 0,9 para o estado final de cada cena (é nele que se vê se algo
encosta na faixa da legenda). Olhe o PNG com Read antes do render em 1080p.
"""
import argparse
import json
import os
import subprocess


def duracao(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("pasta")
    ap.add_argument("--fracao", type=float, default=0.9)
    ap.add_argument("--saida")
    ap.add_argument("--colunas", type=int, default=4)
    ap.add_argument("--largura", type=int, default=480)
    ap.add_argument("--cenas", help="ids separados por vírgula; padrão todas")
    a = ap.parse_args()

    spec = json.load(open(a.spec, encoding="utf-8"))
    cenas = spec if isinstance(spec, list) else spec["cenas"]
    slug = (spec.get("slug") if isinstance(spec, dict) else None) or os.path.splitext(os.path.basename(a.spec))[0]
    ids = [c["id"] for c in cenas]
    if a.cenas:
        ids = [i for i in ids if i in a.cenas.split(",")]
    saida = a.saida or os.path.join("trabalho", slug, f"folha_{a.fracao:.2f}.png")
    quadros = os.path.join(os.path.dirname(saida) or ".", "quadros")
    os.makedirs(quadros, exist_ok=True)
    ins = []
    for i in ids:
        f = os.path.join(a.pasta, f"{i}.mp4")
        t = max(0.0, duracao(f) * a.fracao - 0.05)
        png = os.path.join(quadros, f"{i}_{a.fracao:.2f}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1",
                        "-vf", f"scale={a.largura}:-2", png], check=True)
        ins += ["-i", png]
    n, cols = len(ids), a.colunas
    if n == 1:
        subprocess.run(["cp", ins[1], saida], check=True)
    else:
        lay = "|".join(f"{'0' if i % cols == 0 else '+'.join(['w0'] * (i % cols))}_{'0' if i // cols == 0 else '+'.join(['h0'] * (i // cols))}"
                       for i in range(n))
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex",
                        f"xstack=inputs={n}:layout={lay}:fill=black[v]", "-map", "[v]", saida], check=True)
    print(f"ok -> {saida} ({n} cenas, fração {a.fracao})")


if __name__ == "__main__":
    main()
