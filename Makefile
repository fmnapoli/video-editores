.PHONY: test lint doctor docs-example

test:            ## teste de fumaça (ffmpeg + python3)
	bash tests/smoke.sh

lint:            ## shellcheck + ruff, se instalados
	@command -v shellcheck >/dev/null && shellcheck -S warning scripts/*.sh tests/*.sh || echo "shellcheck ausente, pulando"
	@command -v ruff >/dev/null && ruff check scripts skills/video-docs/scripts || echo "ruff ausente ou com erros"

doctor:          ## verifica dependências
	bash scripts/doctor.sh

docs-example:    ## roda o exemplo do video-docs (precisa de internet para o edge-tts)
	cd exemplos/video-docs && ./gerar-bruto.sh && ../../scripts/render-docs.sh spec.json
