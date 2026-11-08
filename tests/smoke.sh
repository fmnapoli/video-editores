#!/usr/bin/env bash
# Teste de fumaça: gera um vídeo sintético e roda os scripts que não dependem de modelos de IA.
# Uso: tests/smoke.sh        (só precisa de ffmpeg e python3)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/scripts"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }

# 12 s: vídeo de teste + áudio com 4 "falas" (tom) separadas por silêncio
ffmpeg -v error -y -f lavfi -i "testsrc2=size=1080x1920:rate=30:duration=12" \
  -f lavfi -i "sine=f=300:d=12" \
  -af "volume='if(lt(mod(t,3),2),1,0)':eval=frame" -shortest \
  -c:v libx264 -pix_fmt yuv420p -c:a aac in.mp4
pass "vídeo sintético"

# takes.py com transcrição falsa: a fala 2 foi repetida (a 1ª tentativa deve cair)
cat > in.transcript.json <<'JSON'
{"source":"in.mp4","language":"pt","duration":12.0,"segments":[
 {"start":0.0,"end":2.0,"text":"Olá, hoje vou mostrar o plugin.","avg_logprob":-0.2},
 {"start":3.0,"end":5.0,"text":"Ele corta o vídeo sozi","avg_logprob":-0.3},
 {"start":6.0,"end":8.0,"text":"Ele corta o vídeo sozinho em segundos.","avg_logprob":-0.2},
 {"start":9.0,"end":11.0,"text":"Valeu e até a próxima.","avg_logprob":-0.2}]}
JSON
python3 "$S/takes.py" in.transcript.json >/dev/null
python3 - <<'PY'
import json
d = json.load(open("in.takes.json"))
assert len(d["dropped"]) == 1 and d["dropped"][0]["start"] == 3.0, d
assert len(d["keep"]) == 3, d
PY
pass "takes.py descarta a tomada repetida"

bash "$S/render_spans.sh" in.mp4 in.takes.json out_tomada.mp4 >/dev/null
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out_tomada.mp4)
python3 -c "d=$DUR; assert 6.0 < d < 7.0, d"
pass "render_spans.sh monta os trechos (${DUR}s)"

cat > textos.json <<'JSON'
[{"text":"TÍTULO","start":0.2,"end":2.5,"style":"titulo","anim":"pop"},
 {"text":"Nome\\NCargo","start":3,"end":5,"style":"lower","anim":"slide"},
 {"text":"DESTAQUE","start":6,"end":7,"style":"destaque","anim":"fade"}]
JSON
python3 "$S/lettering_ass.py" out_tomada.mp4 textos.json --burn out_lettering.mp4 >/dev/null
grep -q "Dialogue" textos.ass && test -s out_lettering.mp4
pass "lettering_ass.py gera ASS e queima (sem drawtext)"

bash "$S/proof.sh" out_lettering.mp4 8 >/dev/null
test -s out_lettering.proof.jpg && test -s out_lettering.preview.mp4 && grep -q "quadros da folha" out_lettering.proof.txt
pass "proof.sh gera folha de contato, preview e relatório"

# vídeo sem áudio + keep vazio
ffmpeg -v error -y -f lavfi -i "testsrc2=size=320x180:rate=30:duration=3" -c:v libx264 -pix_fmt yuv420p mudo.mp4
echo '{"keep":[[0,1],[2,3]]}' > k.json && bash "$S/render_spans.sh" mudo.mp4 k.json mudo_out.mp4 >/dev/null && test -s mudo_out.mp4
echo '{"keep":[]}' > k0.json && ! bash "$S/render_spans.sh" mudo.mp4 k0.json x.mp4 >/dev/null 2>&1
pass "render_spans.sh: sem áudio funciona, keep vazio aborta"

# rotação de celular: lettering deve usar 1080x1920 exibido
ffmpeg -v error -y -f lavfi -i "testsrc2=size=1920x1080:rate=30:duration=1" -c:v libx264 -pix_fmt yuv420p -display_rotation 90 rot.mp4 2>/dev/null \
  || ffmpeg -v error -y -f lavfi -i "testsrc2=size=1920x1080:rate=30:duration=1" -c:v libx264 -pix_fmt yuv420p -metadata:s:v rotate=90 rot.mp4
echo '[{"text":"X","start":0,"end":1}]' > r.json && python3 "$S/lettering_ass.py" rot.mp4 r.json >/dev/null
grep -q "PlayResX: 1080" r.ass && grep -q "PlayResY: 1920" r.ass
pass "lettering_ass.py respeita a rotação do vídeo"

# takes.py com transcrição vazia aborta com mensagem
echo '{"segments":[]}' > vazio.transcript.json && ! python3 "$S/takes.py" vazio.transcript.json >/dev/null 2>&1
pass "takes.py aborta em transcrição vazia"

bash -n "$S"/*.sh && python3 -c 'import ast, sys; [ast.parse(open(f, encoding="utf-8").read(), f) for f in sys.argv[1:]]' "$S"/*.py "$ROOT"/skills/video-docs/scripts/*.py
pass "sintaxe de todos os scripts"

# frontmatter de todos os skills
for f in "$ROOT"/skills/*/SKILL.md; do
  head -1 "$f" | grep -q '^---$' && grep -q '^name: ' "$f" && grep -q '^description: ' "$f" \
    || { echo "frontmatter inválido: $f"; exit 1; }
done
pass "frontmatter dos $(ls -d "$ROOT"/skills/*/ | wc -l) skills"
python3 -c "import json; json.load(open('$ROOT/.claude-plugin/plugin.json')); json.load(open('$ROOT/.claude-plugin/marketplace.json'))"
pass "manifestos JSON válidos"
echo "smoke ok"
