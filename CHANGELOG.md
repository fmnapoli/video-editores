# Changelog

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
