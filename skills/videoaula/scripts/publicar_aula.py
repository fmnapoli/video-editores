#!/usr/bin/env python3
"""Pacote de publicação da videoaula: capítulos do YouTube (tempos finais), descrição e thumbnail.

Uso: uv run --with pillow --with numpy python publicar_aula.py aula.json [--saida saida/<slug>] [--thumb-t 5.0]
     [--sem-thumb] [--descricao "texto livre do autor"]
Saídas: <saida>.youtube.md (título sugerido, capítulos "mm:ss Título", descrição, hashtags) e <saida>_thumb.jpg (1280x720).
A thumbnail usa o recorte do locutor já feito pelo matte (mattes/talk_00000_alpha.mp4 + o vídeo cortado) no instante
--thumb-t (tempo do corte), o fundo da identidade, o kicker e o título em duas linhas. Só o .md precisa de nada além da stdlib.
"""
import argparse, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from montar_aula import Aula  # noqa: E402


def mmss(t):
    t = int(round(t)); h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def thumbnail(cfg, aula, t, out):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = 1280, 720
    ident = cfg.get("identidade", "identidade"); mattes = cfg.get("mattes", "mattes")
    bg = Image.open(f"{ident}/fundo.png").convert("RGBA").resize((W, H), Image.LANCZOS)
    # frame do locutor + máscara no instante t (procura o matte que contém t)
    loc = cfg.get("modos", {}).get("locutor", "locutor")
    cena = next((c for c in aula.cenas if c["kind"] == loc and c["cut_start"] <= t < c["cut_end"]), None)
    if cena is None:
        cena = next(c for c in aula.cenas if c["kind"] == loc)
        t = cena["cut_start"] + min(5.0, cena["cut_len"] / 2)
    base = f"{mattes}/talk_{int(cena['cut_start']):05d}"
    def grab(src, ss, pix):
        return subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-i", src, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", pix, "-s", "1920x1080", "-"],
                              capture_output=True, check=True).stdout
    rgb = np.frombuffer(grab(cfg["corte"], t, "rgb24"), np.uint8).reshape(1080, 1920, 3)
    al = np.frombuffer(grab(base + "_alpha.mp4", t - cena["cut_start"], "gray"), np.uint8).reshape(1080, 1920)
    person = Image.fromarray(np.dstack([rgb, al]), "RGBA")
    # pessoa ocupa a metade direita, um pouco maior
    bbox = Image.fromarray(al).point(lambda v: 255 if v > 40 else 0).getbbox() or (480, 0, 1440, 1080)
    crop = person.crop((max(0, bbox[0] - 60), 0, min(1920, bbox[2] + 60), 1080))
    sc = (H * 1.05) / crop.height; crop = crop.resize((int(crop.width * sc), int(crop.height * sc)), Image.LANCZOS)
    sh = Image.new("RGBA", crop.size, (0, 0, 0, 0)); sh.putalpha(crop.split()[3].point(lambda v: v * 170 // 255)); sh = sh.filter(ImageFilter.GaussianBlur(24))
    px = W - crop.width + 40; py = H - crop.height + 10
    bg.alpha_composite(sh, dest=(px, py + 16)); bg.alpha_composite(crop, dest=(px, py))
    # texto à esquerda
    C = {"acento": "#4B8BBE", "destaque": "#FFD43B", "texto": "#F1F5F9", **cfg.get("cores", {})}
    col = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))  # noqa: E731
    FD = os.path.expanduser(cfg.get("fonte_dir", "~/.local/share/fonts/inter"))
    def font(w, size):
        for cand in (f"{FD}/Inter-{w}.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.exists(cand): return ImageFont.truetype(cand, size)
        return ImageFont.load_default()
    d = ImageDraw.Draw(bg)
    if "\n" in cfg["titulo"]:
        linhas = cfg["titulo"].split("\n")
    else:  # quebra em duas linhas de largura parecida
        ws = cfg["titulo"].split(); best = None
        for k in range(1, len(ws)):
            l1, l2 = " ".join(ws[:k]), " ".join(ws[k:]); score = abs(len(l1) - len(l2))
            if best is None or score < best[0]: best = (score, [l1, l2])
        linhas = best[1] if best else [cfg["titulo"]]
    d.text((70, 150), cfg.get("kicker", ""), font=font("700", 40), fill=col(C["destaque"]))
    max_w = px - 66 - 30 if px > 500 else W * 0.55   # não invade a pessoa
    size = 118
    while size > 56 and max(d.textlength(ln, font=font("800", size)) for ln in linhas) > max_w: size -= 4
    d.text((66, 205), linhas[0], font=font("800", size), fill=col(C["texto"]))
    if len(linhas) > 1: d.text((66, 205 + size + 10), linhas[1], font=font("800", size), fill=col(C["acento"]))
    caps = [c["titulo"] for c in cfg["capitulos"]][:4]
    y = 205 + (size + 10) * len(linhas) + 50
    for cap in caps:
        d.rounded_rectangle((70, y + 8, 94, y + 32), radius=5, fill=col(C["acento"])); d.text((110, y), cap, font=font("600", 30), fill=col(C["texto"])); y += 46
    bg.convert("RGB").save(out, quality=92)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aula"); ap.add_argument("--saida", default=None); ap.add_argument("--thumb-t", type=float, default=5.0)
    ap.add_argument("--sem-thumb", action="store_true"); ap.add_argument("--descricao", default="")
    a = ap.parse_args()
    aula = Aula(a.aula); cfg = aula.cfg
    slug = cfg.get("slug", "aula"); saida = a.saida or f"saida/{slug}"
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    caps = [(0.0, "Abertura")] + [(aula.map_time(c["inicio"]), c["titulo"]) for c in cfg["capitulos"]]
    # o YouTube exige o primeiro capítulo em 0:00 e capítulos com >= 10 s
    linhas = [f"{mmss(t)} {nome}" for t, nome in caps]
    titulo = f"{cfg.get('kicker', '').title()} · {cfg['titulo']}".strip(" ·")
    md = [f"# {titulo}", "", "## Capítulos", *linhas, "", "## Descrição",
          a.descricao or f"{cfg['titulo']}: " + ", ".join(c["titulo"].lower() for c in cfg["capitulos"]) + ".",
          "", "Capítulos:", *linhas, "", "## Hashtags", "#" + " #".join(w.lower() for w in cfg["titulo"].replace("do ", "").split()[:3] if len(w) > 2) + " #programacao #aula"]
    open(saida + ".youtube.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("ok ->", saida + ".youtube.md")
    if not a.sem_thumb:
        print("ok ->", thumbnail(cfg, aula, a.thumb_t, saida + "_thumb.jpg"))


if __name__ == "__main__":
    main()
