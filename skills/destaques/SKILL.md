---
name: destaques
description: Seleciona os melhores momentos de um vídeo longo pela transcrição, para um alvo de duração ou para extrair N reels. Use para /destaques, "melhores momentos", "resume essa aula em 10 minutos", "transforma essa live num vídeo de 8 minutos", "tira três reels desse vídeo", "corta só as partes boas".
---

# /destaques — melhores momentos

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`. Script: `${CLAUDE_PLUGIN_ROOT}/scripts/highlights.py`.

## Passos
1. Levante: duração alvo (ou nº de reels e duração de cada), tema/palavras-chave (ou infira do título e do pedido), se a introdução deve ficar (`--keep-intro`).
2. Transcreva com vocabulário do domínio (pule se já houver `trabalho/<slug>/<nome>.transcript.json`):
   ```bash
   uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" originais/IN.mp4 --lang pt --prompt "<vocabulário>" --out-dir trabalho/<slug>
   ```
   Vídeo de 2 h leva ~2,5 h em CPU com `medium`; avise e, se o usuário preferir, use `--model small` para a seleção e refaça só os trechos escolhidos com `medium` para a legenda.
3. Primeira seleção:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/highlights.py" trabalho/<slug>/IN.transcript.json --target 600 --keywords "k8s,container,custo" --keep-intro
   # ou: --reels 3 --reel-len 45
   ```
   Gera `.highlights.json` (`keep`, compatível com `render_spans.sh`) e `.highlights.md` (tabela com todos os blocos e pontuação).
4. **Refine lendo a transcrição**, não só a pontuação: o script é heurístico. Garanta começo, meio e fim coerentes; não corte no meio de um raciocínio; inclua a conclusão. Edite `keep` à mão se precisar e **mostre a lista ao usuário** (tempo, começo da fala) antes de renderizar.
5. Renderize:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/render_spans.sh" originais/IN.mp4 trabalho/<slug>/IN.highlights.json trabalho/<slug>/<slug>_destaques.mp4
   ```
   Para reels, renderize cada janela separadamente (um `keep` com um trecho por arquivo) e siga com `/ganchos`, `/lettering`, `/legenda` em 9:16 (`crop` central: `-vf "crop=ih*9/16:ih"`).
6. Transições entre trechos distantes: um `xfade` de 0,25 s ou um corte seco com B-roll/lettering disfarça o salto. Sugira `/trilha` com ducking para cobrir mudanças de ambiente.

## Regras
- O usuário aprova a lista de trechos antes do render.
- Nunca inverta a ordem cronológica sem avisar (exceto quando o pedido é um gancho antecipado).
