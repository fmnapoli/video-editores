#!/usr/bin/env python3
"""Cena por HTML: renderiza uma página (HTML/CSS/canvas/WebGL) quadro a quadro num Chrome sem janela e junta no
ffmpeg. É o caminho para o que CSS e WebGL fazem melhor que ASS e Manim: 3D em tempo de autoria com Three.js
(câmera, luz, sombra), tipografia e layout em CSS, linhas do tempo com GSAP.

Contrato da cena (um arquivo .html):
  window.veQuadro = (t) => { ...desenha o instante t, em segundos... }   obrigatório; pode devolver Promise
  window.veDuracao = 6                                                    opcional (ou use --dur)
A cena NÃO anima por relógio (sem requestAnimationFrame livre, setTimeout, CSS animation solta): tudo é função de
`t`. Assim o render é determinístico e não depende da velocidade da máquina. Com GSAP: crie a timeline pausada e
faça `veQuadro = t => tl.seek(t)`. Modelos prontos em skills/cena-web/templates/.

Uso: cena_web.py CENA.html SAIDA.mp4|SAIDA.mov [--dur S] [--fps 30] [--tamanho 1920x1080] [--alpha] [--escala 1]
       [--rede] [--espera-quadro] [--palavras ARQ.json] [--dados ARQ.json] [--marca ARQ|--sem-marca]
     cena_web.py CENA.html --quadro T SAIDA.png [--tamanho ...] [--alpha]     um quadro só, para a prova
     cena_web.py CENA.html --quadros T1,T2,...|N FOLHA.png [--reserva-baixo 0.2] [--auditoria erro|aviso|nao]
                                                                               folha de quadros-chave + auditoria
     cena_web.py --libs                                                        baixa e mostra as bibliotecas

Sincronia com a narração (--palavras): um JSON [{"t": início, "d": duração, "w": palavra}, ...] no tempo da cena
vira `window.vePalavras`, e a cena pergunta o instante de uma palavra em vez de chutar o segundo:
  const t0 = veQuando("Blender");          // início da 1ª vez que a palavra é dita (aceita expressão: "três minutos")
  const t1 = veQuando("Blender", 2);       // 2ª ocorrência
  const { ini, fim } = veTrecho("na ordem certa");
A comparação ignora maiúsculas, acentos e pontuação. Palavra que não está na narração é erro e interrompe o
render: a narração mudou e a cena precisa acompanhar. Sem --palavras, `veQuando(termo, n, padrao)` devolve
`padrao` (para abrir a cena solta); sem `padrao`, é erro. `--dados ARQ.json` entrega qualquer JSON em
`window.veDados`. `--marcas ARQ.json` grava o que a cena consultou ao carregar (`[{termo, n, ini, fim}]`, no
tempo da cena): é de onde o /video-animado tira a sugestão de efeitos sonoros.

Marca: havendo `marca/marca.json` (ou $VE_MARCA, ou --marca), a página recebe `window.veMarca` ({nome, cores,
fonte, logo}), as variáveis CSS `--ve-<papel>` (`--ve-fundo`, `--ve-acento`, `--ve-texto`...) e `--ve-fonte`, e os
TTF da marca ficam registrados com o nome da família. Escreva `color: var(--ve-acento, #FFD43B)`: sem marca,
vale o valor depois da vírgula. `--sem-marca` desliga.

Quadros-chave (--quadros): desenha os instantes pedidos (lista `0.5,2,3.5`, ou um inteiro N para N instantes
espalhados pela duração), grava uma folha com todos e confere o texto da página em cada um: texto visível
cortado pela borda do quadro e, com `--reserva-baixo F`, texto dentro da fração F de baixo (a faixa da
legenda). Havendo problema, a folha é gravada, a lista sai no stderr e o código de saída é 2
(`--auditoria aviso` só avisa; `nao` desliga). Elemento que sangra de propósito: atributo `data-ve-sangra`.
A auditoria lê o DOM: texto desenhado em <canvas> (ex.: textura do Three.js) não é visto, confira na folha.

  .mp4  vídeo opaco no codificador configurado (VE_ENCODER).   .mov  ProRes 4444; com --alpha, fundo transparente
  para sobrepor (a página precisa ter fundo transparente e, em WebGL, `alpha: true`).
  --rede           permite a página buscar recursos na internet (padrão: bloqueado, para o render ser reprodutível)
  --espera-quadro  espera a composição do navegador depois de cada veQuadro (cenas com vídeo ou filtro CSS pesado)

Bibliotecas: a página importa por nome e o script entrega do cache local, sem CDN:
  <script type="importmap">{"imports": {"three": "/_ve/three/build/three.module.js",
    "three/addons/": "/_ve/three/examples/jsm/", "gsap": "/_ve/gsap/index.js", "gsap/": "/_ve/gsap/"}}</script>
  three (MIT) e gsap (gratuita, licença própria "no charge", não é open source: https://gsap.com/standard-license)
  são baixadas do registro do npm na primeira vez, na versão fixada abaixo, conferidas por sha256 e guardadas em
  ~/.cache/video-editores/web/ (`VE_CACHE`). Arquivos ao lado do .html (imagens, fontes, .js) são servidos também.

Navegador: o Chrome instalado (ou `VE_CHROME=/caminho`); sem ele, o Chromium do Playwright
(`uv run --with playwright playwright install chromium`).
Dependências: `uv run --with playwright` (ou `video-editores cena-web ...`, que resolve sozinho).
"""
import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request


def _raiz_pacote(arquivo):
    """Primeira pasta acima do script que contém video_editores/ (raiz do checkout ou site-packages da roda)."""
    for d in pathlib.Path(arquivo).resolve().parents:
        if (d / "video_editores" / "__init__.py").is_file():
            return str(d)
    return str(pathlib.Path(arquivo).resolve().parents[1])


sys.path.insert(0, os.environ.get("VE_PKG_DIR") or _raiz_pacote(__file__))
from video_editores.nucleo.ffmpeg import codec_video  # noqa: E402

ORIGEM = "http://cena.local"
# nome -> (versão, sha256 do .tgz do npm, prefixos que interessam dentro de package/, licença)
LIBS = {
    "three": ("0.187.0", "ff540832ded0cfe919764d24a3d88f3e2a05f23303f876423e4f893841e90728",
              ("build/", "examples/jsm/", "LICENSE"), "MIT"),
    "gsap": ("3.15.1", "c70a3bcf656015f32b4f6456e686034564c90d64280db535cfbd84de4497d988",
             ("",), "gratuita, licença própria 'no charge' (não é open source): https://gsap.com/standard-license"),
}


def pasta_lib(nome: str) -> pathlib.Path:
    """Pasta da biblioteca no cache, baixando e conferindo o pacote do npm na primeira vez."""
    versao, sha, prefixos, _ = LIBS[nome]
    cache = pathlib.Path(os.environ.get("VE_CACHE") or pathlib.Path.home() / ".cache" / "video-editores") / "web"
    alvo = cache / f"{nome}-{versao}"
    if (alvo / ".ok").is_file():
        return alvo
    url = f"https://registry.npmjs.org/{nome}/-/{nome}-{versao}.tgz"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            dados = r.read()
    except OSError as e:
        raise SystemExit(f"não consegui baixar {nome} {versao} ({e}).\nBaixe {url} e extraia `package/` em {alvo}, "
                         "criando um arquivo vazio `.ok` dentro.") from None
    if hashlib.sha256(dados).hexdigest() != sha:
        raise SystemExit(f"{nome} {versao}: sha256 do pacote baixado difere do esperado ({sha[:12]}…): download recusado")
    alvo.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as tf:
        for m in tf.getmembers():
            rel = m.name[len("package/"):] if m.name.startswith("package/") else None
            if not rel or not m.isfile() or ".." in pathlib.PurePosixPath(rel).parts:
                continue
            if any(rel.startswith(p) for p in prefixos):
                dest = alvo / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tf.extractfile(m).read())
    (alvo / ".ok").write_text(sha)
    return alvo


# Roda antes de qualquer script da página: dados, marca e o mapa de palavras da narração.
INICIO_JS = r"""
(() => {
  const d = __DADOS__;
  window.veDados = d.dados;
  window.veMarcas = [];
  window.veMarca = d.marca;
  window.vePalavras = d.palavras;
  const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  window.veTrecho = (termo, n = 1, padrao) => {
    const ps = window.vePalavras;
    if (!ps) {
      if (padrao !== undefined) return typeof padrao === "number" ? { ini: padrao, fim: padrao } : padrao;
      throw new Error(`veQuando("${termo}"): a cena foi renderizada sem --palavras e sem valor padrão`);
    }
    const alvo = norm(termo).split(" ").filter(Boolean), toks = [];
    ps.forEach((p, i) => norm(p.w).split(" ").filter(Boolean).forEach((k) => toks.push([k, i])));
    let visto = 0;
    for (let i = 0; alvo.length && i + alvo.length <= toks.length; i++) {
      if (alvo.every((k, j) => toks[i + j][0] === k) && ++visto === n) {
        const a = ps[toks[i][1]], b = ps[toks[i + alvo.length - 1][1]];
        window.veMarcas.push({ termo: String(termo), n, ini: a.t, fim: b.t + b.d });
        return { ini: a.t, fim: b.t + b.d };
      }
    }
    throw new Error(`veQuando("${termo}"${n > 1 ? ", " + n : ""}): ` + (visto
      ? `a narração só tem ${visto} ocorrência(s)` : "não está na narração") + ` [${ps.map((p) => p.w).join(" ")}]`);
  };
  window.veQuando = (termo, n = 1, padrao) => window.veTrecho(termo, n, padrao).ini;
  if (d.marca) {
    const aplica = () => {
      const r = document.documentElement;
      if (!r) return false;
      for (const [k, v] of Object.entries(d.marca.cores)) r.style.setProperty("--ve-" + k, v);
      r.style.setProperty("--ve-fonte", `"${d.marca.fonte}"`);
      const faces = Object.entries(d.marca.fontes || {}).map(([peso, url]) =>
        `@font-face { font-family: "${d.marca.fonte}"; src: url("${url}"); font-weight: ${peso === "bold" ? 700 : 400}; }`);
      if (faces.length) {
        const st = document.createElement("style");
        st.textContent = faces.join("\n");
        r.appendChild(st);
      }
      return true;
    };
    if (!aplica()) new MutationObserver((_, o) => { if (aplica()) o.disconnect(); }).observe(document, { childList: true });
  }
})();
"""

# Texto visível cortado pela borda do quadro, ou dentro da faixa reservada embaixo. Mede os retângulos do
# próprio texto (Range), não a caixa do elemento. Texto inteiro fora do quadro (ainda não entrou) não conta.
AUDITA_JS = r"""
(reserva) => {
  const W = innerWidth, H = innerHeight, tol = 1.5, out = [], visto = new Set();
  const visivel = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.display === "none" || s.visibility === "hidden" || +s.opacity < 0.05) return false;
    }
    return true;
  };
  const w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const el = n.parentElement, txt = n.nodeValue.replace(/\s+/g, " ").trim();
    if (!txt || !el || el.closest("script, style, noscript, template, [data-ve-sangra]") || !visivel(el)) continue;
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const b of r.getClientRects()) {
      if (b.width < 1 || b.height < 1) continue;
      if (b.right <= 0 || b.left >= W || b.bottom <= 0 || b.top >= H) continue;
      const lados = [];
      if (b.left < -tol) lados.push("esquerda");
      if (b.right > W + tol) lados.push("direita");
      if (b.top < -tol) lados.push("cima");
      if (b.bottom > H + tol) lados.push("baixo");
      let tipo = lados.length ? "cortado pela borda (" + lados.join(", ") + ")" : null;
      if (!tipo && reserva > 0 && b.bottom > H * (1 - reserva) + tol) tipo = "dentro da faixa reservada embaixo";
      const chave = tipo + "|" + txt;
      if (tipo && !visto.has(chave)) {
        visto.add(chave);
        out.push({ tipo, texto: txt.length > 48 ? txt.slice(0, 47) + "…" : txt });
      }
    }
  }
  return out;
}
"""


def dados_marca(explicito):
    """(dados para window.veMarca, pasta da marca) ou (None, None) quando o projeto não define marca."""
    from video_editores.nucleo import marca as mm
    m = mm.carregar(explicito, estrito=False)
    if not m.definida:
        return None, None
    pasta = pathlib.Path(m.pasta).resolve()

    def url(rel):
        arq = m.caminho(rel)
        if not arq or not os.path.isfile(arq):
            return None
        try:
            return "/_ve/marca/" + urllib.parse.quote(pathlib.Path(arq).resolve().relative_to(pasta).as_posix())
        except ValueError:   # arquivo fora da pasta da marca: a página não alcança
            return None
    fontes = {peso: url(rel) for peso, rel in (m.dados["fonte"].get("arquivos") or {}).items()}
    logo = {tipo: url(rel) for tipo, rel in (m.dados.get("logo") or {}).items() if isinstance(rel, str)}
    return {"nome": m.nome, "cores": dict(m.cores), "fonte": m.fonte,
            "fontes": {k: v for k, v in fontes.items() if v}, "logo": {k: v for k, v in logo.items() if v}}, pasta


def ler_palavras(arq):
    try:
        ps = json.load(open(arq, encoding="utf-8"))
        return [{"t": float(x["t"]), "d": float(x.get("d", 0)), "w": str(x["w"])} for x in ps]
    except (OSError, ValueError, KeyError, TypeError) as e:
        sys.exit(f'--palavras {arq}: esperava [{{"t": início, "d": duração, "w": palavra}}, ...] ({e})')


def instantes(txt, dur):
    """`0.5,2,3.5` -> esses instantes; um inteiro N -> N instantes espalhados pela duração (centro de cada fatia)."""
    try:
        if re.fullmatch(r"\d+", txt.strip()):
            n = int(txt)
            if n < 1 or not dur or dur <= 0:
                raise ValueError
            return [round((i + 0.5) * dur / n, 3) for i in range(n)]
        ts = [float(v) for v in txt.split(",") if v.strip()]
        if not ts or min(ts) < 0:
            raise ValueError
        return ts
    except ValueError:
        sys.exit("--quadros: lista de instantes em segundos (0.5,2,3.5) ou um inteiro N (N quadros espalhados pela "
                 "duração, que precisa estar em --dur ou em window.veDuracao)")


def folha(ctx, itens, w, h):
    """PNG com os quadros lado a lado (até 3 por linha), o instante embaixo de cada um e a contagem de problemas."""
    cols, cel = min(len(itens), 3), 640
    cels = []
    for t, png, probs in itens:
        nota = f'<b>{len(probs)} problema(s)</b>' if probs else ""
        cels.append(f'<figure class="{"ruim" if probs else ""}"><img src="data:image/png;base64,{base64.b64encode(png).decode()}">'
                    f'<figcaption>t = {t:g} s {nota}</figcaption></figure>')
    pagina = f"""<!doctype html><meta charset="utf-8"><style>
      body {{ margin: 0; padding: 8px; background: #2B2F36; font: 20px sans-serif; color: #E5E7EB;
             display: grid; grid-template-columns: repeat({cols}, {cel}px); gap: 8px; width: max-content; }}
      figure {{ margin: 0; border: 3px solid transparent; }} figure.ruim {{ border-color: #EF4444; }}
      img {{ display: block; width: {cel}px; height: {round(cel * h / w)}px;
            background: repeating-conic-gradient(#555 0% 25%, #777 0% 50%) 0 0 / 24px 24px; }}
      figcaption {{ padding: 4px 6px; }} b {{ color: #F87171; margin-left: 12px; }}
    </style>{"".join(cels)}"""
    pg = ctx.new_page()
    pg.set_viewport_size({"width": cols * cel + 16 + 8 * (cols - 1), "height": 200})
    pg.set_content(pagina, wait_until="load")
    png = pg.locator("body").screenshot(type="png")
    pg.close()
    return png


def _dentro(base: pathlib.Path, rel: str):
    """Arquivo `rel` dentro de `base`, ou None se sair da pasta ou não existir."""
    p = (base / rel.lstrip("/")).resolve()
    return p if p.is_file() and base.resolve() in p.parents else None


def rotear(ctx, pasta_cena: pathlib.Path, rede: bool, avisos: list, pasta_marca=None):
    """Roteia no CONTEXTO, não na página: janela aberta pela cena (`window.open`) passa pelo mesmo bloqueio. Sem
    --rede, WebSocket é fechado na hora (não passa por `route`) e o Chrome sobe sem resolver nomes (ver `abrir`)."""
    def trata(route):
        url = route.request.url
        if not url.startswith(ORIGEM + "/"):
            if rede or url.startswith(("data:", "blob:", "about:")):
                return route.continue_()
            avisos.append(url)
            return route.abort()
        # unquote, não url2pathname: no Windows este devolve "\\cena.html", e o caminho aqui é sempre de URL (com /)
        caminho = urllib.parse.unquote(url[len(ORIGEM):].split("?")[0].split("#")[0])
        arq = None
        if caminho.startswith("/_ve/"):
            nome, _, resto = caminho[len("/_ve/"):].partition("/")
            if nome in LIBS:
                arq = _dentro(pasta_lib(nome), resto)
            elif nome == "marca" and pasta_marca:
                arq = _dentro(pasta_marca, resto)
        else:
            arq = _dentro(pasta_cena, caminho)
        if arq is None:
            avisos.append(url)
            return route.fulfill(status=404, body="não encontrado")
        tipo = "text/javascript" if arq.suffix in (".js", ".mjs") else (mimetypes.guess_type(arq.name)[0] or "application/octet-stream")
        route.fulfill(status=200, body=arq.read_bytes(), headers={"content-type": tipo, "cache-control": "no-store"})
    ctx.route("**/*", trata)
    if not rede:
        def fecha(ws):
            avisos.append(ws.url)
            ws.close()
        if hasattr(ctx, "route_web_socket"):   # Playwright >= 1.48
            ctx.route_web_socket("**/*", fecha)


def abrir(p, w, h, escala, rede=False):
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
            "--hide-scrollbars", "--force-color-profile=srgb", "--font-render-hinting=none"]
    if not rede:
        # segunda tranca do "sem internet": nenhum nome resolve, nem para o que escapa do roteamento (a origem
        # da cena é atendida pelo roteamento antes de qualquer consulta de nome)
        args += ["--host-resolver-rules=MAP * ~NOTFOUND", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]
    exe = os.environ.get("VE_CHROME")
    if exe:
        tentativas = [{"executable_path": exe}]
    else:   # Chrome instalado, depois um Chromium do sistema (o doctor.sh aceita os dois), depois o do Playwright
        do_sistema = [shutil.which(n) for n in ("chromium", "chromium-browser")]
        tentativas = [{"channel": "chrome"}] + [{"executable_path": x} for x in do_sistema if x] + [{}]
    erro = None
    for kw in tentativas:
        try:
            b = p.chromium.launch(headless=True, args=args, **kw)
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=escala)
            return b, ctx, ctx.new_page()
        except Exception as e:   # navegador ausente: tenta o próximo
            erro = e
    raise SystemExit(f"não achei um Chrome para renderizar ({str(erro).splitlines()[0]}).\n"
                     "Instale o Google Chrome, aponte VE_CHROME=/caminho/do/chrome, ou rode\n"
                     "  uv run --with playwright playwright install chromium")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cena", nargs="?")
    ap.add_argument("saida", nargs="?")
    ap.add_argument("--dur", type=float, default=None, help="duração em segundos (padrão: window.veDuracao da cena)")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--tamanho", default="1920x1080")
    ap.add_argument("--escala", type=float, default=1, help="densidade de pixels (2 = renderiza com o dobro de pixels)")
    ap.add_argument("--alpha", action="store_true", help="fundo transparente (saída .mov ProRes 4444 ou .png)")
    ap.add_argument("--quadro", type=float, default=None, metavar="T", help="grava só o quadro do instante T em SAIDA.png")
    ap.add_argument("--quadros", metavar="T1,T2|N", help="folha com esses instantes (ou N instantes espalhados) em SAIDA.png, com auditoria do texto")
    ap.add_argument("--reserva-baixo", type=float, default=0, metavar="F", help="com --quadros: acusa texto na fração F de baixo do quadro (faixa da legenda)")
    ap.add_argument("--auditoria", choices=("erro", "aviso", "nao"), default="erro", help="com --quadros: problema de texto encerra com código 2 (padrão), só avisa, ou não confere")
    ap.add_argument("--palavras", metavar="ARQ.json", help="mapa de palavras da narração, no tempo da cena: window.vePalavras, veQuando(), veTrecho()")
    ap.add_argument("--dados", metavar="ARQ.json", help="JSON qualquer entregue à cena em window.veDados")
    ap.add_argument("--marcas", metavar="ARQ.json", help="grava as palavras que a cena consultou ao carregar: [{termo, n, ini, fim}]")
    ap.add_argument("--marca", metavar="ARQ", help="marca.json a usar (padrão: $VE_MARCA ou marca/marca.json)")
    ap.add_argument("--sem-marca", action="store_true")
    ap.add_argument("--rede", action="store_true")
    ap.add_argument("--espera-quadro", action="store_true")
    ap.add_argument("--libs", action="store_true", help="baixa as bibliotecas para o cache e mostra versão, licença e pasta")
    a = ap.parse_args()
    if a.libs:
        for nome, (versao, _, _, lic) in LIBS.items():
            print(f"{nome} {versao}  [{lic}]\n  {pasta_lib(nome)}")
        return
    if not a.cena or not a.saida:
        ap.error("informe CENA.html e a SAIDA")
    cena, saida = pathlib.Path(a.cena).resolve(), pathlib.Path(a.saida)
    if not cena.is_file():
        sys.exit(f"não achei {cena}")
    try:
        w, h = (int(v) for v in a.tamanho.lower().split("x"))
        assert w > 0 and h > 0 and w % 2 == 0 and h % 2 == 0
    except (ValueError, AssertionError):
        sys.exit("--tamanho LARGURAxALTURA, com números pares (ex.: 1920x1080, 1080x1920)")
    if a.fps <= 0 or a.escala <= 0:
        sys.exit("--fps e --escala precisam ser maiores que zero")
    ext = saida.suffix.lower()
    um_png = a.quadro is not None or a.quadros is not None
    if a.quadro is not None and a.quadros is not None:
        sys.exit("--quadro (um instante) ou --quadros (folha): escolha um")
    if a.quadros is not None and ext != ".png":
        sys.exit("--quadros grava uma folha: a saída precisa ser .png")
    if not 0 <= a.reserva_baixo < 1:
        sys.exit("--reserva-baixo é uma fração do quadro, entre 0 e 1 (0.2 = os 20% de baixo)")
    if not um_png and ext not in (".mp4", ".mov"):
        sys.exit("saída .mp4 (opaco) ou .mov (ProRes 4444; com --alpha, transparente)")
    if not um_png and a.alpha and ext != ".mov":
        sys.exit("--alpha pede saída .mov (ProRes 4444): o H.264 do .mp4 não guarda transparência")
    inicio = {"dados": None, "palavras": ler_palavras(a.palavras) if a.palavras else None}
    if a.dados:
        try:
            inicio["dados"] = json.load(open(a.dados, encoding="utf-8"))
        except (OSError, ValueError) as e:
            sys.exit(f"--dados {a.dados}: {e}")
    inicio["marca"], pasta_marca = dados_marca(False if a.sem_marca else a.marca)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("faltam dependências: uv run --with playwright python cena_web.py ...")

    # `erros` (exceção da cena) interrompe o render; `console` (console.error, recurso que não carregou) só avisa
    # no fim, junto com a URL em `avisos`: uma imagem bloqueada não pode derrubar o vídeo sem dizer qual foi
    avisos, erros, console = [], [], []
    with sync_playwright() as p:
        nav, ctx, page = abrir(p, w, h, a.escala, a.rede)
        page.on("pageerror", lambda e: erros.append(str(e)))
        page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
        rotear(ctx, cena.parent, a.rede, avisos, pasta_marca)
        # </ dentro de um <script> fecharia a tag: o JSON vai com a barra escapada
        ctx.add_init_script(INICIO_JS.replace("__DADOS__", json.dumps(inicio, ensure_ascii=False).replace("</", "<\\/")))
        page.goto(f"{ORIGEM}/{urllib.request.pathname2url(cena.name)}", wait_until="load")
        espera = float(os.environ.get("VE_ESPERA_CENA", "20"))
        # exceção ao carregar (ex.: veQuando de palavra que não está na narração) não espera o prazo inteiro:
        # meio segundo depois do erro, sem veQuadro, a cena não vai mais se definir
        pronta, restam, com_erro = False, espera, 0
        while not pronta and restam > 0 and com_erro < 2:
            try:
                page.wait_for_function("typeof window.veQuadro === 'function'", timeout=min(0.5, restam) * 1000)
                pronta = True
            except Exception:
                restam -= 0.5
                com_erro += 1 if erros else 0
        if not pronta:
            nav.close()
            det = "\n  ".join(dict.fromkeys(erros + console + [f"não carregou: {u}" for u in avisos]))
            motivo = "a cena falhou ao carregar e" if erros else "a cena"
            sys.exit(f"{motivo} não definiu window.veQuadro(t) em {espera - restam:g} s." + (f"\n  {det}" if det else ""))
        if inicio["marca"] and inicio["marca"]["fontes"]:   # fonte só usada em <canvas> não carrega sozinha
            page.evaluate("f => Promise.all([400, 700].map(p => document.fonts.load(`${p} 16px \"${f}\"`))).then(() => 0, () => 0)",
                          inicio["marca"]["fonte"])
        page.evaluate("document.fonts ? document.fonts.ready.then(() => 0) : 0")
        dur = a.dur if a.dur is not None else page.evaluate("window.veDuracao || 0")
        if a.marcas:   # o que a cena perguntou ao carregar: cada veQuando/veTrecho, com o instante que recebeu
            with open(a.marcas, "w", encoding="utf-8") as f:
                json.dump(page.evaluate("window.veMarcas || []"), f, ensure_ascii=False)
        ESPERA = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"

        def desenha(t):
            # só se espera uma Promise de verdade. A timeline do GSAP tem `.then()` (resolve quando a animação
            # termina, o que nunca acontece com ela pausada): tratá-la como Promise trava o render para sempre.
            page.evaluate("t => { const r = window.veQuadro(t); return r instanceof Promise ? r.then(() => 0) : 0; }", t)
            if a.espera_quadro:
                page.evaluate(ESPERA)
            # O Chrome sem janela às vezes recusa a captura de um quadro ("Unable to capture screenshot"; visto no
            # Windows sem GPU, no primeiro quadro). O quadro já está desenhado e é função só de t: repetir a
            # captura dá a mesma imagem. Qualquer outro erro, ou a terceira recusa, sobe.
            for tentativa in range(3):
                try:
                    return page.screenshot(type="png", omit_background=a.alpha)
                except Exception as e:
                    if tentativa == 2 or "Unable to capture screenshot" not in str(e):
                        raise
                    page.wait_for_timeout(200)

        problemas = []
        if a.quadro is not None:
            saida.write_bytes(desenha(a.quadro))
            nav.close()
            if erros:
                sys.exit(f"erro na cena em t = {a.quadro:g}s: {erros[0]}")
            print(f"ok -> {saida} (t = {a.quadro:g}s)")
        elif a.quadros is not None:
            itens = []
            for t in instantes(a.quadros, dur):
                png = desenha(t)
                if erros:
                    nav.close()
                    sys.exit(f"erro na cena em t = {t:g}s: {erros[0]}")
                probs = [] if a.auditoria == "nao" else page.evaluate(AUDITA_JS, a.reserva_baixo)
                problemas += [f"t = {t:g}s: texto {x['tipo']}: “{x['texto']}”" for x in probs]
                itens.append((t, png, probs))
            saida.parent.mkdir(parents=True, exist_ok=True)
            saida.write_bytes(folha(ctx, itens, w, h))
            nav.close()
            conf = "sem auditoria" if a.auditoria == "nao" else f"{len(problemas)} problema(s) de texto"
            print(f"ok -> {saida} ({len(itens)} quadros: {', '.join(f'{t:g}s' for t, _, _ in itens)}; {conf})")
        else:
            if not dur or dur <= 0:
                nav.close()
                sys.exit("sem duração: passe --dur S ou defina window.veDuracao na cena")
            n = max(1, round(dur * a.fps))
            W2, H2 = int(w * a.escala), int(h * a.escala)
            if ext == ".mov":
                cod = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le" if a.alpha else "yuv444p10le"]
            else:
                cod = codec_video(crf=18) + ["-movflags", "+faststart"]
            saida.parent.mkdir(parents=True, exist_ok=True)
            ff = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", f"{a.fps:g}",
                                   "-c:v", "png", "-i", "-", "-vf", f"scale={W2 - W2 % 2}:{H2 - H2 % 2}:flags=lanczos", "-r", f"{a.fps:g}",
                                   *cod, str(saida)], stdin=subprocess.PIPE)
            falha = None
            try:
                for i in range(n):
                    ff.stdin.write(desenha(i / a.fps))
                    if erros:
                        raise RuntimeError(erros[0])
                    if (i + 1) % 60 == 0:
                        print(f"  {i + 1}/{n} quadros", flush=True)
            except BrokenPipeError:   # o ffmpeg morreu no meio (codificador indisponível): o código de saída explica
                pass
            except Exception as e:
                falha = f"erro na cena no quadro {i} (t = {i / a.fps:.3f}s): {e}"
            try:
                ff.stdin.close()
            except OSError:
                pass
            rc = ff.wait()
            nav.close()
            if falha or rc != 0:
                saida.unlink(missing_ok=True)   # não deixa um vídeo pela metade no caminho da entrega
                sys.exit(falha or f"ffmpeg falhou ao codificar (código {rc}); confira VE_ENCODER e a mensagem acima")
            print(f"ok -> {saida} ({n} quadros, {n / a.fps:.2f}s, {W2}x{H2}{', com alpha' if a.alpha else ''})")
    for u in dict.fromkeys(avisos):
        print(f"AVISO: recurso não entregue: {u}" + ("" if u.startswith(ORIGEM) else "  (rede bloqueada; use --rede se for de propósito)"), file=sys.stderr)
    for e in dict.fromkeys(erros + console):
        print(f"AVISO (console da página): {e}", file=sys.stderr)
    for x in problemas:
        print(f"{'AVISO' if a.auditoria == 'aviso' else 'PROBLEMA'}: {x}", file=sys.stderr)
    if problemas and a.auditoria == "erro":
        sys.exit(2)


if __name__ == "__main__":
    main()
