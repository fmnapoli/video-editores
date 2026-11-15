---
name: ler-tela
description: Lê o texto que está na tela (OCR local) de um print ou de um quadro do vídeo e devolve a posição de cada palavra, para o destaque cair no lugar certo e a tarja cobrir o dado sensível. Use para /ler-tela, "destaca o botão Salvar", "marca essa frase do print", "sublinha o nome do arquivo na tela", "onde está escrito X", "põe tarja nos e-mails", "esconde o CPF da gravação", "OCR".
---

# /ler-tela — achar o texto na tela e marcar no lugar certo

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/ler_tela.py` (RapidOCR com modelos PP-OCR, Apache-2.0, em CPU; lê português com acento). As formas saem em ASS.

## Passos
1. Levante: a fonte (print `.png/.jpg` ou vídeo + instante `--t`), o texto a marcar e o estilo.
2. Leia a tela e confira o que foi lido (a primeira execução baixa os pacotes, ~100 MB):
   ```bash
   uv run --with rapidocr --with onnxruntime python "${CLAUDE_PLUGIN_ROOT}/scripts/ler_tela.py" IN.mp4 --t 12.4
   ```
   Gera `IN_12.4s.ocr.json`: linhas e palavras com caixa em fração da imagem e confiança. Linha com confiança abaixo de ~0,8 pode estar errada: olhe o quadro.
3. Marque. Intervalo padrão: de `--t` até `--t` + 3 s (ajuste com `--inicio`/`--fim` para o tempo em que a frase é falada, tirado do `.transcript.json`).
   ```bash
   uv run --with rapidocr --with onnxruntime python "${CLAUDE_PLUGIN_ROOT}/scripts/ler_tela.py" IN.mp4 --t 12.4 \
     --achar "Salvar alterações" --estilo marca --inicio 12.4 --fim 15 --burn trabalho/<slug>/<slug>_destaque.mp4
   ```
4. **Tarja de privacidade**: por expressão regular, cobrindo o vídeo inteiro quando não há `--inicio`/`--fim`.
   ```bash
   uv run --with rapidocr --with onnxruntime python "${CLAUDE_PLUGIN_ROOT}/scripts/ler_tela.py" IN.mp4 --t 3 \
     --regex '[\w.+-]+@[\w-]+\.[\w.]+' --estilo tarja --burn trabalho/<slug>/<slug>_tarja.mp4
   ```
   Mostre ao usuário a lista do que foi coberto e um quadro do resultado **antes** de seguir: tarja é gate.
5. Se sair com código 1 ("NÃO ENCONTRADO"), o script lista o que leu: ajuste o texto de `--achar` ao que está na tela, ou mude `--t` para um quadro em que o texto já apareceu.

## Estilos
| `--estilo` | Visual | Uso |
|---|---|---|
| `marca` | marca-texto translúcido que entra da esquerda para a direita | frase num print, linha de código, valor numa tabela |
| `caixa` | moldura em volta | botão, campo, item de menu |
| `sublinhado` | traço embaixo | nome de arquivo, termo dentro de um parágrafo |
| `tarja` | retângulo opaco, sem animação | e-mail, CPF, token, nome de cliente |

`--achar` não diferencia maiúscula nem acento e pega a primeira ocorrência (`--todos` pega todas); pode repetir. `--regex` pega todas. Cor: acento da marca, senão amarelo; `--cor "#RRGGBB"` troca (a tarja é preta por padrão). `--folga` controla a margem em volta do texto.

Padrões úteis para `--regex`: e-mail `[\w.+-]+@[\w-]+\.[\w.]+` · CPF `\d{3}\.\d{3}\.\d{3}-\d{2}` · telefone `\(?\d{2}\)?\s?9?\d{4}-?\d{4}`.

## Regras
- A caixa vale para o quadro lido. Em gravação de tela com rolagem ou troca de página, marque só o intervalo em que a tela está parada; para outro trecho, rode de novo com outro `--t`.
- **A tarja por OCR não substitui a revisão**: o OCR pode não ler texto pequeno, borrado ou parcialmente coberto. Depois de tarjar, passe a `/prova` e olhe os quadros; o que escapou, tarje pela posição com `/lettering` ou corte o trecho.
- Texto que se move com um objeto é caso do `/rastrear`, não deste skill.
- A legenda vem depois, por cima (`/legenda`).
