#!/usr/bin/env bash
# Roda o montador do video-docs de ponta a ponta sem internet, com um stub do edge-tts.
# Uso: tests/docs_offline.sh   (precisa de ffmpeg com libass, uv e fonte DejaVu Sans Bold)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp -r "$ROOT/exemplos/video-docs/." "$T/"
cd "$T"
bash ./gerar-bruto.sh >/dev/null
PYTHONPATH="$ROOT/tests/stub" uv run --quiet --with pillow python "$ROOT/skills/video-docs/scripts/build.py" spec.json >/dev/null
test -s saida/demo.mp4 && test -s saida/demo.srt && test -s saida/roteiro-demo.md
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of csv=p=0 saida/demo.mp4)
[[ "$W" == "h264,1280,720" ]] || { echo "saída inesperada: $W"; exit 1; }
grep -q "Dialogue" trabalho/demo/*.ass
echo "video-docs offline ok ($(ffprobe -v error -show_entries format=duration -of csv=p=0 saida/demo.mp4)s)"
