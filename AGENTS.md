# video-editores

Plugin de edição de vídeo por IA local: 21 skills (`skills/*/SKILL.md`), scripts determinísticos (`scripts/`,
`skills/*/scripts/`) e o núcleo `video_editores/` (modelos trocáveis, catálogo, CLI, tarefas, servidor MCP,
integração com outros agentes). Arquitetura e ADRs em `docs/arquitetura.md`; convenções em `docs/convencoes.md`;
como contribuir em `CONTRIBUTING.md`.

- Testes: `make test` (smoke + núcleo), `bash tests/docs_offline.sh`; lint: `make lint` (shellcheck + ruff).
- Scripts novos entram no catálogo (`video_editores/nucleo/catalogo.py`); modelos de IA só via `video_editores.modelos`.
- Texto na tela sempre em ASS (nunca `drawtext`); dependências Python via `uv run --with`, nunca `pip install` global.
- Versão em três lugares: `pyproject.toml`, `video_editores/__init__.py`, `.claude-plugin/plugin.json`; registre em `CHANGELOG.md`.
