"""Contratos dos modelos de IA usados pelo plugin. Os backends ficam nos módulos ao lado.

Quatro papéis, cada um com um método principal:
  ASR          transcrever(áudio) -> Transcricao           (faster-whisper, ...)
  Segmentador  mascara(imagem) -> máscara da pessoa (PIL L) (rembg/U²-Net, BiRefNet, ...)
  TTS          sintetizar(texto, voz, mp3) -> fronteiras de palavra  (edge-tts, ...)
  Imagem       gerar(prompt, pasta, sementes, ...) -> PNGs, um por semente  (ComfyUI, ...)  (ADR-15)

Um backend declara `nome`, `descricao` e `deps(device)` (pacotes para `uv run --with`). Importações
pesadas ficam dentro dos métodos, para que listar e configurar backends não exija os modelos instalados.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Palavra:
    start: float
    end: float
    word: str


@dataclass
class Segmento:
    start: float
    end: float
    text: str
    words: list = field(default_factory=list)   # list[Palavra]
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass
class Transcricao:
    language: str
    duration: float
    segments: list = field(default_factory=list)  # list[Segmento]

    def to_dict(self, source: str = "") -> dict:
        d = {"source": source, "language": self.language, "duration": self.duration,
             "segments": [asdict(s) for s in self.segments]}
        return d

    @property
    def palavras(self) -> list:
        return [w for s in self.segments for w in s.words]


class Backend:
    nome: str = ""
    descricao: str = ""

    @staticmethod
    def deps(device: str = "cpu") -> list:
        return []

    def info(self) -> dict:
        return {"nome": self.nome, "descricao": self.descricao}


@runtime_checkable
class ASR(Protocol):
    def transcrever(self, audio: Any, lang: str = "pt", prompt: "str | None" = None, vad: bool = True) -> Transcricao: ...


@runtime_checkable
class Segmentador(Protocol):
    def mascara(self, img: Any, pos_processar: bool = True) -> Any: ...
    def recortar(self, img: Any) -> Any: ...


@runtime_checkable
class TTS(Protocol):
    def sintetizar(self, texto: str, voz: str, mp3: str) -> list: ...


@runtime_checkable
class Imagem(Protocol):
    def gerar(self, prompt: str, saida_dir: Any, negativo: str = "", largura: int = 1344, altura: int = 768,
              sementes: tuple = (0,), passos: "int | None" = None, prefixo: str = "ve") -> list: ...
