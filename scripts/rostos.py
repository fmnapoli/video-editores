#!/usr/bin/env python3
"""Onde está o rosto em cada instante, e se algum texto passou por cima dele.

Dois usos:

1. Localizar (antes de pôr texto): amostra o vídeo a cada --passo segundos, detecta os rostos e grava
   <nome>.rostos.json com as caixas em fração do quadro (0–1), a zona ocupada no vídeo inteiro, quanto
   sobra livre em cada lado e uma sugestão de posição para o texto.

     rostos.py VIDEO [--passo 0.5] [--inicio T] [--fim T] [--min-conf 0.6] [--out ARQ.rostos.json] [--backend yunet]

2. Conferir (depois de queimar texto): compara o vídeo de ANTES da etapa com o de DEPOIS, só dentro das caixas
   de rosto. Onde os pixels mudaram, alguma coisa cobriu o rosto. Lista os intervalos e sai com código 3.
   Os dois vídeos precisam ter a mesma linha do tempo (entrada e saída da mesma etapa: _corte e _lettering).

     rostos.py ANTES.mp4 --conferir DEPOIS.mp4 [--rostos ARQ.rostos.json] [--limiar 28] [--area 0.05]

Dependências: `uv run --with opencv-python-headless --with numpy` (ou `video-editores rostos ...`, que resolve
sozinho). Com --rostos já pronto, a conferência usa só numpy e ffmpeg.
"""
import argparse
import json
import os
import pathlib
import sys


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores import modelos  # noqa: E402
from video_editores.nucleo import quadros  # noqa: E402
from video_editores.nucleo.ffmpeg import duracao, probe_dimensoes  # noqa: E402

LARGURA = 640          # a detecção não precisa de mais; as caixas saem em fração do quadro
ZONA_SEGURA = 0.15     # reels: 15% de cima e de baixo são da interface do aplicativo (convencoes.md)


def saida_padrao(video, sufixo):
    src = pathlib.Path(video)
    base = pathlib.Path("trabalho") / src.stem if pathlib.Path("trabalho").is_dir() else src.parent
    base.mkdir(parents=True, exist_ok=True)
    return base / (src.stem + sufixo)


def resumo(amostras):
    """Zona ocupada pelos rostos no vídeo inteiro, folga em cada lado e sugestão de posição para texto."""
    caixas = [r for q in amostras for r in q["rostos"]]
    if not caixas:
        return None, None, {"lado": "centro", "pos": [0.5, 0.5], "motivo": "nenhum rosto detectado"}
    x0 = min(r["x"] for r in caixas)
    y0 = min(r["y"] for r in caixas)
    x1 = max(r["x"] + r["w"] for r in caixas)
    y1 = max(r["y"] + r["h"] for r in caixas)
    zona = {"x0": round(x0, 4), "y0": round(y0, 4), "x1": round(x1, 4), "y1": round(y1, 4)}
    livre = {"topo": round(y0, 4), "base": round(1 - y1, 4), "esquerda": round(x0, 4), "direita": round(1 - x1, 4)}
    # faixa horizontal útil acima e abaixo do rosto, descontada a zona da interface
    util = {"topo": y0 - ZONA_SEGURA, "base": (1 - ZONA_SEGURA) - y1}
    lado = max(util, key=util.get)
    if util[lado] < 0.08:   # sem faixa horizontal: texto ao lado
        lado = "direita" if livre["direita"] >= livre["esquerda"] else "esquerda"
        x = (x1 + 1) / 2 if lado == "direita" else x0 / 2
        pos = [round(x, 3), round((y0 + y1) / 2, 3)]
    elif lado == "topo":
        pos = [0.5, round((ZONA_SEGURA + y0) / 2, 3)]
    else:
        pos = [0.5, round((y1 + 1 - ZONA_SEGURA) / 2, 3)]
    return zona, livre, {"lado": lado, "pos": pos, "motivo": f"maior faixa sem rosto ({lado})"}


def localizar(a):
    det = modelos.get_rosto(a.backend, device=modelos.device())
    amostras = []
    for _, t, q in quadros.ler(a.video, largura=LARGURA, passo=a.passo, inicio=a.inicio, fim=a.fim):
        h, w = q.shape[:2]
        rostos = [{"x": round(c.x / w, 4), "y": round(c.y / h, 4), "w": round(c.w / w, 4), "h": round(c.h / h, 4),
                   "conf": c.conf} for c in det.detectar(q, a.min_conf)]
        amostras.append({"t": round(t, 3), "rostos": rostos})
    W, H = probe_dimensoes(a.video)
    zona, livre, sug = resumo(amostras)
    com = sum(1 for q in amostras if q["rostos"])
    doc = {"source": str(a.video), "largura": W, "altura": H, "passo": a.passo, "inicio": a.inicio, "backend": det.nome,
           "amostras_com_rosto": com, "amostras": len(amostras), "zona": zona, "livre": livre, "sugestao": sug,
           "quadros": amostras}
    out = pathlib.Path(a.out) if a.out else saida_padrao(a.video, ".rostos.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: rosto em {com}/{len(amostras)} amostras -> {out}")
    if zona:
        print(f"  zona do rosto: x {zona['x0']:.2f}–{zona['x1']:.2f}, y {zona['y0']:.2f}–{zona['y1']:.2f}")
        print(f"  sugestão para texto: {sug['lado']}, pos {sug['pos']}")
    return doc


def intervalos(achados, passo):
    """Junta amostras consecutivas (distância ≤ 1,5 passo) em {inicio, fim, pior}: `pior` é a maior fração coberta."""
    grupos = []
    for x in sorted(achados, key=lambda x: x["t"]):
        if grupos and x["t"] - grupos[-1][-1]["t"] <= passo * 1.5:
            grupos[-1].append(x)
        else:
            grupos.append([x])
    return [{"inicio": round(g[0]["t"], 2), "fim": round(g[-1]["t"] + passo, 2), "pior": max(x["coberto"] for x in g)}
            for g in grupos]


def conferir(a):
    import numpy as np
    if a.rostos:
        doc = json.loads(pathlib.Path(a.rostos).read_text(encoding="utf-8"))
    else:
        doc = localizar(a)
    passo = float(doc["passo"])
    da, dd = duracao(a.video), duracao(a.conferir)
    if abs(da - dd) > max(0.25, passo):
        sys.exit(f"durações diferentes ({da:.2f}s e {dd:.2f}s): compare a entrada e a saída da MESMA etapa "
                 "(mesma linha do tempo), por exemplo _corte.mp4 e _lettering.mp4")
    amostras = doc["quadros"]
    # mesma amostragem da localização (mesmo início e passo): a amostra i dos dois vídeos é a amostra i do JSON
    ini = float(doc.get("inicio", amostras[0]["t"] if amostras else 0.0))
    antes = quadros.ler(a.video, largura=480, passo=passo, inicio=ini, cinza=True)
    depois = quadros.ler(a.conferir, largura=480, passo=passo, inicio=ini, cinza=True)
    achados = []
    for amostra, (_, t, qa), (_, _, qd) in zip(amostras, antes, depois):
        if qa.shape != qd.shape:
            sys.exit("os dois vídeos têm proporções diferentes: compare a entrada e a saída da mesma etapa")
        h, w = qa.shape
        for r in amostra["rostos"]:
            x0, y0 = int(r["x"] * w), int(r["y"] * h)
            x1, y1 = max(x0 + 2, int((r["x"] + r["w"]) * w)), max(y0 + 2, int((r["y"] + r["h"]) * h))
            dif = np.abs(qa[y0:y1, x0:x1].astype(np.int16) - qd[y0:y1, x0:x1].astype(np.int16))
            frac = float((dif > a.limiar).mean()) if dif.size else 0.0
            if frac >= a.area:
                achados.append({"t": round(t, 3), "coberto": round(frac, 3), "rosto": r})
    faixas = intervalos(achados, passo)
    out = pathlib.Path(a.out) if a.out and a.rostos else saida_padrao(a.conferir, ".rosto-coberto.json")
    out.write_text(json.dumps({"antes": str(a.video), "depois": str(a.conferir), "limiar": a.limiar, "area": a.area,
                               "intervalos": [[f["inicio"], f["fim"]] for f in faixas], "amostras": achados}, ensure_ascii=False, indent=1), encoding="utf-8")
    if not faixas:
        print(f"ok: nada cobre o rosto em {len(amostras)} amostras -> {out}")
        return
    print(f"ROSTO COBERTO em {len(faixas)} intervalo(s) -> {out}")
    for f in faixas:
        print(f"  {f['inicio']:.2f}s–{f['fim']:.2f}s  (até {f['pior']:.0%} da área do rosto alterada)")
    print("  mova o texto para a posição de `sugestao` do .rostos.json e refaça a etapa")
    sys.exit(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--passo", type=float, default=0.5, help="intervalo entre amostras, em segundos")
    ap.add_argument("--inicio", type=float, default=0.0)
    ap.add_argument("--fim", type=float, default=None)
    ap.add_argument("--min-conf", type=float, default=0.6)
    ap.add_argument("--out", default=None)
    ap.add_argument("--backend", default=None, help="backend de detecção de rosto (padrão: VE_ROSTO ou yunet)")
    ap.add_argument("--conferir", default=None, metavar="DEPOIS.mp4", help="vídeo depois da etapa de texto")
    ap.add_argument("--rostos", default=None, help=".rostos.json já calculado do vídeo de antes")
    ap.add_argument("--limiar", type=int, default=28, help="diferença de brilho (0–255) que conta como pixel alterado")
    ap.add_argument("--area", type=float, default=0.05, help="fração da caixa do rosto alterada que conta como coberto")
    a = ap.parse_args()
    if a.passo <= 0:
        sys.exit("--passo precisa ser maior que zero")
    if a.conferir:
        conferir(a)
    else:
        localizar(a)


if __name__ == "__main__":
    main()
