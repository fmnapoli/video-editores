"""Partitura de bateria para vídeo: padrão compacto (JSON) -> MusicXML -> Verovio (SVG) -> cartão PNG + posição
de cada nota e de cada tempo, para animar depois (tocar.py) ou sobrepor num clipe gravado.

Uso:
  uv run --with verovio --with resvg-py --with pillow python partitura.py padroes.json [ID ...]
      [--out partituras] [--tamanho card|big|ambos] [--compassos N] [--fonte ARQ.ttf]

Entrada: {"padroes": [...]} ou lista. Cada padrão:
  {"id": "CINCO", "titulo": "Groove em 5/4", "sub": "2 + 3", "ts": [5, 4], "div": 1,
   "hh": "xxxxx", "sn": [2], "bd": {"pos": [1]}, "stick": {"2": "L"}, "acento": [0, 2]}
  - "ts": fórmula de compasso; "div": subdivisões por tempo (1 semínima, 2 colcheias, 4 semicolcheias).
  - instrumentos: hh (chimbal), ride, crash, sn (caixa), tom, ft (surdo), bd (bumbo), hf (chimbal de pé).
    Valor: lista de índices da grade (0 = 1ª subdivisão do tempo 1), "all", {"pos": [1, 2, 3]} (posições
    dentro de cada tempo) ou grade em texto: "x.xx x.xx" (x toca, X toca com acento, . ou - silêncio;
    espaços e | são ignorados; um caractere por subdivisão, tempos*div ao todo).
  - "stick": {indice: "R"|"L"}, "alterna" (R L R L… nas notas das mãos; "alterna:L" começa com L) ou texto
    com uma letra por subdivisão ("RLRRLRLL", . onde não há nota). Padrão R.
  - "acento": índices acentuados nas mãos (soma-se aos X da grade).
Saída em --out: <id>.png (cartão 1800×270, fundo claro) e <id>_big.png (1800×430), com <id>[_big].json
  {ts, div, compassos, tempos, beats_px (x por tempo), fim_px, y0, y1, card, titulo, sub,
   notas: [{t (onset em semínimas), x, y, inst, acento}]}, mais o .musicxml e o .svg.
Pegadinhas do Verovio (ficam aqui para não voltar): qfracOn vem em <divisions> e é relativo ao compasso;
  as coordenadas do SVG precisam do translate de .page-margin; a âncora do glifo é a borda esquerda da cabeça
  (+90 unidades para o centro).
"""
import argparse
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

TAMANHOS = {"card": (1800, 270), "big": (1800, 430)}
AZUL, ROSA, LARANJA, VERDE = "#2563EB", "#DB2777", "#EA580C", "#059669"
# posição na pauta (clave de percussão): passo/oitava e forma da cabeça
POS = {"hh": ("G", 5, "x"), "ride": ("F", 5, "x"), "crash": ("A", 5, "x"), "sn": ("C", 5, "normal"),
       "tom": ("E", 5, "normal"), "ft": ("A", 4, "normal"), "bd": ("F", 4, "normal"), "hf": ("D", 4, "x")}
MAOS = ("hh", "ride", "crash", "sn", "tom", "ft")
PES = ("bd", "hf")
TIPO = {1: "16th", 2: "eighth", 3: "eighth", 4: "quarter", 6: "quarter", 8: "half"}   # em semicolcheias


def fonte_padrao(peso="700"):
    """TTF para o título do cartão: Inter (se instalada), DejaVu Sans Bold ou Arial Bold; senão a fonte do Pillow."""
    cands = [os.path.expanduser(f"~/.local/share/fonts/inter/Inter-{peso}.ttf"),
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def fonte(caminho, tamanho):
    if caminho and os.path.exists(caminho):
        return ImageFont.truetype(caminho, tamanho)
    try:
        return ImageFont.load_default(tamanho)
    except TypeError:    # Pillow < 10.1
        return ImageFont.load_default()


def carrega(caminho):
    d = json.load(open(caminho, encoding="utf-8"))
    if isinstance(d, list):
        d = {"padroes": d}
    return d


def _indices(v, total, div):
    """Lista | "all" | {"pos": [...]} | grade em texto -> (índices, índices acentuados)."""
    if v == "all":
        return list(range(total)), []
    if isinstance(v, dict):
        pos = v["pos"]
        return [b * div + (q - 1) for b in range(total // div) for q in pos], []
    if isinstance(v, str):
        s = re.sub(r"[\s|]", "", v)
        if len(s) != total:
            raise ValueError(f"grade {v!r} tem {len(s)} posições; o compasso tem {total}")
        return [i for i, ch in enumerate(s) if ch in "xX"], [i for i, ch in enumerate(s) if ch == "X"]
    return [int(i) for i in v], []


def normaliza(p):
    """Padrão compacto -> dict com índices por instrumento, stick e acento resolvidos."""
    beats, bt = p["ts"]
    div = int(p.get("div", 4))
    if div not in (1, 2, 4):
        raise ValueError(f"{p['id']}: div={div}; só 1, 2 ou 4 subdivisões por tempo (tercinas não são suportadas)")
    total = beats * div
    q = {"id": p["id"], "titulo": p.get("titulo", p["id"]), "sub": p.get("sub", ""), "ts": [beats, bt], "div": div,
         "inst": {}, "acento": set(int(i) for i in p.get("acento", []))}
    for inst in POS:
        if inst in p:
            idx, ac = _indices(p[inst], total, div)
            q["inst"][inst] = sorted(set(idx))
            if inst in MAOS:
                q["acento"] |= set(ac)
    maos = sorted({i for inst in MAOS for i in q["inst"].get(inst, [])})
    st = p.get("stick", {})
    stick = {}
    if isinstance(st, str) and st.startswith("alterna"):
        m = st.split(":")[1] if ":" in st else "R"
        for i in maos:
            stick[i] = m
            m = "L" if m == "R" else "R"
    elif isinstance(st, str):
        s = re.sub(r"[\s|]", "", st)
        stick = {i: ch for i, ch in enumerate(s) if ch in "RL"}
    else:
        stick = {int(k): v for k, v in st.items()}
    q["stick"] = stick
    return q


def _dur_tipo(n_sub, div):
    semi = n_sub * (4 // div)
    if semi == 3:
        return "eighth", 1
    if semi == 6:
        return "quarter", 1
    return TIPO[semi], 0


def _eventos(indices_por_inst, total, div):
    """Grade -> [(índice, duração em subdivisões, [instrumentos])], silêncios como []; nada cruza a barra do tempo."""
    grade = {}
    for inst, idx in indices_por_inst.items():
        for i in idx:
            grade.setdefault(i, []).append(inst)
    ev, i = [], 0
    while i < total:
        fim_tempo = (i // div + 1) * div
        prox = min([j for j in grade if j > i] + [total])
        fim = min(fim_tempo, prox)
        ev.append((i, fim - i, grade.get(i, [])))
        i = fim
    return ev


def musicxml(q, compassos=1):
    beats, bt = q["ts"]
    div, total = q["div"], q["ts"][0] * q["div"]
    maos = {k: v for k, v in q["inst"].items() if k in MAOS}
    pes = {k: v for k, v in q["inst"].items() if k in PES}
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="4.0">',
           '<part-list><score-part id="P1"><part-name></part-name></score-part></part-list>', '<part id="P1">']

    def voz(evs, n, stem, com_stick, m):
        beam_aberto = False
        for k, (i, d, insts) in enumerate(evs):
            tipo, dots = _dur_tipo(d, div)
            if not insts:
                out.append(f'<note><rest/><duration>{d}</duration><voice>{n}</voice><type>{tipo}</type>' + '<dot/>' * dots + '</note>')
                beam_aberto = False
                continue
            sub_beat = d < div
            prox = k + 1 < len(evs) and evs[k + 1][2] and evs[k + 1][1] < div and (evs[k + 1][0] // div == i // div)
            beam = ""
            if sub_beat:
                if not beam_aberto and prox:
                    beam, beam_aberto = '<beam number="1">begin</beam>', True
                elif beam_aberto and prox:
                    beam = '<beam number="1">continue</beam>'
                elif beam_aberto:
                    beam, beam_aberto = '<beam number="1">end</beam>', False
            for j, inst in enumerate(sorted(insts, key=lambda x: list(POS).index(x))):
                step, octv, head = POS[inst]
                chord = "<chord/>" if j else ""
                cor = f' color="{LARANJA}"' if inst == "bd" else (f' color="{VERDE}"' if inst == "hf" else "")
                lyr = ""
                if com_stick and j == 0:
                    s = q["stick"].get(i, "R")
                    lyr = (f'<lyric number="1" color="{AZUL if s == "R" else ROSA}"><syllabic>single</syllabic>'
                           f'<text>{s}</text></lyric>')
                art = '<notations><articulations><accent/></articulations></notations>' if (com_stick and j == 0 and i in q["acento"]) else ""
                nh = '<notehead>x</notehead>' if head == "x" else ""
                out.append(f'<note id="{inst}_{m}_{i}_{j}"{cor}>{chord}<unpitched><display-step>{step}</display-step>'
                           f'<display-octave>{octv}</display-octave></unpitched><duration>{d}</duration><voice>{n}</voice>'
                           f'<type>{tipo}</type>' + '<dot/>' * dots + f'<stem>{stem}</stem>{nh}{beam if j == 0 else ""}{art}{lyr}</note>')

    for m in range(compassos):
        out.append(f'<measure number="{m + 1}">')
        if m == 0:
            out.append(f'<attributes><divisions>{div}</divisions><time><beats>{beats}</beats><beat-type>{bt}</beat-type></time>'
                       '<clef><sign>percussion</sign><line>2</line></clef><staff-lines>5</staff-lines></attributes>')
        voz(_eventos(maos, total, div), 1, "up", True, m)
        if pes:
            out.append(f'<backup><duration>{total}</duration></backup>')
            voz(_eventos(pes, total, div), 2, "down", False, m)
        if m == compassos - 1:
            out.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
        out.append('</measure>')
    out.append('</part></score-partwise>')
    return "\n".join(out)


def svg_para_png(svg, caminho, largura, altura):
    """Rasteriza com resvg (roda sem biblioteca de sistema); cai no cairosvg se instalado."""
    try:
        import resvg_py
        png = resvg_py.svg_to_bytes(svg_string=svg, width=largura, height=altura)
        open(caminho, "wb").write(bytes(png))
    except ImportError:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=caminho, output_width=largura, output_height=altura)


def render(q, outdir="partituras", tamanho="card", compassos=2, fonte_ttf=None):
    """Renderiza um padrão normalizado; devolve o dict gravado no JSON."""
    import verovio
    os.makedirs(outdir, exist_ok=True)
    CARD_W, CARD_H = TAMANHOS[tamanho]
    nome = q["id"] if tamanho == "card" else f"{q['id']}_{tamanho}"
    xml = musicxml(q, compassos)
    open(f"{outdir}/{nome}.musicxml", "w", encoding="utf-8").write(xml)
    tk = verovio.toolkit()
    tk.setOptions({"pageWidth": 6000, "pageHeight": 800, "scale": 50, "adjustPageHeight": True, "footer": "none", "header": "none",
                   "svgViewBox": True, "pageMarginLeft": 10, "pageMarginRight": 10, "pageMarginTop": 30, "pageMarginBottom": 10,
                   "lyricSize": 5.5, "spacingLinear": 0.3, "spacingNonLinear": 0.55, "breaks": "none", "staffLineWidth": 0.2,
                   "stemWidth": 0.22})
    if not tk.loadData(xml):
        raise RuntimeError(f"verovio não carregou o MusicXML de {q['id']}")
    svg = tk.renderToSVG(1)
    open(f"{outdir}/{nome}.svg", "w", encoding="utf-8").write(svg)

    m = re.search(r'class="definition-scale"[^>]*viewBox="0 0 (\d+) (\d+)"', svg)
    vw, vh = (int(m.group(1)), int(m.group(2))) if m else (6200, 1600)
    pm = re.search(r'class="page-margin" transform="translate\((-?\d+),\s*(-?\d+)\)"', svg)
    mx, my = (int(pm.group(1)), int(pm.group(2))) if pm else (0, 0)
    beats_bar, bt = q["ts"]
    beats = beats_bar * compassos
    xs, notas = {}, []
    for g in re.finditer(r'<g id="([^"]+)" class="note"[^>]*>(.*?)</g>', svg, re.S):
        nid, corpo = g.group(1), g.group(2)
        u = re.search(r'translate\((-?\d+),\s*(-?\d+)\)', corpo)
        if not u:
            continue
        t = tk.getTimesForElement(nid)
        qf = (t.get("qfracOn") or [[None, 1]])[0] if isinstance(t, dict) else [None, 1]
        if qf[0] is None:
            continue
        partes = nid.split("_")
        inst, mi, gi = partes[0], int(partes[1]), int(partes[2])
        on = qf[0] / qf[1] / q["div"] + mi * beats_bar * 4 / bt      # onset absoluto em semínimas
        b = int(round(on * bt / 4, 6))                               # tempo absoluto (0-based)
        x, y = int(u.group(1)) + mx + 90, int(u.group(2)) + my
        xs[b] = min(xs.get(b, 10 ** 9), x)
        notas.append({"t": on, "xv": x, "yv": y, "inst": inst, "acento": inst in MAOS and gi in q["acento"]})

    outer = re.search(r'<svg viewBox="0 0 (\d+) (\d+)"', svg)
    sw, sh = int(outer.group(1)), int(outer.group(2))
    topo = 58
    escala = min((CARD_W - 60) / sw, (CARD_H - topo - 12) / sh)
    pw, ph = int(sw * escala), int(sh * escala)
    tmp = f"{outdir}/_{nome}.png"
    svg_para_png(svg, tmp, pw, ph)
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=22, fill=(248, 250, 252, 255))
    pauta = Image.open(tmp).convert("RGBA")
    ox = 30 if tamanho == "card" else (CARD_W - pw) // 2
    oy = topo + (CARD_H - topo - ph) // 2
    card.alpha_composite(pauta, (ox, oy))
    f = fonte(fonte_ttf or fonte_padrao("700"), 34 if tamanho == "card" else 40)
    d.text((34, 14), q["titulo"], font=f, fill=(15, 23, 42, 255))
    if q.get("sub"):
        f2 = fonte(fonte_ttf or fonte_padrao("600"), 26 if tamanho == "card" else 30)
        tw = d.textlength(q["titulo"], font=f)
        d.text((34 + tw + 18, 21 if tamanho == "card" else 24), q["sub"], font=f2, fill=(100, 116, 139, 255))
    card.save(f"{outdir}/{nome}.png")
    os.remove(tmp)

    beats_px = [ox + int(xs[b] / vw * pw) if b in xs else None for b in range(beats)]
    known = [(b, x) for b, x in enumerate(beats_px) if x is not None]
    if len(known) >= 2:          # tempo sem nota (silêncio): interpola pelos vizinhos
        for b, x in enumerate(beats_px):
            if x is None:
                b0, x0 = max([k for k in known if k[0] < b], default=known[0])
                b1, x1 = min([k for k in known if k[0] > b], default=known[-1])
                beats_px[b] = int(x0 + (x1 - x0) * (b - b0) / max(1, b1 - b0)) if b1 != b0 else x0
    fim = beats_px[-1] + (beats_px[-1] - beats_px[-2]) if len(beats_px) >= 2 and None not in beats_px[-2:] else ox + pw - 20
    for n in notas:
        n["x"] = ox + int(n.pop("xv") / vw * pw)
        n["y"] = oy + int(n.pop("yv") / vh * ph)
    info = {"id": q["id"], "titulo": q["titulo"], "sub": q.get("sub", ""), "ts": q["ts"], "div": q["div"], "compassos": compassos,
            "tempos": beats, "beats_px": beats_px, "fim_px": min(fim, ox + pw - 20), "y0": oy, "y1": oy + ph, "card": [CARD_W, CARD_H],
            "notas": sorted(notas, key=lambda n: (n["t"], n["y"]))}
    json.dump(info, open(f"{outdir}/{nome}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("padroes", help="JSON com os padrões")
    ap.add_argument("ids", nargs="*", help="só estes ids (padrão: todos)")
    ap.add_argument("--out", default="partituras")
    ap.add_argument("--tamanho", choices=["card", "big", "ambos"], default="ambos")
    ap.add_argument("--compassos", type=int, help="compassos renderizados (padrão: 4 se div=1, senão 2)")
    ap.add_argument("--fonte", help="TTF do título (padrão: Inter, DejaVu Sans Bold ou Arial Bold)")
    a = ap.parse_args()
    d = carrega(a.padroes)
    fonte_ttf = a.fonte or d.get("fonte")
    pads = [p for p in d["padroes"] if not a.ids or p["id"] in a.ids]
    if not pads:
        sys.exit(f"nenhum padrão casa com {a.ids}")
    for p in pads:
        q = normaliza(p)
        nc = a.compassos or (4 if q["div"] == 1 else 2)
        for tam in (["card", "big"] if a.tamanho == "ambos" else [a.tamanho]):
            info = render(q, a.out, tam, nc, fonte_ttf)
        print(f"{q['id']}: {len(info['notas'])} notas, {info['tempos']} tempos -> {a.out}/{q['id']}[_big].png/.json")


if __name__ == "__main__":
    main()
