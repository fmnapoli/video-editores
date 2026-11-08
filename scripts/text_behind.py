#!/usr/bin/env python3
"""Texto atrás da pessoa: desenha o texto e recoloca a pessoa (segmentada) por cima.

Pipeline por frame: frame -> rembg (máscara da pessoa) -> fundo + texto -> pessoa por cima.
Processa só o intervalo pedido (--start/--end) e devolve o vídeo completo com o
trecho substituído. CPU funciona, mas é lento (~2-6 fps); use trechos curtos.

Uso: text_behind.py IN.mp4 OUT.mp4 --text "TEXTO" [--start 0 --end 3]
     [--font /caminho/fonte.ttf] [--size 0.22] [--color "#FFFFFF"] [--y 0.35]
     [--model u2net_human_seg|birefnet-portrait]

Modelos (rembg): u2net_human_seg (rápido, padrão) ou birefnet-portrait (bordas e cabelo
muito melhores, ~3-5x mais lento; recomendado com GPU).
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

import os
sys.path.insert(0, os.environ.get("VE_PKG_DIR") or str(pathlib.Path(__file__).resolve().parents[1]))
from video_editores import modelos  # noqa: E402


def sh(*cmd):
    subprocess.run(cmd, check=True)


def probe_fps(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "default=nw=1:nk=1", path],
                         capture_output=True, text=True, check=True).stdout.strip()
    n, d = out.split("/")
    return float(n) / float(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--text", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=3.0)
    ap.add_argument("--font", default=None)
    ap.add_argument("--size", type=float, default=0.22, help="altura da fonte relativa à altura do vídeo")
    ap.add_argument("--color", default="#FFFFFF")
    ap.add_argument("--y", type=float, default=0.35, help="posição vertical do centro do texto (0-1)")
    ap.add_argument("--model", default="u2net_human_seg")
    ap.add_argument("--backend", default=None, help="backend de segmentação (padrão: VE_SEG ou rembg)")
    a = ap.parse_args()

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        sys.exit("faltam dependências: uv run --with rembg --with onnxruntime --with pillow --with numpy ...")

    fps = probe_fps(a.input)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="tb_"))
    fr, outfr = tmp / "in", tmp / "out"
    fr.mkdir(); outfr.mkdir()
    sh("ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(a.start), "-to", str(a.end),
       "-i", a.input, str(fr / "%06d.png"))

    seg = modelos.get_segmentador(a.backend, modelo=a.model, device=modelos.device())
    frames = sorted(fr.glob("*.png"))
    font = None
    for i, p in enumerate(frames, 1):
        img = Image.open(p).convert("RGBA")
        W, H = img.size
        if font is None:
            px = int(H * a.size)
            try:
                font = ImageFont.truetype(a.font, px) if a.font else ImageFont.truetype("DejaVuSans-Bold.ttf", px)
            except OSError:
                font = ImageFont.load_default(px)
            # encolhe até caber na largura
            d = ImageDraw.Draw(img)
            while d.textlength(a.text, font=font) > W * 0.92 and px > 10:
                px = int(px * 0.92)
                font = font.font_variant(size=px)
        person = seg.recortar(img)  # RGBA com alpha = pessoa
        bg = img.copy()
        d = ImageDraw.Draw(bg)
        d.text((W / 2, H * a.y), a.text, font=font, fill=a.color, anchor="mm")
        bg.alpha_composite(person)
        bg.convert("RGB").save(outfr / p.name)
        if i % 25 == 0:
            print(f"  {i}/{len(frames)} frames", flush=True)

    seg = tmp / "seg.mp4"
    sh("ffmpeg", "-hide_banner", "-loglevel", "error", "-framerate", f"{fps}", "-i", str(outfr / "%06d.png"),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(seg))

    # substitui o trecho de vídeo mantendo o áudio original
    fc = (f"[0:v]trim=0:{a.start},setpts=PTS-STARTPTS[a];"
          f"[1:v]setpts=PTS-STARTPTS[b];"
          f"[0:v]trim=start={a.end},setpts=PTS-STARTPTS[c];"
          f"[a][b][c]concat=n=3:v=1:a=0[v]")
    if a.start <= 0:
        fc = (f"[1:v]setpts=PTS-STARTPTS[b];[0:v]trim=start={a.end},setpts=PTS-STARTPTS[c];"
              f"[b][c]concat=n=2:v=1:a=0[v]")
    sh("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.input, "-i", str(seg),
       "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
       "-crf", "20", "-c:a", "copy", a.output)
    shutil.rmtree(tmp)
    print(f"ok -> {a.output}")


if __name__ == "__main__":
    main()
