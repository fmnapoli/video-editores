---
name: checklist
description: Checklist com moldura na tela em que cada item aparece no instante em que é falado. Use para /checklist, "faz um checklist do que eu falar", "lista os passos na tela conforme eu explico", "itens entrando um por um".
---

# /checklist — itens no tempo da fala

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`. Script: `${CLAUDE_PLUGIN_ROOT}/scripts/checklist_ass.py`.

## Passos
1. Transcreva com palavras (`transcribe.py`, já padrão) se ainda não houver `.transcript.json` **do vídeo que vai receber o checklist** (depois dos cortes).
2. Leia a transcrição e escreva os itens, curtos (2–5 palavras), com o gatilho = primeira palavra distintiva que a pessoa fala ao introduzir o item:
   ```json
   [{"text": "Backup diário", "trigger": "backup"},
    {"text": "Monitoramento 24x7", "trigger": "monitor"},
    {"text": "Rollback em 1 clique", "at": 41.2}]
   ```
   `at` força o tempo. Mostre a lista ao usuário.
3. Gere e queime:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checklist_ass.py" IN.mp4 itens.json trabalho/<slug>/IN.transcript.json --side left --accent "#FF6B35" --burn trabalho/<slug>/<slug>_checklist.mp4
   ```
   O script avisa itens cujo gatilho não foi encontrado; ajuste o gatilho ou use `at`.
4. Confira com `/prova` que a moldura não cobre o rosto (use `--side right` se a pessoa estiver à esquerda) e que o painel some antes da legenda final, se preciso (`--end`).

## Combinações
- Checklist + legenda: queime o checklist antes, a legenda por cima.
- Som "pop" em cada item: passe os tempos impressos pelo script ao `/efeitos`.
