# Referência dos scripts

Ficam em `scripts/` e podem ser usados sem o Claude. Os scripts Python que precisam de pacotes rodam com `uv run --with <pacote>`, sem instalar nada globalmente. Desde a 0.5.0 todos têm um nome estável na CLI `video-editores <operação>` (que resolve o `uv run --with` sozinho) e no servidor MCP; a tabela nome → script está em [nucleo.md](nucleo.md).

Os scripts que usam modelos de IA (`transcribe.py`, `text_behind.py`, `matte.py`, `tts_cenas.py`) aceitam `--backend` e respeitam `VE_ASR`/`VE_SEG`/`VE_TTS`/`VE_DEVICE`; `matte.py` e `montar_aula.py` codificam com `VE_ENCODER`.

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

## legenda_palavra.py
```bash
python3 scripts/legenda_palavra.py VIDEO IN.transcript.json [--burn SAIDA.mp4] [--ass SAIDA.ass] [--janela 1.5] [--max-palavras 5] [--max-chars N] [--pausa 0.6] [--modo atual|preenche] [--pos F] [--tamanho 0.05] [--font Montserrat] [--cor #FFFFFF] [--destaque #FACC15] [--caixa] [--maiusculas] [--correcoes c.json]
```
Legenda estilo reels/TikTok: agrupa as palavras do `transcript.json` (ou de um `.srt` com um cue por palavra) em páginas fechadas por janela de tempo, pausa, nº de palavras, nº de caracteres (padrão: duas linhas na largura do vídeo) e fim de frase; cada palavra muda para a cor de destaque no instante em que é dita (`\t` por palavra; `--modo preenche` usa `\k`, karaokê). Uma página vai até a próxima começar quando a fala continua. Página que ficaria com uma palavra só recebe a última palavra da anterior, se a fala for contínua, a palavra não fechar frase e couber na janela. Saídas: `<nome>.palavra.ass` e `<nome>.palavra.paginas.txt` (tempos e texto de cada página, para revisar antes de queimar). `--correcoes` troca palavras erradas do ASR ignorando a pontuação em volta. Respeita a rotação do vídeo (mesmo `probe` do lettering). A queima é o filtro `ass=` do ffmpeg: 20 s de vídeo em ~3 s.

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

Gate: pico real acima de `PROVA_TP_MAX` (padrão −1,0 dBTP) grava `PICO ACIMA DO LIMITE` no `.proof.txt` e sai com código 3 (`PROVA_SEM_GATE=1` só avisa). Conserto: `normalizar_audio.py`.

## normalizar_audio.py
```bash
python3 scripts/normalizar_audio.py ENTRADA SAIDA.mp4|SAIDA.wav [--alvo -14] [--tp -1.5] [--filtro "highpass=f=80,afftdn=nf=-25:nr=12"]
python3 scripts/normalizar_audio.py ENTRADA --medir        # JSON com I, TP, LRA, thresh
```
Ganho estático até o alvo LUFS e `alimiter` com oversampling (192 kHz) segurando o pico real; mede antes e depois e repete com teto menor se o pico passar, ou com o ganho corrigido se o loudness saiu do alvo (`video_editores/nucleo/audio.py`). Saída `.mp4`: vídeo copiado, áudio AAC 192k. Sai com código 3 se o pico continuar acima de `--tp` + 0,3. Usado pelo `finalizar.sh` e pelo `montar_cenas.py` no lugar do `loudnorm` linear.

## tts_cenas.py (video-animado)
```bash
uv run --with edge-tts python skills/video-animado/scripts/tts_cenas.py cenas/<slug>.json [--glossario g.json] [--lead 0.6] [--tail 0.8]
```
Uma narração por cena, com fronteiras de palavra, e `tempos.json` com `fala`, `total` (= lead + fala + tail) e `lead` por cena; cena sem `narracao` usa `duracao`, ou a duração do arquivo em `audio` (bloco pronto com áudio próprio, ex.: exemplo tocado do `/partitura`). Cache por hash de voz + texto falado. O glossário (`pronuncia.py`) vale só para a fala.

## montar_cenas.py (video-animado)
```bash
python3 skills/video-animado/scripts/montar_cenas.py cenas/<slug>.json <pasta dos mp4> [--cenas B1,B2] [--saida ...] [--legenda ...] [--fonte "..."] [--tamanho 15] [--margem 22] [--loudness -16] [--tp -1.5] [--jobs 2] [--roteiro roteiros/roteiro-<slug>.md]
```
Montagem por EDL: cada bloco dura exatamente a narração da cena (`tempos.json`, no grid de quadros); cena 1 quadro curta tem o último quadro clonado (`tpad`), o áudio é atrasado em `lead` e preenchido até a mesma duração com fades de 12/18 ms (blocos em paralelo, `--jobs`). Concat sem recodificar, normalização pelo núcleo (`--loudness`, `--tp`), legenda queimada na codificação final (`.srt` em pasta separada; sem legenda o vídeo é copiado). Cena mais longa que a narração fica inteira, com aviso. Cena com `video` (caminho do mp4 fora da pasta do Manim) e `audio` (wav/mp3 próprio, `volume` opcional) entra como bloco pronto: o áudio dela substitui a narração, com os mesmos fades. `--roteiro` escreve o roteiro final com tempos, texto falado e legenda.

## folha_cenas.py (video-animado)
```bash
python3 skills/video-animado/scripts/folha_cenas.py cenas/<slug>.json <pasta dos mp4> [--fracao 0.9] [--colunas 4]
```
Um quadro de cada cena no instante `fracao` da sua duração, em grade; 0,5 mostra o meio da animação, 0,9 o estado final (para ver se algo invade a faixa da legenda).

## partitura.py (partitura)
```bash
uv run --with verovio --with resvg-py --with pillow python skills/partitura/scripts/partitura.py padroes.json [ID ...] [--out partituras] [--tamanho card|big|ambos] [--compassos N] [--fonte ARQ.ttf]
```
Padrão compacto → MusicXML → Verovio → cartão PNG. Entrada `{"padroes": [...]}`; cada padrão tem `id`, `titulo`, `sub`, `ts` (fórmula), `div` (1, 2 ou 4 subdivisões por tempo) e os instrumentos `hh`, `ride`, `crash`, `sn`, `tom`, `ft`, `bd`, `hf` como grade em texto (`"X.xx .x.."`: `x` toca, `X` com acento, `.` silêncio), `{"pos": [1, 2, 3]}`, lista de índices ou `"all"`; `stick` (texto `"RLRR LRLL"`, `"alterna"` ou `{índice: "R"|"L"}`) e `acento`. Saída: `<id>.png` (1800×270) e `<id>_big.png` (1800×430) com `.json` (`beats_px` por tempo, `fim_px`, `y0/y1`, `notas[{t, x, y, inst, acento}]`), mais `.musicxml` e `.svg`. Compassos: 2 (4 se `div` = 1).

## tocar.py (partitura)
```bash
uv run --with numpy --with scipy --with pillow python skills/partitura/scripts/tocar.py ID [--partituras partituras] [--out exemplos] [--bpm 72] [--voltas 2] [--contagem] [--fundo PNG] [--rotulo "Exemplo tocado"] [--titulo T] [--fonte ARQ.ttf] [--fps 30] [--so-audio]
```
Exemplo tocado a partir de `<ID>_big.json/.png`: síntese por fórmula (determinística), nota acendendo quando soa, playhead, contador e contagem opcional. Saída `<ID>.mp4` (1920×1080, áudio AAC sem PNS) e `<ID>.wav` (48 kHz estéreo, pico −6 dBFS) com a mesma duração no grid de quadros, mais `<ID>.json` (`dur`, `bpm`, `pre`, `eventos`). `VE_ENCODER` vale para o vídeo.

## andamento.py (partitura)
```bash
uv run --with librosa --with numpy --with scipy --with soundfile python skills/partitura/scripts/andamento.py CLIPE [CLIPE ...] [--ini S] [--fim S] [--faixa 70-160] [--tempos N] [--bumbo 0,3] [--out beats.json]
```
Andamento e fase do compasso de um clipe de bateria (vídeo ou áudio; o ffmpeg decodifica a 22,05 kHz mono). Beat tracking do librosa com quadros de 256 amostras; `bpm` é a mediana dos intervalos medidos sobre 4 batidas (robusta a uma batida perdida e ao grid), `bpm_tracker` a estimativa global, `bpm_desvio` o espalhamento. Com `--tempos N` e `--bumbo` (posições do compasso em que o bumbo toca), escolhe o "1" pela energia em 40–110 Hz nas batidas: `fase`, `contrastes` (um por fase), `confiavel` (melhor ≥ 1,3 e ≥ 1,1× a segunda) e `uns` (instantes do "1"). `--faixa` dobra ou divide o bpm que cair fora dela (ambiguidade de oitava). Acrescenta ao JSON de saída, um registro por clipe, chave = nome do arquivo sem extensão.

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

## validar_marca.py
Valida `marca/marca.json` (ADR-17) e gera a prancha de aprovação (cartela, faixa, destaque e legenda sobre tela clara e escura, encerramento, paleta, tipografia). Erros: cor obrigatória ausente, arquivo citado inexistente, contraste de texto (< 7) ou de acento (< 3) sobre o fundo, fonte sem os glifos do português. Propõe o ajuste mínimo de cor sem aplicar.
```bash
uv run --with pillow --with fonttools python scripts/validar_marca.py marca/marca.json --gravar
```
`legenda_palavra.py --espaco-largo` dobra o espaço entre palavras para fontes de espaço estreito.

## confere_saida.py (video-docs)
Confere, para cada spec, se o `.mp4` e o `.srt` existem, se o texto do `.srt` é o das legendas do spec e se o `.mp4` é mais novo que o spec. Sai com 1 listando o que remontar. Rode ao fim de todo lote:
```bash
python3 skills/video-docs/scripts/confere_saida.py specs/*/spec.json
```

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
| `finalizar.sh` | `finalizar.sh aula.json SAIDA.mp4 SAIDA.srt [--textos textos.json] [--ajustes ajustes.json] [--jobs N] [--limpar-audio]` | render de blocos → concat → lettering → (passa-alta + afftdn) → normalização −14 LUFS com teto de pico real → SRT → prova (reprova pico > −1 dBTP) |
| `detectar_layout.py` | `uv run --with pillow --with numpy python detectar_layout.py VIDEO cenas.json [--saida layout] [--quadro quadro] [--codigo codigo]` | círculo da webcam `{cx, cy, r}` e rascunho de `codigo_grupos` com réguas `regua_<grupo>.jpg` |
| `publicar_aula.py` | `uv run --with pillow --with numpy python publicar_aula.py aula.json [--saida saida/<slug>] [--thumb-t 5.0] [--sem-thumb] [--descricao ...]` | `<saida>.youtube.md` (capítulos nos tempos finais, descrição, hashtags) e `<saida>_thumb.jpg` 1280×720 |

`aula.json` (campos): `corte`, `corte_v1`, `transcript`, `cenas_corte`, `identidade`, `manim`, `mattes`, `blocos`, `whoosh`, `modos` (nomes dos `kind` no `cenas_corte.json`), `cartela_dur`, `capitulos[] {n, titulo, inicio}` (instante **no corte** em que a cartela entra), `diagramas[] {cena, inicio, fim}`, `circulo {cx, cy, r}` (webcam na gravação), `codigo_grupos[] {grupo, orig_ini, orig_fim, crop}` (tempos no **original**), `abertura`/`encerramento` (`cena`, `xoff`, tempos do overlay), `cores`, `fonte`, `fonte_dir`, `autor`, `subtitulo_autor`, `titulo`, `kicker`.
