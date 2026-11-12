#!/usr/bin/env bash
# Testa a skill /partitura: notação (Verovio + resvg, via uv) e exemplo tocado (síntese + animação + mux AAC).
# Uso: tests/partitura.sh   (precisa de ffmpeg, python3 e uv; os pacotes chegam pelo uv run --with)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
P="$ROOT/skills/partitura/scripts"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
PART=(uv run --quiet --with verovio --with resvg-py --with pillow python -I "$P/partitura.py")
TOCA=(uv run --quiet --with numpy --with scipy --with pillow python -I "$P/tocar.py")

"${PART[@]}" "$ROOT/skills/partitura/templates/padroes-exemplo.json" GRADE PARA CINCO --out partituras >/dev/null
python3 - <<'PY'
import json, struct
def png(p):
    with open(p, "rb") as f:
        f.read(16); return struct.unpack(">II", f.read(8))
assert png("partituras/GRADE.png") == (1800, 270) and png("partituras/GRADE_big.png") == (1800, 430)
g = json.load(open("partituras/GRADE_big.json"))
assert g["tempos"] == 8 and len(g["notas"]) == 32, (g["tempos"], len(g["notas"]))          # 16 semicolcheias × 2 compassos
assert g["beats_px"] == sorted(g["beats_px"]) and 0 < g["beats_px"][0] < g["fim_px"] <= 1800, g["beats_px"]
assert all(0 <= n["x"] <= 1800 and g["y0"] <= n["y"] <= g["y1"] for n in g["notas"])
assert g["titulo"].startswith("Um tempo")
p = json.load(open("partituras/PARA_big.json"))
assert sum(n["acento"] for n in p["notas"]) == 4, "X na grade vira acento (2 por compasso)"    # 'X.xx .x..' ×2 compassos
assert {n["inst"] for n in p["notas"]} == {"hh", "sn", "bd"} and len(p["notas"]) == 40
c = json.load(open("partituras/CINCO_big.json"))
assert c["tempos"] == 20 and c["compassos"] == 4 and len(c["notas"]) == 28, (c["tempos"], len(c["notas"]))   # div=1 -> 4 compassos
xml = open("partituras/PARA_big.musicxml").read()
assert xml.count("<measure ") == 2 and "<beats>4</beats>" in xml and 'color="#2563EB"' in xml and 'color="#DB2777"' in xml
PY
pass "partitura.py: cartões 1800×270/430, notas e tempos com posição, acentos da grade, manulação colorida"

echo '[{"id":"X","ts":[4,4],"div":4,"hh":"x.x."}]' > ruim.json
! "${PART[@]}" ruim.json --out r >/dev/null 2>&1
echo '[{"id":"Y","ts":[4,4],"div":3,"hh":"all"}]' > ruim2.json
! "${PART[@]}" ruim2.json --out r >/dev/null 2>&1
pass "partitura.py: grade com tamanho errado e div=3 abortam"

"${TOCA[@]}" CINCO --partituras partituras --out exemplos --bpm 120 --voltas 1 --contagem >/dev/null
test -s exemplos/CINCO.mp4 && test -s exemplos/CINCO.wav && test -s exemplos/CINCO.json
python3 - <<'PY'
import json, subprocess
pr = lambda f, st, e: subprocess.run(["ffprobe", "-v", "error", "-select_streams", st, "-show_entries", f"stream={e}", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
m = json.load(open("exemplos/CINCO.json"))
# contagem (1 compasso de 5 tempos a 120 bpm = 2,5 s) + 4 compassos (10 s) + 1 s de cauda, no grid de quadros
assert abs(m["dur"] - 13.5) < 1 / 30 and m["pre"] == 2.5 and len(m["eventos"]) == 28, m
nf = int(pr("exemplos/CINCO.mp4", "v:0", "nb_frames")); assert nf == round(m["dur"] * 30), nf
va, aa = float(pr("exemplos/CINCO.mp4", "v:0", "duration")), float(pr("exemplos/CINCO.wav", "a:0", "duration"))
assert abs(va - aa) < 0.002 and abs(va - m["dur"]) < 0.002, (va, aa, m["dur"])
assert pr("exemplos/CINCO.mp4", "a:0", "codec_name") == "aac" and pr("exemplos/CINCO.mp4", "a:0", "sample_rate") == "48000"
assert pr("exemplos/CINCO.mp4", "v:0", "width,height") == "1920,1080"
PY
python3 "$ROOT/scripts/normalizar_audio.py" exemplos/CINCO.mp4 --medir | python3 -c "
import json, sys; d = json.load(sys.stdin); assert d['TP'] <= -1.5 and d['I'] > -30, d"
pass "tocar.py: vídeo e wav com a mesma duração no grid de quadros, AAC 48 kHz, pico real ≤ -1,5 dBTP"

cp exemplos/CINCO.wav antes.wav
"${TOCA[@]}" CINCO --partituras partituras --out exemplos --bpm 120 --voltas 1 --contagem --so-audio >/dev/null
cmp -s antes.wav exemplos/CINCO.wav
pass "tocar.py: --so-audio regenera o mesmo wav (síntese determinística)"

# identidade do projeto (ADR-17): fundos.cartela da marca vira o fundo do exemplo quando não há --fundo
mkdir -p marca && ffmpeg -v error -y -f lavfi -i color=c=0xC81E1E:s=1920x1080:d=0.1 -frames:v 1 marca/bg.png
echo '{"cores": {"fundo": "#0B2545", "acento": "#2DD4BF", "texto": "#FFFFFF"}, "fundos": {"cartela": "bg.png"}}' > marca/marca.json
"${TOCA[@]}" CINCO --partituras partituras --out exemplos_m --bpm 120 --voltas 1 >/dev/null
ffmpeg -v error -y -ss 1 -i exemplos_m/CINCO.mp4 -frames:v 1 -vf "crop=8:8:20:20,scale=1:1" -f rawvideo -pix_fmt rgb24 px.rgb
python3 -c 'r, g, b = open("px.rgb", "rb").read()[:3]; assert r > 150 and g < 80 and b < 80, (r, g, b)'
rm -rf marca
pass "tocar.py: fundo da marca do projeto (marca/marca.json) quando não há --fundo"

AND=(uv run --quiet --with librosa --with numpy --with scipy --with soundfile python -I "$P/andamento.py")
"${AND[@]}" exemplos/CINCO.wav --tempos 5 --bumbo 0 --out medido.json >/dev/null 2>&1
python3 - <<'PY'
import json
r = json.load(open("medido.json"))["CINCO"]
assert abs(r["bpm"] - 120) < 1.5, r["bpm"]                                     # sintetizado a 120 bpm
assert r["n"] == 5 and r["confiavel"], (r["fase"], r["contrastes"])
# os "1" caem nos bumbos: 2,5 s (fim da contagem de 5 tempos), 5,0, 7,5, 10,0; o índice `fase` depende de quantas
# batidas da contagem o tracker pegou, por isso se confere o instante, não o índice
bd = [2.5, 5.0, 7.5, 10.0]
assert len(r["uns"]) == 4 and all(abs(u - t) < 0.1 for u, t in zip(r["uns"], bd)), r["uns"]
PY
pass "andamento.py: bpm, fase e instantes do 1 recuperados do exemplo sintetizado"
echo "partitura ok"
