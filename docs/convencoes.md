# Convenções do plugin video-editores

Valem para todos os skills, inclusive o `video-docs`.

## Pastas do projeto de vídeo
```
meu-projeto/
  originais/      brutos — NUNCA alterar, sobrescrever ou mover
  trabalho/<slug>/  intermediários: transcrições, .ass, .takes.json, frames, cache
  saida/          vídeos finais
  legendas/       .srt finais (separados do .mp4: o VLC carrega o sidecar e dobra a legenda queimada)
```
Rode os comandos a partir da raiz do projeto. Os scripts de transcrição gravam em `trabalho/<nome>/` automaticamente quando a pasta `trabalho/` existe (ou use `--out-dir`). Caminhos de trabalho em ASCII, sem espaço. Arquivo com espaço, parêntese ou acento entra só como `-i`, nunca dentro do `filter_complex`.

## Nomes de saída
`<slug>_<etapa>.mp4` em `trabalho/<slug>/` a cada etapa (`_tomada`, `_corte`, `_lettering`, `_legenda`, `_trilha`…). O resultado aprovado vai para `saida/<slug>.mp4`. Assim qualquer etapa pode ser refeita a partir da anterior.

## Ordem recomendada
```
/editar recebe o pedido e monta a ordem. Padrão:
/referencia (opcional) → /destaques (vídeo longo) → /tomada → /corte → /ganchos → /tela-dividida, /animacao, /3d, /tela-verde, /texto-atras
→ /checklist → /lettering → /legenda → /trilha → /efeitos → /prova
```
Legenda depois dos efeitos visuais (fica por cima). Áudio por último (cortes mudam o tempo).

## Formatos
| Destino | Resolução | Loudness | Observação |
|---|---|---|---|
| Reels, Shorts, TikTok | 1080x1920, 30 fps | -14 LUFS, TP -1.5 | zona segura: 15% de cima e de baixo |
| YouTube | 1920x1080 | -14 LUFS | `.srt` separado para upload |
| Documentação (`video-docs`) | 1280x720 (ou 1920x1080) | -16 LUFS | coordenadas sempre em 1280x720 |
| Animação por código (`video-animado`) | 1920x1080, 30 fps | -16 LUFS, TP -1.5 | conteúdo acima da faixa da legenda (y > -2,3 no Manim); sem tela preta entre cenas |

Pico real sempre ≤ −1,5 dBTP; a `/prova` reprova acima de −1,0. Normalize com `scripts/normalizar_audio.py` (ganho estático + limiter), não com `loudnorm` linear; em montagem por blocos, fades de 12/18 ms nas pontas de cada bloco.

Codificação: `-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 256k -aac_pns 0 -movflags +faststart`. Use `-preset slow` só se o usuário pedir qualidade máxima. Câmera lenta com som: estique o áudio com `rubberband=tempo=<vel>:transients=crisp`, nunca com `atempo` em cadeia (feito para fala; a 4× granula a música). O `-aac_pns 0` não é opcional: o PNS do codificador AAC nativo injeta ruído sintético que não respeita o pico do original (medido: wav limitado a −2,5 dBTP virou +4,7 dBTP a 192k com PNS; −2,4 sem PNS a 256k).

## Texto na tela
ASS/libass (`ass`, `subtitles`), nunca `drawtext`: o ffmpeg estático não tem. Fonte padrão DejaVu Sans Bold; Montserrat ou Inter (OFL) para redes.

## Gates humanos
Mostre e espere aprovação antes de: descartar tomadas, queimar legenda (texto revisado), render longo (3D, texto-atrás, IA). Use `/prova` antes de declarar pronto.

## Privacidade e verdade
- Nenhum dado pessoal, senha, token, e-mail ou CPF no vídeo final: corte ou tarje.
- A fala do bruto não é verdade: em conteúdo técnico, confira afirmações contra o código ou a doc oficial.
- O `/video-docs` envia o texto da narração ao serviço edge-tts da Microsoft: não coloque segredos nem informação confidencial no roteiro; o resto do plugin é 100% local.
- Música e efeitos só com licença clara (CC0, CC-BY com crédito, ou do usuário). Pesos do MusicGen/AudioGen são não comerciais.

## Ferramentas e licenças
| Ferramenta | Licença | Uso |
|---|---|---|
| ffmpeg | LGPL/GPL | tudo |
| faster-whisper | MIT | transcrição com timestamps por palavra |
| auto-editor | Unlicense | corte de silêncio |
| PySceneDetect | BSD-3 | detecção de cortes |
| rembg + BiRefNet | MIT | recorte de pessoa |
| Manim Community | MIT | motion graphics |
| Blender | GPL | 3D headless |
| edge-tts | GPL-3 (cliente; o serviço é da Microsoft) | narração do `video-docs` |
| AudioCraft | código MIT, pesos CC-BY-NC | trilha e efeitos gerados (não comercial) |
