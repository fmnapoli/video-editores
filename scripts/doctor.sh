#!/usr/bin/env bash
# Verifica dependências do plugin video-editores (não instala nada no Python do sistema).
# Uso: doctor.sh
set -u
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
miss() { printf '  \033[31m✘\033[0m %s  →  %s\n' "$1" "$2"; MISSING=1; }
opt()  { printf '  \033[33m•\033[0m %s  →  %s\n' "$1" "$2"; }
MISSING=0

echo "Base (obrigatório):"
command -v ffmpeg  >/dev/null && ok "ffmpeg"  || miss "ffmpeg"  "apt install ffmpeg | brew install ffmpeg"
command -v ffprobe >/dev/null && ok "ffprobe" || miss "ffprobe" "vem com o ffmpeg"
if command -v ffmpeg >/dev/null; then
  ffmpeg -hide_banner -filters 2>/dev/null | grep -qE ' (ass|subtitles) ' && ok "ffmpeg com libass" \
    || miss "ffmpeg com libass" "Linux: ffmpeg do apt. macOS: 'brew install ffmpeg-full' e ponha \$(brew --prefix ffmpeg-full)/bin antes no PATH (a fórmula 'ffmpeg' do Homebrew vem sem libass desde a v8)"
fi
command -v python3 >/dev/null && ok "python3" || miss "python3" "instale Python 3.10+"
command -v uv      >/dev/null && ok "uv"      || miss "uv" "https://docs.astral.sh/uv/getting-started/installation/"
if command -v fc-list >/dev/null; then
  fc-list 2>/dev/null | grep -qi "DejaVuSans-Bold\|DejaVu Sans:style=Bold" && ok "fonte DejaVu Sans Bold" \
    || miss "fonte DejaVu Sans Bold" "apt install fonts-dejavu-core | brew install --cask font-dejavu"
else
  opt "fontconfig (fc-list)" "sem ele não dá para checar a fonte; instale fontconfig"
fi

echo "CLIs por skill:"
command -v auto-editor >/dev/null && ok "auto-editor (/corte)" || miss "auto-editor (/corte)" "uv tool install auto-editor"
command -v yt-dlp      >/dev/null && ok "yt-dlp (/referencia)" || opt "yt-dlp (/referencia)" "uv tool install yt-dlp"
command -v scenedetect >/dev/null && ok "scenedetect (/referencia, /efeitos)" || opt "scenedetect" "uv tool install scenedetect"
command -v manim       >/dev/null && ok "manim (/animacao, /video-animado)" || opt "manim (/animacao, /video-animado)" "uv tool install manim  (se o manimpango falhar por falta de libpango-dev: micromamba create -n manim -c conda-forge manim, ver docs/troubleshooting.md)"
command -v blender     >/dev/null && ok "blender (/3d)" || opt "blender (/3d)" "https://www.blender.org/download/"

echo "Modelos de IA (video_editores.modelos; troque com VE_ASR/VE_SEG/VE_TTS/VE_IMAGEM, VE_DEVICE, VE_ENCODER):"
HERE="$(cd "$(dirname "$0")" && pwd)"
if PYTHONPATH="$HERE/.." python3 -c "import video_editores" 2>/dev/null; then
  PYTHONPATH="$HERE/.." python3 - <<'PY2'
from video_editores import modelos
from video_editores.nucleo import ffmpeg
l = modelos.listar()
for tipo, d in l["tipos"].items():
    print(f"  • {tipo}: {d['escolhido']}  (disponíveis: {', '.join(d['backends'])})")
print(f"  • dispositivo: {l['config']['device']} -> efetivo {l['device_efetivo']}; codificador: {ffmpeg.encoder()}")
PY2
  if command -v nvidia-smi >/dev/null; then ok "GPU NVIDIA visível (nvidia-smi); use VE_DEVICE=cuda e VE_ENCODER=h264_nvenc"; else opt "GPU NVIDIA" "sem nvidia-smi: tudo roda em CPU (recorte por IA ~1-3 s/frame)"; fi
  # geração de imagem (ADR-15): servidor ComfyUI à parte, opcional
  COMFY=$(PYTHONPATH="$HERE/.." python3 - 2>&1 <<'PY3'
from video_editores import modelos
try:
    g = modelos.get_imagem()
    s = g.conferir(timeout=5)
    gpu = ", ".join(f"{d['nome']} {d['vram_gb']} GB" for d in s["dispositivos"]) or "sem dispositivo"
    print(f"OK servidor {g.url} (ComfyUI {s['versao']}; {gpu}); workflow {g.workflow_arq.stem}: {g.checkpoint()}")
except Exception as e:
    print(f"-- {e}")
PY3
)
  case "$COMFY" in
    OK*) ok "imagem (gerar-imagem): ${COMFY#OK }" ;;
    *)   opt "imagem (gerar-imagem, opcional)" "${COMFY#-- }" ;;
  esac
  if command -v ffmpeg >/dev/null; then
    ENCS=$(PYTHONPATH="$HERE/.." python3 -c "from video_editores.nucleo import ffmpeg; print(' '.join(ffmpeg.encoders_disponiveis()))")
    echo "  • codificadores neste ffmpeg: ${ENCS:-nenhum da tabela}"
  fi
else
  opt "pacote video_editores" "rode o doctor de dentro do repositório/plugin para ver os modelos configurados"
fi

echo "Integração (skills portadas para outros agentes):"
VERSAO=$(grep -m1 '^version' "$HERE/../pyproject.toml" 2>/dev/null | cut -d'"' -f2)
if [ -n "$VERSAO" ]; then
  for d in "$HOME/.agents/skills" "$HOME/.config/opencode/skills" "$HOME/.kiro/skills" "$HOME/.zcode/skills"; do
    [ -d "$d" ] || continue
    N=$(grep -ls 'video-editores:port\|plugin \[video-editores\]' "$d"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
    [ "${N:-0}" -gt 0 ] || continue
    V=$(grep -h -m1 -oE 'video-editores:port +v?[0-9][0-9.]*|plugin \[video-editores\]\([^)]*\) v[0-9][0-9.]*' "$d"/*/SKILL.md 2>/dev/null | head -1 | grep -oE '[0-9][0-9.]*$')
    if [ "$V" = "$VERSAO" ]; then
      ok "$N skills do plugin em $d (port $V, em dia)"
    else
      miss "$N skills do plugin em $d estão desatualizadas (port ${V:-?} ≠ plugin $VERSAO)" "da instalação atual, rode: video-editores integrar <agente> [--usuario]"
    fi
  done
else
  opt "Integração" "rode o doctor de dentro do repositório/plugin para checar ports desatualizados"
fi

echo "Pacotes Python (baixados sob demanda por 'uv run --with'; nada a instalar):"
echo "  faster-whisper (/tomada, /legenda), rembg (/texto-atras, /tela-verde), edge-tts + pillow (/video-docs), verovio + resvg-py + numpy + scipy (/partitura)"
if command -v uv >/dev/null; then
  uv run --quiet --with faster-whisper python -c "import faster_whisper" 2>/dev/null \
    && ok "faster-whisper resolve via uv" || opt "faster-whisper" "será baixado no primeiro uso; precisa de internet"
fi
exit $MISSING
