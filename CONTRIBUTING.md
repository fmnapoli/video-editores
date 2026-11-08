# Contribuindo

## Ambiente
```bash
git clone https://github.com/fmnapoli/video-editores && cd video-editores
make doctor   # dependências
make test     # smoke
make lint     # shellcheck + ruff
```

## Novo skill
1. Crie `skills/<nome>/SKILL.md`, com nome curto em kebab-case, sem acento.
2. Frontmatter obrigatório:
   ```yaml
   ---
   name: <nome>
   description: <o que faz> + <quando usar, com as frases que o usuário diria>. Use para /<nome>, "...", "...".
   ---
   ```
   O `description` decide quando o Claude aciona o skill sozinho: inclua os gatilhos em português.
3. Logo depois do título, a linha padrão apontando para `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` e o `doctor.sh`.
4. Estrutura do corpo: **Passos** numerados → **Ajustes/Parâmetros** → **Regras**. Instruções no imperativo.
5. Caminhos para scripts sempre como `"${CLAUDE_PLUGIN_ROOT}/scripts/<script>"`.
6. Gate humano antes de qualquer passo destrutivo, caro ou demorado.
7. Documente o skill em `docs/skills.md` e adicione uma linha no README.

## Novo script
- Lógica determinística vai para script, não para o texto do skill.
- Python: `argparse`, docstring com o uso, só biblioteca padrão quando der; dependências via `uv run --with` (nunca `pip install` global).
- Bash: `set -euo pipefail`, sem warnings do shellcheck.
- Nunca sobrescreva a entrada. Saída com sufixo da etapa.
- Texto na tela só em ASS (sem `drawtext`).
- Cubra o script no `tests/smoke.sh` se ele não depender de modelo de IA.
- Documente em `docs/scripts.md`.

## Licenças
Só dependências com licença compatível com uso comercial do plugin (MIT/BSD/Apache/Unlicense/LGPL como executável). Ferramenta com restrição (ex.: pesos CC-BY-NC) só como opcional e com aviso explícito no skill e em `docs/convencoes.md`.

## Versão
SemVer em `.claude-plugin/plugin.json` e entrada no `CHANGELOG.md`. Commits no formato Conventional Commits (`feat:`, `fix:`, `docs:`).
