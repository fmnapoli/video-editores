"""Andamento e fase do compasso de um clipe de bateria, para o exemplo tocado soar como o que a pessoa toca.

Uso:
  uv run --with librosa --with numpy --with scipy --with soundfile python andamento.py CLIPE [CLIPE ...]
      [--ini S] [--fim S] [--faixa 70-160] [--tempos N] [--bumbo 0,3] [--out beats.json]

Para cada clipe (vídeo ou áudio; o ffmpeg decodifica) imprime o bpm e grava um JSON:
  {clipe: {"bpm": mediana dos intervalos entre batidas (o número a passar no tocar.py --bpm),
           "bpm_tracker": estimativa global do beat tracker, "beats": [...] instantes das batidas,
           "n": tempos por compasso, "fase": índice da primeira batida que é o "1", "contraste": razão,
           "confiavel": contraste >= 1.3, "uns": instantes dos "1"}}
A mediana dos intervalos é mais estável que a estimativa global quando o andamento oscila (caso real: campo
`tempo` a 92, mediana a 96). `--faixa` dobra ou divide o bpm que cair fora dela (ambiguidade de oitava do tracker).
`--tempos` e `--bumbo` escolhem o "1" pela energia grave (40–110 Hz) nas posições onde o bumbo toca:
--tempos 7 --bumbo 0,3 para um 7/4 com bumbo no 1 e no 4. Sem `--tempos`, só o andamento.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

SR = 22050
HOP = 256                                  # 11,6 ms por quadro de análise


def decodifica(caminho, ini, fim, destino):
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if ini:
        cmd += ["-ss", f"{ini:.3f}"]
    cmd += ["-i", caminho]
    if fim:
        cmd += ["-t", f"{max(0.0, fim - (ini or 0.0)):.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", destino]
    subprocess.run(cmd, check=True)


def dobra_na_faixa(bpm, lo, hi):
    while bpm and bpm < lo:
        bpm *= 2
    while bpm and bpm > hi:
        bpm /= 2
    return bpm


def analisa(y, faixa, n, bumbo):
    import librosa
    from scipy.signal import butter, sosfilt

    lo, hi = faixa
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    tempo, frames = librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=HOP, start_bpm=(lo + hi) / 2, units="frames")
    bt = librosa.frames_to_time(frames, sr=SR, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    out = {"bpm_tracker": round(dobra_na_faixa(tempo, lo, hi), 1), "beats": [round(float(t), 3) for t in bt]}
    if len(bt) < 6:
        out["bpm"] = out["bpm_tracker"]
        out["aviso"] = "menos de 6 batidas detectadas; andamento pouco confiável"
        return out
    # mediana dos intervalos medidos sobre 4 batidas: robusta a uma batida perdida e 4× menos sensível ao grid de quadros
    ibi = (bt[4:] - bt[:-4]) / 4
    out["bpm"] = round(dobra_na_faixa(60.0 / float(np.median(ibi)), lo, hi), 1)
    out["bpm_desvio"] = round(float(60.0 / np.percentile(ibi, 25) - 60.0 / np.percentile(ibi, 75)), 1)
    if not n:
        return out
    grave = sosfilt(butter(4, [40, 110], btype="band", fs=SR, output="sos"), y)
    og = librosa.onset.onset_strength(y=grave, sr=SR, hop_length=HOP)
    fr = librosa.time_to_frames(bt, sr=SR, hop_length=HOP)
    forca = np.array([og[max(0, f - 4):f + 5].max() if f < len(og) else 0.0 for f in fr])   # ±46 ms em volta da batida
    contrastes = []
    for fase in range(n):
        alvo = [k for k in range(len(bt)) if (k - fase) % n in bumbo]
        resto = [k for k in range(len(bt)) if (k - fase) % n not in bumbo]
        c = float(forca[alvo].mean() / max(1e-6, forca[resto].mean())) if alvo and resto else 0.0
        contrastes.append(round(c, 2))
    fase = int(np.argmax(contrastes))
    c = contrastes[fase]
    segundo = max([x for i, x in enumerate(contrastes) if i != fase], default=0.0)
    # confiável: o "1" escolhido se destaca (>= 1,3) e a segunda melhor fase fica claramente atrás
    out.update({"n": n, "fase": fase, "contraste": c, "contrastes": contrastes,
                "confiavel": c >= 1.3 and c >= 1.1 * segundo,
                "uns": [round(float(bt[k]), 3) for k in range(fase, len(bt), n)]})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("clipes", nargs="+", help="vídeo ou áudio")
    ap.add_argument("--ini", type=float, default=0.0, help="início do trecho analisado (s)")
    ap.add_argument("--fim", type=float, default=0.0, help="fim do trecho (s; 0 = até o fim)")
    ap.add_argument("--faixa", default="70-160", help="faixa de bpm plausível; fora dela dobra/divide (padrão 70-160)")
    ap.add_argument("--tempos", type=int, default=0, help="tempos por compasso, para achar o 1 (4, 5, 7...)")
    ap.add_argument("--bumbo", default="0", help="posições do compasso (0 = o 1) em que o bumbo toca, ex. 0,3")
    ap.add_argument("--out", default="beats.json", help="JSON de saída (acrescenta aos clipes já medidos)")
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.faixa.split("-"))
    bumbo = [int(x) for x in a.bumbo.split(",") if x.strip() != ""]
    if a.tempos and any(b >= a.tempos for b in bumbo):
        sys.exit(f"--bumbo {a.bumbo} fora do compasso de {a.tempos} tempos")

    import soundfile as sf
    res = {}
    if os.path.exists(a.out):
        try:
            res = json.load(open(a.out, encoding="utf-8"))
        except (OSError, ValueError):
            res = {}
    with tempfile.TemporaryDirectory() as td:
        for clipe in a.clipes:
            wav = os.path.join(td, "a.wav")
            decodifica(clipe, a.ini, a.fim, wav)
            y, _ = sf.read(wav, dtype="float32", always_2d=False)
            if y.ndim > 1:
                y = y.mean(axis=1)
            r = analisa(y, (lo, hi), a.tempos, bumbo)
            r["trecho"] = [a.ini, a.fim]
            nome = os.path.splitext(os.path.basename(clipe))[0]
            res[nome] = r
            extra = f"  tracker {r['bpm_tracker']}  ±{r.get('bpm_desvio', 0)}"
            if a.tempos:
                extra += f"  fase {r['fase']}/{a.tempos}  contraste {r['contraste']}" + ("" if r["confiavel"] else "  (fase NÃO confiável)")
            print(f"{nome}: {r['bpm']} bpm{extra}" + (f"  AVISO: {r['aviso']}" if "aviso" in r else ""))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"ok {a.out}")


if __name__ == "__main__":
    main()
