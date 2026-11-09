"""Normaliza o áudio de um vídeo ou wav a um alvo LUFS com teto de pico real, e mede antes e depois.

Uso:
  python3 normalizar_audio.py ENTRADA SAIDA.mp4|SAIDA.wav [--alvo -14] [--tp -1.5] [--filtro "highpass=f=80,afftdn=nf=-25:nr=12"]
  python3 normalizar_audio.py ENTRADA --medir

Saída .wav: só o áudio (estéreo, 48 kHz). Saída de vídeo: o vídeo é copiado sem recodificar e o áudio
vai em AAC 192k. `--filtro` é uma cadeia ffmpeg aplicada antes (limpeza de sala). Ganho estático +
alimiter com oversampling, nunca loudnorm linear (ver video_editores/nucleo/audio.py).
"""
import argparse
import json
import os
import pathlib
import sys


def _raiz_pacote(arquivo):
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo import audio  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada")
    ap.add_argument("saida", nargs="?")
    ap.add_argument("--alvo", type=float, default=-14.0, help="LUFS integrado (-14 redes/YouTube, -16 docs)")
    ap.add_argument("--tp", type=float, default=-1.5, help="pico real máximo em dBTP")
    ap.add_argument("--filtro", help="cadeia ffmpeg aplicada antes (ex.: passa-alta + afftdn)")
    ap.add_argument("--medir", action="store_true", help="só mede e imprime JSON")
    a = ap.parse_args()
    if a.medir or not a.saida:
        print(json.dumps(audio.medir(a.entrada, a.filtro)))
        return
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    if a.saida.lower().endswith(".wav"):
        res = audio.normalizar(a.entrada, a.saida, a.alvo, a.tp, a.filtro)
    else:
        res = audio.normalizar_video(a.entrada, a.saida, a.alvo, a.tp, a.filtro)
    print(audio.resumo(res))
    if res["saida"]["TP"] > a.tp + 0.3:
        print(f"AVISO: pico real {res['saida']['TP']:.1f} dBTP ainda acima de {a.tp} dBTP", file=sys.stderr)
        sys.exit(3)
    print(f"ok -> {a.saida}")


if __name__ == "__main__":
    main()
