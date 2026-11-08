#!/usr/bin/env python3
"""Converte tempos do vídeo original para o vídeo cortado, usando o JSON `--export v1` do auto-editor.

Entradas: o v1 json (chunks [ini_frame, fim_frame, speed]; speed 1 = mantido), o mapa de cenas do
original (lista de {start, end, kind, ...}) e a transcrição do transcribe.py.
Saídas (em --out): cenas_corte.json (cenas remapeadas e fundidas por tipo) e transcript_corte.json
(palavras com tempos no corte; palavras cortadas somem).

Uso: remap_tempos.py CORTE.v1.json cenas.json VIDEO.transcript.json [--out PASTA] [--fps 30]
Só biblioteca padrão.
"""
import argparse, bisect, json, os


class Remap:
    def __init__(self, v1_path, fps=30.0):
        self.fps = fps
        self.chunks = [c for c in json.load(open(v1_path, encoding="utf-8"))["chunks"] if c[2] == 1]
        self.starts = [c[0] for c in self.chunks]
        self.acc, t = [], 0
        for c in self.chunks:
            self.acc.append(t); t += c[1] - c[0]
        self.total = t / fps

    def to_cut(self, sec):
        """Tempo original -> tempo no corte. Dentro de trecho removido, vai para o início do próximo mantido."""
        f = sec * self.fps
        i = bisect.bisect_right(self.starts, f) - 1
        if i >= 0 and self.chunks[i][0] <= f < self.chunks[i][1]:
            return (self.acc[i] + (f - self.chunks[i][0])) / self.fps
        j = i + 1
        return self.acc[j] / self.fps if j < len(self.chunks) else self.total

    def kept(self, a, b):
        """Segundos mantidos entre a e b (original)."""
        fa, fb, s = a * self.fps, b * self.fps, 0
        for c in self.chunks:
            lo, hi = max(fa, c[0]), min(fb, c[1])
            if hi > lo: s += hi - lo
        return s / self.fps


def remap_cenas(rm, cenas):
    out = []
    for c in cenas:
        k = rm.kept(c["start"], c["end"])
        if k < 0.2: continue
        a = rm.to_cut(c["start"])
        out.append({**c, "cut_start": round(a, 3), "cut_end": round(a + k, 3), "cut_len": round(k, 3)})
    merged = []
    for c in out:
        if merged and merged[-1]["kind"] == c["kind"] and abs(merged[-1]["cut_end"] - c["cut_start"]) < 0.05:
            merged[-1]["cut_end"] = c["cut_end"]; merged[-1]["end"] = c["end"]
            merged[-1]["cut_len"] = round(merged[-1]["cut_end"] - merged[-1]["cut_start"], 3)
        else:
            merged.append(dict(c))
    return merged


def remap_transcript(rm, tr):
    segs = []
    for s in tr["segments"]:
        ws = []
        for w in s.get("words", []):
            dur = max(0.01, w["end"] - w["start"])
            if rm.kept(w["start"], w["end"]) < 0.5 * dur: continue
            ws.append({"word": w["word"], "start": round(rm.to_cut(w["start"]), 3),
                       "end": round(rm.to_cut(w["end"]), 3), "orig_start": w["start"]})
        if ws:
            segs.append({"start": ws[0]["start"], "end": ws[-1]["end"],
                         "text": "".join(w["word"] for w in ws).strip(), "words": ws})
    return {"duration": rm.total, "segments": segs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("v1"); ap.add_argument("cenas"); ap.add_argument("transcript")
    ap.add_argument("--out", default="."); ap.add_argument("--fps", type=float, default=30.0)
    a = ap.parse_args()
    rm = Remap(a.v1, a.fps)
    cenas = remap_cenas(rm, json.load(open(a.cenas, encoding="utf-8")))
    tr = remap_transcript(rm, json.load(open(a.transcript, encoding="utf-8")))
    os.makedirs(a.out, exist_ok=True)
    json.dump(cenas, open(os.path.join(a.out, "cenas_corte.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(tr, open(os.path.join(a.out, "transcript_corte.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(os.path.join(a.out, "transcript_corte.txt"), "w", encoding="utf-8") as f:
        for s in tr["segments"]:
            f.write(f"[{s['start']:7.2f}-{s['end']:7.2f}] {s['text']}\n")
    print(f"corte: {rm.total:.1f}s; cenas: {len(cenas)}; segmentos: {len(tr['segments'])}")
    for c in cenas:
        print(f"{c['kind']:10s} {c['cut_start']:8.1f} -> {c['cut_end']:8.1f} ({c['cut_len']:6.1f}s)  orig {c['start']:.0f}-{c['end']:.0f}")


if __name__ == "__main__":
    main()
