# video-editores

Plugin do Claude Code que transforma a IA na sua editora de vídeo: **21 skills** open source, rodando no seu computador, sem SaaS e sem vendor lock-in. Você manda a gravação e pede em português; o `/editar` monta o plano, para nos pontos de aprovação e entrega o vídeo com um relatório do que fez.

| Skill | O que faz | Ferramenta |
|---|---|---|
| **`/editar`** | Pedido livre → plano → execução com gates → relatório de edição | orquestra os demais |
| `/destaques` | Melhores momentos de vídeo longo (aula 2 h → 10 min; N reels) | faster-whisper + `highlights.py` |
| `/checklist` | Itens com moldura que entram no instante em que são falados | `checklist_ass.py` |
| `/tela-dividida` | Reação, antes/depois, 16:9 → 9:16 e 1:1 | ffmpeg vstack/crop |
| `/corte` | Corta silêncio e tempo morto | auto-editor |
| `/tomada` | Detecta tomadas repetidas e fica com a melhor | faster-whisper + `takes.py` |
| `/legenda` | Legenda automática (SRT ou queimada, estilo reels) | faster-whisper + libass |
| `/referencia` | Extrai o "DNA" de edição de um vídeo de referência | yt-dlp + PySceneDetect |
| `/lettering` | Títulos, destaques, lower thirds, cartão de comentário e capa de revista | ASS/libass (`lettering_ass.py`) |
| `/animacao` | Motion graphics por código | Manim / ffmpeg |
| `/texto-atras` | Texto entre o fundo e a pessoa | rembg (U²-Net / BiRefNet) |
| `/tela-verde` | Chroma key, troca de fundo por IA, contorno neon | ffmpeg chromakey / rembg |
| `/3d` | Texto e objetos 3D com fundo transparente | Blender headless |
| `/trilha` | Música de fundo com ducking e loudness | ffmpeg sidechaincompress |
| `/efeitos` | Sound design sincronizado com cortes | ffmpeg (sons sintetizados) |
| `/ganchos` | 5 ganchos para os 3 primeiros segundos | Claude + transcrição |
| `/prova` | Folha de contato, preview e QA | ffmpeg |
| `/video-docs` | Gravação de tela → vídeo de documentação narrado | edge-tts + `build.py` |
| `/video-animado` | Vídeo 100% animado por código, narração que dita o tempo de cada cena, sem tela preta | Manim + edge-tts + `montar_cenas.py` |
| `/videoaula` | Aula gravada (professor + quadro + IDE) → versão redesenhada: cenário novo por IA, diagramas animados no lugar do quadro, capítulos, legenda, −14 LUFS | rembg + Manim + auto-editor + `montar_aula.py` |
| `/partitura` | Partitura de bateria com R/L e cores por membro, e "exemplo tocado": som sintetizado + notação animada nota a nota, pronto para entrar como bloco | Verovio + resvg + numpy/scipy (`partitura.py`, `tocar.py`) |

No Claude Code, os skills aparecem com o prefixo do plugin (ex.: `/video-editores:corte`). Também são chamados automaticamente pela descrição ("tira os silêncios desse vídeo").

Funciona também no **Codex**, no **OpenCode** e no **Kiro**: `video-editores integrar codex|opencode|kiro|todos` instala as mesmas skills, registra o servidor MCP e grava as regras do projeto no formato de cada agente ([docs/agentes.md](docs/agentes.md)).

Por baixo das skills há um núcleo que funciona **sem o Claude**: a CLI `video-editores <operação>` roda qualquer script, os modelos de IA (transcrição, recorte de pessoa, narração) são trocáveis por configuração (`VE_ASR`, `VE_SEG`, `VE_TTS`, `VE_DEVICE=cuda`, `VE_ENCODER=h264_nvenc`), e um servidor MCP expõe as mesmas operações a outros agentes, com tarefas em segundo plano. Detalhes em [docs/nucleo.md](docs/nucleo.md).

## Instalação rápida

```bash
# dependências base (detalhes e macOS/Windows em docs/instalacao.md)
sudo apt install ffmpeg fonts-dejavu-core
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install auto-editor && uv tool install yt-dlp && uv tool install scenedetect

# plugin direto do GitHub
claude plugin marketplace add fmnapoli/video-editores
claude plugin install video-editores@video-editores-local
```

Reinicie o Claude Code e rode `make doctor` num clone do repositório para ver o que falta.

Sem Claude Code (CLI) ou para outro agente (MCP):

```bash
uv tool install "video-editores @ git+https://github.com/fmnapoli/video-editores"      # CLI: video-editores listar
video-editores integrar todos            # Codex + OpenCode + Kiro neste projeto (skills, MCP, regras)
claude mcp add video-editores -- uvx --from "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores" video-editores-mcp --raiz "$PWD"
```

## Como pedir

Sem decorar comando. Exemplos (mais em [docs/pedidos-prontos.md](docs/pedidos-prontos.md)):

- "Corta as pausas e fica com a última tomada, legenda palavra por palavra."
- "Edita pro YouTube com os melhores momentos. Onde eu não falo, põe música."
- "Transforma essa aula de 2 horas num vídeo de 10 minutos e tira três Reels."
- "Faz um checklist do que eu falar e põe a frase forte atrás de mim."
- "Transforma as gravações em originais/ em vídeos de documentação, um por ação."
- "Refaz essa videoaula com cenário novo, diagramas animados no lugar do Excalidraw e separadores de assunto, mantendo o professor na tela."

Pipeline padrão de Reels que o `/editar` executa:

```
/tomada → /corte → /ganchos → /lettering → /legenda → /trilha → /efeitos → /prova
```

Passo a passo completo: [docs/tutorial.md](docs/tutorial.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [Instalação](docs/instalacao.md) | requisitos por sistema, opcionais por skill, GPU, instalação sem plugin |
| [Pedidos prontos](docs/pedidos-prontos.md) | pedidos por categoria (Reels, aula, vlog, anúncio, docs) e os skills que executam |
| [Tutorial](docs/tutorial.md) | do bruto ao reels pronto, e variações (docs, referência, efeitos) |
| [Skills](docs/skills.md) | entrada, saída, parâmetros, gates e tempo de cada skill |
| [Scripts](docs/scripts.md) | CLI de cada script, formatos JSON e saídas |
| [Convenções](docs/convencoes.md) | pastas, nomes, ordem, formatos, loudness, privacidade, licenças |
| [Arquitetura](docs/arquitetura.md) | camadas, ADRs, fluxo de dados, testes |
| [Núcleo](docs/nucleo.md) | CLI `video-editores`, modelos trocáveis e GPU, servidor MCP, backend próprio |
| [Outros agentes](docs/agentes.md) | Codex, OpenCode e Kiro: `video-editores integrar`, onde cada um lê skills, MCP e regras |
| [ADR núcleo/MCP](docs/adr/2026-11-08-nucleo-modelos-mcp.md) | decisão de abstrair modelos, CLI e MCP; integração com GPU; roteiro |
| [ADRs propostos e avaliações](docs/arquitetura.md#decisões-adrs-resumidos) | geração por IA (ADR-15, proposto) e Remotion (ADR-16, avaliado e não adotado) |
| [Solução de problemas](docs/troubleshooting.md) | sintomas comuns e correções |
| [video-docs](docs/video-docs-LEIAME.md) | harness de vídeos de documentação |
| [Contribuindo](CONTRIBUTING.md) | como criar skills e scripts no padrão |

## Desenvolvimento

```bash
make test           # teste de fumaça com vídeo sintético (ffmpeg + python3)
bash tests/nucleo.sh        # núcleo: modelos, catálogo, CLI, tarefas e MCP em processo (uv)
bash tests/docs_offline.sh  # montador do video-docs offline (stub do edge-tts)
make lint           # shellcheck + ruff
make docs-example   # exemplo do video-docs (precisa de internet para o edge-tts)
```

CI em `.github/workflows/ci.yml` roda lint, smoke e o teste offline do video-docs em Linux e macOS a cada push.

## Licença

Código e skills: MIT. Cada ferramenta externa mantém a própria licença (tabela em `docs/convencoes.md`). Atenção: pesos do MusicGen/AudioGen são CC-BY-NC.
