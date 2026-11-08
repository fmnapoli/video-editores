---
name: video-docs
description: Use quando pedirem para transformar gravações de tela brutas (demos, tours de portal, Vimeo/OBS) em vídeos curtos de documentação — com corte de tempo morto, narração sintetizada (edge-tts), legenda queimada, balões/setas de destaque e cartela de título — ou quando precisar transcrever gravações com timestamps, inventariar o que cada gravação mostra, escrever roteiros por ação e revisar a narração contra o código-fonte antes de publicar.
---

# Vídeos de documentação a partir de gravações brutas

No plugin: scripts desta skill em `${CLAUDE_PLUGIN_ROOT}/skills/video-docs/scripts/`; atalho de montagem `${CLAUDE_PLUGIN_ROOT}/scripts/render-docs.sh <spec.json>`. Convenções compartilhadas: `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`.

## Princípio

A gravação bruta é **fonte**, não produto: o áudio original sai, a tela fica. O que
chega ao espectador é narração reescrita (sintetizada), legenda alinhada por palavra,
balões apontando o que importa e só os segundos em que algo acontece na tela.
Três gates humanos: inventário, roteiros, piloto. **Nada é cortado antes do inventário
aprovado; nada é produzido em lote antes do piloto aprovado.**

E uma regra aprendida a duro: **a fala do bruto não é verdade.** Quem gravou improvisa
e erra (semântica de campos, restrições que não existem). Antes de produzir, cada
afirmação do roteiro é conferida com o código/doc que implementa a tela, e a narração
segue o código. Ver `references/revisao-coerencia.md`.

## Quando usar

- "transforma essas gravações em vídeos de documentação", "um vídeo por ação"
- "transcreve e inventaria o que tem nessas gravações"
- "escreve o roteiro e a legenda", "faz o piloto e para"
- "revisa o vídeo pronto e corrige os destaques"

**Não use para:** gravar de novo (isso é roteiro de gravação), editar
áudio original, ou vídeo com a voz do próprio apresentador.

## Ferramentas (validadas em out/2026, Ubuntu 26.04)

| Função | Ferramenta | Observações |
|---|---|---|
| Transcrição | `whisper-ctranslate2` (uv tool), modelo `medium`, CPU int8 — ou `${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py` (mesmo motor, mesmo padrão `medium` + `--prompt`) | `--vad_filter True --initial_prompt "<vocabulário do domínio>"`; ~1,2× tempo real. `small` erra termos de domínio. Validar em 60 s antes do lote. |
| Voz | `edge-tts` 7.x, `pt-BR-ThalitaMultilingualNeural` (padrão, escolhida de ouvido em nov/2026) | Pela API Python com `boundary="WordBoundary"` (timestamps por palavra, usados na legenda). Rodar com `uv run --with edge-tts --with pillow`. |
| Montagem | `ffmpeg` ≥ 6 com libass (o do apt serve) | Usa `subtitles`/`ass`, `tpad`, `gradients`, `drawgrid`, `xstack`, `loudnorm`. **Não depende de `drawtext`** (o build estático do johnvansickle não tem): título e balões vão em ASS. |
| Medir texto | Pillow + `DejaVuSans-Bold.ttf` | Para dimensionar balões no ASS. |
| Montador | `scripts/build.py` desta skill | spec JSON → mp4 + srt + roteiro gerado. |

### Pronúncia de termos em inglês

A voz padrão, `pt-BR-ThalitaMultilingualNeural`, fala português e **pronuncia termos em
inglês nativamente** ("deploy", "dashboard", "rollback"). Foi escolhida por comparação de
ouvido contra a `pt-BR-FranciscaNeural` com grafia fonética. Escreva os termos normalmente,
na legenda e no `tts`.

- Sem `tts` na cena, a voz lê os blocos de `legend`. Só escreva `tts` quando a fala
  precisar ser diferente da legenda.
- Se a voz errar um termo específico do projeto (nome de produto, comando, sigla), corrija
  só ele no spec: `"glossary": {"kubectl": "cube control"}` (ou caminho de JSON). A troca
  vale só para o texto falado; a legenda mantém a grafia normal. Pronúncia `""` remove.
- Siglas (chave toda em maiúsculas) casam só em maiúsculas; o resto ignora caixa. Plural
  com "s" herda a pronúncia. Termos mais longos vencem ("web app" antes de "app").
- O `roteiro-<slug>.md` gerado mostra o texto **efetivamente falado**.
- Ouvir antes do lote: `uv run --with edge-tts python scripts/testar_pronuncia.py "frase com os termos"`
  (gera `pronuncia-cru.mp3` e `pronuncia-glossario.mp3`).
- Voz não multilíngue (`"voice": "pt-BR-FranciscaNeural"`): ela lê inglês como português
  ("deploy" sai "de-plo-i"). Nesse caso o montador carrega sozinho o `glossario-ingles.json`
  (grafia fonética: "diplói", "clôster"; seção `validados` ouvida em produção,
  `nao_validados` não). `"glossary": true` força esse arquivo com qualquer voz;
  `"glossary": false` desliga tudo.
- O whisper **não serve** para validar pronúncia: ele corrige pelo contexto e transcreve
  "deploy" tanto da versão crua quanto da fonética.

## Fluxo

### Etapa 0 — preparação
1. `ffprobe` em cada bruto (resolução, fps, duração). Saída padrão 1280x720/30 fps.
2. Frames a cada 10 s em folhas de contato (`xstack` 4×3) para ler o que cada gravação mostra.
3. Mudanças de tela: `select='gt(scene,0.004)',showinfo` → lista de `pts_time` por bruto
   (0.004 pega digitação; 0.03 só trocas de tela). É com isso que se acham cliques,
   carregamentos e esperas.

### Etapa 1 — inventário (GATE)
- Transcrever com timestamps (`[mm:ss-mm:ss] texto`).
- Segmentar cada gravação em trechos → ação → seção do doc de referência (ou "só novo").
- Registrar duplicatas e o take recomendado, esperas a cortar, e **propor o recorte**
  (um vídeo por ação × um por tema). Entregar `inventario.md` e **parar**.

### Etapa 2 — roteiros (GATE)
Um `roteiro-<slug>.md` por vídeo com: cabeçalho (fonte, trechos, doc, alvo, cartela),
**Cenas** (bruto, tratamento, tela, destaque, narração), **Narração TTS** (glossário
aplicado), **Legenda** (blocos ≤ 2 linhas / ~42 caracteres) e **Cortes**.
Quando o vídeo documenta uma migração, a abertura liga o "antes" ao "depois" ("Antes, … Agora, …").
Ritmo: ~2,7 palavras/s (Thalita e Francisca medidas iguais); narração ocupa 40–60 % do vídeo.
**Antes de mostrar o lote, rodar a revisão de coerência** (`references/revisao-coerencia.md`)
e corrigir pelo código. Mostrar em lote e **parar**.

### Etapa 3 — produção
1. **Piloto** de um vídeo de ponta a ponta; revisar por frames; **parar** para validação.
2. Lote: um spec JSON por vídeo (`references/producao.md` tem o guia completo e o
   formato), `build.py`, revisão por frames, correção, `qa.png`.
3. Checagens: `ffprobe` (1280x720, h264, aac estéreo), duração no alvo, legenda visível
   em 3 frames, destaques no elemento certo **no instante certo**.
4. Status no `inventario.md`; reorganizar a saída (`videos/`, `legendas/`, `roteiros/`,
   `transcricoes/`, `producao/`, `relatorios/`, README). **`.srt` separado do `.mp4`**:
   VLC carrega o sidecar de mesmo nome e dobra a legenda queimada.

## O que o montador faz (`scripts/build.py`)

- Cartela 3,2 s (gradiente navy, título, barra laranja animada, subtítulo).
- Por cena: clipes `[ini, fim, vel]` do bruto; `fit: auto` acelera (≤ 2,2×) ou
  desacelera (≥ 0,7×) a filmagem até casar com a narração; o que sobrar congela.
- TTS por cena (cache por hash do texto); áudio original fora; `amix` + `loudnorm -16 LUFS`.
- Legenda SRT alinhada pelos *word boundaries* do TTS (mapa texto-exibido → texto-TTS
  por sentença); queimada com `force_style` (DejaVu Sans Bold, caixa translúcida).
- Destaques em ASS: chip "n/N · cena" no topo, caixa arredondada laranja, foco
  (escurece o resto), balão escuro com cauda ou seta automática, animação de entrada.
- Exporta `roteiro-<slug>.md` final a partir do spec (narração, legenda, cortes).
- Tarjas (`masks` por cena: retângulo opaco, com rótulo opcional) para e-mail, telefone, CPF, token na URL, caixa de entrada; na última cena valem até o fim do vídeo. A legenda é desenhada por cima das tarjas.
- `"size": [1920,1080]` gera em 1080p mantendo as coordenadas em 1280x720. Cada clipe termina no quadro exato do timeline (sem deriva entre imagem, destaques e tarjas).

## Pegadinhas que custaram tempo

- **Gravação mostrando a si mesma** no início (compartilhamento de tela do próprio
  gravador): cortar os primeiros segundos.
- **Carregamentos**: spinner, modal em branco, página vazia — nunca entram.
- **O instante do clique/colagem não é o que a fala sugere**: conferir frame a frame
  (±1 s) antes de fixar o tempo de um balão. "Conteúdo colado" com campo vazio foi o
  erro clássico.
- **Listas e painéis rolam sozinhos** (ex.: um painel de "últimas ações" ganha entrada de
  outro usuário): a caixa que estava certa em 0:58 está errada em 1:06.
- Coordenadas: extrair frame com `drawgrid=w=100:h=100` e ler; a ferramenta de imagem
  informa o fator de escala quando reduz.
- `ls` pode ser alias de `eza` (vazio fora do terminal): usar `/bin/ls`.
- zsh: `${f%% (720p).mp4}` dá "bad pattern"; escapar `\(`.
- Nomes de arquivo com espaço/parênteses/acento: passar como `-i`, nunca dentro do
  `filter_complex`; manter os caminhos de trabalho em ASCII sem espaço.
- Python que lê downloads: `-I`; não rodar interpretador de dentro de pasta baixada.
- **Dados pessoais na tela** (Gmail, formulários com CPF/telefone, URL com token, seletor de cliente): tarjar com `masks` ou cortar. Conferir em vários quadros por cena: o conteúdo rola.
- **A tela vence a fala e às vezes o próprio código**: aviso na tela que contradiz a narração (ex.: "backup manual de banco não disponível") manda reescrever a narração.
- Narração revisada costuma ser mais curta que o alvo: não esticar com tempo morto.

## Entregáveis

`<slug>.mp4`, `<slug>.srt`, `roteiro-<slug>.md`, `inventario.md`, `revisao-coerencia.md`,
specs JSON de produção, e um resumo de 8–12 linhas para o canal do time com a lista de
vídeos e durações.

Na entrega, manter `.srt` separado do `.mp4` (pastas diferentes).
