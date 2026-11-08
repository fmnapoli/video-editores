#!/usr/bin/env bash
# Verifica dependências do plugin video-editores (não instala nada no Python do sistema).
# Uso: doctor.sh
set -u
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✘\033[0m %s  →  %s\n' "$1" "$2"; MISSING=1; }
opt()  { printf '  \033[33m•\033[0m %s  →  %s\n' "$1" "$2"; }
MISSING=0

echo "Base (obrigatório):"
command -v ffmpeg  >/dev/null && ok "ffmpeg"  || miss "ffmpeg"  "apt install ffmpeg | brew install ffmpeg"
command -v ffprobe >/dev/null && ok "ffprobe" || miss "ffprobe" "vem com o ffmpeg"
if command -v ffmpeg >/dev/null; then
  ffmpeg -hide_banner -filters 2>/dev/null | grep -qE ' (ass|subtitles) ' && ok "ffmpeg com libass" \
    || miss "ffmpeg com libass" "Linux: ffmpeg do apt. macOS: 'brew install ffmpeg-full' e ponha \$(brew --prefix ffmpeg-full)/bin antes no PATH (a fórmula 'ffmpeg' do Homebrew vem sem libass desde a v8)"
fi
command -v python3 >/dev/null && ok "python3" || miss "python3" "instale Python 3.10+"
command -v uv      >/dev/null && ok "uv"      || miss "uv" "https://docs.astral.sh/uv/getting-started/installation/"
if command -v fc-list >/dev/null; then
  fc-list 2>/dev/null | grep -qi "DejaVuSans-Bold\|DejaVu Sans:style=Bold" && ok "fonte DejaVu Sans Bold" \
    || miss "fonte DejaVu Sans Bold" "apt install fonts-dejavu-core | brew install --cask font-dejavu"
else
  opt "fontconfig (fc-list)" "sem ele não dá para checar a fonte; instale fontconfig"
fi

echo "CLIs por skill:"
command -v auto-editor >/dev/null && ok "auto-editor (/corte)" || miss "auto-editor (/corte)" "uv tool install auto-editor"
command -v yt-dlp      >/dev/null && ok "yt-dlp (/referencia)" || opt "yt-dlp (/referencia)" "uv tool install yt-dlp"
command -v scenedetect >/dev/null && ok "scenedetect (/referencia, /efeitos)" || opt "scenedetect" "uv tool install 'scenedetect[opencv]'"
command -v manim       >/dev/null && ok "manim (/animacao, /video-animado)" || opt "manim (/animacao, /video-animado)" "uv tool install manim  (se o manimpango falhar por falta de libpango-dev: micromamba create -n manim -c conda-forge manim, ver docs/troubleshooting.md)"
command -v blender     >/dev/null && ok "blender (/3d)" || opt "blender (/3d)" "https://www.blender.org/download/"

echo "Pacotes Python (baixados sob demanda por 'uv run --with'; nada a instalar):"
echo "  faster-whisper (/tomada, /legenda), rembg (/texto-atras, /tela-verde), edge-tts + pillow (/video-docs)"
if command -v uv >/dev/null; then
  uv run --quiet --with faster-whisper python -c "import faster_whisper" 2>/dev/null \
    && ok "faster-whisper resolve via uv" || opt "faster-whisper" "será baixado no primeiro uso; precisa de internet"
fi
exit $MISSING
