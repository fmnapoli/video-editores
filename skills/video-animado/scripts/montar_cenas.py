"""Monta o vídeo 100% animado: cenas do Manim + narração + legenda queimada + loudnorm.

Uso:
  python3 montar_cenas.py cenas/<slug>.json <pasta dos mp4 do Manim> [--saida saida/<slug>.mp4]
      [--legenda legendas/<slug>.srt] [--tts trabalho/<slug>/tts] [--cenas B1,B2,B3]
      [--fonte "DejaVu Sans Bold"] [--tamanho 15] [--margem 22] [--loudness -16] [--roteiro roteiros/roteiro-<slug>.md]

- Os mp4 têm o nome do id da cena (<pasta>/B1.mp4). A sincronia usa a duração REAL de cada mp4:
  o áudio da cena é atrasado em `lead` e preenchido até ela, então um frame a mais ou a menos no
  Manim não desloca a legenda.
- A legenda vem das fronteiras de palavra do edge-tts (sem pontuação e com a grafia do glossário);
  a grafia original da narração é recuperada casando os tokens um a um. Blocos de até 2 linhas de
  ~42 caracteres, frase a frase, sem linha órfã.
- Saída: libx264 crf 18, aac 192k a 48 kHz, `.srt` em pasta separada do `.mp4`.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "video-docs", "scripts"))
import pronuncia  # noqa: E402

LINHA_MAX = 42
LINHAS_MAX = 2


def sh(*cmd):
    subprocess.run(cmd, check=True)


def duracao(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _chave(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(ch for ch in t if ch.isalnum())


def com_grafia_original(words, narracao, gloss):
    """Troca a palavra falada (sem pontuação, com glossário) pelo token original da narração."""
    orig = narracao.split()
    fal = pronuncia.apply(narracao, gloss).split()
    if len(fal) != len(orig):
        fal = orig
    i, out = 0, []
    for w in words:
        k = _chave(w["w"])
        j = i
        while j < len(fal) and j < i + 3 and not _chave(fal[j]).startswith(k[:3] or k):
            j += 1
        if j < len(fal) and j < i + 3:
            out.append({**w, "w": orig[j]})
            i = j + 1
        else:
            out.append(w)
    return out


def _flui(palavras, largura):
    linhas, linha = [], []
    for w in palavras:
        if linha and len(" ".join([x["w"] for x in linha] + [w["w"]])) > largura:
            linhas.append(linha)
            linha = []
        linha.append(w)
    if linha:
        linhas.append(linha)
    return linhas


def blocos(words):
    """Blocos de até 2 linhas. Cada frase é fluída na largura que evita linha órfã no fim."""
    frases, atual = [], []
    for w in words:
        atual.append(w)
        if re.search(r"[.;:!?]$", w["w"]):
            frases.append(atual)
            atual = []
    if atual:
        frases.append(atual)
    out = []
    for fr in frases:
        melhor = None
        for larg in (LINHA_MAX, 39, 36, 33, 30):
            ls = _flui(fr, larg)
            ultima = len(" ".join(x["w"] for x in ls[-1]))
            pena = (len(ls) % 2) * 2 + (ultima < 0.45 * larg) * 3 + (LINHA_MAX - larg) * 0.1
            if melhor is None or pena < melhor[0]:
                melhor = (pena, ls)
        ls = melhor[1]
        for i in range(0, len(ls), LINHAS_MAX):
            par = ls[i:i + LINHAS_MAX]
            ini, fim = par[0][0]["t"], par[-1][-1]["t"] + par[-1][-1]["d"]
            out.append((ini, fim, [" ".join(x["w"] for x in li) for li in par]))
    return out


def carrega_spec(caminho):
    spec = json.load(open(caminho, encoding="utf-8"))
    if isinstance(spec, list):
        spec = {"cenas": spec}
    spec.setdefault("slug", os.path.splitext(os.path.basename(caminho))[0])
    return spec


def roteiro_md(spec, cenas, tempos, gloss, srt_blocos, saida, legenda):
    soma = sum(tempos[c["id"]]["total"] for c in cenas)
    out = [f"# {spec.get('titulo') or spec['slug']}: roteiro final\n",
           f"- **Vídeo:** `{saida}`; legenda em `{legenda}`.",
           f"- **Voz:** {spec.get('voice', 'pt-BR-ThalitaMultilingualNeural')}; glossário só no texto falado.",
           f"- **Duração:** {int(soma // 60)} min {soma % 60:02.0f} s, {len(cenas)} cenas.\n", "## Cenas\n"]
    t0 = 0.0
    for c in cenas:
        cid, tot = c["id"], tempos[c["id"]]["total"]
        out.append(f"### {cid}. {c.get('titulo') or '(sem título)'}  ·  {int(t0 // 60):02d}:{t0 % 60:04.1f}–{int((t0 + tot) // 60):02d}:{(t0 + tot) % 60:04.1f}")
        if c.get("narracao"):
            out.append(f"**Narração:** {c['narracao']}\n")
            falado = pronuncia.apply(c.get("tts") or c["narracao"], gloss)
            if falado != c["narracao"]:
                out.append(f"**Falado (glossário):** {falado}\n")
            out.append("**Legenda:**\n```")
            for linhas in srt_blocos.get(cid, []):
                out.append("\n".join(linhas))
                out.append("")
            out.append("```\n")
        else:
            out.append(f"Sem narração ({tot:.1f} s).\n")
        t0 += tot
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("pasta", help="pasta com <id>.mp4 renderizados pelo Manim")
    ap.add_argument("--saida", help="padrão saida/<slug>.mp4")
    ap.add_argument("--legenda", help="padrão legendas/<slug>.srt")
    ap.add_argument("--tts", help="padrão trabalho/<slug>/tts")
    ap.add_argument("--cenas", help="ids separados por vírgula (piloto); padrão todas")
    ap.add_argument("--glossario", help="o mesmo JSON passado ao tts_cenas.py")
    ap.add_argument("--fonte", default="DejaVu Sans Bold")
    ap.add_argument("--tamanho", type=int, default=15, help="FontSize na escala 288 (15 = ~56 px em 1080p)")
    ap.add_argument("--margem", type=int, default=22, help="MarginV na escala 288 (22 = ~82 px em 1080p)")
    ap.add_argument("--loudness", type=float, default=-16.0)
    ap.add_argument("--sem-legenda", action="store_true")
    ap.add_argument("--roteiro", help="grava o roteiro final em markdown neste caminho")
    a = ap.parse_args()

    spec = carrega_spec(a.spec)
    slug = spec["slug"]
    tts_dir = a.tts or os.path.join("trabalho", slug, "tts")
    tempos = json.load(open(os.path.join(tts_dir, "tempos.json"), encoding="utf-8"))
    voz = spec.get("voice", "pt-BR-ThalitaMultilingualNeural")
    gloss = pronuncia.load(a.glossario or spec.get("glossary"), base_dir=os.path.dirname(os.path.abspath(a.spec)), voice=voz)
    cenas = spec["cenas"]
    if a.cenas:
        ids = a.cenas.split(",")
        cenas = [c for c in cenas if c["id"] in ids]
    saida = a.saida or os.path.join("saida", f"{slug}.mp4")
    legenda = a.legenda or os.path.join("legendas", f"{slug}.srt")
    trab = os.path.join("trabalho", slug, "montagem")
    os.makedirs(trab, exist_ok=True)
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(legenda) or ".", exist_ok=True)

    lista, audios, srt, por_cena, n, t0 = [], [], [], {}, 1, 0.0
    for c in cenas:
        cid = c["id"]
        mp4 = os.path.abspath(os.path.join(a.pasta, f"{cid}.mp4"))
        vd = duracao(mp4)
        info = tempos[cid]
        wav = os.path.join(trab, f"{cid}.wav")
        if info.get("mudo"):
            sh("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{vd:.3f}", wav)
        else:
            ms = int(info["lead"] * 1000)
            sh("ffmpeg", "-v", "error", "-y", "-i", os.path.join(tts_dir, f"{cid}.mp3"),
               "-af", f"adelay={ms}|{ms},apad=whole_dur={vd:.3f},atrim=0:{vd:.3f}", "-ar", "48000", "-ac", "2", wav)
            words = json.load(open(os.path.join(tts_dir, f"{cid}.words.json"), encoding="utf-8"))
            bl = blocos(com_grafia_original(words, c.get("tts") or c["narracao"], gloss))
            por_cena[cid] = [linhas for _, _, linhas in bl]
            for i, (ini, fim, linhas) in enumerate(bl):
                ia = t0 + info["lead"] + ini
                ib = t0 + info["lead"] + fim + 0.25
                if i + 1 < len(bl):
                    ib = min(ib, t0 + info["lead"] + bl[i + 1][0] - 0.05)
                ib = max(ib, ia + 0.9)
                srt.append(f"{n}\n{srt_time(ia)} --> {srt_time(ib)}\n" + "\n".join(linhas) + "\n")
                n += 1
        lista.append(f"file '{mp4}'")
        audios.append(wav)
        print(f"{cid}: vídeo {vd:6.2f}s  (narração {info['total']:.2f}s)")
        t0 += vd

    with open(os.path.join(trab, "lista.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lista) + "\n")
    srt_txt = "\n".join(srt)
    with open(legenda, "w", encoding="utf-8") as f:
        f.write(srt_txt)
    srt_local = os.path.join(trab, "legenda.srt")
    with open(srt_local, "w", encoding="utf-8") as f:
        f.write(srt_txt)
    sh("ffmpeg", "-v", "error", "-y", *sum([["-i", w] for w in audios], []),
       "-filter_complex", "".join(f"[{i}:a]" for i in range(len(audios))) + f"concat=n={len(audios)}:v=0:a=1[a]",
       "-map", "[a]", os.path.join(trab, "narracao.wav"))
    estilo = (f"FontName={a.fonte},FontSize={a.tamanho},PrimaryColour=&H00FFFFFF,BorderStyle=4,"
              f"BackColour=&H66000000,Outline=0,Shadow=0,MarginV={a.margem},Alignment=2")
    vf = [] if (a.sem_legenda or not srt) else ["-vf", f"subtitles={srt_local.replace(chr(92), '/')}:force_style='{estilo}'"]
    sh("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(trab, "lista.txt"),
       "-i", os.path.join(trab, "narracao.wav"), *vf,
       "-af", f"loudnorm=I={a.loudness}:TP=-1.5:LRA=11", "-ar", "48000",
       "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", saida)
    if a.roteiro:
        os.makedirs(os.path.dirname(a.roteiro) or ".", exist_ok=True)
        with open(a.roteiro, "w", encoding="utf-8") as f:
            f.write(roteiro_md(spec, cenas, tempos, gloss, por_cena, saida, legenda))
    print(f"ok: {saida} ({duracao(saida):.1f}s), legenda em {legenda}" + (f", roteiro em {a.roteiro}" if a.roteiro else ""))


if __name__ == "__main__":
    main()
