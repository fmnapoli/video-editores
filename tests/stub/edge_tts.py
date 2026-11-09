"""Stub offline do edge_tts para testes: gera um tom por palavra (~2,7 palavras/s) e WordBoundary sintéticos.

Ativado com PYTHONPATH=tests/stub. Nunca usado em produção.
"""
import os
import subprocess
import tempfile

_falhas = [int(os.environ.get("VE_STUB_EDGE_FALHAS", "0"))]   # as N primeiras chamadas falham como o serviço real


class exceptions:
    class NoAudioReceived(Exception):
        pass


class Communicate:
    def __init__(self, text, voice="stub", boundary="WordBoundary", **_):
        self.text, self.voice = text, voice

    async def stream(self):
        if _falhas[0] > 0:
            _falhas[0] -= 1
            raise exceptions.NoAudioReceived("No audio was received. Please verify that your parameters are correct.")
        words = self.text.split()
        per = 1 / 2.7
        dur = max(0.5, len(words) * per)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
            path = t.name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=220:d={dur:.3f}",
                        "-b:a", "48k", path], check=True)
        with open(path, "rb") as f:
            yield {"type": "audio", "data": f.read()}
        for i, w in enumerate(words):
            yield {"type": "WordBoundary", "offset": int(i * per * 1e7), "duration": int(per * 0.9 * 1e7), "text": w}
