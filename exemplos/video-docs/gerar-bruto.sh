#!/usr/bin/env bash
# Gera um "bruto" sintético de 20 s (1280x720) para testar o montador sem gravação real.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p originais
ffmpeg -v error -y -f lavfi -i "testsrc2=size=1280x720:rate=30:duration=20" \
  -f lavfi -i "sine=frequency=440:duration=20" -shortest \
  -c:v libx264 -pix_fmt yuv420p -c:a aac originais/demo.mp4
echo "ok: originais/demo.mp4"
