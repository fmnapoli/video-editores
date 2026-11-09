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

# gate de pico real da prova e normalização pelo núcleo
ffmpeg -v error -y -i out_tomada.mp4 -af "volume=24dB" -c:v copy -c:a aac quente.mp4
if bash "$S/proof.sh" quente.mp4 4 >/dev/null 2>&1; then echo "proof devia sair com 3"; exit 1; fi
grep -q "PICO ACIMA DO LIMITE" quente.proof.txt
PROVA_SEM_GATE=1 bash "$S/proof.sh" quente.mp4 4 >/dev/null 2>&1
python3 "$S/normalizar_audio.py" quente.mp4 frio.mp4 --alvo -14 >/dev/null
bash "$S/proof.sh" frio.mp4 4 >/dev/null
grep -q "Input True Peak" frio.proof.txt && ! grep -q "PICO ACIMA" frio.proof.txt
python3 "$S/normalizar_audio.py" frio.mp4 --medir | python3 -c "import json,sys; d=json.load(sys.stdin); assert -15.5 < d['I'] < -12.5 and d['TP'] <= -1.0, d"
pass "proof.sh reprova pico > -1 dBTP (código 3); normalizar_audio.py conserta (-14 LUFS, vídeo copiado)"

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

# highlights.py e checklist_ass.py com transcrição sintética (palavras com tempo)
python3 - <<'PY'
import json
segs=[]
def seg(t0,text):
    ws=text.split(); cur=t0; wl=[]
    for w in ws:
        wl.append({"start":round(cur,2),"end":round(cur+0.3,2),"word":" "+w}); cur+=0.35
    segs.append({"start":t0,"end":round(cur,2),"text":text,"words":wl,"avg_logprob":-0.2})
seg(0.5,"Olá, hoje vou mostrar três coisas importantes sobre containers.")
seg(3.5,"Primeiro, o backup é diário e automático.")
seg(6.0,"Segundo, o monitoramento roda vinte e quatro por sete.")
seg(8.8,"Terceiro, rollback em um clique.")
json.dump({"duration":12,"segments":segs},open("hl.transcript.json","w"),ensure_ascii=False)
json.dump([{"text":"Backup diário","trigger":"backup"},{"text":"Monitoramento","trigger":"monitoramento"},{"text":"Sem gatilho","trigger":"xyzqq"}],open("itens.json","w"),ensure_ascii=False)
PY
python3 "$S/highlights.py" hl.transcript.json --target 6 --keywords "backup,rollback" --min-block 2 >/dev/null
python3 -c "import json; k=json.load(open('hl.highlights.json'))['keep']; assert 1 <= len(k) <= 3 and sum(e-s for s,e in k) <= 6.5, k"
python3 "$S/highlights.py" hl.transcript.json --reels 2 --reel-len 4 --min-block 2 --out r.json >/dev/null
python3 -c "import json; k=json.load(open('r.json'))['keep']; assert len(k)==2 and all(abs((e-s)-4)<0.05 for s,e in k), k"
pass "highlights.py: corte por alvo e modo reels"
python3 "$S/checklist_ass.py" in.mp4 itens.json hl.transcript.json --burn out_check.mp4 2>erros.txt >/dev/null
grep -q "Sem gatilho" erros.txt && grep -c "Dialogue" itens.ass | grep -q "^5$" && test -s out_check.mp4
pass "checklist_ass.py: 2 itens no tempo da fala, 1 sem gatilho avisado"

# estilos cartao e capa
echo '[{"text":"Funciona?","start":0,"end":1,"style":"cartao","autor":"@x"},{"text":"A\\NB","start":1,"end":2,"style":"capa","kicker":"k"}]' > t2.json
python3 "$S/lettering_ass.py" in.mp4 t2.json >/dev/null && grep -q "Cartao" t2.ass && grep -q "\\p1" t2.ass
pass "lettering_ass.py: estilos cartao e capa"

# video-animado: narração com stub do edge-tts, cenas sintéticas, montagem e folha
VA="$ROOT/skills/video-animado/scripts"
mkdir -p va && cd va
cat > cenas.json <<'JSON'
{"slug":"va","glossary":{"operator":"operêitor"},"cenas":[
 {"id":"S1","classe":"S1","titulo":"Um","narracao":"O operator monta tudo na ordem certa. Em menos de três minutos, o ambiente está pronto."},
 {"id":"S2","classe":"S2","titulo":"Dois","narracao":"Se uma peça cai, ele recria sozinho."},
 {"id":"V1","classe":"V1","titulo":"","duracao":1.5},
 {"id":"X1","video":"ex/x.mp4","audio":"ex/x.wav","volume":0.5}]}
JSON
# X1: bloco pronto com áudio próprio (como um exemplo tocado do /partitura): 1,2 s de seno
mkdir -p ex && ffmpeg -v error -y -f lavfi -i "sine=f=440:d=1.2" -ar 48000 -ac 2 ex/x.wav \
  && ffmpeg -v error -y -f lavfi -i "color=c=0x3b0764:size=640x360:rate=30:duration=1.2" -c:v libx264 -pix_fmt yuv420p ex/x.mp4
PYTHONPATH="$ROOT/tests/stub" python3 "$VA/tts_cenas.py" cenas.json --out tts >/dev/null
test -s tts/S1.mp3 && test -s tts/S1.words.json && python3 -c "
import json; t=json.load(open('tts/tempos.json')); assert t['V1']['mudo'] and t['S1']['total']>t['S1']['fala']>0, t
assert t['X1']['mudo'] and t['X1']['audio'] == 'ex/x.wav' and abs(t['X1']['total'] - 1.2) < 0.01, t['X1']"
grep -q "operêitor" tts/S1.hash || true
mkdir -p mp4 && for id in S1 S2 V1; do
  d=$(python3 -c "import json; print(json.load(open('tts/tempos.json'))['$id']['total'])")
  [[ "$id" == "S1" ]] && d=$(python3 -c "print($d - 0.1)")      # S1 sai 3 quadros curta, como o Manim faz
  ffmpeg -v error -y -f lavfi -i "color=c=0x0f172a:size=640x360:rate=30:duration=$d" -c:v libx264 -pix_fmt yuv420p mp4/$id.mp4
done
python3 "$VA/montar_cenas.py" cenas.json mp4 --tts tts --saida out/va.mp4 --legenda leg/va.srt --roteiro rot/va.md > montar.log
test -s out/va.mp4 && test -s leg/va.srt && test -s rot/va.md
grep -q "O operator monta tudo na ordem certa." leg/va.srt && ! grep -q "operêitor" leg/va.srt
A=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 out/va.mp4); [[ "$A" == "48000" ]]
python3 - <<'PY'
import json, subprocess
t = json.load(open("tts/tempos.json"))
alvo = sum(round(v["total"] * 30) / 30 for v in t.values())
pr = lambda st: float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", st, "-show_entries", "stream=duration", "-of", "csv=p=0", "out/va.mp4"], capture_output=True, text=True).stdout)
v, a = pr("v:0"), pr("a:0")
assert abs(v - alvo) < 0.04 and abs(a - alvo) < 0.1, (v, a, alvo)   # a cena curta foi completada; vídeo e áudio fecham com a narração
# o bloco X1 (último) leva o áudio próprio, não silêncio
import re
ini = alvo - round(t["X1"]["total"] * 30) / 30 + 0.1
err = subprocess.run(["ffmpeg", "-v", "info", "-ss", f"{ini:.3f}", "-t", "1.0", "-i", "out/va.mp4", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
mv = float(re.search(r"mean_volume: (-?[\d.]+) dB", err).group(1)); assert mv > -30, (mv, ini)
PY
grep -q "AVISO S1" montar.log && grep -q "LUFS" montar.log
pass "video-animado: tts_cenas (stub), montar_cenas (duração = narração mesmo com cena curta, bloco com áudio próprio, legenda com grafia original, 48 kHz, normalização) e roteiro"
python3 "$VA/montar_cenas.py" cenas.json mp4 --tts tts --cenas S2 --saida out/p.mp4 --legenda leg/p.srt >/dev/null && test -s out/p.mp4
python3 "$VA/folha_cenas.py" cenas.json mp4 --fracao 0.9 --saida folha.png >/dev/null && test -s folha.png
pass "video-animado: piloto por --cenas e folha_cenas"
cd ..

# videoaula: remap de tempos, EDL e legenda com dados sintéticos (sem IA, sem render)
VA2="$ROOT/skills/videoaula/scripts"
mkdir -p va2 && cd va2
# corte sintético: 30 fps; mantidos [0,10s) e [12,20s); removido [10,12s)
echo '{"version":"1","chunks":[[0,300,1],[300,360,99999],[360,600,1]]}' > corte.v1.json
echo '[{"start":0,"end":5,"kind":"locutor"},{"start":5,"end":15,"kind":"quadro"},{"start":15,"end":20,"kind":"codigo"}]' > cenas.json
python3 - <<'PY'
import json
segs=[]
def seg(t0,text):
    ws=[]; cur=t0
    for w in text.split():
        ws.append({"start":round(cur,2),"end":round(cur+0.4,2),"word":" "+w}); cur+=0.5
    segs.append({"start":t0,"end":round(cur,2),"text":text,"words":ws})
seg(1.0,"Olá turma hoje vamos ver variáveis.")
seg(9.0,"Este trecho vai ser cortado no meio.")
seg(16.0,"E agora o código no editor.")
json.dump({"source":"x","language":"pt","duration":20,"segments":segs},open("in.transcript.json","w"),ensure_ascii=False)
PY
python3 "$VA2/remap_tempos.py" corte.v1.json cenas.json in.transcript.json --out . >/dev/null
python3 - <<'PY'
import json
c=json.load(open("cenas_corte.json")); t=json.load(open("transcript_corte.json"))
assert abs(t["duration"]-18.0)<1e-6, t["duration"]
assert [x["kind"] for x in c]==["locutor","quadro","codigo"], c
assert abs(c[2]["cut_start"]-13.0)<1e-6 and abs(c[2]["cut_end"]-18.0)<1e-6, c[2]   # 15s original -> 13s no corte
w=[w for s in t["segments"] for w in s["words"] if w["word"].strip()=="editor."][0]
assert abs(w["start"]-(16.0+2.5-2.0))<0.05, w                                          # palavra depois do corte desloca 2 s
PY
pass "videoaula: remap_tempos.py (cenas e palavras no tempo do corte)"
mkdir -p identidade && echo '{}' > identidade/l3_geo.json
cat > aula.json <<'JSON'
{"corte":"corte.mp4","corte_v1":"corte.v1.json","transcript":"in.transcript.json","cenas_corte":"cenas_corte.json","identidade":"identidade","manim":"manim","mattes":"mattes","blocos":"blocos",
 "cartela_dur":2.0,"capitulos":[{"n":1,"titulo":"Variáveis","inicio":5.0}],"diagramas":[{"cena":"D1","inicio":5.0,"fim":13.0}],
 "circulo":{"cx":1596,"cy":827,"r":186},"codigo_grupos":[{"grupo":"A","orig_ini":15,"orig_fim":20,"crop":[0,0,830,900]}]}
JSON
python3 "$VA2/montar_aula.py" aula.json edl > edl.txt
grep -q "sep " edl.txt && grep -q "D1" edl.txt && grep -q "duração final: 20.0s" edl.txt
# cartela num ponto com lacuna entre cenas (13.0 -> 13.033): tem de entrar mesmo assim, uma vez só
python3 - <<'PY'
import json
c=json.load(open("cenas_corte.json")); c[2]["cut_start"]=13.033; json.dump(c,open("cenas_corte2.json","w"))
a=json.load(open("aula.json")); a["cenas_corte"]="cenas_corte2.json"; a["capitulos"].append({"n":2,"titulo":"Código","inicio":13.0}); json.dump(a,open("aula2.json","w"))
PY
python3 "$VA2/montar_aula.py" aula2.json edl > edl2.txt && [[ "$(grep -c " sep " edl2.txt)" == "2" ]]
[[ "$(python3 "$VA2/montar_aula.py" aula.json map 7.0)" == "9.000" ]]
pass "videoaula: montar_aula.py edl (cartela inserida) e map (corte -> final)"
echo '{"fixes":{"9.0":null},"corr":[["turma","pessoal"]]}' > ajustes.json
python3 "$VA2/legenda_aula.py" aula.json corte.v1.json in.transcript.json out.srt --ajustes ajustes.json >/dev/null
grep -q "Olá pessoal" out.srt && ! grep -q "cortado no meio" out.srt && grep -q "00:00:16,000 --> " out.srt
pass "videoaula: legenda_aula.py (ajustes, remoção da frase cortada, deslocamento da cartela)"
python3 - <<'PY'
import json; c=json.load(open("aula.json")); c.update({"slug":"t","titulo":"Fundamentos do Python","kicker":"AULA 01"}); json.dump(c,open("aula.json","w"))
PY
python3 "$VA2/publicar_aula.py" aula.json --saida pub/t --sem-thumb >/dev/null
grep -q "^00:00 Abertura" pub/t.youtube.md && grep -q "^00:07 Variáveis" pub/t.youtube.md
pass "videoaula: publicar_aula.py (capítulos do YouTube nos tempos finais)"
cd ..

bash -n "$S"/*.sh "$ROOT"/skills/videoaula/scripts/*.sh && python3 -c 'import ast, sys; [ast.parse(open(f, encoding="utf-8").read(), f) for f in sys.argv[1:]]' "$S"/*.py "$ROOT"/skills/video-docs/scripts/*.py "$ROOT"/skills/video-animado/scripts/*.py "$ROOT"/skills/video-animado/templates/*.py "$ROOT"/skills/videoaula/scripts/*.py "$ROOT"/skills/videoaula/templates/*.py
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
