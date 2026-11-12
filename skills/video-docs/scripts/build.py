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
     ],
     "no_client": true}                         # opcional: desliga a tarja fixa (chrome.client) nesta cena
  ],
  "srt_dir": "legendas", "roteiro_dir": "roteiros",   # opcionais: .srt e roteiro fora da pasta do .mp4
  "chrome": {"band": 100, "logo": "marca/logo.png",   # opcional: faixa sobre a barra do navegador (0 = sem faixa)
             "client": [x, y, w, h], "client_label": "cliente de teste"},  # tarja fixa em toda cena
  "chrome_src": {"b": {"band": 0}}                    # opcional: ajuste por fonte (gravação sem navegador)
}
Saídas extras: <work>/palavras.transcript.json (palavras com a grafia da legenda e o tempo da fala, para o
/legenda reels-palavra) e "avisos" no relatório (destaque fora do quadro ou sobre a legenda, "at" num corte).
Scene duration = max(footage, narration + lead + tail); shortfall becomes a freeze of the last frame.
"""
import asyncio, hashlib, json, math, os, re, shutil, subprocess, sys, time, unicodedata

import pathlib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pronuncia  # noqa: E402


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[3])


RAIZ = os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__)
sys.path.insert(0, RAIZ)
from video_editores.nucleo import marca as marca_mod  # noqa: E402


def ffesc(p):
    """Escapa um caminho para uso dentro de opções de filtro do ffmpeg."""
    return (p.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
             .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]"))


W, H, FPS = 1280, 720, 30
TITLE_DUR = 3.2
END_DUR = 3.0   # tela de encerramento com o logo; só existe quando a marca tem logo
TTS_LEAD, TTS_TAIL, TAIL_HOLD = 0.25, 0.35, 0.8
FIT_CAP, FIT_SLACK, SLOW_MIN = 2.2, 1.2, 0.7
VOICE = "pt-BR-ThalitaMultilingualNeural"  # pronuncia termos em inglês nativamente
def _find_font():
    """DejaVu Sans Bold em Linux, macOS ou Windows; por último, fontconfig."""
    cands = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
             os.path.expanduser("~/Library/Fonts/DejaVuSans-Bold.ttf"),
             "/Library/Fonts/DejaVuSans-Bold.ttf",
             "/opt/homebrew/share/fonts/DejaVuSans-Bold.ttf",
             r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"]
    for c in cands:
        if os.path.exists(c):
            return c
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if out:
            return out
    except (OSError, subprocess.CalledProcessError):
        pass
    return cands[0]


FONT = _find_font()
FONT_NAME = "DejaVu Sans"
# colours (ASS &HAABBGGRR&)
ACCENT = "&H00356BFF&"        # laranja FF6B35
ACCENT_BGR = "356BFF"
INK = "&H142A170F&"           # navy 0F172A, 92% opaco
INK_SOFT = "&H402A170F&"
DIM = "&H8C000000&"           # preto 45% opaco
TEXT = "&H00FFFFFF"            # texto de balões, chips e título (estilo ASS, sem & final)
SUB = "&H00E2E8F0"             # subtítulo da cartela


def legend_style():
    return (f"FontName={FONT_NAME},FontSize=11,Bold=1,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H78000000,BorderStyle=3,Outline=2,"
            "Shadow=0,MarginV=18,Alignment=2")


def aplica_marca(m):
    """Troca as constantes de identidade pelas da marca (ADR-17). Sem marca definida, nada muda."""
    global FONT, FONT_NAME, ACCENT, ACCENT_BGR, INK, INK_SOFT, TEXT, SUB
    if not m.definida:
        return
    c = m.cores
    ACCENT, ACCENT_BGR = marca_mod.ass(c["acento"]), marca_mod.ass_bgr(c["acento"])
    INK, INK_SOFT = marca_mod.ass(c["fundo"], 0x14), marca_mod.ass(c["fundo"], 0x40)
    TEXT = marca_mod.ass(c["texto"]).rstrip("&")
    SUB = marca_mod.ass(c["acento"]).rstrip("&")
    FONT_NAME = m.fonte
    arq = m.fonte_arquivo("bold")
    if arq:
        FONT = arq
    else:   # fonte do sistema: acha o arquivo pelo fontconfig, para medir o texto dos balões
        try:
            out = subprocess.run(["fc-match", "-f", "%{file}", f"{FONT_NAME}:bold"],
                                 capture_output=True, text=True, check=True).stdout.strip()
            FONT = out or FONT
        except (OSError, subprocess.CalledProcessError):
            pass
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


def logo_w(path, band):
    """Largura (em 1280x720) do logo escalado a 42% da faixa."""
    try:
        from PIL import Image
        w, h = Image.open(path).size
        return band * 0.42 * w / h
    except Exception:
        return band * 0.42 * 3


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


def synth_retry(text, voice, mp3, tentativas=3):
    """O edge-tts falha de vez em quando (NoAudioReceived, WebSocket fechado): repete com espera crescente
    (VE_TTS_ESPERA s, padrão 2) e, se não der, ENCERRA com erro. Seguir em frente deixaria o .mp4 antigo
    no lugar, parecendo atualizado."""
    espera = float(os.environ.get("VE_TTS_ESPERA", "2"))
    erro = None
    for i in range(tentativas):
        try:
            words = asyncio.run(_synth(text, voice, mp3))
            if os.path.getsize(mp3) > 0:
                return words
            erro = "resposta sem áudio"
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:  # transitórios do serviço
            erro = f"{type(e).__name__}: {e}"
        if os.path.exists(mp3):
            os.remove(mp3)
        if i + 1 < tentativas:
            print(f"edge-tts: tentativa {i + 1} falhou ({erro}); repetindo em {espera * (i + 1):.0f}s", file=sys.stderr)
            time.sleep(espera * (i + 1))
    raise SystemExit(f"edge-tts falhou {tentativas} vezes ({erro}); nada foi gravado em out_dir")


def tts(text, voice, work):
    h = hashlib.sha1((voice + "|" + text).encode()).hexdigest()[:12]
    mp3, js = os.path.join(work, f"tts-{h}.mp3"), os.path.join(work, f"tts-{h}.json")
    if not (os.path.exists(mp3) and os.path.exists(js)):
        words = synth_retry(text, voice, mp3)
        json.dump({"words": words, "dur": ffdur(mp3)}, open(js, "w", encoding="utf-8"))
    d = json.load(open(js, encoding="utf-8"))
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
def ass_head():
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shape,{FONT_NAME},20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Balloon,{FONT_NAME},21,{TEXT},&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Chip,{FONT_NAME},17,{TEXT},&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Title,{FONT_NAME},48,{TEXT},&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Sub,{FONT_NAME},26,{SUB},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1

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



def end_evs(t0, subtitle):
    """Encerramento: logo centralizado (overlay no ffmpeg) e a linha do produto embaixo."""
    if not subtitle:
        return []
    return [ev(4, t0 + 0.4, t0 + END_DUR, "Sub", f"{{\\an8\\pos({W/2:.0f},420)\\fad(300,0)}}{subtitle}")]


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
    rd = spec.get("roteiro_dir", out_dir)
    os.makedirs(rd, exist_ok=True)
    open(os.path.join(rd, f"roteiro-{spec['slug']}.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

def com_pontuacao(words, narracao, gloss):
    """O edge-tts devolve as palavras FALADAS (glossário aplicado, sem pontuação); devolve [(ini, fim, token)]
    com os tokens da legenda. Um termo do glossário pode virar várias palavras faladas."""
    def chave(x):
        x = unicodedata.normalize("NFKD", x.lower())
        return "".join(ch for ch in x if ch.isalnum())

    orig = narracao.split()
    flat = [(chave(sp), oi) for oi, tok in enumerate(orig) for sp in pronuncia.apply(tok, gloss).split()]
    flat = [f for f in flat if f[0]]
    span, pos, cur = {}, 0, 0
    for t0, d, w in words:
        k = chave(w)
        j = pos
        while k and j < len(flat) and j < pos + 4 and not (flat[j][0].startswith(k[:3]) or k.startswith(flat[j][0][:3])):
            j += 1
        if k and j < len(flat) and j < pos + 4:
            cur, pos = flat[j][1], j + 1
        span[cur] = (span[cur][0], max(span[cur][1], t0 + d)) if cur in span else (t0, t0 + d)
    out, fim = [], 0.0
    for oi, tok in enumerate(orig):
        a, b = span.get(oi, (fim, fim + 0.01))
        out.append((a, b, tok))
        fim = b
    return out


def valida(spec, scenes):
    """Avisos de destaque/tarja que costumam sair errados: fora do quadro, sobre a faixa da legenda,
    "at" caindo num trecho cortado (o destaque aparece no instante errado)."""
    av = []
    for i, sc in enumerate(scenes, 1):
        clips = sc["clips"]

        def cortado(t, clips=clips):
            return not any(s - 0.05 <= t <= e + 0.05 for s, e, *_ in clips)
        for kind, lst in (("destaque", sc.get("callouts", [])), ("tarja", sc.get("masks", []))):
            for n, c in enumerate(lst, 1):
                tag = f"cena {i} ({sc.get('chip', '')}), {kind} {n}"
                box = c.get("box")
                if box:
                    x, y, w, h = box
                    if x < 0 or y < 0 or x + w > W or y + h > H:
                        av.append(f"{tag}: caixa {box} sai do quadro 1280x720 (coordenadas de uma fonte 1080p? divida por 1,5)")
                    elif kind == "destaque" and y + h > SAFE_BOTTOM:
                        av.append(f"{tag}: caixa {box} entra na faixa da legenda (y > {SAFE_BOTTOM})")
                if kind == "destaque" and c.get("balloon_at"):
                    bx, by = c["balloon_at"]
                    if by + 40 > SAFE_BOTTOM or by < 0:
                        av.append(f"{tag}: balão em y={by} cobre a legenda ou sai do quadro (use y ≤ {SAFE_BOTTOM - 40})")
                if "at" in c:
                    a, b = c["at"]
                    if b <= a:
                        av.append(f"{tag}: at {c['at']} com fim antes do início")
                    elif not any(s < b and e > a for s, e, *_ in clips):
                        av.append(f"{tag}: at {c['at']} cai inteiro em trecho cortado do bruto (não aparece)")
                    elif cortado(a):
                        av.append(f"{tag}: at[0]={a} cai num corte; o destaque entra no começo do clipe seguinte")
    return av


# ---------------- main ----------------
def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    slug, out_dir, work = spec["slug"], spec["out_dir"], spec["work_dir"]
    voice = spec.get("voice", VOICE)
    gloss = pronuncia.load(spec.get("glossary"), voice=voice)
    os.makedirs(out_dir, exist_ok=True); os.makedirs(work, exist_ok=True)
    # identidade (ADR-17): "marca" no spec (caminho; false = padrão do plugin) > $VE_MARCA > marca/marca.json
    m = marca_mod.carregar(spec.get("marca"), base=".")
    aplica_marca(m)
    logo_png = m.logo("png") if m.definida else None
    fim = END_DUR if (logo_png and spec.get("encerramento", True)) else 0.0
    leg = dict(m.legenda, **spec.get("legenda", {}))
    if leg.get("estilo", "bloco") not in ("bloco", "palavra"):
        raise SystemExit("legenda.estilo deve ser 'bloco' ou 'palavra'")
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
    content_end = t + TAIL_HOLD
    total = content_end + fim

    avisos = valida(spec, scenes)
    for a in avisos:
        print(f"aviso: {a}", file=sys.stderr)

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
            sc["cues"] = legend_cues(sc["legend"], sc["tts_spoken"], sc["words"], sc["t0"] + TTS_LEAD)
            for s, e, txt in sc["cues"]:
                n += 1
                srt.append(f"{n}\n{srt_ts(s)} --> {srt_ts(e)}\n{txt}\n")
    # o .srt é escrito no work e só vai para srt_dir depois que o .mp4 sai: falha no meio não deixa par trocado
    srt_path = os.path.join(work, f"{slug}.srt")
    open(srt_path, "w", encoding="utf-8").write("\n".join(srt))
    segs = []
    for sc in scenes:
        disp = " ".join(b.replace("\n", " ") for b in sc.get("legend", []))
        if not (disp and sc["td"]):
            continue
        if sc.get("tts"):   # fala própria, diferente da legenda: tempo repartido por igual dentro de cada bloco
            ws = []
            for a, b, txt in sc["cues"]:
                toks = txt.split()
                passo = (b - a) / len(toks)
                ws += [{"start": round(a + q * passo, 3), "end": round(a + (q + 1) * passo, 3), "word": w}
                       for q, w in enumerate(toks)]
            segs.append({"words": ws})
        else:
            off = sc["t0"] + TTS_LEAD
            segs.append({"words": [{"start": round(off + a, 3), "end": round(off + b, 3), "word": w}
                                   for a, b, w in com_pontuacao(sc["words"], disp, gloss)]})
    tj = os.path.join(work, "palavras.transcript.json")
    json.dump({"segments": segs}, open(tj, "w", encoding="utf-8"), ensure_ascii=False)
    leg_ass = None
    if leg.get("estilo") == "palavra" and segs:
        # legenda por página com a palavra falada em destaque (scripts/legenda_palavra.py), nas cores da marca
        lp = next((c for c in (os.path.join(HERE, "..", "..", "..", "scripts", "legenda_palavra.py"),
                               os.path.join(RAIZ, "scripts", "legenda_palavra.py")) if os.path.exists(c)), None)
        if not lp:
            raise SystemExit("legenda.estilo 'palavra' precisa de scripts/legenda_palavra.py (não encontrado)")
        dummy = os.path.join(work, f"dummy-{OW}x{OH}.mp4")
        if not os.path.exists(dummy):
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={OW}x{OH}:d=0.1", dummy])
        leg_ass = os.path.join(work, "legenda.ass")
        run([sys.executable, lp, dummy, tj, "--ass", leg_ass, "--font", FONT_NAME,
             "--cor", m.cor("texto"), "--destaque", m.cor(leg.get("destaque") or "acento"),
             "--pos", str(leg.get("pos", 0.915)), "--tamanho", str(leg.get("tamanho", 0.046)),
             "--janela", str(leg.get("janela", 2.4)), "--max-palavras", str(leg.get("max_palavras", 6))]
            + (["--caixa"] if leg.get("caixa") else []) + (["--espaco-largo"] if leg.get("espaco_largo") else []))

    # 3. ASS
    ass = [ass_head()] + title_evs(spec["title"], spec.get("subtitle", ""))
    if fim:
        ass += end_evs(content_end, spec.get("subtitle", ""))
    for i, sc in enumerate(scenes, 1):
        s0, s1 = sc["t0"], sc["t0"] + sc["dur"]
        if sc.get("chip"):
            ass += chip_evs(s0 + 0.1, s1 - 0.1, f"{i}/{N}  ·  {sc['chip']}")
        # masks: tarjas opacas sobre dados pessoais (e-mail, telefone, token, caixa de entrada).
        # {"box":[x,y,w,h], "at":[t0,t1] (segundos do bruto; omitido = cena inteira), "label": "opcional"}
        for mk in sc.get("masks", []):
            if "at" in mk:
                ms, me = out_time(sc, mk["at"][0]), out_time(sc, mk["at"][1])
                if mk["at"][1] >= sc["clip_out"][-1][1] - 0.05:
                    me = s1
            else:
                ms, me = s0, s1
            cap = content_end if i == N else s1    # última cena: tarja cobre também o TAIL_HOLD
            if me >= s1 - 0.05:
                me = cap
            x, y, w, h = mk["box"]
            ass.append(ev(1, ms, min(me, cap), "Shape",
                          f"{{\\pos(0,0)\\1c&H3B302A&\\1a&H00&\\bord0\\shad0\\p1}}" + rrect(x, y, w, h, 6) + "{\\p0}"))
            if mk.get("label"):
                ass.append(ev(1, ms, min(me, cap), "Chip",
                              f"{{\\an5\\pos({x + w / 2:.0f},{y + h / 2:.0f})\\fs15\\1c&HB8B0A8&}}{mk['label']}"))
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
    # faixa sobre a barra do navegador (abas, URL, favoritos) e tarja fixa (ex.: seletor de cliente do portal)
    chrome_def = {"band": 0, "client": None, "client_label": "oculto", "logo": logo_png}
    chrome_def.update(spec.get("chrome", {}))
    bands = []
    for i, sc in enumerate(scenes, 1):
        ch = dict(chrome_def, **spec.get("chrome_src", {}).get(sc["src"], {}))
        s0, s1 = sc["t0"], (content_end if i == N else sc["t0"] + sc["dur"])
        bh = ch.get("band") or 0
        if bh:
            bands.append((s0, s1, bh, ch.get("logo")))
            tx = 28 + (logo_w(ch.get("logo"), bh) + 18 if ch.get("logo") else 0)
            ass.append(ev(1, s0, s1, "Shape", f"{{\\pos(0,0)\\1c{INK}\\1a&H00&\\bord0\\shad0\\p1}}" + rect(0, 0, W, bh) + "{\\p0}"))
            ass.append(ev(1, s0, s1, "Shape", f"{{\\pos(0,0)\\1c{ACCENT}\\bord0\\shad0\\p1}}" + rect(0, bh - 3, W, 3) + "{\\p0}"))
            ass.append(ev(2, s0, s1, "Chip", f"{{\\an4\\pos({tx:.0f},{bh/2:.0f})\\fs22}}{spec['title']}"))
            if spec.get("subtitle"):
                ass.append(ev(2, s0, s1, "Chip", f"{{\\an6\\pos({W - 28:.0f},{bh/2:.0f})\\fs17\\1c{ACCENT}}}{spec['subtitle']}"))
        if ch.get("client") and not sc.get("no_client"):
            x, y, w, h = ch["client"]
            ass.append(ev(1, s0, s1, "Shape", f"{{\\pos(0,0)\\1c&HF7F5F3&\\3c&HDED7D0&\\bord1\\shad0\\p1}}" + rrect(x, y, w, h, h / 2) + "{\\p0}"))
            if ch.get("client_label"):
                ass.append(ev(1, s0, s1, "Chip", f"{{\\an5\\pos({x + w / 2:.0f},{y + h / 2:.0f})\\fs14\\1c&H6E655C&}}{ch['client_label']}"))
    ass_path = os.path.join(work, f"{slug}.ass")
    open(ass_path, "w", encoding="utf-8").write("".join(ass))
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
    json.dump(tl, open(os.path.join(work, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

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
    ninp = [len(srcs) + len(aud)]

    def img(path, dur):
        """Acrescenta uma imagem em loop como entrada e devolve o índice."""
        cmd.extend(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", path])
        ninp[0] += 1
        return ninp[0] - 1

    logos = []   # um overlay por logo distinto, ligado só enquanto a faixa daquela fonte está na tela
    for lg in dict.fromkeys(b[3] for b in bands if b[3]):
        logos.append((img(lg, total + 1), lg, [b for b in bands if b[3] == lg]))

    def fundo(qual, dur, rotulo):
        """Fundo da cartela/encerramento: PNG da marca, senão gradiente das cores da marca, senão o do plugin."""
        arq = (m.fundo(qual) or m.fundo("cartela")) if m.definida else None
        if arq:
            return f"[{img(arq, dur)}:v]scale={OW}:{OH},setsar=1,fps={FPS},trim=end_frame={round(dur * FPS)}[{rotulo}]"
        c0, c1 = ((marca_mod.ffcor(m.cores["fundo"]), marca_mod.ffcor(m.cores["fundo2"])) if m.definida
                  else ("0x0b1220", "0x1e3a8a"))
        return f"gradients=s={OW}x{OH}:c0={c0}:c1={c1}:x0=0:y0=0:x1={OW}:y1={OH}:d={dur}:r={FPS}:seed=7[{rotulo}]"

    fc = [fundo("cartela", TITLE_DUR, "bg1")]
    if logo_png:   # logo pequeno no canto da cartela
        fc.append(f"[{img(logo_png, TITLE_DUR)}:v]scale=-2:{round(OH * 0.065)}[lgs]")
        fc.append(f"[bg1][lgs]overlay={round(OW * 0.047)}:{round(OH * 0.075)},trim=end_frame={round(TITLE_DUR * FPS)}[bg1l]")
    fc.append(f"[{'bg1l' if logo_png else 'bg1'}]fade=t=out:st={TITLE_DUR-0.35}:d=0.35,format=yuv420p[v0]")
    if fim:        # encerramento: fundo + logo grande centralizado
        fc.append(fundo("encerramento", END_DUR, "bg2"))
        fc.append(f"[{img(logo_png, END_DUR)}:v]scale=-2:{round(OH * 0.12)},format=rgba,fade=t=in:st=0:d=0.5:alpha=1[lgb]")
        fc.append(f"[bg2][lgb]overlay=(W-w)/2:{round(OH * 0.36)}-h/2,trim=end_frame={round(END_DUR * FPS)},"
                  f"fade=t=in:st=0:d=0.35,format=yuv420p[vend]")
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
    if fim:
        labels.append("[vend]")
    fc.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[vc]")
    # destaques/tarjas (ASS) primeiro, legenda por cima: tarja nunca esconde a legenda
    vlab = "vc"
    fd = f":fontsdir='{ffesc(m.fontes_dir())}'" if m.fontes_dir() else ""   # fonte da marca fora do sistema
    fc.append(f"[vc]ass=filename='{ffesc(ass_path)}'{fd}[va]"); vlab = "va"
    for q, (idx, _, bs) in enumerate(logos):
        bh = max(b[2] for b in bs)
        en = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b, _, _ in bs)
        fc.append(f"[{idx}:v]scale=-2:{round(bh * 0.42 * OH / H)}[lg{q}]")
        fc.append(f"[{vlab}][lg{q}]overlay={round(28 * OW / W)}:{round(bh / 2 * OH / H)}-h/2:enable='{en}'[vl{q}]")
        vlab = f"vl{q}"
    if leg_ass:
        fc.append(f"[{vlab}]ass=filename='{ffesc(leg_ass)}'{fd}[vout]")
    else:
        fc.append(f"[{vlab}]subtitles=filename='{ffesc(srt_path)}'{fd}:force_style='{legend_style()}'[vout]")
    al = []
    for q, (idx, sc) in enumerate(aud):
        ms = int((sc["t0"] + TTS_LEAD) * 1000)
        fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{q}]"); al.append(f"[a{q}]")
    if al:
        fc.append("".join(al) + f"amix=inputs={len(al)}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11,apad[aout]")
    else:
        fc.append("anullsrc=r=48000:cl=stereo[aout]")
    out_mp4 = os.path.join(out_dir, f"{slug}.mp4")
    tmp_mp4 = os.path.join(work, f"{slug}.parcial.mp4")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-t", f"{total:.3f}", "-movflags", "+faststart", tmp_mp4]
    open(os.path.join(work, f"{slug}.ffmpeg.txt"), "w", encoding="utf-8").write(" ".join(repr(c) if " " in c else c for c in cmd))
    run(cmd)
    shutil.move(tmp_mp4, out_mp4)          # só agora o vídeo antigo é substituído
    srt_dir = spec.get("srt_dir", out_dir)
    os.makedirs(srt_dir, exist_ok=True)
    shutil.copyfile(srt_path, os.path.join(srt_dir, f"{slug}.srt"))
    rep = {"out": out_mp4, "total": round(total, 2), "cues": n,
           "scenes": [{"t0": round(sc["t0"], 2), "dur": round(sc["dur"], 2), "footage": round(sc["fd"], 2),
                       "tts": round(sc["td"], 2), "freeze": round(sc["freeze"], 2),
                       "speeds": [round(v, 2) for _, _, v in sc["clips"]]} for sc in scenes],
           "marca": (m.nome or os.path.basename(m.pasta)) if m.definida else None, "avisos": avisos}
    write_roteiro(spec, scenes, total, out_dir)
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
