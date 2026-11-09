"""video_editores: núcleo do plugin video-editores.

Camadas (docs/arquitetura.md, ADR-10):
  modelos/  interfaces de IA (ASR, segmentação de pessoa, TTS) com backends trocáveis por configuração;
  nucleo/   utilidades determinísticas (ffmpeg, catálogo de operações);
  cli.py    `video-editores <operação> ...`, um ponto de entrada para todos os scripts;
  tarefas.py / mcp_server.py  execução assíncrona e servidor MCP sobre o mesmo catálogo.

Os scripts em scripts/ e skills/*/scripts/ continuam funcionando sozinhos; o pacote só os organiza.
"""
from pathlib import Path

__version__ = "0.8.0"

_PKG = Path(__file__).resolve().parent


def raiz_recursos() -> Path:
    """Pasta que contém scripts/ e skills/: a raiz do repositório quando rodando do checkout
    (ou do cache do plugin), ou video_editores/recursos/ quando instalado como roda."""
    repo = _PKG.parent
    if (repo / "scripts").is_dir() and (repo / "skills").is_dir():
        return repo
    return _PKG / "recursos"
