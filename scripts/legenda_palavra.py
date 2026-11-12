#!/usr/bin/env python3
"""Legenda por página com a palavra falada em destaque (estilo reels), em ASS, a partir da transcrição por palavra.

Agrupa as palavras em páginas curtas (janela de tempo, máximo de palavras e de caracteres, pausas e fim de frase)
e escreve um .ass em que a palavra atual muda de cor no instante em que é dita. A queima é pelo ffmpeg (libass):
mesma velocidade e o mesmo determinismo do `subtitles=`; nada é renderizado quadro a quadro fora do ffmpeg.

Uso: legenda_palavra.py VIDEO IN.transcript.json [--ass SAIDA.ass] [--burn SAIDA.mp4]
       [--janela 1.5] [--max-palavras 5] [--max-chars AUTO] [--pausa 0.6]
       [--modo atual|preenche] [--pos 0.68|0.86] [--tamanho 0.05] [--font "Montserrat"]
       [--cor #FFFFFF] [--destaque #FACC15] [--caixa] [--maiusculas] [--espaco-largo] [--correcoes correcoes.json]

Entrada: `<nome>.transcript.json` do transcribe.py (segments[].words[] com start/end) ou um .srt com um cue por palavra.
Saídas: o .ass e um `.paginas.txt` com cada página e seus tempos, para revisar o texto antes de queimar.
  modo atual     só a palavra falada fica na cor de destaque (as anteriores voltam à cor base)
  modo preenche  karaokê: as palavras já ditas ficam na cor de destaque até a página acabar
  --correcoes    JSON {"Paiton": "Python"}: troca a palavra (ignorando pontuação em volta) antes de paginar
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lettering_ass import color, ffesc, probe, t  # noqa: E402

PONTUACAO_FIM = re.compile(r"[.!?…]$")


def srt_t(s):
    h, m, r = s.strip().split(":")
    sec, ms = r.replace(".", ",").split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def carrega_palavras(caminho):
    """Lista de {start, end, word} a partir do transcript.json ou de um SRT com um cue por palavra."""
    if caminho.endswith(".json"):
        d = json.load(open(caminho, encoding="utf-8"))
        segs = d["segments"] if isinstance(d, dict) else d
        ws = [{"start": float(w["start"]), "end": float(w["end"]), "word": (w.get("word") or w.get("text") or "").strip()}
              for s in segs for w in s.get("words", [])]
        ws = [w for w in ws if w["word"]]
        if not ws:
            sys.exit("transcrição sem palavras: use o <nome>.transcript.json do transcribe.py ou um .srt com um cue por palavra")
        return ws
    ws = []
    for bloco in re.split(r"\n\s*\n", open(caminho, encoding="utf-8").read().strip()):
        linhas = bloco.strip().split("\n")
        if len(linhas) < 3 or "-->" not in linhas[1]:
            continue
        a, z = linhas[1].split("-->")
        ws.append({"start": srt_t(a), "end": srt_t(z), "word": " ".join(x.strip() for x in linhas[2:])})
    return ws


def corrige(ws, correcoes):
    for w in ws:
        m = re.match(r"^(\W*)(.*?)(\W*)$", w["word"], re.S)
        if m and m.group(2) in correcoes:
            w["word"] = m.group(1) + correcoes[m.group(2)] + m.group(3)
    return ws


def pagina(ws, janela, max_pal, max_chars, pausa):
    """Fecha a página por pausa, janela de tempo, nº de palavras, nº de caracteres ou fim de frase."""
    pags, atual = [], []
    for w in ws:
        if atual:
            gap = w["start"] - atual[-1]["end"]
            chars = sum(len(x["word"]) for x in atual) + len(atual) + len(w["word"])
            if (gap > pausa or w["end"] - atual[0]["start"] > janela or len(atual) >= max_pal
                    or chars > max_chars or PONTUACAO_FIM.search(atual[-1]["word"])):
                pags.append(atual)
                atual = []
        atual.append(w)
    if atual:
        pags.append(atual)
    equilibra(pags, janela, max_chars, pausa)
    out = []
    for i, p in enumerate(pags):
        ini, fim = p[0]["start"], p[-1]["end"]
        if i + 1 < len(pags) and pags[i + 1][0]["start"] - fim < pausa:
            fim = pags[i + 1][0]["start"]          # sem buraco entre páginas quando a fala continua
        else:
            fim += 0.25
        out.append({"start": round(ini, 3), "end": round(fim, 3), "palavras": p})
    return out


def equilibra(pags, janela, max_chars, pausa):
    """Página de uma palavra só recebe a última palavra da anterior, se a fala for contínua e couber.

    Evita "ele basicamente faz uma | matemática | básica": vira "ele basicamente faz | uma matemática | básica".
    Não move palavra que fecha frase (a quebra ali é natural) nem quando há pausa entre as duas.
    """
    for i in range(1, len(pags)):
        a, b = pags[i - 1], pags[i]
        if len(b) != 1 or len(a) < 3:
            continue
        w = a[-1]
        chars = sum(len(x["word"]) for x in b) + len(b) + len(w["word"])
        if (PONTUACAO_FIM.search(w["word"]) or b[0]["start"] - w["end"] > pausa
                or b[-1]["end"] - w["start"] > janela or chars > max_chars):
            continue
        b.insert(0, a.pop())


def texto_pagina(p, modo, cor, dest, maiusculas, sep=" "):
    t0 = p["start"]
    partes = []
    for i, w in enumerate(p["palavras"]):
        txt = w["word"].upper() if maiusculas else w["word"]
        a = int(round((w["start"] - t0) * 1000))
        prox = p["palavras"][i + 1]["start"] if i + 1 < len(p["palavras"]) else p["end"]
        b = int(round((prox - t0) * 1000))       # o destaque dura até a próxima palavra começar
        if modo == "preenche":
            partes.append(f"{{\\k{max(1, (b - a) // 10)}}}{txt}")
        elif a == 0:
            partes.append(f"{{\\1c{dest}\\t({b},{b},\\1c{cor})}}{txt}")
        else:
            partes.append(f"{{\\1c{cor}\\t({a},{a},\\1c{dest})\\t({b},{b},\\1c{cor})}}{txt}")
    return sep.join(partes)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("transcricao", help="<nome>.transcript.json ou .srt com um cue por palavra")
    ap.add_argument("--ass", help="padrão: <transcrição>.palavra.ass")
    ap.add_argument("--burn", help="queima e grava este mp4")
    ap.add_argument("--janela", type=float, default=1.5, help="duração máxima de uma página, em s")
    ap.add_argument("--max-palavras", type=int, default=5)
    ap.add_argument("--max-chars", type=int, default=0, help="padrão: duas linhas na largura do vídeo")
    ap.add_argument("--pausa", type=float, default=0.6, help="silêncio que fecha a página, em s")
    ap.add_argument("--modo", choices=["atual", "preenche"], default="atual")
    ap.add_argument("--pos", type=float, default=None, help="centro vertical em fração da altura (padrão 0,68 em vertical, 0,86 em horizontal)")
    ap.add_argument("--tamanho", type=float, default=0.05, help="altura da fonte em fração da altura")
    ap.add_argument("--font", default="Montserrat")
    ap.add_argument("--cor", default="#FFFFFF")
    ap.add_argument("--destaque", default="#FACC15")
    ap.add_argument("--caixa", action="store_true", help="caixa translúcida atrás do texto em vez de contorno")
    ap.add_argument("--maiusculas", action="store_true")
    ap.add_argument("--espaco-largo", action="store_true",
                    help="espaço duplo entre palavras, para fonte de espaço estreito em que elas grudam")
    ap.add_argument("--correcoes", help="JSON {errado: certo}")
    a = ap.parse_args()

    W, H = probe(a.video)
    ws = carrega_palavras(a.transcricao)
    if a.correcoes:
        ws = corrige(ws, json.load(open(a.correcoes, encoding="utf-8")))
    px = int(H * a.tamanho)
    margem = int(W * 0.08)
    chars_linha = max(8, int((W - 2 * margem) / (px * 0.55)))
    max_chars = a.max_chars or 2 * chars_linha
    pags = pagina(ws, a.janela, a.max_palavras, max_chars, a.pausa)

    cor, dest = color(a.cor), color(a.destaque)
    primaria = dest if a.modo == "preenche" else cor
    if a.caixa:
        estilo = f"Style: Palavra,{a.font},{px},{primaria},{cor},&H90000000,&H90000000,1,0,0,0,100,100,0,0,3,{max(6, px // 6)},0,5,{margem},{margem},10,1"
    else:
        estilo = f"Style: Palavra,{a.font},{px},{primaria},{cor},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,{max(2, px // 12)},0,5,{margem},{margem},10,1"
    pos = a.pos if a.pos is not None else (0.68 if H > W else 0.86)
    X, Y = W // 2, int(H * pos)
    sep = "\\h " if a.espaco_largo else " "   # \h = espaço rígido do ASS, somado ao espaço comum
    linhas = [f"Dialogue: 0,{t(p['start'])},{t(p['end'])},Palavra,,0,0,0,,{{\\an5\\pos({X},{Y})}}"
              f"{texto_pagina(p, a.modo, cor, dest, a.maiusculas, sep)}" for p in pags]
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{estilo}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(linhas) + "\n"
    out_ass = a.ass or re.sub(r"\.(transcript\.json|json|srt)$", "", a.transcricao) + ".palavra.ass"
    open(out_ass, "w", encoding="utf-8").write(ass)
    rev = out_ass.rsplit(".", 1)[0] + ".paginas.txt"
    open(rev, "w", encoding="utf-8").write("".join(
        f"[{p['start']:7.2f} – {p['end']:7.2f}] {' '.join(w['word'] for w in p['palavras'])}\n" for p in pags))
    media = sum(p["end"] - p["start"] for p in pags) / max(1, len(pags))
    maior = max((len(" ".join(w["word"] for w in p["palavras"])) for p in pags), default=0)
    print(f"ass -> {out_ass} ({len(pags)} páginas, {media:.2f} s em média, maior com {maior} caracteres; revisão em {rev})")

    if a.burn:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.video,
                        "-vf", f"ass=filename='{ffesc(out_ass)}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", a.burn], check=True)
        print(f"ok -> {a.burn}")


if __name__ == "__main__":
    sys.exit(main())
