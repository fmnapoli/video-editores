#!/usr/bin/env python3
"""OPCIONAL: busca e baixa vídeo de banco de imagens para cobrir um trecho sem imagem (B-roll).

Fora do padrão do plugin, que é local e sem serviço de terceiros. Só funciona com uma chave SUA do banco
(gratuita no Pexels: https://www.pexels.com/api/), na variável PEXELS_API_KEY. O que sai da máquina é o termo
de busca; nenhum arquivo do projeto é enviado. Sem chave, o script explica e encerra: nada mais no plugin
depende dele. Antes de procurar fora, veja se o próprio bruto ou um lettering resolve.

Três passos, com a escolha no meio:

  banco_video.py buscar "ondas do mar" [--id ondas] [--orientacao paisagem|retrato|quadrado]
                 [--min-dur 4] [--max-dur 60] [--n 8] [--out banco]
      grava <id>.busca.json (candidatos com autor, duração, tamanho e página) e <id>.folha.jpg (miniaturas
      numeradas, da esquerda para a direita e de cima para baixo). Mostre a folha e espere a escolha.

  banco_video.py baixar ID --escolha N [--altura 1080] [--out banco]     (--altura = lado menor: 1080 é 1080p, deitado ou em pé)
      baixa o candidato N (1 = primeiro da folha) como <id>.mp4 e grava <id>.json: autor, página, banco,
      licença, termo buscado, data, sha256. É o registro que alimenta os créditos e o relatório de edição.

  banco_video.py creditos [--out banco]
      lista os créditos de tudo que foi baixado, pronta para a descrição do vídeo.

Depois de baixar: corte o trecho e iguale formato e cor ao resto do vídeo antes de montar (skill /banco).
Só biblioteca padrão e ffmpeg. `VE_BANCO_URL` troca o endereço da API (testes).
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.pexels.com"
LICENCA = "Licença Pexels (uso gratuito, inclusive comercial; crédito ao autor recomendado): https://www.pexels.com/license/"
ORIENT = {"paisagem": "landscape", "retrato": "portrait", "quadrado": "square"}


def chave():
    k = os.environ.get("PEXELS_API_KEY", "").strip()
    if not k:
        sys.exit("banco de vídeo é opcional e está desligado: falta PEXELS_API_KEY.\n"
                 "Crie uma chave gratuita em https://www.pexels.com/api/ e exporte PEXELS_API_KEY=...\n"
                 "Sem isso, cubra o trecho com o próprio bruto, lettering ou animação (/lettering, /animacao).")
    return k


def http(url, cabecalhos=None, destino=None):
    req = urllib.request.Request(url, headers={"User-Agent": "video-editores", **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            sys.exit(f"o banco recusou a chave (HTTP {e.code}): confira PEXELS_API_KEY")
        if e.code == 429:
            sys.exit("limite de requisições do banco atingido (HTTP 429): espere e tente de novo")
        sys.exit(f"erro do banco: HTTP {e.code} em {url.split('?')[0]}")
    except OSError as e:
        sys.exit(f"sem resposta do banco ({e}): confira a rede")
    if destino:
        pathlib.Path(destino).write_bytes(dados)
        return destino
    return dados


def buscar(a):
    k = chave()
    base = os.environ.get("VE_BANCO_URL", API).rstrip("/")
    q = {"query": a.termo, "per_page": min(80, max(a.n * 3, 15))}
    if a.orientacao:
        q["orientation"] = ORIENT[a.orientacao]
    d = json.loads(http(f"{base}/v1/videos/search?{urllib.parse.urlencode(q)}", {"Authorization": k}))
    cands = []
    for v in d.get("videos", []):
        if not a.min_dur <= v.get("duration", 0) <= a.max_dur:
            continue
        arqs = [f for f in v.get("video_files", []) if f.get("link") and (f.get("file_type") or "video/mp4") == "video/mp4"]
        if not arqs:
            continue
        cands.append({"video_id": v["id"], "duracao": v["duration"], "largura": v.get("width"), "altura": v.get("height"),
                      "autor": (v.get("user") or {}).get("name", ""), "autor_url": (v.get("user") or {}).get("url", ""),
                      "pagina": v.get("url", ""), "miniatura": v.get("image", ""),
                      "arquivos": [{"largura": f.get("width"), "altura": f.get("height"), "fps": f.get("fps"),
                                    "link": f["link"]} for f in arqs]})
        if len(cands) == a.n:
            break
    if not cands:
        sys.exit(f"nenhum vídeo para \"{a.termo}\" com {a.min_dur:g}–{a.max_dur:g} s: tente outro termo (em inglês costuma render mais)")
    pasta = pathlib.Path(a.out)
    pasta.mkdir(parents=True, exist_ok=True)
    ident = a.id or "-".join(a.termo.lower().split())[:40]
    (pasta / f"{ident}.busca.json").write_text(json.dumps(
        {"id": ident, "banco": "pexels", "termo": a.termo, "orientacao": a.orientacao,
         "data": datetime.date.today().isoformat(), "candidatos": cands}, ensure_ascii=False, indent=1), encoding="utf-8")
    # folha de escolha: miniaturas na ordem dos candidatos (o número é a posição: esquerda->direita, cima->baixo)
    tmp = pasta / f".{ident}.mini"
    tmp.mkdir(exist_ok=True)
    ok = []
    for i, c in enumerate(cands, 1):
        if c["miniatura"]:
            ok.append(http(c["miniatura"], destino=tmp / f"{i:02}.jpg"))
    folha = pasta / f"{ident}.folha.jpg"
    if ok:
        col = min(4, len(ok))
        ent = [x for p in ok for x in ("-i", str(p))]
        esc = "".join(f"[{i}:v]scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2[m{i}];" for i in range(len(ok)))
        layout = "|".join(f"{(i % col) * 480}_{(i // col) * 270}" for i in range(len(ok)))
        fc = esc + "".join(f"[m{i}]" for i in range(len(ok))) + (f"xstack=inputs={len(ok)}:layout={layout}:fill=black[v]" if len(ok) > 1 else "null[v]")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ent, "-filter_complex", fc, "-map", "[v]",
                        "-frames:v", "1", "-update", "1", str(folha)], check=True)
    for p in tmp.glob("*"):
        p.unlink()
    tmp.rmdir()
    print(f"ok: {len(cands)} candidatos -> {pasta / (ident + '.busca.json')}" + (f" e {folha}" if ok else ""))
    for i, c in enumerate(cands, 1):
        print(f"  {i}. {c['duracao']:>3} s  {c['largura']}x{c['altura']}  {c['autor']}  {c['pagina']}")
    print(f"mostre a folha, espere a escolha e rode: banco_video.py baixar {ident} --escolha N --out {a.out}")


def baixar(a):
    chave()
    pasta = pathlib.Path(a.out)
    arq = pasta / f"{a.ident}.busca.json"
    if not arq.is_file():
        sys.exit(f"não achei {arq}: rode `buscar` antes")
    busca = json.loads(arq.read_text(encoding="utf-8"))
    cands = busca["candidatos"]
    if not 1 <= a.escolha <= len(cands):
        sys.exit(f"--escolha vai de 1 a {len(cands)}")
    c = cands[a.escolha - 1]
    # menor arquivo cujo lado menor ainda tem a medida pedida (1080 = 1080p, deitado ou em pé); senão, o maior
    def lado(f):
        return min(f.get("largura") or 0, f.get("altura") or 0)
    arqs = sorted(c["arquivos"], key=lado)
    serve = [f for f in arqs if lado(f) >= a.altura]
    f = serve[0] if serve else arqs[-1]
    mp4 = pasta / f"{a.ident}.mp4"
    if mp4.exists():
        sys.exit(f"{mp4} já existe: use outro --id na busca ou apague o arquivo (nada é sobrescrito)")
    http(f["link"], destino=mp4)
    reg = {"id": a.ident, "arquivo": mp4.name, "banco": busca["banco"], "termo": busca["termo"], "video_id": c["video_id"],
           "autor": c["autor"], "autor_url": c["autor_url"], "pagina": c["pagina"], "licenca": LICENCA,
           "largura": f.get("largura"), "altura": f.get("altura"), "duracao": c["duracao"],
           "baixado_em": datetime.date.today().isoformat(), "sha256": hashlib.sha256(mp4.read_bytes()).hexdigest()}
    (pasta / f"{a.ident}.json").write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok -> {mp4} ({f.get('largura')}x{f.get('altura')}, {c['duracao']} s), registro em {a.ident}.json")
    print(f"crédito: vídeo de {c['autor']} (Pexels) {c['pagina']}")


def creditos(a):
    regs = []
    for p in sorted(pathlib.Path(a.out).glob("*.json")):
        if p.name.endswith(".busca.json"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("banco") and d.get("autor") is not None:
            regs.append(d)
    if not regs:
        print("nenhum vídeo de banco registrado")
        return
    print("Vídeos de banco (" + ", ".join(sorted({r['banco'].capitalize() for r in regs})) + "):")
    for r in regs:
        print(f"- {r['autor']}: {r['pagina']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buscar")
    b.add_argument("termo")
    b.add_argument("--id", default=None)
    b.add_argument("--orientacao", default=None, choices=list(ORIENT))
    b.add_argument("--min-dur", type=float, default=4)
    b.add_argument("--max-dur", type=float, default=60)
    b.add_argument("--n", type=int, default=8)
    b.add_argument("--out", default="banco")
    x = sub.add_parser("baixar")
    x.add_argument("ident", metavar="ID")
    x.add_argument("--escolha", type=int, required=True)
    x.add_argument("--altura", type=int, default=1080, help="lado menor mínimo do arquivo (1080 = 1080p, paisagem ou retrato)")
    x.add_argument("--out", default="banco")
    c = sub.add_parser("creditos")
    c.add_argument("--out", default="banco")
    a = ap.parse_args()
    {"buscar": buscar, "baixar": baixar, "creditos": creditos}[a.cmd](a)


if __name__ == "__main__":
    main()
