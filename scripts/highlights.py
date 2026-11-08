#!/usr/bin/env python3
"""Seleciona os melhores momentos de uma transcrição para um alvo de duração.

Primeira seleção determinística, para o Claude refinar com o usuário:
  - divide a fala em "blocos" (segmentos agrupados por pausas >= --gap);
  - pontua cada bloco: densidade de palavras-chave (--keywords), números, perguntas,
    marcadores de ênfase ("importante", "dica", "resumo", "cuidado"), tamanho útil,
    penaliza muletas ("né", "tipo", "então", "hum") e blocos muito curtos;
  - escolhe por pontuação por segundo até bater --target (segundos), mantendo a
    ordem cronológica; sempre inclui o 1º bloco quando --keep-intro.
  - --reels N: em vez de um corte único, devolve N janelas de --reel-len segundos
    centradas nos blocos mais fortes (sem sobreposição).

Saídas:
  <nome>.highlights.json  -> {"keep": [[s,e],...], "blocks": [...]}  (compatível com render_spans.sh)
  <nome>.highlights.md    -> tabela legível com tempo, pontuação e começo do texto

Uso: highlights.py VIDEO.transcript.json --target 600 [--keywords "k8s,container,custo"]
     highlights.py VIDEO.transcript.json --reels 3 --reel-len 45
"""
import argparse
import json
import pathlib
import re
import sys

EMPH = ["importante", "dica", "resumo", "resumindo", "cuidado", "atenção", "segredo", "erro",
        "nunca", "sempre", "melhor", "pior", "resultado", "exemplo", "na prática", "por quê", "porque",
        "primeiro", "segundo", "terceiro", "passo", "conclusão"]
FILLERS = ["né", "tipo", "então", "hum", "éé", "ééé", "aí", "tá", "ok", "enfim", "assim"]


def norm(t):
    return re.sub(r"[^\w\s?%]", " ", t.lower())


def score_block(text, keywords):
    t = norm(text)
    words = t.split()
    n = max(1, len(words))
    s = 0.0
    s += 3.0 * sum(t.count(k) for k in keywords)
    s += 1.5 * sum(t.count(e) for e in EMPH)
    s += 1.0 * len(re.findall(r"\b\d+[%]?\b", t))
    s += 1.0 * text.count("?")
    s -= 0.8 * sum(words.count(f) for f in FILLERS)
    s += min(n, 40) / 40.0  # blocos com conteúdo valem mais que fragmentos
    return s / n * 10.0  # por palavra, escala legível


def build_blocks(segs, gap, max_block):
    """Agrupa segmentos separados por pausas < gap; blocos maiores que max_block são
    divididos em fronteiras de segmento, para que sempre exista algo que caiba no alvo."""
    blocks, cur = [], None
    for sg in segs:
        if cur and sg["start"] - cur["end"] < gap and sg["end"] - cur["start"] <= max_block:
            cur["end"] = sg["end"]
            cur["text"] += " " + sg["text"]
        else:
            if cur:
                blocks.append(cur)
            cur = {"start": sg["start"], "end": sg["end"], "text": sg["text"]}
    if cur:
        blocks.append(cur)
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--target", type=float, default=None, help="duração alvo em segundos (corte único)")
    ap.add_argument("--reels", type=int, default=0, help="quantidade de reels a extrair")
    ap.add_argument("--reel-len", type=float, default=45.0)
    ap.add_argument("--gap", type=float, default=1.2, help="pausa (s) que separa blocos")
    ap.add_argument("--min-block", type=float, default=4.0, help="descarta blocos mais curtos (s)")
    ap.add_argument("--keywords", default="", help="palavras-chave separadas por vírgula")
    ap.add_argument("--keep-intro", action="store_true", help="sempre manter o primeiro bloco")
    ap.add_argument("--pad", type=float, default=0.15)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if not a.target and not a.reels:
        sys.exit("informe --target SEGUNDOS ou --reels N")

    data = json.loads(pathlib.Path(a.transcript).read_text(encoding="utf-8"))
    segs = [s for s in data.get("segments", []) if s.get("text", "").strip()]
    if not segs:
        sys.exit("transcrição sem fala")
    dur_total = data.get("duration") or segs[-1]["end"]
    keywords = [k.strip().lower() for k in a.keywords.split(",") if k.strip()]

    max_block = a.reel_len if a.reels else max(a.min_block * 2, min(60.0, a.target * 0.4))
    blocks = [b for b in build_blocks(segs, a.gap, max_block) if b["end"] - b["start"] >= a.min_block]
    if not blocks:
        sys.exit(f"nenhum bloco com pelo menos {a.min_block}s; reduza --min-block")
    for b in blocks:
        b["dur"] = b["end"] - b["start"]
        b["score"] = round(score_block(b["text"], keywords), 2)
    ranked = sorted(blocks, key=lambda b: b["score"], reverse=True)

    keep = []
    if a.reels:
        used = []
        for b in ranked:
            if len(keep) >= a.reels:
                break
            mid = (b["start"] + b["end"]) / 2
            cands = [mid - a.reel_len / 2, b["start"] - 0.3, b["end"] + 0.3 - a.reel_len]
            cands += [u[1] for u in used] + [u[0] - a.reel_len for u in used]
            placed = None
            for st in cands:
                st = max(0.0, min(st, dur_total - a.reel_len))
                en = min(dur_total, st + a.reel_len)
                if en - st < a.reel_len * 0.8:
                    continue
                if any(not (en <= u[0] or st >= u[1]) for u in used):
                    continue
                if not (st <= b["end"] and en >= b["start"]):  # precisa conter parte do bloco
                    continue
                placed = [st, en]
                break
            if not placed:
                continue
            used.append(placed)
            keep.append([round(placed[0], 2), round(placed[1], 2)])
        keep.sort()
    else:
        chosen, total = [], 0.0
        if a.keep_intro and blocks:
            chosen.append(blocks[0])
            total += blocks[0]["dur"]
        for b in ranked:
            if b in chosen:
                continue
            if total + b["dur"] > a.target:
                continue
            chosen.append(b)
            total += b["dur"]
        chosen.sort(key=lambda b: b["start"])
        for b in chosen:
            st, en = max(0.0, b["start"] - a.pad), min(dur_total, b["end"] + a.pad)
            if keep and st <= keep[-1][1]:
                keep[-1][1] = max(keep[-1][1], en)
            else:
                keep.append([round(st, 2), round(en, 2)])

    src = pathlib.Path(a.transcript)
    stem = src.name[:-len(".transcript.json")] if src.name.endswith(".transcript.json") else src.stem
    out = pathlib.Path(a.out) if a.out else src.with_name(stem + ".highlights.json")
    out.write_text(json.dumps({"keep": keep, "blocks": blocks}, ensure_ascii=False, indent=1), encoding="utf-8")

    sel = sum(e - s for s, e in keep)
    md = [f"# Melhores momentos — {stem}", "",
          f"Original: {dur_total/60:.1f} min · selecionado: {sel/60:.1f} min · {len(keep)} trechos · {len(blocks)} blocos analisados", "",
          "| # | início | fim | pontuação | começo do texto |", "|---|---|---|---|---|"]
    for i, b in enumerate(sorted(blocks, key=lambda b: b["start"]), 1):
        mark = "**" if any(b["start"] >= s - 0.5 and b["end"] <= e + 0.5 for s, e in keep) else ""
        md.append(f"| {i} | {b['start']:.1f} | {b['end']:.1f} | {mark}{b['score']}{mark} | {b['text'][:80]} |")
    out.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{len(keep)} trechos, {sel:.0f}s de {dur_total:.0f}s -> {out} e {out.with_suffix('.md')}")
    if not keep:
        sys.exit("nada selecionado: aumente --target ou reduza --min-block")


if __name__ == "__main__":
    main()
