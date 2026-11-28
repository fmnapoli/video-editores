"""Catálogo das operações do plugin: nome estável -> script, dependências e uso.

É a única fonte para a CLI (`video-editores <op>`), para o servidor MCP (uma ferramenta por operação) e
para a documentação (docs/scripts.md). Dependências de modelo são declaradas pelo papel ("asr", "seg",
"tts", "imagem") e resolvidas no backend configurado; pacotes fixos entram pelo nome.
"""
import shutil
import sys
from dataclasses import dataclass, field

from .. import raiz_recursos
from .. import modelos


@dataclass(frozen=True)
class Operacao:
    nome: str
    script: str                 # relativo à raiz de recursos (scripts/… ou skills/…/scripts/…)
    resumo: str
    uso: str                    # argumentos, como na docstring do script
    deps: tuple = ()            # "asr" | "seg" | "tts" | nome de pacote
    longa: bool = False         # costuma passar de 1 min: o MCP roda em segundo plano por padrão
    skill: str = ""
    saidas: tuple = field(default_factory=tuple)

    @property
    def caminho(self):
        return raiz_recursos() / self.script

    def pacotes(self, device=None) -> list:
        out = []
        for d in self.deps:
            out += modelos.deps(d, dev=device) if d in modelos.TIPOS else [d]
        seen = []
        for p in out:
            if p not in seen:
                seen.append(p)
        return seen


_V = "skills/videoaula/scripts/"
_A = "skills/video-animado/scripts/"
_P = "skills/partitura/scripts/"
OPERACOES = {o.nome: o for o in [
    Operacao("transcrever", "scripts/transcribe.py", "Transcrição com timestamps por palavra (ASR configurado)",
             "VIDEO [--model medium] [--lang pt] [--prompt VOCABULÁRIO] [--out-dir PASTA] [--device auto|cpu|cuda] [--backend NOME]",
             ("asr",), longa=True, skill="legenda, tomada, destaques", saidas=("<nome>.transcript.json", "<nome>.srt", "<nome>.words.srt")),
    Operacao("tomadas", "scripts/takes.py", "Acha tomadas repetidas na transcrição e marca a melhor de cada",
             "VIDEO.transcript.json [--threshold 0.6] [--pad 0.08] [--out ARQ.takes.json]", skill="tomada", saidas=("<nome>.takes.json",)),
    Operacao("montar-trechos", "scripts/render_spans.sh", "Monta um vídeo só com os trechos `keep` de um JSON",
             "VIDEO ARQ.takes.json SAIDA.mp4", skill="tomada, destaques", longa=True),
    Operacao("destaques", "scripts/highlights.py", "Melhores momentos pela transcrição, por alvo de duração ou N reels",
             "VIDEO.transcript.json [--target 600] [--reels 3] [--out ARQ.json]", skill="destaques"),
    Operacao("backbone", "scripts/backbone.py", "Arco narrativo em 7 etapas (desafio → conclusão): blocos com etapa sugerida, relatório do arco e corte por etapa",
             "blocos VIDEO.transcript.json | relatorio ARQ.backbone.json [--json] | montar ARQ.backbone.json --target 90 [--reordenar]",
             skill="destaques", saidas=("<nome>.backbone.json", "<nome>.backbone.md", "<nome>.backbone.keep.json")),
    Operacao("lettering", "scripts/lettering_ass.py", "Textos na tela (ASS/libass): títulos, lower third, cartão, capa",
             "VIDEO textos.json [--font FONTE] [--burn SAIDA.mp4]", skill="lettering", saidas=("textos.ass",)),
    Operacao("legenda-palavra", "scripts/legenda_palavra.py", "Legenda por página com a palavra falada em destaque (ASS), a partir da transcrição",
             "VIDEO IN.transcript.json [--burn SAIDA.mp4] [--janela 1.5] [--max-palavras 5] [--modo atual|preenche] [--pos F] [--tamanho 0.05] [--font FONTE] [--caixa] [--correcoes c.json]",
             skill="legenda", saidas=("<nome>.palavra.ass", "<nome>.palavra.paginas.txt")),
    Operacao("checklist", "scripts/checklist_ass.py", "Checklist com moldura em que cada item aparece quando é falado",
             "VIDEO itens.json transcript.json [--burn SAIDA.mp4]", skill="checklist"),
    Operacao("texto-atras", "scripts/text_behind.py", "Texto atrás da pessoa (segmentação por IA)",
             "IN.mp4 OUT.mp4 --text TEXTO [--start 0 --end 3] [--model u2net_human_seg|birefnet-portrait]",
             ("seg", "pillow"), longa=True, skill="texto-atras"),
    Operacao("prova", "scripts/proof.sh", "Folha de contato, preview leve e relatório técnico com loudness",
             "VIDEO [N_QUADROS=12]", skill="prova", saidas=("<nome>.proof.jpg", "<nome>.preview.mp4", "<nome>.proof.txt")),
    Operacao("normalizar-audio", "scripts/normalizar_audio.py", "Normaliza a -14/-16 LUFS com teto de pico real (mede antes e depois)",
             "ENTRADA SAIDA.mp4|SAIDA.wav [--alvo -14] [--tp -1.5] [--filtro CADEIA] | ENTRADA --medir", skill="prova, trilha, videoaula, video-animado"),
    Operacao("validar-marca", "scripts/validar_marca.py", "Valida marca/marca.json (contraste, fonte, logo) e gera a prancha de aprovação",
             "[marca/marca.json] [--prancha SAIDA.png] [--gravar] [--sem-prancha]", ("pillow", "fonttools"), skill="marca", saidas=("prancha.png",)),
    Operacao("extrair-marca", "scripts/extrair_marca.py", "Coleta cores, fontes e logos de tema PPTX/DOCX, manual em PDF, pacote de marca ou tokens e grava um rascunho",
             "FONTE [--out marca] [--nome NOME] [--gravar-sugestao]", ("pillow", "fonttools", "pypdf"), skill="marca", saidas=("rascunho.json",)),
    Operacao("gerar-imagem", "scripts/gerar_imagem.py", "Gera N variações de imagem por prompt (servidor ComfyUI), com folha de escolha e registro para regenerar",
             '"PROMPT" [--id ID] [--out gerados] [--variacoes 4] [--semente N] [--largura 1344] [--altura 768] [--passos N] [--negativo T] [--workflow NOME|ARQ] | --conferir',
             ("imagem", "pillow"), longa=True, saidas=("<id>-<semente>.png", "<id>.folha.png", "<id>.json")),
    Operacao("rostos", "scripts/rostos.py", "Onde está o rosto em cada instante (zona livre para texto) e conferência de texto sobre o rosto",
             "VIDEO [--passo 0.5] [--out ARQ.rostos.json] [--backend NOME] | ANTES.mp4 --conferir DEPOIS.mp4 [--rostos ARQ.rostos.json] [--limiar 28] [--area 0.05]",
             ("rosto",), skill="prova, lettering", saidas=("<nome>.rostos.json", "<nome>.rosto-coberto.json")),
    Operacao("rastrear", "scripts/rastrear.py", "Acompanha uma região do vídeo quadro a quadro e gruda uma etiqueta nela (ASS)",
             'VIDEO --caixa X,Y,L,A [--inicio T] [--fim T] [--etiqueta "TEXTO"] [--ancora cima|baixo|centro|esquerda|direita] [--tamanho 0.035] [--seta] [--girar] [--burn SAIDA.mp4]',
             ("opencv-python-headless", "numpy"), skill="rastrear", saidas=("<id>.rastro.json", "<id>.rastro.ass")),
    Operacao("camera", "scripts/camera.py", "Câmera sobre o corte: troca de plano a cada corte, aproximação lenta, punch e plano fechado no rosto",
             "VIDEO --cortes ARQ.takes.json|ARQ.v1.json [--cortes ...] [--cortes-em T,T] [--rostos ARQ.rostos.json] [--punches ARQ.json] [--fechado 1.18] [--deriva 0.03] [--seguir] | VIDEO --aplicar ARQ.camera.json SAIDA.mp4",
             ("opencv-python-headless", "numpy"), longa=True, skill="camera", saidas=("<nome>.camera.json", "SAIDA.mp4")),
    Operacao("efeitos", "scripts/efeitos.py", "Efeitos sonoros por evento ou por palavra falada: pico do som no evento, nível relativo à voz, sem repetir o mesmo arquivo",
             "VIDEO --eventos ARQ.camera.json|textos.json|lista.json [--eventos ...] [--palavras ARQ.transcript.json] [--sons PASTA] [--intervalo 2.0] [--ganho 0] | VIDEO --aplicar ARQ.sfx.json SAIDA.mp4",
             skill="efeitos", saidas=("<nome>.sfx.json", "SAIDA.mp4")),
    Operacao("ler-tela", "scripts/ler_tela.py", "OCR de print ou de quadro do vídeo: palavras com posição; destaque ou tarja no texto encontrado (ASS)",
             'IMAGEM|VIDEO [--t T] [--achar "TEXTO"] [--regex PADRÃO] [--estilo caixa|marca|sublinhado|tarja] [--inicio T --fim T] [--burn SAIDA.mp4] [--backend NOME]',
             ("ocr", "opencv-python-headless", "numpy"), skill="ler-tela", saidas=("<nome>.ocr.json", "<nome>.destaque.ass")),
    Operacao("conferir-fala", "scripts/conferir_fala.py", "Compara o roteiro com a transcrição do áudio final, palavra por palavra",
             "ROTEIRO.txt|.md|cenas.json VIDEO.transcript.json [--tolerancia 0.02] [--equivalentes eq.json] [--out ARQ.fala.md]",
             skill="prova, video-animado, video-docs", saidas=("<nome>.fala.md", "<nome>.fala.json")),
    Operacao("banco-video", "scripts/banco_video.py", "Opcional: busca e baixa vídeo de banco (Pexels, exige chave própria), com folha de escolha e registro de crédito",
             'buscar "TERMO" [--id ID] [--orientacao paisagem|retrato|quadrado] [--min-dur 4] [--n 8] | baixar ID --escolha N [--altura 1080] | creditos',
             skill="banco", saidas=("<id>.busca.json", "<id>.folha.jpg", "<id>.mp4", "<id>.json")),
    Operacao("cena-web", "scripts/cena_web.py", "Renderiza uma cena HTML (CSS, canvas, WebGL/Three.js, GSAP) quadro a quadro em Chrome sem janela + ffmpeg",
             "CENA.html SAIDA.mp4|SAIDA.mov [--dur S] [--fps 30] [--tamanho 1920x1080] [--alpha] [--escala 1] [--rede] [--palavras ARQ.json] [--dados ARQ.json] | CENA.html --quadro T SAIDA.png | CENA.html --quadros T1,T2|N FOLHA.png [--reserva-baixo 0.2] | --libs",
             ("playwright",), longa=True, skill="cena-web", saidas=("SAIDA.mp4", "SAIDA.mov")),
    Operacao("doctor", "scripts/doctor.sh", "Verifica dependências (ffmpeg+libass, uv, CLIs, fontes, GPU)", ""),
    Operacao("docs-render", "scripts/render-docs.sh", "Montador do video-docs (gravações de tela -> vídeos de documentação)",
             "spec.json", ("tts", "pillow"), longa=True, skill="video-docs"),
    Operacao("docs-conferir", "skills/video-docs/scripts/confere_saida.py", "Confere se .mp4 e .srt de cada spec do video-docs estão atualizados",
             "specs/*/spec.json", skill="video-docs"),
    Operacao("cenas-tts", _A + "tts_cenas.py", "Narração por cena (TTS configurado) e tempos.json que dita as durações",
             "cenas/<slug>.json [--out PASTA] [--voz VOZ] [--glossario JSON] [--lead 0.6] [--tail 0.8]", ("tts",), longa=True, skill="video-animado"),
    Operacao("cenas-montar", _A + "montar_cenas.py", "Junta as cenas Manim com a narração e a legenda frase a frase",
             "cenas/<slug>.json PASTA_MP4 [--cenas A,B] [--jobs 2] [--loudness -16] [--tp -1.5] [--roteiro ARQ.md]", longa=True, skill="video-animado"),
    Operacao("cenas-folha", _A + "folha_cenas.py", "Um quadro por cena para aprovação", "cenas/<slug>.json", skill="video-animado"),
    Operacao("cenas-web", _A + "render_web.py", "Renderiza as cenas em HTML do spec, sincronizadas com a narração (ou só a folha de quadros-chave)",
             "cenas/<slug>.json PASTA_MP4 [--cenas A,B] [--tamanho 1920x1080] [--jobs 2] | ... --folha [N] [--reserva-baixo 0.21]",
             ("playwright",), longa=True, skill="video-animado, cena-web"),
    Operacao("partitura", _P + "partitura.py", "Partitura de bateria (padrão JSON -> Verovio) em cartão PNG com a posição de cada nota",
             "padroes.json [ID ...] [--out partituras] [--tamanho card|big|ambos] [--compassos N] [--fonte ARQ.ttf]",
             ("verovio", "resvg-py", "pillow"), skill="partitura", saidas=("<id>.png", "<id>.json", "<id>_big.png", "<id>_big.json")),
    Operacao("partitura-tocar", _P + "tocar.py", "Exemplo tocado: som sintetizado + partitura animada nota a nota (bloco mp4 + wav)",
             "ID [--partituras partituras] [--out exemplos] [--bpm 72] [--voltas 2] [--contagem] [--fundo PNG] [--so-audio]",
             ("numpy", "scipy", "pillow"), longa=True, skill="partitura", saidas=("<id>.mp4", "<id>.wav", "<id>.json")),
    Operacao("partitura-andamento", _P + "andamento.py", "Andamento (bpm) e fase do compasso de um clipe de bateria, para o exemplo tocado e o cursor",
             "CLIPE [CLIPE ...] [--ini S] [--fim S] [--faixa 70-160] [--tempos N] [--bumbo 0,3] [--out beats.json]",
             ("librosa", "numpy", "scipy", "soundfile"), skill="partitura", saidas=("beats.json",)),
    Operacao("aula-cenas-modo", _V + "cenas_modo.py", "Classifica cada cena da aula em locutor/quadro/código pelos frames",
             "cenas.csv PASTA_FRAMES cenas.json", ("pillow", "numpy"), skill="videoaula"),
    Operacao("aula-layout", _V + "detectar_layout.py", "Mede o círculo da webcam e rascunha os grupos de layout da IDE",
             "VIDEO cenas.json [--saida PASTA] [--quadro] [--codigo]", ("pillow", "numpy"), skill="videoaula"),
    Operacao("aula-remap", _V + "remap_tempos.py", "Remapeia cenas e transcrição do tempo original para o do corte (v1 do auto-editor)",
             "cenas|transcript ENTRADA.json CORTE.v1.json SAIDA.json [--fps 30]", skill="videoaula"),
    Operacao("aula-identidade", _V + "identidade.py", "Gera fundo, chips, anel, lower third e painéis da identidade visual",
             "aula.json", ("pillow", "numpy"), skill="videoaula"),
    Operacao("aula-recorte", _V + "matte.py", "Recorta o locutor por IA num trecho e compõe sobre o fundo com sombra",
             "VIDEO INI FIM FUNDO.png OUT_BASE [--threads 4] [--model u2net_human_seg] [--fps 30] [--gpu] [--backend NOME]",
             ("seg",), longa=True, skill="videoaula, tela-verde", saidas=("OUT_BASE.mp4", "OUT_BASE_alpha.mp4")),
    Operacao("aula-recorte-paralelo", _V + "matte_workers.sh", "Recorta todos os trechos de locutor em N processos balanceados",
             "aula.json [N=2]", longa=True, skill="videoaula"),
    Operacao("aula-render-cenas", _V + "render_cenas.sh", "Renderiza cenas Manim em paralelo (ql|qh), separadores por Separador:N",
             "ARQ.py ql|qh [-j N] Cena... Separador:N", longa=True, skill="videoaula, animacao"),
    Operacao("aula-montar", _V + "montar_aula.py", "EDL alinhada ao frame, render dos blocos e concat com áudio contínuo",
             "aula.json edl|render [--ate T] [--only N] [--jobs N]|concat SAIDA.mp4 [--ate T]|map T", longa=True, skill="videoaula"),
    Operacao("aula-legenda", _V + "legenda_aula.py", "SRT final a partir da transcrição original remapeada, com ajustes",
             "aula.json CORTE.v1.json transcript.json SAIDA.srt [--ajustes ajustes.json]", skill="videoaula"),
    Operacao("aula-finalizar", _V + "finalizar.sh", "Render + concat + lettering + normalização (-14 LUFS, pico real) + SRT: a entrega",
             "aula.json SAIDA.mp4 SAIDA.srt [--textos textos.json] [--ajustes ajustes.json] [--jobs N] [--limpar-audio]", longa=True, skill="videoaula"),
    Operacao("aula-publicar", _V + "publicar_aula.py", "Capítulos do YouTube, descrição, hashtags e thumbnail",
             "aula.json [--saida PASTA] [--thumb-t T] [--sem-thumb]", ("pillow", "numpy"), skill="videoaula"),
]}


def operacao(nome: str) -> Operacao:
    try:
        return OPERACOES[nome]
    except KeyError:
        raise KeyError(f"operação desconhecida: {nome!r}; veja `video-editores listar`") from None


def ambiente() -> dict:
    """Variáveis que os scripts precisam para achar o pacote: VE_PKG_DIR aponta para a pasta que contém
    video_editores/ (raiz do checkout, ou site-packages quando instalado como roda), já que `python -I`
    dentro do `uv run` não enxerga nem o PYTHONPATH nem o ambiente de quem chamou."""
    import os
    from pathlib import Path
    pkg_dir = str(Path(__file__).resolve().parents[2])
    amb = {"VE_PKG_DIR": os.environ.get("VE_PKG_DIR") or pkg_dir}
    if os.name == "nt":   # arquivos e saída em UTF-8: o padrão do Windows é cp1252 e os acentos sairiam trocados
        amb["PYTHONUTF8"] = os.environ.get("PYTHONUTF8") or "1"
    return amb


def bash() -> str:
    """O bash que roda os scripts .sh. No Windows é o do Git for Windows, procurado de propósito: `bash` sozinho
    pode resolver para C:\\Windows\\System32\\bash.exe, que é o lançador do WSL e não enxerga estes caminhos.
    $VE_BASH aponta outro."""
    import os
    if os.environ.get("VE_BASH"):
        return os.environ["VE_BASH"]
    if os.name != "nt":
        return "bash"
    achado = shutil.which("bash")
    if achado and "system32" not in achado.lower():
        return achado
    cands = []
    git = shutil.which("git")
    if git:   # <Git>\cmd\git.exe ou <Git>\bin\git.exe -> <Git>\bin\bash.exe
        cands.append(os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe"))
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            cands += [os.path.join(base, "Git", "bin", "bash.exe"), os.path.join(base, "Programs", "Git", "bin", "bash.exe")]
    for c in cands:
        if os.path.isfile(c):
            return c
    raise SystemExit("bash não encontrado: instale o Git for Windows (https://git-scm.com/download/win) "
                     "ou aponte VE_BASH para o bash.exe")


def comando(nome: str, args, device=None, direto=False) -> list:
    """Linha de comando completa para a operação. Scripts .py com dependências rodam com
    `uv run --with …` (isolado, ADR-04); sem uv, ou com direto=True, usam o Python atual."""
    op = operacao(nome)
    p = str(op.caminho)
    if p.endswith(".sh"):
        return [bash(), p, *args]
    pk = op.pacotes(device)
    if pk and not direto and shutil.which("uv"):
        withs = [x for pkg in pk for x in ("--with", pkg)]
        # -X utf8: o modo isolado (-I) ignora PYTHONUTF8, e no Windows a saída e os arquivos iriam em cp1252
        return ["uv", "run", "--quiet", *withs, "python", "-X", "utf8", "-I", p, *args]
    return [sys.executable, p, *args]
