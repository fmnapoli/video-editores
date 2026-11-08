---
name: efeitos
description: Adiciona efeitos sonoros (whoosh em transições, pop em textos, ding, swoosh, riser) sincronizados com cortes e letterings, e efeitos de áudio na voz. Use para /efeitos, "sound design", "coloca um whoosh", "efeito sonoro".
---

# /efeitos — sound design

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## Onde pôr efeitos
Monte a lista de instantes a partir do que já existe:
- **Cortes**: `scenedetect -i IN.mp4 detect-adaptive list-scenes -f cenas.csv` → whoosh curto em cada troca de plano (no máximo 1 a cada 2–3 s, senão cansa).
- **Letterings**: `start` de cada item em `textos.json` → pop ou click.
- **Ganchos/revelações**: riser terminando no instante da revelação.
Mostre a lista ao usuário antes de mixar.

## Origem dos sons (livres)
- Freesound.org filtrando **CC0** (sem crédito).
- Sintetizar na hora com ffmpeg, sem baixar nada:
  ```bash
  # whoosh (ruído filtrado com varredura)
  ffmpeg -f lavfi -i "anoisesrc=d=0.45:c=pink:a=0.6" -af "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.2,afade=t=out:st=0.2:d=0.25" whoosh.wav
  # pop
  ffmpeg -f lavfi -i "sine=f=900:d=0.08" -af "afade=t=out:d=0.08,volume=0.8" pop.wav
  # ding
  ffmpeg -f lavfi -i "sine=f=1760:d=0.6" -af "afade=t=out:d=0.6,aecho=0.8:0.5:40:0.3" ding.wav
  ```
- AudioGen (AudioCraft): mesma ressalva da `/trilha`, pesos não comerciais.

## Mixagem
Para N efeitos, gere o filtro com `adelay` (milissegundos) e um `amix`:
```bash
ffmpeg -i IN.mp4 -i whoosh.wav -i pop.wav -filter_complex \
 "[1:a]adelay=2350|2350,volume=0.6[e1];[2:a]adelay=4100|4100,volume=0.5[e2]; \
  [0:a][e1][e2]amix=inputs=3:duration=first:normalize=0[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k IN_efeitos.mp4
```
Com muitos efeitos, escreva um script Python curto que lê a lista e monta o `filter_complex`.

## Efeitos na voz (opcionais)
- Limpeza de ruído: `afftdn=nf=-25`
- Presença: `highpass=f=80,equalizer=f=3000:t=q:w=1:g=3,acompressor=threshold=-18dB:ratio=3`
