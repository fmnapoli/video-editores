---
name: tomada
description: Encontra tomadas repetidas (quando a pessoa errou e regravou a frase) e mantém só a melhor de cada, montando o vídeo limpo. Use para /tomada, "tira os erros", "deixa só as tomadas boas", "remove as repetições".
---

# /tomada — seleção de melhores tomadas

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.


## Passos
1. Transcreva (gera `.transcript.json`, `.srt`, `.words.srt`):
   ```bash
   uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" "IN.mp4" --lang pt \
     --prompt "termos do seu domínio: Kubernetes, ArgoCD, Grafana"
   ```
   Padrão `medium` (o `small` erra termos técnicos). Sempre passe `--prompt` com o vocabulário do vídeo.
2. Detecte repetições:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/takes.py" "IN.transcript.json" --threshold 0.6
   ```
   Regra do script: em cada grupo de frases parecidas, fica a **última tentativa completa** (convenção de quem grava repetindo até acertar).
3. **Mostre ao usuário a lista de tomadas descartadas** (o script imprime) e peça OK. Ajuste se ele quiser manter outra tentativa: edite `IN.takes.json` (lista `keep` de `[início, fim]` em segundos).
4. Renderize:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/render_spans.sh" "IN.mp4" "IN.takes.json" "IN_tomada.mp4"
   ```
5. Sugira `/corte` em seguida (tira silêncios restantes) e `/legenda`.

## Ajustes
- Muitas falas diferentes sendo agrupadas → suba `--threshold` para 0.75.
- Repetições não detectadas → desça para 0.5.
