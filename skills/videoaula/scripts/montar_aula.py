#!/usr/bin/env python3
"""Monta uma videoaula redesenhada a partir de `aula.json`: lista de blocos (EDL) no tempo do vídeo
cortado, render de cada bloco (locutor recortado, quadro → diagrama Manim + círculo, código reenquadrado,
cartelas) e concatenação com trilha de áudio contínua (sem deriva entre blocos).

Uso: montar_aula.py aula.json edl
     montar_aula.py aula.json render [--ate T] [--only 3,13] [--jobs N]
     montar_aula.py aula.json concat SAIDA.mp4 [--ate T]
     montar_aula.py aula.json map T            # tempo do corte -> tempo final (com as cartelas)

aula.json (campos principais; exemplo completo em ../templates/aula-exemplo.json):
  corte, cenas_corte, identidade, manim, mattes, blocos      caminhos
  capitulos: [{"n":1, "titulo":"...", "inicio": 19.75}]      cartela entra ANTES de `inicio` (tempo do corte)
  cartela_dur: 2.6                                           duração do separador
  diagramas: [{"cena":"D1Fluxo", "inicio":25.1, "fim":53.3}] cenas Manim (.mov com alpha) por trecho de quadro
  circulo: {"cx":1596, "cy":827, "r":186}                    webcam circular na gravação
  codigo_grupos: [{"grupo":"A", "orig_ini":266, "orig_fim":392}]   grupos de recorte (geometria em identidade/l3_geo.json)
  abertura/encerramento: {"cena":"Abertura", "xoff":380}     overlays Manim do 1º e do último trecho de locutor
Só biblioteca padrão + ffmpeg. Codificador por VE_ENCODER (libx264 padrão; h264_nvenc etc. em máquina com GPU).
"""
import json, os, shlex, subprocess, sys

sys.path.insert(0, os.environ.get("VE_PKG_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
from video_editores.nucleo.ffmpeg import codec_video  # noqa: E402

FPS = 30
ENC = [*codec_video(crf=18), "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
CIRC = {"l2": dict(size=420, pos=(1452, 632), ring=(1412, 592)), "l3": dict(size=444, pos=(1404, 190), ring=(1364, 150))}


class Aula:
    def __init__(self, cfg_path):
        self.cfg = json.load(open(cfg_path, encoding="utf-8"))
        c = self.cfg
        self.root = os.path.dirname(os.path.abspath(cfg_path))
        os.chdir(self.root)
        self.cut = c["corte"]; self.ident = c["identidade"]; self.man = c["manim"]; self.blocos = c.get("blocos", "blocos")
        os.makedirs(self.blocos, exist_ok=True)
        self.cenas = json.load(open(c["cenas_corte"], encoding="utf-8"))
        self.sep = {k["n"]: k["inicio"] for k in c["capitulos"]}
        self.sep_dur = c.get("cartela_dur", 2.6)
        self.diag = [(d["cena"], d["inicio"], d["fim"]) for d in c.get("diagramas", [])]
        self.grupos = c.get("codigo_grupos", [])
        geo_path = os.path.join(self.ident, "l3_geo.json")
        self.geo = json.load(open(geo_path, encoding="utf-8")) if os.path.exists(geo_path) else {}
        self.kinds = c.get("modos", {"locutor": "locutor", "quadro": "quadro", "codigo": "codigo"})

    # ---- utilidades
    def capitulo(self, t):
        n = 0
        for k, s in self.sep.items():
            if t >= s - 0.02: n = k
        return max(n, 1)

    def hq(self, scene):
        for sub in ("diagramas", "cartelas"):
            p = f"{self.man}/{sub}/1080p30/{scene}.mov"
            if os.path.exists(p): return p
        for sub in ("diagramas", "cartelas"):
            p = f"{self.man}/{sub}/540p30/{scene}.mov"
            if os.path.exists(p): return p
        raise SystemExit(f"cena Manim não encontrada: {scene} (renderize em {self.man}/<diagramas|cartelas>/1080p30/)")

    def map_time(self, t):
        return t + sum(self.sep_dur for s in self.sep.values() if t >= s - 0.02)

    # ---- EDL
    def edl(self):
        def snap(t):
            return round(round(t * FPS) / FPS, 4)
        pts = [c["cut_start"] for c in self.cenas] + [c["cut_end"] for c in self.cenas] + list(self.sep.values())
        pts += [d[1] for d in self.diag] + [d[2] for d in self.diag]
        cuts = sorted(set(snap(t) for t in pts))
        K = self.kinds; blocks = []
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b - a < 0.05: continue
            c = next((x for x in self.cenas if x["cut_start"] - 0.02 <= a < x["cut_end"] - 0.02), None)
            if c is None:
                if b - a < 0.25: continue
                raise SystemExit(f"sem cena para {a}-{b}")
            blk = {"a": round(a, 4), "b": round(b, 4), "kind": c["kind"], "cap": self.capitulo(a)}
            if c["kind"] == K["locutor"]:
                blk["matte"] = f"{self.cfg.get('mattes', 'mattes')}/talk_{int(c['cut_start']):05d}"; blk["matte_t0"] = c["cut_start"]
            elif c["kind"] == K["quadro"]:
                d = next((d for d in self.diag if d[1] - 0.02 <= a < d[2] - 0.02), None)
                blk["scene"] = d[0] if d else None; blk["scene_t0"] = d[1] if d else a
            else:
                og = c["start"] + (a - c["cut_start"])
                g = next((g for g in self.grupos if g["orig_ini"] - 1 <= og <= g["orig_fim"] + 1), None)
                blk["grupo"] = g["grupo"] if g else (self.grupos[0]["grupo"] if self.grupos else "A")
            blocks.append(blk)
        out = []; usados = set()
        for blk in blocks:
            for n, s in self.sep.items():          # cartela antes do PRIMEIRO bloco em s (tolera lacuna de até 0,3 s)
                if n not in usados and s - 0.02 <= blk["a"] < s + 0.3:
                    out.append({"kind": "sep", "n": n, "a": s, "b": s, "dur": self.sep_dur}); usados.add(n)
            out.append(blk)
        faltam = set(self.sep) - usados
        if faltam: raise SystemExit(f"cartelas sem bloco correspondente (confira capitulos[].inicio): {sorted(faltam)}")
        ultimo = self.cenas[-1]["cut_end"]
        for blk in out:
            if blk["kind"] == K["locutor"] and blk["a"] == 0.0 and "abertura" in self.cfg: blk["kind"] = "abertura"
            if blk["kind"] == K["locutor"] and blk["b"] >= ultimo - 0.02 and "encerramento" in self.cfg: blk["kind"] = "encerramento"
        return out

    # ---- render
    def ff(self, args, desc):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("ERRO em", desc, "\n", " ".join(shlex.quote(c) for c in cmd), "\n", r.stderr[-3000:]); sys.exit(1)

    def circle_chain(self, src, tag, out):
        c = CIRC[tag]; ci = self.cfg["circulo"]; d = 2 * ci["r"]
        return (f"[{src}]crop={d}:{d}:{ci['cx'] - ci['r']}:{ci['cy'] - ci['r']},scale={c['size']}:{c['size']}[cf];"
                f"movie={self.ident}/circmask_{tag}.png[cm];[cf][cm]alphamerge[{out}]")

    def render_block(self, i, blk):
        out = f"{self.blocos}/{i:03d}_{blk['kind']}.mp4"
        a, b = blk["a"], blk["b"]; dur = b - a; k = blk["kind"]; K = self.kinds
        fundo = f"{self.ident}/fundo.png"; sfx = self.cfg.get("whoosh", "sfx/whoosh.wav")
        if k == "sep":
            self.ff(["-loop", "1", "-framerate", str(FPS), "-i", fundo, "-i", self.hq(f"Separador{blk['n']}"), "-i", sfx,
                     "-filter_complex", "[1:v]scale=1920:1080[s];[0:v][s]overlay=0:0:shortest=1[v];[2:a]apad[a]",
                     "-map", "[v]", "-map", "[a]", "-t", f"{blk['dur']:.3f}", *ENC, out], out)
        elif k == K["locutor"]:
            t0 = a - blk["matte_t0"]
            self.ff(["-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", blk["matte"] + ".mp4", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", self.cut,
                     "-map", "0:v", "-map", "1:a", *ENC, out], out)
        elif k in ("abertura", "encerramento"):
            ov = self.cfg[k]; t0 = a - blk["matte_t0"]; xoff = ov.get("xoff", 380)
            self.ff(["-loop", "1", "-framerate", str(FPS), "-i", fundo,
                     "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", self.cut,
                     "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", blk["matte"] + "_alpha.mp4", "-i", self.hq(ov["cena"]),
                     "-filter_complex",
                     f"[2:v]format=gray,scale=1920:1080,split[al1][al2];[al1]boxblur=22:2,lut=y=val*0.6[sh];"
                     f"color=black:s=1920x1080:r={FPS}[blk];[blk][sh]alphamerge[shadow];[1:v]format=rgba[p0];[p0][al2]alphamerge[person];"
                     f"[0:v][shadow]overlay={xoff}:24:shortest=1[b1];[b1][person]overlay={xoff}:0[b2];[3:v]scale=1920:1080[ov];[b2][ov]overlay=0:0:eof_action=pass[v]",
                     "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", *ENC, out], out)
        elif k == K["quadro"]:
            if not blk["scene"]:
                raise SystemExit(f"trecho de quadro {a}-{b} sem diagrama em aula.json")
            off = a - blk["scene_t0"]; c2 = CIRC["l2"]
            self.ff(["-loop", "1", "-framerate", str(FPS), "-i", fundo, "-ss", f"{off:.3f}", "-t", f"{dur:.3f}", "-i", self.hq(blk["scene"]),
                     "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", self.cut, "-i", f"{self.ident}/chip_{blk['cap']}.png", "-i", f"{self.ident}/ring_l2.png",
                     "-filter_complex",
                     "[1:v]scale=1920:1080[dg];[0:v][dg]overlay=0:0:shortest=1:eof_action=pass[b1];" + self.circle_chain("2:v", "l2", "circ") +
                     f";[b1][circ]overlay={c2['pos'][0]}:{c2['pos'][1]}[b2];[b2][4:v]overlay={c2['ring'][0]}:{c2['ring'][1]}[b3];[b3][3:v]overlay=0:0[v]",
                     "-map", "[v]", "-map", "2:a", "-t", f"{dur:.3f}", *ENC, out], out)
        else:  # código
            g = self.geo[blk["grupo"]]; cw, ch, cx, cy = g["crop"]; pw, ph = g["scale"]; px, py = g["pos"]; rx = g["right_col_x"]; c3 = CIRC["l3"]
            self.ff(["-loop", "1", "-framerate", str(FPS), "-i", f"{self.ident}/l3_base_{blk['grupo']}.png",
                     "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", self.cut, "-i", f"{self.ident}/l3_cover_{blk['grupo']}.png",
                     "-i", f"{self.ident}/ring_l3.png", "-i", f"{self.ident}/chip_{blk['cap']}.png",
                     "-filter_complex",
                     f"[1:v]split[v1][v2];[v1]crop={cw}:{ch}:{cx}:{cy},scale={pw}:{ph}:flags=lanczos[panel];"
                     f"[0:v][panel]overlay={px}:{py}:shortest=1[b1];[b1][2:v]overlay=0:0[b2];" + self.circle_chain("v2", "l3", "circ") +
                     f";[b2][circ]overlay={c3['pos'][0]}:{c3['pos'][1]}[b3];[b3][3:v]overlay={c3['ring'][0]}:{c3['ring'][1]}[b4];"
                     f"[4:v]crop=iw-72:ih:72:0[chip];[b4][chip]overlay={rx}:0[v]",
                     "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", *ENC, out], out)
        return out

    def concat(self, E, saida, ate):
        lst = f"{self.blocos}/lista.txt"
        with open(lst, "w") as f:
            for i, b in enumerate(E):
                if b["a"] >= ate: break
                f.write(f"file '{i:03d}_{b['kind']}.mp4'\n")
        self.ff(["-f", "concat", "-safe", "0", "-i", lst, "-map", "0:v", "-c", "copy", f"{self.blocos}/_video.mp4"], "concat vídeo")
        parts = []; ins = ""; n = 0; sfx = self.cfg.get("whoosh", "sfx/whoosh.wav")
        for i, b in enumerate(E):                      # mesma sequência dos blocos de vídeo: áudio nunca diverge
            if b["a"] >= ate: break
            if b["kind"] == "sep":
                parts.append(f"[1:a]atrim=0:{b['dur']},apad=whole_dur={b['dur']},asetpts=PTS-STARTPTS[w{i}];"); ins += f"[w{i}]"
            else:
                parts.append(f"[0:a]atrim={b['a']:.4f}:{b['b']:.4f},asetpts=PTS-STARTPTS[s{i}];"); ins += f"[s{i}]"
            n += 1
        fc = "".join(parts) + f"{ins}concat=n={n}:v=0:a=1,aresample=48000[a]"
        self.ff(["-i", self.cut, "-i", sfx, "-filter_complex", fc, "-map", "[a]", "-c:a", "pcm_s16le", f"{self.blocos}/_audio.wav"], "áudio contínuo")
        self.ff(["-i", f"{self.blocos}/_video.mp4", "-i", f"{self.blocos}/_audio.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", saida], "mux")
        def pr(st):
            return subprocess.run(["ffprobe", "-v", "error", "-select_streams", st, "-show_entries", "stream=duration", "-of", "csv=p=0", saida],
                                  capture_output=True, text=True).stdout.strip()
        print("ok", saida, "vídeo", pr("v"), "áudio", pr("a"))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    aula = Aula(sys.argv[1]); cmd = sys.argv[2]; E = aula.edl()
    ate = float(sys.argv[sys.argv.index("--ate") + 1]) if "--ate" in sys.argv else 1e9
    only = set(int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    if cmd == "edl":
        tf = 0
        for i, b in enumerate(E):
            d = b["dur"] if b["kind"] == "sep" else b["b"] - b["a"]
            print(f"{i:3d} {b['kind']:12s} {b['a']:8.2f}-{b['b']:8.2f} ({d:6.2f}s) final {tf:8.2f} cap{b.get('cap', b.get('n'))} "
                  f"{b.get('scene') or b.get('grupo') or b.get('matte', '')}")
            tf += d
        print(f"duração final: {tf:.1f}s ({tf / 60:.1f} min)")
    elif cmd == "render":
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 1
        fila = []
        for i, b in enumerate(E):
            if b["a"] >= ate: break
            if only is not None and i not in only: continue
            if os.path.exists(f"{aula.blocos}/{i:03d}_{b['kind']}.mp4.ok"): continue
            fila.append((i, b))
        def um(ib):
            i, b = ib; out = aula.render_block(i, b); open(out + ".ok", "w").close(); print("ok", out, flush=True)
        if jobs > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=jobs) as ex:
                list(ex.map(um, fila))     # cada bloco é um ffmpeg independente; --jobs = núcleos/4
        else:
            for ib in fila: um(ib)
    elif cmd == "concat":
        aula.concat(E, sys.argv[3], ate)
    elif cmd == "map":
        print(f"{aula.map_time(float(sys.argv[3])):.3f}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
