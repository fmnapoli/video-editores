#!/usr/bin/env bash
# Testa o núcleo (pacote video_editores): registro de modelos, catálogo, CLI, tarefas e servidor MCP em processo.
# Uso: tests/nucleo.sh   (ffmpeg, python3 e uv; o pacote mcp é baixado pelo uv)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cd "$T"
pass() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
export PYTHONPATH="$ROOT"

# registro e configuração de modelos (sem instalar os modelos)
python3 - <<'PY'
import os
from video_editores import modelos, __version__
assert __version__
l = modelos.listar()
assert l["tipos"]["asr"]["escolhido"] == "faster-whisper" and l["tipos"]["tts"]["escolhido"] == "edge"
assert modelos.deps("seg", dev="cpu") == ["rembg", "onnxruntime", "pillow", "numpy"]
assert modelos.deps("seg", dev="cuda")[1] == "onnxruntime-gpu"
os.environ["VE_SEG"] = "inexistente"
try:
    modelos.classe("seg"); raise SystemExit("devia falhar")
except KeyError as e:
    assert "inexistente" in str(e)
os.environ["VE_SEG"] = "rembg"
os.environ["VE_MODELOS_EXTRA"] = "asr:fake=video_editores.modelos.asr_faster_whisper:FasterWhisper"
assert "fake" in modelos.listar()["tipos"]["asr"]["backends"]
open("video-editores.toml", "w").write('[modelos]\nasr = "fake"\ndevice = "cpu"\n')
assert modelos.config()["asr"] == "fake" and modelos.device() == "cpu"
os.environ["VE_ASR"] = "faster-whisper"
assert modelos.config()["asr"] == "faster-whisper", "env vence o toml"
PY
rm -f video-editores.toml
pass "modelos: registro, deps por dispositivo, toml e env"

# codificador configurável
python3 - <<'PY'
import os
from video_editores.nucleo import ffmpeg
assert ffmpeg.codec_video(crf=18)[:2] == ["-c:v", "libx264"]
os.environ["VE_ENCODER"] = "h264_nvenc"
assert "-cq" in ffmpeg.codec_video(crf=18)
os.environ["VE_ENCODER"] = "nada"
try:
    ffmpeg.codec_video(); raise AssertionError
except SystemExit:
    pass
PY
pass "ffmpeg.codec_video: libx264 padrão, NVENC por VE_ENCODER, valor inválido aborta"

# identidade visual (ADR-17): resolução, papéis derivados, conversões, contraste, erros
mkdir -p marca && ffmpeg -v error -y -f lavfi -i color=c=white:s=283x81:d=0.1 -frames:v 1 marca/logo.png
python3 - <<'PY'
import json, os
from video_editores.nucleo import marca as M
assert M.carregar(base="vazio").definida is False and M.carregar().cores["acento"] == "#FF6B35"
json.dump({"nome": "Teste", "cores": {"fundo": "#0B2545", "acento": "#2DD4BF", "texto": "#FFFFFF"},
           "logo": {"png": "logo.png"}, "legenda": {"estilo": "palavra"}}, open("marca/marca.json", "w"))
m = M.carregar()
assert m.definida and m.nome == "Teste" and m.logo("png").endswith("marca/logo.png") and not m.problemas()
assert m.cores["fundo2"] == "#0B2545" and m.cores["secundario"] == "#2DD4BF" and m.cores["texto2"] == "#FFFFFF", "opcional deriva da marca"
assert m.fonte == "DejaVu Sans" and m.fontes_dir() is None and m.legenda["estilo"] == "palavra" and m.legenda["caixa"] is True
assert M.ass("#2DD4BF") == "&H00BFD42D&" and M.ass("#0B2545", 0x14) == "&H1445250B&" and M.ffcor("#0B2545") == "0x0B2545"
assert M.rgb("#2DD4BF") == (45, 212, 191) and m.cor("acento") == "#2DD4BF" and m.cor("#FACC15") == "#FACC15"
assert round(M.contraste("#FFFFFF", "#000000")) == 21 and 15 < M.contraste("#FFFFFF", "#0B2545") < 16
aj = M.ajustar_contraste("#335577", "#0B2545", 7)
assert aj != "#335577" and M.contraste(aj, "#0B2545") >= 7 and M.ajustar_contraste("#FFFFFF", "#0B2545", 7) == "#FFFFFF"
assert M.carregar(False).definida is False, "marca: false força o padrão"
os.environ["VE_MARCA"] = "nao-existe.json"; assert M.carregar().nome == "Teste"; del os.environ["VE_MARCA"]
json.dump({"cores": {"fundo": "azul", "texto": "#FFFFFF"}, "logo": {"png": "sumiu.png"}, "legenda": {"estilo": "x"}}, open("ruim.json", "w"))
p = M.carregar("ruim.json", estrito=False).problemas()
assert any("acento" in x for x in p) and any("#RRGGBB" in x for x in p) and any("sumiu.png" in x for x in p) and any("estilo" in x for x in p), p
for ruim in ("ruim.json", "nao-existe.json"):
    try:
        M.carregar(ruim); raise AssertionError(ruim)
    except SystemExit:
        pass
PY
uv run --quiet --with pillow --with fonttools python "$ROOT/scripts/validar_marca.py" marca/marca.json --gravar >val.json
python3 - <<'PY'
import json
v = json.load(open("val.json")); m = json.load(open("marca/marca.json"))
assert not v["erros"] and v["contraste"]["texto_fundo"] > 15 and m["contraste"]["acento_fundo"] > 7, v
assert any("tela clara" in a for a in v["avisos"]) and any("pequeno para o encerramento" in a for a in v["avisos"]), v["avisos"]
PY
test -s marca/prancha.png
python3 -c 'import json; json.dump({"cores": {"fundo": "#0B2545", "acento": "#113355", "texto": "#8899AA"}}, open("fraca.json", "w"))'
if uv run --quiet --with pillow --with fonttools python "$ROOT/scripts/validar_marca.py" fraca.json --sem-prancha >fraca.out; then echo "validador deveria reprovar contraste"; exit 1; fi
python3 -c 'import json; v=json.load(open("fraca.out")); assert len(v["ajustes_propostos"]) == 2 and len(v["erros"]) == 2, v'
rm -rf marca
pass "marca: resolução (spec > VE_MARCA > marca/), papéis derivados, conversões, contraste e ajuste proposto, validador e prancha"

# áudio: normalização com teto de pico real (fala simulada: senoide baixa + um estalo a fundo de escala a cada 2 s,
# o degrau de junção que o loudnorm linear amplificava)
ffmpeg -v error -y -f lavfi -i "aevalsrc=0.05*sin(2*PI*300*t)+if(lt(mod(t\,2)\,0.005)\,0.99\,0):s=48000:d=8" -c:a pcm_s16le cliques.wav
python3 - <<'PY'
from video_editores.nucleo import audio
assert audio.quadros(1.016, 30) == 1.0 and audio.quadros(2.49, 30) == 2.5
assert audio.fades(2.0).endswith("afade=t=out:st=1.9820:d=0.018")
m = audio.medir("cliques.wav")
assert m["TP"] > -1.0, m          # os cliques estouram antes
r = audio.normalizar("cliques.wav", "norm.wav", alvo=-14, tp=-1.5)
s = r["saida"]
assert s["TP"] <= -1.3, r
assert abs(s["I"] + 14) < 1.5, r      # o limiter só age nos estalos; a fala fica no alvo
assert r["passadas"] >= 1 and r["ganho_db"] > 0, r
print(audio.resumo(r))
PY
pass "audio.normalizar: -14 LUFS com pico real <= -1,5 dBTP apesar dos cliques; quadros e fades"

# TTS: o edge-tts falha de vez em quando sem motivo; o backend repete (stub simula as falhas)
VE_TTS_ESPERA=0 VE_STUB_EDGE_FALHAS=2 PYTHONPATH="$ROOT:$ROOT/tests/stub" python3 - <<'PY' 2>err.txt
from video_editores.modelos.tts_edge import EdgeTTS
ws = EdgeTTS().sintetizar("um dois três", mp3="r.mp3")
assert len(ws) == 3, ws
PY
grep -q "tentativa 2 falhou" err.txt && test -s r.mp3
if VE_TTS_ESPERA=0 VE_STUB_EDGE_FALHAS=5 PYTHONPATH="$ROOT:$ROOT/tests/stub" python3 -c "
from video_editores.modelos.tts_edge import EdgeTTS; EdgeTTS().sintetizar('a', mp3='r2.mp3')" 2>/dev/null; then echo "devia falhar"; exit 1; fi
pass "tts_edge: repete 3 vezes em NoAudioReceived e desiste com erro claro"

# catálogo e CLI
python3 -m video_editores.cli listar | grep -q "aula-finalizar"
python3 -m video_editores.cli modelos | grep -q '"device_efetivo"'
python3 - <<'PY'
from video_editores.nucleo import catalogo
for op in catalogo.OPERACOES.values():
    assert op.caminho.is_file(), op.script
c = catalogo.comando("transcrever", ["x.mp4"])
assert c[:4] == ["uv", "run", "--quiet", "--with"] and c[4] == "faster-whisper" and "-I" in c
assert catalogo.comando("prova", ["x.mp4"])[0] == "bash"
assert catalogo.comando("tomadas", ["x.json"])[0].endswith("python3") or "python" in catalogo.comando("tomadas", ["x.json"])[0]
assert catalogo.comando("aula-recorte", [], device="cuda")[6] == "onnxruntime-gpu"
PY
pass "catálogo: todos os scripts existem; comando com uv/--with, bash e python"

ffmpeg -v error -y -f lavfi -i "testsrc2=size=320x180:rate=30:duration=4" -f lavfi -i "sine=f=300:d=4" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac in.mp4
python3 -m video_editores.cli prova in.mp4 4 >/dev/null && test -s in.proof.txt
pass "CLI: video-editores prova roda o script"

echo '{"keep":[[0,1],[2,3]]}' > k.json
ID=$(python3 -m video_editores.cli montar-trechos in.mp4 k.json fundo.mp4 --fundo 2>/dev/null)
python3 - "$ID" <<'PY'
import sys, os
from video_editores.tarefas import Tarefas
t = Tarefas(os.getcwd()).esperar(sys.argv[1], timeout=120)
assert t["estado"] == "ok" and os.path.exists("fundo.mp4"), t
PY
python3 -m video_editores.cli tarefas | grep -q "\"$ID\""
pass "tarefas: --fundo roda detached, esperar e listar"

if command -v uv >/dev/null; then
  # o servidor registra no stderr os erros esperados (caminho fora da raiz, operação inexistente); só mostra se falhar
  if ! OUT=$(uv run --quiet --with "mcp>=2" python -I "$ROOT/tests/mcp_test.py" "$T" 2>"$T/mcp.err"); then cat "$T/mcp.err"; exit 1; fi
  echo "$OUT" | grep -q '"tools"'
  pass "MCP em processo: ferramentas, operação curta, tarefa longa, raiz respeitada ($OUT)"
else
  echo "  (uv ausente: teste do MCP pulado)"
fi
# integração com Codex, OpenCode e Kiro (escopo de projeto): skills portadas, MCP registrado, regras; idempotente; remoção limpa
mkdir -p integ/.codex && printf '[model]\nname = "x"\n\n[mcp_servers.outro]\ncommand = "y"\n' > integ/.codex/config.toml
printf '# Meu projeto\n\nRegras minhas.\n' > integ/AGENTS.md
python3 -m video_editores.cli integrar todos --projeto integ >/dev/null
python3 -m video_editores.cli integrar todos --projeto integ >/dev/null   # 2ª vez: nada duplica
python3 - <<'PY'
import json, re, pathlib, tomllib
p = pathlib.Path("integ")
sk = sorted(x.name for x in (p / ".agents/skills").iterdir()); assert len(sk) == 21 and "partitura" in sk, sk
assert sorted(x.name for x in (p / ".kiro/skills").iterdir()) == sk
for s in (p / ".kiro/skills").glob("*/SKILL.md"):
    t = s.read_text(); fm = re.match(r"---\n(.*?)\n---", t, re.S).group(1)
    assert re.search(r"^name: " + re.escape(s.parent.name) + "$", fm, re.M), s      # Kiro exige name == pasta
    assert "CLAUDE_PLUGIN_ROOT" not in t and "Fora do Claude Code" in t, s
assert (p / ".agents/skills/video-docs/glossario-ingles.json").is_file()
ag = (p / "AGENTS.md").read_text(); assert ag.startswith("# Meu projeto") and ag.count("video-editores:inicio") == 1, ag
oc = json.loads((p / "opencode.json").read_text())["mcp"]["servers"]["video-editores"]; assert oc["type"] == "local" and oc["command"][-2] == "--raiz"
ki = json.loads((p / ".kiro/settings/mcp.json").read_text())["mcpServers"]["video-editores"]; assert ki["command"] and "args" in ki
cx = tomllib.loads((p / ".codex/config.toml").read_text()); assert cx["model"]["name"] == "x" and cx["mcp_servers"]["outro"]["command"] == "y"
assert cx["mcp_servers"]["video-editores"]["args"][-1].endswith("integ")
st = (p / ".kiro/steering/video-editores.md").read_text(); assert st.startswith("---\ninclusion: always") and st.count("inicio -->") == 1
PY
python3 -m video_editores.cli integrar todos --projeto integ --remover >/dev/null
test ! -e integ/.agents/skills/videoaula && test ! -e integ/.kiro/steering/video-editores.md
grep -q "Regras minhas" integ/AGENTS.md && ! grep -q "video-editores:inicio" integ/AGENTS.md
python3 -c "import tomllib; d=tomllib.loads(open('integ/.codex/config.toml').read()); assert 'video-editores' not in d['mcp_servers'] and d['mcp_servers']['outro']"
pass "integrar: Codex, OpenCode e Kiro (skills, MCP, regras), idempotente, remoção preserva o que não é nosso"

if command -v uv >/dev/null; then
  # o comando que os agentes vão executar sobe o servidor por stdio e responde
  uv run --quiet --with "mcp>=2" python -I - "$ROOT" "$T" <<'PY' 2>"$T/stdio.err" || { cat "$T/stdio.err"; exit 1; }
import asyncio, os, sys
from mcp import Client, StdioServerParameters
root, raiz = sys.argv[1], sys.argv[2]
real = os.path.realpath(raiz)   # macOS: /var/folders/... -> /private/var/...
async def m():
    p = StdioServerParameters(command="uv", args=["run", "--quiet", "--with", "mcp>=2", "--directory", root, "python", "-m", "video_editores.mcp_server", "--raiz", raiz])
    async with Client(p) as c:
        assert len((await c.list_tools()).tools) >= 15
        v = (await c.call_tool("versao", {})).structured_content
        assert os.path.realpath(v["raiz"]) == real, (v["raiz"], real)
asyncio.run(m())
PY
  pass "MCP por stdio: o comando registrado nos agentes sobe e responde"
fi
echo "nucleo ok"
