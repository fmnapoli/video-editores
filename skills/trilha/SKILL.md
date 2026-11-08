---
name: trilha
description: Coloca trilha sonora de fundo com ducking automático (a música abaixa quando há fala), fade in/out e normalização de loudness para redes. Use para /trilha, "coloca uma música de fundo", "trilha", "abaixa a música quando eu falo".
---

# /trilha — música de fundo com ducking

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## Origem da música (sempre livre de direitos)
- Arquivo do usuário (pergunte se ele tem direito de uso).
- Bibliotecas CC0/livres: Free Music Archive (filtrar CC0/CC-BY), Pixabay Music, YouTube Audio Library. Para CC-BY, gere o crédito em `creditos.txt`.
- Geração local: AudioCraft/MusicGen. O código é MIT, mas **os pesos do modelo são CC-BY-NC**: só para uso não comercial. Avise o usuário.
  ```bash
  uv run --with audiocraft python -c "from audiocraft.models import MusicGen; from audiocraft.data.audio import audio_write; m=MusicGen.get_pretrained('facebook/musicgen-small'); m.set_generation_params(duration=30); w=m.generate(['lofi calmo, piano, 85 bpm']); audio_write('trilha', w[0].cpu(), m.sample_rate)"
  ```

## Mixagem (ffmpeg)
```bash
ffmpeg -i IN.mp4 -stream_loop -1 -i musica.mp3 -filter_complex \
 "[1:a]volume=0.35,afade=t=in:d=1.5,afade=t=out:st=DUR-2:d=2[m]; \
  [m][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]; \
  [0:a][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest IN_trilha.mp4
```
- Troque `DUR` pela duração do vídeo (`ffprobe`).
- Alvo de loudness: **-14 LUFS** para Reels, Shorts e TikTok. Para vídeo de documentação, use -16, igual ao `video-docs`.
- Música alta demais na fala: baixe `volume` (0.35 → 0.2) ou suba `ratio`.

## Regras
- Pergunte o clima (calmo, energético, tenso) antes de escolher.
- Nunca use música comercial sem licença; o Instagram/YouTube derruba ou silencia o vídeo.
