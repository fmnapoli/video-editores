.PHONY: test lint doctor docs-example

test:            ## versão + teste de fumaça (ffmpeg + python3) + núcleo (CLI, modelos, tarefas, MCP) + partitura (uv)
	bash tests/versao.sh
	bash tests/smoke.sh
	bash tests/nucleo.sh
	bash tests/partitura.sh

lint:            ## shellcheck + ruff (falha se houver erro)
	@if command -v shellcheck >/dev/null; then shellcheck -S warning scripts/*.sh tests/*.sh exemplos/video-docs/*.sh skills/videoaula/scripts/*.sh; else echo "shellcheck ausente, pulando"; fi
	@if command -v ruff >/dev/null; then ruff check video_editores scripts skills/video-docs/scripts skills/video-animado/scripts skills/videoaula/scripts skills/partitura/scripts tests; \
	 elif command -v uvx >/dev/null; then uvx ruff check video_editores scripts skills/video-docs/scripts skills/video-animado/scripts skills/videoaula/scripts skills/partitura/scripts tests; \
	 else echo "ruff ausente, pulando"; fi

doctor:          ## verifica dependências
	bash scripts/doctor.sh

docs-example:    ## roda o exemplo do video-docs (precisa de internet para o edge-tts)
	cd exemplos/video-docs && ./gerar-bruto.sh && ../../scripts/render-docs.sh spec.json
