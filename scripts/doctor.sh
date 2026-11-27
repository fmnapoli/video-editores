#!/usr/bin/env bash
# Verifica dependências do plugin video-editores (não instala nada no Python do sistema).
# Uso: doctor.sh
set -u
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✘\033[0m %s  →  %s\n' "$1" "$2"; MISSING=1; }
opt()  { printf '  \033[33m•\033[0m %s  →  %s\n' "$1" "$2"; }
MISSING=0
HERE="$(cd "$(dirname "$0")" && pwd)"
# Windows nativo: o Claude Code roda os comandos no Git Bash (MINGW/MSYS)
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; *) WIN=0 ;; esac
# Python: python3; no Windows o instalador do python.org só cria `python`, e `python3` pode ser o atalho da
# Microsoft Store, que está no PATH e não roda nada (por isso o teste executa, não usa `command -v`)
PY=""
if python3 -c '' >/dev/null 2>&1; then PY=python3
elif python -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1; then PY=python; fi
VE_PYTHONUTF8_DO_USUARIO="${PYTHONUTF8:-}"
[ "$WIN" = 1 ] && export PYTHONUTF8=1   # para o próprio doctor imprimir acentos; a checagem abaixo usa o valor do usuário

echo "Base (obrigatório):"
if [ "$WIN" = 1 ]; then
  command -v ffmpeg >/dev/null && ok "ffmpeg" || miss "ffmpeg" "winget install Gyan.FFmpeg (e reabra o terminal)"
else
  command -v ffmpeg >/dev/null && ok "ffmpeg" || miss "ffmpeg" "apt install ffmpeg | brew install ffmpeg"
fi
command -v ffprobe >/dev/null && ok "ffprobe" || miss "ffprobe" "vem com o ffmpeg"
if command -v ffmpeg >/dev/null; then
  ffmpeg -hide_banner -filters 2>/dev/null | grep -qE ' (ass|subtitles) ' && ok "ffmpeg com libass" \
    || miss "ffmpeg com libass" "Linux: ffmpeg do apt. Windows: a build 'full' ou 'essentials' do gyan.dev (winget install Gyan.FFmpeg). macOS: 'brew install ffmpeg-full' e ponha \$(brew --prefix ffmpeg-full)/bin antes no PATH (a fórmula 'ffmpeg' do Homebrew vem sem libass desde a v8)"
fi
if [ "$PY" = python3 ]; then ok "python3"
elif [ "$PY" = python ]; then
  # as skills chamam `python3`; a cópia ao lado do python.exe vale em qualquer terminal, não só no Git Bash
  miss "python3 (só existe \`python\`)" "crie o atalho: cp \"\$(command -v python)\" \"\$(dirname \"\$(command -v python)\")/python3.exe\""
else
  miss "python3" "instale Python 3.10+$([ "$WIN" = 1 ] && echo ' (winget install Python.Python.3.12)')"
fi
command -v uv      >/dev/null && ok "uv"      || miss "uv" "https://docs.astral.sh/uv/getting-started/installation/$([ "$WIN" = 1 ] && echo ' (winget install astral-sh.uv)')"
if [ "$WIN" = 1 ]; then
  # sem isto o Python lê e escreve em cp1252, e os acentos do roteiro e das legendas saem trocados
  [ "${VE_PYTHONUTF8_DO_USUARIO:-}" = 1 ] && ok "PYTHONUTF8=1" \
    || miss "PYTHONUTF8=1 (arquivos e saída do Python em UTF-8)" "setx PYTHONUTF8 1   (e reabra o terminal)"
fi
if [ -n "$PY" ] && PYTHONPATH="$HERE/.." "$PY" -c "import video_editores" 2>/dev/null; then
  PYTHONPATH="$HERE/.." "$PY" -m video_editores.nucleo.fontes "DejaVu Sans" bold >/dev/null 2>&1 && ok "fonte DejaVu Sans Bold" \
    || miss "fonte DejaVu Sans Bold" "apt install fonts-dejavu-core | brew install --cask font-dejavu | Windows: choco install dejavufonts, ou instale os TTF de https://dejavu-fonts.github.io"
elif command -v fc-list >/dev/null; then
  fc-list 2>/dev/null | grep -qi "DejaVuSans-Bold\|DejaVu Sans:style=Bold" && ok "fonte DejaVu Sans Bold" \
    || miss "fonte DejaVu Sans Bold" "apt install fonts-dejavu-core | brew install --cask font-dejavu"
else
  opt "fonte DejaVu Sans Bold" "não deu para checar: sem Python 3 e sem fontconfig (fc-list)"
fi

echo "CLIs por skill:"
command -v auto-editor >/dev/null && ok "auto-editor (/corte)" || miss "auto-editor (/corte)" "uv tool install auto-editor"
command -v yt-dlp      >/dev/null && ok "yt-dlp (/referencia)" || opt "yt-dlp (/referencia)" "uv tool install yt-dlp"
command -v scenedetect >/dev/null && ok "scenedetect (/referencia, /efeitos)" || opt "scenedetect" "uv tool install scenedetect"
command -v manim       >/dev/null && ok "manim (/animacao, /video-animado)" || opt "manim (/animacao, /video-animado)" "uv tool install manim  (se o manimpango falhar por falta de libpango-dev: micromamba create -n manim -c conda-forge manim, ver docs/troubleshooting.md)"
command -v blender     >/dev/null && ok "blender (/3d)" || opt "blender (/3d)" "https://www.blender.org/download/"

echo "Modelos de IA (video_editores.modelos; troque com VE_ASR/VE_SEG/VE_TTS/VE_IMAGEM/VE_ROSTO/VE_OCR, VE_DEVICE, VE_ENCODER):"
if [ -n "$PY" ] && PYTHONPATH="$HERE/.." "$PY" -c "import video_editores" 2>/dev/null; then
  PYTHONPATH="$HERE/.." "$PY" - <<'PY2'
from video_editores import modelos
from video_editores.nucleo import ffmpeg
l = modelos.listar()
for tipo, d in l["tipos"].items():
    print(f"  • {tipo}: {d['escolhido']}  (disponíveis: {', '.join(d['backends'])})")
print(f"  • dispositivo: {l['config']['device']} -> efetivo {l['device_efetivo']}; codificador: {ffmpeg.encoder()}")
PY2
  if command -v nvidia-smi >/dev/null; then ok "GPU NVIDIA visível (nvidia-smi); use VE_DEVICE=cuda e VE_ENCODER=h264_nvenc"; else opt "GPU NVIDIA" "sem nvidia-smi: tudo roda em CPU (recorte por IA ~1-3 s/frame)"; fi
  # geração de imagem (ADR-15): servidor ComfyUI à parte, opcional
  COMFY=$(PYTHONPATH="$HERE/.." "$PY" - 2>&1 <<'PY3' | tr -d '\r'
from video_editores import modelos
try:
    g = modelos.get_imagem()
    s = g.conferir(timeout=5)
    gpu = ", ".join(f"{d['nome']} {d['vram_gb']} GB" for d in s["dispositivos"]) or "sem dispositivo"
    print(f"OK servidor {g.url} (ComfyUI {s['versao']}; {gpu}); workflow {g.workflow_arq.stem}: {g.checkpoint()}")
except Exception as e:
    print(f"-- {e}")
PY3
)
  case "$COMFY" in
    OK*) ok "imagem (gerar-imagem): ${COMFY#OK }" ;;
    *)   opt "imagem (gerar-imagem, opcional)" "${COMFY#-- }" ;;
  esac
  # cena HTML (/cena-web): precisa de um Chrome/Chromium para renderizar
  if command -v google-chrome >/dev/null || command -v chromium >/dev/null || command -v chromium-browser >/dev/null || [ -n "${VE_CHROME:-}" ] || [ -d "/Applications/Google Chrome.app" ] \
     || [ -f "${PROGRAMFILES:-/c/Program Files}/Google/Chrome/Application/chrome.exe" ] || [ -f "${LOCALAPPDATA:-/nonexistent}/Google/Chrome/Application/chrome.exe" ]; then ok "Chrome/Chromium (/cena-web)"; else opt "Chrome/Chromium (/cena-web)" "instale o Google Chrome, aponte VE_CHROME, ou: uv run --with playwright playwright install chromium"; fi
  # banco de vídeo (/banco): opcional, só com chave própria; nada mais depende dele
  if [ -n "${PEXELS_API_KEY:-}" ]; then ok "banco de vídeo (/banco): PEXELS_API_KEY definida"; else opt "banco de vídeo (/banco, opcional)" "desligado: sem PEXELS_API_KEY (chave gratuita em https://www.pexels.com/api/)"; fi
  if command -v ffmpeg >/dev/null; then
    ENCS=$(PYTHONPATH="$HERE/.." "$PY" -c "from video_editores.nucleo import ffmpeg; print(' '.join(ffmpeg.encoders_disponiveis()))" | tr -d '\r')
    echo "  • codificadores neste ffmpeg: ${ENCS:-nenhum da tabela}"
  fi
else
  opt "pacote video_editores" "rode o doctor de dentro do repositório/plugin para ver os modelos configurados"
fi

echo "Integração (skills portadas para outros agentes):"
VERSAO=$(grep -m1 '^version' "$HERE/../pyproject.toml" 2>/dev/null | cut -d'"' -f2)
if [ -n "$VERSAO" ]; then
  for d in "$HOME/.agents/skills" "$HOME/.config/opencode/skills" "$HOME/.kiro/skills" "$HOME/.zcode/skills"; do
    [ -d "$d" ] || continue
    N=$(grep -ls 'video-editores:port\|plugin \[video-editores\]' "$d"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
    [ "${N:-0}" -gt 0 ] || continue
    # manifesto primeiro (fonte primária do integrar); sem ele, todas as versões distintas dos carimbos —
    # um re-port parcial não pode sair como "em dia". `(\.[0-9]+)*` exige dígito após o ponto: o cabeçalho até a
    # 0.13 era "…video-editores) 0.13.0." e o ponto final da frase não entra na versão
    V=$(sed -n 's/.*"versao": *"\([^"]*\)".*/\1/p' "$d/.video-editores.json" 2>/dev/null | head -1)
    [ -n "$V" ] || V=$(grep -h -oE 'video-editores:port +v?[0-9]+(\.[0-9]+)*|plugin \[video-editores\]\([^)]*\) v?[0-9]+(\.[0-9]+)*' "$d"/*/SKILL.md 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)*$' | sort -u | paste -sd, -)
    if [ "$V" = "$VERSAO" ]; then
      ok "$N skills do plugin em $d (port $V, em dia)"
    else
      miss "$N skills do plugin em $d estão desatualizadas (port ${V:-?} ≠ plugin $VERSAO)" "da instalação atual, rode: video-editores integrar <agente> [--usuario]"
    fi
  done
else
  opt "Integração" "rode o doctor de dentro do repositório/plugin para checar ports desatualizados"
fi

echo "Pacotes Python (baixados sob demanda por 'uv run --with'; nada a instalar):"
echo "  faster-whisper (/tomada, /legenda), rembg (/texto-atras, /tela-verde), edge-tts + pillow (/video-docs), verovio + resvg-py + numpy + scipy (/partitura)"
if command -v uv >/dev/null; then
  uv run --quiet --with faster-whisper python -c "import faster_whisper" 2>/dev/null \
    && ok "faster-whisper resolve via uv" || opt "faster-whisper" "será baixado no primeiro uso; precisa de internet"
fi
exit $MISSING
