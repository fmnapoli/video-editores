#!/usr/bin/env python3
"""Ponte entre os scripts de linha de comando e a identidade do projeto (marca/marca.json, ADR-17).

Como módulo: `add_arg(ap)` acrescenta --marca; `carregar(a.marca)` devolve a Marca (ou a padrão, com
`definida = False`); `escolhe(valor, da_marca, padrao)` aplica a precedência argumento > marca > padrão do script;
`fontsdir(m)` devolve o sufixo `:fontsdir=...` do filtro ass/subtitles quando a fonte vem por arquivo.

Como comando, para a queima de SRT pelo ffmpeg (skill /legenda):
  marca_cli.py force-style [--marca ARQ] [--tamanho 22] [--margem 60]   imprime o force_style nas cores e fonte da marca
  marca_cli.py fontsdir [--marca ARQ]                                    imprime a pasta dos TTF da marca (vazio se não houver)
"""
import argparse
import os
import pathlib
import sys


def _raiz_pacote(arquivo):
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo import marca as M  # noqa: E402


def add_arg(ap):
    ap.add_argument("--marca", default=None,
                    help="marca.json do projeto (padrão: $VE_MARCA ou marca/marca.json, se existir; 'nao' ignora)")


def carregar(explicito=None):
    return M.carregar(False if explicito in ("nao", "não", "none") else explicito)


def escolhe(valor, da_marca, padrao, m=None):
    """Argumento explícito > marca definida > padrão do script."""
    if valor is not None:
        return valor
    return da_marca if (m is None or m.definida) and da_marca is not None else padrao


def fontsdir(m):
    d = m.fontes_dir() if m.definida else None
    if not d:
        return ""
    esc = d.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
    return f":fontsdir='{esc}'"


def force_style(m, tamanho=22, margem=60):
    c = m.cores
    return (f"FontName={m.fonte},FontSize={tamanho},Bold=1,PrimaryColour={M.ass(c['texto']).rstrip('&')},"
            f"OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV={margem}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["force-style", "fontsdir"])
    add_arg(ap)
    ap.add_argument("--tamanho", type=int, default=22)
    ap.add_argument("--margem", type=int, default=60)
    a = ap.parse_args()
    m = carregar(a.marca)
    if a.comando == "force-style":
        print(force_style(m, a.tamanho, a.margem))
    else:
        print((m.fontes_dir() or "") if m.definida else "")


if __name__ == "__main__":
    main()
