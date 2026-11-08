# Instalação

Tudo roda local. O único serviço externo é o edge-tts, usado só pelo `/video-docs` para narração.

**Windows:** os scripts são bash e usam `python3`, `fc-list` e `mktemp`. Use o **WSL2 com Ubuntu** e siga a coluna Ubuntu; no Windows nativo (PowerShell) o plugin não roda.

## 1. Requisitos base (obrigatórios)

| Item | Para quê | Ubuntu/Debian | macOS (Homebrew) | Windows (WSL2) |
|---|---|---|---|---|
| Claude Code | executar os skills | `npm i -g @anthropic-ai/claude-code` | idem | idem |
| ffmpeg ≥ 6 com libass | tudo | `sudo apt install ffmpeg` | `brew install ffmpeg-full` (**não** `ffmpeg`, veja abaixo) | WSL2: `sudo apt install ffmpeg` |
| Python ≥ 3.10 | scripts | `sudo apt install python3` | já vem / `brew install python` | `winget install Python.Python.3.12` |
| uv | rodar scripts com dependências isoladas | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `brew install uv` | `winget install astral-sh.uv` |
| Fonte DejaVu | textos ASS e `video-docs` | `sudo apt install fonts-dejavu-core` | `brew install --cask font-dejavu` | baixar em dejavu-fonts.github.io |

Confira se o ffmpeg tem libass (os filtros `ass` e `subtitles` precisam aparecer):

```bash
ffmpeg -hide_banner -filters | grep -E " (ass|subtitles) "
```

Builds estáticos sem libass não servem. Builds sem `drawtext` servem: o plugin não usa `drawtext`.

**macOS:** desde a versão 8, a fórmula `ffmpeg` do Homebrew é uma build enxuta, sem libass, freetype e fontconfig, então os filtros `ass` e `subtitles` não existem nela. Instale `ffmpeg-full`, que é keg-only (não entra no PATH sozinho), e coloque-o na frente:

```bash
brew install ffmpeg-full
echo 'export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
ffmpeg -hide_banner -filters | grep -E " (ass|subtitles) "   # tem que listar os dois
```

Se outra ferramenta já instalou a fórmula `ffmpeg` enxuta (ocrmypdf, vhs etc.), as duas convivem; o que importa é a ordem no PATH.

## 2. Ferramentas CLI (recomendadas)

```bash
uv tool install auto-editor              # /corte
uv tool install yt-dlp                   # /referencia
uv tool install scenedetect               # /referencia, /efeitos, /videoaula (o extra [opencv] não existe mais no 0.7)
```

## 3. Opcionais por skill

| Skill | Instalar |
|---|---|
| `/video-docs` (transcrição opcional) | `uv tool install whisper-ctranslate2`, ou use o `scripts/transcribe.py` do plugin |
| `/animacao` | `uv tool install manim` (no Linux precisa de `libcairo2-dev libpango1.0-dev`; veja docs.manim.community) |
| `/3d` | Blender 4.2+ (blender.org) com `blender` no PATH |
| `/texto-atras`, `/tela-verde` (IA) | nada: `uv run --with "rembg[cpu]"` baixa sob demanda. Com GPU NVIDIA: `rembg[gpu]` |
| `/tomada`, `/legenda` | nada: `uv run --with faster-whisper` baixa sob demanda. O modelo `medium` (~1,5 GB) é baixado no primeiro uso |
| `/trilha`, `/efeitos` (gerados por IA) | `uv run --with audiocraft` (pesado; precisa de PyTorch; pesos não comerciais) |

## 4. Instalar o plugin

```bash
git clone https://github.com/fmnapoli/video-editores ~/src/video-editores
claude plugin marketplace add ~/src/video-editores
claude plugin install video-editores@video-editores-local
```

Reinicie o Claude Code. Para conferir, digite `/` e procure `video-editores:`.

Para atualizar: `git -C ~/src/video-editores pull` e reinicie o Claude Code.

### Alternativa sem plugin
Copie os skills que quiser para `~/.claude/skills/`. Nesse caso `${CLAUDE_PLUGIN_ROOT}` não existe: exporte a variável apontando para o clone.

```bash
export CLAUDE_PLUGIN_ROOT=~/src/video-editores
cp -r ~/src/video-editores/skills/* ~/.claude/skills/
```

## 5. Verificar

```bash
make -C ~/src/video-editores doctor      # lista o que falta e como instalar
make -C ~/src/video-editores test        # teste de fumaça (~10 s)
```

## 6. GPU (opcional)

| Componente | Ganho com GPU NVIDIA |
|---|---|
| faster-whisper | 5–10× (`--device cuda`; precisa de CUDA 12 + cuDNN 9) |
| rembg / BiRefNet | 10×+ (`rembg[gpu]`) |
| Blender (Cycles) | grande; EEVEE já é rápido em GPU integrada |

Sem GPU tudo funciona. Use trechos curtos para os passos de IA.

Com GPU, nada a instalar à mão: `VE_DEVICE=cuda` faz o backend de segmentação declarar `onnxruntime-gpu` e o faster-whisper usar `float16`; `VE_ENCODER=h264_nvenc` troca o libx264 no recorte e nos blocos da videoaula. `make doctor` mostra o dispositivo efetivo e os codificadores do seu ffmpeg. Detalhes e `video-editores.toml` em [nucleo.md](nucleo.md).

## 7. CLI, servidor MCP e outros agentes (opcional)

```bash
uv tool install "video-editores @ git+https://github.com/fmnapoli/video-editores"   # video-editores listar | modelos | <operação>
claude mcp add video-editores -- uvx --from "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores" video-editores-mcp --raiz /caminho/do/projeto
cd /caminho/do/projeto && video-editores integrar todos     # Codex, OpenCode e Kiro: skills + MCP + regras (docs/agentes.md)
```
