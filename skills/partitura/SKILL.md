---
name: partitura
description: Partitura de bateria na tela e "exemplo tocado" — transcreve um groove ou exercício para um padrão compacto, renderiza a notação (Verovio) com manulação R/L e cores por membro, sintetiza o som e anima a partitura nota a nota com cursor e contador, pronto para entrar como bloco num vídeo. Use para /partitura, "mostra a partitura do que ele está tocando", "exemplo tocado", "notação com R e L", "anima o groove", "partitura de bateria para o vídeo".
---

# /partitura — notação de bateria e exemplo tocado

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: ffmpeg e `uv` (Verovio, resvg, numpy, scipy, Pillow e librosa chegam pelo `uv run --with`; nada de sistema). Scripts em `${CLAUDE_PLUGIN_ROOT}/skills/partitura/scripts/`, modelo em `templates/padroes-exemplo.json`.

Validado em nov/2026 num curso de bateria de 19 min (12 padrões em 4/4, 5/4 e 7/4, um exemplo tocado antes de cada clipe gravado).

## O que entra e o que sai
- **Entra**: o que a pessoa toca (clipe gravado, descrição falada ou escrita, foto de caderno) e, quando houver, o andamento. Com clipe gravado, o andamento se **mede** (`andamento.py`), não se chuta: exemplo em andamento diferente do clipe soa como outro exercício, mesmo com a partitura certa.
- **Sai** em `trabalho/<slug>/`:
  - `padroes.json`: a transcrição em padrão compacto, revisável por quem toca;
  - `partituras/<ID>.png` (cartão 1800×270, para sobrepor num clipe) e `<ID>_big.png` (1800×430, para o exemplo tocado), com `<ID>[_big].json` trazendo a posição de cada nota e de cada tempo;
  - `exemplos/<ID>.mp4` + `<ID>.wav`: exemplo tocado (1920×1080, som sintetizado, nota acendendo quando soa, cursor e contador), com a mesma duração no vídeo e no áudio: entra em qualquer EDL sem ajuste.

## Passos

1. **Transcrever (GATE 1: a pessoa que toca aprova).** Escreva `trabalho/<slug>/padroes.json` a partir do modelo. Um padrão por exercício:
   ```json
   {"id": "PARA", "titulo": "Paradiddle aplicado", "sub": "R no chimbal, L na caixa · bumbo na 2ª nota",
    "ts": [4, 4], "div": 4,
    "hh": "X.xx .x.. X.xx .x..", "sn": ".x.. x.xx .x.. x.xx", "bd": {"pos": [2]},
    "stick": "RLRR LRLL RLRR LRLL"}
   ```
   `ts` é a fórmula de compasso, `div` as subdivisões por tempo (1, 2 ou 4). Instrumentos: `hh` chimbal, `ride`, `crash`, `sn` caixa, `tom`, `ft` surdo, `bd` bumbo, `hf` chimbal de pé. Cada um aceita grade em texto (`x` toca, `X` toca com acento, `.` silêncio; um caractere por subdivisão), `{"pos": [1, 2, 3]}` (posições dentro de cada tempo), lista de índices da grade ou `"all"`. `stick` é a manulação: texto com uma letra por subdivisão, `"alterna"` (R L R L…) ou `{índice: "R"|"L"}`. Transcrevendo de um clipe, use a transcrição e o áudio como no `/videoaula` (`transcribe.py` para a fala; a distribuição dos ataques confirma a condução). Anote no roteiro toda interpretação que não estiver explícita na fala ("1-2-3 = semicolcheias 1, 2 e 3 de cada tempo"): a lista vai para a pessoa aprovar **antes** de gerar qualquer vídeo, porque partitura errada ensina errado.
2. **Renderizar e olhar.**
   ```bash
   uv run --with verovio --with resvg-py --with pillow python "${CLAUDE_PLUGIN_ROOT}/skills/partitura/scripts/partitura.py" trabalho/<slug>/padroes.json --out trabalho/<slug>/partituras
   ```
   Abra cada `_big.png` com Read: beams por tempo, R azul e L rosa sob as notas, bumbo laranja, chimbal de pé verde, acento `>`. Compassos renderizados: 2 (4 quando `div` = 1); mude com `--compassos`. Título com a fonte do projeto: `--fonte caminho.ttf` (padrão Inter, DejaVu Sans Bold ou Arial Bold).
3. **Andamento e fase do clipe** (sempre que o exemplo antecede um clipe gravado ou o cursor vai correr sobre ele):
   ```bash
   uv run --with librosa --with numpy --with scipy --with soundfile python "${CLAUDE_PLUGIN_ROOT}/skills/partitura/scripts/andamento.py" originais/clipe.mp4 --ini 4 --fim 40 --tempos 5 --bumbo 0 --out trabalho/<slug>/beats/beats.json
   ```
   `bpm` é a mediana dos intervalos entre batidas (é o que vai no `--bpm` do passo seguinte). `--tempos` (tempos por compasso) e `--bumbo` (posições em que o bumbo toca, pelo `padroes.json`; `0` é o "1") escolhem o "1" pela energia grave e dizem se a fase é `confiavel` (contraste ≥ 1,3 e a segunda melhor fase pelo menos 10 % atrás); `uns` são os instantes do "1". Restrinja ao trecho em que a pessoa toca o exercício (`--ini/--fim`): fala e contagem confundem o tracker. **Confira a oitava**: o tracker pode entregar a metade ou o dobro (caso real: 5/4 medido a 112 bpm por um prior preso, quando a pessoa contava "1 2 3 4 5" a 0,36 s por tempo, 168 bpm). Compare com a contagem falada na transcrição e force a faixa com `--faixa 140-200` se preciso.
4. **Exemplo tocado.** No andamento medido quando há clipe. Lento para estudo (66–80 bpm; 90–100 para grooves de semínimas) só sem clipe, ou quando a pessoa pedir uma versão de estudo além da real. `--voltas 2` e `--contagem` quando o padrão abre um capítulo:
   ```bash
   uv run --with numpy --with scipy --with pillow python "${CLAUDE_PLUGIN_ROOT}/skills/partitura/scripts/tocar.py" PARA --partituras trabalho/<slug>/partituras --out trabalho/<slug>/exemplos --bpm 72 --voltas 2 --contagem --fundo trabalho/<slug>/identidade/fundo.png
   ```
   Ouça o `.mp4` (ou mande o preview) e confira um quadro no meio (`ffmpeg -ss T -i … -frames:v 1 q.jpg`): a nota que acende tem de ser a que soa. O áudio sai com pico a −6 dBFS e sem conteúdo acima de 15 kHz; a normalização final é da montagem.
5. **Montar.** Três caminhos:
   - **`/video-animado`**: o exemplo é uma cena com áudio próprio: `{"id": "EX1", "video": "trabalho/<slug>/exemplos/PARA.mp4", "audio": "trabalho/<slug>/exemplos/PARA.wav", "volume": 0.7}`; o `tts_cenas.py` pega a duração do wav e o `montar_cenas.py` usa esse áudio no lugar da narração.
   - **`/videoaula`** ou clipe gravado: sobreponha o cartão `<ID>.png` na faixa inferior do clipe (acima da legenda) com `overlay`, e o exemplo tocado entra como bloco antes do clipe. Contador e cursor sincronizados com a pessoa tocando **só** onde o `andamento.py --tempos` deu `confiavel` (energia do bumbo nos tempos fortes, contraste ≥ 1,3), usando `beats`, `fase` e `uns` do JSON; em dúvida, cartão estático: melhor não mostrar do que mostrar errado.
   - **Avulso**: `exemplos/<ID>.mp4` já tem áudio; passe pelo `/prova` antes de entregar.
6. **Entrega.** `padroes.json` e a lista de interpretações aprovadas vão junto do vídeo (`README.md` do projeto ou `COMO-FOI-FEITO.md`), com o comando de regenerar cada peça.

## Parâmetros

| Onde | Padrão | Quando mudar |
|---|---|---|
| `partitura.py --tamanho` | `ambos` | `card` só para sobrepor em clipe; `big` só para o exemplo tocado |
| `partitura.py --compassos` | 2 (4 se `div` = 1) | 1 para um cartão curto; mais compassos encolhem a notação |
| `andamento.py --ini/--fim` | clipe inteiro | o trecho em que a pessoa toca o exercício; fala e contagem no início confundem o tracker |
| `andamento.py --faixa` | 70-160 | bpm fora da faixa é dobrado/dividido; estreite (`140-200`) quando a contagem falada mostrar que o tracker caiu na oitava errada |
| `andamento.py --tempos` / `--bumbo` | desligado | ligar para achar o "1" (fase) quando o cursor ou o contador vão correr sobre o clipe; `--bumbo` pelo `padroes.json` |
| `tocar.py --bpm` | 72 | o `bpm` do `andamento.py` quando o exemplo antecede um clipe; 66–80 só para versão de estudo sem clipe |
| `tocar.py --voltas` | 2 | 1 em padrões longos (7/4 com 4 compassos), 3–4 para looping de estudo |
| `tocar.py --contagem` | desligado | ligar quando o exemplo abre um capítulo ou muda de fórmula |
| `tocar.py --fundo` | gradiente escuro | o `fundo.png` da identidade do projeto |
| `tocar.py --rotulo` / `--titulo` | "Exemplo tocado" / título do padrão | rótulo do capítulo, título traduzido |

## Regras

- Nada de material protegido na tela: páginas de método e play-alongs comerciais não aparecem nem tocam. Ritmos não são protegidos: renote com `padroes.json` e cite a fonte como referência recomendada.
- Toda interpretação da fala do músico ("na primeira, na terceira") vira item de uma lista a confirmar; a partitura só vai para o vídeo depois do aceite.
- Cores fixas no plugin: R azul `#2563EB`, L rosa `#DB2777`, bumbo laranja `#EA580C`, chimbal de pé verde `#059669`; a legenda de cores do exemplo tocado é gerada pelo próprio script. Não reinvente a convenção entre vídeos do mesmo autor.
- Um padrão = um compasso repetido. Frase de 2 compassos diferentes = dois padrões (A e B) ou um `ts` dobrado; tercinas (`div` = 3) não são suportadas.
- Só bateria. Instrumento com altura (baixo, piano) pede notação na pauta com clave e um sampler, fora desta skill; registre o pedido em vez de improvisar com a síntese de bateria.
- Nada é "pronto" sem o `/prova`: o exemplo tocado tem bateria sintetizada com bandas de ruído, exatamente o material em que o AAC com PNS estourou o pico (por isso toda entrega do núcleo codifica com `-aac_pns 0`).

## Identidade do projeto
Havendo `marca/marca.json` (skill `/marca`), os rótulos usam a fonte bold da marca e o `tocar.py` usa `fundos.cartela` como fundo quando não há `--fundo`. As cores por membro não mudam: são código de leitura, não identidade.
