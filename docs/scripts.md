# Referência dos scripts

Ficam em `scripts/` e podem ser usados sem o Claude. Os scripts Python que precisam de pacotes rodam com `uv run --with <pacote>`, sem instalar nada globalmente. Desde a 0.5.0 todos têm um nome estável na CLI `video-editores <operação>` (que resolve o `uv run --with` sozinho) e no servidor MCP; a tabela nome → script está em [nucleo.md](nucleo.md).

Os scripts que usam modelos de IA (`transcribe.py`, `text_behind.py`, `matte.py`, `tts_cenas.py`, `rostos.py`, `ler_tela.py`) aceitam `--backend` e respeitam `VE_ASR`/`VE_SEG`/`VE_TTS`/`VE_ROSTO`/`VE_OCR`/`VE_DEVICE`; `matte.py` e `montar_aula.py` codificam com `VE_ENCODER`.

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
A saída mantém a taxa de quadros da entrada (filtro `fps` depois do `concat`; sem ele o ffmpeg 7 gravava 25 fps).
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

## backbone.py
```bash
python3 scripts/backbone.py blocos VIDEO.transcript.json [--gap 1.2] [--min-block 3] [--max-block 45] [--keywords "a,b"] [--out ARQ]
python3 scripts/backbone.py relatorio ARQ.backbone.json [--json] [--usar-sugestao]
python3 scripts/backbone.py montar ARQ.backbone.json --target 90 [--reordenar] [--pesos "metodo=0.4,causa=0.1"] [--pad 0.15] [--out ARQ]
```
Arco narrativo em sete etapas (`desafio`, `identificacao`, `causa`, `solucao`, `metodo`, `motivacao`, `conclusao`; estrutura "Backbone", de Letícia Pacheco). `blocos` grava `<nome>.backbone.json`: cada bloco com `sugestao` e `confianca` (palavras-marcadoras e posição no vídeo), `pontos` (a pontuação do `highlights.py`) e `etapa` vazia, para quem lê preencher com uma chave ou `fora`. `relatorio` grava `<nome>.backbone.md` (etapas ausentes, duração e fração por etapa, inversões de ordem, etapa com mais de 50% ou menos de 3% do arco); `--json` imprime o resumo. `montar` grava `<nome>.backbone.keep.json` para o `render_spans.sh`: o melhor bloco de cada etapa entra sempre, os demais enquanto couberem na fração do alvo daquela etapa (pesos padrão: método 28%, causa e solução 15%, desafio e identificação 12%, motivação 10%, conclusão 8%), e o que uma etapa não usa passa para a seguinte. Plano com `etapa` vazia é recusado com código 2, a menos de `--usar-sugestao`.

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

## extrair_marca.py
Coleta candidatos de identidade de uma fonte externa e grava `<out>/rascunho.json` (cores, fontes e logos com a evidência de cada um, `sugestao` de papéis, `avisos`). Aceita `.pptx/.potx/.docx/.dotx/.xlsx` (tema), `.pdf` (manual), pasta ou `.zip` (pacote de marca) e `.json` (tokens). `--gravar-sugestao` escreve um primeiro `marca.json` se não houver um (de pacote, copia logo e fontes para `<out>/`). URL é recusada: site não é lido.
```bash
uv run --with pillow --with fonttools --with pypdf python scripts/extrair_marca.py manual.pdf --out marca
```

## gerar_imagem.py
Gera N variações de uma imagem a partir de um prompt no backend de imagem (padrão: servidor ComfyUI, ADR-15), uma por semente, e grava `<out>/<id>-<semente>.png`, a folha de escolha `<out>/<id>.folha.png` e o registro `<out>/<id>.json`. O registro soma uma rodada por execução, com prompt, negativo, tamanho, passos, sementes, workflow (com sha256), modelo, licença e versão do servidor. Largura e altura em múltiplos de 16. Para regenerar uma escolhida: o mesmo prompt com `--semente S --variacoes 1`.
```bash
VE_COMFYUI_URL=http://gpu:8188 uv run --with pillow python scripts/gerar_imagem.py "fundo abstrato azul, luz suave" --id fundo-abertura --out trabalho/aula01/gerados
uv run python scripts/gerar_imagem.py --conferir     # servidor no ar, workflow compatível com os nós dele e checkpoint presente
```

## cena_web.py
Renderiza uma cena HTML quadro a quadro (Playwright dirigindo o Chrome instalado, ou `VE_CHROME`, ou o Chromium do Playwright) e codifica no ffmpeg.
```bash
uv run --with playwright python scripts/cena_web.py CENA.html SAIDA.mp4|SAIDA.mov [--dur S] [--fps 30] [--tamanho 1920x1080] [--escala 1] [--alpha] [--rede] [--espera-quadro]
uv run --with playwright python scripts/cena_web.py CENA.html --quadro T SAIDA.png
uv run --with playwright python scripts/cena_web.py CENA.html --quadros T1,T2,...|N FOLHA.png [--reserva-baixo 0.21] [--auditoria erro|aviso|nao]
uv run --with playwright python scripts/cena_web.py CENA.html SAIDA.mp4 --palavras ARQ.json [--dados ARQ.json] [--marca ARQ|--sem-marca]
uv run --with playwright python scripts/cena_web.py --libs
```
Contrato da cena: `window.veQuadro = (t) => {...}` (obrigatório; pode devolver `Promise`, e só `Promise` de verdade é esperada: a timeline do GSAP tem `.then()` e travaria o render) e `window.veDuracao` (ou `--dur`). A página é servida de `http://cena.local/` por interceptação de requisição, sem abrir porta: arquivos ao lado do `.html` e as bibliotecas em `/_ve/three/` e `/_ve/gsap/`, baixadas do registro do npm na versão fixada, conferidas por sha256 e guardadas em `~/.cache/video-editores/web/`. Qualquer outra origem é bloqueada e vira `AVISO` no fim (`--rede` libera). Erro de JavaScript na cena encerra o render dizendo o quadro. `.mov` sai em ProRes 4444 (`yuva444p` com `--alpha`); `.mp4` usa `VE_ENCODER`. WebGL roda por software (SwiftShader). `VE_ESPERA_CENA` muda os 20 s de espera pelo `veQuadro`.

`--palavras` entrega o mapa de palavras da narração (`[{"t", "d", "w"}]`, no tempo da cena) e as funções `veQuando(termo, n, padrao)` e `veTrecho(termo, n)`; palavra ausente interrompe o render. `--quadros` grava a folha de quadros-chave e confere o texto do DOM em cada instante (cortado pela borda; dentro da faixa de `--reserva-baixo`), com código de saída 2 se houver problema. Com `marca/marca.json`, a página recebe `window.veMarca`, as variáveis `--ve-*` e os TTF da marca.

## render_web.py (video-animado)
```bash
uv run --with playwright python skills/video-animado/scripts/render_web.py cenas/<slug>.json PASTA_MP4 [--cenas A,B] [--tamanho 1920x1080] [--fps 30] [--jobs 2]
uv run --with playwright python skills/video-animado/scripts/render_web.py cenas/<slug>.json PASTA_MP4 --folha [N] [--reserva-baixo 0.21]
```
Renderiza as cenas do spec que têm `"html"` em `PASTA_MP4/<id>.mp4`, com a duração do `tempos.json` e as palavras da narração na grafia do roteiro, já deslocadas pelo silêncio inicial. `--folha` grava `PASTA_MP4/<id>.folha.png` por cena e sai com código 2 se alguma tiver texto cortado ou na faixa da legenda.

## camera.py
Câmera sobre o vídeo cortado, em dois passos. Planejar usa só a biblioteca padrão; aplicar usa OpenCV.
```bash
python3 scripts/camera.py VIDEO --cortes ARQ [--cortes ARQ2 ...] [--rostos ARQ.rostos.json] [--punches ARQ.json] \
  [--fechado 1.18] [--deriva 0.03] [--olhos 0.38] [--min-plano 0.8] [--comeca aberto|fechado] [--seguir] [--out ARQ.camera.json]
python3 scripts/camera.py VIDEO --cortes-em 3.2,7.9,12.4 [...]
uv run --with opencv-python-headless --with numpy python scripts/camera.py VIDEO --aplicar ARQ.camera.json SAIDA.mp4
```
`--cortes` aceita o `.takes.json` (trechos `keep`, como o `render_spans.sh` os monta) e o JSON `--export v1` do auto-editor, na ordem em que as etapas rodaram; `VIDEO` é a saída da última. `<nome>.camera.json`: `planos[]` (`id`, `inicio`, `fim`, `plano`, `escala`, `deriva`, `foco` = `[x, y dos olhos]` em fração do quadro, `trilha` com `--seguir`), `punches[]` (`id`, `t`, `forca`, `dur`), `eventos[]` (`t`, `tipo` `corte`|`punch`, `forca`) para o `efeitos.py` e `avisos[]`. Avisa quando a soma dos quadros dos arquivos de corte não bate com o vídeo, quando um trecho é curto demais para trocar de plano, quando um punch cai em cima de um corte e quando a ampliação passa de 135%. `--punches`: `[{"t": 12.3, "forca": 0.06, "dur": 0.3, "texto": "…"}]`, no tempo de `VIDEO`.

## efeitos.py
Efeitos sonoros por evento, em dois passos. Só biblioteca padrão + ffmpeg.
```bash
python3 scripts/efeitos.py VIDEO --eventos ARQ [--eventos ARQ2 ...] [--palavras ARQ] [--sons PASTA] [--intervalo 2.0] [--ganho 0] [--out ARQ.sfx.json]
python3 scripts/efeitos.py VIDEO --aplicar ARQ.sfx.json SAIDA.mp4
```
`--eventos`: `.camera.json` (`corte` → whoosh, `punch` → impacto), `textos.json` do lettering (`start` → pop) ou lista `[{"t", "som", "forca", "ganho", "alinhar", "arquivo"}]`. Na lista, `"quando": "palavra ou expressão"` substitui `"t"` pelo instante em que ela é falada (`"n"` = ocorrência, `"no_fim"` = fim em vez do começo, `"desloca"` = segundos somados), lido de `--palavras`: `transcript.json` do `transcribe.py`, `palavras.transcript.json` do `montar_cenas.py` ou `[{"t", "d", "w"}]`; a busca ignora maiúsculas, acentos e pontuação, e palavra ausente vai para `pulados[]`. `<nome>.sfx.json`: `voz_lufs`, `itens[]` (`id`, `t`, `som`, `arquivo`, `alinhar`, `inicio` = onde o som começa no vídeo, `corte` = quanto do começo do arquivo é pulado, `ganho_db`; `"tira": true` exclui da mixagem) e `pulados[]` com o motivo. Sons sintetizados em `sfx/` ao lado do plano: whoosh, pop, clique, ding, impacto, riser. Nível: pico do efeito = loudness da voz + ajuste da categoria + `forca` + `ganho`, com teto de −3 dBFS; sem fala mensurável, assume −16 LUFS e avisa.

## rostos.py
Onde está o rosto, e se algum texto passou por cima dele (papel `rosto`, padrão YuNet/OpenCV; o modelo de 230 KB é baixado uma vez para `~/.cache/video-editores/modelos/` e conferido por sha256; `VE_YUNET_MODELO` aponta um arquivo local).
```bash
uv run --with opencv-python-headless --with numpy python scripts/rostos.py VIDEO [--passo 0.5] [--inicio T] [--fim T] [--min-conf 0.6] [--out ARQ.rostos.json]
uv run --with opencv-python-headless --with numpy python scripts/rostos.py ANTES.mp4 --conferir DEPOIS.mp4 [--rostos ARQ.rostos.json] [--limiar 28] [--area 0.05]
```
`<nome>.rostos.json`: `quadros[]` com `t` e `rostos[]` (`x`, `y`, `w`, `h` em fração do quadro, `conf`), `zona` (união de todas as caixas), `livre` (folga em cada lado) e `sugestao` (`lado` e `pos` para texto, descontando 15% de cima e de baixo da interface dos aplicativos). A conferência amostra os dois vídeos no mesmo passo e, dentro de cada caixa, conta os pixels cujo brilho mudou mais que `--limiar`; acima de `--area` da caixa, o instante entra em `<depois>.rosto-coberto.json` e o script sai com código 3. Os dois vídeos precisam ter a mesma duração (entrada e saída da mesma etapa).

## rastrear.py
Rastreamento de uma região por fluxo óptico (Lucas-Kanade com verificação de ida e volta) e transformação de similaridade por RANSAC; só OpenCV, sem modelo.
```bash
uv run --with opencv-python-headless --with numpy python scripts/rastrear.py VIDEO --caixa X,Y,L,A [--inicio 0] [--fim T] [--id NOME] [--out PASTA] \
  [--etiqueta "TEXTO"] [--ancora cima|baixo|centro|esquerda|direita] [--tamanho 0.035] [--cor "#FFD54F"] [--seta] [--girar] [--sem-escala] [--suavizar 5] [--burn SAIDA.mp4]
```
`<id>.rastro.json`: `quadros[]` com `t`, `cx`, `cy` (fração do quadro), `escala`, `rot` (graus), `conf` (fração de pontos coerentes) e `cantos` (os quatro cantos da caixa transformada); `perdido_em` e `motivo` quando o rastro termina antes do fim (código 2). `<id>.rastro.ass`: um evento por quadro, com a fronteira meio quadro antes do instante para o arredondamento do ASS não deslocar o evento, e entrada/saída por alfa em 0,2 s. Fonte e cor seguem a marca (`--marca`).

## ler_tela.py
OCR de imagem ou de um quadro do vídeo (papel `ocr`, padrão RapidOCR com modelos PP-OCR), com busca e desenho no lugar do texto.
```bash
uv run --with rapidocr --with onnxruntime python scripts/ler_tela.py IMAGEM|VIDEO [--t T] [--out ARQ.ocr.json] \
  [--achar "TEXTO"]... [--regex PADRÃO]... [--todos] [--estilo caixa|marca|sublinhado|tarja] [--inicio T] [--fim T] [--cor "#RRGGBB"] [--folga 0.25] [--burn SAIDA]
```
`<nome>.ocr.json`: `linhas[]` (`texto`, `conf`, `caixa` `[x, y, l, a]` em fração da imagem, `palavras[]`) e `achados[]` (`consulta`, `texto`, `caixa`). `--achar` compara sem acento nem caixa e junta as palavras do trecho, recortando a primeira e a última na proporção dos caracteres que entram (em código de largura fixa, um pedaço de dentro de um token sai justo); linha sem caixas de palavra recebe uma fatia proporcional da caixa da linha. Código 1 quando nada é encontrado, com a lista do que foi lido. Com imagem de entrada, `--burn SAIDA.png` grava a imagem marcada.

Vídeo longo com vários destaques: `--lote itens.json` (`[{"achar"|"regex", "entre": [início, fim], "estilo", "dur", "cor"}]`) procura cada texto na sua janela de tempo, uma amostra a cada `--passo` (0,5 s), e escolhe o primeiro trecho em que o texto fica pelo menos `--minimo` (1,5 s) no mesmo lugar, até `dur` (2,5 s). Grava um `.destaques.ass` com tudo e um `.destaques.json` com instante e caixa de cada um; item que só aparece com a tela em movimento sai marcado `curto`, e item não encontrado é listado (código 1, com o `.ass` dos demais).

## conferir_fala.py
Compara o roteiro com a transcrição do áudio final (só biblioteca padrão).
```bash
python3 scripts/conferir_fala.py ROTEIRO.txt|.md|cenas.json|spec.json FINAL.transcript.json [--tolerancia 0.02] [--equivalentes eq.json] [--out ARQ.fala.md]
```
Roteiro em texto ignora títulos (`#`), citações (`>`) e trechos entre colchetes; `cenas.json` lê `narracao` e `spec.json` lê `tts` (senão `legend`). Saídas `<nome>.fala.md` e `.fala.json` com cada diferença: `faltou`, `sobrou`, `trocou` ou `parecida` (troca por palavra com 80% de semelhança, que não conta na taxa), o instante e as palavras de antes. Código 1 quando a taxa de palavras com diferença passa de `--tolerancia`.

## banco_video.py
Opcional (skill `/banco`): busca e download em banco de vídeo, só com `PEXELS_API_KEY`. Só biblioteca padrão e ffmpeg.
```bash
python3 scripts/banco_video.py buscar "TERMO" [--id ID] [--orientacao paisagem|retrato|quadrado] [--min-dur 4] [--max-dur 60] [--n 8] [--out banco]
python3 scripts/banco_video.py baixar ID --escolha N [--altura 1080] [--out banco]
python3 scripts/banco_video.py creditos [--out banco]
```
`buscar` grava `<id>.busca.json` e `<id>.folha.jpg` (miniaturas na ordem dos candidatos); `baixar` pega o menor arquivo cujo lado menor tem a medida de `--altura`, recusa sobrescrever e grava `<id>.json` (autor, página, licença, termo, data, sha256). `VE_BANCO_URL` troca o endereço da API (testes).

## marca_cli.py
Biblioteca dos scripts de texto (`lettering_ass.py`, `checklist_ass.py`, `legenda_palavra.py`): acrescenta `--marca` (`nao` ignora), resolve fonte e cores pela marca quando o parâmetro não foi passado e devolve o `fontsdir` para o libass. Também serve a quem monta ffmpeg à mão:
```bash
python3 scripts/marca_cli.py force-style    # FontName, cores e contorno no formato do filtro subtitles
python3 scripts/marca_cli.py fontsdir       # pasta dos TTF da marca (vazio se a fonte é do sistema)
```

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
