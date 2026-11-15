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
- Se a `/prova` reprovar o pico real (código 3), troque o `loudnorm` do filtro por uma passada final de `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/normalizar_audio.py" IN_trilha.mp4 OUT.mp4 --alvo -14` (ganho estático + limiter).

## Trilha por capítulo (vídeo longo)
Uma música em laço por 10 minutos cansa e não acompanha a estrutura. Em vídeo com capítulos (aula, `/video-animado`, YouTube longo), dê a cada capítulo um trecho de música do tamanho dele, com fade nas pontas, e junte tudo numa trilha só **antes** da mixagem acima. Durações dos capítulos: do `aula.json`, do `tempos.json` ou dos marcadores do roteiro.
```bash
# capítulo 1 = 12,5 s com musica1, capítulo 2 = 20 s com musica2 (fade de saída começa 1,5 s antes do fim de cada um)
ffmpeg -stream_loop -1 -i musica1.mp3 -stream_loop -1 -i musica2.mp3 -filter_complex \
 "[0:a]aresample=async=1:first_pts=0,atrim=0:12.5,afade=t=in:d=0.5,afade=t=out:st=11:d=1.5[c1]; \
  [1:a]aresample=async=1:first_pts=0,atrim=0:20,afade=t=in:d=0.5,afade=t=out:st=18.5:d=1.5[c2]; \
  [c1][c2]concat=n=2:v=0:a=1[m]" -map "[m]" trabalho/<slug>/trilha_capitulos.wav
```
O `aresample=async=1` fecha os buracos de tempo que o MP3 em laço deixa; sem ele a trilha sai mais curta que a soma dos capítulos e a troca de música escorrega para dentro do capítulo seguinte. Confira com `ffprobe` que a duração é a soma. Depois use `trilha_capitulos.wav` no lugar de `musica.mp3` na mixagem, sem `-stream_loop`. A mesma música pode voltar em capítulos alternados; o que importa é a virada cair na troca de assunto.

## Regras
- Pergunte o clima (calmo, energético, tenso) antes de escolher.
- Nunca use música comercial sem licença; o Instagram/YouTube derruba ou silencia o vídeo.
