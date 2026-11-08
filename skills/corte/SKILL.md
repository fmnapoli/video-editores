---
name: corte
description: Corta silêncios, respirações e tempo morto de um vídeo falado (talking head, aula, vlog) e entrega um corte seco. Use quando o usuário pedir /corte, "tira os silêncios", "corte seco", "jump cut" ou "deixa mais dinâmico".
---

# /corte — corte seco automático

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.


## Passos
1. Confirme o arquivo de entrada. Se o usuário não disse, pergunte o ritmo: **suave** (margem 0.25s), **normal** (0.15s) ou **agressivo** (0.06s). Padrão: normal.
2. Rode o auto-editor (open source), que corta por volume de áudio:
   ```bash
   auto-editor "IN.mp4" --edit audio:threshold=0.04 --margin 0.15s --no-open \
     --video-codec libx264 --output "trabalho/<slug>/<slug>_corte.mp4"
   ```
   - Ambiente com ruído de fundo: suba `threshold` para 0.06–0.08.
   - Fala baixa/sussurrada: desça para 0.02–0.03.
   - Para exportar timeline editável em vez de vídeo: `--export resolve` (DaVinci), `--export premiere` ou `--export final-cut-pro`.
3. Compare durações (`ffprobe -v error -show_entries format=duration -of csv=p=0`) e informe: original → final, % removido.
4. Se removeu mais de 45%, avise: pode ter cortado fala. Ofereça refazer com threshold menor ou margem maior.
5. Sugira `/prova` para revisar o resultado.

## Regras
- Nunca sobrescreva o original; saída sempre `trabalho/<slug>/<slug>_corte.mp4`. `--no-open` é obrigatório (sem ele o auto-editor abre um player).
- Se o vídeo tiver tomadas repetidas (a pessoa repetiu frases), rode `/tomada` **antes** do `/corte`.
