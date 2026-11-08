"""video-editores: um comando para todos os scripts do plugin, sem o Claude.

  video-editores listar                       operações e scripts
  video-editores modelos                      backends de IA configurados e dependências
  video-editores <operação> ARGS...           roda o script (com `uv run --with` quando precisa de pacotes)
      [--fundo]  roda em segundo plano e imprime o id da tarefa
      [--direto] usa o Python atual em vez de `uv run`
  video-editores tarefas [ID]                 estado das tarefas em segundo plano
  video-editores mcp [--http PORTA] [--raiz DIR]   servidor MCP (stdio por padrão)

Exemplos:
  video-editores transcrever originais/aula.mp4 --prompt "Python, lista, dicionário"
  VE_DEVICE=cuda video-editores aula-recorte-paralelo trabalho/aula01/aula.json 4
  VE_ENCODER=h264_nvenc video-editores aula-finalizar trabalho/aula01/aula.json saida/aula01.mp4 legendas/aula01.srt
"""
import json
import os
import subprocess
import sys

from . import __version__, modelos
from .nucleo import catalogo


def _listar():
    print(f"video-editores {__version__}  (recursos em {catalogo.raiz_recursos()})\n")
    larg = max(len(n) for n in catalogo.OPERACOES)
    for op in catalogo.OPERACOES.values():
        dep = f"  [{', '.join(op.deps)}]" if op.deps else ""
        print(f"  {op.nome:<{larg}}  {op.resumo}{dep}")
        print(f"  {'':<{larg}}  {op.script} {op.uso}".rstrip())
    print("\nModelos: VE_ASR, VE_SEG, VE_TTS, VE_DEVICE (auto|cpu|cuda), VE_ENCODER (libx264|h264_nvenc|…); `video-editores modelos`.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "ajuda"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd in ("--version", "-V", "versao"):
        print(__version__)
        return 0
    if cmd == "listar":
        _listar()
        return 0
    if cmd == "modelos":
        print(json.dumps(modelos.listar(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "tarefas":
        from .tarefas import Tarefas
        t = Tarefas(os.getcwd())
        print(json.dumps(t.status(args[0]) if args else t.listar(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "mcp":
        from .mcp_server import main as mcp_main
        return mcp_main(args)
    fundo = "--fundo" in args
    direto = "--direto" in args
    args = [a for a in args if a not in ("--fundo", "--direto")]
    try:
        linha = catalogo.comando(cmd, args, direto=direto)
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2
    if fundo:
        from .tarefas import Tarefas
        t = Tarefas(os.getcwd()).iniciar(cmd, linha, env=catalogo.ambiente())
        print(t["id"])
        print(f"log: {t['log']}", file=sys.stderr)
        return 0
    return subprocess.call(linha, env={**os.environ, **catalogo.ambiente()})


if __name__ == "__main__":
    sys.exit(main())
