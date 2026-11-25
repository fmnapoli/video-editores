#!/usr/bin/env python3
"""Câmera sobre o vídeo já cortado: troca de plano a cada corte (esconde o jump cut), aproximação lenta e punch.

Dois passos, com um arquivo revisável no meio:

1. Planejar: lê de onde vieram os cortes, calcula o quadro exato de cada um no vídeo cortado e grava
   <nome>.camera.json com os planos numerados (cam01, cam02…), os punches e os eventos para o /efeitos.

     camera.py VIDEO --cortes ARQ [--cortes ARQ2 ...] [--rostos ARQ.rostos.json] [--punches ARQ.json]
               [--fechado 1.18] [--deriva 0.03] [--olhos 0.38] [--min-plano 0.8] [--seguir] [--out ARQ.camera.json]
     camera.py VIDEO --cortes-em 3.2,7.9,12.4 ...        (instantes já no tempo do vídeo cortado)

   --cortes aceita, na ordem em que as etapas rodaram: o .takes.json do /tomada (trechos `keep`) e o
   JSON `--export v1` do auto-editor (/corte). VIDEO é a saída da última etapa.

2. Aplicar: renderiza o vídeo com a câmera do .camera.json (editável à mão entre um passo e outro).

     camera.py VIDEO --aplicar ARQ.camera.json SAIDA.mp4

Planejar usa só a biblioteca padrão. Aplicar precisa de `uv run --with opencv-python-headless --with numpy`
(ou `video-editores camera ...`, que resolve sozinho). A câmera vem ANTES de qualquer texto queimado:
legenda e lettering entram depois, sobre o vídeo já com a câmera.
"""
import argparse
import json
import math
import os
import pathlib
import statistics
import subprocess
import sys


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo.ffmpeg import codec_video, probe_dimensoes  # noqa: E402

DERIVA_MIN_S = 4.0     # plano mais curto que isto não faz a aproximação inteira (senão ela vira um zoom rápido)
ATAQUE_PUNCH = 0.07    # o punch sobe em ~2 quadros e assenta: salto instantâneo no meio do take parece defeito
AMPLIA_MAX = 1.35      # acima disto a imagem amolece visivelmente quando a saída tem a resolução da entrada


def sonda(video):
    """(taxa como fração "30000/1001", taxa float, nº de quadros) do vídeo."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=r_frame_rate,nb_read_packets", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True).stdout
    st = json.loads(out)["streams"][0]
    n, d = st["r_frame_rate"].split("/")
    return st["r_frame_rate"], float(n) / float(d), int(st["nb_read_packets"])


def tem_audio(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                          str(video)], capture_output=True, text=True).stdout
    return out.strip() != ""


# ---------------------------------------------------------------- de onde vieram os cortes
def mapa(arquivo, fps, com_audio):
    """Trechos mantidos por uma etapa, como [a, b, o]: os quadros [a, b) da ENTRADA dela começam no quadro o da saída."""
    doc = json.loads(pathlib.Path(arquivo).read_text(encoding="utf-8"))
    if isinstance(doc, dict) and "chunks" in doc:        # auto-editor --export v1: quadros, speed 1 = mantido
        brutos = [[int(c[0]), int(c[1]), None] for c in doc["chunks"] if c[2] == 1]
    elif isinstance(doc, dict) and "keep" in doc:        # takes.py / highlights.py: segundos
        # render_spans.sh corta com trim=s:e (3 casas): fica o quadro n com s <= n/fps < e
        brutos = [[math.ceil(round(s, 3) * fps - 1e-6), math.ceil(round(e, 3) * fps - 1e-6), round(e, 3) - round(s, 3)]
                  for s, e in doc["keep"]]
    else:
        sys.exit(f"{arquivo}: não é um .takes.json (keep) nem um JSON v1 do auto-editor (chunks)")
    juntos = []
    for a, b, d in brutos:
        if b <= a:
            continue
        if juntos and d is None and a <= juntos[-1][1]:   # trechos vizinhos do v1 sem nada cortado entre eles
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b, d])
    # Onde cada trecho começa na saída. No v1 é a soma dos quadros. No render_spans.sh cada trecho ocupa, na linha
    # do tempo do concat, o maior entre o vídeo (quadros inteiros) e o áudio (e - s): com áudio, o trecho seguinte
    # começa em e - s, não no fim do último quadro, e o `fps` arredonda para o quadro mais próximo.
    out, acc_q, acc_s = [], 0, 0.0
    for a, b, d in juntos:
        if d is None:
            out.append([a, b, acc_q])
            acc_q += b - a
        else:
            out.append([a, b, round(acc_s * fps)])
            acc_s += max((b - a) / fps, d if com_audio else 0.0)
    return out


def _mapear(m, f):
    """Quadro da entrada de uma etapa -> quadro na saída dela (dentro de trecho cortado, o começo do próximo mantido)."""
    for a, b, o in m:
        if f < b:
            return o + max(0, f - a)
    return m[-1][2] + (m[-1][1] - m[-1][0])


def cortes_em_quadros(mapas, total):
    """Quadro, no vídeo final, em que começa cada trecho depois de um corte (qualquer etapa)."""
    cortes = set()
    for i, m in enumerate(mapas):
        cs = [o for _, _, o in m[1:]]
        for depois in mapas[i + 1:]:
            cs = [_mapear(depois, c) for c in cs]
        cortes |= set(cs)
    return sorted(c for c in cortes if 0 < c < total)


# ---------------------------------------------------------------- rosto
def _maior(rostos):
    return max(rostos, key=lambda r: r["w"] * r["h"])


def focos(doc_rostos):
    """[(t, x do centro do rosto, y dos olhos)] por amostra com rosto. Os olhos ficam a ~40% da caixa do detector."""
    out = []
    for q in (doc_rostos or {}).get("quadros", []):
        if q["rostos"]:
            r = _maior(q["rostos"])
            out.append((q["t"], r["x"] + r["w"] / 2, r["y"] + 0.4 * r["h"]))
    return out


def foco_do_plano(fs, ini, fim, padrao):
    dentro = [f for f in fs if ini <= f[0] < fim]
    if not dentro:
        return padrao, []
    return [round(statistics.median(f[1] for f in dentro), 4), round(statistics.median(f[2] for f in dentro), 4)], dentro


def _suaviza(pontos, janela=3):
    out = []
    for i, p in enumerate(pontos):
        viz = pontos[max(0, i - janela // 2): i + janela // 2 + 1]
        out.append([round(p[0], 3), round(sum(v[1] for v in viz) / len(viz), 4), round(sum(v[2] for v in viz) / len(viz), 4)])
    return out


# ---------------------------------------------------------------- plano
def planejar(a):
    W, H = probe_dimensoes(a.video)
    taxa, fps, total = sonda(a.video)
    avisos = []
    if a.cortes_em:
        cortes = sorted({round(float(x) * fps) for x in a.cortes_em.split(",") if x.strip()})
        cortes = [c for c in cortes if 0 < c < total]
    else:
        mapas = [mapa(c, fps, tem_audio(a.video)) for c in a.cortes]
        esperado = mapas[-1][-1][2] + mapas[-1][-1][1] - mapas[-1][-1][0]
        if abs(esperado - total) > 2:
            avisos.append(f"o último arquivo de cortes soma {esperado} quadros e o vídeo tem {total}: confira se VIDEO é a "
                          "saída da última etapa de --cortes (se não for, a troca de plano cai fora do corte)")
        cortes = cortes_em_quadros(mapas, total)
    if not cortes:
        avisos.append("nenhum corte: o vídeo inteiro fica em um plano só (aproximação lenta e punches continuam valendo)")

    # trecho curto demais não troca de plano: duas trocas em menos de --min-plano piscam
    minimo, bordas = round(a.min_plano * fps), [0]
    for c in cortes:
        if c - bordas[-1] < minimo:
            avisos.append(f"corte em {c / fps:.2f}s ignorado: o trecho antes dele tem menos de {a.min_plano:g}s")
        else:
            bordas.append(c)
    if total - bordas[-1] < minimo and len(bordas) > 1:
        avisos.append(f"corte em {bordas[-1] / fps:.2f}s ignorado: o trecho final tem menos de {a.min_plano:g}s")
        bordas.pop()
    bordas.append(total)

    doc_r = json.loads(pathlib.Path(a.rostos).read_text(encoding="utf-8")) if a.rostos else None
    fs = focos(doc_r)
    geral = [round(statistics.median(f[1] for f in fs), 4), round(statistics.median(f[2] for f in fs), 4)] if fs else [0.5, 0.4]
    if a.rostos and not fs:
        avisos.append("o .rostos.json não tem rosto: os planos fechados usam o centro do quadro")
    elif fs and (abs(geral[0] - 0.5) > 0.25 or geral[1] > 0.6):
        avisos.append(f"o rosto fica no canto do quadro (x {geral[0]:.2f}, olhos em y {geral[1]:.2f}): parece gravação de tela "
                      "com webcam, e o plano fechado vai cortar o conteúdo. A câmera é para pessoa em quadro cheio; aqui use "
                      "--fechado 1 (só aproximação lenta e punch) ou não aplique")

    planos, eventos = [], []
    for i in range(len(bordas) - 1):
        q0, q1 = bordas[i], bordas[i + 1]
        fechado = (i % 2 == 1) != (a.comeca == "fechado")
        foco, dentro = foco_do_plano(fs, q0 / fps, q1 / fps, geral)
        p = {"id": f"cam{i + 1:02d}", "inicio": round(q0 / fps, 4), "fim": round(q1 / fps, 4),
             "plano": "fechado" if fechado else "aberto", "escala": a.fechado if fechado else 1.0,
             "deriva": a.deriva, "foco": foco}
        if a.seguir and fechado and len(dentro) >= 3:
            p["trilha"] = _suaviza(dentro)
        planos.append(p)
        if i:
            eventos.append({"t": p["inicio"], "tipo": "corte", "forca": "leve", "de": p["id"]})

    punches = []
    if a.punches:
        bruto = json.loads(pathlib.Path(a.punches).read_text(encoding="utf-8"))
        for j, x in enumerate(sorted(bruto, key=lambda x: x["t"])):
            t, forca = float(x["t"]), float(x.get("forca", 0.06))
            pid = f"p{j + 1:02d}"
            if not 0 <= t < total / fps:
                avisos.append(f"{pid} em {t:.2f}s está fora do vídeo: ignorado")
                continue
            perto = [c / fps for c in bordas[1:-1] if abs(c / fps - t) < 0.3]
            if perto:
                avisos.append(f"{pid} em {t:.2f}s cai a menos de 0,3 s do corte de {perto[0]:.2f}s: o corte já muda o plano")
            punches.append({"id": pid, "t": round(t, 3), "forca": forca, "dur": float(x.get("dur", 0.3)),
                            **({"texto": x["texto"]} if x.get("texto") else {})})
            eventos.append({"t": round(t, 3), "tipo": "punch", "forca": "forte" if forca >= 0.08 else "media", "de": pid})

    pior = max([p["escala"] * (1 + p["deriva"]) for p in planos] or [1.0]) * (1 + max([x["forca"] for x in punches] or [0]))
    if pior > AMPLIA_MAX:
        avisos.append(f"a câmera chega a {pior:.0%} do quadro original: acima de {AMPLIA_MAX:.0%} a imagem amolece "
                      "(grave em resolução maior que a de entrega, ou baixe --fechado)")

    doc = {"source": str(a.video), "largura": W, "altura": H, "taxa": taxa, "quadros": total, "olhos": a.olhos,
           "planos": planos, "punches": punches, "eventos": sorted(eventos, key=lambda e: e["t"]), "avisos": avisos}
    src = pathlib.Path(a.video)
    out = pathlib.Path(a.out) if a.out else src.with_name(src.stem + ".camera.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    fech = sum(1 for p in planos if p["plano"] == "fechado")
    print(f"{len(planos)} planos ({len(planos) - fech} abertos, {fech} fechados a {a.fechado:.0%}), "
          f"{len(punches)} punch(es), {len(avisos)} aviso(s) -> {out}")
    for p in planos:
        z1 = p["escala"] * (1 + p["deriva"] * min(1.0, (p["fim"] - p["inicio"]) / DERIVA_MIN_S))
        print(f"  {p['id']}  {p['inicio']:7.2f}–{p['fim']:7.2f}  {p['plano']:7s} {p['escala']:.0%} → {z1:.0%}"
              + ("  segue o rosto" if "trilha" in p else ""))
    for x in punches:
        print(f"  {x['id']}    {x['t']:7.2f}  punch +{x['forca']:.0%}" + (f"  “{x['texto']}”" if x.get("texto") else ""))
    for av in avisos:
        print(f"  AVISO: {av}")
    return doc


# ---------------------------------------------------------------- câmera em cada instante
def _interp(trilha, t):
    if t <= trilha[0][0]:
        return trilha[0][1], trilha[0][2]
    for (t0, x0, y0), (t1, x1, y1) in zip(trilha, trilha[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    return trilha[-1][1], trilha[-1][2]


def camera_em(doc, t):
    """(escala, x0, y0): a janela do quadro original que aparece em t, com x0 e y0 em fração do quadro."""
    p = next((p for p in doc["planos"] if p["inicio"] - 1e-6 <= t < p["fim"] - 1e-6), doc["planos"][-1])
    dur = max(p["fim"] - p["inicio"], DERIVA_MIN_S)
    z = p["escala"] * (1 + p.get("deriva", 0.0) * min(1.0, max(0.0, t - p["inicio"]) / dur))
    for x in doc.get("punches", []):
        u = t - x["t"]
        if 0 <= u < ATAQUE_PUNCH:
            z *= 1 + x["forca"] * u / ATAQUE_PUNCH
        elif ATAQUE_PUNCH <= u < ATAQUE_PUNCH + x["dur"]:
            z *= 1 + x["forca"] * (1 - (u - ATAQUE_PUNCH) / x["dur"]) ** 2     # power2.out: assenta freando
    fx, fy = _interp(p["trilha"], t) if p.get("trilha") else p["foco"]
    lado = 1.0 / z
    x0 = min(max(fx - lado / 2, 0.0), 1.0 - lado)
    y0 = min(max(fy - doc.get("olhos", 0.38) * lado, 0.0), 1.0 - lado)       # olhos a ~38% da altura do plano
    return z, x0, y0


def aplicar(a):
    import cv2
    import numpy as np

    from video_editores.nucleo import quadros
    doc = json.loads(pathlib.Path(a.aplicar).read_text(encoding="utf-8"))
    if not doc.get("planos"):
        sys.exit(f"{a.aplicar}: sem planos")
    W, H = probe_dimensoes(a.video)
    taxa, fps, _ = sonda(a.video)
    if pathlib.Path(a.saida).resolve() == pathlib.Path(a.video).resolve():
        sys.exit("a saída não pode ser o próprio vídeo de entrada")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", taxa,
                            "-i", "-", "-i", str(a.video), "-map", "0:v:0", "-map", "1:a?", *codec_video(), "-c:a", "copy",
                            "-movflags", "+faststart", str(a.saida)], stdin=subprocess.PIPE)
    n = 0
    try:
        for i, _, q in quadros.ler(a.video):
            z, x0, y0 = camera_em(doc, i / fps)
            if z > 1.0005:
                m = np.float32([[z, 0, -x0 * W * z], [0, z, -y0 * H * z]])
                q = cv2.warpAffine(q, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            enc.stdin.write(q.tobytes())
            n += 1
    except BrokenPipeError:
        pass
    finally:
        enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg falhou ao codificar a saída (confira VE_ENCODER e o caminho de saída)")
    print(f"ok: {n} quadros, {len(doc['planos'])} planos, {len(doc.get('punches', []))} punch(es) -> {a.saida}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("saida", nargs="?", help="vídeo de saída (só com --aplicar)")
    ap.add_argument("--cortes", action="append", default=[], metavar="ARQ",
                    help=".takes.json ou JSON v1 do auto-editor; repita na ordem das etapas")
    ap.add_argument("--cortes-em", default=None, metavar="T,T,...", help="instantes dos cortes já no tempo de VIDEO")
    ap.add_argument("--rostos", default=None, help=".rostos.json de VIDEO (rostos.py): centra o plano fechado no rosto")
    ap.add_argument("--punches", default=None, help='JSON [{"t": 12.3, "forca": 0.06, "dur": 0.3, "texto": "…"}], t no tempo de VIDEO')
    ap.add_argument("--fechado", type=float, default=1.18, help="escala do plano fechado (1.18 = 118%%)")
    ap.add_argument("--deriva", type=float, default=0.03, help="aproximação lenta por plano (0 desliga)")
    ap.add_argument("--olhos", type=float, default=0.38, help="altura dos olhos no plano, em fração (0 = topo)")
    ap.add_argument("--min-plano", type=float, default=0.8, help="trecho mais curto que isto não troca de plano")
    ap.add_argument("--comeca", choices=["aberto", "fechado"], default="aberto")
    ap.add_argument("--seguir", action="store_true", help="nos planos fechados, a câmera acompanha o rosto (pede --rostos)")
    ap.add_argument("--out", default=None, help="caminho do .camera.json")
    ap.add_argument("--aplicar", default=None, metavar="ARQ.camera.json")
    a = ap.parse_args()
    for arq in [a.video, a.rostos, a.punches, a.aplicar, *a.cortes]:
        if arq and not pathlib.Path(arq).is_file():
            sys.exit(f"arquivo não encontrado: {arq}")
    if a.aplicar:
        if not a.saida:
            sys.exit("--aplicar pede o vídeo de saída: camera.py VIDEO --aplicar ARQ.camera.json SAIDA.mp4")
        return aplicar(a)
    if a.saida:
        sys.exit("vídeo de saída só com --aplicar (planeje, revise o .camera.json e então aplique)")
    if not a.cortes and a.cortes_em is None:
        sys.exit("diga de onde vêm os cortes: --cortes ARQ (.takes.json, v1 do auto-editor) ou --cortes-em T,T,...")
    if a.fechado < 1 or a.deriva < 0:
        sys.exit("--fechado precisa ser >= 1 e --deriva >= 0")
    if a.seguir and not a.rostos:
        sys.exit("--seguir pede --rostos")
    planejar(a)


if __name__ == "__main__":
    main()
