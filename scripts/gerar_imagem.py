#!/usr/bin/env python3
"""Gera imagens a partir de um prompt no backend de imagem configurado (padrão: servidor ComfyUI). ADR-15.

Uma rodada = N variações (uma por semente) + folha de contato para o gate de escolha + registro em JSON
para regenerar e para o relatório de edição dizer o que foi gerado:
  <out>/<id>-<semente>.png     uma por variação
  <out>/<id>.folha.png         miniaturas lado a lado com a semente de cada uma (gate 1 do ADR-15)
  <out>/<id>.json              rodadas: prompt, negativo, tamanho, passos, sementes, backend, workflow (sha256),
                               modelo, licença, versão do servidor, data. Rodadas novas do mesmo id se somam.

Uso: gerar_imagem.py "PROMPT" [--id fundo-abertura] [--out gerados] [--variacoes 4] [--semente N]
     [--largura 1344] [--altura 768] [--passos N] [--negativo TEXTO] [--workflow NOME|ARQ.json]
     [--backend comfyui] [--sem-folha]
     gerar_imagem.py --conferir [--workflow ...]   (só verifica servidor e checkpoint; imprime JSON)

Regenerar uma escolhida: mesmo prompt com --semente S --variacoes 1. Servidor: VE_COMFYUI_URL (padrão
http://127.0.0.1:8188). A skill não gera rosto de pessoa real nem imita a pessoa gravada (ADR-15).
"""
import argparse
import json
import os
import pathlib
import random
import re
import sys
import time
import unicodedata


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores import modelos  # noqa: E402


def slug(texto, n=5):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", t)[:n]) or "imagem"


def folha(pngs, sementes, destino, largura=480):
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p).convert("RGB") for p in pngs]
    alt = round(largura * ims[0].height / ims[0].width)
    cols = 2 if len(ims) > 1 else 1
    linhas = -(-len(ims) // cols)
    m, faixa = 12, 34
    sheet = Image.new("RGB", (cols * (largura + m) + m, linhas * (alt + faixa + m) + m), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    try:
        fonte = ImageFont.load_default(size=20)
    except TypeError:  # Pillow < 10.1
        fonte = ImageFont.load_default()
    for i, (im, s) in enumerate(zip(ims, sementes)):
        x, y = m + (i % cols) * (largura + m), m + (i // cols) * (alt + faixa + m)
        sheet.paste(im.resize((largura, alt)), (x, y))
        d.text((x + 4, y + alt + 6), f"{i + 1}  semente {s}", fill=(230, 230, 230), font=fonte)
    sheet.save(destino)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompt", nargs="?")
    ap.add_argument("--id")
    ap.add_argument("--out", default="gerados")
    ap.add_argument("--variacoes", type=int, default=4)
    ap.add_argument("--semente", type=int, help="primeira semente; as variações usam as seguintes")
    ap.add_argument("--largura", type=int, default=1344)
    ap.add_argument("--altura", type=int, default=768)
    ap.add_argument("--passos", type=int)
    ap.add_argument("--negativo", default="")
    ap.add_argument("--workflow")
    ap.add_argument("--backend")
    ap.add_argument("--sem-folha", action="store_true")
    ap.add_argument("--conferir", action="store_true")
    a = ap.parse_args()

    kw = {"workflow": a.workflow} if a.workflow else {}
    try:
        g = modelos.get_imagem(a.backend, **kw)
        servidor = g.conferir() if hasattr(g, "conferir") else {}
    except (RuntimeError, ValueError) as e:
        raise SystemExit(f"gerar_imagem: {e}") from None
    if a.conferir:
        print(json.dumps({"backend": g.info(), "servidor": servidor}, ensure_ascii=False, indent=1))
        return
    if not a.prompt:
        ap.error("falta o PROMPT (ou use --conferir)")
    for nome, v in (("largura", a.largura), ("altura", a.altura)):
        if v % 16:
            ap.error(f"--{nome} {v} precisa ser múltiplo de 16 (latente do modelo)")

    ident = a.id or slug(a.prompt)
    base = a.semente if a.semente is not None else random.SystemRandom().randrange(2**31)
    sementes = [base + i for i in range(max(1, a.variacoes))]
    out = pathlib.Path(a.out)
    t0 = time.time()
    try:
        pngs = g.gerar(a.prompt, out, negativo=a.negativo, largura=a.largura, altura=a.altura,
                       sementes=sementes, passos=a.passos, prefixo=ident)
    except (RuntimeError, ValueError) as e:
        raise SystemExit(f"gerar_imagem: {e}") from None

    rodada = {"data": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "segundos": round(time.time() - t0, 1),
              "prompt": a.prompt, "negativo": a.negativo, "largura": a.largura, "altura": a.altura,
              "passos": a.passos or getattr(g, "meta", {}).get("passos"), "sementes": sementes,
              "arquivos": [p.name for p in pngs], "backend": g.info(), "servidor": servidor}
    reg = out / f"{ident}.json"
    dados = json.loads(reg.read_text(encoding="utf-8")) if reg.is_file() else {"id": ident, "rodadas": []}
    dados["rodadas"].append(rodada)
    reg.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    if not a.sem_folha:
        folha(pngs, sementes, out / f"{ident}.folha.png")
        print(out / f"{ident}.folha.png")
    for p in pngs:
        print(p)
    print(reg)


if __name__ == "__main__":
    main()
