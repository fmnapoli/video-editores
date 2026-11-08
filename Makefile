.PHONY: test lint doctor docs-example

test:            ## teste de fumaça (ffmpeg + python3)
	bash tests/smoke.sh

lint:            ## shellcheck + ruff (falha se houver erro)
	@if command -v shellcheck >/dev/null; then shellcheck -S warning scripts/*.sh tests/*.sh exemplos/video-docs/*.sh skills/videoaula/scripts/*.sh; else echo "shellcheck ausente, pulando"; fi
	@if command -v ruff >/dev/null; then ruff check scripts skills/video-docs/scripts skills/video-animado/scripts skills/videoaula/scripts tests; \
	 elif command -v uvx >/dev/null; then uvx ruff check scripts skills/video-docs/scripts skills/video-animado/scripts skills/videoaula/scripts tests; \
	 else echo "ruff ausente, pulando"; fi

doctor:          ## verifica dependências
	bash scripts/doctor.sh

docs-example:    ## roda o exemplo do video-docs (precisa de internet para o edge-tts)
	cd exemplos/video-docs && ./gerar-bruto.sh && ../../scripts/render-docs.sh spec.json
