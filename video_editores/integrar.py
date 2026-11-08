"""Integra o video-editores com outros agentes: Codex (OpenAI), OpenCode e Kiro (AWS).

Para cada agente, três coisas (ADR-12):
  1. skills   as mesmas SKILL.md do plugin, copiadas para a pasta que o agente lê, com `${CLAUDE_PLUGIN_ROOT}`
              trocado pelo caminho real dos scripts e um cabeçalho dizendo como executar fora do Claude Code;
  2. MCP      o servidor video-editores-mcp registrado no formato de configuração do agente;
  3. regras   um bloco em AGENTS.md (Codex, OpenCode) ou um steering (Kiro) com as convenções do projeto.

Escopos: --projeto DIR (padrão: pasta atual) grava dentro do projeto; --usuario grava na configuração global.
Tudo idempotente: rodar de novo atualiza o que é nosso e não toca no resto do arquivo.

Pastas e arquivos (fontes: docs oficiais, nov/2026):
  Codex     skills .agents/skills/ ou ~/.agents/skills/ · MCP .codex/config.toml ou ~/.codex/config.toml [mcp_servers.x] · AGENTS.md
  OpenCode  skills .agents/skills/ (também .opencode/skills/) ou ~/.config/opencode/skills/ · MCP opencode.json mcp.servers.x · AGENTS.md
  Kiro      skills .kiro/skills/ ou ~/.kiro/skills/ (global só na IDE) · MCP .kiro/settings/mcp.json mcpServers.x · .kiro/steering/*.md

Uso: video-editores integrar codex|opencode|kiro|todos [--projeto DIR] [--usuario] [--raiz-midia DIR]
                               [--sem-skills] [--sem-mcp] [--sem-regras] [--remover] [--mostrar]
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import __version__, raiz_recursos

NOME = "video-editores"
AGENTES = ("codex", "opencode", "kiro")
GIT = "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores"
INI, FIM = f"<!-- {NOME}:inicio -->", f"<!-- {NOME}:fim -->"


# ---------------------------------------------------------------- comando do servidor MCP
def _efemero(p) -> bool:
    """Caminho dentro do cache do uv (ambiente de um `uvx`), que pode sumir: não serve para registrar em configuração."""
    s = str(p)
    return "/.cache/uv/" in s or "/archive-v0/" in s or "/uv/cache/" in s


def comando_mcp(raiz_midia: Path) -> list:
    """Como iniciar o servidor MCP nesta máquina: binário instalado (uv tool install) > checkout com uv > uvx do GitHub."""
    raiz_midia = str(raiz_midia)
    bin_ = shutil.which("video-editores-mcp")
    if bin_ and not _efemero(bin_):
        return [bin_, "--raiz", raiz_midia]
    rec = raiz_recursos()
    if (rec / "pyproject.toml").is_file() and shutil.which("uv"):
        return ["uv", "run", "--quiet", "--with", "mcp>=2", "--directory", str(rec), "python", "-m",
                "video_editores.mcp_server", "--raiz", raiz_midia]
    return ["uvx", "--from", GIT, "video-editores-mcp", "--raiz", raiz_midia]


# ---------------------------------------------------------------- skills
CABECALHO = """> **Fora do Claude Code.** Esta skill vem do plugin [video-editores]({repo}) {versao}. Os scripts estão em
> `{raiz}` (os comandos abaixo já apontam para lá). Alternativas equivalentes: a CLI `video-editores <operação>`
> (`video-editores listar`) e as ferramentas do servidor MCP `video-editores` (`listar_operacoes`, `executar_operacao`,
> `tarefa_status`). Onde o texto fala em *subagentes*, execute em sequência ou use o mecanismo de paralelismo do seu
> agente; onde pede *aprovação*, pare e pergunte ao usuário antes de seguir.

"""


def _portar_skill(src: Path, dst: Path, raiz: Path):
    texto = src.read_text(encoding="utf-8")
    texto = texto.replace("${CLAUDE_PLUGIN_ROOT}", str(raiz)).replace("$CLAUDE_PLUGIN_ROOT", str(raiz))
    texto = texto.replace("/video-editores:", "/")  # nomes de slash do plugin não existem nos outros agentes
    m = re.match(r"(---\n.*?\n---\n)", texto, re.S)
    cab = CABECALHO.format(repo="https://github.com/fmnapoli/video-editores", versao=__version__, raiz=raiz)
    texto = (m.group(1) + "\n" + cab + texto[m.end():].lstrip("\n")) if m else cab + texto
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "SKILL.md").write_text(texto, encoding="utf-8")
    for extra in src.parent.iterdir():  # arquivos de referência ao lado do SKILL.md (glossário, references/)
        if extra.name in ("SKILL.md", "scripts", "templates"):
            continue
        if extra.is_dir():
            shutil.copytree(extra, dst / extra.name, dirs_exist_ok=True)
        else:
            shutil.copy2(extra, dst / extra.name)


def exportar_skills(dest: Path, remover=False) -> list:
    """Copia todas as skills do plugin para `dest/<nome>/SKILL.md`. Devolve os nomes."""
    raiz = raiz_recursos()
    nomes = []
    for sk in sorted((raiz / "skills").glob("*/SKILL.md")):
        nome = sk.parent.name
        alvo = dest / nome
        if remover:
            if alvo.is_dir() and (alvo / "SKILL.md").exists():
                shutil.rmtree(alvo)
        else:
            _portar_skill(sk, alvo, raiz)
        nomes.append(nome)
    return nomes


# ---------------------------------------------------------------- regras (AGENTS.md / steering)
def texto_regras(raiz_midia: Path, agente: str) -> str:
    chamada = {"codex": "`$nome-da-skill` ou /skills", "opencode": "`@nome-da-skill`", "kiro": "pela descrição ou `#`"}[agente]
    return f"""## video-editores (edição de vídeo por IA local)

- Projeto de vídeo em `{raiz_midia}`: `originais/` é imutável, intermediários em `trabalho/<slug>/`, entregas em `saida/`, legendas em `legendas/`.
- Skills do plugin instaladas neste agente ({chamada}): corte, legenda, lettering, tomada, destaques, trilha, efeitos, prova, tela-verde, texto-atras, animacao, video-docs, video-animado, videoaula e outras; `editar` é a entrada em linguagem natural.
- Execução: scripts chamados pelas skills, ou `video-editores <operação>` (`video-editores listar`), ou as ferramentas do servidor MCP `video-editores` (operações longas devolvem um id; acompanhe com `tarefa_status`).
- Pare para aprovação antes de descartar tomadas, queimar legenda, render longo e entrega (gates das skills). Texto na tela sempre em ASS, nunca `drawtext`. Áudio final a −14 LUFS.
- Modelos de IA e GPU por variáveis: `VE_DEVICE=cuda`, `VE_ENCODER=h264_nvenc`, `VE_ASR`/`VE_SEG`/`VE_TTS`. Documentação: https://github.com/fmnapoli/video-editores (docs/nucleo.md, docs/agentes.md).
"""


def gravar_bloco(arq: Path, bloco: str, remover=False, frontmatter: str = ""):
    """Insere/atualiza o bloco marcado em `arq`, preservando o resto do arquivo."""
    atual = arq.read_text(encoding="utf-8") if arq.is_file() else ""
    padrao = re.compile(re.escape(INI) + r".*?" + re.escape(FIM) + r"\n?", re.S)
    novo = padrao.sub("", atual)
    if not remover:
        novo = (novo.rstrip("\n") + "\n\n" if novo.strip() else frontmatter) + f"{INI}\n{bloco}{FIM}\n"
    if novo.strip() and novo.strip() != frontmatter.strip():
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(novo, encoding="utf-8")
    elif arq.is_file():
        arq.unlink()


# ---------------------------------------------------------------- MCP por agente
def _json_rw(arq: Path, muda):
    dados = json.loads(arq.read_text(encoding="utf-8")) if arq.is_file() and arq.read_text(encoding="utf-8").strip() else {}
    muda(dados)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mcp_opencode(arq: Path, cmd: list, remover=False):
    def muda(d):
        srv = d.setdefault("mcp", {}).setdefault("servers", {})
        if remover:
            srv.pop(NOME, None)
        else:
            srv[NOME] = {"type": "local", "command": cmd, "timeout": {"startup": 120000, "execution": 7200000}}
    _json_rw(arq, muda)


def mcp_kiro(arq: Path, cmd: list, remover=False):
    def muda(d):
        srv = d.setdefault("mcpServers", {})
        if remover:
            srv.pop(NOME, None)
        else:
            srv[NOME] = {"command": cmd[0], "args": cmd[1:], "disabled": False,
                         "autoApprove": ["listar_operacoes", "listar_modelos", "tarefa_status", "tarefas_listar", "versao", "ler_texto"]}
    _json_rw(arq, muda)


def _toml_str(s):
    return json.dumps(s, ensure_ascii=False)  # strings TOML básicas aceitam a mesma escape do JSON


def mcp_codex(arq: Path, cmd: list, remover=False):
    """Edita só a tabela [mcp_servers.video-editores] do config.toml; o resto do arquivo fica como está."""
    atual = arq.read_text(encoding="utf-8") if arq.is_file() else ""
    padrao = re.compile(rf'^\[mcp_servers\."?{re.escape(NOME)}"?(\.[^\]]+)?\]\n(?:(?!^\[).*\n?)*', re.M)
    novo = padrao.sub("", atual).rstrip("\n")
    if not remover:
        bloco = (f'[mcp_servers."{NOME}"]\ncommand = {_toml_str(cmd[0])}\nargs = [{", ".join(_toml_str(a) for a in cmd[1:])}]\n'
                 f"startup_timeout_sec = 120\ntool_timeout_sec = 7200\n")
        novo = (novo + "\n\n" if novo else "") + bloco
    if novo.strip():
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(novo.rstrip("\n") + "\n", encoding="utf-8")
    elif arq.is_file():
        arq.unlink()


# ---------------------------------------------------------------- alvos por agente e escopo
def alvos(agente: str, projeto: Path, usuario: bool) -> dict:
    home = Path.home()
    if agente == "codex":
        return {"skills": home / ".agents/skills" if usuario else projeto / ".agents/skills",
                "mcp": home / ".codex/config.toml" if usuario else projeto / ".codex/config.toml",
                "regras": None if usuario else projeto / "AGENTS.md"}
    if agente == "opencode":
        return {"skills": home / ".config/opencode/skills" if usuario else projeto / ".agents/skills",
                "mcp": home / ".config/opencode/opencode.json" if usuario else projeto / "opencode.json",
                "regras": home / ".config/opencode/AGENTS.md" if usuario else projeto / "AGENTS.md"}
    if agente == "kiro":
        return {"skills": home / ".kiro/skills" if usuario else projeto / ".kiro/skills",
                "mcp": home / ".kiro/settings/mcp.json" if usuario else projeto / ".kiro/settings/mcp.json",
                "regras": home / ".kiro/steering" / f"{NOME}.md" if usuario else projeto / ".kiro/steering" / f"{NOME}.md"}
    raise KeyError(agente)


def integrar(agente, projeto, usuario=False, raiz_midia=None, skills=True, mcp=True, regras=True, remover=False, mostrar=False) -> list:
    projeto = Path(projeto).resolve()
    raiz_midia = Path(raiz_midia or projeto).resolve()
    a = alvos(agente, projeto, usuario)
    cmd = comando_mcp(raiz_midia)
    feito = []
    if _efemero(raiz_recursos()):
        feito.append("aviso: rodando de um ambiente efêmero do uvx; os caminhos dos scripts nas skills podem sumir. "
                     "Instale com `uv tool install \"video-editores @ git+https://github.com/fmnapoli/video-editores\"` e rode de novo.")
    if mostrar:
        return [f"{agente}: skills → {a['skills']}", f"{agente}: MCP → {a['mcp']}  cmd: {' '.join(cmd)}",
                f"{agente}: regras → {a['regras'] or '(sem regras no escopo de usuário deste agente)'}"]
    if skills:
        nomes = exportar_skills(a["skills"], remover)
        feito.append(f"{agente}: {'removidas' if remover else 'instaladas'} {len(nomes)} skills em {a['skills']}")
        if agente == "kiro" and usuario:
            feito.append("kiro: skills globais valem só na IDE; na CLI do Kiro use --projeto")
    if mcp:
        {"codex": mcp_codex, "opencode": mcp_opencode, "kiro": mcp_kiro}[agente](a["mcp"], cmd, remover)
        feito.append(f"{agente}: servidor MCP {'removido de' if remover else 'registrado em'} {a['mcp']}")
    if regras and a["regras"]:
        fm = "---\ninclusion: always\n---\n\n" if agente == "kiro" else ""
        gravar_bloco(a["regras"], texto_regras(raiz_midia, agente), remover, frontmatter=fm)
        feito.append(f"{agente}: regras {'removidas de' if remover else 'gravadas em'} {a['regras']}")
    return feito


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("agente", choices=AGENTES + ("todos",))
    ap.add_argument("--projeto", default=os.getcwd(), help="pasta do projeto onde gravar (padrão: atual)")
    ap.add_argument("--usuario", action="store_true", help="grava na configuração global do agente em vez do projeto")
    ap.add_argument("--raiz-midia", default=None, help="raiz dos vídeos para o servidor MCP (padrão: --projeto)")
    ap.add_argument("--sem-skills", action="store_true"); ap.add_argument("--sem-mcp", action="store_true")
    ap.add_argument("--sem-regras", action="store_true")
    ap.add_argument("--remover", action="store_true", help="desfaz a integração (só o que é nosso)")
    ap.add_argument("--mostrar", action="store_true", help="só mostra onde gravaria")
    a = ap.parse_args(argv)
    for ag in (AGENTES if a.agente == "todos" else (a.agente,)):
        for linha in integrar(ag, a.projeto, a.usuario, a.raiz_midia, not a.sem_skills, not a.sem_mcp, not a.sem_regras, a.remover, a.mostrar):
            print(linha)
    if not a.mostrar and not a.remover:
        print("Reinicie o agente para ele recarregar skills e servidores MCP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
