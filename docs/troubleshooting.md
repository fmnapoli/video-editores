# Solução de problemas

## Instalação

| Sintoma | Causa | Solução |
|---|---|---|
| `No such filter: 'ass'` ou `'subtitles'` | ffmpeg sem libass | use o ffmpeg do apt/brew; confira com `ffmpeg -filters \| grep ass` |
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
| volume diferente entre vídeos | sempre `loudnorm` no fim (-14 redes / -16 docs) |

## `/3d`

| Sintoma | Solução |
|---|---|
| `BLENDER_EEVEE_NEXT` não existe | o nome vale só no Blender 4.2–4.5; em < 4.2 e em 5.x use `BLENDER_EEVEE` (o skill já escolhe pela versão) |
| render preto | câmera sem enquadrar ou luz fraca; renderize um frame (`-f 45`) e ajuste |
| `.mov` sem transparência | precisa de `film_transparent = True` e ProRes 4444 `yuva444p10le` |

## `/video-docs`
Veja [video-docs-LEIAME.md](video-docs-LEIAME.md) ("Pontos que mais pegam") e `skills/video-docs/SKILL.md` ("Pegadinhas que custaram tempo"). Erro de rede no edge-tts significa que a montagem precisa de internet.
