"""Catálogo das operações do plugin: nome estável -> script, dependências e uso.

É a única fonte para a CLI (`video-editores <op>`), para o servidor MCP (uma ferramenta por operação) e
para a documentação (docs/scripts.md). Dependências de modelo são declaradas pelo papel ("asr", "seg",
"tts") e resolvidas no backend configurado; pacotes fixos entram pelo nome.
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
    Operacao("doctor", "scripts/doctor.sh", "Verifica dependências (ffmpeg+libass, uv, CLIs, fontes, GPU)", ""),
    Operacao("docs-render", "scripts/render-docs.sh", "Montador do video-docs (gravações de tela -> vídeos de documentação)",
             "spec.json", ("tts", "pillow"), longa=True, skill="video-docs"),
    Operacao("cenas-tts", _A + "tts_cenas.py", "Narração por cena (TTS configurado) e tempos.json que dita as durações",
             "cenas/<slug>.json [--out PASTA] [--voz VOZ] [--glossario JSON] [--lead 0.6] [--tail 0.8]", ("tts",), longa=True, skill="video-animado"),
    Operacao("cenas-montar", _A + "montar_cenas.py", "Junta as cenas Manim com a narração e a legenda frase a frase",
             "cenas/<slug>.json PASTA_MP4 [--cenas A,B] [--jobs 2] [--loudness -16] [--tp -1.5] [--roteiro ARQ.md]", longa=True, skill="video-animado"),
    Operacao("cenas-folha", _A + "folha_cenas.py", "Um quadro por cena para aprovação", "cenas/<slug>.json", skill="video-animado"),
    Operacao("partitura", _P + "partitura.py", "Partitura de bateria (padrão JSON -> Verovio) em cartão PNG com a posição de cada nota",
             "padroes.json [ID ...] [--out partituras] [--tamanho card|big|ambos] [--compassos N] [--fonte ARQ.ttf]",
             ("verovio", "resvg-py", "pillow"), skill="partitura", saidas=("<id>.png", "<id>.json", "<id>_big.png", "<id>_big.json")),
    Operacao("partitura-tocar", _P + "tocar.py", "Exemplo tocado: som sintetizado + partitura animada nota a nota (bloco mp4 + wav)",
             "ID [--partituras partituras] [--out exemplos] [--bpm 72] [--voltas 2] [--contagem] [--fundo PNG] [--so-audio]",
             ("numpy", "scipy", "pillow"), longa=True, skill="partitura", saidas=("<id>.mp4", "<id>.wav", "<id>.json")),
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
    return {"VE_PKG_DIR": os.environ.get("VE_PKG_DIR") or pkg_dir}


def comando(nome: str, args, device=None, direto=False) -> list:
    """Linha de comando completa para a operação. Scripts .py com dependências rodam com
    `uv run --with …` (isolado, ADR-04); sem uv, ou com direto=True, usam o Python atual."""
    op = operacao(nome)
    p = str(op.caminho)
    if p.endswith(".sh"):
        return ["bash", p, *args]
    pk = op.pacotes(device)
    if pk and not direto and shutil.which("uv"):
        withs = [x for pkg in pk for x in ("--with", pkg)]
        return ["uv", "run", "--quiet", *withs, "python", "-I", p, *args]
    return [sys.executable, p, *args]
