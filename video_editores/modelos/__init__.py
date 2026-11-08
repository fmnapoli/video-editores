"""Registro e configuração dos backends de modelo.

Configuração, em ordem de precedência:
  1. argumentos explícitos (`get_asr("faster-whisper")`, `--backend` nos scripts);
  2. variáveis de ambiente VE_ASR, VE_SEG, VE_TTS, VE_DEVICE (auto|cpu|cuda), VE_ENCODER (libx264|h264_nvenc|...);
  3. arquivo video-editores.toml ($VE_CONFIG ou ./video-editores.toml), seção [modelos];
  4. padrões: faster-whisper, rembg, edge, device auto, libx264.

Backends extras sem mexer no pacote: VE_MODELOS_EXTRA="asr:meu=pacote.modulo:Classe;seg:outro=mod:Cls".
"""
import importlib
import os
import shutil
from pathlib import Path

PADRAO = {"asr": "faster-whisper", "seg": "rembg", "tts": "edge", "device": "auto", "encoder": "libx264"}
_ENV = {"asr": "VE_ASR", "seg": "VE_SEG", "tts": "VE_TTS", "device": "VE_DEVICE", "encoder": "VE_ENCODER"}

REGISTRO = {
    "asr": {"faster-whisper": "video_editores.modelos.asr_faster_whisper:FasterWhisper"},
    "seg": {"rembg": "video_editores.modelos.seg_rembg:Rembg"},
    "tts": {"edge": "video_editores.modelos.tts_edge:EdgeTTS"},
}
TIPOS = tuple(REGISTRO)


def _toml():
    p = os.environ.get("VE_CONFIG") or "video-editores.toml"
    p = Path(p)
    if not p.is_file():
        return {}
    try:
        import tomllib
    except ImportError:  # Python 3.10
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f).get("modelos", {})


def config() -> dict:
    c = dict(PADRAO)
    c.update({k: str(v) for k, v in _toml().items() if k in c})
    for k, var in _ENV.items():
        if os.environ.get(var):
            c[k] = os.environ[var]
    return c


def _extras():
    spec = os.environ.get("VE_MODELOS_EXTRA", "")
    for item in filter(None, (s.strip() for s in spec.split(";"))):
        tipo, resto = item.split(":", 1)
        nome, caminho = resto.split("=", 1)
        registrar(tipo.strip(), nome.strip(), caminho.strip())


def registrar(tipo: str, nome: str, caminho: str):
    """caminho = "pacote.modulo:Classe"."""
    if tipo not in REGISTRO:
        raise KeyError(f"tipo de modelo desconhecido: {tipo} (use {', '.join(TIPOS)})")
    REGISTRO[tipo][nome] = caminho


def device() -> str:
    """Dispositivo efetivo: 'auto' vira cuda se houver driver NVIDIA visível, senão cpu."""
    d = config()["device"]
    if d != "auto":
        return d
    return "cuda" if shutil.which("nvidia-smi") else "cpu"


def classe(tipo: str, nome: "str | None" = None):
    _extras()
    nome = nome or config()[tipo]
    try:
        caminho = REGISTRO[tipo][nome]
    except KeyError:
        raise KeyError(f"backend {tipo}={nome!r} não registrado; disponíveis: {', '.join(REGISTRO[tipo])}") from None
    mod, cls = caminho.split(":")
    return getattr(importlib.import_module(mod), cls)


def deps(tipo: str, nome: "str | None" = None, dev: "str | None" = None) -> list:
    """Pacotes para `uv run --with` do backend escolhido, no dispositivo escolhido."""
    return list(classe(tipo, nome).deps(dev or device()))


def get_asr(nome=None, **kw):
    return classe("asr", nome)(**kw)


def get_segmentador(nome=None, **kw):
    return classe("seg", nome)(**kw)


def get_tts(nome=None, **kw):
    return classe("tts", nome)(**kw)


def listar() -> dict:
    """Backends registrados por tipo, com o escolhido e as dependências de cada um."""
    _extras()
    c = config()
    dev = device()
    out = {"config": c, "device_efetivo": dev, "tipos": {}}
    for tipo, backs in REGISTRO.items():
        out["tipos"][tipo] = {"escolhido": c[tipo], "backends": {}}
        for nome in backs:
            try:
                cls = classe(tipo, nome)
                out["tipos"][tipo]["backends"][nome] = {"descricao": cls.descricao, "deps": list(cls.deps(dev))}
            except Exception as e:  # backend extra quebrado não derruba a listagem
                out["tipos"][tipo]["backends"][nome] = {"erro": str(e)}
    return out
