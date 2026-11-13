# ADR-18 — Integração com o ZCode e antideriva das portações (`integrar`)

**Data:** 2026-11-13 · **Estado:** aprovado; implementado na 0.14.0

## Contexto

O ADR-12 disse que "uma segunda cópia editada à mão divergiria em semanas" — e foi exatamente o que aconteceu fora
do alcance dos três alvos: um usuário portou as skills à mão para o harness ZCode (desktop z.ai, skills em
`~/.zcode/skills/<nome>/SKILL.md`). Quatro releases depois, as 21 portações continuavam carimbadas na v0.9.2
apontando para um checkout fixo do plugin na mesma versão antiga: sem `/marca` (0.12.0), sem identidade visual
(0.11–0.12), sem o fail-fast de TTS do `/video-docs` (0.10.0). Nada no plugin detecta esse modo de falha — o
carimbo de versão do cabeçalho é prosa que nenhum código lê.

Do lado do ZCode, a integração em escopo de projeto já existia de graça: o agente lê `.agents/skills/` (o mesmo
caminho que os alvos Codex/OpenCode escrevem) e `AGENTS.md`. O que faltava eram duas coisas: skills de usuário
(`~/.zcode/skills/`) e o registro do servidor MCP (`~/.zcode/cli/config.json`, chave `mcp.servers`, formato
`{type: "stdio", command, args, enabled}` — só escopo global; schema estrito, chave desconhecida descarta o
servidor sem aviso). Outra descoberta do port manual: o cabeçalho genérico "execute em sequência ou use o
mecanismo de paralelismo do seu agente" rende pouco; o texto que funciona mapeia os conceitos do Claude Code
para as ferramentas do harness (subagentes → ferramenta *Agent*, aprovação → *AskUserQuestion*), e o modelo do
harness obedece.

## Decisão proposta

1. **`video-editores integrar zcode`** como 4º alvo, via o registro de dados de `integrar.py` (um alvo é uma
   entrada, não um ramo de `if`): skills de usuário em `~/.zcode/skills/`, MCP global em
   `~/.zcode/cli/config.json` (sem campo inventado — o schema é estrito), regras em `AGENTS.md` em projeto e
   `None` no escopo de usuário (não há arquivo de regras global conhecido). Em projeto, o alvo reaproveita
   `.agents/skills/` em vez de criar `zcode/skills/` de projeto — segunda cópia divergente é o que o ADR-12 proíbe.
2. **Cabeçalho por agente**: o registro permite sobrecarregar o cabeçalho padrão; a variante ZCode traz o
   mapeamento de ferramentas (Agent/AskUserQuestion) provado pelo port manual.
3. **Antideriva para os quatro alvos**, atacando o modo de falha que motivou o ADR:
   - todo port carimba a versão: `<!-- video-editores:port X.Y.Z -->` logo após o frontmatter;
   - cada destino ganha um manifesto oculto `.video-editores.json` (versão, agente, escopo, raiz, skills);
   - `integrar --mostrar` compara o instalado com a versão atual e acusa `DESATUALIZADO` com o comando de
     correção, lendo manifesto ou carimbo (reconhece ports feitos à mão);
   - `doctor.sh` ganha a seção "Integração", com a mesma checagem nas pastas globais.
4. **Guarda de procedência**: sobrescrever e remover só toca em portação do plugin (carimbo novo ou cabeçalho
   antigo reconhecido); pasta homônima alheia é preservada e relatada — relevante porque `~/.zcode/skills/`
   convive com skills de outros plugins e nomes genéricos (`checklist` existe nos dois mundos). Falha em uma
   skill não derruba o relatório e o comando sai com erro.

## Alternativas pesadas

- **Só documentar a receita** ("o ZCode lê `~/.zcode/skills`; copie as skills") — resolve o snapshot, não o
  drift nem o upgrade; as 21 portações manuais são a prova.
- **Consumir o plugin como marketplace Claude dentro do ZCode** — o ZCode carrega plugins no formato
  `.claude-plugin` de marketplaces Claude, o que daria upgrade nativo sem portar. Caminho futuro legítimo, mas
  não validado end-to-end, não cobre o cabeçalho adaptado ao harness e deixa de fora o MCP da CLI. Reavaliar
  quando o ZCode documentar o suporte.
- **`mcp_zcode` espelhando o do Kiro com `autoApprove`** — rejeitado: o formato do ZCode não tem esse campo e o
  schema descarta o servidor com chave desconhecida.
- **Manter o alvo só no fork** — rejeitado: a antideriva e a guarda de procedência beneficiam os três alvos
  existentes e valem por si num PR upstream.

## Consequências

- Cada alvo novo de integração é uma entrada de dados (caminhos, writer MCP, cabeçalho, invocação) e uma linha
  de teste; os formatos seguem os observados em nov/2026 — o ZCode não tem documentação pública citável para os
  caminhos usados, então o ajuste futuro morre em `REGISTRO`/`mcp_zcode`, como nos outros três.
- `~/.zcode/cli/config.json` é gerenciado pelo próprio app; o writer faz read-modify-write cirúrgico e preserva
  o resto, mas quem editar config com o app aberto sujeita-se a last-writer-wins (rodar `integrar` de novo
  repara).
- A migração das portações manuais antigas é uma rodada do próprio comando: `integrar zcode --usuario`
  sobrescreve as 21 (carimbo reconhecido como nosso), instala a 22ª (`/marca`) e grava o manifesto; o
  `--remover` delas passa a ser reversível.
