---
name: lettering
description: Adiciona textos estilizados na tela (títulos, palavras-chave, call-outs, lower thirds, cartão de comentário, capa de revista) com animação (fade, pop, slide) via ASS/libass. Use para /lettering, "coloca um título", "texto na tela", "destaca essa palavra", "lower third com meu nome", "responde esse comentário com um cartão", "cara de capa de revista".
---

# /lettering — texto na tela (ASS, sem drawtext)

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Mesma escolha do `video-docs`: texto em ASS/libass, porque o ffmpeg estático não tem `drawtext`. Script: `${CLAUDE_PLUGIN_ROOT}/scripts/lettering_ass.py`.

## Passos
1. Levante com o usuário: texto, momento, estilo e animação. Se ele disser "quando eu falar X", ache o tempo da palavra no `IN.transcript.json` (gere com `/tomada` ou `/legenda` se não houver).
2. Escreva `textos.json`:
   ```json
   [
     {"text": "COMO EU CORTO 80% DO TEMPO", "start": 0.3, "end": 2.8, "style": "titulo", "anim": "pop"},
     {"text": "Fabrizio Napoli\\NPlatform Engineer", "start": 4, "end": 8, "style": "lower", "anim": "slide"},
     {"text": "SEM VENDOR LOCK-IN", "start": 12.1, "end": 13.6, "style": "destaque", "anim": "fade"}
   ]
   ```
   - `style`: `titulo` (topo, branco), `destaque` (amarelo, 30% da altura), `lower` (caixa translúcida, canto inferior esquerdo), `cartao` (cartão branco no topo para responder comentário ou painel flutuante; campo extra `autor` para a linha "@usuário"), `capa` (moldura na borda + título grande no terço inferior, estilo revista; campo extra `kicker` para a linha pequena acima).
   - `anim`: `pop`, `fade`, `slide`, `none`. Opcionais: `pos` `[x, y]` em fração da tela, `size` (fração da altura), `color` `#RRGGBB`.
   - `\\N` quebra linha.
3. Gere e queime:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lettering_ass.py" IN.mp4 textos.json --font "DejaVu Sans" --burn IN_lettering.mp4
   ```
   A fonte é o nome da família instalada (`fc-list : family`). Montserrat e Inter (OFL) ficam boas em reels.
4. Rode `/prova` e confira se o texto não cobre o rosto nem a legenda (no estilo reels a legenda fica entre ~55% e ~65% da altura; no clássico, no rodapé). Em vídeo gravado no celular, o script já considera a rotação do arquivo.

## Combinando com /legenda
Queime o lettering **antes** da legenda, para a legenda ficar por cima. Ou junte os dois num filtro só: `-vf "ass=textos.ass,subtitles=IN.words.srt:force_style=..."`.

## Identidade do projeto
Havendo `marca/marca.json` (skill `/marca`), a fonte e as cores dos presets vêm dela (`titulo`, `lower` e `capa` na cor de texto, `destaque` no acento), e a fonte entra por arquivo, sem instalar, sem parâmetro extra. Parâmetro explícito vence a marca; `--marca CAMINHO` aponta outra e `--marca nao` volta ao padrão do plugin.
