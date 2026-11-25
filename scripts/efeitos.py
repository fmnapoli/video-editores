#!/usr/bin/env python3
"""Efeitos sonoros a partir de eventos: o pico do som cai no evento, o nível segue a voz e o mesmo som não se repete.

Dois passos, com um arquivo revisável no meio:

1. Planejar: junta os eventos, escolhe um som para cada um e grava <nome>.sfx.json (sfx01, sfx02…).

     efeitos.py VIDEO --eventos ARQ [--eventos ARQ2 ...] [--sons PASTA] [--intervalo 2.0] [--ganho 0] [--out ARQ.sfx.json]

   --eventos aceita: o .camera.json do camera.py (corte com troca de plano → whoosh; punch → impacto), o
   textos.json do /lettering (entrada de cada texto → pop) e uma lista própria:
     [{"t": 12.3, "som": "riser", "forca": "leve|media|forte", "ganho": -3, "alinhar": "pico|inicio"}]
   Tempos sempre no relógio de VIDEO.

2. Aplicar: mixa os sons do .sfx.json sobre o áudio do vídeo (vídeo copiado, sem recodificar).

     efeitos.py VIDEO --aplicar ARQ.sfx.json SAIDA.mp4

Sons: whoosh, pop, clique, ding, impacto e riser são sintetizados pelo ffmpeg (sem baixar nada). Com
--sons PASTA, os arquivos de PASTA/<categoria>/ (ou PASTA/<categoria>-*.wav) têm preferência e são alternados.
Só biblioteca padrão + ffmpeg.
"""
import argparse
import array
import json
import math
import os
import pathlib
import subprocess
import sys


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo import audio  # noqa: E402
from video_editores.nucleo.ffmpeg import duracao  # noqa: E402

TAXA = 48000
JANELA = 480           # 10 ms: o pico é o da envoltória, não o de uma amostra solta (ruído tem amostra alta em qualquer lugar)
VOZ_PADRAO = -16.0     # LUFS assumido quando o vídeo não tem fala mensurável
TETO_DB = -3.0         # nenhum efeito passa disto, por mais alto que o plano peça
SEM_REPETIR_S = 20.0   # o mesmo arquivo não volta antes disto quando a pasta tem alternativa

# Sons sintetizados (fonte lavfi, filtro). Ruído com semente fixa: dois renders dão o mesmo arquivo.
SINTESE = {
    "whoosh": ("anoisesrc=d=0.5:c=pink:a=0.7:seed=7:r=48000",
               "highpass=f=300,lowpass=f=5000,afade=t=in:d=0.28,afade=t=out:st=0.28:d=0.22"),
    "pop": ("sine=f=900:d=0.08:r=48000", "afade=t=out:d=0.08"),
    "clique": ("anoisesrc=d=0.03:c=white:a=0.8:seed=11:r=48000", "highpass=f=2000,afade=t=out:d=0.03"),
    "ding": ("sine=f=1760:d=0.6:r=48000", "afade=t=out:d=0.6,aecho=0.8:0.5:40:0.3"),
    "impacto": ("aevalsrc=exprs='0.9*sin(2*PI*(45+90*exp(-t*25))*t)*exp(-t*7)':d=0.6:s=48000", "afade=t=out:st=0.45:d=0.15"),
    "riser": ("anoisesrc=d=1.2:c=pink:a=0.7:seed=3:r=48000",
              "highpass=f=500,volume='pow(t/1.2,2)':eval=frame,afade=t=out:st=1.18:d=0.02"),
}
# Pico do som no evento (whoosh, impacto, riser que termina nele) ou começo do som no evento (pop, clique, ding).
ALINHAR = {"whoosh": "pico", "impacto": "pico", "riser": "pico", "pop": "inicio", "clique": "inicio", "ding": "inicio"}
# Pico do efeito em relação ao loudness integrado da voz (dB). Ponto de partida: ajuste por --ganho ou por item.
NIVEL = {"whoosh": 3.0, "impacto": 6.0, "riser": 2.0, "pop": 2.0, "clique": 0.0, "ding": 2.0}
FORCA = {"leve": -4.0, "media": 0.0, "forte": 3.0}
DE_TIPO = {"corte": "whoosh", "punch": "impacto", "texto": "pop"}
AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".aif"}


def _amostras(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    a = array.array("h")
    a.frombytes(out[: len(out) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def envoltoria(a):
    """Soma do módulo em janelas de 10 ms."""
    return [sum(map(abs, a[i:i + JANELA])) for i in range(0, len(a), JANELA)]


def medir_som(path):
    """Duração, começo útil (sem o silêncio inicial), instante do pico da envoltória e pico em dBFS."""
    a = _amostras(path)
    if not a:
        sys.exit(f"{path}: sem áudio")
    env = envoltoria(a)
    topo = max(env)
    if topo == 0:
        sys.exit(f"{path}: só silêncio")
    ipico = env.index(topo)
    util = next(i for i, v in enumerate(env) if v >= 0.02 * topo)
    amp = max(max(a), -min(a))
    return {"dur": round(len(a) / TAXA, 3), "util": round(util * JANELA / TAXA, 3),
            "pico": round((ipico + 0.5) * JANELA / TAXA, 3), "pico_db": round(20 * math.log10(amp / 32768), 2)}


def sintetizar(nome, pasta):
    dest = pathlib.Path(pasta) / f"{nome}.wav"
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        fonte, filtro = SINTESE[nome]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", fonte, "-af", filtro, "-ar", str(TAXA),
                        "-c:a", "pcm_s16le", str(dest)], check=True)
    return dest


def biblioteca(pasta):
    """{categoria: [arquivos]} de PASTA/<categoria>/* e PASTA/<categoria>-*.ext (ou _)."""
    lib = {}
    if not pasta:
        return lib
    raiz = pathlib.Path(pasta)
    if not raiz.is_dir():
        sys.exit(f"--sons {pasta}: pasta não encontrada")
    for f in sorted(raiz.rglob("*")):
        if f.suffix.lower() not in AUDIO_EXT:
            continue
        cat = f.parent.name.lower() if f.parent != raiz else f.stem.lower().replace("_", "-").split("-")[0]
        lib.setdefault(cat, []).append(f)
    return lib


def ler_eventos(arquivos):
    evs = []
    for arq in arquivos:
        doc = json.loads(pathlib.Path(arq).read_text(encoding="utf-8"))
        if isinstance(doc, dict) and "eventos" in doc:                       # .camera.json
            evs += [dict(e, origem=e.get("de", e.get("tipo", ""))) for e in doc["eventos"]]
        elif isinstance(doc, list) and doc and all("start" in x for x in doc):   # textos.json do lettering
            evs += [{"t": float(x["start"]), "tipo": "texto", "origem": str(x.get("text", ""))[:30].replace("\\N", " ")} for x in doc]
        elif isinstance(doc, list):
            evs += [dict(e, origem=e.get("origem", "plano"), pedido=True) for e in doc]
        else:
            sys.exit(f"{arq}: não reconheço o formato (esperado .camera.json, textos.json ou lista de eventos com t)")
    for e in evs:
        if "t" not in e:
            sys.exit(f"evento sem t: {e}")
        e["t"] = float(e["t"])
    return sorted(evs, key=lambda e: e["t"])


def planejar(a):
    dur = duracao(a.video)
    try:
        voz = audio.medir(a.video)["I"]
    except Exception:
        voz = float("-inf")
    voz_medida = math.isfinite(voz) and voz > -50
    if not voz_medida:
        voz = VOZ_PADRAO
    lib = biblioteca(a.sons)
    src = pathlib.Path(a.video)
    out = pathlib.Path(a.out) if a.out else src.with_name(src.stem + ".sfx.json")
    pasta_sint = out.parent / "sfx"
    medidas, itens, pulados, ultimo_uso, ultimo_auto, rodizio = {}, [], [], {}, {}, {}

    for e in ler_eventos(a.eventos):
        som = (e.get("som") or DE_TIPO.get(e.get("tipo", ""), "")).lower()
        motivo = None
        if e.get("visivel") is False:
            motivo = "evento marcado como não visível"
        elif not som:
            motivo = f"tipo {e.get('tipo')!r} sem som associado (diga \"som\")"
        elif som not in SINTESE and som not in lib:
            motivo = f"som {som!r} não existe na síntese nem em --sons"
        elif not 0 <= e["t"] <= dur:
            motivo = "fora do vídeo"
        elif not e.get("pedido") and e["t"] - ultimo_auto.get(som, -1e9) < a.intervalo:
            motivo = f"a menos de {a.intervalo:g}s do {som} anterior"
        if motivo:
            pulados.append({"t": round(e["t"], 3), "som": som, "origem": e.get("origem", ""), "motivo": motivo})
            continue
        if not e.get("pedido"):
            ultimo_auto[som] = e["t"]

        if e.get("arquivo"):
            arq = pathlib.Path(e["arquivo"])
        elif som in lib:   # alterna os arquivos da categoria; pula o que tocou há menos de SEM_REPETIR_S se houver outro
            cands = lib[som]
            k = rodizio.get(som, 0)
            ordem = cands[k % len(cands):] + cands[:k % len(cands)]
            arq = next((c for c in ordem if e["t"] - ultimo_uso.get(str(c), -1e9) >= SEM_REPETIR_S), ordem[0])
            rodizio[som] = cands.index(arq) + 1
        else:
            arq = sintetizar(som, pasta_sint)
        ultimo_uso[str(arq)] = e["t"]
        if str(arq) not in medidas:
            medidas[str(arq)] = medir_som(arq)
        m = medidas[str(arq)]

        alinhar = e.get("alinhar") or ALINHAR.get(som, "inicio")
        corte = m["util"]
        inicio = e["t"] - ((m["pico"] - m["util"]) if alinhar == "pico" else 0.0)
        if inicio < 0:      # o evento está perto demais do começo: o som entra já andando, o pico continua no evento
            corte, inicio = corte - inicio, 0.0
        alvo = min(TETO_DB, voz + NIVEL.get(som, 0.0) + FORCA.get(e.get("forca", "media"), 0.0) + float(e.get("ganho", 0.0)) + a.ganho)
        itens.append({"id": f"sfx{len(itens) + 1:02d}", "t": round(e["t"], 3), "som": som, "arquivo": str(arq),
                      "alinhar": alinhar, "inicio": round(inicio, 3), "corte": round(corte, 3),
                      "ganho_db": round(alvo - m["pico_db"], 2), "origem": e.get("origem", "")})

    doc = {"source": str(a.video), "voz_lufs": round(voz, 1), "voz_medida": voz_medida, "itens": itens, "pulados": pulados}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(itens)} efeito(s), {len(pulados)} evento(s) sem som; voz a {voz:.1f} LUFS"
          + ("" if voz_medida else " (sem fala mensurável: valor assumido)") + f" -> {out}")
    for it in itens:
        print(f"  {it['id']}  {it['t']:7.2f}  {it['som']:8s} {pathlib.Path(it['arquivo']).name:22s} "
              f"{it['alinhar']:6s} {it['ganho_db']:+6.1f} dB  {it['origem']}")
    for p in pulados:
        print(f"  –      {p['t']:7.2f}  {p['som'] or '?':8s} sem som: {p['motivo']}")
    return doc


def aplicar(a):
    doc = json.loads(pathlib.Path(a.aplicar).read_text(encoding="utf-8"))
    itens = [it for it in doc.get("itens", []) if not it.get("tira")]
    if not itens:
        sys.exit(f"{a.aplicar}: nenhum efeito a mixar")
    if pathlib.Path(a.saida).resolve() == pathlib.Path(a.video).resolve():
        sys.exit("a saída não pode ser o próprio vídeo de entrada")
    tem_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
                                str(a.video)], capture_output=True, text=True).stdout.strip() != ""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(a.video)]
    base = "[0:a]"
    if not tem_audio:
        cmd += ["-f", "lavfi", "-t", f"{duracao(a.video):.3f}", "-i", f"anullsrc=r={TAXA}:cl=stereo"]
        base = "[1:a]"
    n_fixas = 2 if not tem_audio else 1
    arquivos = sorted({it["arquivo"] for it in itens})
    for arq in arquivos:
        if not pathlib.Path(arq).is_file():
            sys.exit(f"som não encontrado: {arq} (planeje de novo ou corrija o caminho no .sfx.json)")
        cmd += ["-i", arq]
    fmt = f"aformat=sample_rates={TAXA}:channel_layouts=stereo"
    partes, rotulos = [f"{base}{fmt}[b]"], []
    for k, arq in enumerate(arquivos):
        usos = [j for j, it in enumerate(itens) if it["arquivo"] == arq]
        saidas = "".join(f"[s{j}]" for j in usos)
        partes.append(f"[{k + n_fixas}:a]asplit={len(usos)}{saidas}")
        for j in usos:
            it = itens[j]
            partes.append(f"[s{j}]atrim=start={it['corte']:.3f},asetpts=PTS-STARTPTS,{fmt},volume={it['ganho_db']:.2f}dB,"
                          f"adelay={round(it['inicio'] * 1000)}:all=1[e{j}]")
            rotulos.append(f"[e{j}]")
    partes.append(f"[b]{''.join(rotulos)}amix=inputs={len(rotulos) + 1}:duration=first:normalize=0,"
                  "alimiter=limit=0.891:level=false[a]")
    cmd += ["-filter_complex", ";".join(partes), "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", *audio.AAC,
            "-movflags", "+faststart", str(a.saida)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg falhou na mixagem:\n" + r.stderr[-1500:])
    print(f"ok: {len(itens)} efeito(s) mixados -> {a.saida}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("saida", nargs="?", help="vídeo de saída (só com --aplicar)")
    ap.add_argument("--eventos", action="append", default=[], metavar="ARQ", help=".camera.json, textos.json ou lista de eventos")
    ap.add_argument("--sons", default=None, metavar="PASTA", help="biblioteca própria, por categoria")
    ap.add_argument("--intervalo", type=float, default=2.0, help="mínimo entre dois sons automáticos do mesmo tipo (s)")
    ap.add_argument("--ganho", type=float, default=0.0, help="ajuste geral em dB sobre o nível calculado")
    ap.add_argument("--out", default=None, help="caminho do .sfx.json")
    ap.add_argument("--aplicar", default=None, metavar="ARQ.sfx.json")
    a = ap.parse_args()
    if a.aplicar:
        if not a.saida:
            sys.exit("--aplicar pede o vídeo de saída: efeitos.py VIDEO --aplicar ARQ.sfx.json SAIDA.mp4")
        return aplicar(a)
    if a.saida:
        sys.exit("vídeo de saída só com --aplicar (planeje, mostre a lista e então aplique)")
    if not a.eventos:
        sys.exit("diga de onde vêm os eventos: --eventos ARQ (.camera.json, textos.json ou lista com t)")
    planejar(a)


if __name__ == "__main__":
    main()
