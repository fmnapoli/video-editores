#!/usr/bin/env bash
# Montagem final da videoaula: blocos (em paralelo) -> concat -> lettering (opcional) -> normalização (-14 LUFS, pico real <= -1,5 dBTP)
# -> SRT -> prova. Uso: finalizar.sh aula.json SAIDA.mp4 SAIDA.srt [--textos textos.json] [--ajustes ajustes.json] [--jobs N] [--limpar-audio]
# --limpar-audio: passa-alta 80 Hz + redução de ruído (afftdn) antes da normalização; use quando a sala tiver zumbido/ar-condicionado.
set -euo pipefail
CFG="$1"; SAIDA="$2"; SRT="$3"; shift 3
TEXTOS=""; AJUSTES=""; JOBS=2; LIMPAR=""
while [[ $# -gt 0 ]]; do case "$1" in --textos) TEXTOS="$2"; shift 2;; --ajustes) AJUSTES="$2"; shift 2;; --jobs) JOBS="$2"; shift 2;; --limpar-audio) LIMPAR="highpass=f=80,afftdn=nf=-25:nr=12"; shift;; *) echo "arg desconhecido $1"; exit 2;; esac; done
HERE="$(cd "$(dirname "$0")" && pwd)"; PLUG="$(cd "$HERE/../../.." && pwd)"
# shellcheck source=../../../scripts/_py.sh
. "$PLUG/scripts/_py.sh"   # VE_PY, py e sonda (python3 ou python; saída sem \r no Windows)
SAIDA="$(realpath -m "$SAIDA")"; SRT="$(realpath -m "$SRT")"; [[ -n "$TEXTOS" ]] && TEXTOS="$(realpath "$TEXTOS")"; [[ -n "$AJUSTES" ]] && AJUSTES="$(realpath "$AJUSTES")"
V1=$(py -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8')).get('corte_v1','aula01_corte.v1.json'))" "$CFG")
TRANS=$(py -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['transcript'])" "$CFG")
cd "$(dirname "$CFG")"; CFG="$(basename "$CFG")"
mkdir -p "$(dirname "$SAIDA")" "$(dirname "$SRT")"
"$VE_PY" "$HERE/montar_aula.py" "$CFG" render --jobs "$JOBS"
"$VE_PY" "$HERE/montar_aula.py" "$CFG" concat _montado.mp4
IN=_montado.mp4
if [[ -n "$TEXTOS" ]]; then
  FONTE=$(py -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8')).get('fonte','Inter'))" "$CFG")
  "$VE_PY" "$PLUG/scripts/lettering_ass.py" _montado.mp4 "$TEXTOS" --font "$FONTE" --burn _lettering.mp4; IN=_lettering.mp4
fi
# ganho estático + limiter de pico real, medido antes e depois (nunca loudnorm linear: estourou +9 dBTP numa montagem por blocos)
"$VE_PY" "$PLUG/scripts/normalizar_audio.py" "$IN" "$SAIDA" --alvo -14 --tp -1.5 ${LIMPAR:+--filtro "$LIMPAR"}
"$VE_PY" "$HERE/legenda_aula.py" "$CFG" "$V1" "$TRANS" "$SRT" ${AJUSTES:+--ajustes "$AJUSTES"}
bash "$PLUG/scripts/proof.sh" "$SAIDA" 16
echo "ok -> $SAIDA · $SRT"
