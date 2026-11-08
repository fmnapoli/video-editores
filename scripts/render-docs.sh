#!/usr/bin/env bash
# Monta um vídeo a partir de um spec:  ./render.sh <caminho/spec.json>
# Os caminhos do spec (sources, out_dir, work_dir) são relativos ao diretório onde você
# roda o comando, normalmente a raiz do projeto de vídeos.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/../skills/video-docs/scripts/build.py"

die() { echo "erro: $*" >&2; exit 1; }
[ $# -eq 1 ] || die "uso: $0 <spec.json>"
[ -f "$1" ] || die "spec não existe: $1"
command -v uv >/dev/null      || die "uv não encontrado (https://docs.astral.sh/uv/)"
command -v ffmpeg >/dev/null  || die "ffmpeg não encontrado"
command -v ffprobe >/dev/null || die "ffprobe não encontrado"
grep -qE '^ ... (ass|subtitles) ' <<<"$(ffmpeg -hide_banner -filters 2>/dev/null)" \
  || die "este ffmpeg não tem libass (filtros ass/subtitles). Use o ffmpeg do apt."
[ -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf ] \
  || die "fonte DejaVu Sans Bold ausente: sudo apt install fonts-dejavu-core"

uv run --quiet --with edge-tts --with pillow python "$BUILD" "$1"
