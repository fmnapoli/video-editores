#!/usr/bin/env python3
"""Recorta a pessoa (rembg, sem tela verde) num trecho do vídeo e compõe sobre o fundo com sombra.
Processa em streaming (ffmpeg -> rembg -> ffmpeg), sem gravar frames em disco; máscara calculada a
960x540 (o U²-Net trabalha a 320x320, nada se perde) e suavizada no tempo (65/35) para o cabelo não tremer.
Saída: <out>.mp4 (composto, H.264) e <out>_alpha.mp4 (máscara em cinza, para recompor com deslocamento).

Uso: uv run --with rembg --with onnxruntime --with pillow --with numpy python matte.py VIDEO INI FIM FUNDO.png OUT_BASE
     [--threads 4] [--model u2net_human_seg] [--fps 30] [--gpu] [--backend rembg]
CPU: ~1–3 s por frame. Vários trechos em paralelo: matte_workers.sh. Com GPU NVIDIA: VE_DEVICE=cuda (ou `--gpu`) e
`--with onnxruntime-gpu`; `video-editores aula-recorte` escolhe o pacote certo sozinho. Codificador por VE_ENCODER
(libx264 padrão, h264_nvenc, ...). O segmentador é o backend "seg" de video_editores.modelos.
"""
import argparse, os, pathlib, subprocess, sys, time
import numpy as np
from PIL import Image, ImageFilter

def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores import modelos  # noqa: E402
from video_editores.nucleo.ffmpeg import codec_video  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("start", type=float); ap.add_argument("end", type=float)
ap.add_argument("fundo"); ap.add_argument("out"); ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--fps", type=int, default=30); ap.add_argument("--model", default="u2net_human_seg")
ap.add_argument("--gpu", action="store_true", help="força CUDA (equivale a VE_DEVICE=cuda)")
ap.add_argument("--backend", default=None, help="backend de segmentação (padrão: VE_SEG ou rembg)")
a = ap.parse_args()
W, H = 1920, 1080
dev = "cuda" if a.gpu else modelos.device()
seg = modelos.get_segmentador(a.backend, modelo=a.model, device=dev, threads=a.threads)
bg = np.asarray(Image.open(a.fundo).convert("RGB")).astype(np.float32)

dur = a.end - a.start
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a.start:.3f}", "-t", f"{dur:.3f}", "-i", a.video,
                        "-vf", f"fps={a.fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       stdout=subprocess.PIPE, bufsize=W*H*3*4)
enc_args = [*codec_video(crf=17), "-movflags", "+faststart"]
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                        *enc_args, a.out + ".mp4"], stdin=subprocess.PIPE)
enca = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                         *codec_video(crf=20), a.out + "_alpha.mp4"], stdin=subprocess.PIPE)
prev = None; n = 0; t0 = time.time()
while True:
    buf = dec.stdout.read(W*H*3)
    if len(buf) < W*H*3: break
    frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    small = Image.fromarray(frame).resize((960, 540), Image.BILINEAR)
    m = seg.mascara(small)   # PIL L 960x540
    m = np.asarray(m.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255.0
    if prev is not None:
        m = 0.65 * m + 0.35 * prev          # suavização temporal leve
    prev = m
    # sombra: máscara deslocada e borrada
    # sombra em baixa resolução (4x menor) e reamostrada: mesmo visual, ~4x mais rápido
    shs = Image.fromarray((m * 255).astype(np.uint8)).resize((480, 270), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6.5))
    sh = np.asarray(shs.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255.0
    sh = np.roll(sh, 24, axis=0) * 0.6
    comp = bg * (1 - sh[..., None]) + 0 * sh[..., None]     # escurece o fundo onde há sombra
    comp = comp * (1 - m[..., None]) + frame.astype(np.float32) * m[..., None]
    enc.stdin.write(np.clip(comp, 0, 255).astype(np.uint8).tobytes())
    enca.stdin.write((m * 255).astype(np.uint8).tobytes())
    n += 1
    if n % 150 == 0:
        el = time.time() - t0
        print(f"{a.out}: {n} frames, {el/n:.2f} s/frame, faltam ~{(dur*a.fps-n)*el/n/60:.0f} min", flush=True)
enc.stdin.close(); enca.stdin.close(); enc.wait(); enca.wait(); dec.wait()
print(f"ok {a.out}: {n} frames em {(time.time()-t0)/60:.1f} min", flush=True)
