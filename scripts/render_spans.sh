#!/usr/bin/env bash
# Renderiza só os trechos [start,end] de um JSON {"keep": [[s,e],...]} e concatena.
# Uso: render_spans.sh ENTRADA.mp4 TRECHOS.json SAIDA.mp4
set -euo pipefail
IN="$1"; SPANS="$2"; OUT="$3"
FILTER=$(python3 - "$SPANS" <<'PY'
import json, sys
k = json.load(open(sys.argv[1]))["keep"]
parts = []
for i, (s, e) in enumerate(k):
    parts.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];"
                 f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
                 f"afade=t=out:st={max(0,e-s-0.02):.3f}:d=0.02[a{i}];")
ins = "".join(f"[v{i}][a{i}]" for i in range(len(k)))
print("".join(parts) + f"{ins}concat=n={len(k)}:v=1:a=1[v][a]")
PY
)
ffmpeg -hide_banner -loglevel error -y -i "$IN" -filter_complex "$FILTER" -map "[v]" -map "[a]" \
  -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k -movflags +faststart "$OUT"
echo "ok -> $OUT"
