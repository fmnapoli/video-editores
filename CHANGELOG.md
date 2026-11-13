# Changelog

## 0.14.0 — 2026-11-13
Integração com o ZCode (desktop z.ai) como 4º agente, e a integração ganha antideriva: port que envelhece em silêncio agora é sintoma com comando de correção (ADR-18).
- **`video-editores integrar zcode`**: skills de usuário em `~/.zcode/skills/` com cabeçalho próprio que traduz o Claude Code para o harness (subagentes → ferramenta Agent, aprovação → AskUserQuestion); em projeto o ZCode já lê `.agents/skills/` e `AGENTS.md`, então o alvo reaproveita esses caminhos; MCP só no escopo global (`~/.zcode/cli/config.json`, `mcp.servers`, formato stdio — schema estrito, sem campo inventado).
- **Integração como registro de dados** (`video_editores/integrar.py`): o que define cada agente (caminhos, writer MCP, cabeçalho, invocação, nota de usuário) mora em uma entrada do `REGISTRO`; alvo novo é uma linha, não um ramo de `if` espalhado por cinco pontos.
- **Antideriva para os quatro agentes**: todo port carimba a versão (`<!-- video-editores:port X.Y.Z -->`) e cada destino ganha o manifesto oculto `.video-editores.json` (versão, agente, escopo, raiz, skills); `integrar --mostrar` compara o instalado com a versão atual e acusa `DESATUALIZADO` com o comando de correção — lendo manifesto ou carimbo, então port feito à mão de versão antiga também é reconhecido; `doctor.sh` ganhou a seção "Integração" com a mesma checagem nas pastas globais.
- **Guarda de procedência**: sobrescrever e remover só toca em portação do plugin; pasta homônima que não é do plugin (o diretório de skills do usuário convive com outros plugins) é preservada e relatada. Falha em uma skill não derruba o relatório (try/except por skill) e o comando sai com erro.
- O bloco de regras gravado nos agentes passou a listar as skills a partir do repositório (a enumeração fixa já estava sem as últimas).
- Testes: guarda de procedência com colisão de nome, status `DESATUALIZADO` via `--mostrar`, ZCode em `HOME` isolado (idempotência, formato stdio preservando servidores de terceiros, remoção limpa, aviso de MCP só global). Docs: ADR-18, agentes.md (tabela de 4 colunas, antideriva, ZCode no MCP e nas limitações), troubleshooting (port órfão e MCP ausente).

## 0.13.0 — 2026-11-12
Geração de imagem por IA, fase 1a do ADR-15, com o ComfyUI como backend. Quem não usa não baixa nada nem precisa de servidor.
- **Papel `imagem`** em `video_editores.modelos` (`VE_IMAGEM`, `get_imagem`), com o backend **`comfyui`**: fala com um servidor ComfyUI à parte pela API HTTP (`/prompt`, `/history`, `/view`), local ou na máquina que tem a GPU (`VE_COMFYUI_URL`, padrão `http://127.0.0.1:8188`). Só biblioteca padrão; o ComfyUI (GPL-3.0) nunca é importado, como ffmpeg e Blender no ADR-05.
- **Workflows versionados no pacote**, só com nós nativos, com marcadores e uma chave `_ve` com modelo, licença, checkpoint e onde baixar. Primeiro: `flux-schnell` (FLUX.1-schnell fp8, pesos Apache-2.0, 4 passos). Workflow próprio por `VE_COMFYUI_WORKFLOW`.
- **`scripts/gerar_imagem.py`** (operação `gerar-imagem`): N variações por semente, folha de escolha com a semente de cada uma e registro `<id>.json` que soma rodadas com prompt, sementes, sha256 do workflow, checkpoint, licença e versão do servidor, para regenerar a escolhida. `--conferir` checa servidor e checkpoint antes de gastar GPU; erros dizem o que fazer (checkpoint ausente com o link, servidor fora, falha do job com a mensagem do nó).
- **`doctor.sh`** mostra o servidor ComfyUI, a GPU dele e o checkpoint do workflow, como item opcional.
- ADR-15 revisto: por que ComfyUI e não `diffusers` (memória e modelos de vídeo em 8–12 GB), regras do backend e a fase 1b (validar com GPU real e então a skill `/gerar`). Docs: núcleo, scripts, convenções (licenças), arquitetura.
- Testes: `nucleo.sh` contra um ComfyUI falso (`tests/stub/comfyui_servidor.py`): variações, folha, registro, workflow preenchido e os quatro erros.

## 0.12.1 — 2026-11-12
- **`render-docs.sh` acusava "fonte DejaVu Sans Bold ausente" com a fonte instalada**, de forma intermitente: com `pipefail`, o `grep -q` fecha o pipe no primeiro acerto e o `fc-list` termina por SIGPIPE, o que derruba o teste. A checagem passou a ler de here-string. Aparece mais em máquina com muitas fontes instaladas.

## 0.12.0 — 2026-11-11
Identidade visual, fases 2 e 3 do ADR-17: todas as skills leem a marca, e a skill `/marca` extrai a identidade de uma fonte externa. Sem `marca/marca.json`, a saída é a de antes.
- **Skill `/marca`** (22ª) e **`scripts/extrair_marca.py`** (operação `extrair-marca`): lê tema de PPTX/POTX/DOCX/DOTX/XLSX (paleta com os slots do tema, fontes de título e corpo, imagens do slide mestre), manual de marca em PDF (HEX e RGB do texto com página e linha, fontes embutidas), pacote de marca em pasta ou zip (SVG, PNG, TTF/OTF com a família real, tokens JSON) e design tokens. Grava `marca/rascunho.json` com a evidência de cada candidato e uma sugestão de papéis; `--gravar-sugestao` escreve um primeiro `marca.json` sem nunca sobrescrever. O fluxo termina na prancha do `validar_marca.py`, que é o ponto de aprovação. URL é recusada: site e Figma ainda não são lidos.
- **`/lettering`, `/checklist` e `/legenda`** (por palavra) tiram fonte e cores da marca quando o parâmetro não é passado, com a fonte entrando por arquivo (`fontsdir`), sem instalar. `--marca CAMINHO` aponta outra marca e `--marca nao` volta ao padrão. Lógica comum em `scripts/marca_cli.py`, que também imprime `force-style` e `fontsdir` para quem monta ffmpeg à mão.
- **`/videoaula`**: `identidade.py` e `publicar_aula.py` usam cores e fonte da marca (`marca_aula.py`); `cores` e `fonte_dir` do `aula.json` continuam vencendo.
- **`/partitura`**: fonte bold da marca nos rótulos e `fundos.cartela` como fundo do exemplo tocado quando não há `--fundo`. As cores por membro não mudam.
- Docs: skill nova em README, skills, pedidos prontos e `/editar`; `extrair_marca.py` e `marca_cli.py` em scripts; seção "Identidade do projeto" nas skills que passaram a ler a marca; ADR-17 com o resultado das fases 2 e 3.
- Testes: `nucleo.sh` (extração de tema, pacote em pasta e zip, PDF e tokens; sugestão aprovada pelo validador; não sobrescreve; site recusado), `smoke.sh` (marca nos scripts de texto e na videoaula), `partitura.sh` (fundo da marca).

## 0.11.0 — 2026-11-11
Identidade visual como contrato único (ADR-17, fase 1). Sem `marca/marca.json`, a saída é a de antes.
- **`video_editores/nucleo/marca.py`**: lê `marca/marca.json` (campo `marca` do spec > `VE_MARCA` > pasta do projeto > padrão), deriva papéis opcionais da própria marca, converte cores para ASS, ffmpeg e Pillow, resolve fonte, logo e fundos, mede contraste WCAG e propõe ajuste mínimo.
- **`scripts/validar_marca.py`** (operação `validar-marca`): erros de contraste (texto < 7, acento < 3 sobre o fundo), fonte sem glifos do português, arquivo ausente; avisos de acento que some em tela clara, logo pequeno, fonte substituta. Gera a **prancha** de aprovação (cartela, faixa, destaque e legenda sobre claro e escuro, encerramento, paleta, tipografia). Nunca altera a cor oficial: só propõe.
- **`/video-docs` lê a marca**: cores, fonte (por arquivo, via `fontsdir`, sem instalar), fundo e logo da cartela, logo da faixa, **tela de encerramento** com o logo (`"encerramento": false` desliga) e **legenda por palavra** dentro do montador (`legenda.estilo: "palavra"`, com `pos`, `tamanho`, `janela`, `max_palavras`, `caixa`, `espaco_largo`). O `palavras.transcript.json` passa a cobrir também as cenas com `tts` próprio (tempo repartido por bloco).
- **`/video-animado`**: o `cena_base.py` lê fonte, cores, fundo e logo do `marca.json` e registra a fonte no Pango.
- `legenda_palavra.py --espaco-largo` (fonte de espaço estreito); `pronuncia.py` não troca termo colado depois de ponto (extensão de arquivo: "arquivo .log").
- Gradiente da cartela com semente fixa: duas montagens do mesmo spec dão os mesmos quadros.
- Aceite: vídeo de um projeto real remontado com o plugin + `marca.json` contra o montador copiado do projeto: SSIM médio 0,993 em 2.520 quadros. O montador copiado deixa de ser necessário.
- Docs: guia do video-docs (identidade, pastas, lote, faixa do navegador), solução de problemas (tabela do `/video-docs` com os sintomas da 0.10.0 e da 0.11.0), pedidos prontos (regravação, identidade), convenções (pasta `marca/`), núcleo, instalação, skills e README.
- Testes: `nucleo.sh` (marca e validador), `smoke.sh` (espaço largo, extensão no glossário), `docs_offline.sh` (determinismo sem marca, marca com legenda por palavra e encerramento, `legenda` e `encerramento` no spec, `"marca": false`).

## 0.10.0 — 2026-11-11
Lições da regravação de um vídeo de ação já publicado (video-docs, num curso de produto) e da comparação com o montador de projeto que tinha divergido do plugin.
- **`build.py` do video-docs encerra quando o TTS falha** (3 tentativas, `VE_TTS_ESPERA`) e grava o `.mp4` em `trabalho/`, trocando `.mp4` e `.srt` de `out_dir` só no fim. Antes, um lote com o edge-tts fora deixou o vídeo com a narração antiga no lugar, parecendo atualizado.
- **`confere_saida.py`** (operação `docs-conferir`): compara o texto de cada `.srt` com as legendas do spec e o horário do `.mp4` com o do spec; sai com 1 listando o que remontar. Recomendado ao fim de todo lote.
- **`chrome` no spec**: faixa opaca sobre a barra do navegador (`band`, com `logo`, título e subtítulo) e tarja fixa (`client`, `client_label`) em todas as cenas, desligável por cena com `no_client` e ajustável por fonte em `chrome_src`. Vinha do montador do projeto; padrão desligado.
- **`srt_dir` e `roteiro_dir`**: `.srt` e roteiro em pastas próprias, já separados do `.mp4`.
- **`palavras.transcript.json`** em `work_dir`: palavras com a grafia da legenda e o tempo da fala (glossário desfeito), entrada direta do `/legenda` estilo `reels-palavra`.
- **`avisos`** no relatório e no stderr: caixa fora de 1280x720 (fonte 1080p medida sem escalar), destaque ou balão sobre a faixa da legenda, `at` que começa num corte ou cai inteiro num corte.
- Docs: seções "Lote" e "Regravação de um vídeo já publicado" no `producao.md` (backup, remedir tudo, corrigir o material de apoio junto, `rclone copyto` para manter o ID no Drive); coordenadas com fonte 1080p e busca de elemento por pixel; pegadinhas novas no SKILL.md.
- Teste `docs_offline.sh` cobre faixa com logo, `no_client`, pastas de saída, avisos, TTS que falha 2 vezes e se recupera, TTS fora (build falha, vídeo anterior intacto, conferidor acusa).

## 0.9.2 — 2026-11-09
Lição da terceira rodada do curso de bateria: o exemplo tocado tem de estar no andamento **medido** do clipe, e a medição tem de ser conferida.
- **`/partitura` ganha `andamento.py`** (operação `partitura-andamento`): andamento de um clipe gravado (beat tracking do librosa com quadros de 256 amostras; `bpm` = mediana dos intervalos sobre 4 batidas), fase do compasso pela energia do bumbo (`--tempos N --bumbo 0,3` → `fase`, `contrastes` por fase, `confiavel`, instantes do "1" em `uns`), `--ini/--fim` para o trecho tocado e `--faixa` para a oitava. Caso real: o 5/4 do curso media 112,3 bpm (tracker preso no prior: 23 quadros de 512 amostras, quatro clipes com o mesmo valor) e toca a 168; o exemplo e o contador sobre o clipe estavam errados. Teste no `tests/partitura.sh` (recupera 120 bpm, fase 0 e os "1" a cada 2,5 s do exemplo sintetizado).
- Skill: o andamento do exemplo passa a ser o medido quando há clipe (66–80 bpm só para versão de estudo sem clipe); cursor e contador só com `confiavel`. Docs: scripts, skills, troubleshooting (andamento, fase, música granulada em câmera lenta), convenções (câmera lenta com som usa `rubberband=tempo=<vel>:transients=crisp`, nunca `atempo` em cadeia).

## 0.9.1 — 2026-11-09
- `legenda_palavra.py`: página órfã (uma palavra só) recebe a última palavra da anterior quando a fala é contínua, a palavra não fecha frase e cabe na janela ("ele basicamente faz | uma matemática" em vez de "ele basicamente faz uma | matemática"). Teste ajustado.

## 0.9.0 — 2026-11-09
Melhoria derivada da avaliação do Remotion (ADR-16): o que ele fazia melhor que o plugin, feito em ASS.
- **`/legenda` estilo `reels-palavra`** (`scripts/legenda_palavra.py`, operação `legenda-palavra`): pagina as palavras do `transcript.json` (janela de 1,5 s, pausa, nº de palavras e de caracteres, fim de frase) e destaca a palavra falada no instante em que é dita (`\t` por palavra), ou karaokê (`--modo preenche`, `\k`). Caixa ou contorno, maiúsculas, posição por orientação (0,68 em vertical, 0,86 em horizontal), `--correcoes` para os termos que o ASR errou. Escreve também `<nome>.palavra.paginas.txt` para a revisão antes de queimar. Queima pelo filtro `ass=` do ffmpeg: 20 s de vídeo em ~3 s, contra 318 s para 60 s no Remotion.
- Teste no `smoke.sh` (páginas, tempos, destaque, correção, karaokê, caixa, rotação vertical); docs da skill, `docs/skills.md`, `docs/scripts.md`, pedidos prontos.
- Docs: **ADR-16** avalia o Remotion como motor de motion graphics e de legenda e decide **não adotar** por ora (licença source-available com assento pago a partir de 4 pessoas, inclusive para código escrito por agente; 18× mais lento que o ffmpeg para queimar legenda sobre filmagem). Prova mínima com medições em `docs/adr/2026-11-09-remotion-poc/`; melhorias derivadas anotadas para o `/legenda` (página com palavra destacada em ASS).

## 0.8.0 — 2026-11-09
**`/partitura`** (21º skill): notação de bateria e "exemplo tocado", extraídos do pipeline do curso de bateria (ADR-14).
- `skills/partitura/scripts/partitura.py` (operação `partitura`): padrão compacto em JSON (`ts`, `div`, grade em texto `"X.xx .x.."`, `{"pos": [1,2,3]}`, índices ou `"all"`; manulação `stick` por texto, `"alterna"` ou dict; acentos) → MusicXML → Verovio → cartão PNG 1800×270 e 1800×430 com a posição de cada nota e de cada tempo no JSON (onset em semínimas, x/y, instrumento, acento). R azul, L rosa, bumbo laranja, chimbal de pé verde; 8 instrumentos (hh, ride, crash, sn, tom, ft, bd, hf); 4/4, 5/4, 7/4 ou qualquer fórmula; `div` 1, 2 ou 4. Rasterização com **resvg** (`resvg-py`, sem biblioteca de sistema; cai no cairosvg se instalado). As pegadinhas do Verovio (qfracOn em `<divisions>`, translate de `.page-margin`, +90 para o centro da cabeça) ficam no código.
- `tocar.py` (operação `partitura-tocar`): síntese determinística por fórmula (bumbo, caixa, tom/surdo, chimbal, chimbal de pé, ride, crash), nota acendendo no instante em que soa, playhead e contador de tempos, contagem opcional, fundo da identidade ou gradiente, legenda de cores gerada; sai `<ID>.mp4` (1080p, AAC sem PNS) e `<ID>.wav` com a **mesma duração no grid de quadros**, pico a −6 dBFS e passa-baixa a 15 kHz.
- **`/video-animado` aceita bloco pronto com áudio próprio**: cena `{"id", "video": "x.mp4", "audio": "x.wav", "volume": 0.7}`; `tts_cenas.py` toma a duração do áudio, `montar_cenas.py` usa esse áudio no lugar da narração (com fades e a mesma duração) e `folha_cenas.py` acha o vídeo. É assim que o exemplo tocado entra na montagem.
- Testes: `tests/partitura.sh` (render com Verovio + resvg via uv: tamanhos, notas, tempos, acentos, manulação, erros de grade; exemplo tocado: vídeo = wav no grid de quadros, AAC 48 kHz, pico real ≤ −1,5 dBTP, síntese determinística) no CI em Linux e macOS; smoke cobre o bloco com áudio próprio no `montar_cenas.py`. Docs: skill, scripts, núcleo, instalação, troubleshooting (Verovio/resvg), pedidos prontos, arquitetura (ADR-14) e o ADR-15 **proposto** de geração de imagem e vídeo por IA (`docs/adr/2026-11-09-geracao-por-ia.md`), não implementado.

## 0.7.0 — 2026-11-08
Lições de um curso de bateria de 19 min montado por blocos (cenas Manim, exemplos sintetizados e clipes gravados). ADR-13.
- **`nucleo/audio.py`** e operação **`normalizar-audio`** (`scripts/normalizar_audio.py`): ganho estático até o alvo LUFS + `alimiter` com oversampling a 192 kHz segurando o pico real, medido antes e depois e repetindo com teto menor se passar. Substitui o `loudnorm` linear no `finalizar.sh` do `/videoaula` e o `loudnorm` de uma passada no `montar_cenas.py`: o linear tinha chegado a **+9,2 dBTP** por causa dos degraus nas junções entre blocos. `fades()` (12/18 ms) e `quadros()` (duração no grid de quadros) para montagens por blocos.
- **AAC sem PNS** (`audio.AAC`: `-c:a aac -b:a 256k -aac_pns 0`) em toda entrega do núcleo: o codificador nativo com PNS transformou um wav limitado a −2,5 dBTP em **+4,7 dBTP** (bateria sintetizada, bandas de ruído). Foi a causa do pico real do curso original (−0,4 dBTP a partir de um limiter em −4,4). `normalizar_video` e `montar_cenas.py` medem o arquivo final, depois do AAC.
- **`/prova` reprova pico real acima de −1 dBTP** (`proof.sh` sai com código 3 e grava `PICO ACIMA DO LIMITE` no `.proof.txt`; `PROVA_TP_MAX` muda o limite, `PROVA_SEM_GATE=1` só avisa).
- **`montar_cenas.py` (`/video-animado`) monta por EDL**: cada bloco dura exatamente a narração (`tempos.json`, no grid de quadros); cena 1 quadro curta tem o último quadro clonado (`tpad`), áudio com a mesma duração e fades; blocos em paralelo (`--jobs`), concat sem recodificar, normalização pelo núcleo (`--loudness`, `--tp`), vídeo copiado quando não há legenda a queimar. Cena mais longa que a narração fica inteira, com aviso.
- **`cena_base.py` com relógio no grid de quadros**: `p()`/`w()` arredondam cada passo ao quadro e contam como o renderer (piso no `wait`, teto no `play`); uma cena de 20 passos tinha derivado 0,3 s e cortado o fim da narração. A cena fecha em `total` com ±1 quadro.
- **`montar_aula.py concat`** aplica os mesmos fades por bloco no áudio contínuo.
- **edge-tts repete** até 3 vezes em `NoAudioReceived` e erros de rede (`VE_TTS_ESPERA` entre tentativas), em vez de derrubar o lote de narração.
- Testes: normalização com estalos a fundo de escala (pico ≤ −1,5 dBTP, −14 LUFS), gate da prova (código 3 e conserto), montagem com cena curta (vídeo e áudio fecham com a narração), retry do TTS com o stub. Docs: núcleo, scripts, convenções (pico real), troubleshooting, arquitetura (ADR-13), skills `video-animado`, `videoaula`, `prova`, `trilha`.

## 0.6.0 — 2026-11-08
Compatível com **Codex**, **OpenCode** e **Kiro** (ADR-12 implementado): `video-editores integrar codex|opencode|kiro|todos [--projeto DIR|--usuario] [--remover]`.
- Skills geradas da fonte única: as 20 SKILL.md copiadas para `.agents/skills/` (Codex e OpenCode) e `.kiro/skills/` (Kiro), com `${CLAUDE_PLUGIN_ROOT}` trocado pelo caminho real dos scripts, cabeçalho explicando CLI/MCP, subagentes e gates fora do Claude Code, e arquivos de referência ao lado (glossário, references/). Nomes já satisfazem Kiro (name = pasta, kebab-case).
- Servidor MCP registrado no formato de cada agente: `[mcp_servers."video-editores"]` em `.codex/config.toml` (ou `~/.codex/config.toml`), `mcp.servers` em `opencode.json`, `mcpServers` em `.kiro/settings/mcp.json` (com `autoApprove` das ferramentas de leitura). O comando escolhe binário instalado > checkout com `uv run` > `uvx` do GitHub. Edição preserva o resto do arquivo (TOML por bloco, JSON por chave).
- Regras do projeto: bloco marcado em `AGENTS.md` (Codex, OpenCode) e steering `inclusion: always` (Kiro); idempotente, `--remover` desfaz só o que é nosso.
- Roda inclui `skills/` inteiro em `recursos/`, então `uv tool install … && video-editores integrar todos` funciona sem clonar. Bootstrap dos scripts acha o pacote subindo a árvore (checkout ou site-packages), sem depender de `VE_PKG_DIR`.
- `AGENTS.md` no repositório para quem desenvolve o plugin com Codex/OpenCode/Kiro. Testes: integração dos três agentes (idempotência, remoção, TOML preservado, Kiro name = pasta) e o servidor MCP por stdio com o comando que os agentes executam. Docs: `agentes.md`, README, arquitetura (ADR-12), ADR.

## 0.5.0 — 2026-11-08
Núcleo em camadas: modelos de IA trocáveis, CLI única e servidor MCP (ADR-10 a 12, `docs/adr/2026-11-08-nucleo-modelos-mcp.md`). Motivado pela proposta de abstrair o modelo, servir outros agentes e rodar numa plataforma com GPUs.
- **Pacote `video_editores`** (`pyproject.toml`, hatchling; a roda leva `scripts/` e `skills/*/scripts` em `recursos/`): `modelos/` com os papéis ASR, Segmentador e TTS, backends `faster-whisper`, `rembg`, `edge`, registro por nome e `VE_MODELOS_EXTRA` para backend próprio; configuração por `VE_ASR`/`VE_SEG`/`VE_TTS`/`VE_DEVICE`/`VE_ENCODER`, `video-editores.toml` ou padrão; `deps(device)` de cada backend alimenta o `uv run --with` (cuda → `onnxruntime-gpu`).
- `nucleo/ffmpeg.py`: sondagem, decodificação de áudio para ASR e `codec_video()` (libx264, h264_nvenc, hevc_nvenc, h264_videotoolbox, h264_vaapi). `nucleo/catalogo.py`: nome estável de cada operação → script, uso, dependências, se é longa; única fonte da CLI, do MCP e da documentação.
- **CLI `video-editores`**: `listar`, `modelos`, `tarefas`, `mcp` e qualquer operação do catálogo (`transcrever`, `prova`, `aula-recorte-paralelo`, `aula-finalizar`, …), com `--fundo` para segundo plano. `tarefas.py`: processos detached com código de saída em arquivo.
- **Servidor MCP** (`video-editores-mcp`, SDK `mcp>=2`, stdio ou `--http PORTA`): `executar_operacao` genérica, ferramentas tipadas (`transcrever`, `recortar_pessoa`, `lettering`, `prova`, `videoaula_montar`, `videoaula_finalizar`), `tarefa_status/esperar/cancelar`, `tarefas_listar`, `ler_texto`, `versao`; caminhos restritos a `--raiz`.
- Scripts adaptados sem mudar a CLI: `transcribe.py`, `text_behind.py`, `matte.py`, `tts_cenas.py` usam o backend configurado (`--backend`); `matte.py` e `montar_aula.py` codificam por `VE_ENCODER`; `matte_workers.sh` escolhe o onnxruntime pelo `VE_DEVICE`. Validado com os modelos reais num trecho da Aula 01 (transcrição e recorte idênticos em comportamento).
- `doctor.sh` mostra backends, dispositivo efetivo, GPU e codificadores do ffmpeg. `tests/nucleo.sh` + `tests/mcp_test.py` (cliente MCP em memória) no CI, mais build da roda e CLI a partir dela. Docs: `nucleo.md`, ADR, arquitetura (4 camadas, ADR-01 revisto), README, instalação, scripts, CONTRIBUTING.
- Não feito, por decisão (ADR-12 e roteiro do ADR): skills para outros agentes só quando houver um segundo agente em uso; validação em GPU e backends de video matting (BiRefNet/MatAnyone) dependem de uma máquina com GPU.

## 0.4.0 — 2026-11-08
Videoaula redesenhada e paralelismo em dois níveis. Lições de uma aula de Python de 20 min (3 modos visuais, 9 diagramas, 6 capítulos → 17,5 min).
- **`/videoaula`** (20º skill): aula gravada (professor + quadro/Excalidraw + IDE, webcam circular) → versão com cenário novo por recorte de IA, diagramas Manim sincronizados por palavra no lugar do quadro, IDE reenquadrada por grupos de layout, abertura com checklist, separadores por capítulo, encerramento, lower third, call-outs, SRT e −14 LUFS; 4 gates (design, visual, piloto, entrega). Tudo dirigido por `aula.json`.
- Scripts da skill: `cenas_modo.py` (modos visuais por cena), `remap_tempos.py` (tempos do original → corte pelo `--export v1` do auto-editor, sem retranscrever), `identidade.py` (fundo, chips, anel, lower third, base/tampa do painel de código), `matte.py` + `matte_workers.sh` (recorte por IA em streaming, N processos balanceados, stdin-safe), `render_cenas.sh` (Manim em paralelo, separadores por `Separador:N`), `montar_aula.py` (EDL alinhada ao frame, blocos em paralelo com `--jobs`, concat com **áudio contínuo**), `legenda_aula.py` (SRT com frases inteiras e ajustes das frases cortadas), `finalizar.sh`. Modelos: `base_cenas.py` (`Timed`/`Trecho`, `att()` por palavra, área segura do círculo), `cartelas.py`, `diagramas_exemplo.py`, `aula-exemplo.json`, `ajustes-exemplo.json`, `textos-exemplo.json`.
- Publicação: `publicar_aula.py` gera capítulos do YouTube nos tempos finais, descrição, hashtags e thumbnail 1280×720 com o recorte do locutor. `detectar_layout.py` mede o círculo da webcam e rascunha os grupos de layout da IDE com réguas. `finalizar.sh --limpar-audio` (passa-alta + afftdn). `matte.py --gpu` (onnxruntime-gpu; não validado sem GPU).
- Paralelismo (ADR-08): processos para o que é computação (recorte, render de cenas e de blocos), subagentes para a autoria (uma cena Manim por subagente, revisão só da folha), sequencial onde há dependência de dados ou gate. Documentado no skill, no `/animacao` e na arquitetura.
- `montar_aula.py`: a cartela entra antes do primeiro bloco a partir do instante do capítulo (tolera a micro-lacuna entre cenas que o remap deixa) e o áudio contínuo é construído da própria EDL, bloco a bloco; sem isso uma cartela ficou só no áudio e o vídeo dessincronizou 2,6 s a partir dali (caso real, pego na prova pela diferença vídeo × áudio).
- `transcribe.py`: decodifica o áudio com o ffmpeg (PyAV 19 removeu `metadata_errors` e quebrava o faster-whisper 1.2).
- `/corte`: cortes manuais com `--cut-out` (um por trecho, array em zsh), `--export v1` para remapear tempos; margem 0,3 s como padrão de aula.
- `/tela-verde`: recorte sem tela verde passa a usar `matte.py` (streaming, sombra, máscara separada) em vez de adaptar o `text_behind.py`.
- `doctor.sh`, README e instalação: `uv tool install scenedetect` (o extra `[opencv]` não existe mais).
- `troubleshooting.md`: PyAV × faster-whisper, 504 do CDN de releases do GitHub (espelho Hugging Face com md5), `--cut-out` em zsh, laço `while read` que perde a lista para o filho, deriva de áudio em montagem por blocos, título × chip, layouts da IDE, `ImageDraw` em RGBA, processos que morrem com a sessão.
- Smoke test cobre `remap_tempos.py`, `montar_aula.py edl/map` e `legenda_aula.py` com dados sintéticos; lint inclui `skills/videoaula/scripts`.


## 0.3.0 — 2026-11-08
Vídeo 100% animado por código e lições de um vídeo de 24 cenas para gestores.
- **`/video-animado`** (19º skill): sem bruto; a narração é gerada antes e dita a duração de cada `Scene` do Manim; instantes por fração da fala; cenas fecham com fade sobre o fundo fixo e a troca de fundo é um fade entre imagens (nunca preto); gates de roteiro e piloto; conteúdo acima da faixa da legenda.
- Scripts: `tts_cenas.py` (narração por cena + `tempos.json`, cena muda por `duracao`), `montar_cenas.py` (sincronia pela duração real de cada mp4, legenda frase a frase sem linha órfã e com a grafia original da narração, 48 kHz, `--roteiro`), `folha_cenas.py` (um quadro por cena). Modelo `templates/cena_base.py` e `cenas-exemplo.json`.
- `video-docs`: a voz multilíngue também erra termos ("operator", "orchestrator"); seção `validados_thalita` no glossário e orientação de ouvir antes do lote.
- `doctor.sh` e `troubleshooting.md`: Manim sem headers de sistema (micromamba/conda-forge), fonte da marca no fontconfig, `round_corners`, faixa da legenda, taxa de amostragem do `loudnorm`, grafia fonética vazando para a legenda.
- Smoke test cobre os três scripts novos com cenas sintéticas e o stub do edge-tts.

## 0.2.0 — 2026-11-07
Pedido em linguagem natural, vídeo longo e novos estilos.
- **`/editar`**: entrada em linguagem natural; tabela de estilos → skills; relatório de edição padronizado; ajustes refazem só a etapa afetada.
- **`/destaques`** + `highlights.py`: melhores momentos por transcrição para um alvo de duração ou N reels.
- **`/checklist`** + `checklist_ass.py`: itens com moldura no instante em que são falados.
- **`/tela-dividida`**: reação, antes/depois, 16:9 → 9:16 e 1:1 (receitas validadas).
- `/lettering`: estilos `cartao` (resposta a comentário) e `capa` (revista, com moldura e kicker).
- `/tela-verde`: receita de contorno neon pela máscara do rembg.
- `docs/pedidos-prontos.md`: pedidos por categoria.
- Smoke test cobre os scripts novos e os estilos novos.
- macOS: documentado que a fórmula `ffmpeg` do Homebrew (v8+) vem sem libass; o plugin exige `ffmpeg-full`. CI do macOS passa a usar `ffmpeg-full`; `doctor.sh` e `render-docs.sh` orientam.

## 0.1.1 — 2026-11-07
Correções a partir de revisão independente (21 achados) e testes das receitas com mídia sintética.
- `lettering_ass.py`: respeita o metadado de rotação (vídeo de celular saía com texto no tamanho/posição errados); escapa caminhos com espaço, vírgula e `:`.
- `render_spans.sh`: funciona em vídeo sem áudio; `keep` vazio aborta com mensagem.
- `proof.sh`: tolera `duration=N/A`; argumentos passados por `argv`, não interpolados em código.
- `takes.py`: `--out`, aborta em transcrição vazia, não agrupa frases por prefixo curto demais.
- `transcribe.py`: `--out-dir` (padrão `trabalho/<nome>/`), `--lang auto`. Nada mais é escrito em `originais/`.
- `build.py` (video-docs): fonte DejaVu resolvida em Linux/macOS/Windows; `encoding="utf-8"` em todos os arquivos; caminhos escapados no filtro.
- `/corte`: `--no-open` (o auto-editor abria um player). `/3d`: motor EEVEE escolhido pela versão do Blender (4.2–4.5 vs 5.x). `/referencia`: `-t mp4`, `--lang auto`. `/legenda`: `FontSize=22`. `/animacao`: `-pix_fmt yuv420p`, `offset` numérico no `xfade`.
- `doctor.sh` reescrito conforme o ADR-04: não instala nada no Python do sistema; checa libass e fonte.
- CI: lint agora falha de verdade; `ruff` roda via `uvx`; job macOS; `tests/docs_offline.sh` roda o montador do video-docs com stub do edge-tts (`tests/stub/`).
- Docs: caminhos do video-docs no plugin, aviso de WSL2 no Windows, privacidade do edge-tts, 14 (não 13) nos manifestos.

## 0.1.0 — 2026-11-07
- 13 skills de edição: corte, tomada, legenda, referencia, lettering, animacao, texto-atras, tela-verde, 3d, trilha, efeitos, ganchos, prova.
- `video-docs` (harness de 2026-11-06) incorporado como 14º skill, sem mudanças no montador.
- Scripts compartilhados: transcribe, takes, render_spans, lettering_ass (ASS, sem drawtext), text_behind, proof, doctor, render-docs.
- Convenções únicas (`docs/convencoes.md`), teste de fumaça e CI.
- Documentação: instalação, tutorial, referência de skills e scripts, arquitetura com ADRs, solução de problemas, guia de contribuição.
