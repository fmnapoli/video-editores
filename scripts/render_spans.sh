#!/usr/bin/env bash
# Renderiza só os trechos [start,end] de um JSON {"keep": [[s,e],...]} e concatena, na ordem da lista.
# Funciona com ou sem faixa de áudio. Uso: render_spans.sh ENTRADA.mp4 TRECHOS.json SAIDA.mp4
# A saída mantém a taxa de quadros da entrada: o filtro concat não declara taxa, e sem o `fps` o ffmpeg 7
# gravava 25 fps (um vídeo de 30 fps perdia 1 quadro em cada 6).
set -euo pipefail
IN="$1"; SPANS="$2"; OUT="$3"
HAS_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$IN" | head -1)
TAXA=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$IN" | head -1 | tr -d ',')
FILTER=$(python3 - "$SPANS" "$TAXA" "${HAS_AUDIO:+1}" <<'PY'
import json, sys
k = json.load(open(sys.argv[1], encoding="utf-8")).get("keep") or []
if not k:
    sys.exit("lista keep vazia: nada a renderizar")
taxa = sys.argv[2]
audio = len(sys.argv) > 3 and sys.argv[3] == "1"
parts, ins = [], ""
for i, (s, e) in enumerate(k):
    parts.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS[v{i}];")
    ins += f"[v{i}]"
    if audio:
        parts.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
                     f"afade=t=out:st={max(0, e - s - 0.02):.3f}:d=0.02[a{i}];")
        ins += f"[a{i}]"
print("".join(parts) + f"{ins}concat=n={len(k)}:v=1:a={1 if audio else 0}[vc]" + ("[a]" if audio else "") + f";[vc]fps={taxa}[v]")
PY
)
if [[ -n "$HAS_AUDIO" ]]; then
  ffmpeg -hide_banner -loglevel error -y -i "$IN" -filter_complex "$FILTER" -map "[v]" -map "[a]" \
    -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$OUT"
else
  ffmpeg -hide_banner -loglevel error -y -i "$IN" -filter_complex "$FILTER" -map "[v]" \
    -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -movflags +faststart "$OUT"
fi
echo "ok -> $OUT"
