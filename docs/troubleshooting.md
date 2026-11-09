# Solução de problemas

## Instalação

| Sintoma | Causa | Solução |
|---|---|---|
| `No such filter: 'ass'` ou `'subtitles'` | ffmpeg sem libass | use o ffmpeg do apt/brew; confira com `ffmpeg -filters \| grep ass`. No macOS, a fórmula `ffmpeg` do Homebrew (v8+) **não tem libass**: instale `ffmpeg-full` e coloque `$(brew --prefix ffmpeg-full)/bin` primeiro no PATH (`which -a ffmpeg` mostra a ordem) |
| `No such filter: 'drawtext'` | build estático | não afeta o plugin (não usa drawtext). Se aparecer, algum comando manual usou; troque por `lettering_ass.py` |
| skills não aparecem no `/` | plugin não instalado ou Claude Code não reiniciado | `claude plugin list`; reinstale e reinicie |
| `${CLAUDE_PLUGIN_ROOT}` vazio | skills copiados sem o plugin | `export CLAUDE_PLUGIN_ROOT=~/src/video-editores` |
| `uv: command not found` | uv não instalado | `curl -LsSf https://astral.sh/uv/install.sh \| sh` e abra outro terminal |

## Transcrição (`/tomada`, `/legenda`)

| Sintoma | Solução |
|---|---|
| termos técnicos errados ("cube CTL", "Argo CD") | passe `--prompt "kubectl, ArgoCD, ..."`; corrija no `.srt` antes de queimar |
| muito lento | `--model small` só para rascunho; com GPU, `--device cuda` |
| `libcudnn` não encontrada | rode em CPU (`--device cpu`) ou instale cuDNN 9 + CUDA 12 |
| frases cortadas na legenda | aumente `--words-per-cue` ou use o `.srt` por frase |
| legenda adiantada ou atrasada | VAD cortou o início; transcreva o vídeo final (depois dos cortes), não o bruto |

## `/tomada`

| Sintoma | Solução |
|---|---|
| juntou frases que não eram repetição | `--threshold 0.75` |
| não pegou uma repetição | `--threshold 0.5`, ou edite `keep` no `.takes.json` |
| corta o começo ou o fim da palavra | `--pad 0.15` |
| manteve a tentativa errada | edite `keep` à mão e rode só o `render_spans.sh` |

## `/corte`

| Sintoma | Solução |
|---|---|
| cortou fala baixa | `threshold` 0,02–0,03 ou margem maior |
| não cortou nada (ambiente ruidoso) | `threshold` 0,06–0,08; limpe antes com `afftdn` |
| ritmo picotado | margem 0,25 s (ritmo suave) |

## Texto e legenda

| Sintoma | Solução |
|---|---|
| fonte diferente da pedida | o nome não bate com a família instalada; veja `fc-list : family` |
| acento ou emoji como quadrado | fonte sem o glifo; use DejaVu, Noto ou Montserrat |
| legenda dupla no VLC | `.srt` com o mesmo nome ao lado do `.mp4`; mova para `legendas/` |
| texto em cima da legenda | no estilo reels a legenda ocupa ~55–65% da altura; mantenha o lettering acima de 50% ou abaixo de 70% (`pos`) |
| lettering pequeno ou deslocado em vídeo de celular | versão antiga do `lettering_ass.py` sem leitura da rotação; atualize o plugin |

## IA visual (`/texto-atras`, `/tela-verde`)

| Sintoma | Solução |
|---|---|
| borda da pessoa tremendo | `--model birefnet-portrait`; fundo mais limpo; trecho mais curto |
| muito lento | trecho de 1–3 s; GPU com `rembg[gpu]` |
| primeira execução demora | download do modelo (~170 MB U²-Net, ~900 MB BiRefNet), só uma vez |
| verde nas bordas (chroma) | aumente `similarity` e mantenha `despill` |

## Áudio

| Sintoma | Solução |
|---|---|
| música alta sobre a fala | `volume` 0,2 ou `ratio` maior no sidechain |
| clique entre cortes | `render_spans.sh` já faz fade de 20 ms; em cortes manuais use `afade` |
| volume diferente entre vídeos | normalize no fim (`scripts/normalizar_audio.py`, -14 redes / -16 docs) |
| `/prova` reprova com `PICO ACIMA DO LIMITE` (código 3), ou `loudnorm` linear entregou pico real positivo | degraus nas junções de uma montagem por blocos viram picos que o `loudnorm` linear amplifica (caso real: +9,2 dBTP). `normalizar_audio.py` (ganho estático + limiter de pico real) e fades de 12/18 ms em cada bloco (`audio.fades`) |
| wav limitado a −2,5 dBTP, mas o mp4 final mede pico positivo | PNS do codificador AAC nativo (substituição perceptual de ruído) em material com bandas de ruído (pratos, caixa sintetizada, chiado): +4,7 dBTP medidos. Codifique com `-c:a aac -b:a 256k -aac_pns 0` (`audio.AAC`); `-aac_coder fast` também resolve, com qualidade menor |
| edge-tts morre com `NoAudioReceived` no meio do lote | transitório do serviço; o backend `edge` repete 3 vezes (`VE_TTS_ESPERA` entre tentativas). Se persistir, é rede ou voz inexistente |

## `/3d`

| Sintoma | Solução |
|---|---|
| `BLENDER_EEVEE_NEXT` não existe | o nome vale só no Blender 4.2–4.5; em < 4.2 e em 5.x use `BLENDER_EEVEE` (o skill já escolhe pela versão) |
| render preto | câmera sem enquadrar ou luz fraca; renderize um frame (`-f 45`) e ajuste |
| `.mov` sem transparência | precisa de `film_transparent = True` e ProRes 4444 `yuva444p10le` |

## `/animacao` e `/video-animado`

| Sintoma | Solução |
|---|---|
| `uv tool install manim` falha compilando `manimpango` (`cmanimpango.c ... returned non-zero exit status 1`) | faltam os headers do Pango/Cairo (`libpango1.0-dev libcairo2-dev pkg-config python3-dev`). Sem sudo: `micromamba create -r ~/.local/opt/micromamba -n manim -c conda-forge manim python=3.12` (binário pronto do conda-forge) e `ln -s ~/.local/opt/micromamba/envs/manim/bin/manim ~/.local/bin/manim` |
| `Text(font="Minha Fonte")` sai em outra fonte | a fonte não está no fontconfig: copie o TTF para `~/.local/share/fonts/`, `fc-cache -f`, confira com `fc-list \| grep -i minha` |
| `round_corners` num polígono vira bolha | raio grande demais; use ~9 % da altura (`p.round_corners(h * 0.09)`) depois de dimensionar |
| legenda cobre o rodapé da animação | com 2 linhas em 1080p a faixa vai até y = -2,3 (unidades do Manim); confira com `folha_cenas.py --fracao 0.9` |
| áudio final a 96 ou 192 kHz | o `loudnorm` sobe a taxa; o `montar_cenas.py` já força `-ar 48000` (faça o mesmo em filtros próprios) |
| cena termina antes da narração ou o mp4 sai 1 quadro curto | o Manim grava int(s·fps) quadros num `wait` e len(arange(0, rt, 1/fps)) num `play`; contando por segundos, 20 passos derivam 0,3 s. O `cena_base.py` arredonda cada passo ao quadro e conta igual ao renderer; o `montar_cenas.py` completa o que faltar clonando o último quadro (`tpad`) até a duração da narração |
| grafia fonética do glossário vaza para a legenda | as fronteiras de palavra do edge-tts trazem a palavra **falada** e sem pontuação; o `montar_cenas.py` recupera o token original da narração (casamento 1 a 1); em pipeline próprio, faça o mesmo |

## `/partitura`

| Sintoma | Causa | Solução |
|---|---|---|
| nota acesa fora de lugar no exemplo tocado (atrás/na frente da que soa) | onset lido errado do Verovio: `qfracOn` vem em unidades de `<divisions>` e é relativo ao compasso, não absoluto | o `partitura.py` já divide por `div` e soma o compasso (`mi`); se mudar `divisions` no MusicXML, ajuste a conta junto |
| bolinha deslocada da cabeça da nota | coordenada do `<use>` sem o `translate` de `.page-margin`, ou sem o +90 (a âncora do glifo é a borda esquerda) | ambos estão no `render()`; não leia x/y direto do SVG |
| `ModuleNotFoundError: resvg_py` / PNG em branco | rasterizador ausente ou SVG sem `viewBox` | use `--with resvg-py` (sem dependência de sistema); o script cai no `cairosvg` só se ele estiver instalado (precisa de libcairo) |
| `grade ... tem N posições; o compasso tem M` | grade em texto com tamanho diferente de `tempos × div` | um caractere por subdivisão; espaços e `\|` são ignorados |
| `div=3` recusado | tercinas não são suportadas pelo `_dur_tipo` (só 1, 2 e 4 subdivisões) | escreva a frase em `div` 4 aproximando, ou registre o pedido |
| título do cartão com fonte genérica | nenhuma das fontes padrão instalada (Inter, DejaVu Sans Bold, Arial Bold) | `--fonte caminho.ttf` ou `sudo apt install fonts-dejavu-core` |
| pico real do vídeo final acima do limite com bateria sintetizada | PNS do AAC nativo (bandas de ruído) | o `tocar.py` e o núcleo já codificam com `-aac_pns 0`; se remuxar à mão, use `audio.AAC` |

## `/video-docs`
Veja [video-docs-LEIAME.md](video-docs-LEIAME.md) ("Pontos que mais pegam") e `skills/video-docs/SKILL.md` ("Pegadinhas que custaram tempo"). Erro de rede no edge-tts significa que a montagem precisa de internet.

## `/videoaula` (e tudo que transcreve ou recorta pessoa)

| Sintoma | Causa | Solução |
|---|---|---|
| `transcribe.py`: `open() got an unexpected keyword argument 'metadata_errors'` | PyAV 19 removeu o argumento que o faster-whisper 1.2 ainda passa; `av<15` não tem wheel e pede pkg-config | o `transcribe.py` 0.4 decodifica o áudio com o ffmpeg e passa um array ao modelo; atualize o plugin |
| rembg trava em `Downloading ... github.com/danielgatis/rembg/releases/download/...` ou dá `504 Gateway Time-out` | a rede (gateway corporativo) barra o CDN de releases do GitHub | baixe o mesmo `.onnx` de um espelho no Hugging Face (ex.: `skillsafe-ai/u2net-human-seg`) para `~/.rembg/models/u2net_human_seg/u2net_human_seg.onnx` e confira o md5 com o oficial (`c09ddc2e0104f800e3e1bb4652583d1f`) |
| `auto-editor ... --cut-out A,B C,D` → `Could not open input file: C,D` | cada trecho exige o próprio flag; em zsh, variável string não faz word-splitting | `CO=(--cut-out 1sec,2sec --cut-out 9sec,11sec); auto-editor IN.mp4 "${CO[@]}" ...` |
| trabalhador de recorte processa só o 1º trecho e "termina" | laço `while read` cujo filho (`uv run`) engoliu o resto da lista pelo stdin herdado | `< /dev/null` no comando filho, ou `mapfile` + `for` (é o que o `matte_workers.sh` faz) |
| áudio dessincroniza alguns frames no fim do vídeo montado por blocos | blocos codificados separadamente têm priming de AAC e durações arredondadas | `montar_aula.py concat` monta **uma** trilha de áudio contínua do corte e alinha as fronteiras ao frame; confira `vídeo == áudio` na saída |
| `vídeo` e `áudio` com durações diferentes na saída do `concat` (ex.: 2,6 s) | uma cartela não entrou no vídeo (instante do capítulo caiu numa micro-lacuna entre cenas) ou a EDL mudou depois do render | o `montar_aula.py` atual insere a cartela antes do primeiro bloco a partir do instante e monta o áudio da própria EDL; apague os `.ok` dos blocos após o ponto alterado e refaça `render` + `concat`; a prova deve mostrar vídeo == áudio |
| título do diagrama por cima do chip de capítulo | `to_edge(UP)` com folga pequena | `titulo()` da `base_cenas.py` usa `buff=1.35`; conteúdo da área do círculo: nada com x > 3,4 abaixo de y < −1,3 |
| código da IDE ilegível depois de reenquadrar | janela muda de layout ao longo da gravação (explorer aberto, fechado, zoom diferente) | um `crop` por grupo de layout em `codigo_grupos` (`aula.json`); meça com um frame e régua de 100 px |
| mockup/overlay com caixa branca opaca onde devia ser translúcida | `ImageDraw` sobre RGBA substitui o pixel, não compõe | desenhe numa camada própria e use `alpha_composite` (como em `identidade.py`) |
| processo de fundo morre quando a sessão do Claude Code reinicia | filhos da sessão recebem SIGHUP | lance com `setsid nohup ... < /dev/null &` e acompanhe por log; `matte_workers.sh` e os renders longos sempre assim |
| scenedetect: `does not have an extra named 'opencv'` | o extra sumiu no 0.7 | `uv tool install scenedetect` |
