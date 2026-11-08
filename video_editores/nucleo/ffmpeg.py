"""ffmpeg/ffprobe: sondagem, decodificação de áudio para ASR e escolha de codificador (CPU ou GPU)."""
import json
import os
import shutil
import subprocess


def probe_dimensoes(path):
    """(largura, altura) já considerando o metadado de rotação (vídeo de celular)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    st = json.loads(out)["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    return (h, w) if abs(rot) % 180 == 90 else (w, h)


def duracao(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def fps(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    n, d = out.split("/")
    return float(n) / float(d)


def decodificar_audio(path, sr=16000):
    """Áudio mono float32 a `sr` Hz como numpy, via ffmpeg. Sem ffmpeg devolve o caminho (o ASR tenta o PyAV).
    Motivo: o PyAV 19 removeu `metadata_errors` e quebrava o decode interno do faster-whisper 1.2."""
    import numpy as np
    if not shutil.which("ffmpeg"):
        return str(path)
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32)


# Codificadores: qualidade equivalente a libx264 crf 18 / veryfast. NVENC usa -cq, VideoToolbox -q:v.
_ENCODERS = {
    "libx264": lambda crf, preset: ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)],
    "h264_nvenc": lambda crf, preset: ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(crf), "-b:v", "0"],
    "hevc_nvenc": lambda crf, preset: ["-c:v", "hevc_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(crf), "-b:v", "0"],
    "h264_videotoolbox": lambda crf, preset: ["-c:v", "h264_videotoolbox", "-q:v", str(max(1, 100 - crf * 3))],
    "h264_vaapi": lambda crf, preset: ["-c:v", "h264_vaapi", "-qp", str(crf)],
}


def encoder() -> str:
    return os.environ.get("VE_ENCODER") or "libx264"


def codec_video(crf=18, preset="veryfast", pix_fmt="yuv420p") -> list:
    """Argumentos de vídeo do ffmpeg para o codificador configurado em VE_ENCODER (padrão libx264).
    A escolha de GPU é só desta variável: os scripts não precisam saber se há NVENC."""
    enc = encoder()
    if enc not in _ENCODERS:
        raise SystemExit(f"VE_ENCODER={enc!r} desconhecido; use {', '.join(_ENCODERS)}")
    return _ENCODERS[enc](crf, preset) + ["-pix_fmt", pix_fmt]


def encoders_disponiveis() -> list:
    """Codificadores da tabela que este ffmpeg declara ter (não garante que o hardware exista)."""
    if not shutil.which("ffmpeg"):
        return []
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return [e for e in _ENCODERS if f" {e} " in out]
