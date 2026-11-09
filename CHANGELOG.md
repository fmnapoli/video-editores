# Changelog

## Não lançado
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
