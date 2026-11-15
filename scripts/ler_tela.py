#!/usr/bin/env python3
"""Lê o texto de um print ou de um quadro do vídeo (OCR) e diz onde cada palavra está; com isso o destaque
cai em cima do texto certo, e a tarja cobre o dado sensível sem ninguém medir coordenada no olho.

Sempre grava <nome>.ocr.json: linhas e palavras com a caixa em fração da imagem (0–1) e a confiança.
Com --achar/--regex, localiza o texto; com --estilo, gera um .ass com a forma no lugar; --burn queima.

Uso: ler_tela.py IMAGEM|VIDEO [--t 12.4] [--out ARQ.ocr.json] [--backend rapidocr]
       [--achar "Salvar alterações"]... [--regex "[\\w.+-]+@[\\w-]+\\.[\\w.]+"]... [--todos]
       [--estilo caixa|marca|sublinhado|tarja] [--inicio T] [--fim T] [--cor "#FFD54F"] [--folga 0.25]
       [--marca marca.json] [--burn SAIDA.mp4|SAIDA.png]

  --achar   texto a localizar, sem diferenciar maiúscula nem acento; pode repetir. Vale a 1ª ocorrência de
            cada um (--todos pega todas).
  --regex   expressão regular sobre o texto de cada linha (todas as ocorrências). Ex.: e-mails, CPFs.
  estilos   caixa: moldura em volta · marca: marca-texto translúcido que entra da esquerda para a direita ·
            sublinhado: traço embaixo · tarja: retângulo opaco (privacidade), sem animação.
  intervalo padrão: de --t até --t + 3 s; a tarja, sem --inicio/--fim, cobre o vídeo inteiro.

A caixa vale para o quadro lido: em gravação de tela com rolagem, use um intervalo em que a tela está parada
(ou rode de novo em outro --t). Sai com código 1 quando --achar/--regex não encontra nada, listando o que leu.

Dependências: `uv run --with rapidocr --with onnxruntime` (ou `video-editores ler-tela ...`, que resolve sozinho).
"""
import argparse
import json
import os
import pathlib
import re
import sys
import unicodedata


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # marca_cli, também sob `python -I`
from video_editores import modelos  # noqa: E402
from video_editores.nucleo import ass, quadros  # noqa: E402
from video_editores.nucleo.ffmpeg import duracao  # noqa: E402

IMAGENS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def plano(s: str) -> str:
    """Minúsculas e sem acento, com o mesmo número de caracteres (para mapear posição -> palavra)."""
    out = []
    for ch in s:
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        out.append((base or ch)[0].lower())
    return "".join(out)


def frac(c, w, h):
    return [round(c.x / w, 5), round(c.y / h, 5), round(c.w / w, 5), round(c.h / h, 5)]


def uniao(caixas):
    x0 = min(c[0] for c in caixas)
    y0 = min(c[1] for c in caixas)
    x1 = max(c[0] + c[2] for c in caixas)
    y1 = max(c[1] + c[3] for c in caixas)
    return [round(x0, 5), round(y0, 5), round(x1 - x0, 5), round(y1 - y0, 5)]


def trecho(linha, ini, fim):
    """Caixa do intervalo de caracteres [ini, fim) da linha: união das palavras tocadas; sem caixas de palavra,
    fatia proporcional da caixa da linha."""
    pals = linha["palavras"]
    if pals:
        tocadas, pos = [], 0
        for p in pals:
            a, b = pos, pos + len(p["texto"])
            if a < fim and b > ini:
                tocadas.append(p["caixa"])
            pos = b + 1
        if tocadas:
            return uniao(tocadas)
    x, y, w, h = linha["caixa"]
    n = max(1, len(linha["texto"]))
    return [round(x + w * ini / n, 5), y, round(w * (fim - ini) / n, 5), h]


def procurar(linhas, achar, regexes, todos):
    achados = []
    for consulta in achar:
        alvo = " ".join(plano(consulta).split())
        n = 0
        for i, ln in enumerate(linhas):
            base = plano(ln["busca"])
            pos = base.find(alvo)
            while pos >= 0 and alvo:
                achados.append({"consulta": consulta, "texto": ln["busca"][pos:pos + len(alvo)], "linha": i,
                                "caixa": trecho(ln, pos, pos + len(alvo))})
                n += 1
                if not todos:
                    break
                pos = base.find(alvo, pos + len(alvo))
            if n and not todos:
                break
    for padrao in regexes:
        try:
            rx = re.compile(padrao)
        except re.error as e:
            sys.exit(f"--regex inválida ({padrao}): {e}")
        for i, ln in enumerate(linhas):
            for m in rx.finditer(ln["busca"]):
                if m.end() > m.start():
                    achados.append({"consulta": padrao, "texto": m.group(0), "linha": i,
                                    "caixa": trecho(ln, m.start(), m.end())})
    return achados


def eventos(achados, W, H, estilo, ini, fim, cor_hex, folga):
    linhas = []
    for ac in achados:
        x, y, w, h = ac["caixa"]
        f = h * H * (max(folga, 0.3) if estilo == "tarja" else folga)
        x0, y0, x1, y1 = x * W - f, y * H - f, (x + w) * W + f, (y + h) * H + f
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        base = "\\an7\\pos(0,0)\\bord0\\shad0"
        varre = f"\\clip({x0:.0f},{y0:.0f},{x0:.0f},{y1:.0f})\\t(0,280,\\clip({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}))"
        if estilo == "caixa":
            tags, forma = f"{base}\\1c{ass.cor(cor_hex)}\\fad(150,150)", ass.moldura(x0, y0, x1, y1, max(3, H * 0.005))
        elif estilo == "marca":
            tags, forma = f"{base}\\1c{ass.cor(cor_hex)}\\1a&H8C&{varre}\\fad(0,150)", ass.retangulo(x0, y0, x1, y1)
        elif estilo == "sublinhado":
            e = max(3, H * 0.006)
            tags, forma = f"{base}\\1c{ass.cor(cor_hex)}{varre}\\fad(0,150)", ass.retangulo(x0, y1 - e, x1, y1)
        else:   # tarja
            tags, forma = f"{base}\\1c{ass.cor(cor_hex)}", ass.retangulo(x0, y0, x1, y1)
        linhas.append(f"Dialogue: 2,{ass.tempo(ini)},{ass.tempo(fim)},Base,,0,0,0,,{{{tags}\\p1}}{forma}{{\\p0}}")
    return linhas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonte", help="imagem (png/jpg) ou vídeo")
    ap.add_argument("--t", type=float, default=0.0, help="instante do quadro, quando a fonte é vídeo")
    ap.add_argument("--out", default=None)
    ap.add_argument("--backend", default=None, help="backend de OCR (padrão: VE_OCR ou rapidocr)")
    ap.add_argument("--achar", action="append", default=[])
    ap.add_argument("--regex", action="append", default=[])
    ap.add_argument("--todos", action="store_true", help="todas as ocorrências de cada --achar")
    ap.add_argument("--estilo", default=None, choices=["caixa", "marca", "sublinhado", "tarja"])
    ap.add_argument("--inicio", type=float, default=None)
    ap.add_argument("--fim", type=float, default=None)
    ap.add_argument("--cor", default=None, help="padrão: acento da marca, senão #FFD54F; tarja: #000000")
    ap.add_argument("--folga", type=float, default=0.25, help="margem em volta do texto, em fração da altura dele")
    ap.add_argument("--burn", default=None)
    import marca_cli
    marca_cli.add_arg(ap)
    a = ap.parse_args()
    src = pathlib.Path(a.fonte)
    if not src.is_file():
        sys.exit(f"não achei {src}")
    eh_imagem = src.suffix.lower() in IMAGENS
    if a.burn and not a.estilo:
        sys.exit("--burn precisa de --estilo")
    if a.estilo and not (a.achar or a.regex):
        sys.exit("--estilo precisa de --achar ou --regex (o que destacar)")

    if eh_imagem:
        try:
            import cv2
        except ImportError:
            sys.exit("faltam dependências: uv run --with rapidocr --with onnxruntime ...")
        img = cv2.imread(str(src))
        if img is None:
            sys.exit(f"não consegui abrir a imagem {src}")
    else:
        img = quadros.em(src, a.t)
        if img is None:
            sys.exit(f"--t {a.t:g} passa do fim do vídeo")
    H, W = img.shape[:2]

    ocr = modelos.get_ocr(a.backend, device=modelos.device())
    linhas = []
    for ln in ocr.ler(img):
        pals = [{"texto": p.texto, "conf": p.conf, "caixa": frac(p, W, H)} for p in ln.palavras]
        linhas.append({"texto": ln.texto, "conf": ln.caixa.conf, "caixa": frac(ln.caixa, W, H), "palavras": pals,
                       "busca": " ".join(p["texto"] for p in pals) if pals else ln.texto})
    achados = procurar(linhas, a.achar, a.regex, a.todos)
    for ln in linhas:
        del ln["busca"]

    sufixo = ".ocr.json" if eh_imagem or not a.t else f"_{a.t:g}s.ocr.json"
    if a.out:
        out = pathlib.Path(a.out)
    else:
        base = pathlib.Path("trabalho") / src.stem if pathlib.Path("trabalho").is_dir() else src.parent
        base.mkdir(parents=True, exist_ok=True)
        out = base / (src.stem + sufixo)
    out.write_text(json.dumps({"source": str(src), "t": None if eh_imagem else a.t, "largura": W, "altura": H,
                               "backend": ocr.nome, "linhas": linhas, "achados": achados},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok: {len(linhas)} linhas, {sum(len(x['palavras']) for x in linhas)} palavras -> {out}")
    for ac in achados:
        x, y, w, h = ac["caixa"]
        print(f"  achei \"{ac['texto']}\" em x {x:.3f} y {y:.3f} (largura {w:.3f}, altura {h:.3f})")

    if (a.achar or a.regex) and not achados:
        print("NÃO ENCONTRADO. Texto lido:", file=sys.stderr)
        for ln in linhas[:40]:
            print(f"  {ln['texto']}", file=sys.stderr)
        sys.exit(1)

    if a.estilo:
        m = marca_cli.carregar(a.marca)
        cor_hex = a.cor or ("#000000" if a.estilo == "tarja" else marca_cli.escolhe(None, m.cores["acento"], "#FFD54F", m))
        if eh_imagem:
            ini, fim = 0.0, 10.0
        elif a.estilo == "tarja" and a.inicio is None and a.fim is None:
            ini, fim = 0.0, duracao(src) + 1
        else:
            ini = a.t if a.inicio is None else a.inicio
            fim = ini + 3.0 if a.fim is None else a.fim
        base_ass = out.name[:-len(".ocr.json")] if out.name.endswith(".ocr.json") else out.stem
        arq_ass = out.with_name(base_ass + ".destaque.ass")
        arq_ass.write_text(ass.documento(W, H, "DejaVu Sans", eventos(achados, W, H, a.estilo, ini, fim, cor_hex, a.folga)),
                           encoding="utf-8")
        print(f"ass -> {arq_ass}")
        if a.burn:
            if eh_imagem:   # imagem parada: queima o estado final da forma (1 s depois do início)
                import subprocess
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(src),
                                "-vf", f"ass=filename={ass.ffesc(arq_ass)},trim=start=1,setpts=PTS-STARTPTS",
                                "-frames:v", "1", a.burn], check=True)
            else:
                ass.queimar(src, arq_ass, a.burn)
            print(f"ok -> {a.burn}")


if __name__ == "__main__":
    main()
