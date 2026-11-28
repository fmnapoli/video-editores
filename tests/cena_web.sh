#!/usr/bin/env bash
# Testa o cena_web.py: cena HTML renderizada quadro a quadro (Chrome sem janela + ffmpeg).
# Uso: tests/cena_web.sh   (ffmpeg, python3, uv e um Chrome/Chromium; sem navegador, o teste é pulado)
#      VE_TESTE_REDE=1 tests/cena_web.sh   também baixa Three.js e GSAP do npm e renderiza os dois modelos
set -euo pipefail
# shellcheck source=tests/_plataforma.sh
. "$(dirname "$0")/_plataforma.sh"
ROOT="$(caminho "$(cd "$(dirname "$0")/.." && pwd)")"
T="$(tmpdir)"; trap 'rm -rf "$T" || true' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
WEB=(uv run --quiet --with playwright python "$ROOT/scripts/cena_web.py")

# cena sem biblioteca: a cor do fundo é função de t, e um quadrado anda da esquerda para a direita
cat > cena.html <<'HTML'
<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}
#q{position:absolute;top:40%;width:20%;height:20%;background:rgb(255,0,0)}</style>
<div id="q"></div><img id="i" src="ponto.png" style="display:none">
<script>
window.veDuracao = 2;
window.veQuadro = (t) => { document.getElementById("q").style.left = (t / 2 * 80) + "%"; return {grande: document}; };
</script>
HTML
ffmpeg -v error -y -f lavfi -i "color=c=white:s=2x2" -frames:v 1 -update 1 ponto.png

set +e; "${WEB[@]}" cena.html --quadro 0 q0.png > saida.txt 2> err.txt; RC=$?; set -e
if [[ $RC != 0 ]] && grep -q "não achei um Chrome" err.txt; then
  echo "  - sem Chrome/Chromium nesta máquina: teste do cena_web pulado"; echo "cena_web ok (pulado)"; exit 0
fi
[[ $RC == 0 ]] || { echo "cena_web --quadro falhou:"; cat err.txt; exit 1; }

"${WEB[@]}" cena.html a.mp4 --tamanho 640x360 >/dev/null
"${WEB[@]}" cena.html b.mp4 --tamanho 640x360 >/dev/null
N=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 a.mp4)
[[ "$N" == 60 ]] || { echo "esperava 60 quadros (2 s a 30 fps), vieram $N"; exit 1; }
A=$(ffmpeg -v error -i a.mp4 -f framemd5 - | md5sum); B=$(ffmpeg -v error -i b.mp4 -f framemd5 - | md5sum)
[[ "$A" == "$B" ]] || { echo "dois renders da mesma cena deram quadros diferentes"; exit 1; }
# no quadro 15 (t = 0,5 s) o quadrado está em 20%–40% da largura: vermelho ali, nada em 70%
ffmpeg -v error -y -i a.mp4 -vf "select='eq(n,15)',crop=20:20:182:170,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 dentro.rgb
ffmpeg -v error -y -i a.mp4 -vf "select='eq(n,15)',crop=20:20:450:170,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 fora.rgb
python3 -c '
d = open("dentro.rgb","rb").read(); f = open("fora.rgb","rb").read()
assert d[0] > 200 and d[1] < 60 and d[2] < 60, tuple(d)
assert max(f) < 40 or min(f) > 215, tuple(f)'
pass "cena_web.py: 60 quadros em 2 s, mesmo resultado em dois renders, o instante t desenha o que deve (valor devolvido pela cena é ignorado)"

"${WEB[@]}" cena.html camada.mov --alpha --tamanho 640x360 --dur 0.5 >/dev/null
PIX=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt -of csv=p=0 camada.mov)
[[ "$PIX" == prores,yuva444p* ]] || { echo "camada com alpha saiu como $PIX"; exit 1; }
ffmpeg -v error -y -i camada.mov -vf "select='eq(n,0)',alphaextract,crop=20:20:450:170,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt gray fora.a
ffmpeg -v error -y -i camada.mov -vf "select='eq(n,0)',alphaextract,crop=20:20:50:170,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt gray dentro.a
python3 -c 'f = open("fora.a","rb").read()[0]; d = open("dentro.a","rb").read()[0]; assert f < 20 and d > 235, (f, d)'
pass "cena_web.py: --alpha grava ProRes 4444 com o fundo transparente e o objeto opaco"

if "${WEB[@]}" cena.html x.mp4 --alpha 2>err.txt; then echo "--alpha em .mp4 devia falhar"; exit 1; fi
grep -q "pede saída .mov" err.txt
echo '<!doctype html><script>window.veQuadro = (t) => { throw new Error("quebrou em " + t); }; window.veDuracao = 1;</script>' > ruim.html
if "${WEB[@]}" ruim.html r.mp4 --tamanho 320x180 2>err.txt; then echo "erro na cena devia falhar"; exit 1; fi
grep -q "quebrou em 0" err.txt
echo '<!doctype html><p>sem contrato</p><script src="https://cdn.exemplo.invalid/lib.js"></script>' > vazio.html
if VE_ESPERA_CENA=3 "${WEB[@]}" vazio.html v.mp4 2>err.txt; then echo "cena sem veQuadro devia falhar"; exit 1; fi
grep -q "não definiu window.veQuadro" err.txt && grep -q "cdn.exemplo.invalid" err.txt
pass "cena_web.py: --alpha exige .mov; erro da cena aponta o quadro; cena sem veQuadro e recurso de CDN bloqueado são explicados"

# sem --rede nada sai da máquina: imagem, fetch, WebSocket e janela aberta pela cena não chegam a um servidor local,
# e o render termina com o aviso de cada endereço (recurso bloqueado não derruba o vídeo)
command python3 - <<'PYOUVE' &
import os, socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("127.0.0.1", 0)); s.listen(8)
open("porta.tmp", "w").write(str(s.getsockname()[1])); os.replace("porta.tmp", "porta.txt"); s.settimeout(60)
try:
    while True:
        c, _ = s.accept(); open("chegou.txt", "ab").write(c.recv(200) + b"\n"); c.close()
except socket.timeout:
    pass
PYOUVE
OUVE=$!
for _ in $(seq 50); do [[ -s porta.txt ]] && break; sleep 0.1; done
P=$(cat porta.txt)
cat > vaza.html <<HTML
<!doctype html><img src="http://127.0.0.1:$P/img.png">
<script>
window.veDuracao = 0.2;
try { new WebSocket("ws://127.0.0.1:$P/ws"); } catch (e) {}
window.open("http://127.0.0.1:$P/popup");
fetch("http://127.0.0.1:$P/fetch").catch(() => 0);
window.veQuadro = (t) => {};
</script>
HTML
"${WEB[@]}" vaza.html vaza.mp4 --tamanho 320x180 >/dev/null 2>aviso.txt
kill $OUVE 2>/dev/null || true
if [[ ! -s vaza.mp4 || -e chegou.txt ]]; then echo "a cena falou com a rede sem --rede (ou não renderizou):"; cat chegou.txt aviso.txt 2>/dev/null; exit 1; fi
for r in img.png ws popup fetch; do grep -q "recurso não entregue: .*127.0.0.1:$P/$r" aviso.txt || { echo "faltou o aviso de $r"; cat aviso.txt; exit 1; }; done
if VE_ENCODER=codificador_que_nao_existe "${WEB[@]}" cena.html enc.mp4 --tamanho 320x180 2>err.txt; then echo "codificador inexistente devia falhar"; exit 1; fi
grep -q "ffmpeg falhou ao codificar" err.txt && test ! -e enc.mp4
if grep -q "Traceback" err.txt; then echo "ffmpeg que morre cedo virou traceback"; cat err.txt; exit 1; fi
if "${WEB[@]}" cena.html z.mp4 --fps 0 2>err.txt; then echo "--fps 0 devia falhar"; exit 1; fi
grep -q "maiores que zero" err.txt
pass "cena_web.py: sem --rede, imagem, fetch, WebSocket e window.open não saem da máquina e viram aviso; ffmpeg que falha e --fps 0 dão erro claro, sem vídeo pela metade"

# quadros-chave: folha + auditoria do texto do DOM. "sai" passa da borda direita; "rodape" está na faixa de baixo;
# "decorativo" sangra de propósito (data-ve-sangra); "longe" está inteiro fora do quadro e "oculto" tem opacidade 0
cat > texto.html <<'HTML'
<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#000;color:#fff;font:24px sans-serif}
div{position:absolute;white-space:nowrap}</style>
<div style="left:20px;top:20px">cabe inteiro</div>
<div id="sai" style="left:85%;top:80px">texto que sai pela direita do quadro</div>
<div style="left:20px;bottom:6px">rodape</div>
<div style="right:-60px;top:140px" data-ve-sangra>decorativo sangrando</div>
<div style="left:-900px;top:200px">longe</div>
<div style="left:95%;top:240px;opacity:0">oculto mas tambem passaria da borda</div>
<script>
window.veDuracao = 2;
window.veQuadro = (t) => { document.getElementById("sai").style.left = t < 1 ? "20px" : "85%"; };
</script>
HTML
set +e; "${WEB[@]}" texto.html --quadros 0.5,1.5 folha.png --tamanho 640x360 >saida.txt 2>err.txt; RC=$?; set -e
[[ $RC == 2 ]] || { echo "texto cortado devia sair com código 2, saiu $RC"; cat err.txt; exit 1; }
[[ $(grep -c "PROBLEMA" err.txt) == 1 ]] || { echo "esperava 1 problema (o texto que sai, só em t = 1,5 s):"; cat err.txt; exit 1; }
grep -q "t = 1.5s: texto cortado pela borda (direita): .*texto que sai pela direita" err.txt || { echo "faltou o problema do texto cortado:"; cat err.txt; exit 1; }
python3 -c '
import struct
b = open("folha.png", "rb").read(24); w, h = struct.unpack(">II", b[16:24])
assert b[:8] == b"\x89PNG\r\n\x1a\n" and w > 1280 and 360 < h < 480, (w, h)   # 2 quadros de 640 lado a lado + legenda'
set +e; "${WEB[@]}" texto.html --quadros 2 folha2.png --tamanho 640x360 --reserva-baixo 0.2 >/dev/null 2>err.txt; RC=$?; set -e
[[ $RC == 2 ]] && [[ $(grep -c "faixa reservada embaixo: .*rodape" err.txt) == 2 ]] || { echo "--reserva-baixo devia acusar o rodapé nos 2 instantes"; cat err.txt; exit 1; }
"${WEB[@]}" texto.html --quadros 1.5 folha3.png --tamanho 640x360 --auditoria aviso >/dev/null 2>err.txt
grep -q "AVISO: t = 1.5s: texto cortado" err.txt || { echo "--auditoria aviso não avisou:"; cat err.txt; exit 1; }
"${WEB[@]}" texto.html --quadros 1.5 folha4.png --tamanho 640x360 --auditoria nao >saida.txt 2>err.txt && grep -q "sem auditoria" saida.txt
if "${WEB[@]}" texto.html --quadros 1,2 folha.mp4 2>err.txt; then echo "--quadros em .mp4 devia falhar"; exit 1; fi
grep -q "precisa ser .png" err.txt
pass "cena_web.py --quadros: folha com os instantes, código 2 e lista quando o texto é cortado pela borda ou cai na faixa reservada; sangria marcada, texto fora do quadro e invisível não contam"

# mapa de palavras e marca: o quadrado só aparece quando "operator" é dito (t = 1,0 s) e tem a cor de acento da marca
cat > fala.html <<'HTML'
<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;width:100%;height:100%;background:var(--ve-fundo,#000)}
#q{position:absolute;left:40%;top:40%;width:20%;height:20%;background:var(--ve-acento,#f00)}</style>
<div id="q"></div>
<script>
const t0 = veQuando("OPERATOR"), tr = veTrecho("três minutos"), t2 = veQuando("o", 2);
if (Math.abs(tr.ini - 2.0) > 1e-9 || Math.abs(tr.fim - 2.9) > 1e-9 || t2 !== 1.6 || veDados.id !== "B1") throw new Error("mapa errado " + JSON.stringify([tr, t2, veDados]));
window.veDuracao = 3;
window.veQuadro = (t) => { document.getElementById("q").style.opacity = t >= t0 ? 1 : 0; };
</script>
HTML
echo '[{"t":0.6,"d":0.2,"w":"O"},{"t":1.0,"d":0.4,"w":"operator,"},{"t":1.6,"d":0.1,"w":"o"},{"t":2.0,"d":0.3,"w":"Três"},{"t":2.4,"d":0.5,"w":"minutos."}]' > palavras.json
echo '{"id": "B1"}' > dados.json
mkdir -p marca && echo '{"nome":"Acme","cores":{"fundo":"#102030","acento":"#00FF88","texto":"#FFFFFF"},"fonte":{"familia":"DejaVu Sans"}}' > marca/marca.json
for t in 0.5 1.5; do
  "${WEB[@]}" fala.html --quadro $t "f$t.png" --tamanho 320x180 --palavras palavras.json --dados dados.json >/dev/null
  ffmpeg -v error -y -i "f$t.png" -vf "crop=20:20:150:80,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 "f$t.rgb"
done
"${WEB[@]}" fala.html --quadro 1.5 sm.png --tamanho 320x180 --palavras palavras.json --dados dados.json --sem-marca >/dev/null
ffmpeg -v error -y -i sm.png -vf "crop=20:20:150:80,scale=1:1" -frames:v 1 -f rawvideo -pix_fmt rgb24 sm.rgb
python3 -c '
a, d, s = (tuple(open(f, "rb").read()) for f in ("f0.5.rgb", "f1.5.rgb", "sm.rgb"))
assert a == (0x10, 0x20, 0x30), a        # antes da palavra: só o fundo da marca
assert d == (0x00, 0xFF, 0x88), d        # depois: o quadrado, na cor de acento da marca
assert s == (255, 0, 0), s               # --sem-marca: vale a reserva do CSS'
echo '[{"t":0.6,"d":0.2,"w":"outra"},{"t":1.0,"d":0.2,"w":"fala"}]' > outras.json
SECONDS=0
if "${WEB[@]}" fala.html --quadro 1 x.png --palavras outras.json --dados dados.json 2>err.txt; then echo "palavra ausente devia falhar"; exit 1; fi
grep -q 'veQuando("OPERATOR"): .* \[outra fala\]' err.txt || { echo "faltou a mensagem da palavra ausente:"; cat err.txt; exit 1; }
(( SECONDS < 15 )) || { echo "erro ao carregar a cena esperou o prazo inteiro (${SECONDS}s)"; exit 1; }
if "${WEB[@]}" fala.html --quadro 1 x.png --dados dados.json 2>err.txt; then echo "cena narrada sem --palavras e sem padrão devia falhar"; exit 1; fi
grep -q "sem --palavras e sem valor padr" err.txt || { cat err.txt; exit 1; }
rm -rf marca
pass "cena_web.py --palavras/--dados: veQuando e veTrecho acham palavra, expressão e ocorrência sem ligar para caixa e acento; palavra ausente falha rápido e mostra a fala; marca vira variável CSS (e --sem-marca desliga)"

# /video-animado com cena em HTML: a duração vem da narração (stub), o termo do glossário chega com a grafia do roteiro
VA="$ROOT/skills/video-animado/scripts"
mkdir -p va/cenas && cp "$ROOT/skills/cena-web/templates/cena-narrada.html" va/cenas/EX.html
cat > va/cenas/GL.html <<'HTML'
<!doctype html><meta charset="utf-8"><body style="margin:0;background:#000">
<script>
const t0 = veQuando("operator");
if (!(t0 > veDados.fala.ini) || veDados.id !== "GL") throw new Error("dados errados");
window.veDuracao = veDados.total;
window.veQuadro = (t) => { document.body.style.background = t >= t0 ? "#fff" : "#000"; };
</script>
HTML
cat > va/cenas/va.json <<'JSON'
{"slug": "va", "voice": "pt-BR-ThalitaMultilingualNeural", "glossary": {"operator": "operêitor"},
 "cenas": [{"id": "EX", "html": "cenas/EX.html", "titulo": "Três ideias em uma cena",
            "narracao": "A primeira ideia aparece logo no começo. A segunda entra no meio. E a terceira fecha a cena."},
           {"id": "GL", "html": "cenas/GL.html", "narracao": "Quem monta tudo é o operator."},
           {"id": "M1", "classe": "M1", "narracao": "Esta cena é do Manim."}]}
JSON
(
  cd va
  PYTHONPATH="$ROOT/tests/stub" python3 "$VA/tts_cenas.py" cenas/va.json >/dev/null
  RW=(uv run --quiet --with playwright python "$VA/render_web.py" cenas/va.json mp4 --tamanho 640x360)
  "${RW[@]}" --folha 3 > folha.log 2> folha.err || { echo "render_web --folha falhou:"; cat folha.log folha.err; exit 1; }
  test -s mp4/EX.folha.png && test -s mp4/GL.folha.png && test ! -e mp4/M1.folha.png
  grep -q "EX: ok -> .*0 problema(s) de texto" folha.log
  "${RW[@]}" > render.log 2> render.err || { echo "render_web falhou:"; cat render.log render.err; exit 1; }
  python3 - <<'PY'
import json, subprocess
t = json.load(open("trabalho/va/tts/tempos.json"))
for cid in ("EX", "GL"):
    n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", f"mp4/{cid}.mp4"], capture_output=True, text=True).stdout.strip())
    assert n == round(t[cid]["total"] * 30), (cid, n, t[cid])
ps = json.load(open("mp4/web/GL.palavras.json"))
assert ps[-1]["w"].startswith("operator") and abs(ps[0]["t"] - t["GL"]["lead"]) < 1e-6, ps
PY
  sed -i.bak 's/veQuando("operator")/veQuando("orquestrador")/' cenas/GL.html
  if "${RW[@]}" --cenas GL > render.log 2>&1; then echo "cena com palavra fora da narração devia falhar"; exit 1; fi
  grep -q 'veQuando("orquestrador")' render.log || { echo "faltou a mensagem da palavra fora da fala:"; cat render.log; exit 1; }
)
pass "render_web.py (video-animado): cena em HTML com a duração da narração, palavras na grafia do roteiro, folha por cena, cena do Manim ignorada, palavra fora da fala derruba só com mensagem clara"

if [[ "${VE_TESTE_REDE:-}" == 1 ]]; then
  for m in cena-three cena-gsap; do
    "${WEB[@]}" "$ROOT/skills/cena-web/templates/$m.html" "$m.png" --quadro 3.5 --tamanho 960x540 2>aviso.txt >/dev/null
    ! grep -q "AVISO" aviso.txt || { echo "$m: avisos no render:"; cat aviso.txt; exit 1; }
    ffmpeg -v error -y -i "$m.png" -vf "scale=8:8,format=gray" -f rawvideo - > "$m.g"
    python3 -c "b = open('$m.g','rb').read(); assert max(b) - min(b) > 40, ('quadro sem conteúdo', min(b), max(b))"
  done
  pass "modelos cena-three.html e cena-gsap.html renderizam com as bibliotecas do cache, sem aviso"
fi
echo "cena_web ok"
