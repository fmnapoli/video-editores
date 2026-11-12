#!/usr/bin/env python3
"""Coleta candidatos de identidade visual de uma fonte externa e grava um rascunho para aprovação (ADR-17).

Uso: uv run --with pillow --with fonttools --with pypdf python extrair_marca.py FONTE [--out marca] [--gravar-sugestao]

FONTE pode ser:
  .pptx .potx .docx .dotx .xlsx   tema do Office (paleta com papéis, fontes de título e de corpo, imagens do mestre)
                                  Google Slides/Docs: baixe como .pptx/.docx e passe o arquivo
  .pdf                            manual de marca: HEX/RGB citados no texto (com a página e a linha), fontes embutidas
  pasta ou .zip                   pacote de marca: logos (SVG/PNG), fontes (TTF/OTF), tokens JSON, cores dos logos
  .json                           design tokens (DTCG "$value" ou {"value": ...})

Grava <out>/rascunho.json com cores, fontes e logos candidatos, a EVIDÊNCIA de cada um (slot do tema, página do PDF,
arquivo do pacote) e uma `sugestao` de papéis. O script só coleta e sugere: quem decide os papéis é a pessoa, depois
de ver a prancha do validar_marca.py. --gravar-sugestao escreve <out>/marca.json com a sugestão (se ainda não existir)
e, para pacote de marca, copia o logo e as fontes escolhidos para <out>/.

Não baixa fonte nem logo de site: fonte entra só de pacote do cliente ou de licença que permita; logo, só de arquivo oficial.
"""
import argparse
import colorsys
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

HEX = re.compile(r"(?<![0-9A-Za-z])#([0-9A-Fa-f]{6})(?![0-9A-Za-z])")
HEX_SOLTO = re.compile(r"(?i)\bhex\b[^0-9A-Fa-f#]{0,6}#?([0-9A-Fa-f]{6})\b")
RGB = re.compile(r"(?i)\bR(?:GB)?\b[\s:=(]*?(\d{1,3})\D{1,6}?G?\D{0,5}?(\d{1,3})\D{1,6}?B?\D{0,5}?(\d{1,3})\b")
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
SLOTS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink")


def norm(h):
    return "#" + h.lstrip("#").upper()


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def saturacao(h):
    r, g, b = (c / 255 for c in rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[2]


class Rascunho:
    def __init__(self, fonte, tipo):
        self.d = {"origem": {"tipo": tipo, "ref": fonte}, "cores": [], "fontes": [], "logos": [], "avisos": []}

    def cor(self, h, evidencia, papel=None):
        h = norm(h)
        for c in self.d["cores"]:
            if c["hex"] == h:
                if evidencia not in c["evidencia"]:
                    c["evidencia"].append(evidencia)
                c["papel_no_tema"] = c.get("papel_no_tema") or papel
                return
        self.d["cores"].append({"hex": h, "evidencia": [evidencia], **({"papel_no_tema": papel} if papel else {})})

    def fonte(self, familia, evidencia, arquivo=None, uso=None):
        familia = familia.strip()
        if not familia or familia.startswith("+"):
            return
        for f in self.d["fontes"]:
            if f["familia"].lower() == familia.lower() and f.get("arquivo") == arquivo:
                if evidencia not in f["evidencia"]:
                    f["evidencia"].append(evidencia)
                return
        self.d["fontes"].append({"familia": familia, "evidencia": [evidencia],
                                 **({"arquivo": arquivo} if arquivo else {}), **({"uso": uso} if uso else {})})

    def logo(self, arquivo, evidencia, **extra):
        self.d["logos"].append({"arquivo": arquivo, "evidencia": evidencia, **extra})

    def aviso(self, txt):
        if txt not in self.d["avisos"]:
            self.d["avisos"].append(txt)


# ---------------- tema do Office ----------------
def do_office(caminho, r, out):
    z = zipfile.ZipFile(caminho)
    temas = sorted(n for n in z.namelist() if re.search(r"(ppt|word|xl)/theme/theme\d+\.xml$", n))
    if not temas:
        raise SystemExit(f"{caminho}: sem tema (theme1.xml); o arquivo é mesmo do Office?")
    raiz = ET.fromstring(z.read(temas[0]))
    esquema = raiz.find(f".//{A}clrScheme")
    nome = esquema.get("name") if esquema is not None else ""
    for slot in SLOTS:
        el = esquema.find(f"{A}{slot}") if esquema is not None else None
        if el is None:
            continue
        srgb, sysc = el.find(f"{A}srgbClr"), el.find(f"{A}sysClr")
        val = srgb.get("val") if srgb is not None else (sysc.get("lastClr") if sysc is not None else None)
        if val:
            r.cor(val, f"tema \"{nome}\", slot {slot}", papel=slot)
    for tag, uso in (("majorFont", "títulos"), ("minorFont", "corpo")):
        lat = raiz.find(f".//{A}{tag}/{A}latin")
        if lat is not None and lat.get("typeface"):
            r.fonte(lat.get("typeface"), f"tema, {tag} ({uso})", uso=uso)
    # imagens do slide mestre e dos layouts: candidatas a logo
    midia = {}
    for rel in (n for n in z.namelist() if re.search(r"ppt/(slideMasters|slideLayouts)/_rels/.*\.rels$", n)):
        for alvo in re.findall(r'Target="\.\./media/([^"]+)"', z.read(rel).decode("utf-8", "ignore")):
            midia.setdefault(alvo, rel.split("/")[1])
    if midia:
        pasta = os.path.join(out, "candidatos")
        os.makedirs(pasta, exist_ok=True)
        for alvo, onde in sorted(midia.items()):
            dest = os.path.join(pasta, alvo)
            open(dest, "wb").write(z.read(f"ppt/media/{alvo}"))
            r.logo(dest, f"imagem do {onde} ({alvo})", **dims(dest))
        r.aviso("Imagens do slide mestre foram extraídas como candidatas a logo: confirme com o arquivo oficial "
                "(prefira SVG ou PNG de alta resolução do pacote de marca).")
    r.aviso("Tema do Office traz o NOME da fonte, não o arquivo: obtenha o TTF no pacote do cliente ou use uma "
            "substituta livre e registre em fonte.substituta.")
    s = {c["papel_no_tema"]: c["hex"] for c in r.d["cores"] if c.get("papel_no_tema")}
    escuros = [s[k] for k in ("dk2", "dk1") if k in s]
    claros = [s[k] for k in ("lt1", "lt2") if k in s]
    fundo = escuros[0] if escuros else None
    if fundo and lum(fundo) < 0.01 and len(escuros) > 1:      # dk2 preto puro: prefere o outro escuro, se tiver cor
        fundo = max(escuros, key=saturacao)
    sug = {"fundo": fundo, "texto": claros[0] if claros else None, "acento": s.get("accent1"), "secundario": s.get("accent2")}
    return sug


def dims(arquivo):
    try:
        from PIL import Image
        w, h = Image.open(arquivo).size
        return {"largura": w, "altura": h}
    except Exception:
        return {}


# ---------------- PDF ----------------
def do_pdf(caminho, r, out):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("PDF precisa do pypdf: uv run --with pypdf --with pillow --with fonttools python extrair_marca.py ...") from None
    pdf = PdfReader(caminho)
    vistos = set()
    for n, pag in enumerate(pdf.pages, 1):
        try:
            texto = pag.extract_text() or ""
        except Exception:
            texto = ""
        for linha in texto.splitlines():
            ctx = re.sub(r"\s+", " ", linha).strip()[:90]
            for m in list(HEX.finditer(linha)) + list(HEX_SOLTO.finditer(linha)):
                r.cor(m.group(1), f"p. {n}: \"{ctx}\"")
            if not HEX.search(linha) and not HEX_SOLTO.search(linha):
                for m in RGB.finditer(linha):
                    v = [int(x) for x in m.groups()]
                    if all(0 <= x <= 255 for x in v):
                        r.cor("%02X%02X%02X" % tuple(v), f"p. {n} (RGB {v[0]}, {v[1]}, {v[2]}): \"{ctx}\"")
        try:
            fontes = (pag.get("/Resources") or {}).get("/Font") or {}
            for f in fontes.values():
                base = str(f.get_object().get("/BaseFont", "")).lstrip("/")
                base = re.sub(r"^[A-Z]{6}\+", "", base)
                fam = re.sub(r"[-,](Bold|Regular|Italic|Light|Medium|Semi[Bb]old|Black|Book|Heavy|Thin|ExtraBold|Oblique|MT|PS).*$", "", base)
                if fam and (fam, n) not in vistos and not any(fam == x for x, _ in vistos):
                    vistos.add((fam, n))
                    r.fonte(fam, f"fonte embutida no PDF (p. {n}, {base})")
        except Exception:
            pass
    if not r.d["cores"]:
        r.aviso("Nenhum HEX ou RGB no texto do PDF: o manual pode estar em imagem. Abra as páginas de cor e informe os valores.")
    r.aviso("As fontes embutidas incluem a do próprio manual: confirme no texto qual é a tipografia institucional.")
    r.aviso("Logo não é extraído de PDF: use o arquivo oficial (SVG/PNG).")
    return sugestao_generica(r)


# ---------------- pacote de marca / tokens ----------------
def cores_png(arquivo, n=4):
    try:
        from PIL import Image
        im = Image.open(arquivo).convert("RGBA")
        im.thumbnail((200, 200))
        d = im.tobytes()
        px = [(d[i], d[i + 1], d[i + 2]) for i in range(0, len(d), 4) if d[i + 3] > 200]
        if not px:
            return []
        cont = {}
        for p in px:
            q = tuple(v // 8 * 8 for v in p)
            cont[q] = cont.get(q, 0) + 1
        top = sorted(cont.items(), key=lambda kv: -kv[1])[:n]
        return [("%02X%02X%02X" % c, k / len(px)) for c, k in top if k / len(px) > 0.05]
    except Exception:
        return []


def tokens(dados, r, origem, caminho=""):
    if isinstance(dados, dict):
        val = dados.get("$value", dados.get("value"))
        if isinstance(val, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", val.strip()):
            r.cor(val.strip()[:7], f"{origem}: token {caminho.strip('.')}")
        for k, v in dados.items():
            if not k.startswith("$"):
                tokens(v, r, origem, f"{caminho}.{k}")
    elif isinstance(dados, list):
        for i, v in enumerate(dados):
            tokens(v, r, origem, f"{caminho}[{i}]")
    elif isinstance(dados, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", dados.strip()):
        r.cor(dados.strip(), f"{origem}: {caminho.strip('.')}")


def do_pacote(pasta, r, out):
    achou = False
    for raiz, _, arqs in sorted(os.walk(pasta)):
        if "__MACOSX" in raiz:
            continue
        for nome in sorted(arqs):
            p = os.path.join(raiz, nome)
            rel = os.path.relpath(p, pasta)
            ext = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""
            if ext in ("ttf", "otf"):
                achou = True
                fam, peso = nome.rsplit(".", 1)[0], None
                try:
                    from fontTools.ttLib import TTFont
                    nm = TTFont(p, lazy=True)["name"]
                    fam = nm.getDebugName(16) or nm.getDebugName(1) or fam
                    peso = nm.getDebugName(17) or nm.getDebugName(2)
                except Exception:
                    pass
                r.fonte(fam, f"arquivo {rel}" + (f" ({peso})" if peso else ""), arquivo=p, uso=peso)
            elif ext == "svg":
                achou = True
                txt = open(p, encoding="utf-8", errors="ignore").read()
                cores = sorted({norm(m.group(1)) for m in HEX.finditer(txt)})
                r.logo(p, f"arquivo {rel}", vetorial=True, cores=cores)
                for c in cores:
                    r.cor(c, f"cor usada em {rel}")
            elif ext == "png":
                achou = True
                cs = cores_png(p)
                r.logo(p, f"arquivo {rel}", cores=[norm(c) for c, _ in cs], **dims(p))
                for c, frac in cs:
                    r.cor(c, f"{frac:.0%} dos pixels de {rel}")
            elif ext == "json":
                try:
                    tokens(json.load(open(p, encoding="utf-8")), r, rel)
                    achou = True
                except ValueError:
                    pass
            elif ext in ("ase", "aco", "ai", "eps", "pdf"):
                r.aviso(f"{rel}: formato não lido; se for a paleta ou o manual, exporte os valores (o PDF pode ser passado direto)")
    if not achou:
        raise SystemExit(f"{pasta}: nenhum SVG, PNG, TTF, OTF ou JSON de tokens")
    r.aviso("Cores tiradas de PNG são aproximadas (quantizadas): confirme com o manual ou com o SVG.")
    return sugestao_generica(r)


def sugestao_generica(r):
    cs = [c["hex"] for c in r.d["cores"]]
    if not cs:
        return {}
    escuras = [c for c in cs if lum(c) < 0.12]
    claras = [c for c in cs if lum(c) > 0.8]
    fundo = max(escuras, key=lambda c: (saturacao(c) > 0.2, -lum(c))) if escuras else min(cs, key=lum)
    texto = max(claras, key=lum) if claras else "#FFFFFF"
    vivas = [c for c in cs if c not in (fundo, texto) and saturacao(c) > 0.35 and contraste(c, fundo) >= 3]
    vivas.sort(key=lambda c: -saturacao(c) * min(contraste(c, fundo), 8))
    return {"fundo": fundo, "texto": texto, "acento": vivas[0] if vivas else None,
            "secundario": vivas[1] if len(vivas) > 1 else None}


def escolhe_logo(r):
    """Logo para vídeo sobre fundo escuro: prefere SVG/PNG com cor clara dominante; devolve (svg, png)."""
    def claro(lg):
        return any(lum(c) > 0.7 for c in lg.get("cores", [])[:2])
    svgs = [x for x in r.d["logos"] if x.get("vetorial")]
    pngs = [x for x in r.d["logos"] if x["arquivo"].lower().endswith(".png")]
    svgs.sort(key=lambda x: (not claro(x), len(os.path.basename(x["arquivo"]))))
    pngs.sort(key=lambda x: (not claro(x), -(x.get("altura") or 0)))
    return (svgs[0]["arquivo"] if svgs else None), (pngs[0]["arquivo"] if pngs else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fonte")
    ap.add_argument("--out", default="marca")
    ap.add_argument("--nome", help="nome da marca no marca.json (padrão: nome do arquivo ou da pasta)")
    ap.add_argument("--gravar-sugestao", action="store_true",
                    help="escreve <out>/marca.json com a sugestão, se ainda não existir (revise antes de usar)")
    a = ap.parse_args()
    f = a.fonte
    if re.match(r"https?://", f):
        raise SystemExit("Site ainda não é lido por este script (ADR-17, fase posterior): salve o manual em PDF, "
                         "baixe o pacote de marca ou exporte o tema da apresentação e passe o arquivo.")
    if not os.path.exists(f):
        raise SystemExit(f"fonte não existe: {f}")
    os.makedirs(a.out, exist_ok=True)
    ext = f.lower().rsplit(".", 1)[-1] if os.path.isfile(f) and "." in f else ""
    tmp = None
    if os.path.isdir(f):
        r = Rascunho(f, "pacote"); sug = do_pacote(f, r, a.out)
    elif ext in ("pptx", "potx", "docx", "dotx", "xlsx"):
        r = Rascunho(f, "tema-office"); sug = do_office(f, r, a.out)
    elif ext == "pdf":
        r = Rascunho(f, "pdf"); sug = do_pdf(f, r, a.out)
    elif ext == "json":
        r = Rascunho(f, "tokens")
        tokens(json.load(open(f, encoding="utf-8")), r, os.path.basename(f))
        sug = sugestao_generica(r)
    elif ext == "zip":
        tmp = tempfile.mkdtemp(prefix="marca-")
        with zipfile.ZipFile(f) as z:
            for n in z.namelist():        # sem caminhos absolutos nem ".." vindos do zip
                if not (n.startswith("/") or ".." in n.split("/")):
                    z.extract(n, tmp)
        r = Rascunho(f, "pacote"); sug = do_pacote(tmp, r, a.out)
    else:
        raise SystemExit(f"tipo de fonte não reconhecido: {f} (aceitos: pptx, potx, docx, dotx, xlsx, pdf, json, zip, pasta)")

    sug = {k: v for k, v in sug.items() if v}
    if sug.get("fundo") and sug.get("texto"):
        sug["contraste_texto_fundo"] = round(contraste(sug["texto"], sug["fundo"]), 2)
    if sug.get("fundo") and sug.get("acento"):
        sug["contraste_acento_fundo"] = round(contraste(sug["acento"], sug["fundo"]), 2)
    r.d["sugestao"] = {"cores": sug, "fonte": (r.d["fontes"][0]["familia"] if r.d["fontes"] else None),
                       "observacao": "heurística: confirme cada papel pela evidência e pela prancha do validar_marca.py"}
    for obrig in ("fundo", "acento", "texto"):
        if obrig not in sug:
            r.aviso(f"sem candidata para cores.{obrig}: escolha na lista de cores ou peça o valor a quem cuida da marca")

    gravou = None
    alvo = os.path.join(a.out, "marca.json")
    if a.gravar_sugestao and os.path.exists(alvo):
        r.aviso(f"{alvo} já existe: não foi sobrescrito")
    elif a.gravar_sugestao and all(k in sug for k in ("fundo", "acento", "texto")):
        nome = a.nome or os.path.splitext(os.path.basename(os.path.normpath(f)))[0]
        m = {"nome": nome, "origem": [{"tipo": r.d["origem"]["tipo"], "ref": f}],
             "cores": {k: sug[k] for k in ("fundo", "acento", "secundario", "texto") if k in sug}}
        if r.d["fontes"]:
            fam = r.d["fontes"][0]["familia"]
            m["fonte"] = {"familia": fam}
            arqs = [x for x in r.d["fontes"] if x["familia"] == fam and x.get("arquivo")]
            if arqs and r.d["origem"]["tipo"] == "pacote":
                os.makedirs(os.path.join(a.out, "fontes"), exist_ok=True)
                m["fonte"]["arquivos"] = {}
                for x in arqs:
                    peso = "bold" if re.search(r"(?i)bold|black|heavy|semi", (x.get("uso") or "") + x["arquivo"]) else "regular"
                    if peso not in m["fonte"]["arquivos"]:
                        dest = os.path.join("fontes", os.path.basename(x["arquivo"]))
                        shutil.copyfile(x["arquivo"], os.path.join(a.out, dest))
                        m["fonte"]["arquivos"][peso] = dest
        if r.d["origem"]["tipo"] == "pacote":
            svg, png = escolhe_logo(r)
            m["logo"] = {}
            for tipo, arq in (("svg", svg), ("png", png)):
                if arq:
                    dest = f"logo.{tipo}"
                    shutil.copyfile(arq, os.path.join(a.out, dest))
                    m["logo"][tipo] = dest
            if not m["logo"]:
                del m["logo"]
        json.dump(m, open(alvo, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        gravou = alvo
    elif a.gravar_sugestao:
        r.aviso("sugestão incompleta (falta fundo, acento ou texto): marca.json não foi gravado")

    if tmp:   # caminhos do zip extraído não sobrevivem: registra só o nome dentro do pacote
        for lst, campo in ((r.d["logos"], "arquivo"), (r.d["fontes"], "arquivo")):
            for x in lst:
                if x.get(campo, "").startswith(tmp):
                    x[campo] = os.path.relpath(x[campo], tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    rasc = os.path.join(a.out, "rascunho.json")
    json.dump(r.d, open(rasc, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"rascunho": rasc, "marca": gravou, "cores": len(r.d["cores"]), "fontes": len(r.d["fontes"]),
                      "logos": len(r.d["logos"]), "sugestao": r.d["sugestao"], "avisos": r.d["avisos"]},
                     ensure_ascii=False, indent=1))
    sys.exit(0)


if __name__ == "__main__":
    main()
