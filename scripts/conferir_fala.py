#!/usr/bin/env python3
"""Confere se o que se ouve no vídeo final é o que estava no roteiro, palavra por palavra.

Entrada: o roteiro e a transcrição do áudio FINAL (rode `transcribe.py` no vídeo entregue). Compara as duas
sequências de palavras sem diferenciar maiúscula, acento nem pontuação e lista, com o instante no vídeo:
  faltou    palavras do roteiro que não foram ditas (corte errado, TTS que engoliu um trecho, cena fora de ordem)
  sobrou    palavras ditas que não estão no roteiro (tomada repetida que escapou, cena duplicada)
  trocou    palavra dita no lugar de outra
  parecida  troca por palavra quase igual: quase sempre erro do reconhecimento de fala; não conta na taxa

Uso: conferir_fala.py ROTEIRO TRANSCRICAO.transcript.json [--tolerancia 0.02] [--equivalentes eq.json] [--out ARQ.fala.md]
  ROTEIRO  .txt/.md (linhas de título `#`, citações `>` e trechos entre [colchetes] são ignorados),
           cenas.json do /video-animado (campo `narracao`) ou spec.json do /video-docs (`tts`, senão `legend`).
  --equivalentes  JSON {"como está no roteiro": "como o reconhecimento escreve"}, para número, sigla e nome
                  próprio. Ex.: {"5.2": "cinco ponto dois", "k8s": "kubernetes"}.
  --tolerancia    fração de palavras do roteiro com diferença acima da qual o script sai com código 1.

Só biblioteca padrão. Grava <nome>.fala.md (para ler) e <nome>.fala.json (para o relatório de edição).
"""
import argparse
import difflib
import json
import pathlib
import re
import sys
import unicodedata


def plano(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]|_", " ", s)


def tokens(s: str) -> list:
    return plano(s).split()


def texto_roteiro(path: pathlib.Path) -> str:
    bruto = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        d = json.loads(bruto)
        cenas = d if isinstance(d, list) else d.get("cenas") if isinstance(d, dict) else None
        if cenas is not None:   # /video-animado: lista de cenas, ou {"cenas": [...]}
            return " ".join(c.get("narracao") or "" for c in cenas if isinstance(c, dict))
        if isinstance(d, dict) and "scenes" in d:
            return " ".join(sc["tts"] if sc.get("tts") else " ".join(sc.get("legend", [])) for sc in d["scenes"])
        sys.exit(f"{path}: JSON sem cenas (video-animado) nem `scenes` (video-docs)")
    linhas = [ln for ln in bruto.splitlines() if not ln.lstrip().startswith(("#", ">"))]
    return re.sub(r"\[[^\]]*\]", " ", " ".join(linhas))


def palavras_fala(path: pathlib.Path) -> list:
    """[(token, instante)] da transcrição; sem tempos por palavra, usa o início do segmento."""
    d = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for seg in d.get("segments", []):
        if seg.get("words"):
            for w in seg["words"]:
                out += [(tk, float(w["start"])) for tk in tokens(w["word"])]
        else:
            out += [(tk, float(seg["start"])) for tk in tokens(seg.get("text", ""))]
    return out


def aplicar_equivalentes(toks, pares):
    """Troca sequências `de` por `para` (já em tokens). `toks` pode ser lista de str ou de (str, t)."""
    eh_par = bool(toks) and isinstance(toks[0], tuple)
    out, i = [], 0
    while i < len(toks):
        for de, para in pares:
            n = len(de)
            trecho = [t[0] if eh_par else t for t in toks[i:i + n]]
            if n and trecho == de:
                out += [(p, toks[i][1]) for p in para] if eh_par else list(para)
                i += n
                break
        else:
            out.append(toks[i])
            i += 1
    return out


def relogio(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def comparar(roteiro, fala):
    """roteiro: [str]; fala: [(str, t)] -> lista de diferenças na ordem do vídeo."""
    f_tok = [p[0] for p in fala]
    sm = difflib.SequenceMatcher(None, roteiro, f_tok, autojunk=False)
    difs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        j = min(j1, len(fala) - 1)
        t = fala[j][1] if fala else 0.0
        r, f = roteiro[i1:i2], f_tok[j1:j2]
        tipo = {"delete": "faltou", "insert": "sobrou"}.get(op, "trocou")
        if tipo == "trocou" and difflib.SequenceMatcher(None, " ".join(r), " ".join(f)).ratio() >= 0.8:
            tipo = "parecida"
        ctx = " ".join(roteiro[max(0, i1 - 4):i1])
        difs.append({"tipo": tipo, "t": round(t, 2), "roteiro": " ".join(r), "fala": " ".join(f), "antes": ctx,
                     "peso": 0 if tipo == "parecida" else max(len(r), len(f))})
    return difs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roteiro")
    ap.add_argument("transcricao")
    ap.add_argument("--tolerancia", type=float, default=0.02)
    ap.add_argument("--equivalentes", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    roteiro = tokens(texto_roteiro(pathlib.Path(a.roteiro)))
    fala = palavras_fala(pathlib.Path(a.transcricao))
    if not roteiro:
        sys.exit(f"{a.roteiro}: roteiro vazio")
    if not fala:
        sys.exit(f"{a.transcricao}: transcrição sem palavras (o vídeo tem fala?)")
    if a.equivalentes:
        eq = json.loads(pathlib.Path(a.equivalentes).read_text(encoding="utf-8"))
        # as duas pontas vão para a mesma forma (a do roteiro), então tanto faz como o reconhecimento escreveu
        pares = sorted(((tokens(v), tokens(k)) for k, v in eq.items()), key=lambda p: -len(p[0]))
        fala = aplicar_equivalentes(fala, pares)
        roteiro = aplicar_equivalentes(roteiro, pares)

    difs = comparar(roteiro, fala)
    erros = sum(d["peso"] for d in difs)
    taxa = erros / len(roteiro)
    passou = taxa <= a.tolerancia
    tr = pathlib.Path(a.transcricao)
    base = tr.name[:-len(".transcript.json")] if tr.name.endswith(".transcript.json") else tr.stem
    out_md = pathlib.Path(a.out) if a.out else tr.with_name(base + ".fala.md")
    if out_md.suffix.lower() == ".json":   # --out x.json: o relatório para ler vai ao lado, em .md
        out_md = out_md.with_suffix(".md")
    out_json = out_md.with_suffix(".json")

    linhas = [f"# Fala × roteiro: {'OK' if passou else 'DIFERENTE'}", "",
              f"- palavras no roteiro: {len(roteiro)} · na fala: {len(fala)}",
              f"- diferenças que contam: {erros} ({taxa:.1%}; tolerância {a.tolerancia:.1%})",
              f"- parecidas (provável erro do reconhecimento, não contam): {sum(1 for d in difs if d['tipo'] == 'parecida')}", ""]
    if difs:
        linhas += ["| instante | tipo | roteiro | fala | depois de |", "|---|---|---|---|---|"]
        linhas += [f"| {relogio(d['t'])} | {d['tipo']} | {d['roteiro'] or '—'} | {d['fala'] or '—'} | …{d['antes']} |" for d in difs]
        linhas += ["", "Ouça cada instante antes de corrigir: a transcrição também erra. Nome próprio, sigla e número "
                   "que o reconhecimento escreve de outro jeito vão para `--equivalentes`."]
    out_md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps({"ok": passou, "taxa": round(taxa, 4), "tolerancia": a.tolerancia,
                                    "palavras_roteiro": len(roteiro), "palavras_fala": len(fala), "diferencas": difs},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'ok' if passou else 'DIFERENTE'}: {erros} palavra(s) com diferença em {len(roteiro)} ({taxa:.1%}) -> {out_md}")
    for d in [d for d in difs if d["tipo"] != "parecida"][:12]:
        print(f"  {relogio(d['t'])}  {d['tipo']}: roteiro \"{d['roteiro'] or '—'}\" · fala \"{d['fala'] or '—'}\"")
    if not passou:
        sys.exit(1)


if __name__ == "__main__":
    main()
