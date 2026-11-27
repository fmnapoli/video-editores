---
name: destaques
description: Seleciona os melhores momentos de um vídeo longo pela transcrição, para um alvo de duração ou para extrair N reels, e confere ou monta o arco narrativo em 7 etapas (Backbone). Use para /destaques, "melhores momentos", "resume essa aula em 10 minutos", "transforma essa live num vídeo de 8 minutos", "tira três reels desse vídeo", "corta só as partes boas", "esse vídeo tem começo, meio e fim?", "monta no formato Backbone", "confere o arco do vídeo", "o que falta nesse roteiro".
---

# /destaques — melhores momentos

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`. Script: `${CLAUDE_PLUGIN_ROOT}/scripts/highlights.py`.

## Passos
1. Levante: duração alvo (ou nº de reels e duração de cada), tema/palavras-chave (ou infira do título e do pedido), se a introdução deve ficar (`--keep-intro`).
2. Transcreva com vocabulário do domínio (pule se já houver `trabalho/<slug>/<nome>.transcript.json`):
   ```bash
   uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" originais/IN.mp4 --lang pt --prompt "<vocabulário>" --out-dir trabalho/<slug>
   ```
   Vídeo de 2 h leva ~2,5 h em CPU com `medium`; avise e, se o usuário preferir, use `--model small` para a seleção e refaça só os trechos escolhidos com `medium` para a legenda.
3. Primeira seleção:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/highlights.py" trabalho/<slug>/IN.transcript.json --target 600 --keywords "k8s,container,custo" --keep-intro
   # ou: --reels 3 --reel-len 45
   ```
   Gera `.highlights.json` (`keep`, compatível com `render_spans.sh`) e `.highlights.md` (tabela com todos os blocos e pontuação).
4. **Refine lendo a transcrição**, não só a pontuação: o script é heurístico. Garanta começo, meio e fim coerentes; não corte no meio de um raciocínio; inclua a conclusão. Edite `keep` à mão se precisar e **mostre a lista ao usuário** (tempo, começo da fala) antes de renderizar.
5. Renderize:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/render_spans.sh" originais/IN.mp4 trabalho/<slug>/IN.highlights.json trabalho/<slug>/<slug>_destaques.mp4
   ```
   Para reels, renderize cada janela separadamente (um `keep` com um trecho por arquivo) e siga com `/ganchos`, `/lettering`, `/legenda` em 9:16 (`crop` central: `-vf "crop=ih*9/16:ih"`).
6. Transições entre trechos distantes: um `xfade` de 0,25 s ou um corte seco com B-roll/lettering disfarça o salto. Sugira `/trilha` com ducking para cobrir mudanças de ambiente.

## Com arco narrativo (Backbone)

Use quando o vídeo ensina ou convence (aula, reels, apresentação) e o pedido é um corte **com começo, meio e fim**, ou quando o usuário quer saber o que falta no vídeo. Não use em tutorial de tela nem em documentação: ali o corte por pontuação acima é o caminho. Script: `${CLAUDE_PLUGIN_ROOT}/scripts/backbone.py`. A estrutura é de Letícia Pacheco (@leticiapachecovoz); cite a autora se o usuário perguntar de onde vem.

| Etapa (chave) | O trecho responde |
|---|---|
| Desafio (`desafio`) | Que problema é este, e por que ele incomoda? |
| Identificação (`identificacao`) | Onde quem assiste se reconhece nisso? |
| Causa (`causa`) | Por que isso acontece, e com que base se afirma? |
| Solução (`solucao`) | O que resolve, e o que mostra que resolve? |
| Método (`metodo`) | Quais são os passos, na ordem em que se faz? |
| Motivação (`motivacao`) | Que resultado dá vontade de agir agora? |
| Conclusão (`conclusao`) | Com que frase e com que energia o vídeo termina? |

1. Divida a transcrição em blocos:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backbone.py" blocos trabalho/<slug>/IN.transcript.json --keywords "k8s,custo"
   ```
   Gera `IN.backbone.json`: cada bloco com `sugestao` (heurística por palavras e posição) e `etapa` vazia.
2. **Leia cada bloco e preencha `etapa`** com uma das sete chaves, ou `"fora"` para o que não entra no arco (saudação, recado, repetição). A sugestão erra: quem decide é a leitura. Um bloco que mistura duas etapas fica com a que ocupa mais tempo; se a mistura atrapalhar, refaça o passo 1 com `--max-block` menor.
3. Gere o relatório e **mostre ao usuário**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backbone.py" relatorio trabalho/<slug>/IN.backbone.json
   ```
   `IN.backbone.md` diz quais etapas faltam, quanto tempo cada uma ocupa, se a ordem de aparição é a do arco e onde o tempo está desequilibrado. Se o pedido era só conferir o vídeo, pare aqui. Etapa ausente não se inventa no corte: proponha regravar a fala, cobrir com `/lettering`, ou seguir sem ela.
4. Monte o corte e mostre a lista de trechos (etapa, tempo, começo da fala) antes de renderizar:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backbone.py" montar trabalho/<slug>/IN.backbone.json --target 90
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/render_spans.sh" originais/IN.mp4 trabalho/<slug>/IN.backbone.keep.json trabalho/<slug>/<slug>_arco.mp4
   ```
   Entra pelo menos um bloco de cada etapa presente; o alvo é repartido por etapa (`--pesos "metodo=0.4"` muda a divisão). Os trechos ficam na ordem da gravação. `--reordenar` põe na ordem do arco: só com o aval do usuário, e depois de ler os avisos de inversão, porque um trecho deslocado pode citar algo que ainda não foi dito.
5. Siga com `/ganchos` (a etapa Desafio é a matéria-prima do gancho), `/camera`, `/legenda` e `/prova`.

## Regras
- O usuário aprova a lista de trechos antes do render.
- No arco, a etapa de cada bloco é decidida lendo a fala; nunca rode `relatorio` ou `montar` com `--usar-sugestao` para entregar.
- Nunca inverta a ordem cronológica sem avisar (exceto quando o pedido é um gancho antecipado).
