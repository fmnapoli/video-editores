#!/usr/bin/env python3
"""video-docs builder v2: spec JSON -> <slug>.mp4 + <slug>.srt (+ .ass de cartela/destaques).

Run:  uv run --with edge-tts --with pillow python build.py spec.json
Needs ffmpeg/ffprobe (with libass) in PATH and DejaVu Sans Bold installed.

Spec:
{
  "slug": "...", "title": "...", "subtitle": "Produto X",
  "out_dir": "/abs/out", "work_dir": "/abs/work",
  "sources": {"a": "/abs/raw.mp4"},
  "scenes": [
    {"src": "a",
     "clips": [[start, end, speed], ...],      # seconds of the raw file; speed optional (1.0)
     "fit": "auto",                             # auto: speeds up (cap 2.2x) so footage ~ narration; "none" keeps speeds
     "chip": "Colar a chave",                   # pill at the top-left for the whole scene ("n/N · chip")
     "tts": "texto falado",                   # opcional: sem ele, fala-se a legenda; o glossário de
                                                # pronúncia ("glossary" do spec; glossario-ingles.json só em voz não
                                                # multilíngue) é aplicado aqui, a legenda continua com a grafia normal
     "legend": ["bloco\nde legenda", ...],
     "callouts": [
        {"at": [src_a, src_b],                  # raw-file seconds (mapped through the clips)
         "box": [x, y, w, h],                   # rounded highlight
         "focus": true,                         # dims everything outside the box
         "balloon": "texto", "balloon_at": [x, y],   # auto-placed near the box when omitted
         "arrow": [x1, y1, x2, y2]}             # explicit arrow; a balloon far from its box gets one automatically
     ]}
  ]
}
Scene duration = max(footage, narration + lead + tail); shortfall becomes a freeze of the last frame.
"""
import asyncio, hashlib, json, math, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronuncia  # noqa: E402

W, H, FPS = 1280, 720, 30
TITLE_DUR = 3.2
TTS_LEAD, TTS_TAIL, TAIL_HOLD = 0.25, 0.35, 0.8
FIT_CAP, FIT_SLACK, SLOW_MIN = 2.2, 1.2, 0.7
VOICE = "pt-BR-ThalitaMultilingualNeural"  # pronuncia termos em inglês nativamente
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NAME = "DejaVu Sans"
# colours (ASS &HAABBGGRR&)
ACCENT = "&H00356BFF&"        # laranja FF6B35
ACCENT_BGR = "356BFF"
INK = "&H142A170F&"           # navy 0F172A, 92% opaco
INK_SOFT = "&H402A170F&"
DIM = "&H8C000000&"           # preto 45% opaco
LEGEND_STYLE = (f"FontName={FONT_NAME},FontSize=11,Bold=1,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,BackColour=&H78000000,BorderStyle=3,Outline=2,"
                "Shadow=0,MarginV=18,Alignment=2")
SAFE_TOP, SAFE_BOTTOM = 104, 630   # browser chrome / legend zone

try:
    from PIL import ImageFont
    _fonts = {}

    def text_w(s, size):
        f = _fonts.setdefault(size, ImageFont.truetype(FONT, size))
        return f.getlength(s)
except Exception:  # pragma: no cover
    def text_w(s, size):
        return len(s) * size * 0.6


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"command failed: {cmd[0]}")
    return r.stdout


def ffdur(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


# ---------------- TTS ----------------
async def _synth(text, voice, mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
    return words


def tts(text, voice, work):
    h = hashlib.sha1((voice + "|" + text).encode()).hexdigest()[:12]
    mp3, js = os.path.join(work, f"tts-{h}.mp3"), os.path.join(work, f"tts-{h}.json")
    if not (os.path.exists(mp3) and os.path.exists(js)):
        words = asyncio.run(_synth(text, voice, mp3))
        json.dump({"words": words, "dur": ffdur(mp3)}, open(js, "w"))
    d = json.load(open(js))
    return mp3, d["words"], d["dur"]


# ---------------- legend alignment ----------------
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentence_spans(text):
    spans, pos = [], 0
    for s in SENT_SPLIT.split(text):
        i = text.find(s, pos)
        spans.append((i, i + len(s)))
        pos = i + len(s)
    return spans


def map_display_to_tts(disp, ttstext):
    ds, ts = sentence_spans(disp), sentence_spans(ttstext)
    if len(ds) != len(ts):
        ds, ts = [(0, len(disp))], [(0, len(ttstext))]

    def f(p):
        for (a, b), (c, d) in zip(ds, ts):
            if p <= b:
                frac = 0 if b == a else (p - a) / (b - a)
                return c + frac * (d - c)
        return len(ttstext)
    return f


def word_anchors(ttstext, words):
    out, cur = [], 0
    for t0, d, w in words:
        i = ttstext.find(w, cur)
        if i < 0:
            i = cur
        out.append((i, t0, t0 + d))
        cur = i + len(w)
    return out


def legend_cues(blocks, ttstext, words, t_offset):
    disp = " ".join(b.replace("\n", " ") for b in blocks)
    f = map_display_to_tts(disp, ttstext)
    anchors = word_anchors(ttstext, words)
    cues, pos = [], 0
    for b in blocks:
        flat = b.replace("\n", " ")
        a = disp.find(flat, pos); z = a + len(flat); pos = z
        ta, tz = f(a), f(z)
        starts = [s for p, s, e in anchors if p >= ta - 1]
        ends = [e for p, s, e in anchors if p < tz + 1]
        st = starts[0] if starts else anchors[-1][1]
        en = ends[-1] if ends else anchors[-1][2]
        cues.append([t_offset + st - 0.05, t_offset + en + 0.25, b])
    for i, c in enumerate(cues):
        c[1] = max(c[1], c[0] + 0.9)
        if i + 1 < len(cues):
            c[1] = min(c[1], cues[i + 1][0] - 0.04)
    return cues


def srt_ts(t):
    t = max(t, 0); h, m = divmod(int(t), 3600); m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int(round((t - int(t)) * 1000)):03d}"


def ass_ts(t):
    t = max(t, 0); h, m = divmod(int(t), 3600); m, s = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}.{int((t - int(t)) * 100):02d}"


# ---------------- ASS drawing ----------------
ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shape,{FONT_NAME},20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Balloon,{FONT_NAME},21,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Chip,{FONT_NAME},17,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Title,{FONT_NAME},48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Sub,{FONT_NAME},26,&H00E2E8F0,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ev(layer, s, e, style, text):
    return f"Dialogue: {layer},{ass_ts(s)},{ass_ts(e)},{style},,0,0,0,,{text}\n"


def rrect(x, y, w, h, r):
    """Rounded-rect drawing commands, absolute coordinates."""
    r = min(r, w / 2, h / 2)
    return (f"m {x+r:.0f} {y:.0f} l {x+w-r:.0f} {y:.0f} b {x+w:.0f} {y:.0f} {x+w:.0f} {y:.0f} {x+w:.0f} {y+r:.0f} "
            f"l {x+w:.0f} {y+h-r:.0f} b {x+w:.0f} {y+h:.0f} {x+w:.0f} {y+h:.0f} {x+w-r:.0f} {y+h:.0f} "
            f"l {x+r:.0f} {y+h:.0f} b {x:.0f} {y+h:.0f} {x:.0f} {y+h:.0f} {x:.0f} {y+h-r:.0f} "
            f"l {x:.0f} {y+r:.0f} b {x:.0f} {y:.0f} {x:.0f} {y:.0f} {x+r:.0f} {y:.0f}")


def rect(x, y, w, h):
    return f"m {x:.0f} {y:.0f} l {x+w:.0f} {y:.0f} l {x+w:.0f} {y+h:.0f} l {x:.0f} {y+h:.0f}"


def box_ev(s, e, x, y, w, h):
    cx, cy = x + w / 2, y + h / 2
    tags = (f"{{\\pos(0,0)\\org({cx:.0f},{cy:.0f})\\fad(120,150)\\fscx94\\fscy94\\t(0,220,\\fscx100\\fscy100)"
            f"\\bord3\\1a&HFF&\\3c{ACCENT}\\shad0\\p1}}")
    return ev(2, s, e, "Shape", tags + rrect(x - 4, y - 4, w + 8, h + 8, 8) + "{\\p0}")


def dim_ev(s, e, x, y, w, h):
    x0, y0, x1, y1 = x - 4, y - 4, x + w + 4, y + h + 4
    parts = [rect(0, 0, W, y0), rect(0, y1, W, H - y1), rect(0, y0, x0, y1 - y0), rect(x1, y0, W - x1, y1 - y0)]
    return ev(0, s, e, "Shape", f"{{\\pos(0,0)\\fad(200,200)\\1c&H000000&\\1a&H8C&\\bord0\\shad0\\p1}}" + " ".join(parts) + "{\\p0}")


def arrow_shape(x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L; px, py = -uy, ux
    hw, head, hh = 3.5, 20, 10
    bx, by = x2 - ux * head, y2 - uy * head
    pts = [(x1 + px * hw, y1 + py * hw), (bx + px * hw, by + py * hw), (bx + px * hh, by + py * hh), (x2, y2),
           (bx - px * hh, by - py * hh), (bx - px * hw, by - py * hw), (x1 - px * hw, y1 - py * hw)]
    return "m " + " l ".join(f"{p[0]:.0f} {p[1]:.0f}" for p in pts), (ux, uy)


def arrow_ev(s, e, x1, y1, x2, y2):
    shape, (ux, uy) = arrow_shape(x1, y1, x2, y2)
    mx, my = -ux * 14, -uy * 14
    return ev(3, s, e, "Shape",
              f"{{\\move({mx:.0f},{my:.0f},0,0,0,260)\\fad(140,140)\\bord2\\1c{ACCENT}\\3c{INK}\\shad0\\p1}}{shape}{{\\p0}}")


def balloon_evs(s, e, text, bx=None, by=None, bw=None, bh=None, at=None):
    """Rounded dark balloon with text; tail to the box when close, arrow when far."""
    size = 21
    tw = text_w(text, size)
    w, h = tw + 32, 40
    if at:
        x, y = at
    else:  # auto: above the box, else below; clamp horizontally
        x = bx
        y = by - h - 16
        if y < SAFE_TOP:
            y = by + bh + 16
        if y + h > SAFE_BOTTOM:
            y = max(SAFE_TOP, by - h - 16)
    x = max(8, min(x, W - w - 8))
    out = []
    shape = rrect(x, y, w, h, 11)
    tail = ""
    arrow = ""
    if bx is not None:
        # nearest points between balloon and box
        tx = max(bx + 14, min(x + w / 2, bx + bw - 14))
        if y + h <= by:          # balloon above box
            gap = by - (y + h)
            base_y, tip_y = y + h - 1, by - 3
        elif y >= by + bh:        # below
            gap = y - (by + bh)
            base_y, tip_y = y + 1, by + bh + 3
        else:
            gap = 999
        if gap <= 70:
            bxc = max(x + 18, min(tx, x + w - 18))
            tail = f" m {bxc-10:.0f} {base_y:.0f} l {bxc+10:.0f} {base_y:.0f} l {tx:.0f} {tip_y:.0f}"
        else:
            # arrow from balloon edge nearest to the box edge nearest
            cx, cy = x + w / 2, y + h / 2
            gx, gy = bx + bw / 2, by + bh / 2
            # start on balloon boundary, end on box boundary (axis-aligned approx)
            sx = min(max(gx, x), x + w); sy = min(max(gy, y), y + h)
            ex = min(max(cx, bx), bx + bw); ey = min(max(cy, by), by + bh)
            if abs(sx - ex) < 1 and abs(sy - ey) < 1:
                ex, ey = gx, gy
            arrow = arrow_ev(s, e, sx, sy, ex, ey)
    out.append(ev(3, s, e, "Shape",
                  f"{{\\move({x:.0f},{y+14:.0f},{x:.0f},{y:.0f},0,240)\\pos(0,0)\\fad(140,140)\\bord0\\shad3\\4c&H60000000&\\1c{INK}\\p1}}"
                  .replace(f"\\move({x:.0f},{y+14:.0f},{x:.0f},{y:.0f},0,240)\\pos(0,0)", f"\\move(0,14,0,0,0,240)")
                  + shape + tail + "{\\p0}"))
    # accent bar on the left of the balloon
    out.append(ev(3, s, e, "Shape", f"{{\\move(0,14,0,0,0,240)\\fad(140,140)\\bord0\\shad0\\1c{ACCENT}\\p1}}" + rrect(x + 10, y + 11, 5, h - 22, 2) + "{\\p0}"))
    out.append(ev(4, s, e, "Balloon", f"{{\\move({x+w/2+8:.0f},{y+h/2+14:.0f},{x+w/2+8:.0f},{y+h/2:.0f},0,240)\\fad(140,140)}}{text}"))
    if arrow:
        out.append(arrow)
    return out


def chip_evs(s, e, text):
    size = 17
    tw = text_w(text, size)
    x, y, h = 16, 110, 30
    w = tw + 44
    out = [ev(3, s, e, "Shape", f"{{\\move(-20,0,0,0,0,260)\\fad(180,220)\\bord0\\shad2\\4c&H60000000&\\1c{INK}\\p1}}" + rrect(x, y, w, h, 15) + "{\\p0}"),
           ev(3, s, e, "Shape", f"{{\\move(-20,0,0,0,0,260)\\fad(180,220)\\bord0\\shad0\\1c{ACCENT}\\p1}}" + rrect(x + 12, y + 10, 10, 10, 5) + "{\\p0}"),
           ev(4, s, e, "Chip", f"{{\\move({x+30-20:.0f},{y+h/2:.0f},{x+30:.0f},{y+h/2:.0f},0,260)\\fad(180,220)}}{text}")]
    return out


def title_evs(title, subtitle):
    out = [ev(4, 0, TITLE_DUR, "Title", f"{{\\move(120,312,160,312,0,420)\\fad(250,350)}}{title}"),
           ev(3, 0.15, TITLE_DUR, "Shape", f"{{\\pos(160,352)\\org(160,352)\\fscx0\\t(0,500,\\fscx100)\\fad(0,350)\\bord0\\shad0\\1c{ACCENT}\\p1}}" + rrect(0, 0, 220, 7, 3) + "{\\p0}"),
           ev(4, 0.35, TITLE_DUR, "Sub", f"{{\\move(120,392,160,392,0,420)\\fad(250,350)}}{subtitle}")]
    return out



def mmss(x):
    return f"{int(x)//60:02d}:{int(x)%60:02d}" + (f".{int(round((x-int(x))*10))}" if abs(x-int(x))>=0.05 else "")


def write_roteiro(spec, scenes, total, out_dir):
    """roteiro-<slug>.md gerado do spec de produção: narração final, legenda, destaques e cortes do bruto."""
    srcs = spec["sources"]
    L = [f"# {spec['title']}" + (f" — {spec['subtitle']}" if spec.get("subtitle") else ""), ""]
    L.append(f"- **Slug:** `{spec['slug']}` → `{os.path.join(out_dir, spec['slug'])}.mp4` ({mmss(total)})")
    L.append("- **Fonte:** " + " · ".join(f"`{os.path.basename(p)}`" for p in srcs.values()))
    for k in ("acoes", "doc", "antes"):
        if spec.get(k):
            L.append(f"- **{ {'acoes':'Ações','doc':'Documento de referência','antes':'Como era antes'}[k] }:** {spec[k]}")
    L.append(f"- **Cartela:** \"{spec['title']} · {spec.get('subtitle','')}\" (3 s)")
    if spec.get("revisao"):
        L += ["", "## Revisão de coerência (contra o código-fonte)", ""] + [f"- {r}" for r in spec["revisao"]]
    L += ["", "## Cenas", ""]
    for i, sc in enumerate(scenes, 1):
        cl = ", ".join(f"{mmss(s)}–{mmss(e)}" + (f" ({v:.2g}×)" if abs(v-1)>0.01 else "") for s, e, v in sc["clips"])
        L.append(f"### {i}. {sc.get('chip','')}  ·  saída {mmss(sc['t0'])}–{mmss(sc['t0']+sc['dur'])}")
        L.append(f"**Bruto:** `{os.path.basename(srcs[sc['src']])}` {cl}" + (f"; congela {sc['freeze']:.1f} s" if sc['freeze']>0.3 else ""))
        if sc.get("callouts"):
            L.append("**Destaques:** " + " · ".join(
                (c.get("balloon") or "caixa") + (" (foco)" if c.get("focus") else "") for c in sc["callouts"]))
        if sc.get("legend"):
            L.append("**Narração:** " + " ".join(x.replace("\n", " ") for x in sc["legend"]))
        L.append("")
    L += ["## Narração TTS (texto com glossário de pronúncia)", ""]
    L += [f"{i}. {sc['tts_spoken']}" for i, sc in enumerate(scenes, 1) if sc.get("tts_spoken")]
    L += ["", "## Legenda (blocos de até 2 linhas, ~42 caracteres)", "", "```"]
    for sc in scenes:
        for x in sc.get("legend", []):
            L += [x, ""]
    L += ["```", "", "## Cortes (timestamps do bruto)", "", "| Arquivo | Trecho | Tratamento |", "|---|---|---|"]
    for sc in scenes:
        for s, e, v in sc["clips"]:
            L.append(f"| `{os.path.basename(srcs[sc['src']])}` | {mmss(s)}–{mmss(e)} | " + ("normal" if abs(v-1)<0.01 else f"velocidade {v:.2g}×") + " |")
    L.append("")
    L.append("Tudo fora dos trechos acima foi removido (carregamentos, esperas, leituras de documentação, passagens repetidas).")
    open(os.path.join(out_dir, f"roteiro-{spec['slug']}.md"), "w").write("\n".join(L) + "\n")

# ---------------- main ----------------
def main(spec_path):
    spec = json.load(open(spec_path))
    slug, out_dir, work = spec["slug"], spec["out_dir"], spec["work_dir"]
    voice = spec.get("voice", VOICE)
    gloss = pronuncia.load(spec.get("glossary"), voice=voice)
    os.makedirs(out_dir, exist_ok=True); os.makedirs(work, exist_ok=True)
    scenes = spec["scenes"]
    N = len(scenes)
    OW, OH = spec.get("size", [W, H])  # saída; coordenadas/ASS seguem em 1280x720 e o libass escala

    # 1. TTS, fit, timeline
    t = TITLE_DUR
    for sc in scenes:
        clips = [list(c) + [1.0] * (3 - len(c)) for c in sc["clips"]]
        text = sc.get("tts") or " ".join(b.replace("\n", " ") for b in sc.get("legend", []))
        sc["tts_spoken"] = pronuncia.apply(text, gloss)
        if sc["tts_spoken"]:
            sc["mp3"], sc["words"], sc["td"] = tts(sc["tts_spoken"], voice, work)
        else:
            sc["mp3"], sc["words"], sc["td"] = None, [], 0.0
        need = sc["td"] + TTS_LEAD + TTS_TAIL if sc["td"] else 0
        F = sum((e - s) / v for s, e, v in clips)
        if sc.get("fit", "auto") == "auto" and need and F > need + FIT_SLACK:
            k = min(F / (need + 0.4), FIT_CAP)
            clips = [[s, e, v * k] for s, e, v in clips]
            F = sum((e - s) / v for s, e, v in clips)
        elif sc.get("fit", "auto") == "auto" and need and F < need - 0.5:
            # narração maior que a filmagem: desacelera até SLOW_MIN antes de congelar
            k = max(F / need, SLOW_MIN)
            clips = [[s, e, v * k] for s, e, v in clips]
            F = sum((e - s) / v for s, e, v in clips)
        sc["clips"] = clips
        sc["fd"] = F
        sc["dur"] = max(F, need, sc.get("min_dur", 0))
        sc["freeze"] = sc["dur"] - F
        sc["t0"] = t
        # clip out-times
        o = t
        sc["clip_out"] = []
        for s, e, v in clips:
            sc["clip_out"].append((s, e, v, o)); o += (e - s) / v
        t += sc["dur"]
    total = t + TAIL_HOLD

    def out_time(sc, src_t):
        prev_end = sc["t0"]
        for s, e, v, o in sc["clip_out"]:
            if src_t < s:
                return o            # inside a cut before this clip -> clip start
            if src_t <= e:
                return o + (src_t - s) / v
            prev_end = o + (e - s) / v
        return min(prev_end + (sc["freeze"] if src_t > sc["clip_out"][-1][1] else 0), sc["t0"] + sc["dur"])

    # 2. SRT
    srt, n = [], 0
    for sc in scenes:
        if sc.get("legend") and sc["td"]:
            for s, e, txt in legend_cues(sc["legend"], sc["tts_spoken"], sc["words"], sc["t0"] + TTS_LEAD):
                n += 1
                srt.append(f"{n}\n{srt_ts(s)} --> {srt_ts(e)}\n{txt}\n")
    srt_path = os.path.join(out_dir, f"{slug}.srt")
    open(srt_path, "w").write("\n".join(srt))

    # 3. ASS
    ass = [ASS_HEAD] + title_evs(spec["title"], spec.get("subtitle", ""))
    for i, sc in enumerate(scenes, 1):
        s0, s1 = sc["t0"], sc["t0"] + sc["dur"]
        if sc.get("chip"):
            ass += chip_evs(s0 + 0.1, s1 - 0.1, f"{i}/{N}  ·  {sc['chip']}")
        # masks: tarjas opacas sobre dados pessoais (e-mail, telefone, token, caixa de entrada).
        # {"box":[x,y,w,h], "at":[t0,t1] (segundos do bruto; omitido = cena inteira), "label": "opcional"}
        for m in sc.get("masks", []):
            if "at" in m:
                ms, me = out_time(sc, m["at"][0]), out_time(sc, m["at"][1])
                if m["at"][1] >= sc["clip_out"][-1][1] - 0.05:
                    me = s1
            else:
                ms, me = s0, s1
            cap = total if i == N else s1          # última cena: tarja cobre também o TAIL_HOLD
            if me >= s1 - 0.05:
                me = cap
            x, y, w, h = m["box"]
            ass.append(ev(1, ms, min(me, cap), "Shape",
                          f"{{\\pos(0,0)\\1c&H3B302A&\\1a&H00&\\bord0\\shad0\\p1}}" + rrect(x, y, w, h, 6) + "{\\p0}"))
            if m.get("label"):
                ass.append(ev(1, ms, min(me, cap), "Chip",
                              f"{{\\an5\\pos({x + w / 2:.0f},{y + h / 2:.0f})\\fs15\\1c&HB8B0A8&}}{m['label']}"))
        for c in sc.get("callouts", []):
            if "at" in c:
                s, e = out_time(sc, c["at"][0]), out_time(sc, c["at"][1])
                if c["at"][1] >= sc["clip_out"][-1][1] - 0.05:
                    e = s1            # runs through the end-of-scene freeze
            else:
                s, e = s0 + c["out"][0], s0 + c["out"][1]
            e = min(e, s1)
            if e - s < 0.4:
                continue
            box = c.get("box")
            if box and c.get("focus"):
                ass.append(dim_ev(s, e, *box))
            if box:
                ass.append(box_ev(s, e, *box))
            if c.get("balloon"):
                ass += balloon_evs(s, e, c["balloon"], *(box or [None] * 4), at=c.get("balloon_at"))
            if c.get("arrow"):
                ass.append(arrow_ev(s, e, *c["arrow"]))
    ass_path = os.path.join(work, f"{slug}.ass")
    open(ass_path, "w").write("".join(ass))
    # timeline.json: tempos de saída por cena e por destaque (usado pelo manual/QA)
    tl = {"total": total, "scenes": []}
    for i, sc in enumerate(scenes, 1):
        s0, s1 = sc["t0"], sc["t0"] + sc["dur"]
        cs = []
        for c in sc.get("callouts", []):
            if "at" in c:
                s, e = out_time(sc, c["at"][0]), out_time(sc, c["at"][1])
                if c["at"][1] >= sc["clip_out"][-1][1] - 0.05:
                    e = s1
            else:
                s, e = s0 + c["out"][0], s0 + c["out"][1]
            cs.append({"start": round(s, 2), "end": round(min(e, s1), 2), "balloon": c.get("balloon"), "box": c.get("box"), "focus": bool(c.get("focus"))})
        tl["scenes"].append({"n": i, "chip": sc.get("chip"), "t0": round(s0, 2), "t1": round(s1, 2), "callouts": cs})
    json.dump(tl, open(os.path.join(work, "timeline.json"), "w"), ensure_ascii=False, indent=1)

    # 4. ffmpeg
    srcs = list(spec["sources"].items())
    src_idx = {k: i for i, (k, _) in enumerate(srcs)}
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for _, p in srcs:
        cmd += ["-i", p]
    aud = []
    for sc in scenes:
        if sc["mp3"]:
            aud.append((len(srcs) + len(aud), sc)); cmd += ["-i", sc["mp3"]]
    fc = [f"gradients=s={OW}x{OH}:c0=0x0b1220:c1=0x1e3a8a:x0=0:y0=0:x1={OW}:y1={OH}:d={TITLE_DUR}:r={FPS},"
          f"fade=t=out:st={TITLE_DUR-0.35}:d=0.35,format=yuv420p[v0]"]
    labels = ["[v0]"]
    k = 1
    # contagem de quadros acumulada: cada clipe termina no quadro exato do timeline,
    # sem perder ~meio quadro por clipe (o vídeo adiantava em relação a destaques e tarjas)
    t_acc = TITLE_DUR
    f_acc = round(TITLE_DUR * FPS)
    for i, sc in enumerate(scenes, 1):
        parts = []
        for j, (s, e, v) in enumerate(sc["clips"]):
            chain = (f"[{src_idx[sc['src']]}:v]trim=start={s}:end={e},setpts=(PTS-STARTPTS)/{v:.4f},"
                     f"fps={FPS},scale={OW}:{OH}:flags=bicubic,setsar=1,format=yuv420p")
            last = (j == len(sc["clips"]) - 1)
            fz = (sc["freeze"] if last else 0) + (TAIL_HOLD if last and i == N else 0)
            t_acc += (e - s) / v + (fz if fz > 0.01 else 0)
            nf = round(t_acc * FPS) - f_acc
            f_acc += nf
            chain += f",tpad=stop_mode=clone:stop_duration={(fz if fz > 0.01 else 0) + 0.5:.3f},trim=end_frame={nf}"
            if i == 1 and j == 0:
                chain += ",fade=t=in:d=0.3"
            fc.append(chain + f"[v{k}]"); labels.append(f"[v{k}]"); k += 1
    fc.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[vc]")
    # destaques/tarjas (ASS) primeiro, legenda por cima: tarja nunca esconde a legenda
    fc.append(f"[vc]ass='{ass_path}',subtitles=filename='{srt_path}':force_style='{LEGEND_STYLE}'[vout]")
    al = []
    for q, (idx, sc) in enumerate(aud):
        ms = int((sc["t0"] + TTS_LEAD) * 1000)
        fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{q}]"); al.append(f"[a{q}]")
    if al:
        fc.append("".join(al) + f"amix=inputs={len(al)}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11,apad[aout]")
    else:
        fc.append("anullsrc=r=48000:cl=stereo[aout]")
    out_mp4 = os.path.join(out_dir, f"{slug}.mp4")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-t", f"{total:.3f}", "-movflags", "+faststart", out_mp4]
    open(os.path.join(work, f"{slug}.ffmpeg.txt"), "w").write(" ".join(repr(c) if " " in c else c for c in cmd))
    run(cmd)
    rep = {"out": out_mp4, "total": round(total, 2), "cues": n,
           "scenes": [{"t0": round(sc["t0"], 2), "dur": round(sc["dur"], 2), "footage": round(sc["fd"], 2),
                       "tts": round(sc["td"], 2), "freeze": round(sc["freeze"], 2),
                       "speeds": [round(v, 2) for _, _, v in sc["clips"]]} for sc in scenes]}
    write_roteiro(spec, scenes, total, out_dir)
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
