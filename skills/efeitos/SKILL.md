---
name: efeitos
description: Adiciona efeitos sonoros (whoosh em transições, pop em textos, ding, swoosh, riser) sincronizados com cortes e letterings, e efeitos de áudio na voz. Use para /efeitos, "sound design", "coloca um whoosh", "efeito sonoro".
---

# /efeitos — sound design

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/efeitos.py` (só biblioteca padrão + ffmpeg). Planeja e aplica em dois passos, com o `.sfx.json` revisável no meio.

## O som segue o que se vê
- Evento **visível** pede som; o que não aparece, não. Corte sem troca de plano é para passar despercebido: sem som.
- Um protagonista por momento, e nem todo corte ganha whoosh: em dez minutos, "um whoosh por corte" cansa.
- O **pico** do whoosh cai no quadro da troca (não o começo do som); o riser **termina** no evento; pop, clique e ding **começam** nele.
- Efeito fica abaixo da voz: o nível é calculado a partir do loudness da fala do próprio vídeo.

## Passos
1. Junte os eventos (tempos no relógio do vídeo em que o som vai entrar):
   - **Câmera**: o `.camera.json` do `/camera` já traz as trocas de plano e os punches.
   - **Letterings**: o `textos.json` (entrada de cada texto → pop).
   - **O que você decidir** (revelação, gancho, troca de cena sem `/camera`): uma lista própria.
     ```json
     [{"t": 2.4, "som": "riser", "forca": "leve"}, {"t": 31.0, "som": "ding"}]
     ```
     Sem `/camera`, as trocas de plano vêm do `scenedetect -i IN.mp4 detect-adaptive list-scenes -f cenas.csv`: escreva um evento `whoosh` para as que importam.
2. Planeje e **mostre a lista ao usuário antes de mixar** (gate):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/efeitos.py" IN.mp4 \
     --eventos trabalho/<slug>/<slug>_corte.camera.json --eventos trabalho/<slug>/textos.json --eventos trabalho/<slug>/sons.json \
     --out trabalho/<slug>/<slug>.sfx.json
   ```
   A lista sai numerada (`sfx01`…) com o som, o alinhamento e o ganho; os eventos sem som aparecem com o motivo.
3. Ajustes por número são edições no `.sfx.json`: `"tira": true` remove ("sfx05 tira"), `ganho_db` −3 abaixa ("sfx12 mais baixo"), `arquivo` troca o som, `inicio` desloca (1 quadro = 0,033 s a 30 fps).
4. Mixe (o vídeo é copiado, só o áudio é refeito):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/efeitos.py" IN.mp4 --aplicar trabalho/<slug>/<slug>.sfx.json trabalho/<slug>/<slug>_efeitos.mp4
   ```
5. Ouça um trecho com o usuário ou siga para a `/prova`.

## Parâmetros
| Parâmetro | Padrão | Efeito |
|---|---|---|
| `--intervalo` | 2.0 s | mínimo entre dois sons automáticos do mesmo tipo (os da sua lista entram sempre) |
| `--ganho` | 0 dB | sobe ou desce todos os efeitos de uma vez |
| `--sons PASTA` | — | biblioteca própria; tem preferência sobre a síntese |
| por evento: `forca` | `media` | `leve` (−4 dB) ou `forte` (+3 dB) |
| por evento: `alinhar` | pelo som | `pico` ou `inicio`, para forçar |

Os níveis são ponto de partida calculado, não mixagem final: ajuste pelo ouvido do usuário (`--ganho`, ou `ganho_db` do item).

## Origem dos sons (livres)
- **Sintetizados** pelo ffmpeg, sem baixar nada: `whoosh`, `pop`, `clique`, `ding`, `impacto`, `riser` (ficam em `sfx/`, ao lado do `.sfx.json`).
- **Biblioteca do usuário** (`--sons PASTA`): uma subpasta por categoria (`PASTA/whoosh/*.wav`) ou o nome da categoria no começo do arquivo (`whoosh-03.wav`). O script mede o pico de cada arquivo, pula o silêncio inicial, alterna os arquivos e não repete o mesmo em menos de 20 s quando há outro. Uma categoria nova (ex.: `glitch`) passa a valer como `"som": "glitch"`.
- Freesound.org filtrando **CC0** (sem crédito) para montar a pasta.
- AudioGen (AudioCraft): mesma ressalva da `/trilha`, pesos não comerciais.

## Efeitos na voz (opcionais)
- Limpeza de ruído: `afftdn=nf=-25`
- Presença: `highpass=f=80,equalizer=f=3000:t=q:w=1:g=3,acompressor=threshold=-18dB:ratio=3`

## Regras
- Nunca sobrescreva a entrada; saída sempre `trabalho/<slug>/<slug>_efeitos.mp4`.
- Efeitos entram depois da `/trilha` e antes da `/prova`: cortes mudam o tempo, então o áudio é o último passo.
- Som que falta não se força: deixe o evento sem som e diga ao usuário qual categoria faria falta na pasta.
