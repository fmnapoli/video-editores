#!/usr/bin/env bash
# Testa as operações de "ver, ler e conferir" (ADR-19): conferir-fala, banco-video, rastrear, rostos e ler-tela.
# Uso: tests/visao.sh   (ffmpeg, python3 e uv; OpenCV e numpy chegam pelo uv run --with)
#      VE_TESTE_MODELOS=1 tests/visao.sh   também roda o OCR real (RapidOCR, ~100 MB de pacotes na 1ª vez)
# Os modelos de IA (rosto, OCR) entram por backends falsos de tests/stub/modelos_falsos.py: o que se testa aqui é
# a lógica dos scripts (zona livre, conferência por diferença de pixels, busca de texto, formas ASS no lugar).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/scripts"
T="$(mktemp -d)"
STUB_PID=""
trap '[[ -n "$STUB_PID" ]] && kill "$STUB_PID" 2>/dev/null || true; rm -rf "$T"' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
export PYTHONPATH="$ROOT/tests/stub:$ROOT"
export VE_MODELOS_EXTRA="rosto:fixo=modelos_falsos:RostoFixo;ocr:fixo=modelos_falsos:OcrFixo"
CV=(uv run --quiet --with opencv-python-headless --with numpy python)

# ---------------------------------------------------------------- conferir-fala (só biblioteca padrão)
cat > roteiro.md <<'MD'
# Abertura
O plugin corta o vídeo sozinho. [pausa]
Na versão 5.2 ele confere a própria fala, palavra por palavra.
MD
python3 - <<'PY'
import json
def seg(t0, palavras): return {"start": t0, "end": t0 + len(palavras) * 0.4, "text": " ".join(palavras),
                               "words": [{"start": round(t0 + i * 0.4, 2), "end": round(t0 + i * 0.4 + 0.3, 2), "word": " " + w} for i, w in enumerate(palavras)]}
certo = [seg(0.0, "O plugin corta o vídeo sozinho.".split()),
         seg(3.0, "Na versão cinco ponto dois, ele confere a própria fala, palavra por palavra.".split())]
json.dump({"language": "pt", "duration": 9, "segments": certo}, open("certo.transcript.json", "w"))
errado = [seg(0.0, "O plugin corta o vídeo sozinho.".split()), seg(3.0, "O plugin corta o vídeo sozinho.".split()),
          seg(6.0, "Na versão cinco ponto dois, ele confere a fala, palavras por palavra.".split())]
json.dump({"language": "pt", "duration": 12, "segments": errado}, open("errado.transcript.json", "w"))
json.dump({"5.2": "cinco ponto dois"}, open("eq.json", "w"))
PY
python3 "$S/conferir_fala.py" roteiro.md certo.transcript.json --equivalentes eq.json >/dev/null
grep -q "^# Fala × roteiro: OK" certo.fala.md
if python3 "$S/conferir_fala.py" roteiro.md certo.transcript.json >/dev/null; then echo "sem equivalentes devia acusar o número"; exit 1; fi
if python3 "$S/conferir_fala.py" roteiro.md errado.transcript.json --equivalentes eq.json > fala.txt; then echo "devia sair com 1"; exit 1; fi
python3 - <<'PY'
import json
d = json.load(open("errado.fala.json"))
t = {x["tipo"]: x for x in d["diferencas"]}
assert not d["ok"] and set(t) == {"sobrou", "faltou", "parecida"}, d
assert t["sobrou"]["fala"] == "o plugin corta o video sozinho" and t["sobrou"]["t"] in (0.0, 3.0), t["sobrou"]   # tomada repetida: uma das duas cópias, com o instante dela
assert t["faltou"]["roteiro"] == "propria" and t["parecida"]["roteiro"] == "palavra" and t["parecida"]["peso"] == 0
assert d["palavras_roteiro"] == 18, d   # "[pausa]" e o título ficam de fora; 5.2 vira dois tokens
PY
echo '{"cenas":[{"id":"A","narracao":"O plugin corta o vídeo sozinho."},{"id":"B","narracao":"Na versão 5.2 ele confere a própria fala, palavra por palavra."},{"id":"V","duracao":2}]}' > cenas.json
python3 "$S/conferir_fala.py" cenas.json certo.transcript.json --equivalentes eq.json --out c2.fala.md >/dev/null && test -s c2.fala.json
echo '[{"id":"A","narracao":"O plugin corta o vídeo sozinho."},{"id":"B","narracao":"Na versão 5.2 ele confere a própria fala, palavra por palavra."},{"id":"V","narracao":null}]' > lista.json
python3 "$S/conferir_fala.py" lista.json certo.transcript.json --equivalentes eq.json --out c3.json >/dev/null
python3 -c 'import json; assert json.load(open("c3.json"))["ok"]' && grep -q "^# Fala" c3.md   # --out .json não vira o mesmo arquivo do .md
pass "conferir_fala.py: roteiro igual passa; tomada repetida, palavra que faltou e palavra parecida são separadas; cenas.json em objeto e em lista"

# ---------------------------------------------------------------- banco-video (opcional) contra um banco falso
mkdir stub && ffmpeg -v error -y -f lavfi -i "testsrc2=size=320x180:rate=30:duration=1" -c:v libx264 -pix_fmt yuv420p stub/clipe.mp4 \
  && ffmpeg -v error -y -i stub/clipe.mp4 -frames:v 1 -update 1 stub/mini.jpg
(cd stub && exec python3 "$ROOT/tests/stub/banco_servidor.py" porta) >stub/log 2>&1 &
STUB_PID=$!
for _ in $(seq 300); do [[ -s stub/porta ]] && break; kill -0 "$STUB_PID" 2>/dev/null || break; sleep 0.1; done
[[ -s stub/porta ]] || { echo "banco falso não subiu:"; cat stub/log; exit 1; }
PORTA="$(cat stub/porta)"
export VE_BANCO_URL="http://127.0.0.1:$PORTA"
if env -u PEXELS_API_KEY python3 "$S/banco_video.py" buscar "mar" 2>err.txt; then echo "sem chave devia encerrar"; exit 1; fi
grep -q "opcional e está desligado" err.txt && grep -q "PEXELS_API_KEY" err.txt
if PEXELS_API_KEY=errada python3 "$S/banco_video.py" buscar "mar" 2>err.txt; then echo "chave errada devia falhar"; exit 1; fi
grep -q "recusou a chave" err.txt
export PEXELS_API_KEY=chave-teste
python3 "$S/banco_video.py" buscar "ondas do mar" --id ondas --orientacao retrato >/dev/null
python3 "$S/banco_video.py" baixar ondas --escolha 2 --altura 720 >/dev/null
if python3 "$S/banco_video.py" baixar ondas --escolha 2 2>err.txt; then echo "não pode sobrescrever"; exit 1; fi
if python3 "$S/banco_video.py" buscar "nada" 2>err.txt; then echo "busca vazia devia falhar"; exit 1; fi
python3 "$S/banco_video.py" creditos > creditos.txt
python3 - <<'PY'
import hashlib, json
b = json.load(open("banco/ondas.busca.json"))
assert [c["duracao"] for c in b["candidatos"]] == [10, 20], b        # o de 2 s cai pelo --min-dur 4
assert all(len(c["arquivos"]) == 2 for c in b["candidatos"])          # o HLS (não mp4) fica de fora
r = json.load(open("banco/ondas.json"))
assert r["autor"] == "Autora 3" and r["altura"] == 1080 and r["banco"] == "pexels" and "pexels.com/license" in r["licenca"], r
assert r["sha256"] == hashlib.sha256(open("banco/ondas.mp4", "rb").read()).hexdigest()
q = json.load(open("stub/recebidos.json"))[0]
assert q["query"] == "ondas do mar" and q["orientation"] == "portrait", q
c = open("creditos.txt").read()
assert "Autora 3: https://banco.exemplo/video/103/" in c and "Pexels" in c, c
PY
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 banco/ondas.folha.jpg)
[[ "$W" == 960 ]] || { echo "folha de escolha com largura $W (esperado 960: 2 miniaturas de 480)"; exit 1; }
unset PEXELS_API_KEY
pass "banco_video.py: desligado sem chave; busca filtrada, folha, download com registro e crédito, sem sobrescrever (banco falso)"

# ---------------------------------------------------------------- nucleo/quadros: instante de cada amostra
ffmpeg -v error -y -f lavfi -i "color=c=black:s=64x64:r=30:d=4,geq=lum='16+N*1.5':cb=128:cr=128" -c:v libx264 -qp 0 -pix_fmt yuv420p indice.mp4
uv run --quiet --with numpy python - <<'PY'
from video_editores.nucleo import quadros
todos = [(t, int(q[0, 0])) for _, t, q in quadros.ler("indice.mp4", cinza=True)]
brilho = [b for _, b in todos]
assert len(todos) == 120 and all(a < b for a, b in zip(brilho, brilho[1:])), "cada quadro tem um brilho só dele"
assert all(abs(t * 30 - k) < 0.01 for k, (t, _) in enumerate(todos))
def n(q): return brilho.index(int(q[0, 0]))                 # brilho -> número do quadro
casos = [({"passo": 0.5}, 8), ({"passo": 0.4}, 10), ({"passo": 0.5, "inicio": 0.3335}, 8),
         ({"passo": 0.125, "inicio": 1.01}, 24), ({"passo": 2}, 2), ({"inicio": 1.01, "fim": 1.2}, 6)]
for kw, total in casos:
    r = [(t, n(q)) for _, t, q in quadros.ler("indice.mp4", cinza=True, **kw)]
    assert len(r) == total, (kw, len(r))
    assert all(abs(t * 30 - k) < 0.01 for t, k in r), (kw, [(round(t * 30, 2), k) for t, k in r][:6])
assert n(quadros.em("indice.mp4", 1.01, cinza=True)) == 31       # primeiro quadro com tempo >= 1,01 s
assert quadros.em("indice.mp4", 9.0) is None
PY
pass "nucleo/quadros: o instante devolvido é o do quadro entregue (todos os quadros, amostrado, início fora do grid)"

# ---------------------------------------------------------------- rastrear (OpenCV real, trajetória conhecida)
# fundo com ruído parado + cartão de teste que anda 150 px/s para a direita e 40 px/s para cima
ffmpeg -v error -y -f lavfi -i "color=c=gray:s=1280x720:r=30:d=3,noise=all_seed=7:alls=40" -f lavfi -i "testsrc=s=200x140:r=30:d=3" \
  -filter_complex "[0][1]overlay=x='200+150*t':y='300-40*t'" -c:v libx264 -crf 18 -pix_fmt yuv420p move.mp4
"${CV[@]}" "$S/rastrear.py" move.mp4 --caixa 0.15625,0.4167,0.15625,0.1944 --id cartao --out r \
  --etiqueta "CARTÃO" --seta --burn move_rastro.mp4 >/dev/null
python3 - <<'PY'
import json, re
d = json.load(open("r/cartao.rastro.json")); q = d["quadros"]
assert len(q) == 90 and d["perdido_em"] is None, (len(q), d["perdido_em"])
erro = max(max(abs(f["cx"] * 1280 - (300 + 150 * f["t"])), abs(f["cy"] * 720 - (370 - 40 * f["t"]))) for f in q)
assert erro < 6, f"rastro errou {erro:.1f} px (limite 6)"
assert all(0.97 < f["escala"] < 1.03 and abs(f["rot"]) < 1 for f in q), "objeto rígido não muda de escala nem gira"
a = open("r/cartao.rastro.ass", encoding="utf-8").read()
ev = [ln for ln in a.splitlines() if ln.startswith("Dialogue: 1,")]
assert len(ev) == 90 and all("CARTÃO" in e for e in ev)
xs = [float(re.search(r"\\pos\(([\d.]+),", e).group(1)) for e in ev]
assert xs == sorted(xs) and 400 < xs[-1] - xs[0] < 460, (xs[0], xs[-1])      # a etiqueta anda com o cartão (~445 px)
ini = [re.search(r"Dialogue: 1,([\d:.]+),([\d:.]+)", e).groups() for e in ev]
assert all(ini[i][1] == ini[i + 1][0] for i in range(len(ini) - 1)), "eventos contíguos, sem buraco nem sobreposição"
assert a.count("Dialogue: 0,") == 90 and "\\p1" in a                          # a seta
PY
N=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 move_rastro.mp4)
[[ "$N" == 90 ]] || { echo "queima mudou o número de quadros: $N"; exit 1; }
pass "rastrear.py: segue o objeto com erro < 6 px em 90 quadros; etiqueta e seta em ASS, um evento por quadro"

# região lisa não tem o que seguir; corte de cena encerra o rastro com código 2
ffmpeg -v error -y -f lavfi -i "color=c=blue:s=640x360:r=30:d=1" -c:v libx264 -pix_fmt yuv420p liso.mp4
if "${CV[@]}" "$S/rastrear.py" liso.mp4 --caixa 0.4,0.4,0.2,0.2 --out r 2>err.txt; then echo "região lisa devia falhar"; exit 1; fi
grep -q "sem textura" err.txt
ffmpeg -v error -y -i move.mp4 -f lavfi -i "testsrc2=s=1280x720:r=30:d=1" -filter_complex "[0:v]trim=0:1,setpts=PTS-STARTPTS[a];[a][1:v]concat=n=2:v=1[v]" \
  -map "[v]" -c:v libx264 -crf 18 -pix_fmt yuv420p corte.mp4
set +e; "${CV[@]}" "$S/rastrear.py" corte.mp4 --caixa 0.15625,0.4167,0.15625,0.1944 --id corte --out r >/dev/null 2>err.txt; RC=$?; set -e
[[ $RC == 2 ]] && grep -q "PERDIDO em 1\.0.*corte de cena" err.txt || { echo "corte de cena: rc=$RC"; cat err.txt; exit 1; }
python3 -c 'import json; d=json.load(open("r/corte.rastro.json")); assert 28 <= len(d["quadros"]) <= 30 and d["motivo"] == "corte de cena", d["motivo"]'
if "${CV[@]}" "$S/rastrear.py" move.mp4 --caixa 0.15625,0.4167,0.15625,0.1944 --inicio 99 --out r 2>err.txt; then echo "início depois do fim devia falhar"; exit 1; fi
grep -q "nenhum quadro" err.txt
mkdir "d'apostrofo, [x]" && cp move.mp4 "d'apostrofo, [x]/m v.mp4"
"${CV[@]}" "$S/rastrear.py" "d'apostrofo, [x]/m v.mp4" --caixa 0.15625,0.4167,0.15625,0.1944 --inicio 1.01 --fim 1.5 --id ch --ancora direita \
  --etiqueta "{50%} ok" --burn "d'apostrofo, [x]/s a.mp4" >/dev/null
python3 - <<'PY'
import json, re
q = json.load(open("d'apostrofo, [x]/ch.rastro.json"))["quadros"]
assert abs(q[0]["t"] * 30 - 31) < 0.01, q[0]["t"]                 # 1º quadro com tempo >= 1,01 s é o 31, não 30,3
ev = [ln for ln in open("d'apostrofo, [x]/ch.rastro.ass", encoding="utf-8").read().splitlines() if ln.startswith("Dialogue: 1,")]
assert ev[0].endswith("}\\{50%\\} ok"), ev[0][-30:]                # chaves do texto não viram bloco de tags
assert re.search(r"Dialogue: 1,0:00:01.02,0:00:01.05", ev[0]), ev[0][:40]   # fronteira meio quadro antes de 1,0333 s
PY
test -s "d'apostrofo, [x]/s a.mp4"
pass "rastrear.py: região sem textura e início fora do vídeo recusados; corte de cena com código 2; início fora do grid, chaves no texto e apóstrofo no caminho"

# ---------------------------------------------------------------- rostos (detector falso; lógica real)
ffmpeg -v error -y -f lavfi -i "testsrc2=size=540x960:rate=30:duration=4" -f lavfi -i "sine=f=300:d=4" -shortest -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac pessoa.mp4
VE_ROSTO=fixo VE_TESTE_ROSTO="0.35,0.20,0.30,0.22" "${CV[@]}" "$S/rostos.py" pessoa.mp4 --passo 0.5 --out pessoa.rostos.json >/dev/null
python3 - <<'PY'
import json
d = json.load(open("pessoa.rostos.json"))
assert d["amostras"] == 8 and d["amostras_com_rosto"] == 8 and d["backend"] == "fixo", d["amostras"]
assert d["zona"] == {"x0": 0.35, "y0": 0.2, "x1": 0.65, "y1": 0.42}, d["zona"]
assert d["sugestao"]["lado"] == "base" and d["sugestao"]["pos"] == [0.5, 0.635], d["sugestao"]   # meio entre o rosto (0,42) e a zona da interface (0,85)
PY
cat > em_cima.json <<'JSON'
[{"text":"EM CIMA","start":0.9,"end":2.4,"style":"titulo","pos":[0.5,0.31],"size":0.09,"anim":"none"}]
JSON
cat > livre.json <<'JSON'
[{"text":"LIVRE","start":1.0,"end":2.4,"style":"titulo","pos":[0.5,0.635]}]
JSON
python3 "$S/lettering_ass.py" pessoa.mp4 em_cima.json --marca nao --burn pessoa_cima.mp4 >/dev/null
python3 "$S/lettering_ass.py" pessoa.mp4 livre.json --marca nao --burn pessoa_livre.mp4 >/dev/null
set +e; "${CV[@]}" "$S/rostos.py" pessoa.mp4 --conferir pessoa_cima.mp4 --rostos pessoa.rostos.json > cima.txt; RC=$?; set -e
[[ $RC == 3 ]] && grep -q "ROSTO COBERTO em 1 intervalo" cima.txt || { echo "texto sobre o rosto: rc=$RC"; cat cima.txt; exit 1; }
python3 -c 'import json; d=json.load(open("pessoa_cima.rosto-coberto.json")); assert d["intervalos"] == [[1.0, 2.5]], d["intervalos"]'
"${CV[@]}" "$S/rostos.py" pessoa.mp4 --conferir pessoa_livre.mp4 --rostos pessoa.rostos.json | grep -q "ok: nada cobre o rosto"
ffmpeg -v error -y -i pessoa.mp4 -t 2 -c copy curto.mp4
if "${CV[@]}" "$S/rostos.py" pessoa.mp4 --conferir curto.mp4 --rostos pessoa.rostos.json 2>err.txt; then echo "durações diferentes deviam falhar"; exit 1; fi
grep -q "MESMA etapa" err.txt
VE_ROSTO=fixo VE_TESTE_ROSTO="" "${CV[@]}" "$S/rostos.py" pessoa.mp4 --out vazio.rostos.json | grep -q "rosto em 0/8"
# passo que não cai em centésimo e início fora do grid de quadros: toda amostra coberta é achada, sem erro de arredondamento
VE_ROSTO=fixo VE_TESTE_ROSTO="0.35,0.20,0.30,0.22" "${CV[@]}" "$S/rostos.py" pessoa.mp4 --passo 0.125 --inicio 0.3335 --out fino.rostos.json >/dev/null
set +e; "${CV[@]}" "$S/rostos.py" pessoa.mp4 --conferir pessoa_cima.mp4 --rostos fino.rostos.json --out fino.coberto.json > fino.txt; RC=$?; set -e
[[ $RC == 3 ]] || { echo "passo 0,125: rc=$RC"; cat fino.txt; exit 1; }
python3 - <<'PY'
import json
d = json.load(open("fino.coberto.json")); (a, b), = d["intervalos"]
assert 0.85 <= a <= 1.0 and 2.4 <= b <= 2.55, d["intervalos"]        # o texto fica de 0,9 a 2,4 s
assert len(d["amostras"]) == 12, len(d["amostras"])                    # as 12 amostras de 0,125 s entre 0,9 e 2,4 s
PY
pass "rostos.py: zona e sugestão de posição; texto sobre o rosto acusa o intervalo (código 3), texto na zona livre e recodificação passam"

# ---------------------------------------------------------------- ler-tela (OCR falso; busca e formas reais)
ffmpeg -v error -y -f lavfi -i "color=c=white:s=1280x720:r=30:d=4" -c:v libx264 -pix_fmt yuv420p tela.mp4
cat > ocr.json <<'JSON'
[{"texto":"Configuração de transcrição","caixa":[0.06,0.14,0.34,0.05],
  "palavras":[["Configuração",0.06,0.14,0.15,0.05],["de",0.22,0.14,0.03,0.05],["transcrição",0.26,0.14,0.14,0.05]]},
 {"texto":"Contato: ana@exemplo.com e bia@exemplo.com","caixa":[0.06,0.30,0.50,0.05],
  "palavras":[["Contato:",0.06,0.30,0.10,0.05],["ana@exemplo.com",0.17,0.30,0.17,0.05],["e",0.35,0.30,0.01,0.05],["bia@exemplo.com",0.37,0.30,0.17,0.05]]},
 {"texto":"Salvar alterações","caixa":[0.55,0.55,0.20,0.05],"palavras":[]}]
JSON
LER=(env VE_OCR=fixo VE_TESTE_OCR="$T/ocr.json" "${CV[@]}" "$S/ler_tela.py")
"${LER[@]}" tela.mp4 --t 1 --achar "configuracao DE" --achar "ALTERAÇÕES" --estilo marca --marca nao --burn tela_marca.mp4 >/dev/null
python3 - <<'PY'
import json, re
d = json.load(open("tela_1s.ocr.json"))
assert d["largura"] == 1280 and len(d["linhas"]) == 3 and d["backend"] == "fixo"
a, b = d["achados"]
assert a["texto"] == "Configuração de" and a["caixa"] == [0.06, 0.14, 0.19, 0.05], a      # sem acento nem caixa; união das 2 palavras
assert b["texto"] == "alterações" and abs(b["caixa"][0] - 0.632) < 0.005 and abs(b["caixa"][2] - 0.118) < 0.005, b   # linha sem palavras: fatia proporcional
s = open("tela_1s.destaque.ass", encoding="utf-8").read()
ev = [ln for ln in s.splitlines() if ln.startswith("Dialogue:")]
assert len(ev) == 2 and all(e.startswith("Dialogue: 2,0:00:01.00,0:00:04.00") for e in ev), ev     # de --t até --t + 3 s
m = re.search(r"\\p1\}m (\d+) (\d+) l (\d+) \d+ l \d+ (\d+)", ev[0]); x0, y0, x1, y1 = map(int, m.groups())
assert 60 <= x0 <= 77 and 315 <= x1 <= 335 and 85 <= y0 <= 101 and 137 <= y1 <= 150, (x0, y0, x1, y1)   # caixa + folga, em pixels
assert "\\t(0,280,\\clip(" in ev[0] and "\\1a&H8C&" in ev[0]                                      # marca-texto translúcido que varre
PY
# o destaque muda os pixels dentro da caixa e não mexe fora dela
ffmpeg -v error -y -ss 2 -i tela_marca.mp4 -frames:v 1 -vf "crop=200:20:90:105,scale=1:1" -f rawvideo -pix_fmt rgb24 dentro.rgb
ffmpeg -v error -y -ss 2 -i tela_marca.mp4 -frames:v 1 -vf "crop=200:20:90:400,scale=1:1" -f rawvideo -pix_fmt rgb24 fora.rgb
python3 -c '
d = open("dentro.rgb","rb").read(); f = open("fora.rgb","rb").read()
assert min(f) > 235, tuple(f)
assert d[0] > 200 and d[1] > 190 and d[2] < 215 and d[0] - d[2] > 40, tuple(d)   # amarelado
'
"${LER[@]}" tela.mp4 --regex '[\w.+-]+@[\w-]+\.[\w.]+' --estilo tarja --burn tela_tarja.mp4 --out priv.ocr.json >/dev/null
python3 - <<'PY'
import json
d = json.load(open("priv.ocr.json"))
assert [a["texto"] for a in d["achados"]] == ["ana@exemplo.com", "bia@exemplo.com"], d["achados"]
ev = [ln for ln in open("priv.destaque.ass", encoding="utf-8").read().splitlines() if ln.startswith("Dialogue:")]
assert len(ev) == 2 and all(",0:00:00.00,0:00:05.00," in e and "\\1c&H00000000&" in e and "\\t(" not in e for e in ev), ev   # vídeo inteiro, opaca, sem animação
PY
ffmpeg -v error -y -ss 3.5 -i tela_tarja.mp4 -frames:v 1 -vf "crop=180:20:240:224,scale=1:1" -f rawvideo -pix_fmt rgb24 tarja.rgb
python3 -c 'd = open("tarja.rgb","rb").read(); assert max(d) < 30, tuple(d)'
set +e; "${LER[@]}" tela.mp4 --achar "não existe" --out nada.ocr.json 2>err.txt >/dev/null; RC=$?; set -e
[[ $RC == 1 ]] && grep -q "NÃO ENCONTRADO" err.txt && grep -q "Salvar alterações" err.txt || { echo "busca sem resultado: rc=$RC"; exit 1; }
ffmpeg -v error -y -i tela.mp4 -frames:v 1 -update 1 print.png
"${LER[@]}" print.png --achar "salvar" --estilo caixa --marca nao --burn print_caixa.png >/dev/null && test -s print_caixa.png && test -s print.ocr.json
"${LER[@]}" print.png --achar "salvar" --estilo caixa --marca nao --out leitura.json >/dev/null
"${LER[@]}" print.png --achar "figura" --achar "@exemplo" --todos --out dentro.json >/dev/null       # trecho de dentro de uma palavra
python3 - <<'PY'
import json
a, b, c = json.load(open("dentro.json"))["achados"]
assert a["texto"] == "figura" and abs(a["caixa"][0] - 0.0975) < 0.001 and abs(a["caixa"][2] - 0.075) < 0.001, a   # letras 4–9 das 12 de "Configuração"
assert [x["texto"] for x in (b, c)] == ["@exemplo", "@exemplo"] and abs(b["caixa"][0] - 0.204) < 0.001 and abs(c["caixa"][0] - 0.404) < 0.001, (b, c)
PY
python3 -c 'import json; assert json.load(open("leitura.json"))["achados"]' && grep -q "^Dialogue:" leitura.destaque.ass   # o ASS não cai em cima do JSON
# --lote: cada texto procurado na sua janela de tempo; o que não aparece é listado e o .ass sai com o resto
cat > itens.json <<'JSON'
[{"achar": "salvar alterações", "entre": [0.5, 2.0], "estilo": "caixa", "dur": 2.0},
 {"regex": "bia@\\w+", "entre": [1.0, 1.5]},
 {"achar": "não existe", "entre": [0, 1]}]
JSON
set +e; "${LER[@]}" tela.mp4 --lote itens.json --marca nao --out lote.destaques.json > lote.txt; RC=$?; set -e
[[ $RC == 1 ]] && grep -q "NÃO ENCONTRADO" lote.txt || { echo "--lote: rc=$RC"; cat lote.txt; exit 1; }
python3 - <<'PY'
import json
d = json.load(open("lote.destaques.json"))
a, b = d["destaques"]
assert (a["inicio"], a["fim"], a["estilo"], a["curto"]) == (0.5, 2.5, "caixa", False), a     # começa na janela e dura `dur`
assert b["texto"] == "bia@exemplo" and (b["inicio"], b["fim"]) == (1.0, 3.5) and b["estilo"] == "marca", b   # padrões: marca, 2,5 s
assert [x["item"] for x in d["nao_encontrados"]] == [3]
ev = [ln for ln in open("lote.destaques.ass", encoding="utf-8").read().splitlines() if ln.startswith("Dialogue:")]
assert len(ev) == 2 and ev[0].startswith("Dialogue: 2,0:00:00.50,0:00:02.50") and ev[1].startswith("Dialogue: 2,0:00:01.00,0:00:03.50"), ev
PY
pass "ler_tela.py: acha sem acento nem caixa, regex de e-mail, marca-texto no lugar, tarja opaca no vídeo inteiro, print, trecho de dentro de uma palavra, lote por janela de tempo"

# ---------------------------------------------------------------- catálogo e registro
python3 - <<'PY'
from video_editores import modelos
from video_editores.nucleo import catalogo
l = modelos.listar()["tipos"]
assert l["rosto"]["escolhido"] == "yunet" and l["ocr"]["escolhido"] == "rapidocr", l
assert modelos.deps("rosto", "yunet", dev="cpu") == ["opencv-python-headless", "numpy"]
assert modelos.deps("ocr", "rapidocr", dev="cpu") == ["rapidocr", "onnxruntime"]
assert modelos.deps("ocr", "rapidocr", dev="cuda") == ["rapidocr", "onnxruntime-gpu"]
for op in ("rostos", "rastrear", "ler-tela", "conferir-fala", "banco-video"):
    assert catalogo.operacao(op).caminho.is_file(), op
assert catalogo.comando("conferir-fala", ["a", "b"])[0].endswith(("python", "python3")) or "python" in catalogo.comando("conferir-fala", ["a", "b"])[0]
c = catalogo.comando("ler-tela", ["x.png"], device="cpu")
assert c[:3] == ["uv", "run", "--quiet"] and "rapidocr" in c and "-I" in c, c
PY
pass "papéis rosto e ocr no registro; cinco operações novas no catálogo"

if [[ "${VE_TESTE_MODELOS:-}" == 1 ]]; then
  cat > t.json <<'JSON'
[{"text":"Configuração avançada","start":0,"end":4,"style":"cartao","pos":[0.3,0.3],"size":0.05},
 {"text":"Salvar alterações","start":0,"end":4,"style":"cartao","pos":[0.7,0.7],"size":0.05}]
JSON
  python3 "$S/lettering_ass.py" tela.mp4 t.json --marca nao --burn tela_txt.mp4 >/dev/null
  env -u VE_MODELOS_EXTRA PYTHONPATH="$ROOT" python3 -m video_editores.cli ler-tela tela_txt.mp4 --t 1 --achar "salvar alteracoes" --out real.ocr.json >/dev/null
  python3 -c '
import json; d = json.load(open("real.ocr.json")); a = d["achados"][0]
assert d["backend"] == "rapidocr" and a["texto"] == "Salvar alterações", a
cx, cy = a["caixa"][0] + a["caixa"][2] / 2, a["caixa"][1] + a["caixa"][3] / 2
assert abs(cx - 0.7) < 0.02 and abs(cy - 0.7) < 0.03, (cx, cy)'
  pass "OCR real (RapidOCR): lê português com acento e devolve a caixa no lugar do texto"
fi
echo "visao ok"
