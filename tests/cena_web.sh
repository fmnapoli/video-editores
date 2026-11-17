#!/usr/bin/env bash
# Testa o cena_web.py: cena HTML renderizada quadro a quadro (Chrome sem janela + ffmpeg).
# Uso: tests/cena_web.sh   (ffmpeg, python3, uv e um Chrome/Chromium; sem navegador, o teste é pulado)
#      VE_TESTE_REDE=1 tests/cena_web.sh   também baixa Three.js e GSAP do npm e renderiza os dois modelos
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
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
python3 - <<'PYOUVE' &
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
