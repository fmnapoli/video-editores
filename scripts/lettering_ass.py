#!/usr/bin/env python3
"""Textos na tela via ASS (libass) — não depende de drawtext, igual ao video-docs.

Gera um .ass a partir de um JSON e, com --burn, queima no vídeo.

JSON (lista):
[
  {"text": "TÍTULO", "start": 0.5, "end": 3.0, "style": "titulo", "anim": "pop"},
  {"text": "Fabrizio\\NPlatform Engineer", "start": 4, "end": 8, "style": "lower", "anim": "slide"},
  {"text": "IMPORTANTE", "start": 9, "end": 11, "style": "destaque", "anim": "fade",
   "pos": [0.5, 0.25], "color": "#FFD54F", "size": 0.09}
]
style: titulo | lower | destaque     anim: fade | pop | slide | none
pos: centro em fração da tela (x, y). size: altura da fonte em fração da altura do vídeo.
"\\N" quebra linha.

Uso: lettering_ass.py VIDEO textos.json [--font "DejaVu Sans"] [--burn SAIDA.mp4]
"""
import argparse, json, subprocess, sys


def probe(path):
    """Largura e altura já considerando o metadado de rotação (vídeo de celular)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    st = json.loads(out)["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    return (h, w) if abs(rot) % 180 == 90 else (w, h)


def ffesc(p):
    """Escapa um caminho para uso dentro de opções de filtro do ffmpeg."""
    return (p.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
             .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]"))


def t(s):
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{sec:02}.{cs:02}"


def color(hexrgb):
    hexrgb = hexrgb.lstrip("#")
    r, g, b = hexrgb[0:2], hexrgb[2:4], hexrgb[4:6]
    return f"&H00{b}{g}{r}&".upper()


PRESETS = {
    #           pos(x,y)      size  color      align
    "titulo":   ((0.5, 0.18), 0.062, "#FFFFFF", 5),
    "destaque": ((0.5, 0.30), 0.065, "#FFD54F", 5),
    "lower":    ((0.05, 0.84), 0.040, "#FFFFFF", 4),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("textos")
    ap.add_argument("--font", default="DejaVu Sans")
    ap.add_argument("--burn", default=None)
    a = ap.parse_args()

    W, H = probe(a.video)
    items = json.load(open(a.textos, encoding="utf-8"))
    lines = []
    for it in items:
        pos, size, col, align = PRESETS.get(it.get("style", "titulo"), PRESETS["titulo"])
        x, y = it.get("pos", pos)
        px = int(H * it.get("size", size))
        c = color(it.get("color", col))
        X, Y = int(W * x), int(H * y)
        an = it.get("anim", "fade")
        tags = [f"\\an{align}", f"\\fs{px}", f"\\1c{c}", "\\b1"]
        if it.get("style") != "lower":
            tags += ["\\bord" + str(max(2, px // 14)), "\\3c&H000000&"]
        if an == "slide":
            tags.append(f"\\move({-W // 3},{Y},{X},{Y},0,300)")
            tags.append("\\fad(0,200)")
        else:
            tags.append(f"\\pos({X},{Y})")
            if an == "fade":
                tags.append("\\fad(200,200)")
            elif an == "pop":
                tags.append("\\fscx40\\fscy40\\t(0,180,\\fscx112\\fscy112)\\t(180,280,\\fscx100\\fscy100)\\fad(0,200)")
        lines.append(f"Dialogue: 0,{t(it['start'])},{t(it['end'])},{'Lower' if it.get('style') == 'lower' else 'Base'},,0,0,0,,{{{''.join(tags)}}}{it['text']}")

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{a.font},48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,5,10,10,10,1
Style: Lower,{a.font},48,&H00FFFFFF,&H00FFFFFF,&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,12,0,4,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(lines) + "\n"
    out_ass = a.textos.rsplit(".", 1)[0] + ".ass"
    open(out_ass, "w", encoding="utf-8").write(ass)
    print(f"ass -> {out_ass}")

    if a.burn:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.video,
                        "-vf", f"ass=filename='{ffesc(out_ass)}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", a.burn], check=True)
        print(f"ok -> {a.burn}")


if __name__ == "__main__":
    sys.exit(main())
