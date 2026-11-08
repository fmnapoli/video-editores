"""Servidor MCP do video-editores: as operações do catálogo como ferramentas, com tarefas em segundo plano.

É um invólucro fino (ADR-11): não contém lógica de edição, só expõe os mesmos scripts da CLI a qualquer
cliente MCP (Claude Code, Claude Desktop, agentes internos). O conhecimento de *como* editar (gates,
decisões de design) continua nas skills, que podem orientar o cliente a usar estas ferramentas.

Uso:
  uvx --from "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores" video-editores-mcp [--raiz DIR]
  video-editores-mcp --http 3001 --raiz /dados/projetos      # streamable HTTP, para rodar numa máquina com GPU

Segurança: todo caminho passado às ferramentas precisa estar dentro de --raiz (padrão: pasta atual).
Processos longos nascem em sessão própria e sobrevivem à desconexão do cliente.
"""
import argparse
import os
import shlex
from typing import Any
from pathlib import Path

from . import __version__, modelos
from .nucleo import catalogo
from .tarefas import Tarefas

try:
    from mcp.server import MCPServer
except ImportError:  # pragma: no cover
    MCPServer = None


def criar_servidor(raiz=None):
    if MCPServer is None:
        raise SystemExit("pacote mcp>=2 não instalado: uvx --from 'video-editores[mcp]' video-editores-mcp")
    raiz = Path(raiz or os.getcwd()).resolve()
    tarefas = Tarefas(raiz)
    srv = MCPServer("video-editores", instructions=(
        "Edição de vídeo local por scripts (ffmpeg, faster-whisper, rembg, Manim). Caminhos são relativos à raiz do "
        f"projeto ({raiz}); use as convenções originais/ (imutável), trabalho/<slug>/ e saida/. Operações longas "
        "devolvem um id de tarefa: acompanhe com tarefa_status. Peça aprovação humana antes de render longo e entrega."))

    def _dentro(p):
        q = (raiz / p).resolve() if not os.path.isabs(p) else Path(p).resolve()
        if raiz != q and raiz not in q.parents:
            raise ValueError(f"caminho fora da raiz {raiz}: {p}")
        return q

    def _valida_args(args):
        # Qualquer argumento que pareça caminho existente ou de saída dentro do projeto tem que ficar na raiz.
        for a in args:
            if a.startswith("-"):
                continue
            if "/" in a or a.endswith((".mp4", ".mov", ".json", ".srt", ".png", ".jpg", ".wav", ".mp3", ".py", ".csv")):
                if os.path.isabs(a) or a.startswith(".."):
                    _dentro(a)

    def _rodar(nome, args, aguardar, timeout):
        op = catalogo.operacao(nome)
        _valida_args(args)
        linha = catalogo.comando(nome, args, device=modelos.device())
        t = tarefas.iniciar(nome, linha, cwd=raiz, env=catalogo.ambiente())
        if aguardar or not op.longa:
            t = tarefas.esperar(t["id"], timeout=timeout)
        return {k: t.get(k) for k in ("id", "nome", "estado", "rc", "decorrido_s", "log", "log_fim")} | {"cmd": shlex.join(linha)}

    @srv.tool()
    def listar_operacoes() -> list[dict[str, Any]]:
        """Lista as operações disponíveis (nome, resumo, uso, dependências de modelo, se é longa, saídas)."""
        return [{"nome": o.nome, "resumo": o.resumo, "uso": o.uso, "deps": list(o.deps), "longa": o.longa,
                 "skill": o.skill, "saidas": list(o.saidas)} for o in catalogo.OPERACOES.values()]

    @srv.tool()
    def listar_modelos() -> dict[str, Any]:
        """Backends de IA configurados (ASR, segmentação, TTS), dispositivo efetivo e dependências de cada um."""
        return modelos.listar()

    @srv.tool()
    def executar_operacao(operacao: str, argumentos: list[str], aguardar: bool = False, timeout_s: float = 600) -> dict[str, Any]:
        """Executa uma operação do catálogo com os argumentos exatamente como na CLI do script
        (ex.: operacao="lettering", argumentos=["trabalho/x/corte.mp4", "trabalho/x/textos.json", "--burn", "trabalho/x/lett.mp4"]).
        Operações curtas rodam e devolvem o resultado; longas voltam com estado "rodando" e um id para tarefa_status,
        a menos que aguardar=True (até timeout_s)."""
        return _rodar(operacao, argumentos, aguardar, timeout_s)

    @srv.tool()
    def transcrever(video: str, vocabulario: str = "", modelo: str = "medium", idioma: str = "pt",
                    pasta_saida: str = "", aguardar: bool = False) -> dict[str, Any]:
        """Transcreve um vídeo com timestamps por palavra (gera .transcript.json, .srt e .words.srt).
        vocabulario: termos do domínio para o initial_prompt (reduz erros em nomes técnicos)."""
        args = [video, "--model", modelo, "--lang", idioma]
        if vocabulario:
            args += ["--prompt", vocabulario]
        if pasta_saida:
            args += ["--out-dir", pasta_saida]
        return _rodar("transcrever", args, aguardar, 3600)

    @srv.tool()
    def recortar_pessoa(video: str, inicio: float, fim: float, fundo_png: str, saida_base: str,
                        threads: int = 4, modelo: str = "u2net_human_seg", aguardar: bool = False) -> dict[str, Any]:
        """Recorta a pessoa por IA (sem tela verde) no trecho [inicio, fim] e compõe sobre fundo_png com sombra.
        Gera saida_base.mp4 e saida_base_alpha.mp4. Lento em CPU (~1-3 s/frame); com GPU configure VE_DEVICE=cuda."""
        args = [video, str(inicio), str(fim), fundo_png, saida_base, "--threads", str(threads), "--model", modelo]
        return _rodar("aula-recorte", args, aguardar, 7200)

    @srv.tool()
    def lettering(video: str, textos_json: str, saida: str = "", fonte: str = "") -> dict[str, Any]:
        """Textos na tela via ASS (títulos, lower third, destaque, cartão, capa). Sem saida só gera o .ass."""
        args = [video, textos_json]
        if fonte:
            args += ["--font", fonte]
        if saida:
            args += ["--burn", saida]
        return _rodar("lettering", args, True, 1800)

    @srv.tool()
    def prova(video: str, quadros: int = 12) -> dict[str, Any]:
        """Material de aprovação: folha de contato (.proof.jpg), preview leve (.preview.mp4) e relatório com loudness (.proof.txt)."""
        return _rodar("prova", [video, str(quadros)], True, 1800)

    @srv.tool()
    def videoaula_montar(aula_json: str, etapa: str, saida: str = "", jobs: int = 2, ate: float = 0, aguardar: bool = False) -> dict[str, Any]:
        """Montagem da videoaula redesenhada a partir de aula.json. etapa: "edl" (lista de blocos), "render" (blocos em paralelo),
        "concat" (vídeo + áudio contínuo em `saida`). ate>0 limita ao tempo T do corte (piloto)."""
        args = [aula_json, etapa]
        if etapa == "concat":
            args.append(saida or "trabalho/_montado.mp4")
        if etapa == "render":
            args += ["--jobs", str(jobs)]
        if ate > 0:
            args += ["--ate", str(ate)]
        return _rodar("aula-montar", args, aguardar or etapa == "edl", 7200)

    @srv.tool()
    def videoaula_finalizar(aula_json: str, saida_mp4: str, saida_srt: str, textos_json: str = "", ajustes_json: str = "",
                            jobs: int = 2, limpar_audio: bool = False, aguardar: bool = False) -> dict[str, Any]:
        """Entrega da videoaula: render + concat + lettering + loudnorm (-14 LUFS) + SRT. Peça aprovação do piloto antes."""
        args = [aula_json, saida_mp4, saida_srt, "--jobs", str(jobs)]
        if textos_json:
            args += ["--textos", textos_json]
        if ajustes_json:
            args += ["--ajustes", ajustes_json]
        if limpar_audio:
            args.append("--limpar-audio")
        return _rodar("aula-finalizar", args, aguardar, 7200)

    @srv.tool()
    def tarefa_status(id: str) -> dict[str, Any]:
        """Estado de uma tarefa em segundo plano (rodando|ok|erro|cancelada), tempo decorrido e fim do log."""
        return tarefas.status(id)

    @srv.tool()
    def tarefa_esperar(id: str, timeout_s: float = 300) -> dict[str, Any]:
        """Bloqueia até a tarefa terminar ou até timeout_s; devolve o mesmo que tarefa_status."""
        return tarefas.esperar(id, timeout=timeout_s)

    @srv.tool()
    def tarefa_cancelar(id: str) -> dict[str, Any]:
        """Interrompe uma tarefa em segundo plano (SIGTERM no grupo de processos)."""
        return tarefas.cancelar(id)

    @srv.tool()
    def tarefas_listar(n: int = 20) -> list[dict[str, Any]]:
        """Últimas tarefas deste projeto."""
        return tarefas.listar(n)

    @srv.tool()
    def ler_texto(caminho: str, max_bytes: int = 200_000) -> str:
        """Lê um arquivo de texto do projeto (transcrição, JSON, SRT, relatório de prova). Só dentro da raiz."""
        p = _dentro(caminho)
        return p.read_text(encoding="utf-8", errors="replace")[:max_bytes]

    @srv.tool()
    def versao() -> dict[str, Any]:
        """Versão do núcleo, raiz do projeto e pasta de recursos (scripts)."""
        return {"video_editores": __version__, "raiz": str(raiz), "recursos": str(catalogo.raiz_recursos()),
                "device": modelos.device(), "encoder": os.environ.get("VE_ENCODER", "libx264")}

    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description="Servidor MCP do video-editores")
    ap.add_argument("--raiz", default=os.getcwd(), help="pasta do projeto; caminhos fora dela são recusados")
    ap.add_argument("--http", type=int, default=0, metavar="PORTA", help="streamable HTTP nesta porta (padrão: stdio)")
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    srv = criar_servidor(a.raiz)
    if a.http:
        srv.run(transport="streamable-http", host=a.host, port=a.http)
    else:
        srv.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
