# Referência dos scripts

Ficam em `scripts/` e podem ser usados sem o Claude. Os scripts Python que precisam de pacotes rodam com `uv run --with <pacote>`, sem instalar nada globalmente.

## transcribe.py
Transcrição com timestamps por palavra (faster-whisper, motor CTranslate2, o mesmo do whisper-ctranslate2 usado no video-docs).

```bash
uv run --with faster-whisper python scripts/transcribe.py VIDEO \
  [--model medium] [--lang pt] [--prompt "Kubernetes, ArgoCD"] [--words-per-cue 3] [--device auto|cpu|cuda] [--out-dir PASTA]
```

`--lang auto` detecta o idioma. Sem `--out-dir`, grava em `trabalho/<nome>/` se a pasta `trabalho/` existir; senão, ao lado da entrada.

| Saída | Conteúdo |
|---|---|
| `<nome>.transcript.json` | `segments[]` com `start`, `end`, `text`, `words[]`, `avg_logprob`, `no_speech_prob` |
| `<nome>.srt` | uma legenda por segmento |
| `<nome>.words.srt` | blocos de N palavras (estilo reels) |

VAD ligado (ignora silêncio). Em CPU usa `int8`. O modelo `small` erra termos técnicos; o padrão é `medium` + `--prompt`.

## takes.py
```bash
python3 scripts/takes.py VIDEO.transcript.json [--threshold 0.6] [--pad 0.08] [--out ARQ.takes.json]
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
Lê `keep` (lista de `[início, fim]` em segundos), recorta vídeo e áudio, aplica micro-fade de 20 ms no áudio (evita clique) e concatena **na ordem da lista**. Vídeo sem faixa de áudio (gravação de tela) também funciona; `keep` vazio aborta com mensagem. Por isso também serve para reordenar trechos, como trazer o gancho para o início.

## lettering_ass.py
```bash
python3 scripts/lettering_ass.py VIDEO textos.json [--font "DejaVu Sans"] [--burn SAIDA.mp4]
```
Gera `textos.ass` com `PlayRes` igual à resolução **exibida** do vídeo (considera o metadado de rotação de vídeos de celular) e, com `--burn`, queima com o filtro `ass`. Caminhos com espaço, vírgula ou `:` são escapados.

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

## highlights.py
```bash
python3 scripts/highlights.py VIDEO.transcript.json --target 600 [--keywords "a,b"] [--keep-intro] [--gap 1.2] [--min-block 4] [--pad 0.15] [--out ARQ]
python3 scripts/highlights.py VIDEO.transcript.json --reels 3 --reel-len 45
```
Saídas: `<nome>.highlights.json` (`keep` para o `render_spans.sh`, mais `blocks` com pontuação) e `<nome>.highlights.md` (tabela legível; trechos escolhidos em negrito). Heurística determinística; a decisão final é do Claude com o usuário.

## checklist_ass.py
```bash
python3 scripts/checklist_ass.py VIDEO itens.json VIDEO.transcript.json [--side left|right] [--start S] [--end S] [--font F] [--accent "#FF6B35"] [--burn SAIDA.mp4]
```
`itens.json`: lista de `{"text", "trigger"}` ou `{"text", "at"}`. Imprime o instante de cada item; itens sem gatilho vão para o stderr e ficam de fora.

## proof.sh
```bash
bash scripts/proof.sh VIDEO [N_FRAMES=12]
```
| Saída | Conteúdo |
|---|---|
| `.proof.jpg` | grid 4 colunas com N frames igualmente espaçados |
| `.preview.mp4` | 480p, CRF 30, leve para celular |
| `.proof.txt` | codec, resolução, fps, áudio, instantes de cada quadro do grid, loudness integrado e true peak |

## tts_cenas.py (video-animado)
```bash
uv run --with edge-tts python skills/video-animado/scripts/tts_cenas.py cenas/<slug>.json [--glossario g.json] [--lead 0.6] [--tail 0.8]
```
Uma narração por cena, com fronteiras de palavra, e `tempos.json` com `fala`, `total` (= lead + fala + tail) e `lead` por cena; cena sem `narracao` usa `duracao`. Cache por hash de voz + texto falado. O glossário (`pronuncia.py`) vale só para a fala.

## montar_cenas.py (video-animado)
```bash
python3 skills/video-animado/scripts/montar_cenas.py cenas/<slug>.json <pasta dos mp4> [--cenas B1,B2] [--saida ...] [--legenda ...] [--fonte "..."] [--tamanho 15] [--margem 22] [--loudness -16] [--roteiro roteiros/roteiro-<slug>.md]
```
Concatena `<id>.mp4` na ordem do spec, atrasa e preenche o áudio de cada cena até a duração real do mp4, gera o `.srt` (blocos de 2 linhas, frase a frase, grafia original da narração) e queima com `force_style`. Saída a 48 kHz, `+faststart`; `.srt` em pasta separada; `--roteiro` escreve o roteiro final com tempos, texto falado e legenda.

## folha_cenas.py (video-animado)
```bash
python3 skills/video-animado/scripts/folha_cenas.py cenas/<slug>.json <pasta dos mp4> [--fracao 0.9] [--colunas 4]
```
Um quadro de cada cena no instante `fracao` da sua duração, em grade; 0,5 mostra o meio da animação, 0,9 o estado final (para ver se algo invade a faixa da legenda).

## doctor.sh
```bash
bash scripts/doctor.sh
```
Checa ffmpeg com libass, python3, uv, fonte DejaVu e as CLIs de cada skill, com o comando para instalar cada uma. Não instala nada no Python do sistema (os pacotes Python vêm por `uv run --with`). Código de saída 1 se faltar algo obrigatório.

## render-docs.sh
Atalho do `render.sh` do video-docs, apontando para `skills/video-docs/scripts/build.py`. Rode a partir da raiz do projeto de vídeos:
```bash
bash scripts/render-docs.sh specs/<slug>/spec.json
```
Formato do spec: `skills/video-docs/references/producao.md`.

## skills/videoaula/scripts/
Ficam na pasta da skill porque dependem do `aula.json` do projeto (exemplo em `skills/videoaula/templates/aula-exemplo.json`).

| Script | Uso | Saída |
|---|---|---|
| `cenas_modo.py` | `uv run --with pillow --with numpy python cenas_modo.py CENAS.csv FRAMES/ cenas.json [--branco 0.55] [--pele 0.12]` | cenas com `kind` ∈ locutor/quadro/codigo |
| `remap_tempos.py` | `python3 remap_tempos.py CORTE.v1.json cenas.json IN.transcript.json --out PASTA` | `cenas_corte.json`, `transcript_corte.json`, `transcript_corte.txt` (tempos no vídeo cortado) |
| `identidade.py` | `uv run --with pillow --with numpy python identidade.py aula.json` | `identidade/`: `fundo.png`, `chip_N.png`, `circmask_*.png`, `ring_*.png`, `lower_third.png`, `l3_base_*.png`, `l3_cover_*.png`, `l3_geo.json` |
| `matte.py` | `uv run --with rembg --with onnxruntime --with pillow --with numpy python matte.py VIDEO INI FIM FUNDO.png OUT [--threads 4] [--model u2net_human_seg] [--gpu]` (GPU: `--with onnxruntime-gpu`) | `OUT.mp4` (pessoa + sombra sobre o fundo) e `OUT_alpha.mp4` (máscara) |
| `matte_workers.sh` | `matte_workers.sh aula.json [N]` | `mattes/talk_<ini>.mp4` para cada trecho de locutor, `.done`, `worker*.log` |
| `render_cenas.sh` | `render_cenas.sh diagramas.py ql\|qh [-j N] Cena1 Cena2 Separador:1` | `media/videos/<modulo>/<540p30\|1080p30>/<Cena>.mov` (alpha) |
| `montar_aula.py` | `montar_aula.py aula.json edl \| render [--ate T] [--only i,j] [--jobs N] \| concat SAIDA.mp4 [--ate T] \| map T` | `blocos/NNN_<tipo>.mp4` (+ `.ok`), vídeo concatenado com áudio contínuo |
| `legenda_aula.py` | `legenda_aula.py aula.json CORTE.v1.json IN.transcript.json SAIDA.srt [--ajustes ajustes.json]` | SRT com frases inteiras, tempos finais (corte + cartelas) |
| `finalizar.sh` | `finalizar.sh aula.json SAIDA.mp4 SAIDA.srt [--textos textos.json] [--ajustes ajustes.json] [--jobs N] [--limpar-audio]` | render de blocos → concat → lettering → (passa-alta + afftdn) → loudnorm −14 → SRT → prova |
| `detectar_layout.py` | `uv run --with pillow --with numpy python detectar_layout.py VIDEO cenas.json [--saida layout] [--quadro quadro] [--codigo codigo]` | círculo da webcam `{cx, cy, r}` e rascunho de `codigo_grupos` com réguas `regua_<grupo>.jpg` |
| `publicar_aula.py` | `uv run --with pillow --with numpy python publicar_aula.py aula.json [--saida saida/<slug>] [--thumb-t 5.0] [--sem-thumb] [--descricao ...]` | `<saida>.youtube.md` (capítulos nos tempos finais, descrição, hashtags) e `<saida>_thumb.jpg` 1280×720 |

`aula.json` (campos): `corte`, `corte_v1`, `transcript`, `cenas_corte`, `identidade`, `manim`, `mattes`, `blocos`, `whoosh`, `modos` (nomes dos `kind` no `cenas_corte.json`), `cartela_dur`, `capitulos[] {n, titulo, inicio}` (instante **no corte** em que a cartela entra), `diagramas[] {cena, inicio, fim}`, `circulo {cx, cy, r}` (webcam na gravação), `codigo_grupos[] {grupo, orig_ini, orig_fim, crop}` (tempos no **original**), `abertura`/`encerramento` (`cena`, `xoff`, tempos do overlay), `cores`, `fonte`, `fonte_dir`, `autor`, `subtitulo_autor`, `titulo`, `kicker`.
