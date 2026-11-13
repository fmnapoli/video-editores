# Codex, OpenCode, Kiro e ZCode

As skills do plugin são Markdown com frontmatter (`SKILL.md`), o formato que os agentes de código convergiram a ler
(padrão Agent Skills). O que muda entre eles é **onde** leem skills, **como** registram servidores MCP e **onde**
ficam as regras do projeto. `video-editores integrar` cuida das três coisas:

```bash
uv tool install "video-editores @ git+https://github.com/fmnapoli/video-editores"   # ou use o checkout com PYTHONPATH
cd /caminho/do/projeto-de-video
video-editores integrar todos            # codex | opencode | kiro | zcode | todos
video-editores integrar codex --usuario  # configuração global do agente em vez do projeto
video-editores integrar todos --mostrar  # mostra onde gravaria e se o que está instalado está desatualizado
video-editores integrar todos --remover  # desfaz (só o que é nosso)
```

Depois, reinicie o agente. As skills aparecem com os mesmos nomes do plugin (`videoaula`, `corte`, `legenda`, …);
`editar` continua sendo a entrada em linguagem natural.

## O que é gravado

| | Codex | OpenCode | Kiro | ZCode |
|---|---|---|---|---|
| Skills (projeto) | `.agents/skills/<nome>/SKILL.md` | `.agents/skills/` (também lê `.opencode/skills/` e `.claude/skills/`) | `.kiro/skills/<nome>/SKILL.md` | `.agents/skills/<nome>/SKILL.md` (a mesma pasta de Codex/OpenCode) |
| Skills (usuário) | `~/.agents/skills/` | `~/.config/opencode/skills/` | `~/.kiro/skills/` (só a IDE lê; a CLI do Kiro só lê o projeto) | `~/.zcode/skills/` |
| MCP (projeto) | `.codex/config.toml` → `[mcp_servers."video-editores"]` (projeto precisa ser confiável) | `opencode.json` → `mcp.servers.video-editores` (`type: local`, `command: [...]`) | `.kiro/settings/mcp.json` → `mcpServers.video-editores` (`command`, `args`, `autoApprove`) | — (o ZCode só registra MCP global; use `--usuario`) |
| MCP (usuário) | `~/.codex/config.toml` | `~/.config/opencode/opencode.json` | `~/.kiro/settings/mcp.json` | `~/.zcode/cli/config.json` → `mcp.servers.video-editores` (`type: stdio`, `command`, `args`, `enabled`) |
| Regras | bloco em `AGENTS.md` | bloco em `AGENTS.md` (ou `~/.config/opencode/AGENTS.md`) | `.kiro/steering/video-editores.md` com `inclusion: always` (a CLI do Kiro também lê `AGENTS.md`) | bloco em `AGENTS.md` do projeto (sem regras globais conhecidas) |
| Invocar skill | `$nome` ou `/skills`; implícito pela descrição | `@nome`; implícito pela descrição | implícito pela descrição; `#` para steering manual | pela descrição ou pedindo `use a skill <nome>` |

Codex, OpenCode e ZCode compartilham `.agents/skills/` em projeto, então o mesmo projeto serve aos três. Em
`AGENTS.md` e no steering o bloco fica entre `<!-- video-editores:inicio -->` e `<!-- video-editores:fim -->`; o
resto do arquivo é preservado. No `config.toml` do Codex só a tabela do servidor é reescrita; nos JSONs, só a chave
do servidor.

## Antideriva: port desatualizado é detectável

Toda portação carimba a versão (`<!-- video-editores:port X.Y.Z -->` na primeira linha após o frontmatter) e cada
destino recebe um manifesto oculto `.video-editores.json` (versão, agente, escopo, raiz, skills). `integrar
--mostrar` compara o instalado com a versão atual e acusa `DESATUALIZADO` com o comando de correção — lendo o
manifesto ou o carimbo, então portações feitas à mão de versões antigas também são reconhecidas. `make doctor`
faz a mesma checagem nas pastas globais (seção "Integração"). Sobrescrever e remover só toca em portação do
plugin: pasta homônima que não é do plugin é preservada e relatada.

## O que muda na skill portada

A cópia é a SKILL.md do plugin com três ajustes:

1. `${CLAUDE_PLUGIN_ROOT}` vira o caminho real dos scripts (o checkout ou `…/site-packages/video_editores/recursos`),
   então os comandos `uv run --with … python <script>` funcionam como estão;
2. um cabeçalho explica as alternativas (`video-editores <operação>`, ferramentas MCP) e o que fazer com o que é do
   Claude Code: onde a skill fala em **subagentes**, executar em sequência ou usar o paralelismo do próprio agente;
   onde pede **aprovação**, parar e perguntar. O cabeçalho pode variar por agente (registro de `integrar.py`); no
   ZCode ele mapeia as ferramentas do harness — subagentes → **Agent**, aprovação → **AskUserQuestion**;
3. referências `/video-editores:skill` viram `/skill`.

Arquivos de referência ao lado da skill (glossário do video-docs, `references/`) vão junto. `scripts/` e `templates/`
não são copiados: continuam no caminho real, que é para onde a skill aponta.

## Servidor MCP

O comando registrado é escolhido nesta ordem: `video-editores-mcp` no PATH (instalado por `uv tool install`),
`uv run --with mcp>=2 --directory <checkout> python -m video_editores.mcp_server` quando se roda do repositório, ou
`uvx --from "video-editores[mcp] @ git+…" video-editores-mcp`. Sempre com `--raiz` apontando para o projeto
(`--raiz-midia` muda), porque o servidor recusa caminhos fora dela. Timeouts de ferramenta são longos (2 h) por causa
do recorte por IA e dos renders; em Kiro as ferramentas de leitura (`listar_*`, `tarefa_status`, `versao`, `ler_texto`)
entram em `autoApprove`.

No ZCode o registro mora em `~/.zcode/cli/config.json`, arquivo gerenciado pelo próprio app: o writer faz
read-modify-write preservando o resto, mas reescrever config com o app aberto sujeita-se a last-writer-wins (rodar
`integrar` de novo repara). O schema é estrito — chave desconhecida faz o servidor ser descartado sem aviso, então o
registro usa só os campos documentados (`type`, `command`, `args`, `enabled`).

## Limitações conhecidas

- Os gates humanos dependem de o agente obedecer ao texto ("pare e pergunte"); no Claude Code e no ZCode isso é uma
  ferramenta de pergunta, nos outros é instrução.
- Paralelismo por subagentes (`/videoaula`, `/animacao`) vira sequência, a menos que o agente tenha o próprio
  mecanismo (no ZCode, a ferramenta Agent); o paralelismo por processos (`matte_workers.sh`, `render_cenas.sh -j`,
  `--jobs`) funciona igual.
- Codex só carrega `.codex/config.toml` em projetos marcados como confiáveis; sem isso use `--usuario`.
- Kiro CLI não lê skills globais; use o escopo de projeto.
- ZCode: sem registro de MCP por projeto (só global, com `--usuario`) e sem arquivo de regras global conhecido.
- As pastas e chaves acima são as documentadas/observadas em novembro de 2026 (Codex: learn.chatgpt.com/docs,
  OpenCode: docs.opencode.ai, Kiro: kiro.dev/docs; ZCode: caminhos observados na prática, sem documentação pública
  citável). Se um agente mudar o formato, o ajuste fica no registro e nos writers de
  `video_editores/integrar.py`.
