#!/usr/bin/env bash
# Gera material de aprovação: folha de contato (grid de frames), preview leve e info técnica.
# Não usa drawtext (compatível com ffmpeg estático); os instantes de cada quadro vão no .proof.txt.
# Uso: proof.sh VIDEO.mp4 [N_FRAMES=12]
set -euo pipefail
IN="$1"; N="${2:-12}"
# shellcheck source=scripts/_py.sh
. "$(cd "$(dirname "$0")" && pwd)/_py.sh"   # VE_PY, py e sonda (python3 ou python; saída sem \r no Windows)
BASE="${IN%.*}"
DUR=$(sonda -v error -show_entries format=duration -of default=nw=1:nk=1 "$IN")
[[ "$DUR" =~ ^[0-9.]+$ ]] || DUR=$(sonda -v error -select_streams v:0 -show_entries stream=duration -of default=nw=1:nk=1 "$IN")
[[ "$DUR" =~ ^[0-9.]+$ && "$N" =~ ^[0-9]+$ && "$N" -gt 0 ]] || { echo "duração ($DUR) ou N ($N) inválidos" >&2; exit 2; }
COLS=4; ROWS=$(( (N + COLS - 1) / COLS ))
FPS=$(py -c 'import sys; print(f"{int(sys.argv[1])/float(sys.argv[2]):.5f}")' "$N" "$DUR")
# -reinit_filter 0: vídeo montado por blocos muda de parâmetros (cor, SPS) nas emendas e o ffmpeg reiniciaria o
# grafo ali, esvaziando o `tile`: a folha saía só com os quadros depois da última emenda.
ffmpeg -hide_banner -loglevel error -y -reinit_filter 0 -i "$IN" \
  -vf "fps=$FPS,scale=360:-2,tile=${COLS}x${ROWS}:padding=4:margin=4" \
  -frames:v 1 "${BASE}.proof.jpg"
ffmpeg -hide_banner -loglevel error -y -i "$IN" -vf "scale=-2:480" -c:v libx264 -preset veryfast -crf 30 \
  -c:a aac -b:a 96k -movflags +faststart "${BASE}.preview.mp4"
{
  sonda -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels \
    -of compact "$IN"
  py -c 'import sys; n, d = int(sys.argv[1]), float(sys.argv[2]); print("quadros da folha (s):", ", ".join(f"{(i+0.5)*d/n:.1f}" for i in range(n)))' "$N" "$DUR"
  ffmpeg -hide_banner -nostats -i "$IN" -af loudnorm=print_format=summary -f null - 2>&1 \
    | tr -d '\r' | grep -E "Input Integrated|Input True Peak" || true
} > "${BASE}.proof.txt"
# Gate de pico real: acima de PROVA_TP_MAX (padrão -1,0 dBTP) o vídeo distorce em alto-falante de celular e as
# plataformas reprocessam o áudio. Sai com código 3 (PROVA_SEM_GATE=1 só avisa). Conserto: scripts/normalizar_audio.py.
TP=$(grep "Input True Peak" "${BASE}.proof.txt" | awk '{print $(NF-1)}' || true)
if [[ -n "$TP" ]] && "$VE_PY" -c 'import sys; sys.exit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)' "$TP" "${PROVA_TP_MAX:--1.0}"; then
  echo "PICO ACIMA DO LIMITE: $TP dBTP > ${PROVA_TP_MAX:--1.0} dBTP (normalize com scripts/normalizar_audio.py)" | tee -a "${BASE}.proof.txt" >&2
  [[ "${PROVA_SEM_GATE:-}" == "1" ]] || exit 3
fi
echo "ok -> ${BASE}.proof.jpg  ${BASE}.preview.mp4  ${BASE}.proof.txt"
