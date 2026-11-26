---
name: camera
description: Movimento de câmera sobre o vídeo já cortado — troca de plano (aberto/fechado) a cada corte para esconder o jump cut, aproximação lenta, punch na palavra de ênfase e plano fechado centrado no rosto. Use para /camera, "põe zoom nos cortes", "disfarça os cortes com zoom", "punch-in", "dá um zoom quando eu falo X", "câmera mais dinâmica", "a câmera segue meu rosto".
---

# /camera — zoom e troca de plano sobre o corte

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/camera.py`. Planeja (só biblioteca padrão) e aplica (OpenCV) em dois passos, com o `.camera.json` revisável no meio.

**Onde entra:** depois do `/tomada` e do `/corte`, **antes** de qualquer texto queimado (`/lettering`, `/legenda`, `/checklist`). Texto queimado antes ganharia zoom junto com a imagem.

## Passos
1. Junte de onde vieram os cortes, na ordem em que as etapas rodaram:
   - `/tomada`: o `trabalho/<slug>/IN.takes.json`;
   - `/corte`: o JSON v1 do auto-editor. Se ainda não existe, gere com **os mesmos parâmetros** do corte, trocando só a saída:
     ```bash
     auto-editor "ENTRADA_DO_CORTE.mp4" --edit audio:threshold=0.04 --margin 0.15s --no-open --export v1 --output "trabalho/<slug>/<slug>_corte.v1.json"
     ```
   O vídeo de entrada da câmera é a saída da **última** etapa (`<slug>_corte.mp4`).
2. Localize o rosto no vídeo cortado (para o plano fechado enquadrar a pessoa, não o centro do quadro). Passe `--out`: sem ele o `rostos.py` grava em `trabalho/<nome do vídeo>/`, outra pasta:
   ```bash
   uv run --with opencv-python-headless --with numpy python "${CLAUDE_PLUGIN_ROOT}/scripts/rostos.py" trabalho/<slug>/<slug>_corte.mp4 \
     --out trabalho/<slug>/<slug>_corte.rostos.json
   ```
3. Punches (opcional). Escolha pela transcrição do vídeo **cortado** as palavras de ápice, no máximo uma a cada ~20 s, e grave `trabalho/<slug>/punches.json` com o instante em que a palavra começa:
   ```json
   [{"t": 12.34, "forca": 0.06, "texto": "impossível"}]
   ```
4. Planeje e **mostre a lista ao usuário** (gate):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/camera.py" trabalho/<slug>/<slug>_corte.mp4 \
     --cortes trabalho/<slug>/IN.takes.json --cortes trabalho/<slug>/<slug>_corte.v1.json \
     --rostos trabalho/<slug>/<slug>_corte.rostos.json --punches trabalho/<slug>/punches.json
   ```
   Sai `<slug>_corte.camera.json` e a lista numerada (`cam01`…, `p01`…). Resolva todo `AVISO` antes de seguir.
5. Ajustes pedidos por número ("cam07 aberto", "tira o p02", "cam04 menos zoom") são edições no `.camera.json`: `plano`/`escala` do plano, `foco` (`[x, y dos olhos]` em fração do quadro), remover o punch. Não replaneje: replanejar apaga os ajustes.
6. Aplique (rode em segundo plano se o vídeo passar de ~5 min):
   ```bash
   uv run --with opencv-python-headless --with numpy python "${CLAUDE_PLUGIN_ROOT}/scripts/camera.py" trabalho/<slug>/<slug>_corte.mp4 \
     --aplicar trabalho/<slug>/<slug>_corte.camera.json trabalho/<slug>/<slug>_camera.mp4
   ```
7. **Olhe antes de seguir**: um quadro do meio de dois ou três planos fechados (Read). Confira os olhos no terço de cima, a cabeça sem encostar na borda e nenhum corte no queixo.
   ```bash
   ffmpeg -ss T -i trabalho/<slug>/<slug>_camera.mp4 -frames:v 1 trabalho/<slug>/cam_T.jpg
   ```
8. Siga com `/lettering` e `/legenda` sobre o `_camera.mp4`. O `/efeitos` lê o mesmo `.camera.json` (`--eventos`) para pôr som só nas trocas de plano e nos punches.

## Parâmetros
| Parâmetro | Padrão | Quando mudar |
|---|---|---|
| `--fechado` | 1.18 | 1.10–1.15 para aula e conteúdo calmo; até 1.25 se a gravação for 4K e a entrega 1080p |
| `--deriva` | 0.03 | aproximação lenta em cada plano; 0 desliga (vídeo institucional); 0.05 para mais energia |
| `--olhos` | 0.38 | altura dos olhos no plano fechado; suba para 0.42 se cortar o topo da cabeça |
| `--min-plano` | 0.8 s | trecho mais curto que isto não troca de plano (duas trocas seguidas piscam) |
| `--comeca` | `aberto` | `fechado` para abrir já no close |
| `--seguir` | desligado | o plano fechado acompanha o rosto quando a pessoa se mexe muito |
| `--cortes-em T,T` | — | instantes dos cortes direto no tempo do vídeo, quando não há arquivo de corte |

## Regras
- É para **pessoa falando em quadro cheio**. Em gravação de tela com webcam no canto, o plano fechado vai atrás do rosto e corta o conteúdo: o script avisa; não aplique (ou use `--fechado 1`, que deixa só a aproximação lenta e os punches).
- A troca de plano cai no **quadro exato** do corte, calculado dos arquivos de corte. Se o script avisar que a soma dos quadros não bate com o vídeo, os arquivos não são os desse vídeo: não aplique.
- Todo corte muda de plano; por isso jump cut vira troca de enquadramento. Não "corrija" dois planos iguais em sequência pondo punch em cima do corte.
- Punch é ênfase, não enfeite: poucos, nas palavras que carregam a ideia. Sob tela cheia (B-roll, animação) a câmera não aparece: não gaste punch ali.
- O zoom amplia a imagem gravada. Acima de 135% do original o script avisa; a saída tem a resolução da entrada.
- Vídeo de taxa de quadros variável (celular, captura de tela): converta antes para taxa constante, ou os planos saem deslocados.
- Nunca sobrescreva a entrada; saída sempre `trabalho/<slug>/<slug>_camera.mp4`.
