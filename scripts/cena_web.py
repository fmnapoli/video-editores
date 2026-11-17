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
       [--rede] [--espera-quadro]
     cena_web.py CENA.html --quadro T SAIDA.png [--tamanho ...] [--alpha]     um quadro só, para a prova
     cena_web.py --libs                                                        baixa e mostra as bibliotecas

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
import hashlib
import io
import mimetypes
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
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


def _dentro(base: pathlib.Path, rel: str):
    """Arquivo `rel` dentro de `base`, ou None se sair da pasta ou não existir."""
    p = (base / rel.lstrip("/")).resolve()
    return p if p.is_file() and base.resolve() in p.parents else None


def rotear(ctx, pasta_cena: pathlib.Path, rede: bool, avisos: list):
    """Roteia no CONTEXTO, não na página: janela aberta pela cena (`window.open`) passa pelo mesmo bloqueio. Sem
    --rede, WebSocket é fechado na hora (não passa por `route`) e o Chrome sobe sem resolver nomes (ver `abrir`)."""
    def trata(route):
        url = route.request.url
        if not url.startswith(ORIGEM + "/"):
            if rede or url.startswith(("data:", "blob:", "about:")):
                return route.continue_()
            avisos.append(url)
            return route.abort()
        caminho = urllib.request.url2pathname(url[len(ORIGEM):].split("?")[0].split("#")[0])
        arq = None
        if caminho.startswith("/_ve/"):
            nome, _, resto = caminho[len("/_ve/"):].partition("/")
            if nome in LIBS:
                arq = _dentro(pasta_lib(nome), resto)
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
    if a.quadro is None and ext not in (".mp4", ".mov"):
        sys.exit("saída .mp4 (opaco) ou .mov (ProRes 4444; com --alpha, transparente)")
    if a.quadro is None and a.alpha and ext != ".mov":
        sys.exit("--alpha pede saída .mov (ProRes 4444): o H.264 do .mp4 não guarda transparência")
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
        rotear(ctx, cena.parent, a.rede, avisos)
        page.goto(f"{ORIGEM}/{urllib.request.pathname2url(cena.name)}", wait_until="load")
        espera = float(os.environ.get("VE_ESPERA_CENA", "20"))
        try:
            page.wait_for_function("typeof window.veQuadro === 'function'", timeout=espera * 1000)
        except Exception:
            nav.close()
            det = "\n  ".join(dict.fromkeys(erros + console + [f"não carregou: {u}" for u in avisos]))
            sys.exit(f"a cena não definiu window.veQuadro(t) em {espera:g} s." + (f"\n  {det}" if det else ""))
        page.evaluate("document.fonts ? document.fonts.ready.then(() => 0) : 0")
        dur = a.dur if a.dur is not None else page.evaluate("window.veDuracao || 0")
        ESPERA = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"

        def desenha(t):
            # só se espera uma Promise de verdade. A timeline do GSAP tem `.then()` (resolve quando a animação
            # termina, o que nunca acontece com ela pausada): tratá-la como Promise trava o render para sempre.
            page.evaluate("t => { const r = window.veQuadro(t); return r instanceof Promise ? r.then(() => 0) : 0; }", t)
            if a.espera_quadro:
                page.evaluate(ESPERA)
            return page.screenshot(type="png", omit_background=a.alpha)

        if a.quadro is not None:
            saida.write_bytes(desenha(a.quadro))
            nav.close()
            print(f"ok -> {saida} (t = {a.quadro:g}s)")
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


if __name__ == "__main__":
    main()
