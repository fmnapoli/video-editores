#!/usr/bin/env bash
# Gera material de aprovação: folha de contato (grid de frames), preview leve e info técnica.
# Não usa drawtext (compatível com ffmpeg estático); os instantes de cada quadro vão no .proof.txt.
# Uso: proof.sh VIDEO.mp4 [N_FRAMES=12]
set -euo pipefail
IN="$1"; N="${2:-12}"
BASE="${IN%.*}"
DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$IN")
COLS=4; ROWS=$(( (N + COLS - 1) / COLS ))
FPS=$(python3 -c "print(f'{$N/$DUR:.5f}')")
ffmpeg -hide_banner -loglevel error -y -i "$IN" \
  -vf "fps=$FPS,scale=360:-2,tile=${COLS}x${ROWS}:padding=4:margin=4" \
  -frames:v 1 "${BASE}.proof.jpg"
ffmpeg -hide_banner -loglevel error -y -i "$IN" -vf "scale=-2:480" -c:v libx264 -preset veryfast -crf 30 \
  -c:a aac -b:a 96k -movflags +faststart "${BASE}.preview.mp4"
{
  ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
    -of compact "$IN"
  python3 -c "
n,d=$N,$DUR
print('quadros da folha (s):', ', '.join(f'{(i+0.5)*d/n:.1f}' for i in range(n)))"
  ffmpeg -hide_banner -nostats -i "$IN" -af loudnorm=print_format=summary -f null - 2>&1 \
    | grep -E "Input Integrated|Input True Peak" || true
} > "${BASE}.proof.txt"
echo "ok -> ${BASE}.proof.jpg  ${BASE}.preview.mp4  ${BASE}.proof.txt"
