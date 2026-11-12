#!/usr/bin/env python3
"""Valida um marca.json (ADR-17) e gera a prancha de aprovação.

Uso: uv run --with pillow --with fonttools python validar_marca.py [marca/marca.json] [--prancha SAIDA.png] [--gravar]

Confere: cores obrigatórias e arquivos citados; contraste WCAG de texto sobre fundo (>= 7) e de acento sobre
fundo (>= 3); fonte encontrada e com os glifos do português; logo com resolução suficiente. Quando um contraste
falha, PROPÕE o menor ajuste de luminosidade (nunca aplica: a cor oficial só muda com aprovação).
--gravar escreve as medidas e as propostas em "contraste" no próprio marca.json.
Prancha (padrão: prancha.png ao lado do marca.json): cartela, destaque com balão sobre tela clara, legenda
sobre claro e escuro, faixa do navegador e encerramento. Mostre a prancha e pare para aprovação antes de renderizar.
Sai com 1 se houver erro (avisos não bloqueiam).
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys


def _raiz_pacote(arquivo):
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo import marca as M  # noqa: E402

GLIFOS_PT = "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
TELA_CLARA, TELA_ESCURA = "#F5F7FA", "#1E1E1E"


def arquivo_da_fonte(m):
    arq = m.fonte_arquivo("bold")
    if arq:
        return arq, True
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}|%{family}", f"{m.fonte}:bold"],
                             capture_output=True, text=True, check=True).stdout.strip()
        arq, fam = out.split("|", 1)
        return arq, m.fonte.lower() in fam.lower()
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None, False


def valida(m):
    erros, avisos, medidas, ajustes = list(m.problemas()), [], {}, []
    if erros:
        return erros, avisos, medidas, ajustes
    c = m.cores
    for nome, a, b, minimo, grave in (("texto_fundo", "texto", "fundo", 7, True),
                                      ("acento_fundo", "acento", "fundo", 3, True),
                                      ("texto2_fundo", "texto2", "fundo", 4.5, False)):
        r = round(M.contraste(c[a], c[b]), 2)
        medidas[nome] = r
        if r < minimo:
            para = M.ajustar_contraste(c[a], c[b], minimo)
            ajustes.append({"papel": a, "de": c[a], "para": para, "motivo": f"contraste {r} < {minimo} sobre {b}"})
            (erros if grave else avisos).append(f"cores.{a} sobre cores.{b}: contraste {r} (mínimo {minimo}); proposta {para}")
    r = round(M.contraste(c["acento"], TELA_CLARA), 2)
    medidas["acento_tela_clara"] = r
    if r < 2:
        avisos.append(f"cores.acento sobre tela clara: contraste {r}; a caixa de destaque some em interface branca "
                      "(use \"focus\": true nos destaques ou aprove um acento mais escuro)")
    arq, achou = arquivo_da_fonte(m)
    if not arq or not os.path.exists(arq):
        erros.append(f"fonte {m.fonte!r}: nenhum arquivo encontrado")
    else:
        if not achou:
            avisos.append(f"fonte {m.fonte!r} não está instalada; o sistema usaria {os.path.basename(arq)}. "
                          "Instale a fonte, aponte fonte.arquivos ou registre uma fonte.substituta")
        try:
            from fontTools.ttLib import TTFont
            cmap = TTFont(arq, fontNumber=0, lazy=True).getBestCmap()
            falta = [ch for ch in GLIFOS_PT if ord(ch) not in cmap]
            if falta:
                erros.append(f"fonte {os.path.basename(arq)} sem os glifos: {''.join(falta)}")
        except ImportError:
            avisos.append("fonttools ausente: glifos do português não conferidos (uv run --with fonttools)")
    if m.dados["fonte"].get("substituta"):
        avisos.append(f"fonte substituta em uso: {m.dados['fonte']['substituta']} (a oficial não foi obtida)")
    png = m.logo("png")
    if png:
        from PIL import Image
        w, h = Image.open(png).size
        if h < 400 and w < 1200:
            avisos.append(f"logo.png tem {w}x{h}: pequeno para o encerramento em 1080p (ideal: altura >= 400)")
    elif not m.logo("svg"):
        avisos.append("sem logo: cartela sem marca e sem tela de encerramento")
    elif m.logo("svg"):
        avisos.append("logo só em SVG: o /video-docs precisa de logo.png (exporte do SVG oficial)")
    return erros, avisos, medidas, ajustes


def prancha(m, saida):
    from PIL import Image, ImageDraw, ImageFont
    arq, _ = arquivo_da_fonte(m)
    c = {k: M.rgb(v) for k, v in m.cores.items()}

    def fonte(tam):
        try:
            return ImageFont.truetype(arq, tam)
        except (OSError, TypeError):
            return ImageFont.load_default()

    CW, CH, G = 960, 540, 24
    img = Image.new("RGB", (CW * 2 + G * 3, CH * 3 + G * 4 + 40), (40, 40, 40))
    d = ImageDraw.Draw(img)
    logo = Image.open(m.logo("png")).convert("RGBA") if m.logo("png") else None

    def fundo(qual):
        arqf = m.fundo(qual) or m.fundo("cartela")
        if arqf:
            return Image.open(arqf).convert("RGB").resize((CW, CH))
        im = Image.new("RGB", (CW, CH))
        px = im.load()
        a, b = c["fundo"], c["fundo2"]
        for y in range(CH):
            for x in range(CW):
                t = (x / CW + y / CH) / 2
                px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
        return im

    def cola_logo(tela, altura, x, y, centro=False):
        if not logo:
            return
        lg = logo.resize((round(logo.width * altura / logo.height), altura))
        tela.paste(lg, (round(x - lg.width / 2) if centro else x, round(y - (altura / 2 if centro else 0))), lg)

    def legenda(td, texto, palavra, y):
        f = fonte(30)
        w = td.textlength(texto, font=f)
        x = (CW - w) / 2
        if m.legenda.get("caixa") or m.legenda.get("estilo", "bloco") == "bloco":
            td.rectangle([x - 14, y - 8, x + w + 14, y + 40], fill=(0, 0, 0))
        td.text((x, y), texto, font=f, fill=c["texto"], stroke_width=2, stroke_fill=(0, 0, 0))
        if m.legenda.get("estilo") == "palavra":
            pre = texto[:texto.index(palavra)]
            td.text((x + td.textlength(pre, font=f), y), palavra, font=f,
                    fill=M.rgb(m.cor(m.legenda.get("destaque") or "acento")), stroke_width=2, stroke_fill=(0, 0, 0))

    def painel(n, titulo):
        x, y = G + (n % 2) * (CW + G), G + (n // 2) * (CH + G)
        return x, y, titulo

    telas = []
    # 1. cartela
    t = fundo("cartela"); td = ImageDraw.Draw(t)
    cola_logo(t, round(CH * 0.065), round(CW * 0.047), round(CH * 0.075))
    td.text((120, 215), "Título do vídeo", font=fonte(36), fill=c["texto"])
    td.rectangle([120, 264, 285, 269], fill=c["acento"])
    td.text((120, 285), "Produto ou área", font=fonte(20), fill=c["acento"])
    telas.append((t, "cartela"))
    # 2 e 3. destaque + legenda sobre tela clara e escura
    for cor_tela, nome in ((TELA_CLARA, "tela clara"), (TELA_ESCURA, "tela escura")):
        t = Image.new("RGB", (CW, CH), M.rgb(cor_tela)); td = ImageDraw.Draw(t)
        ink = tuple(40 if cor_tela == TELA_CLARA else 215 for _ in range(3))
        for i in range(6):
            td.rectangle([80, 120 + i * 48, 80 + 520 - i * 40, 136 + i * 48], fill=ink)
        td.rounded_rectangle([70, 205, 470, 245], radius=6, outline=c["acento"], width=3)
        f = fonte(16); txt = "Balão de destaque"
        bw = td.textlength(txt, font=f) + 30
        td.rounded_rectangle([500, 208, 500 + bw, 240], radius=8, fill=c["fundo"])
        td.rectangle([508, 216, 511, 232], fill=c["acento"])
        td.text((520, 214), txt, font=f, fill=c["texto"])
        td.rounded_rectangle([12, 82, 190, 106], radius=12, fill=c["fundo"])
        td.ellipse([22, 90, 30, 98], fill=c["acento"])
        td.text((36, 85), "1/3  ·  Chip da cena", font=fonte(13), fill=c["texto"])
        # faixa do navegador
        td.rectangle([0, 0, CW, 75], fill=c["fundo"]); td.rectangle([0, 73, CW, 75], fill=c["acento"])
        cola_logo(t, 31, 21, 22)
        lw = round(logo.width * 31 / logo.height) + 14 if logo else 0
        td.text((21 + lw, 27), "Título do vídeo", font=fonte(17), fill=c["texto"])
        st = "Produto ou área"; fs = fonte(13)
        td.text((CW - 21 - td.textlength(st, font=fs), 30), st, font=fs, fill=c["acento"])
        legenda(td, "A legenda aparece assim na tela.", "legenda", 470)
        telas.append((t, f"faixa, destaque e legenda sobre {nome}"))
    # 4. encerramento
    t = fundo("encerramento"); td = ImageDraw.Draw(t)
    cola_logo(t, round(CH * 0.12), CW / 2, CH * 0.36, centro=True)
    st = "Produto ou área"; fs = fonte(20)
    td.text(((CW - td.textlength(st, font=fs)) / 2, 315), st, font=fs, fill=c["acento"])
    telas.append((t, "encerramento" + ("" if logo else " (sem logo: não é gerado)")))
    # 5. paleta
    t = Image.new("RGB", (CW, CH), (250, 250, 250)); td = ImageDraw.Draw(t)
    for i, (k, v) in enumerate(m.cores.items()):
        x = 40 + (i % 3) * 300; y = 40 + (i // 3) * 240
        td.rectangle([x, y, x + 260, y + 150], fill=M.rgb(v), outline=(120, 120, 120))
        td.text((x, y + 160), f"{k}  {v.upper()}", font=fonte(18), fill=(20, 20, 20))
    telas.append((t, "papéis de cor"))
    # 6. tipografia
    t = Image.new("RGB", (CW, CH), c["fundo"]); td = ImageDraw.Draw(t)
    td.text((50, 50), m.fonte, font=fonte(54), fill=c["texto"])
    td.text((50, 140), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", font=fonte(26), fill=c["texto2"])
    td.text((50, 185), "abcdefghijklmnopqrstuvwxyz 0123456789", font=fonte(26), fill=c["texto2"])
    td.text((50, 240), "Ação, configuração, índice, à, õ, ü, ç", font=fonte(30), fill=c["acento"])
    sub = m.dados["fonte"].get("substituta")
    td.text((50, 330), f"arquivo: {os.path.basename(arq) if arq else 'não encontrado'}"
            + (f"  ·  SUBSTITUTA: {sub}" if sub else ""), font=fonte(18), fill=c["texto"])
    telas.append((t, "tipografia"))

    rot = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16) \
        if os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") else ImageFont.load_default()
    for n, (t, titulo) in enumerate(telas):
        x, y = G + (n % 2) * (CW + G), G + (n // 2) * (CH + G + 12)
        img.paste(t, (x, y + 20))
        d.text((x, y), titulo, font=rot, fill=(230, 230, 230))
    img.save(saida)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("marca", nargs="?", default="marca/marca.json")
    ap.add_argument("--prancha", help="PNG de saída (padrão: prancha.png ao lado do marca.json)")
    ap.add_argument("--sem-prancha", action="store_true")
    ap.add_argument("--gravar", action="store_true", help="grava medidas e propostas em 'contraste' no marca.json")
    a = ap.parse_args()
    m = M.carregar(a.marca, estrito=False)
    erros, avisos, medidas, ajustes = valida(m)
    rel = {"marca": m.nome, "arquivo": m.arquivo, "contraste": medidas, "ajustes_propostos": ajustes,
           "erros": erros, "avisos": avisos}
    if not m.problemas():
        if a.gravar:
            dados = json.load(open(m.arquivo, encoding="utf-8"))
            dados["contraste"] = dict(medidas, ajustes=ajustes)
            json.dump(dados, open(m.arquivo, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if not a.sem_prancha:
            rel["prancha"] = a.prancha or os.path.join(m.pasta, "prancha.png")
            prancha(m, rel["prancha"])
    print(json.dumps(rel, ensure_ascii=False, indent=1))
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
