# video-editores

Plugin do Claude Code com **14 editores de vídeo** como skills: os 13 comandos estilo "editor de reels" e o harness `video-docs` para vídeos de documentação. Tudo open source, roda local, sem SaaS e sem vendor lock-in.

| Skill | O que faz | Ferramenta |
|---|---|---|
| `/corte` | Corta silêncio e tempo morto | auto-editor |
| `/tomada` | Detecta tomadas repetidas e fica com a melhor | faster-whisper + `takes.py` |
| `/legenda` | Legenda automática (SRT ou queimada, estilo reels) | faster-whisper + libass |
| `/referencia` | Extrai o "DNA" de edição de um vídeo de referência | yt-dlp + PySceneDetect |
| `/lettering` | Títulos, destaques e lower thirds animados | ASS/libass (`lettering_ass.py`) |
| `/animacao` | Motion graphics por código | Manim / ffmpeg |
| `/texto-atras` | Texto entre o fundo e a pessoa | rembg (U²-Net / BiRefNet) |
| `/tela-verde` | Chroma key ou troca de fundo por IA | ffmpeg chromakey / rembg |
| `/3d` | Texto e objetos 3D com fundo transparente | Blender headless |
| `/trilha` | Música de fundo com ducking e loudness | ffmpeg sidechaincompress |
| `/efeitos` | Sound design sincronizado com cortes | ffmpeg (sons sintetizados) |
| `/ganchos` | 5 ganchos para os 3 primeiros segundos | Claude + transcrição |
| `/prova` | Folha de contato, preview e QA | ffmpeg |
| `/video-docs` | Gravação de tela → vídeo de documentação narrado | edge-tts + `build.py` |

No Claude Code, os skills aparecem com o prefixo do plugin (ex.: `/video-editores:corte`). Também são chamados automaticamente pela descrição ("tira os silêncios desse vídeo").

## Instalação rápida

```bash
# dependências base (detalhes e macOS/Windows em docs/instalacao.md)
sudo apt install ffmpeg fonts-dejavu-core
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install auto-editor && uv tool install yt-dlp && uv tool install "scenedetect[opencv]"

# plugin direto do GitHub
claude plugin marketplace add fmnapoli/video-editores
claude plugin install video-editores@video-editores-local
```

Reinicie o Claude Code e rode `make doctor` num clone do repositório para ver o que falta.

## Fluxo típico (reels)

```
/tomada → /corte → /ganchos → /lettering → /legenda → /trilha → /efeitos → /prova
```

Passo a passo completo: [docs/tutorial.md](docs/tutorial.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [Instalação](docs/instalacao.md) | requisitos por sistema, opcionais por skill, GPU, instalação sem plugin |
| [Tutorial](docs/tutorial.md) | do bruto ao reels pronto, e variações (docs, referência, efeitos) |
| [Skills](docs/skills.md) | entrada, saída, parâmetros, gates e tempo de cada skill |
| [Scripts](docs/scripts.md) | CLI de cada script, formatos JSON e saídas |
| [Convenções](docs/convencoes.md) | pastas, nomes, ordem, formatos, loudness, privacidade, licenças |
| [Arquitetura](docs/arquitetura.md) | camadas, ADRs, fluxo de dados, testes |
| [Solução de problemas](docs/troubleshooting.md) | sintomas comuns e correções |
| [video-docs](docs/video-docs-LEIAME.md) | harness de vídeos de documentação |
| [Contribuindo](CONTRIBUTING.md) | como criar skills e scripts no padrão |

## Desenvolvimento

```bash
make test           # teste de fumaça com vídeo sintético (ffmpeg + python3)
make lint           # shellcheck + ruff
make docs-example   # exemplo do video-docs (precisa de internet para o edge-tts)
```

CI em `.github/workflows/ci.yml` roda lint e smoke a cada push.

## Licença

Código e skills: MIT. Cada ferramenta externa mantém a própria licença (tabela em `docs/convencoes.md`). Atenção: pesos do MusicGen/AudioGen são CC-BY-NC.
