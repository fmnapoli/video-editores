"""Narração por cena com edge-tts para vídeos 100% animados (/video-animado).

Uso:
  uv run --with edge-tts python tts_cenas.py cenas/<slug>.json [--out trabalho/<slug>/tts]
      [--voz pt-BR-ThalitaMultilingualNeural] [--glossario glossario.json] [--lead 0.6] [--tail 0.8]

Spec: lista de cenas, ou {"slug", "voice", "glossary", "cenas": [...]}. Cada cena:
  {"id": "B1", "classe": "B1Salas", "titulo": "...", "narracao": "..."}   (cena narrada)
  {"id": "V1", "classe": "V1Vinheta", "duracao": 4.5}                     (cena muda)
  "tts" opcional: texto falado diferente da narração exibida.

Saída em <out>: <id>.mp3, <id>.words.json (fronteiras de palavra em segundos), <id>.dur e
tempos.json {id: {fala, total, lead, mudo}}. A duração da cena é lead + fala + tail: é ela que a
Scene do Manim precisa preencher. Cache pelo hash de voz + texto falado.

O glossário (pronuncia.py do video-docs) vale só para a fala; o montar_cenas.py devolve a grafia
original para a legenda. Com a voz multilíngue o glossário padrão não entra: passe --glossario.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "video-docs", "scripts"))
def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
import pronuncia  # noqa: E402
from video_editores import modelos  # noqa: E402
from video_editores.modelos.tts_edge import VOZ_PADRAO as VOZ  # noqa: E402


def carrega_spec(caminho):
    spec = json.load(open(caminho, encoding="utf-8"))
    if isinstance(spec, list):
        spec = {"cenas": spec}
    spec.setdefault("slug", os.path.splitext(os.path.basename(caminho))[0])
    return spec


def duracao(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def fala(texto, voz, mp3, words, backend=None):
    """Sintetiza com o backend de TTS configurado (VE_TTS, padrão edge-tts) e grava as fronteiras de palavra."""
    ws = modelos.get_tts(backend).sintetizar(texto, voz, mp3)
    with open(words, "w", encoding="utf-8") as f:
        json.dump(ws, f, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", help="pasta de saída (padrão trabalho/<slug>/tts)")
    ap.add_argument("--voz", help=f"voz do edge-tts (padrão {VOZ} ou 'voice' do spec)")
    ap.add_argument("--glossario", help="JSON {termo: pronúncia}; vale só para a fala")
    ap.add_argument("--lead", type=float, default=0.6, help="silêncio antes da fala (s)")
    ap.add_argument("--tail", type=float, default=0.8, help="silêncio depois da fala (s)")
    ap.add_argument("--backend", help="backend de TTS (padrão: VE_TTS ou edge)")
    a = ap.parse_args()

    spec = carrega_spec(a.spec)
    voz = a.voz or spec.get("voice") or VOZ
    gloss = pronuncia.load(a.glossario or spec.get("glossary"), base_dir=os.path.dirname(os.path.abspath(a.spec)), voice=voz)
    out = a.out or os.path.join("trabalho", spec["slug"], "tts")
    os.makedirs(out, exist_ok=True)
    tempos = {}
    for c in spec["cenas"]:
        cid = c["id"]
        if not c.get("narracao") and not c.get("tts"):
            total = float(c["duracao"])
            tempos[cid] = {"fala": 0.0, "total": total, "lead": 0.0, "mudo": True}
            print(f"{cid}: sem narração, cena {total:5.2f}s")
            continue
        texto = pronuncia.apply(c.get("tts") or c["narracao"], gloss)
        h = hashlib.sha1((voz + texto).encode("utf-8")).hexdigest()[:10]
        mp3, words, tag = (os.path.join(out, f"{cid}.{ext}") for ext in ("mp3", "words.json", "hash"))
        if not (os.path.exists(mp3) and os.path.exists(tag) and open(tag).read() == h):
            fala(texto, voz, mp3, words, a.backend)
            open(tag, "w").write(h)
        d = duracao(mp3)
        total = round(a.lead + d + a.tail, 2)
        tempos[cid] = {"fala": round(d, 2), "total": total, "lead": a.lead}
        print(f"{cid}: fala {d:5.2f}s  cena {total:5.2f}s")
    with open(os.path.join(out, "tempos.json"), "w", encoding="utf-8") as f:
        json.dump(tempos, f, indent=1)
    soma = sum(v["total"] for v in tempos.values())
    print(f"total: {int(soma // 60)} min {soma % 60:04.1f} s em {len(tempos)} cenas -> {out}/tempos.json")


if __name__ == "__main__":
    main()
