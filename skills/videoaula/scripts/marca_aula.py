"""Identidade da videoaula a partir de marca/marca.json (ADR-17): padrões de `cores` e de fonte do aula.json.

O aula.json continua mandando: o que estiver em `cores`, `fonte` e `fonte_dir` vence a marca.
Papéis: fundo -> fundo_borda, fundo2 -> fundo_centro, acento -> acento, secundario -> destaque, texto, texto2.
"""
import os
import pathlib
import sys


def _raiz_pacote(arquivo):
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[3])


def carregar(cfg, base="."):
    """Marca do projeto ("marca" no aula.json > $VE_MARCA > <base>/marca/marca.json), ou a padrão."""
    sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
    from video_editores.nucleo import marca as M
    return M.carregar(cfg.get("marca"), base=base)


def cores(m, padrao):
    """Dicionário de cores da videoaula: padrão do script < marca < cfg["cores"] (aplicado por quem chama)."""
    if not m.definida:
        return dict(padrao)
    c = m.cores
    mapa = {"fundo_borda": c["fundo"], "fundo_centro": c["fundo2"], "acento": c["acento"],
            "destaque": c["secundario"], "texto": c["texto"], "texto2": c["texto2"]}
    return {**padrao, **{k: v for k, v in mapa.items() if k in padrao}}


def fonte_arquivo(m, peso):
    """TTF da marca para um peso numérico (400 -> regular; 600+ -> bold), ou None."""
    if not m.definida:
        return None
    return m.fonte_arquivo("regular" if int(peso) < 600 else "bold")
