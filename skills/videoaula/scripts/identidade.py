#!/usr/bin/env python3
"""Gera a identidade visual de uma videoaula a partir de aula.json: fundo (gradiente + grade de pontos + vinheta),
chips de capítulo, máscara e anel do círculo do locutor, lower third e, para o layout de código, a base com sombra
e a "tampa" com buraco arredondado por grupo de recorte (gera identidade/l3_geo.json para o montador).

Uso: uv run --with pillow --with numpy python identidade.py aula.json
Com marca/marca.json no projeto (ADR-17), cores e fonte padrão vêm da marca; `cores` e `fonte_dir` do aula.json vencem.
Campos usados: cores {fundo_centro, fundo_borda, acento, destaque, texto, texto2}, fonte_dir (TTFs Inter-400/600/700/800),
capitulos[].titulo, autor, subtitulo_autor, codigo_grupos[].{grupo, crop:[x0,y0,x1,y1]}, identidade (pasta de saída).
"""
import json, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import marca_aula  # noqa: E402

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
MARCA = marca_aula.carregar(cfg)          # resolvida a partir da raiz do projeto, antes do chdir
os.chdir(os.path.dirname(os.path.abspath(sys.argv[1])))
OUT = cfg.get("identidade", "identidade"); os.makedirs(OUT, exist_ok=True)
C = {**marca_aula.cores(MARCA, {"fundo_centro": "#131C33", "fundo_borda": "#0B1220", "acento": "#4B8BBE",
                                 "destaque": "#FFD43B", "texto": "#F1F5F9", "texto2": "#94A3B8"}),
     **cfg.get("cores", {})}
def rgb(h):
    return tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


AC, DE, TX, T2 = rgb(C["acento"]), rgb(C["destaque"]), rgb(C["texto"]), rgb(C["texto2"])
FD = os.path.expanduser(cfg.get("fonte_dir", "~/.local/share/fonts/inter"))


def font(w, size):
    da_marca = None if "fonte_dir" in cfg else marca_aula.fonte_arquivo(MARCA, w)
    for cand in (da_marca, f"{FD}/Inter-{w}.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if cand and os.path.exists(cand): return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


# --- fundo
y, x = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((x - W * 0.5) / W) ** 2 + ((y - H * 0.45) / H) ** 2); t = np.clip(d / 0.75, 0, 1)
c0, c1 = np.array(rgb(C["fundo_centro"]), np.float32), np.array(rgb(C["fundo_borda"]), np.float32)
img = c0 * (1 - t[..., None]) + c1 * t[..., None]
img += np.exp(-(((x - W * 0.15) / W) ** 2 + ((y - H * 0.1) / H) ** 2) / 0.03)[..., None] * np.array(AC, np.float32) * 0.10
fundo = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")
dots = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(dots)
for yy in range(40, H, 48):
    for xx in range(40, W, 48): dr.ellipse((xx - 1.5, yy - 1.5, xx + 1.5, yy + 1.5), fill=(255, 255, 255, 16))
fundo = Image.alpha_composite(fundo, dots)
arr = np.asarray(fundo).astype(np.float32); arr[..., :3] *= (1 - np.clip((d - 0.35) / 0.45, 0, 1) * 0.35)[..., None]
fundo = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)); fundo.convert("RGB").save(f"{OUT}/fundo.png")


def shadow_of(mask, blur, off, alpha):
    sh = Image.new("RGBA", mask.size, (0, 0, 0, 0)); sh.putalpha(mask.point(lambda v: v * alpha // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(blur)); out = Image.new("RGBA", mask.size, (0, 0, 0, 0)); out.alpha_composite(sh, dest=off); return out


# --- chips
for cap in cfg["capitulos"]:
    n, nome = cap["n"], cap["titulo"]; f = font("700", 30); num = f"{n:02d}"
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay); x0, y0 = 72, 56
    wn, wt = dd.textlength(num, font=f), dd.textlength(nome, font=f)
    dd.rounded_rectangle((x0, y0, x0 + wn + wt + 72, y0 + 58), radius=14, fill=(255, 255, 255, 22), outline=AC + (220,), width=2)
    dd.text((x0 + 22, y0 + 13), num, font=f, fill=DE); dd.text((x0 + 22 + wn + 22, y0 + 13), nome, font=f, fill=TX)
    lay.save(f"{OUT}/chip_{n}.png")

# --- círculo (l2: 420 px no canto inferior direito; l3: 444 px na coluna da direita)
for tag, D in [("l2", 420), ("l3", 444)]:
    m = Image.new("L", (D, D), 0); ImageDraw.Draw(m).ellipse((0, 0, D - 1, D - 1), fill=255); m.save(f"{OUT}/circmask_{tag}.png")
    pad = 40; S = D + 2 * pad
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0)); ImageDraw.Draw(ring).ellipse((pad - 7, pad - 7, S - pad + 7, S - pad + 7), fill=AC + (255,))
    hole = Image.new("L", (S, S), 255); ImageDraw.Draw(hole).ellipse((pad, pad, S - pad, S - pad), fill=0)
    ring_only = ring.copy(); ring_only.putalpha(Image.fromarray(np.minimum(np.asarray(ring.split()[3]), np.asarray(hole))))
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0)); base.alpha_composite(shadow_of(ring.split()[3], 24, (0, 14), 160)); base.alpha_composite(ring_only)
    base.save(f"{OUT}/ring_{tag}.png")

# --- lower third
if cfg.get("autor"):
    f1, f2 = font("800", 46), font("600", 28); name, sub = cfg["autor"], cfg.get("subtitulo_autor", "")
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay); x0, y0 = 96, 880
    w = max(dd.textlength(name, font=f1), dd.textlength(sub, font=f2)) + 64
    dd.rounded_rectangle((x0, y0, x0 + w, y0 + 120), radius=16, fill=(11, 18, 32, 215)); dd.rounded_rectangle((x0, y0, x0 + 10, y0 + 120), radius=5, fill=AC + (255,))
    dd.text((x0 + 36, y0 + 18), name, font=f1, fill=TX); dd.text((x0 + 36, y0 + 76), sub, font=f2, fill=T2)
    lay.save(f"{OUT}/lower_third.png")

# --- layout de código: base (fundo + sombra) e tampa (fundo com buraco arredondado) por grupo
geo = {}
for g in cfg.get("codigo_grupos", []):
    x0, y0, x1, y1 = g["crop"]; cw, ch = x1 - x0, y1 - y0
    sc = min(1036 / ch, 1.25); pw, ph = int(cw * sc), int(ch * sc); px, py = 64, (H - ph) // 2
    pm = Image.new("L", (W, H), 0); ImageDraw.Draw(pm).rounded_rectangle((px, py, px + pw, py + ph), radius=22, fill=255)
    base = fundo.copy(); base.alpha_composite(shadow_of(pm, 30, (0, 20), 150)); base.convert("RGB").save(f"{OUT}/l3_base_{g['grupo']}.png")
    cover = np.asarray(fundo).copy(); cover[..., 3] = 255 - np.asarray(pm); cover = Image.fromarray(cover)
    ImageDraw.Draw(cover).rounded_rectangle((px, py, px + pw, py + ph), radius=22, outline=(255, 255, 255, 40), width=2)
    cover.save(f"{OUT}/l3_cover_{g['grupo']}.png")
    geo[g["grupo"]] = {"crop": [cw, ch, x0, y0], "scale": [pw, ph], "pos": [px, py], "right_col_x": px + pw + 72}
json.dump(geo, open(f"{OUT}/l3_geo.json", "w"), indent=1)
print("ok ->", OUT, "| grupos de código:", list(geo))
