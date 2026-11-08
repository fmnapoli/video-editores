#!/usr/bin/env python3
"""Recorta a pessoa (rembg, sem tela verde) num trecho do vídeo e compõe sobre o fundo com sombra.
Processa em streaming (ffmpeg -> rembg -> ffmpeg), sem gravar frames em disco; máscara calculada a
960x540 (o U²-Net trabalha a 320x320, nada se perde) e suavizada no tempo (65/35) para o cabelo não tremer.
Saída: <out>.mp4 (composto, H.264) e <out>_alpha.mp4 (máscara em cinza, para recompor com deslocamento).

Uso: uv run --with rembg --with onnxruntime --with pillow --with numpy python matte.py VIDEO INI FIM FUNDO.png OUT_BASE
     [--threads 4] [--model u2net_human_seg] [--fps 30]
CPU: ~1–3 s por frame. Vários trechos em paralelo: matte_workers.sh. Com GPU NVIDIA: `--gpu` e `--with onnxruntime-gpu`
(não validado nesta máquina; sem GPU o onnxruntime cai no CPU sozinho).
"""
import argparse, subprocess, time
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter
from rembg import new_session, remove

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("start", type=float); ap.add_argument("end", type=float)
ap.add_argument("fundo"); ap.add_argument("out"); ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--fps", type=int, default=30); ap.add_argument("--model", default="u2net_human_seg"); ap.add_argument("--gpu", action="store_true", help="onnxruntime-gpu (CUDA); rode com --with onnxruntime-gpu em vez de onnxruntime")
a = ap.parse_args()
W, H = 1920, 1080
so = ort.SessionOptions(); so.intra_op_num_threads = a.threads; so.inter_op_num_threads = 1
prov = ["CUDAExecutionProvider", "CPUExecutionProvider"] if a.gpu else ["CPUExecutionProvider"]
sess = new_session(a.model, sess_opts=so, providers=prov)
bg = np.asarray(Image.open(a.fundo).convert("RGB")).astype(np.float32)

dur = a.end - a.start
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a.start:.3f}", "-t", f"{dur:.3f}", "-i", a.video,
                        "-vf", f"fps={a.fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       stdout=subprocess.PIPE, bufsize=W*H*3*4)
enc_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                        *enc_args, a.out + ".mp4"], stdin=subprocess.PIPE)
enca = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", a.out + "_alpha.mp4"], stdin=subprocess.PIPE)
prev = None; n = 0; t0 = time.time()
while True:
    buf = dec.stdout.read(W*H*3)
    if len(buf) < W*H*3: break
    frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    small = Image.fromarray(frame).resize((960, 540), Image.BILINEAR)
    m = remove(small, session=sess, only_mask=True, post_process_mask=True)   # PIL L 960x540
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
