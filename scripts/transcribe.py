#!/usr/bin/env python3
"""Transcreve um vídeo/áudio com faster-whisper.

Gera, ao lado do arquivo de entrada:
  <nome>.transcript.json  -> segmentos e palavras com timestamps
  <nome>.srt              -> legenda por segmento
  <nome>.words.srt        -> legenda curta (N palavras por bloco, estilo reels)

Uso: uv run --with faster-whisper python transcribe.py VIDEO [--model medium] [--lang pt]
     [--prompt "vocabulário do domínio: Kubernetes, ArgoCD, Terraform"] [--out-dir trabalho/meu-video] [--words-per-cue 3]

Mesmo motor do whisper-ctranslate2 usado no video-docs (CTranslate2). O modelo `small`
erra termos de domínio; `medium` + --prompt é o padrão validado.
"""
import argparse, json, pathlib, shutil, subprocess, sys


def decode_audio_ffmpeg(path, sr=16000):
    """Áudio mono float32 a 16 kHz via ffmpeg (numpy já vem com o faster-whisper)."""
    import numpy as np
    if not shutil.which("ffmpeg"):
        return str(path)  # sem ffmpeg, deixa o faster-whisper tentar o PyAV
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32)


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
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper não instalado: pip install faster-whisper")

    src = pathlib.Path(a.input)
    model = WhisperModel(a.model, device=a.device, compute_type="int8" if a.device in ("auto", "cpu") else "auto")
    # Decodifica o áudio com o ffmpeg em vez do PyAV: o PyAV 19 removeu o argumento `metadata_errors` que o
    # faster-whisper 1.2 ainda passa ("open() got an unexpected keyword argument 'metadata_errors'").
    audio = decode_audio_ffmpeg(src)
    segments, info = model.transcribe(audio, language=None if a.lang == "auto" else a.lang,
                                      word_timestamps=True, vad_filter=True,
                                      initial_prompt=a.prompt)

    segs, words = [], []
    for s in segments:
        ws = [{"start": w.start, "end": w.end, "word": w.word} for w in (s.words or [])]
        segs.append({"start": s.start, "end": s.end, "text": s.text.strip(), "words": ws,
                     "avg_logprob": s.avg_logprob, "no_speech_prob": s.no_speech_prob})
        words.extend(ws)

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
