---
name: tela-verde
description: Remove fundo verde (chroma key) ou, sem tela verde, recorta a pessoa por IA e troca o fundo por imagem, vídeo ou cor; também contorno neon na silhueta. Use para /tela-verde, "tira o fundo", "chroma key", "troca o fundo", "me recorta e troca o cenário", "contorno neon".
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
Use `"${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/matte.py"`: streaming ffmpeg → rembg → ffmpeg (nada em disco), máscara a 960x540 suavizada no tempo, sombra, saída composta + máscara separada (`_alpha.mp4`) para recompor com deslocamento:
```bash
uv run --with rembg --with onnxruntime --with pillow --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/matte.py" IN.mp4 0 25.1 fundo.png trabalho/<slug>/pessoa --threads 4
```
CPU: 1–3 s por frame; vários trechos em paralelo com `matte_workers.sh` (um trabalhador por ~4 núcleos e 1,3 GB). Lance detached (`setsid nohup`) e avise o tempo. Modelo padrão `u2net_human_seg` (download do GitHub pode dar 504 em rede corporativa: espelho no Hugging Face, ver troubleshooting). Para clipes longos com GPU, RobustVideoMatting (GPL-3) é mais estável.

## Contorno neon (efeito de Reels)
Com a máscara do rembg dá para desenhar um contorno colorido na silhueta, sem trocar o fundo:
1. Extraia os frames do trecho e gere a máscara da pessoa (`rembg.remove(img, only_mask=True)`).
2. Dilate a máscara (Pillow `ImageFilter.MaxFilter(15)`), subtraia a original → anel; pinte o anel com a cor neon, aplique `GaussianBlur(6)` para o brilho e componha sobre o frame original, com a pessoa por cima.
3. Remonte com ffmpeg e substitua o trecho como no `text_behind.py` (mesma estrutura de script; copie-o e troque a composição).
Cor típica: `#FF6B35` (laranja) ou `#39FF14` (verde neon). Trechos de 1–3 s, como no `/texto-atras`.

## Regras
- Fundo novo deve ter a mesma resolução/proporção do vídeo (o `scale2ref` resolve, mas avise se for distorcer).
