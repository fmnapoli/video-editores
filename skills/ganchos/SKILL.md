---
name: ganchos
description: Escreve e testa ganchos (os 3 primeiros segundos) para reels, shorts e TikTok a partir da transcrição do vídeo, e reordena o início para abrir no trecho mais forte. Use para /ganchos, "melhora o começo", "gancho", "hook", "como prender nos 3 primeiros segundos".
---

# /ganchos — os 3 primeiros segundos

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## Passos
1. Garanta a transcrição: `IN.transcript.json` (gere com `"${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py"` se não houver).
2. Leia o vídeo inteiro e identifique:
   - a **promessa** (o que a pessoa ganha assistindo);
   - o **trecho mais forte** já gravado (número surpreendente, resultado, frase polêmica, antes/depois);
   - o público (pergunte se não estiver claro).
3. Entregue **5 ganchos**, cada um com um padrão diferente, máx. ~12 palavras (≈3 s de fala):
   | Padrão | Exemplo de forma |
   |---|---|
   | Resultado primeiro | "Esse vídeo foi editado por 13 comandos." |
   | Erro comum | "Você está cortando seus vídeos do jeito mais lento." |
   | Contraste | "Antes: 2 horas editando. Agora: 4 minutos." |
   | Pergunta específica | "Sabia que dá pra editar vídeo sem abrir editor?" |
   | Prova visual | começar no frame do resultado + texto curto |
4. Para cada gancho, diga **como executar**:
   - **Reaproveitar fala existente**: dê os tempos `[início, fim]` do trecho na transcrição e monte com `"${CLAUDE_PLUGIN_ROOT}/scripts/render_spans.sh"` usando um `keep` que põe esse trecho no começo e depois segue o vídeo, sem repetir o trecho.
   - **Texto na tela**: gere o item para `/lettering` (`style: titulo`, `anim: pop`, 0–2.5 s).
   - **Regravar**: escreva a fala exata para o usuário gravar.
5. Recomende 1 dos 5 e explique em uma frase por quê.

## Regras
- O gancho tem que ser cumprido pelo vídeo. Nada de promessa que o conteúdo não entrega.
- Sem clickbait de saúde, dinheiro fácil ou dados inventados.
