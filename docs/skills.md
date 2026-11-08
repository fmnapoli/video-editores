# Referência dos skills

Cada skill tem as instruções completas em `skills/<nome>/SKILL.md`. Esta página resume entrada, saída, parâmetros e gates de cada um.

Invocação: `/video-editores:<nome>`, ou em linguagem natural (o Claude escolhe pelo `description` do skill).

| Skill | Entrada | Saída | Gate humano | Tempo típico (1 min de vídeo, CPU) |
|---|---|---|---|---|
| editar | pedido livre + vídeo | pipeline + relatório de edição | os dos skills chamados | soma |
| destaques | vídeo longo + alvo | `.highlights.json/.md`, `_destaques.mp4` | **sim**: lista de trechos | transcrição ~1,2× tempo real |
| checklist | vídeo + itens | `.ass`, `_checklist.mp4` | lista de itens | 10–20 s |
| tela-dividida | 2 vídeos ou 1 | `_split.mp4` / vertical | prova | 20–60 s |
| corte | vídeo | `_corte.mp4` | não (avisa se cortar > 45%) | 10–30 s |
| tomada | vídeo | `.transcript.json`, `.takes.json`, `_tomada.mp4` | **sim**: lista de descartes | 1–2 min |
| legenda | vídeo (+ transcrição) | `.srt`, `.words.srt`, `_legenda.mp4` | **sim**: texto revisado | 1–2 min |
| referencia | link ou vídeo | `referencia.md`, cenas CSV, folha de contato | pergunta se aplica | 1–3 min |
| lettering | vídeo + `textos.json` | `.ass`, `_lettering.mp4` | não | 10–20 s |
| animacao | descrição | `.mov` com alpha, `_anim.mp4` | prova dos frames | 30 s–5 min |
| texto-atras | vídeo + texto + intervalo | `_texto_atras.mp4` | prova do trecho | 15–60 s por 3 s |
| tela-verde | vídeo + fundo | `_fundo.mp4` | prova | 10 s (chroma) / minutos (IA) |
| 3d | descrição | PNGs, `.mov` ProRes 4444 | **sim**: frame de teste | 1–10 min |
| trilha | vídeo + música | `_trilha.mp4` | escolha da música | 10–20 s |
| efeitos | vídeo | `_efeitos.mp4` | **sim**: lista de instantes | 10–30 s |
| ganchos | transcrição | 5 opções + recomendação | escolha | instantâneo |
| prova | vídeo | `.proof.jpg`, `.preview.mp4`, `.proof.txt` | entrega ao usuário | 10–20 s |
| video-docs | gravações de tela | `.mp4`, `.srt`, roteiros, inventário | **3 gates** (inventário, roteiros, piloto) | ver LEIAME |
| video-animado | roteiro + identidade da marca | cenas Manim, `.mp4`, `.srt`, roteiro final | **2 gates** (roteiro, piloto) + prova | ~1 min por cena em 1080p |

---

## /editar
Lê o pedido, escolhe os skills pela tabela de estilos (igual à do catálogo em `docs/pedidos-prontos.md`), executa com os gates e termina com o **relatório de edição**: pausas e tomadas removidas, duração antes/depois, o que foi aplicado, onde está cada arquivo. Ajustes refazem só a etapa afetada.

## /destaques
`highlights.py` divide a fala em blocos por pausas (`--gap`), pontua por palavras-chave, números, perguntas e marcadores de ênfase, penaliza muletas, e escolhe por pontuação/segundo até o `--target` (ou `--reels N --reel-len S`). Blocos maiores que ~40% do alvo são divididos. Saída `.md` com todos os blocos para o Claude e o usuário refinarem.

## /checklist
`checklist_ass.py` acha o instante de cada item pela primeira palavra-gatilho na transcrição (sem acento/caixa, a partir do item anterior) ou por `at`, e desenha moldura + itens com ✓ entrando um a um. `--side right` quando a pessoa está à esquerda.

## /tela-dividida
Receitas ffmpeg validadas: reação (vstack 1080x960 ×2 com `force_original_aspect_ratio=increase`), antes/depois alinhado pela transcrição, 16:9 → 9:16 (recorte central, seguindo a pessoa, ou com fundo borrado) e 1:1.

## /corte
Corta silêncio com o auto-editor, com base no volume do áudio.

| Parâmetro | Padrão | Faixa | Efeito |
|---|---|---|---|
| ritmo / `--margin` | normal = 0,15 s | suave 0,25 · agressivo 0,06 | folga mantida em volta de cada fala |
| `threshold` | 0,04 | 0,02 (fala baixa) – 0,08 (ruído) | volume abaixo do qual é silêncio |
| export | vídeo | `--export resolve/premiere/final-cut-pro` | gera timeline editável em vez de vídeo |
| `--no-open` | sempre | — | sem ele o auto-editor abre um player ao terminar |

Rode o `/tomada` antes: o `/corte` não sabe o que é uma tomada repetida.

## /tomada
Agrupa segmentos consecutivos com texto parecido (similaridade ≥ `threshold`) e mantém a **última tentativa completa**. Descarta tentativas com menos de 80% do texto mais longo do grupo ou com confiança baixa (`avg_logprob` ≤ -1).

| Parâmetro | Padrão | Quando mudar |
|---|---|---|
| `--threshold` | 0,6 | 0,75 se agrupar frases diferentes; 0,5 se perder repetições |
| `--pad` | 0,08 s | aumente se as falas ficarem com o início ou o fim cortado |
| `--model` (transcrição) | medium | large-v3 para áudio ruim, com GPU |
| `--prompt` | — | **sempre** passe o vocabulário técnico |

Ajuste manual: edite `keep` no `.takes.json` e rode de novo só o `render_spans.sh`.

## /legenda
| Estilo | Arquivo | Visual |
|---|---|---|
| reels (padrão em vídeo vertical) | `.words.srt` (N palavras por bloco) | grande, contorno, centro-baixo (`MarginV=110`) |
| clássico (padrão em horizontal) | `.srt` (frase) | rodapé, menor |

Cores ASS são `&HAABBGGRR` (ordem invertida): amarelo = `&H0000FFFF`. Caixa atrás do texto: `BorderStyle=3`.

## /referencia
Produz `referencia.md` com: duração, número de cortes, duração média/mínima/máxima dos planos, densidade de cortes nos 3 primeiros segundos, texto do gancho, estrutura, estilo de legenda, música, e os **parâmetros a aplicar** nos outros skills. Baixar vídeo de terceiros é só para análise pessoal.

## /lettering
Formato completo do `textos.json` em [scripts.md](scripts.md#lettering_asspy). Estilos: `titulo`, `destaque`, `lower`. Animações: `pop`, `fade`, `slide`, `none`.

## /animacao
- **Manim** (padrão): diagramas, fluxos, gráficos, tipografia cinética. Teste com `-ql`, renderize com `-qh`; `-t` gera fundo transparente.
- **ffmpeg**: punch-in, ken burns, `xfade`.

## /texto-atras
| Modelo (`--model`) | Qualidade | Velocidade em CPU |
|---|---|---|
| `u2net_human_seg` (padrão) | boa | ~2–6 fps |
| `birefnet-portrait` | ótima (cabelo, bordas) | ~0,5–1,5 fps |

O texto fica preso entre o fundo e a pessoa. Funciona melhor com texto curto, acima dos ombros (`--y 0.3–0.4`).

## /tela-verde
- Com tela verde: `chromakey` + `despill`. Amostre a cor real do fundo (raramente é `#00FF00` puro).
- Sem tela verde: rembg por frame; para clipes longos, RobustVideoMatting (GPL-3) com GPU.

## /3d
Blender headless (`blender -b -P cena.py -a`). Sempre renderize um frame de teste (`-f 45`) e mostre antes do render completo. A saída em ProRes 4444 preserva o canal alpha para compor no vídeo.

## /trilha
`sidechaincompress` abaixa a música durante a fala. Alvo: -14 LUFS (redes) ou -16 (docs). Fontes de música livres: FMA (CC0/CC-BY), Pixabay Music, YouTube Audio Library. Os pesos do MusicGen são **não comerciais**.

## /efeitos
Instantes vindos de: trocas de plano (PySceneDetect), `start` dos letterings, revelações. Máximo de um efeito a cada 2–3 s. Os sons base (whoosh, pop, ding) são sintetizados pelo ffmpeg, sem baixar arquivos.

## /ganchos
5 padrões: resultado primeiro, erro comum, contraste, pergunta específica, prova visual. No máximo ~12 palavras (≈ 3 s). O vídeo precisa cumprir a promessa do gancho.

## /prova
Checklist: legenda legível e fora do rosto, textos no lugar, **nenhum dado sensível**, sem frame preto ou congelado, resolução, codec e loudness no alvo.

## /video-animado
Vídeo inteiro em animação por código, sem bruto: a narração (edge-tts) é gerada antes e dita a duração de cada `Scene` do Manim; as cenas marcam os instantes por fração da fala e fecham com fade sobre o fundo fixo (nunca preto). Scripts: `tts_cenas.py` (narração + `tempos.json`), `montar_cenas.py` (concat + narração + legenda com a grafia original + loudnorm), `folha_cenas.py` (um quadro por cena). Modelo de cena em `skills/video-animado/templates/cena_base.py`.

## /video-docs
Harness para gravações de tela, documentado em [video-docs-LEIAME.md](video-docs-LEIAME.md) e `skills/video-docs/references/`. Fluxo: inventário → roteiros (com revisão de coerência contra o código) → piloto → lote. Montagem por `spec.json` com `scripts/render-docs.sh`.
