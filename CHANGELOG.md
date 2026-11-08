# Changelog

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
