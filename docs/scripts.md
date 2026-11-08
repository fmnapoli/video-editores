# Referência dos scripts

Ficam em `scripts/` e podem ser usados sem o Claude. Os scripts Python que precisam de pacotes rodam com `uv run --with <pacote>`, sem instalar nada globalmente.

## transcribe.py
Transcrição com timestamps por palavra (faster-whisper, motor CTranslate2, o mesmo do whisper-ctranslate2 usado no video-docs).

```bash
uv run --with faster-whisper python scripts/transcribe.py VIDEO \
  [--model medium] [--lang pt] [--prompt "Kubernetes, ArgoCD"] [--words-per-cue 3] [--device auto|cpu|cuda]
```

| Saída | Conteúdo |
|---|---|
| `<nome>.transcript.json` | `segments[]` com `start`, `end`, `text`, `words[]`, `avg_logprob`, `no_speech_prob` |
| `<nome>.srt` | uma legenda por segmento |
| `<nome>.words.srt` | blocos de N palavras (estilo reels) |

VAD ligado (ignora silêncio). Em CPU usa `int8`. O modelo `small` erra termos técnicos; o padrão é `medium` + `--prompt`.

## takes.py
```bash
python3 scripts/takes.py VIDEO.transcript.json [--threshold 0.6] [--pad 0.08]
```
Saída: `<nome>.takes.json`:
```json
{"keep": [[0.0, 2.08], [5.92, 8.08]], "dropped": [{"start": 3.0, "end": 5.0, "text": "..."}]}
```
No stdout, a lista de descartes para revisão. Só usa a biblioteca padrão.

## render_spans.sh
```bash
bash scripts/render_spans.sh ENTRADA.mp4 TRECHOS.json SAIDA.mp4
```
Lê `keep` (lista de `[início, fim]` em segundos), recorta vídeo e áudio, aplica micro-fade de 20 ms no áudio (evita clique) e concatena **na ordem da lista**. Por isso também serve para reordenar trechos, como trazer o gancho para o início.

## lettering_ass.py
```bash
python3 scripts/lettering_ass.py VIDEO textos.json [--font "DejaVu Sans"] [--burn SAIDA.mp4]
```
Gera `textos.ass` com `PlayRes` igual à resolução do vídeo e, com `--burn`, queima com o filtro `ass`.

`textos.json`:

| Campo | Obrigatório | Valores |
|---|---|---|
| `text` | sim | texto; `\\N` quebra linha |
| `start`, `end` | sim | segundos |
| `style` | não | `titulo` (padrão), `destaque`, `lower` |
| `anim` | não | `fade` (padrão), `pop`, `slide`, `none` |
| `pos` | não | `[x, y]` em fração da tela (centro do texto) |
| `size` | não | altura da fonte em fração da altura do vídeo |
| `color` | não | `#RRGGBB` |

Padrões por estilo:

| Estilo | Posição | Tamanho | Cor | Visual |
|---|---|---|---|---|
| `titulo` | (0,5; 0,18) | 0,062 | branco | contorno preto |
| `destaque` | (0,5; 0,30) | 0,065 | amarelo `#FFD54F` | contorno preto |
| `lower` | (0,05; 0,84) | 0,040 | branco | caixa translúcida, alinhado à esquerda |

## text_behind.py
```bash
uv run --with "rembg[cpu]" --with pillow python scripts/text_behind.py IN.mp4 OUT.mp4 \
  --text "TEXTO" [--start 0] [--end 3] [--font arquivo.ttf] [--size 0.22] [--color "#FFFFFF"] [--y 0.35] \
  [--model u2net_human_seg|birefnet-portrait]
```
Por frame: extrai → segmenta a pessoa → desenha o texto no fundo → recoloca a pessoa por cima. Só o intervalo pedido é processado; o resto do vídeo e o áudio original são preservados. O texto encolhe sozinho até caber em 92% da largura.

## proof.sh
```bash
bash scripts/proof.sh VIDEO [N_FRAMES=12]
```
| Saída | Conteúdo |
|---|---|
| `.proof.jpg` | grid 4 colunas com N frames igualmente espaçados |
| `.preview.mp4` | 480p, CRF 30, leve para celular |
| `.proof.txt` | codec, resolução, fps, áudio, instantes de cada quadro do grid, loudness integrado e true peak |

## doctor.sh
```bash
bash scripts/doctor.sh [--install]
```
Lista binários e pacotes Python, com o comando para instalar cada um. `--install` instala os pacotes Python que faltam. O código de saída é 1 se faltar algo.

## render-docs.sh
Atalho do `render.sh` do video-docs, apontando para `skills/video-docs/scripts/build.py`. Rode a partir da raiz do projeto de vídeos:
```bash
bash scripts/render-docs.sh specs/<slug>/spec.json
```
Formato do spec: `skills/video-docs/references/producao.md`.
