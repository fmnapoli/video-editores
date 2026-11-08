"""TTS com edge-tts (vozes neurais da Microsoft, gratuito, precisa de internet). Fronteiras de palavra em segundos."""
import asyncio

from .base import Backend

VOZ_PADRAO = "pt-BR-ThalitaMultilingualNeural"


class EdgeTTS(Backend):
    nome = "edge"
    descricao = "edge-tts: vozes neurais pt-BR com WordBoundary; único passo do plugin que usa a internet"

    @staticmethod
    def deps(device="cpu"):
        return ["edge-tts"]

    def __init__(self, voz=VOZ_PADRAO):
        self.voz = voz

    async def _sintetizar(self, texto, voz, mp3):
        try:
            import edge_tts
        except ImportError:
            raise SystemExit("edge-tts não instalado: uv run --with edge-tts ...") from None
        com = edge_tts.Communicate(texto, voz, boundary="WordBoundary")
        ws = []
        with open(mp3, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    ws.append({"t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "w": ch["text"]})
        return ws

    def sintetizar(self, texto, voz=None, mp3="fala.mp3"):
        """Grava o mp3 e devolve [{"t": início, "d": duração, "w": palavra}, ...]."""
        return asyncio.run(self._sintetizar(texto, voz or self.voz, mp3))
