#!/usr/bin/env bash
# Montagem final da videoaula: blocos (em paralelo) -> concat -> lettering (opcional) -> loudnorm 2 passos (-14 LUFS)
# -> SRT -> prova. Uso: finalizar.sh aula.json SAIDA.mp4 SAIDA.srt [--textos textos.json] [--ajustes ajustes.json] [--jobs N]
set -euo pipefail
CFG="$1"; SAIDA="$2"; SRT="$3"; shift 3
TEXTOS=""; AJUSTES=""; JOBS=2
while [[ $# -gt 0 ]]; do case "$1" in --textos) TEXTOS="$2"; shift 2;; --ajustes) AJUSTES="$2"; shift 2;; --jobs) JOBS="$2"; shift 2;; *) echo "arg desconhecido $1"; exit 2;; esac; done
HERE="$(cd "$(dirname "$0")" && pwd)"; PLUG="$(cd "$HERE/../../.." && pwd)"
SAIDA="$(realpath -m "$SAIDA")"; SRT="$(realpath -m "$SRT")"; [[ -n "$TEXTOS" ]] && TEXTOS="$(realpath "$TEXTOS")"; [[ -n "$AJUSTES" ]] && AJUSTES="$(realpath "$AJUSTES")"
V1=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('corte_v1','aula01_corte.v1.json'))" "$CFG")
TRANS=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['transcript'])" "$CFG")
cd "$(dirname "$CFG")"; CFG="$(basename "$CFG")"
mkdir -p "$(dirname "$SAIDA")" "$(dirname "$SRT")"
python3 "$HERE/montar_aula.py" "$CFG" render --jobs "$JOBS"
python3 "$HERE/montar_aula.py" "$CFG" concat _montado.mp4
IN=_montado.mp4
if [[ -n "$TEXTOS" ]]; then
  FONTE=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('fonte','Inter'))" "$CFG")
  python3 "$PLUG/scripts/lettering_ass.py" _montado.mp4 "$TEXTOS" --font "$FONTE" --burn _lettering.mp4; IN=_lettering.mp4
fi
STATS=$(ffmpeg -hide_banner -nostats -i "$IN" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/{/,/}/p')
read -r II TP LRA TH OFF < <(echo "$STATS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['input_i'], d['input_tp'], d['input_lra'], d['input_thresh'], d['target_offset'])")
ffmpeg -hide_banner -loglevel error -y -i "$IN" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$II:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$TH:offset=$OFF:linear=true" \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$SAIDA"
python3 "$HERE/legenda_aula.py" "$CFG" "$V1" "$TRANS" "$SRT" ${AJUSTES:+--ajustes "$AJUSTES"}
bash "$PLUG/scripts/proof.sh" "$SAIDA" 16
echo "ok -> $SAIDA · $SRT"
