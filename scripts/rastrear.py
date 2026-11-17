#!/usr/bin/env python3
"""Rastreamento (tracking): acompanha uma região do vídeo quadro a quadro e gruda uma etiqueta nela.

Você marca a região uma vez (--caixa, no instante --inicio); o script segue os pontos de textura dela com fluxo
óptico (Lucas-Kanade, ida e volta) e ajusta, a cada quadro, deslocamento + escala + rotação (RANSAC). Grava
<id>.rastro.json com a posição em fração do quadro (0–1) e, com --etiqueta, um .ass com um evento por quadro,
para o texto andar junto com o objeto. Sem modelo de IA: só OpenCV, determinístico.

Uso: rastrear.py VIDEO --caixa X,Y,L,A [--inicio 0] [--fim T] [--id nome] [--out PASTA]
       [--etiqueta "TEXTO"] [--ancora cima|baixo|centro|esquerda|direita] [--tamanho 0.035] [--cor "#FFD54F"]
       [--seta] [--girar] [--sem-escala] [--suavizar 5] [--font FONTE] [--marca marca.json] [--burn SAIDA.mp4]
     --caixa em fração do quadro: canto superior esquerdo (X,Y), largura e altura. Ex.: 0.40,0.55,0.20,0.15

Sai com código 2 quando perde o objeto (saiu de quadro, foi coberto, corte de cena): o JSON e o ASS vão até o
último quadro confiável e a mensagem diz o instante, para você encurtar --fim ou marcar de novo dali.

Limites: segue um plano que se desloca, aproxima e gira; não corrige perspectiva (texto "deitado no chão").
Região lisa (céu, parede) não tem ponto para seguir: marque uma parte com textura ou borda.

Dependências: `uv run --with opencv-python-headless --with numpy` (ou `video-editores rastrear ...`).
"""
import argparse
import json
import math
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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # marca_cli, também sob `python -I`
from video_editores.nucleo import ass, quadros  # noqa: E402
from video_editores.nucleo.ffmpeg import fps as probe_fps  # noqa: E402
from video_editores.nucleo.ffmpeg import probe_dimensoes  # noqa: E402

LARGURA = 960
MIN_PONTOS = 8
CORTE_DE_CENA = 45.0   # diferença média de brilho entre quadros vizinhos que indica troca de plano


def _pontos(cv2, np, cinza, quad):
    """Cantos de textura dentro do quadrilátero atual."""
    masc = np.zeros(cinza.shape, np.uint8)
    cv2.fillConvexPoly(masc, quad.astype(np.int32), 255)
    p = cv2.goodFeaturesToTrack(cinza, maxCorners=300, qualityLevel=0.01, minDistance=4, mask=masc, blockSize=5)
    return p if p is not None else np.zeros((0, 1, 2), np.float32)


def rastrear(video, caixa, inicio, fim):
    try:
        import cv2
        import numpy as np
    except ImportError:
        sys.exit("faltam dependências: uv run --with opencv-python-headless --with numpy ...")
    lk = dict(winSize=(21, 21), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    x, y, lw, lh = caixa
    ant = None
    quad0 = total = pts = None
    alvo = 0
    saida, perdido, motivo = [], None, None
    for _, t, q in quadros.ler(video, largura=LARGURA, inicio=inicio, fim=fim, cinza=True):
        h, w = q.shape
        if ant is None:
            quad0 = np.float32([[x * w, y * h], [(x + lw) * w, y * h], [(x + lw) * w, (y + lh) * h], [x * w, (y + lh) * h]])
            pts = _pontos(cv2, np, q, quad0)
            if len(pts) < MIN_PONTOS:
                sys.exit(f"região sem textura para seguir ({len(pts)} pontos): marque uma parte com bordas ou detalhes")
            alvo = len(pts)
            total = np.eye(3, dtype=np.float64)
            conf = 1.0
        else:
            if float(np.mean(cv2.absdiff(q, ant))) > CORTE_DE_CENA:
                perdido, motivo = t, "corte de cena"
                break
            novo, st, _ = cv2.calcOpticalFlowPyrLK(ant, q, pts, None, **lk)
            volta, st2, _ = cv2.calcOpticalFlowPyrLK(q, ant, novo, None, **lk)
            ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.abs(pts - volta).reshape(-1, 2).max(axis=1) < 1.0)
            a, b = pts[ok], novo[ok]
            M, inl = (cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=2.5)
                      if len(a) >= MIN_PONTOS else (None, None))
            n_in = int(inl.sum()) if inl is not None else 0
            if M is None or n_in < MIN_PONTOS:
                perdido, motivo = t, "pontos insuficientes (objeto coberto, borrado ou fora de quadro)"
                break
            total = np.vstack([M, [0, 0, 1]]) @ total
            conf = n_in / max(1, len(pts))
            pts = b[inl.ravel() == 1].reshape(-1, 1, 2)
        quad = cv2.transform(quad0.reshape(-1, 1, 2), total[:2]).reshape(-1, 2)
        c = quad.mean(axis=0)
        if not (-0.1 * w < c[0] < 1.1 * w and -0.1 * h < c[1] < 1.1 * h):
            perdido, motivo = t, "objeto saiu de quadro"
            break
        escala = math.sqrt(abs(total[0, 0] * total[1, 1] - total[0, 1] * total[1, 0]))
        if not 0.2 < escala < 5:
            perdido, motivo = t, "escala fora do razoável (rastreio derivou)"
            break
        rot = math.degrees(math.atan2(total[1, 0], total[0, 0]))
        saida.append({"t": round(t, 4), "cx": round(float(c[0]) / w, 5), "cy": round(float(c[1]) / h, 5),
                      "escala": round(escala, 4), "rot": round(rot, 3), "conf": round(conf, 3),
                      "cantos": [[round(float(px) / w, 5), round(float(py) / h, 5)] for px, py in quad]})
        if ant is not None and len(pts) < 0.6 * alvo:   # repõe pontos dentro da região atual
            extra = _pontos(cv2, np, q, quad)
            if len(extra):
                pts = np.vstack([pts, extra])[:300]
        ant = q.copy()
    return saida, perdido, motivo


def _media(viz, f):
    return sum(f(v) for v in viz) / len(viz)


def suavizar(qs, janela):
    """Média móvel centrada (sem atraso) de centro, cantos, escala e rotação; tira o tremor de 1 px do fluxo
    óptico em tudo que posiciona a etiqueta, qualquer que seja a âncora."""
    if janela < 2 or len(qs) < 3:
        return qs
    m = janela // 2
    out = []
    for i, q in enumerate(qs):
        viz = qs[max(0, i - m): i + m + 1]
        cantos = [[_media(viz, lambda v, k=k: v["cantos"][k][0]), _media(viz, lambda v, k=k: v["cantos"][k][1])]
                  for k in range(4)]
        out.append(dict(q, cx=_media(viz, lambda v: v["cx"]), cy=_media(viz, lambda v: v["cy"]),
                        escala=_media(viz, lambda v: v["escala"]), rot=_media_angulo([v["rot"] for v in viz]), cantos=cantos))
    return out


def _media_angulo(graus):
    """Média circular em graus: a aritmética de 179 e -179 daria 0 e a etiqueta daria uma volta na virada de ±180."""
    s = sum(math.sin(math.radians(g)) for g in graus)
    c = sum(math.cos(math.radians(g)) for g in graus)
    return math.degrees(math.atan2(s, c)) if (abs(s) > 1e-9 or abs(c) > 1e-9) else graus[len(graus) // 2]


def eventos_ass(qs, W, H, fps, a, cor_txt):
    """Um evento por quadro. A fronteira de cada evento fica meio quadro antes do instante do quadro, para o
    arredondamento do ASS (centésimos) nunca jogar o evento no quadro vizinho."""
    px = int(H * a.tamanho)
    meio = 0.5 / fps
    n = len(qs)
    rampa = max(1, int(round(fps * 0.2)))   # entrada e saída em 0,2 s: \fad não serve em evento de 1 quadro
    linhas = []
    for i, q in enumerate(qs):
        ini, fim = max(0.0, q["t"] - meio), q["t"] + meio
        if ass.tempo(ini) == ass.tempo(fim):
            continue
        xs = [c[0] * W for c in q["cantos"]]
        ys = [c[1] * H for c in q["cantos"]]
        cx, cy = q["cx"] * W, q["cy"] * H
        fs = px if a.sem_escala else int(round(px * min(2.5, max(0.4, q["escala"]))))
        folga = fs * 0.45   # proporcional ao tamanho já escalado: a seta nunca entra no texto
        an, x, y = {"cima": (2, cx, min(ys) - folga), "baixo": (8, cx, max(ys) + folga), "centro": (5, cx, cy),
                    "esquerda": (6, min(xs) - folga, cy), "direita": (4, max(xs) + folga, cy)}[a.ancora]
        alfa = int(round(255 * (1 - min(1.0, (i + 1) / rampa, (n - i) / rampa))))
        tags = [f"\\an{an}", f"\\pos({x:.1f},{y:.1f})", f"\\fs{fs}", f"\\1c{cor_txt}", "\\b1",
                f"\\bord{max(2, fs // 12)}", "\\3c&H000000&", f"\\alpha&H{alfa:02X}&"]
        if a.girar:
            tags.append(f"\\frz{-q['rot']:.2f}")
        linhas.append(f"Dialogue: 1,{ass.tempo(ini)},{ass.tempo(fim)},Base,,0,0,0,,{{{''.join(tags)}}}{ass.texto(a.etiqueta)}")
        if a.seta and a.ancora in ("cima", "baixo"):
            s = fs * 0.32
            ponta = min(ys) - folga * 0.15 if a.ancora == "cima" else max(ys) + folga * 0.15
            base = ponta - s if a.ancora == "cima" else ponta + s
            tri = f"m {cx - s * 0.6:.0f} {base:.0f} l {cx + s * 0.6:.0f} {base:.0f} l {cx:.0f} {ponta:.0f}"
            linhas.append(f"Dialogue: 0,{ass.tempo(ini)},{ass.tempo(fim)},Base,,0,0,0,,"
                          f"{{\\an7\\pos(0,0)\\1c{cor_txt}\\bord1\\3c&H000000&\\alpha&H{alfa:02X}&\\p1}}{tri}{{\\p0}}")
    return linhas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--caixa", required=True, help="X,Y,L,A em fração do quadro (0–1)")
    ap.add_argument("--inicio", type=float, default=0.0)
    ap.add_argument("--fim", type=float, default=None)
    ap.add_argument("--id", default=None, help="nome dos arquivos de saída (padrão: <vídeo>_<início>)")
    ap.add_argument("--out", default=None, help="pasta de saída (padrão: trabalho/<nome>/ se existir trabalho/, senão ao lado do vídeo)")
    ap.add_argument("--etiqueta", default=None, help='texto que acompanha a região ("\\N" quebra linha)')
    ap.add_argument("--ancora", default="cima", choices=["cima", "baixo", "centro", "esquerda", "direita"])
    ap.add_argument("--tamanho", type=float, default=0.035, help="altura da fonte em fração da altura do vídeo")
    ap.add_argument("--cor", default=None, help="padrão: acento da marca, senão #FFD54F")
    ap.add_argument("--seta", action="store_true", help="triângulo apontando para a região (âncora cima ou baixo)")
    ap.add_argument("--girar", action="store_true", help="a etiqueta gira com o objeto")
    ap.add_argument("--sem-escala", action="store_true", help="a etiqueta não cresce nem encolhe com o objeto")
    ap.add_argument("--suavizar", type=int, default=5, help="janela da média móvel da posição, em quadros (1 desliga)")
    ap.add_argument("--font", default=None, help="padrão: fonte da marca, senão DejaVu Sans")
    ap.add_argument("--burn", default=None)
    import marca_cli
    marca_cli.add_arg(ap)
    a = ap.parse_args()
    try:
        caixa = [float(v) for v in a.caixa.split(",")]
        assert len(caixa) == 4 and all(0 <= v <= 1 for v in caixa) and caixa[2] > 0 and caixa[3] > 0
        assert caixa[0] + caixa[2] <= 1.0001 and caixa[1] + caixa[3] <= 1.0001
    except (ValueError, AssertionError):
        sys.exit("--caixa X,Y,L,A: quatro números entre 0 e 1 (fração do quadro), com a caixa dentro do quadro")
    if a.burn and not a.etiqueta:
        sys.exit("--burn precisa de --etiqueta")

    if a.fim is not None and a.fim <= a.inicio:
        sys.exit("--fim precisa ser maior que --inicio")
    qs, perdido, motivo = rastrear(a.video, caixa, a.inicio, a.fim)
    if not qs and perdido is None:
        sys.exit(f"nenhum quadro entre {a.inicio:g}s e {'o fim' if a.fim is None else f'{a.fim:g}s'}: confira --inicio (o vídeo é mais curto?)")
    W, H = probe_dimensoes(a.video)
    fps = probe_fps(a.video)
    src = pathlib.Path(a.video)
    pasta = pathlib.Path(a.out) if a.out else (pathlib.Path("trabalho") / src.stem if pathlib.Path("trabalho").is_dir() else src.parent)
    pasta.mkdir(parents=True, exist_ok=True)
    ident = a.id or f"{src.stem}_{a.inicio:g}s"
    arq = pasta / f"{ident}.rastro.json"
    arq.write_text(json.dumps({"source": str(a.video), "largura": W, "altura": H, "fps": round(fps, 4),
                               "caixa_inicial": caixa, "inicio": a.inicio, "fim": qs[-1]["t"] if qs else a.inicio,
                               "perdido_em": perdido, "motivo": motivo, "quadros": qs}, ensure_ascii=False), encoding="utf-8")
    conf = min((q["conf"] for q in qs), default=0)
    print(f"rastro: {len(qs)} quadros ({a.inicio:g}s–{qs[-1]['t'] if qs else a.inicio:g}s), confiança mínima {conf:.2f} -> {arq}")

    if a.etiqueta and qs:
        m = marca_cli.carregar(a.marca)
        fonte = marca_cli.escolhe(a.font, m.fonte, "DejaVu Sans", m)
        cor_txt = ass.cor(marca_cli.escolhe(a.cor, m.cores["acento"], "#FFD54F", m))
        linhas = eventos_ass(suavizar(qs, a.suavizar), W, H, fps, a, cor_txt)
        arq_ass = pasta / f"{ident}.rastro.ass"
        arq_ass.write_text(ass.documento(W, H, fonte, linhas), encoding="utf-8")
        print(f"ass -> {arq_ass}")
        if a.burn:
            ass.queimar(a.video, arq_ass, a.burn, marca_cli.fontsdir(m))
            print(f"ok -> {a.burn}")
    if perdido is not None:
        print(f"PERDIDO em {perdido:.2f}s: {motivo}. O rastro vale até {qs[-1]['t'] if qs else a.inicio:.2f}s; "
              f"use --fim {max(a.inicio, perdido - 0.1):.2f} ou marque a região de novo a partir dali.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
