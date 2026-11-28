"""Renderiza as cenas em HTML (/cena-web) de um vídeo animado, sincronizadas com a narração.

Uso:
  uv run --with playwright python render_web.py cenas/<slug>.json PASTA [--tts trabalho/<slug>/tts] [--cenas B1,B2]
      [--tamanho 1920x1080] [--fps 30] [--escala 1] [--jobs 2] [--glossario JSON]
  ... --folha [N] [--reserva-baixo 0.21]    só a folha de quadros-chave de cada cena, com auditoria do texto

Vale para as cenas do spec que têm "html" no lugar de "classe":
  {"id": "B2", "html": "cenas/B2.html", "titulo": "...", "narracao": "..."}
Cada uma sai em PASTA/<id>.mp4 com a duração da narração (tempos.json do tts_cenas.py), o mesmo lugar em que o
montar_cenas.py procura as cenas do Manim: as duas técnicas convivem no mesmo vídeo.

A cena recebe do cena_web.py:
  window.vePalavras   palavras da narração no tempo da cena (já com o silêncio inicial), com a grafia do roteiro:
                      o termo de glossário falado "operêitor" chega como "operator", e veQuando("operator") acha
  window.veDados      {id, titulo, narracao, total, fala: {ini, fim}, dados: <campo "dados" da cena, se houver>}
Use `window.veDuracao = veDados.total` e marque as entradas com `veQuando("palavra")`.
As palavras que cada cena consultou ficam em PASTA/web/<id>.marcas.json; o montar_cenas.py as leva para o tempo do
vídeo final e grava a sugestão de efeitos sonoros (sons.sugeridos.json).

--folha grava PASTA/<id>.folha.png (N instantes espalhados, padrão 4) e confere texto cortado pela borda ou dentro
da faixa da legenda (--reserva-baixo, padrão 0,21: a legenda de 2 linhas do montar_cenas.py). Código de saída 2 se
alguma cena tiver problema. Rode a folha, olhe com Read e só então renderize.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "video-docs", "scripts"))
import pronuncia  # noqa: E402

CENA_WEB = os.path.join(HERE, "..", "..", "..", "scripts", "cena_web.py")


def carrega_spec(caminho):
    spec = json.load(open(caminho, encoding="utf-8"))
    if isinstance(spec, list):
        spec = {"cenas": spec}
    spec.setdefault("slug", os.path.splitext(os.path.basename(caminho))[0])
    return spec


def prepara(c, info, tts_dir, gloss, trab):
    """Grava os JSON que a cena recebe e devolve os argumentos correspondentes do cena_web.py."""
    cid, lead = c["id"], float(info.get("lead", 0))
    dados = {"id": cid, "titulo": c.get("titulo", ""), "narracao": c.get("narracao", ""), "total": info["total"],
             "fala": {"ini": lead, "fim": round(lead + info.get("fala", 0), 3)}, "dados": c.get("dados")}
    arq_d = os.path.join(trab, f"{cid}.dados.json")
    json.dump(dados, open(arq_d, "w", encoding="utf-8"), ensure_ascii=False)
    args = ["--dados", arq_d, "--dur", f"{info['total']:.3f}", "--marcas", os.path.join(trab, f"{cid}.marcas.json")]
    words = os.path.join(tts_dir, f"{cid}.words.json")
    if c.get("narracao") and os.path.exists(words):
        ws = json.load(open(words, encoding="utf-8"))
        ps = [{"t": round(a + lead, 3), "d": round(b - a, 3), "w": txt}
              for a, b, txt in pronuncia.com_grafia(ws, c["narracao"], gloss)]
        arq_p = os.path.join(trab, f"{cid}.palavras.json")
        json.dump(ps, open(arq_p, "w", encoding="utf-8"), ensure_ascii=False)
        args += ["--palavras", arq_p]
    return args


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("pasta", help="pasta de saída dos <id>.mp4 (a mesma das cenas do Manim)")
    ap.add_argument("--tts", help="padrão trabalho/<slug>/tts")
    ap.add_argument("--cenas", help="ids separados por vírgula; padrão todas as que têm \"html\"")
    ap.add_argument("--glossario", help="o mesmo JSON passado ao tts_cenas.py")
    ap.add_argument("--tamanho", default="1920x1080")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--escala", type=float, default=1)
    ap.add_argument("--jobs", type=int, default=2, help="cenas renderizadas ao mesmo tempo (um Chrome por cena)")
    ap.add_argument("--folha", nargs="?", const=4, type=int, metavar="N", help="só a folha de N quadros-chave por cena (padrão 4)")
    ap.add_argument("--reserva-baixo", type=float, default=0.21, help="com --folha: fração de baixo reservada à legenda (0 desliga)")
    a = ap.parse_args()

    spec = carrega_spec(a.spec)
    tts_dir = a.tts or os.path.join("trabalho", spec["slug"], "tts")
    try:
        tempos = json.load(open(os.path.join(tts_dir, "tempos.json"), encoding="utf-8"))
    except OSError:
        sys.exit(f"não achei {tts_dir}/tempos.json: rode o tts_cenas.py antes (a duração da cena vem da narração)")
    gloss = pronuncia.load(a.glossario or spec.get("glossary"), base_dir=os.path.dirname(os.path.abspath(a.spec)),
                           voice=spec.get("voice", "pt-BR-ThalitaMultilingualNeural"))
    cenas = [c for c in spec["cenas"] if c.get("html")]
    if a.cenas:
        ids = a.cenas.split(",")
        cenas = [c for c in cenas if c["id"] in ids]
    if not cenas:
        sys.exit('nenhuma cena com "html" no spec' + (f" entre {a.cenas}" if a.cenas else ""))
    for c in cenas:
        if not os.path.isfile(c["html"]):
            sys.exit(f"{c['id']}: não achei {c['html']}")
        if c["id"] not in tempos:
            sys.exit(f"{c['id']}: sem entrada em {tts_dir}/tempos.json; rode o tts_cenas.py de novo")
    trab = os.path.join(a.pasta, "web")
    os.makedirs(trab, exist_ok=True)

    def roda(c):
        cid = c["id"]
        comuns = prepara(c, tempos[cid], tts_dir, gloss, trab) + ["--tamanho", a.tamanho, "--escala", f"{a.escala:g}"]
        if a.folha:
            saida = os.path.join(a.pasta, f"{cid}.folha.png")
            cmd = [c["html"], "--quadros", str(a.folha), saida, "--reserva-baixo", f"{a.reserva_baixo:g}"]
        else:
            saida = os.path.join(a.pasta, f"{cid}.mp4")
            cmd = [c["html"], saida, "--fps", f"{a.fps:g}"]
        r = subprocess.run([sys.executable, "-X", "utf8", CENA_WEB, *cmd, *comuns], capture_output=True, text=True, encoding="utf-8")
        return cid, r.returncode, r.stdout, r.stderr

    piores = 0
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        for cid, rc, out, err in ex.map(roda, cenas):
            linhas = [x for x in out.splitlines() if x.startswith("ok ->")] + [x for x in err.splitlines() if x.strip()]
            print(f"{cid}: " + ("\n  ".join(linhas) if linhas else f"código {rc}"), flush=True)
            piores = max(piores, rc)
    if piores:
        sys.exit(2 if piores == 2 else 1)
    print(f"ok: {len(cenas)} cena(s) em {pathlib.Path(a.pasta)}" + (" (folhas; olhe cada uma antes de renderizar)" if a.folha else ""))


if __name__ == "__main__":
    main()
