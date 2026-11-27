#!/usr/bin/env python3
"""Arco narrativo de um vídeo falado, em sete etapas (estrutura "Backbone", de Letícia Pacheco):
desafio -> identificação -> causa -> solução -> método -> motivação -> conclusão.

Serve a vídeo de ensino e de convencimento (aula, reels, apresentação). Não serve a tutorial de tela nem a
documentação: ali etapas como "motivação" ficam forçadas, e o corte por pontuação do highlights.py é o caminho.

Três comandos, com um plano revisável no meio (como o .camera.json):

  backbone.py blocos VIDEO.transcript.json [--gap 1.2] [--min-block 3] [--max-block 45] [--keywords "a,b"]
      Divide a fala em blocos e grava <nome>.backbone.json. Cada bloco sai com `sugestao` (etapa provável, por
      palavras-marcadoras e pela posição no vídeo) e com `etapa` vazia. A sugestão é heurística: QUEM DECIDE É
      QUEM LÊ. Preencha `etapa` em cada bloco com uma das sete chaves, ou "fora" para o que não entra no arco.

  backbone.py relatorio ARQ.backbone.json [--json] [--usar-sugestao]
      Grava <nome>.backbone.md: quais etapas o vídeo tem, quais faltam, quanto tempo cada uma ocupa, se a ordem
      em que aparecem é a do arco e onde o tempo está desequilibrado. --json imprime o resumo.

  backbone.py montar ARQ.backbone.json --target 90 [--reordenar] [--pesos "metodo=0.4,causa=0.1"] [--out ARQ.json]
      Grava <nome>.backbone.keep.json ({"keep": [[s,e],...]}, para o render_spans.sh) com pelo menos um bloco de
      cada etapa presente, repartindo o alvo pelos pesos das etapas e escolhendo os blocos de maior pontuação.
      Sem --reordenar os trechos ficam na ordem em que foram gravados; com ele, na ordem do arco (o relatório
      lista cada inversão, porque fala fora de ordem pode citar algo que ainda não foi dito).

`relatorio` e `montar` recusam plano com `etapa` vazia (código 2), a menos de --usar-sugestao.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from highlights import build_blocks, score_block  # noqa: E402

# chave, nome, pergunta que o trecho responde, posição típica no vídeo (0 a 1), peso no corte, marcadores
ETAPAS = [
    ("desafio", "Desafio", "Que problema é este, e por que ele incomoda?", 0.04, 0.12,
     ["problema", "desafio", "dificuldade", "difícil", "dor", "sofre", "trava", "não consegue", "não sabe",
      "cansado", "frustra", "erro comum", "perde tempo"]),
    ("identificacao", "Identificação", "Onde quem assiste se reconhece nisso?", 0.14, 0.12,
     ["você já", "já aconteceu", "sabe quando", "comigo", "eu também", "eu já", "por exemplo", "imagina",
      "todo mundo", "a gente", "quem nunca"]),
    ("causa", "Causa", "Por que isso acontece, e com que base se afirma?", 0.28, 0.15,
     ["porque", "por que", "motivo", "causa", "acontece", "razão", "estudo", "pesquisa", "dados", "ciência",
      "por cento", "comprov"]),
    ("solucao", "Solução", "O que resolve, e o que mostra que resolve?", 0.44, 0.15,
     ["solução", "resolve", "resposta", "saída", "segredo", "funciona", "o que muda", "a diferença", "prova"]),
    ("metodo", "Método", "Quais são os passos, na ordem em que se faz?", 0.64, 0.28,
     ["passo", "primeiro", "segundo", "terceiro", "depois", "em seguida", "por último", "como fazer", "comece",
      "na prática", "etapa"]),
    ("motivacao", "Motivação", "Que resultado dá vontade de agir agora?", 0.84, 0.10,
     ["resultado", "conseguiu", "consegui", "história", "caso", "cliente", "aluno", "você pode", "você consegue",
      "vale a pena", "mudou", "hoje ele", "hoje ela"]),
    ("conclusao", "Conclusão", "Com que frase e com que energia o vídeo termina?", 0.97, 0.08,
     ["resumindo", "conclusão", "para fechar", "pra fechar", "então é isso", "por hoje", "agora é", "até a próxima",
      "se inscreva", "compartilhe", "comenta", "me conta", "bora"]),
]
CHAVES = [e[0] for e in ETAPAS]
NOME = {e[0]: e[1] for e in ETAPAS}
FORA = "fora"


def _norm(t):
    return re.sub(r"\s+", " ", t.lower())


def sugerir(texto, pos):
    """(etapa, confiança 0-1). Marcadores pesam mais que a posição; sem marcador nenhum, vale só a posição."""
    t = _norm(texto)
    notas = {}
    for chave, _, _, centro, _, marcas in ETAPAS:
        achados = sum(t.count(m) for m in marcas)
        notas[chave] = 2.0 * achados + max(0.0, 1.0 - abs(pos - centro) / 0.25)
    ordem = sorted(notas, key=notas.get, reverse=True)
    melhor, segundo = notas[ordem[0]], notas[ordem[1]]
    return ordem[0], round(min(1.0, (melhor - segundo) / 2.0), 2)


def cmd_blocos(a):
    data = json.loads(pathlib.Path(a.arquivo).read_text(encoding="utf-8"))
    segs = [s for s in data.get("segments", []) if s.get("text", "").strip()]
    if not segs:
        sys.exit("transcrição sem fala")
    dur = data.get("duration") or segs[-1]["end"]
    kw = [k.strip().lower() for k in a.keywords.split(",") if k.strip()]
    brutos = [b for b in build_blocks(segs, a.gap, a.max_block) if b["end"] - b["start"] >= a.min_block]
    if not brutos:
        sys.exit(f"nenhum bloco com pelo menos {a.min_block}s; reduza --min-block")
    blocos = []
    for i, b in enumerate(brutos, 1):
        etapa, conf = sugerir(b["text"], ((b["start"] + b["end"]) / 2) / dur)
        blocos.append({"id": i, "inicio": round(b["start"], 2), "fim": round(b["end"], 2), "etapa": None,
                       "sugestao": etapa, "confianca": conf, "pontos": round(score_block(b["text"], kw), 2),
                       "texto": b["text"].strip()})
    src = pathlib.Path(a.arquivo)
    stem = src.name[:-len(".transcript.json")] if src.name.endswith(".transcript.json") else src.stem
    out = pathlib.Path(a.out) if a.out else src.with_name(stem + ".backbone.json")
    plano = {"duracao": round(dur, 2),
             "etapas": [{"chave": c, "nome": n, "pergunta": p} for c, n, p, _, _, _ in ETAPAS],
             "como_preencher": 'em cada bloco, "etapa" = uma das chaves acima, ou "fora" para o que não entra no arco',
             "blocos": blocos}
    out.write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(blocos)} blocos -> {out} (preencha \"etapa\" em cada um; \"sugestao\" é só o ponto de partida)")


def carregar(arq, usar_sugestao):
    plano = json.loads(pathlib.Path(arq).read_text(encoding="utf-8"))
    blocos = plano.get("blocos") or []
    if not blocos:
        sys.exit("plano sem blocos")
    vazios = [b["id"] for b in blocos if not b.get("etapa")]
    if vazios and not usar_sugestao:
        print(f"{len(vazios)} bloco(s) sem etapa ({', '.join(map(str, vazios[:12]))}{'…' if len(vazios) > 12 else ''}): "
              "preencha, ou use --usar-sugestao para aceitar a heurística", file=sys.stderr)
        sys.exit(2)
    for b in blocos:
        b["etapa"] = b.get("etapa") or b.get("sugestao")
        if b["etapa"] not in CHAVES and b["etapa"] != FORA:
            sys.exit(f"bloco {b['id']}: etapa {b['etapa']!r} desconhecida; use {', '.join(CHAVES)} ou {FORA}")
    return plano, blocos


def resumo(plano, blocos):
    dentro = [b for b in blocos if b["etapa"] != FORA]
    total = sum(b["fim"] - b["inicio"] for b in dentro) or 1.0
    etapas = {}
    for c in CHAVES:
        bs = [b for b in dentro if b["etapa"] == c]
        d = sum(b["fim"] - b["inicio"] for b in bs)
        etapas[c] = {"blocos": len(bs), "duracao": round(d, 1), "fracao": round(d / total, 3),
                     "primeira": bs[0]["inicio"] if bs else None}
    presentes = [c for c in CHAVES if etapas[c]["blocos"]]
    aparicao = sorted(presentes, key=lambda c: etapas[c]["primeira"])
    inversoes = [[a, b] for i, a in enumerate(aparicao) for b in aparicao[i + 1:] if CHAVES.index(a) > CHAVES.index(b)]
    desequilibrio = [c for c in presentes if etapas[c]["fracao"] > 0.5] + \
                    [c for c in presentes if etapas[c]["fracao"] < 0.03]
    return {"duracao_no_arco": round(total, 1), "duracao_fora": round(sum(b["fim"] - b["inicio"] for b in blocos) - total, 1),
            "etapas": etapas, "ausentes": [c for c in CHAVES if c not in presentes], "ordem_de_aparicao": aparicao,
            "inversoes": inversoes, "desequilibrio": desequilibrio}


def _stem(arq):
    p = pathlib.Path(arq)
    return p.with_name(p.name[:-len(".backbone.json")] if p.name.endswith(".backbone.json") else p.stem)


def cmd_relatorio(a):
    plano, blocos = carregar(a.arquivo, a.usar_sugestao)
    r = resumo(plano, blocos)
    md = [f"# Arco narrativo — {_stem(a.arquivo).name}", "",
          f"{r['duracao_no_arco']:.0f} s no arco · {r['duracao_fora']:.0f} s fora dele · {len(blocos)} blocos", "",
          "| etapa | presente | blocos | duração (s) | % do arco | 1ª aparição (s) |", "|---|---|---|---|---|---|"]
    for c in CHAVES:
        e = r["etapas"][c]
        md.append(f"| {NOME[c]} | {'sim' if e['blocos'] else '**não**'} | {e['blocos']} | {e['duracao']:.0f} | "
                  f"{e['fracao'] * 100:.0f} | {'' if e['primeira'] is None else format(e['primeira'], '.1f')} |")
    md += ["", "## O que observar", ""]
    if r["ausentes"]:
        md.append("- **Etapas ausentes:** " + ", ".join(NOME[c] for c in r["ausentes"]) +
                  ". Regravar, cobrir com texto na tela, ou aceitar que o vídeo não tem esse trecho.")
    for x, y in r["inversoes"]:
        md.append(f"- **Ordem:** {NOME[x]} aparece antes de {NOME[y]}; no arco é o contrário.")
    for c in r["desequilibrio"]:
        f = r["etapas"][c]["fracao"]
        md.append(f"- **Tempo:** {NOME[c]} ocupa {f * 100:.0f}% do arco" + (" (mais da metade)." if f > 0.5 else " (quase nada)."))
    if not (r["ausentes"] or r["inversoes"] or r["desequilibrio"]):
        md.append("- Sete etapas presentes, na ordem do arco e sem etapa dominante.")
    md += ["", "## Blocos", "", "| # | início | fim | etapa | começo do texto |", "|---|---|---|---|---|"]
    for b in blocos:
        md.append(f"| {b['id']} | {b['inicio']:.1f} | {b['fim']:.1f} | {NOME.get(b['etapa'], 'fora')} | {b['texto'][:80]} |")
    out = _stem(a.arquivo).with_name(_stem(a.arquivo).name + ".backbone.md")
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        falta = ", ".join(NOME[c] for c in r["ausentes"]) or "nenhuma"
        print(f"etapas ausentes: {falta} · inversões: {len(r['inversoes'])} -> {out}")


def cmd_montar(a):
    plano, blocos = carregar(a.arquivo, a.usar_sugestao)
    pesos = {e[0]: e[4] for e in ETAPAS}
    for par in filter(None, (p.strip() for p in a.pesos.split(","))):
        k, _, v = par.partition("=")
        if k not in pesos:
            sys.exit(f"--pesos: etapa {k!r} desconhecida")
        pesos[k] = float(v)
    presentes = [c for c in CHAVES if any(b["etapa"] == c for b in blocos)]
    if not presentes:
        sys.exit("nenhum bloco dentro do arco")
    soma = sum(pesos[c] for c in presentes) or 1.0
    escolhidos, sobra = [], 0.0
    for c in presentes:
        verba = a.target * pesos[c] / soma + sobra
        cands = sorted((b for b in blocos if b["etapa"] == c), key=lambda b: b.get("pontos", 0), reverse=True)
        usados = 0.0
        for n, b in enumerate(cands):
            d = b["fim"] - b["inicio"]
            if n and usados + d > verba:      # o melhor de cada etapa entra sempre, mesmo passando da verba
                continue
            escolhidos.append(b)
            usados += d
        sobra = max(0.0, verba - usados)      # o que a etapa não usou passa para a seguinte
    dur = plano.get("duracao") or max(b["fim"] for b in blocos)
    if a.reordenar:
        escolhidos.sort(key=lambda b: (CHAVES.index(b["etapa"]), b["inicio"]))
    else:
        escolhidos.sort(key=lambda b: b["inicio"])
    keep = []
    for b in escolhidos:
        s, e = max(0.0, b["inicio"] - a.pad), min(dur, b["fim"] + a.pad)
        if keep and not a.reordenar and s <= keep[-1][1]:
            keep[-1][1] = max(keep[-1][1], round(e, 2))
        else:
            keep.append([round(s, 2), round(e, 2)])
    invertidos = [[x["id"], y["id"]] for x, y in zip(escolhidos, escolhidos[1:]) if y["inicio"] < x["inicio"]]
    out = pathlib.Path(a.out) if a.out else _stem(a.arquivo).with_name(_stem(a.arquivo).name + ".backbone.keep.json")
    out.write_text(json.dumps({"keep": keep, "ordem": "arco" if a.reordenar else "gravacao",
                               "blocos": [{"id": b["id"], "etapa": b["etapa"]} for b in escolhidos],
                               "invertidos": invertidos}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(e - s for s, e in keep)
    print(f"{len(keep)} trechos, {total:.0f}s (alvo {a.target:.0f}s), etapas: {', '.join(presentes)} -> {out}")
    if total > a.target * 1.15:
        print(f"aviso: {total:.0f}s passa do alvo; o melhor bloco de cada etapa entra inteiro. "
              "Divida blocos longos (--max-block menor) ou marque como \"fora\".", file=sys.stderr)
    for x, y in invertidos:
        print(f"aviso: bloco {y} foi gravado antes do {x} e entra depois; confira se a fala não cita o que ainda não foi dito",
              file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)
    b = sub.add_parser("blocos")
    b.add_argument("arquivo")
    b.add_argument("--gap", type=float, default=1.2, help="pausa (s) que separa blocos")
    b.add_argument("--min-block", type=float, default=3.0, help="descarta blocos mais curtos (s)")
    b.add_argument("--max-block", type=float, default=45.0, help="bloco maior que isto é dividido em fronteira de segmento")
    b.add_argument("--keywords", default="", help="palavras-chave do tema, para a pontuação dos blocos")
    b.add_argument("--out", default=None)
    b.set_defaults(f=cmd_blocos)
    r = sub.add_parser("relatorio")
    r.add_argument("arquivo")
    r.add_argument("--json", action="store_true")
    r.add_argument("--usar-sugestao", action="store_true")
    r.set_defaults(f=cmd_relatorio)
    m = sub.add_parser("montar")
    m.add_argument("arquivo")
    m.add_argument("--target", type=float, required=True, help="duração alvo em segundos")
    m.add_argument("--reordenar", action="store_true", help="trechos na ordem do arco, não na da gravação")
    m.add_argument("--pesos", default="", help='fração do alvo por etapa, ex.: "metodo=0.4,causa=0.1"')
    m.add_argument("--pad", type=float, default=0.15)
    m.add_argument("--usar-sugestao", action="store_true")
    m.add_argument("--out", default=None)
    m.set_defaults(f=cmd_montar)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
