#!/usr/bin/env python3
"""Checklist com moldura: cada item aparece no instante em que a palavra-gatilho é falada.

Entrada: transcrição com palavras (transcribe.py) e um JSON de itens:
[
  {"text": "Backup diário", "trigger": "backup"},
  {"text": "Monitoramento 24x7", "trigger": "monitor"},
  {"text": "Rollback em 1 clique", "at": 12.4}          # ou tempo explícito
]
O gatilho é procurado nas palavras da transcrição (prefixo, sem acento/caixa), a partir do
item anterior. Itens sem gatilho encontrado são listados no stderr para o Claude ajustar.

Saída: <itens>.ass (e --burn SAIDA.mp4). Painel à esquerda/direita com moldura, itens com ✓
que entram um a um e ficam até --end (padrão: fim do vídeo).

Uso: checklist_ass.py VIDEO itens.json VIDEO.transcript.json [--side left|right] [--start 0] [--end FIM]
     [--font "DejaVu Sans"] [--accent "#FF6B35"] [--burn SAIDA.mp4]
"""
import argparse
import json
import subprocess
import sys
import unicodedata


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,duration:stream_side_data=rotation:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = 0
    for sd in st.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    dur = float(j.get("format", {}).get("duration") or st.get("duration") or 0)
    return ((h, w) if abs(rot) % 180 == 90 else (w, h)) + (dur,)


def t(s):
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{sec:02}.{cs:02}"


def color(hexrgb):
    hexrgb = hexrgb.lstrip("#")
    return f"&H00{hexrgb[4:6]}{hexrgb[2:4]}{hexrgb[0:2]}&".upper()


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def ffesc(p):
    return (p.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
             .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("itens"); ap.add_argument("transcript")
    ap.add_argument("--side", default="left", choices=["left", "right"])
    ap.add_argument("--start", type=float, default=None, help="quando a moldura aparece (padrão: 0,4 s antes do 1º item)")
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--font", default="DejaVu Sans")
    ap.add_argument("--accent", default="#FF6B35")
    ap.add_argument("--burn", default=None)
    a = ap.parse_args()

    W, H, dur = probe(a.video)
    items = json.load(open(a.itens, encoding="utf-8"))
    tr = json.load(open(a.transcript, encoding="utf-8"))
    words = [w for s in tr.get("segments", []) for w in s.get("words", [])]
    if not words:
        words = [{"start": s["start"], "end": s["end"], "word": s["text"]} for s in tr.get("segments", [])]

    cursor = 0.0
    missing = []
    for it in items:
        if "at" in it:
            it["t"] = float(it["at"]); cursor = it["t"]; continue
        trig = fold(it.get("trigger", it["text"]).split()[0])
        hit = next((w for w in words if w["start"] >= cursor and fold(w["word"].strip(" ,.!?")).startswith(trig)), None)
        if hit:
            it["t"] = hit["start"]; cursor = hit["start"]
        else:
            it["t"] = None; missing.append(it["text"])
    timed = [it for it in items if it.get("t") is not None]
    if not timed:
        sys.exit("nenhum item encontrado na transcrição; informe gatilhos melhores ou 'at'")
    if missing:
        sys.stderr.write("itens sem gatilho encontrado (ficaram de fora): " + "; ".join(missing) + "\n")

    start = a.start if a.start is not None else max(0.0, timed[0]["t"] - 0.4)
    end = a.end if a.end is not None else (dur or timed[-1]["t"] + 5)
    fs = int(H * 0.034)
    pad = int(W * 0.04)
    box_w = int(W * 0.62)
    line_h = int(fs * 1.7)
    box_h = pad + line_h * len(timed) + pad // 2
    top = int(H * 0.16)
    x0 = pad if a.side == "left" else W - pad - box_w
    acc = color(a.accent)

    ev = []
    # moldura (fundo translúcido + borda de acento), desenhada com \p1
    rect = f"m 0 0 l {box_w} 0 l {box_w} {box_h} l 0 {box_h}"
    ev.append(f"Dialogue: 0,{t(start)},{t(end)},Box,,0,0,0,,{{\\pos({x0},{top})\\fad(200,200)\\1c&H000000&\\1a&H70&\\bord3\\3c{acc}\\shad0\\p1}}{rect}{{\\p0}}")
    for i, it in enumerate(timed):
        y = top + pad // 2 + line_h * i + line_h // 2
        x = x0 + pad
        ev.append(f"Dialogue: 1,{t(it['t'])},{t(end)},Item,,0,0,0,,{{\\an4\\pos({x},{y})\\fs{fs}\\1c{acc}\\fad(120,0)\\fscx60\\fscy60\\t(0,160,\\fscx100\\fscy100)}}✓")
        ev.append(f"Dialogue: 1,{t(it['t'])},{t(end)},Item,,0,0,0,,{{\\an4\\move({x + fs + 40},{y},{x + fs + 16},{y},0,220)\\fs{fs}\\fad(160,0)}}{it['text']}")

    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,{a.font},20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Item,{a.font},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,4,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n"
    out_ass = a.itens.rsplit(".", 1)[0] + ".ass"
    open(out_ass, "w", encoding="utf-8").write(ass)
    print(f"ass -> {out_ass} ({len(timed)} itens: " + ", ".join(f"{it['t']:.1f}s" for it in timed) + ")")
    if a.burn:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", a.video, "-vf",
                        f"ass=filename='{ffesc(out_ass)}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-c:a", "copy", a.burn], check=True)
        print(f"ok -> {a.burn}")


if __name__ == "__main__":
    main()
