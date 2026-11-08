#!/usr/bin/env bash
# Renderiza cenas Manim em paralelo (fundo transparente). Uso: render_cenas.sh ARQUIVO.py ql|qh [-j N] CENA [CENA...]
# Separadores: passe "Separador:N" (define CAP=N e grava SeparadorN.mov). Pula cenas já renderizadas.
set -euo pipefail
PY="$1"; Q="$2"; shift 2; J=2
if [[ "${1:-}" == "-j" ]]; then J="$2"; shift 2; fi
case "$Q" in ql) RES="960,540"; SUB="540p30";; qh) RES="1920,1080"; SUB="1080p30";; *) echo "qualidade: ql|qh"; exit 2;; esac
MOD="$(basename "${PY%.py}")"
render_one() {
  local spec="$1" cena="$1" cap="" nome="$1"
  if [[ "$spec" == Separador:* ]]; then cap="${spec#Separador:}"; cena="Separador"; nome="Separador$cap"; fi
  [[ -f "media/videos/$MOD/$SUB/$nome.mov" ]] && { echo "já existe: $nome"; return 0; }
  CAP="$cap" nice -n 5 manim "-$Q" -t -r "$RES" --fps 30 "$PY" "$cena" -o "$nome.mov" 2>&1 | grep -E "Rendered|rror|Traceback" || true
}
export -f render_one; export PY Q RES SUB MOD
printf '%s\n' "$@" | xargs -P "$J" -I{} bash -c 'render_one "$@"' _ {}
echo "render ($Q) concluído"
