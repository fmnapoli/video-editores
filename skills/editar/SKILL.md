---
name: editar
description: Ponto de entrada em linguagem natural para editar um vídeo. Use quando o pedido for livre ou combinar várias coisas ("edita esse vídeo pra Reels", "corta as pausas e legenda", "edita pro YouTube com os melhores momentos e põe música", "deixa com cara de capa de revista", "edição completa"), ou quando não estiver claro qual skill específico usar. Monta o plano a partir do catálogo de estilos, executa com os pontos de aprovação e entrega o relatório de edição.
---

# /editar — do pedido ao vídeo pronto

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`. Catálogo de pedidos: `${CLAUDE_PLUGIN_ROOT}/docs/pedidos-prontos.md`. Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## 1. Entenda o pedido (sem perguntar o que dá para inferir)
Extraia do pedido e do arquivo:
- **destino**: Reels/Shorts/TikTok (9:16, 20–90 s), YouTube (16:9), aula, anúncio, documentação (→ `/video-docs`);
- **estilos** pedidos, usando a tabela abaixo;
- **limites**: duração alvo, o que não cortar, idioma, vocabulário técnico (peça só se o vídeo for técnico e nada tiver sido dito).
Se faltar algo que muda o resultado (ex.: música sim ou não), pergunte **uma** vez, com opções.

| Se o usuário disser… | Skills, nesta ordem |
|---|---|
| corta pausas / tomadas / "limpa" | tomada → corte |
| legenda / "palavra por palavra" | legenda |
| gancho / "abre forte" | ganchos → lettering (titulo, pop) |
| frase atrás de mim / palavra de impacto | texto-atras |
| checklist / passos na tela | checklist |
| responde comentário / cartão / painel | lettering (cartao) |
| capa de revista | lettering (capa) |
| tela dividida / reação / antes e depois | tela-dividida |
| recorta / troca cenário / neon | tela-verde |
| animação / explica com motion | animacao |
| 3D | 3d |
| melhores momentos / resumo / "aula de 2 h em 10 min" / "tira N reels" | destaques |
| música / trilha / "onde não falo põe música" | trilha |
| efeitos sonoros / whoosh | efeitos |
| igual esse vídeo | referencia primeiro |
| "edição completa" (Reels) | tomada → corte → ganchos → lettering → legenda → trilha → efeitos → prova |
| "edição completa" (YouTube longo) | destaques → corte → lettering → legenda → trilha → prova |
| "refaz a aula" / "cenário novo + diagramas animados" / "mais profissional, com capítulos" (aula gravada com quadro e IDE) | videoaula |
| "mostra a partitura do que ele toca" / "exemplo tocado" / "notação com R e L" (bateria) | partitura (depois video-animado ou videoaula para montar) |

## 2. Prepare o projeto
`originais/` (bruto intocado), `trabalho/<slug>/`, `saida/`, `legendas/`. Slug = nome curto do arquivo, sem espaço.

## 3. Execute com os gates
Rode cada skill da lista. **Pare e mostre** antes de: descartar tomadas, queimar legenda (texto revisado), render longo (3D, texto-atrás, IA) e entregar. Entre etapas, uma linha de progresso em linguagem simples, no padrão do relatório abaixo.

## 4. Relatório de edição (sempre, ao final)
```
Ouvi a gravação: 1:24, 212 palavras.
Achei 6 pausas longas e 2 tomadas repetidas; tirei. Ficaram 0:44.
Gancho na tela nos 2,5 s iniciais: "Como eu edito em 4 minutos".
Legenda palavra por palavra (3 por bloco), 2 termos corrigidos: kubectl, ArgoCD.
Trilha "lofi-01" com ducking; -14 LUFS.
Entregue: saida/<slug>.mp4 (1080x1920, 0:44) · legendas/<slug>.srt · trabalho/<slug>/<slug>.proof.jpg
Para ajustar: diga o que mudar (ex.: "mantém a primeira tomada da frase X", "legenda menor").
```
Números vêm dos scripts (`takes.py`, `auto-editor`, `ffprobe`, `proof.txt`), nunca estimados.

## 5. Ajustes
Pedidos de ajuste refazem só a etapa afetada a partir do intermediário anterior em `trabalho/<slug>/`, nunca do zero.
