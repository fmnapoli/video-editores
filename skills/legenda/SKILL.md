---
name: legenda
description: Gera legendas automáticas (faster-whisper) e queima no vídeo no estilo reels/shorts, ou exporta SRT. Use para /legenda, "coloca legenda", "legenda dinâmica", "gera o srt".
---

# /legenda — legendas automáticas

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.


## Passos
1. Pergunte (ou assuma o padrão entre parênteses):
   - estilo: **reels** (2–3 palavras, grande, centro-baixo) ou **clássico** (frase, rodapé) — padrão reels se vertical, clássico se horizontal;
   - só SRT ou queimar no vídeo (queimar).
2. Transcreva (pule se já existir `IN.transcript.json`):
   ```bash
   uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" "IN.mp4" --lang pt --words-per-cue 3 --prompt "vocabulário"
   ```
3. **Revise o texto antes de queimar**: leia o `.srt`/`.words.srt`, corrija nomes próprios, termos técnicos e siglas que o Whisper errou. Mostre ao usuário as correções.
4. Queime:
   - Reels (vertical 1080x1920):
     ```bash
     ffmpeg -i IN.mp4 -vf "subtitles=IN.words.srt:force_style='FontName=Montserrat,FontSize=16,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=110'" -c:a copy IN_legenda.mp4
     ```
   - Clássico:
     ```bash
     ffmpeg -i IN.mp4 -vf "subtitles=IN.srt:force_style='FontSize=20,Outline=2,MarginV=40'" -c:a copy IN_legenda.mp4
     ```
   - Destaque de cor (amarelo): `PrimaryColour=&H0000FFFF`. Cores ASS são `&HAABBGGRR`.
   - Caixa atrás do texto: `BorderStyle=3,BackColour=&H80000000`.
5. Se a fonte não existir no sistema, o ffmpeg usa a padrão — avise e sugira instalar (Montserrat/Inter, OFL).

## Regras
- Nunca queime sem revisar o texto (passo 3).
- Mantenha o `.srt` como entrega extra: serve para upload nativo no YouTube.
