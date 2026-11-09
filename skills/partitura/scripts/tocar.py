"""Exemplo tocado: sintetiza o som de um padrão de bateria (sem samples) e anima a partitura com cada nota
acendendo no instante em que soa, playhead e contador de tempos. Sai um bloco pronto para a montagem.

Uso:
  uv run --with numpy --with scipy --with pillow python tocar.py ID [--partituras partituras] [--out exemplos]
      [--bpm 72] [--voltas 2] [--contagem] [--fundo FUNDO.png] [--rotulo "Exemplo tocado"] [--titulo T]
      [--fonte ARQ.ttf] [--fps 30] [--so-audio]

Lê <partituras>/<ID>_big.json e .png gerados pelo partitura.py (cai no <ID>.json se não houver o grande).
Saída em --out: <ID>.mp4 (1920×1080, com o áudio em AAC), <ID>.wav (48 kHz estéreo, pico a −6 dBFS, o mesmo
áudio sem perda, para a montagem) e <ID>.json {dur, bpm, voltas, pre, eventos}. Vídeo e wav têm a mesma
duração, múltiplo do quadro, então o bloco entra em qualquer EDL sem ajuste (no /video-animado:
cena {"id": ..., "video": "exemplos/ID.mp4", "audio": "exemplos/ID.wav"}).

--voltas: quantas vezes toca os compassos renderizados; --contagem: um compasso de contagem (chimbal + números)
antes. Sons: bumbo (seno com queda de altura), caixa (dois parciais + ruído em banda), chimbal (ruído passa-alta
curto), chimbal de pé, ride (parciais metálicos), tom/surdo (caixa sem esteira). O áudio passa por um passa-baixa
a 15 kHz para não gerar pico real por conteúdo perto de Nyquist.
"""
import argparse
import json
import math
import os
import pathlib
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.signal import butter, sosfilt


def _raiz_pacote(arquivo):
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo import audio  # noqa: E402
from video_editores.nucleo import ffmpeg as ffm  # noqa: E402

SR, W, H = 48000, 1920, 1080
COR = {"hh": (37, 99, 235), "ride": (37, 99, 235), "crash": (37, 99, 235), "sn": (219, 39, 119), "tom": (219, 39, 119),
       "ft": (219, 39, 119), "bd": (234, 88, 12), "hf": (5, 150, 105)}
AMARELO, BRANCO, CINZA = (255, 212, 59, 255), (241, 245, 249, 255), (148, 163, 184, 255)
rng = np.random.default_rng(7)   # ruído determinístico: o mesmo padrão gera o mesmo wav


def fonte_padrao(peso="700"):
    for c in (os.path.expanduser(f"~/.local/share/fonts/inter/Inter-{peso}.ttf"),
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(c):
            return c
    return None


def fonte(caminho, tamanho):
    if caminho and os.path.exists(caminho):
        return ImageFont.truetype(caminho, tamanho)
    try:
        return ImageFont.load_default(tamanho)
    except TypeError:
        return ImageFont.load_default()


# ---------------- síntese
def env(n, dec):
    return np.exp(-np.arange(n) / SR / dec)


def bp(x, lo, hi):
    return sosfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), x)


def hp(x, f):
    return sosfilt(butter(4, f, btype="high", fs=SR, output="sos"), x)


def kick(acento=False):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t / 0.045)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.22) + hp(rng.standard_normal(n), 2000) * env(n, 0.006) * 0.25
    return x * (1.25 if acento else 1.0)


def snare(acento=False, esteira=True):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    tom = (np.sin(2 * np.pi * 185 * t) * 0.5 + np.sin(2 * np.pi * 330 * t) * 0.25) * env(n, 0.07)
    ruido = bp(rng.standard_normal(n), 900, 8000) * env(n, 0.13) * (0.8 if esteira else 0.15)
    return (tom + ruido) * (1.35 if acento else 0.95)


def tom(acento=False):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 130 + 40 * np.exp(-t / 0.08)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.12) * (1.3 if acento else 1.0)


def hihat(acento=False):
    n = int(0.12 * SR)
    return hp(rng.standard_normal(n), 6500) * env(n, 0.035) * 0.55 * (1.4 if acento else 1.0)


def hhfoot(acento=False):
    n = int(0.08 * SR)
    return hp(rng.standard_normal(n), 5000) * env(n, 0.018) * 0.4


def ride(acento=False):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    met = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((3150, 0.22), (5080, 0.14), (7620, 0.09), (1880, 0.1)))
    x = met * env(n, 0.5) + bp(rng.standard_normal(n), 2500, 10000) * env(n, 0.25) * 0.3
    return x * (1.35 if acento else 0.9)


def crash(acento=False):
    n = int(1.4 * SR)
    return bp(rng.standard_normal(n), 1500, 12000) * env(n, 0.45) * 0.5 * (1.3 if acento else 1.0)


SOM = {"hh": hihat, "sn": snare, "bd": kick, "hf": hhfoot, "ride": ride, "tom": tom, "ft": lambda a=False: tom(a) * 0.9,
       "crash": crash}


def sintetiza(eventos, total, contagem=None):
    """eventos: [(t, inst, acento)] -> array mono de `total` s, pico a −6 dBFS."""
    x = np.zeros(int(total * SR) + 2 * SR)
    if contagem:
        for b, t0 in enumerate(contagem):
            s = hihat(b == 0)
            i0 = int(t0 * SR)
            x[i0:i0 + len(s)] += s
    for t, inst, ac in eventos:
        s = SOM[inst](ac)
        i0 = int(t * SR)
        x[i0:i0 + len(s)] += s
    x = np.tanh(x[:int(total * SR)] * 0.9)
    x = sosfilt(butter(8, 15000, btype="low", fs=SR, output="sos"), x)
    return x / max(1e-6, np.abs(x).max()) * 0.5


def grava_wav(x, caminho):
    st = np.stack([x, x], 1)
    with wave.open(caminho, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype(np.int16).tobytes())


def fundo_padrao():
    """Gradiente escuro (azul-marinho) quando o projeto não tem fundo de identidade."""
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    r = np.sqrt((x - 0.5) ** 2 + (y - 0.4) ** 2) / 0.8
    c0, c1 = np.array([30, 41, 75]), np.array([10, 14, 28])
    img = (c0 * (1 - r)[..., None] + c1 * r[..., None]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGB").convert("RGBA")


def legenda_cores(insts, f):
    itens = [("R", "mão direita", COR["hh"]), ("L", "mão esquerda", COR["sn"])]
    if "bd" in insts:
        itens.append(("", "bumbo", COR["bd"]))
    if "hf" in insts:
        itens.append(("", "chimbal de pé", COR["hf"]))
    im = Image.new("RGBA", (420, 34 * len(itens) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (sig, nome, cor) in enumerate(itens):
        y = 4 + 34 * i
        d.ellipse([4, y + 4, 26, y + 26], fill=cor + (255,))
        if sig:
            d.text((15, y + 15), sig, font=f, fill=(255, 255, 255, 255), anchor="mm")
        d.text((40, y + 15), nome, font=f, fill=CINZA, anchor="lm")
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--partituras", default="partituras", help="pasta com <ID>_big.json/.png do partitura.py")
    ap.add_argument("--out", default="exemplos")
    ap.add_argument("--bpm", type=float, default=72)
    ap.add_argument("--voltas", type=int, default=2)
    ap.add_argument("--contagem", action="store_true", help="um compasso de contagem antes")
    ap.add_argument("--fundo", help="PNG 1920×1080 da identidade (padrão: gradiente escuro)")
    ap.add_argument("--rotulo", default="Exemplo tocado", help="texto pequeno acima do título")
    ap.add_argument("--titulo", help="título grande (padrão: o do padrão)")
    ap.add_argument("--fonte", help="TTF (padrão: Inter, DejaVu Sans Bold ou Arial Bold)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--so-audio", action="store_true", help="só regenera o .wav")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base_nome = f"{a.partituras}/{a.id}_big" if os.path.exists(f"{a.partituras}/{a.id}_big.json") else f"{a.partituras}/{a.id}"
    j = json.load(open(base_nome + ".json", encoding="utf-8"))
    fps = a.fps
    beats_bar, bt = j["ts"]
    q = 60.0 / a.bpm                       # segundos por semínima
    comp_q = beats_bar * 4 / bt            # semínimas por compasso
    dur_render = j["compassos"] * comp_q * q
    pre = comp_q * q if a.contagem else 0.6
    total = pre + a.voltas * dur_render + 1.0
    nfr = int(math.ceil(total * fps))
    total = nfr / fps

    eventos = []                           # (t, nota, acento)
    for v in range(a.voltas):
        for n in j["notas"]:
            eventos.append((pre + v * dur_render + n["t"] * q, n, bool(n.get("acento"))))
    eventos.sort(key=lambda e: e[0])
    contagem = [b * q * 4 / bt for b in range(beats_bar)] if a.contagem else None
    x = sintetiza([(t, n["inst"], ac) for t, n, ac in eventos], total, contagem)
    wav = f"{a.out}/{a.id}.wav"
    grava_wav(x, wav)
    meta = {"id": a.id, "dur": total, "bpm": a.bpm, "voltas": a.voltas, "pre": pre, "fps": fps,
            "eventos": [[round(t, 4), n["inst"]] for t, n, _ in eventos]}
    json.dump(meta, open(f"{a.out}/{a.id}.json", "w", encoding="utf-8"), indent=1)
    if a.so_audio:
        print(f"ok {wav} (só áudio, {total:.2f}s)")
        return

    card = Image.open(base_nome + ".png").convert("RGBA")
    fundo = Image.open(a.fundo).convert("RGBA").resize((W, H)) if a.fundo else fundo_padrao()
    f_rot, f_tit, f_sub = fonte(a.fonte or fonte_padrao("800"), 34), fonte(a.fonte or fonte_padrao("800"), 64), fonte(a.fonte or fonte_padrao("600"), 34)
    base = fundo.copy()
    d = ImageDraw.Draw(base)
    d.text((60, 70), (a.rotulo + f" · {int(a.bpm)} bpm").upper(), font=f_rot, fill=AMARELO)
    d.text((60, 118), a.titulo or j.get("titulo", a.id), font=f_tit, fill=BRANCO)
    if j.get("sub"):
        d.text((60, 200), j["sub"], font=f_sub, fill=CINZA)
    cx, cy = (W - card.width) // 2, 330
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([cx + 10, cy + 16, cx + card.width + 10, cy + card.height + 16], radius=22, fill=(0, 0, 0, 150))
    base.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(18)))
    base.alpha_composite(card, (cx, cy))
    leg = legenda_cores({n["inst"] for n in j["notas"]}, fonte(a.fonte or fonte_padrao("700"), 22))
    base.alpha_composite(leg, (W - 60 - leg.width, 70))
    fnum = fonte(a.fonte or fonte_padrao("800"), 72)
    nums_x = [W // 2 + (i - (beats_bar - 1) / 2) * 110 for i in range(beats_bar)]
    ny = cy + card.height + 60
    bx, fim = j["beats_px"], j["fim_px"]
    beat_s = q * 4 / bt                    # segundos por tempo do compasso

    bruto = f"{a.out}/_{a.id}_v.mp4"
    enc = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           *ffm.codec_video(crf=18, preset="veryfast"), "-r", str(fps), "-an", bruto]
    pr = subprocess.Popen(enc, stdin=subprocess.PIPE)
    for fi in range(nfr):
        t = fi / fps
        im = base.copy()
        d = ImageDraw.Draw(im, "RGBA")
        ativo = None
        if pre <= t < pre + a.voltas * dur_render:
            tr = (t - pre) % dur_render
            beat_f = tr / beat_s
            bi = min(int(beat_f), len(bx) - 1)
            frac = beat_f - bi
            x0 = bx[bi]
            x1 = bx[bi + 1] if bi + 1 < len(bx) else fim
            px = cx + x0 + (x1 - x0) * frac
            d.rectangle([px - 2, cy + j["y0"] - 6, px + 2, cy + j["y1"] + 6], fill=(37, 99, 235, 110))
            ativo = bi % beats_bar
        elif a.contagem and t < pre:
            ativo = int(t / beat_s) % beats_bar
        for t0, n, _ in eventos:
            dt = t - t0
            if -0.02 <= dt <= 0.28:
                k = max(0.0, 1 - dt / 0.28)
                r = 16 + 14 * k
                d.ellipse([cx + n["x"] - r, cy + n["y"] - r, cx + n["x"] + r, cy + n["y"] + r], fill=COR[n["inst"]] + (int(170 * k),))
        for i, xn in enumerate(nums_x):
            d.text((xn, ny), str(i + 1), font=fnum, fill=AMARELO if ativo == i else (148, 163, 184, 120), anchor="mt")
        pr.stdin.write(im.convert("RGB").tobytes())
    pr.stdin.close()
    pr.wait()
    if pr.returncode:
        sys.exit("ffmpeg falhou ao codificar o vídeo")
    mp4 = f"{a.out}/{a.id}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", bruto, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    *audio.AAC, "-movflags", "+faststart", mp4], check=True)
    os.remove(bruto)
    print(f"ok {mp4} + {wav}  {total:.2f}s  ({len(eventos)} notas, {nfr} quadros)")


if __name__ == "__main__":
    main()
