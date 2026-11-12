#!/usr/bin/env bash
# Roda o montador do video-docs de ponta a ponta sem internet, com um stub do edge-tts.
# Uso: tests/docs_offline.sh   (precisa de ffmpeg com libass, uv e fonte DejaVu Sans Bold)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp -r "$ROOT/exemplos/video-docs/." "$T/"
cd "$T"
bash ./gerar-bruto.sh >/dev/null
PYTHONPATH="$ROOT/tests/stub" uv run --quiet --with pillow python "$ROOT/skills/video-docs/scripts/build.py" spec.json >/dev/null
test -s saida/demo.mp4 && test -s saida/demo.srt && test -s saida/roteiro-demo.md
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of csv=p=0 saida/demo.mp4)
[[ "$W" == "h264,1280,720" ]] || { echo "saída inesperada: $W"; exit 1; }
grep -q "Dialogue" trabalho/demo/*.ass
CONF="$ROOT/skills/video-docs/scripts/confere_saida.py"
python3 "$CONF" spec.json | grep -q '^OK'
test -s trabalho/demo/palavras.transcript.json
python3 -c 'import json,sys; s=json.load(open(sys.argv[1]))["segments"]; w=[x["word"] for g in s for x in g["words"]]; assert "dashboard" in w and "API." in w, w' trabalho/demo/palavras.transcript.json

# faixa do navegador com logo, tarja fixa desligável por cena, .srt/roteiro em pastas próprias, avisos
ffmpeg -v error -y -f lavfi -i color=c=orange:s=120x40:d=0.1 -frames:v 1 logo.png
python3 - <<'PY'
import json
s = json.load(open("spec.json"))
s.update(slug="demo2", work_dir="trabalho/demo2", srt_dir="legendas", roteiro_dir="roteiros",
         chrome={"band": 100, "logo": "logo.png", "client": [722, 105, 220, 30], "client_label": "cliente de teste"})
s["scenes"][1]["no_client"] = True
s["scenes"][1]["callouts"].append({"at": [14.0, 16.0], "box": [100, 600, 200, 60], "balloon": "baixo demais", "balloon_at": [100, 650]})
json.dump(s, open("spec2.json", "w"), ensure_ascii=False)
PY
R=$(PYTHONPATH="$ROOT/tests/stub" VE_STUB_EDGE_FALHAS=2 VE_TTS_ESPERA=0 uv run --quiet --with pillow python "$ROOT/skills/video-docs/scripts/build.py" spec2.json 2>err.txt)
grep -q "tentativa 1 falhou" err.txt
test -s saida/demo2.mp4 && test -s legendas/demo2.srt && test -s roteiros/roteiro-demo2.md && test ! -e saida/demo2.srt
python3 -c 'import json,sys; a=json.loads(sys.argv[1])["avisos"]; assert any("faixa da legenda" in x for x in a) and any("balão" in x for x in a) and any("cai num corte" in x for x in a), a' "$R"
grep -q "cliente de teste" trabalho/demo2/demo2.ass
[[ $(grep -c "cliente de teste" trabalho/demo2/demo2.ass) == 1 ]] || { echo "no_client não desligou a tarja"; exit 1; }
grep -q "overlay=" trabalho/demo2/demo2.ffmpeg.txt
python3 "$CONF" spec2.json | grep -q '^OK'

# TTS que nunca responde: o build sai com erro e o vídeo anterior fica intacto; o conferidor acusa
antes=$(stat -c %Y saida/demo2.mp4)
python3 -c 'import json; s=json.load(open("spec2.json")); s["scenes"][1]["legend"][0]="Texto novo que obriga a sintetizar de novo,"; json.dump(s, open("spec2.json","w"), ensure_ascii=False)'
if PYTHONPATH="$ROOT/tests/stub" VE_STUB_EDGE_FALHAS=9 VE_TTS_ESPERA=0 uv run --quiet --with pillow python "$ROOT/skills/video-docs/scripts/build.py" spec2.json >/dev/null 2>&1; then
  echo "build deveria falhar com o TTS fora"; exit 1
fi
[[ $(stat -c %Y saida/demo2.mp4) == "$antes" ]] && test ! -e trabalho/demo2/demo2.parcial.mp4
if python3 "$CONF" spec2.json >conf.txt; then echo "conferidor deveria acusar"; exit 1; fi
grep -q '^REFAZER  demo2' conf.txt

echo "video-docs offline ok ($(ffprobe -v error -show_entries format=duration -of csv=p=0 saida/demo.mp4)s)"
