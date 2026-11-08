#!/usr/bin/env bash
# Recorta todos os trechos de locutor (kind do aula.json "modos.locutor") em N trabalhadores paralelos,
# balanceados por duração. Cada trecho vira mattes/talk_<ini>.mp4 (+ _alpha.mp4) e um .done; reexecutar só faz o que falta.
# Uso: matte_workers.sh aula.json [N_TRABALHADORES=2]
# Dimensione pela máquina: cada trabalhador usa ~1,3 GB de RAM e (núcleos/N) threads; confira `nproc` e `free -g`.
# GPU NVIDIA: VE_DEVICE=cuda troca o onnxruntime pelo onnxruntime-gpu e liga o CUDAExecutionProvider no matte.py.
set -euo pipefail
CFG="$1"; N="${2:-2}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUG="$(cd "$HERE/../../.." && pwd)"
export VE_PKG_DIR="${VE_PKG_DIR:-$PLUG}"   # onde o matte.py acha o pacote video_editores
# pacotes do backend de segmentação configurado (VE_SEG/VE_DEVICE), um --with por pacote
mapfile -t WITHS < <(PYTHONPATH="$VE_PKG_DIR" python3 -c "
from video_editores import modelos
for p in modelos.deps('seg'): print('--with'); print(p)")
cd "$(dirname "$CFG")"; CFG="$(basename "$CFG")"
read -r CUT FUNDO MATTES LOCUTOR < <(python3 -c "
import json,sys; c=json.load(open(sys.argv[1])); print(c['corte'], c['identidade']+'/fundo.png', c.get('mattes','mattes'), c.get('modos',{}).get('locutor','locutor'))" "$CFG")
mkdir -p "$MATTES"
python3 - "$CFG" "$N" "$MATTES" "$LOCUTOR" > "$MATTES/lista.txt" <<'PY'
import json, sys
cfg, n, mattes, kind = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
c = json.load(open(cfg)); cenas = [x for x in json.load(open(c["cenas_corte"])) if x["kind"] == kind]
cenas.sort(key=lambda x: -x["cut_len"]); w = [[] for _ in range(n)]; d = [0.0] * n
for x in cenas:
    i = d.index(min(d)); w[i].append(x); d[i] += x["cut_len"]
for i in range(n):
    for x in sorted(w[i], key=lambda x: x["cut_start"]):
        print(i, f"{x['cut_start']:.3f}", f"{x['cut_end']:.3f}", f"talk_{int(x['cut_start']):05d}")
PY
THREADS=$(( $(nproc) / N )); [[ $THREADS -lt 1 ]] && THREADS=1
echo "trechos: $(wc -l < "$MATTES/lista.txt") · trabalhadores: $N · threads cada: $THREADS"
worker() {
  local w="$1"
  mapfile -t LINHAS < <(grep "^$w " "$MATTES/lista.txt")
  for l in "${LINHAS[@]}"; do
    read -r _ s e name <<< "$l"
    [[ -f "$MATTES/$name.done" ]] && continue
    # `< /dev/null` é obrigatório: sem ele o processo filho engole o resto da lista (stdin herdado)
    uv run "${WITHS[@]}" python -I "$HERE/matte.py" \
      "$CUT" "$s" "$e" "$FUNDO" "$MATTES/$name" --threads "$THREADS" < /dev/null && touch "$MATTES/$name.done"
  done
  echo "trabalhador $w: fim"
}
for ((i = 0; i < N; i++)); do worker "$i" > "$MATTES/worker$i.log" 2>&1 & done
wait
echo "mattes prontos: $(ls "$MATTES"/*.done | wc -l)"
