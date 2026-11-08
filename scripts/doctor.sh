#!/usr/bin/env bash
# Verifica dependências do plugin video-editores.
# Uso: doctor.sh [--install]   (--install tenta instalar os pacotes Python que faltam)
set -u
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✘\033[0m %s  →  %s\n' "$1" "$2"; MISSING=1; }
MISSING=0

echo "Binários:"
for b in ffmpeg ffprobe; do command -v "$b" >/dev/null && ok "$b" || miss "$b" "instale ffmpeg (apt/brew/winget)"; done
command -v uv >/dev/null && ok "uv" || miss "uv" "curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v auto-editor >/dev/null && ok "auto-editor" || miss "auto-editor" "uv tool install auto-editor"
command -v yt-dlp      >/dev/null && ok "yt-dlp"      || miss "yt-dlp (só /referencia)" "uv tool install yt-dlp"
command -v blender     >/dev/null && ok "blender"     || miss "blender (só /3d)" "https://www.blender.org/download/"
command -v manim       >/dev/null && ok "manim"       || miss "manim (opcional, /animacao)" "uv tool install manim"

echo "Python:"
PY_PKGS=(faster_whisper:faster-whisper scenedetect:scenedetect[opencv] rembg:rembg[cpu] PIL:pillow numpy:numpy)
TO_INSTALL=()
for pair in "${PY_PKGS[@]}"; do
  mod="${pair%%:*}"; pkg="${pair#*:}"
  python3 -c "import $mod" 2>/dev/null && ok "$pkg" || { miss "$pkg" "pip install '$pkg'"; TO_INSTALL+=("$pkg"); }
done

if [[ "${1:-}" == "--install" && ${#TO_INSTALL[@]} -gt 0 ]]; then
  echo "Instalando: ${TO_INSTALL[*]}"
  python3 -m pip install --user "${TO_INSTALL[@]}" || python3 -m pip install --break-system-packages "${TO_INSTALL[@]}"
fi
exit $MISSING
