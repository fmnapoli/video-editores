---
name: rastrear
description: Rastreamento (tracking) — acompanha um objeto ou uma região do vídeo quadro a quadro e gruda uma etiqueta que anda junto com ele. Local e determinístico (OpenCV, sem modelo de IA). Use para /rastrear, "põe uma etiqueta que segue a prancha", "marca esse objeto e acompanha", "texto grudado no carro", "tracking", "segue esse ponto".
---

# /rastrear — etiqueta que anda com o objeto

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/rastrear.py` (fluxo óptico Lucas-Kanade + RANSAC; a etiqueta sai em ASS, um evento por quadro).

## Passos
1. Levante: o que seguir, de quando a quando (`--inicio`/`--fim`, dentro de **um plano só**) e o texto da etiqueta.
2. Extraia o quadro inicial com uma grade e **olhe a imagem** (Read) para tirar a caixa do objeto em fração do quadro:
   ```bash
   ffmpeg -ss T0 -i IN.mp4 -frames:v 1 -vf "drawgrid=w=iw/10:h=ih/10:t=1:c=yellow@0.6" trabalho/<slug>/grade.jpg
   ```
   Cada célula vale 0,1. `--caixa X,Y,L,A` é o canto superior esquerdo, a largura e a altura. Caixa justa no objeto: sobra de fundo dentro da caixa faz o rastro seguir o fundo.
3. Rode com a etiqueta e queime uma prova:
   ```bash
   uv run --with opencv-python-headless --with numpy python "${CLAUDE_PLUGIN_ROOT}/scripts/rastrear.py" IN.mp4 \
     --caixa 0.38,0.59,0.05,0.14 --inicio 20.5 --fim 24 --id prancha \
     --etiqueta "PRANCHA" --seta --burn trabalho/<slug>/<slug>_rastro.mp4
   ```
   Saídas: `prancha.rastro.json` (posição, escala, rotação e confiança por quadro, em fração do quadro) e `prancha.rastro.ass`.
4. **Confira antes de seguir**: tire 4–5 quadros espalhados do resultado e olhe se a etiqueta continua no objeto no fim do trecho, não só no começo.
   ```bash
   ffmpeg -i trabalho/<slug>/<slug>_rastro.mp4 -vf "fps=1,scale=640:-2,tile=5x1" -frames:v 1 trabalho/<slug>/rastro_prova.jpg
   ```
5. Se o script sair com **código 2** ("PERDIDO em T s"), o objeto foi coberto, saiu de quadro ou houve corte. O rastro vale até ali: encurte `--fim` ou rode de novo a partir daquele instante com uma caixa nova, e junte os dois `.ass`.

## Parâmetros
| Parâmetro | Padrão | Quando mudar |
|---|---|---|
| `--ancora` | `cima` | `baixo`, `esquerda`, `direita` se a etiqueta cobrir algo importante; `centro` para colar em cima do objeto |
| `--tamanho` | 0,035 da altura | menor em vídeo horizontal com muito detalhe; maior em vertical |
| `--seta` | desligada | triângulo apontando para o objeto (âncora `cima` ou `baixo`) |
| `--sem-escala` | a etiqueta cresce com o objeto | texto de tamanho fixo quando o objeto se aproxima muito |
| `--girar` | desligado | a etiqueta gira com o objeto (placa, tela, caixa) |
| `--suavizar` | 5 quadros | 1 se a etiqueta "atrasar" em movimento brusco; 9 se tremer |
| `--cor`, `--font`, `--marca` | acento e fonte da marca, senão amarelo e DejaVu Sans | — |

Usar só a posição: o `.rastro.json` serve a qualquer outra composição (um overlay do ffmpeg, uma cena do Manim). Cada quadro traz `t`, `cx`, `cy`, `escala`, `rot` e os quatro `cantos`.

## Regras
- Um plano por rastro. Corte de cena encerra o rastro (o script detecta e avisa).
- Região lisa (céu, parede, pele) não tem ponto para seguir: marque uma parte com borda ou textura.
- Segue deslocamento, aproximação e giro no plano da imagem. **Não** corrige perspectiva: texto "deitado no chão" ou colado numa parede em ângulo pede rastreio planar, que o plugin não faz.
- Objeto pequeno sobre fundo que também se move (água, folhagem, multidão) é o caso difícil: confira o fim do trecho no passo 4 e prefira trechos de 2–5 s.
- Texto na tela continua sendo ASS; a legenda vem depois, por cima (`/legenda`).
