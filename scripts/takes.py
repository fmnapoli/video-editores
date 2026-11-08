#!/usr/bin/env python3
"""Detecta tomadas repetidas na transcrição e escolhe a melhor de cada grupo.

Lógica: segmentos com texto parecido (similaridade >= --threshold) em sequência
são tratados como tentativas da mesma fala. Fica a ÚLTIMA tentativa completa
(convenção de gravação: você repete até acertar), a menos que ela seja muito
mais curta que as outras (fala cortada) ou tenha confiança muito baixa.

Saída: <nome>.takes.json com {keep: [[start,end],...], dropped: [...]} e um
resumo legível no stdout para o Claude mostrar ao usuário antes de cortar.

Uso: takes.py VIDEO.transcript.json [--threshold 0.6] [--pad 0.08]
"""
import argparse, json, pathlib, re, sys
from difflib import SequenceMatcher


def norm(t):
    return re.sub(r"[^\w\s]", "", t.lower()).strip()


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    # compara pelo prefixo comum: retomadas costumam começar igual
    n = min(len(a), len(b))
    full = SequenceMatcher(None, a, b).ratio()
    if n < 12:  # prefixo curto demais para ser evidência ("Ok." vs "Ok, então...")
        return full
    return max(SequenceMatcher(None, a[:n], b[:n]).ratio(), full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--pad", type=float, default=0.08, help="folga em segundos em volta de cada trecho")
    ap.add_argument("--out", default=None, help="caminho do .takes.json (padrão: ao lado do transcript)")
    a = ap.parse_args()

    data = json.loads(pathlib.Path(a.transcript).read_text(encoding="utf-8"))
    segs = [s for s in data["segments"] if s["text"].strip()]
    if not segs:
        sys.exit("transcrição sem fala: nada a selecionar")

    groups, cur = [], []
    for s in segs:
        if cur and sim(cur[-1]["text"], s["text"]) >= a.threshold:
            cur.append(s)
        else:
            if cur:
                groups.append(cur)
            cur = [s]
    if cur:
        groups.append(cur)

    keep, dropped = [], []
    for g in groups:
        best = g[-1]
        if len(g) > 1:
            longest = max(len(x["text"]) for x in g)
            ok = [x for x in g if len(x["text"]) >= 0.8 * longest and x.get("avg_logprob", 0) > -1.0]
            best = ok[-1] if ok else g[-1]
            dropped += [x for x in g if x is not best]
        keep.append(best)

    dur = data.get("duration") or keep[-1]["end"]
    spans = []
    for s in keep:
        st, en = max(0.0, s["start"] - a.pad), min(dur, s["end"] + a.pad)
        if spans and st <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], en)
        else:
            spans.append([st, en])

    src = pathlib.Path(a.transcript)
    stem = src.name[:-len(".transcript.json")] if src.name.endswith(".transcript.json") else src.stem
    out = pathlib.Path(a.out) if a.out else src.with_name(stem + ".takes.json")
    out.write_text(json.dumps({"keep": spans, "dropped": dropped}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(groups)} falas, {len(dropped)} tomadas descartadas, {len(spans)} trechos mantidos")
    for x in dropped:
        print(f"  ✘ {x['start']:7.2f}-{x['end']:7.2f}  {x['text'][:70]}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
