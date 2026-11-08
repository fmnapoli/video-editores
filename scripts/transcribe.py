#!/usr/bin/env python3
"""Transcreve um vídeo/áudio com faster-whisper.

Gera, ao lado do arquivo de entrada:
  <nome>.transcript.json  -> segmentos e palavras com timestamps
  <nome>.srt              -> legenda por segmento
  <nome>.words.srt        -> legenda curta (N palavras por bloco, estilo reels)

Uso: uv run --with faster-whisper python transcribe.py VIDEO [--model medium] [--lang pt]
     [--prompt "vocabulário do domínio: Kubernetes, ArgoCD, Terraform"] [--out-dir trabalho/meu-video] [--words-per-cue 3]
     [--backend faster-whisper]      (ou VE_ASR=...; `video-editores transcrever` resolve as dependências sozinho)

O motor é o backend de ASR configurado em video_editores.modelos (padrão faster-whisper, CTranslate2, o mesmo
do whisper-ctranslate2 usado no video-docs). O modelo `small` erra termos de domínio; `medium` + --prompt é o
padrão validado.
"""
import argparse, json, os, pathlib, sys

def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores import modelos  # noqa: E402
from video_editores.nucleo.ffmpeg import decodificar_audio  # noqa: E402

decode_audio_ffmpeg = decodificar_audio  # compatibilidade com quem importava daqui


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{text.strip()}\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--model", default="medium", help="tiny|base|small|medium|large-v3")
    ap.add_argument("--prompt", default=None, help="initial_prompt com vocabulário do domínio")
    ap.add_argument("--lang", default="pt", help="código ISO ou auto")
    ap.add_argument("--out-dir", default=None, help="pasta de saída (padrão: trabalho/<nome>/ se existir trabalho/, senão ao lado da entrada)")
    ap.add_argument("--words-per-cue", type=int, default=3)
    ap.add_argument("--device", default=None, help="auto|cpu|cuda (padrão: VE_DEVICE ou auto)")
    ap.add_argument("--backend", default=None, help="backend de ASR (padrão: VE_ASR ou faster-whisper)")
    a = ap.parse_args()

    src = pathlib.Path(a.input)
    dev = a.device or modelos.config()["device"]
    asr = modelos.get_asr(a.backend, modelo=a.model, device=dev)
    # Decodifica o áudio com o ffmpeg em vez do PyAV: o PyAV 19 removeu o argumento `metadata_errors` que o
    # faster-whisper 1.2 ainda passa ("open() got an unexpected keyword argument 'metadata_errors'").
    tr = asr.transcrever(decodificar_audio(src), lang=a.lang, prompt=a.prompt)
    info = tr
    segs = tr.to_dict(str(src))["segments"]
    words = [w for s in segs for w in s["words"]]

    if a.out_dir:
        out_dir = pathlib.Path(a.out_dir)
    elif pathlib.Path("trabalho").is_dir():
        out_dir = pathlib.Path("trabalho") / src.stem
    else:
        out_dir = src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / src.stem
    out = {"source": str(src), "language": info.language, "duration": info.duration, "segments": segs}
    pathlib.Path(f"{base}.transcript.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    write_srt([(s["start"], s["end"], s["text"]) for s in segs], f"{base}.srt")

    n = max(1, a.words_per_cue)
    cues = [(chunk[0]["start"], chunk[-1]["end"], "".join(w["word"] for w in chunk))
            for chunk in (words[i:i + n] for i in range(0, len(words), n))]
    write_srt(cues, f"{base}.words.srt")
    print(f"ok: {len(segs)} segmentos, {len(words)} palavras -> {base}.transcript.json / .srt / .words.srt")


if __name__ == "__main__":
    main()
