#!/usr/bin/env bash
# Valida o backend `comfyui` contra um servidor ComfyUI de verdade (manual: não roda no CI nem no make test).
# Uso: VE_COMFYUI_URL=http://127.0.0.1:8188 tests/comfyui_real.sh
#
# 1. o workflow de produção (flux-schnell) é compatível com os nós deste servidor; o checkpoint dele pode faltar
#    (é só avisado), porque validar sem GPU é o caso que este teste cobre;
# 2. geração de ponta a ponta com tests/comfyui/sd15-cpu.json (SD 1.5, ~2 GB, roda em CPU): variações, folha,
#    registro, e mesma semente = mesmo PNG.
# Precisa do v1-5-pruned-emaonly-fp16.safetensors em models/checkpoints/ do servidor (link no próprio workflow).
set -euo pipefail
# shellcheck source=tests/_plataforma.sh
. "$(dirname "$0")/_plataforma.sh"
ROOT="$(caminho "$(cd "$(dirname "$0")/.." && pwd)")"
: "${VE_COMFYUI_URL:=http://127.0.0.1:8188}"; export VE_COMFYUI_URL
TAM="${TAM:-256}"
T="$(tmpdir)"; trap 'rm -rf "$T" || true' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
export PYTHONPATH="$ROOT"
ve() { python3 -m video_editores.cli gerar-imagem "$@"; }

python3 - <<'PY'
from video_editores import modelos
g = modelos.get_imagem("comfyui", workflow="flux-schnell")
s = g.servidor()
probs = g.validar_workflow()
assert not probs, "flux-schnell incompatível:\n  " + "\n  ".join(probs)
try:
    g.conferir()
    ck = "presente"
except RuntimeError as e:
    ck = "ausente (esperado sem GPU): " + str(e).split(" (")[0]
print(f"  servidor {g.url}: ComfyUI {s['versao']}, {s['dispositivos']}")
print(f"  checkpoint do flux-schnell: {ck}")
PY
pass "flux-schnell: todos os nós, entradas e ligações existem neste servidor"

WF="$ROOT/tests/comfyui/sd15-cpu.json"
VE_COMFYUI_WORKFLOW=$WF ve --conferir >/dev/null
t0=$(date +%s)
VE_COMFYUI_WORKFLOW=$WF ve "a lighthouse on a cliff at sunset, flat illustration" --id farol --out gerados \
  --variacoes 2 --semente 42 --largura "$TAM" --altura "$TAM" >/dev/null
t1=$(date +%s)
VE_COMFYUI_WORKFLOW=$WF ve "a lighthouse on a cliff at sunset, flat illustration" --id farol --out regerado \
  --variacoes 1 --semente 42 --largura "$TAM" --altura "$TAM" --sem-folha >/dev/null
python3 - "$TAM" <<'PY'
import hashlib, json, struct, sys
tam = int(sys.argv[1])
r = json.load(open("gerados/farol.json"))["rodadas"][0]
assert r["sementes"] == [42, 43] and r["backend"]["checkpoint"] == "v1-5-pruned-emaonly-fp16.safetensors", r
for f in r["arquivos"]:
    b = open(f"gerados/{f}", "rb").read(24)
    assert b[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", b[16:24]) == (tam, tam), f
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
assert h("gerados/farol-42.png") != h("gerados/farol-43.png"), "sementes diferentes deram a mesma imagem"
assert h("gerados/farol-42.png") == h("regerado/farol-42.png"), "mesma semente não reproduziu a imagem"
print(f"  servidor ComfyUI {r['servidor']['versao']}; workflow sha256 {r['backend']['workflow_sha256'][:12]}")
PY
pass "sd15-cpu: 2 variações ${TAM}x${TAM} em $((t1 - t0)) s, folha, registro, e a semente 42 regenera o mesmo PNG"
cp gerados/farol.folha.png "${FOLHA_OUT:-/dev/null}" 2>/dev/null || true
echo "comfyui real ok"
