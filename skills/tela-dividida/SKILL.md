---
name: tela-dividida
description: Tela dividida em 9:16 — reação (outro vídeo em cima, você embaixo), antes e depois (bruto em cima, editado embaixo) e conversão de proporção (16:9 → 9:16 ou 1:1). Use para /tela-dividida, "divide a tela", "eu reagindo embaixo", "mostra o antes e o depois", "versão vertical desse vídeo".
---

# /tela-dividida — reação, antes/depois e proporções

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`.

## Reação (vídeo de cima + você embaixo), 1080x1920
```bash
ffmpeg -i CIMA.mp4 -i EU.mp4 -filter_complex \
 "[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[a]; \
  [1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,setsar=1[b]; \
  [a][b]vstack=inputs=2[v]; \
  [1:a]volume=1.0[ma]; [0:a]volume=0.35[va]; [ma][va]amix=inputs=2:duration=first:normalize=0[aout]" \
 -map "[v]" -map "[aout]" -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -shortest OUT.mp4
```
- Sincronize o início do vídeo de cima com `-ss` antes do `-i CIMA.mp4` (quando a reação começa).
- O áudio de cima a 35% e o seu a 100%; para "o de cima só quando eu não falo", use `sidechaincompress` como no `/trilha`.
- Divisão desigual (60/40): troque `960` por `1152` e `768`.

## Antes e depois (bruto em cima, editado embaixo)
Mesmo filtro, com `BRUTO.mp4` e `EDITADO.mp4`. Como os tempos diferem, alinhe pela mesma frase: ache o tempo dela nos dois `.transcript.json` e use `-ss` em cada entrada. Rótulos "Bruto" e "Editado" com `/lettering` (`pos` `[0.08, 0.04]` e `[0.08, 0.54]`, `style: lower`).

## 16:9 → 9:16 (vertical a partir de horizontal)
- **Recorte central**: `-vf "crop=ih*9/16:ih,scale=1080:1920"`.
- **Recorte seguindo a pessoa**: extraia 1 frame a cada 2 s (`fps=0.5`), localize o rosto (olhe as imagens) e use `crop=ih*9/16:ih:X:0` por trecho, concatenando; ou `zoompan` para transição suave de X.
- **Borrado atrás (sem cortar)**: `-filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"`.

## 1:1 (feed)
`-vf "crop=min(iw\,ih):min(iw\,ih),scale=1080:1080"` ou a variante borrada com `1080:1080`.

## Regras
- Dois áudios ao mesmo tempo cansam: a regra é um dominante e o outro a 30–40% ou com ducking.
- Confira com `/prova` que a linha de corte não passa pelo rosto.
