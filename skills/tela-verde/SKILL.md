---
name: tela-verde
description: Remove fundo verde (chroma key) ou, sem tela verde, recorta a pessoa por IA e troca o fundo por imagem, vídeo ou cor. Use para /tela-verde, "tira o fundo", "chroma key", "troca o fundo".
---

# /tela-verde — troca de fundo

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## Com tela verde de verdade (rápido, ffmpeg)
1. Descubra a cor do fundo: extraia um frame (`ffmpeg -ss 1 -i IN.mp4 -frames:v 1 f.png`), olhe a imagem e amostre a cor (padrão `0x00FF00`; telas reais costumam ser ~`0x3BB143`).
2. Componha:
   ```bash
   ffmpeg -i FUNDO.mp4 -i IN.mp4 -filter_complex \
     "[1:v]chromakey=0x3BB143:0.12:0.08,despill=type=green[fg];[0:v][fg]scale2ref[bg][fg2];[bg][fg2]overlay=shortest=1[v]" \
     -map "[v]" -map 1:a -c:a copy IN_fundo.mp4
   ```
   - Fundo imagem: troque `-i FUNDO.mp4` por `-loop 1 -i fundo.jpg`.
   - Sobrou verde na borda → aumente `similarity` (0.12→0.16). Comeu a pessoa → diminua.
   - `scale2ref` está marcado como obsoleto a partir do ffmpeg 7.1 (ainda funciona). Alternativa: `[0:v]scale=W:H[bg]` com a resolução lida por `ffprobe`.
3. Mostre com `/prova`.

## Sem tela verde (IA, rembg — MIT)
Use o mesmo pipeline de `"${CLAUDE_PLUGIN_ROOT}/scripts/text_behind.py"` adaptado: para cada frame, `rembg.remove` gera a pessoa com alpha e cola sobre o novo fundo. Processe em trechos e avise que é lento em CPU. Para clipes longos, sugira RobustVideoMatting (GPL-3, melhor estabilidade temporal) com GPU.

## Regras
- Fundo novo deve ter a mesma resolução/proporção do vídeo (o `scale2ref` resolve, mas avise se for distorcer).
