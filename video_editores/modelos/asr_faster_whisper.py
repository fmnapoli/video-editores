"""ASR com faster-whisper (CTranslate2). Padrão validado: `medium` + initial_prompt com vocabulário, VAD, int8 em CPU."""
from .base import Backend, Palavra, Segmento, Transcricao


class FasterWhisper(Backend):
    nome = "faster-whisper"
    descricao = "Whisper via CTranslate2; medium+prompt é o padrão validado, large-v3 em GPU"

    @staticmethod
    def deps(device="cpu"):
        return ["faster-whisper"]

    def __init__(self, modelo="medium", device="auto", compute_type=None):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise SystemExit("faster-whisper não instalado: uv run --with faster-whisper ...") from None
        if compute_type is None:
            compute_type = "int8" if device in ("auto", "cpu") else "float16"
        self.modelo = WhisperModel(modelo, device=device, compute_type=compute_type)

    def transcrever(self, audio, lang="pt", prompt=None, vad=True) -> Transcricao:
        """audio: caminho ou numpy float32 mono 16 kHz (ver nucleo.ffmpeg.decodificar_audio)."""
        segs, info = self.modelo.transcribe(audio, language=None if lang in (None, "auto") else lang,
                                            word_timestamps=True, vad_filter=vad, initial_prompt=prompt)
        out = []
        for s in segs:
            ws = [Palavra(w.start, w.end, w.word) for w in (s.words or [])]
            out.append(Segmento(s.start, s.end, s.text.strip(), ws, s.avg_logprob, s.no_speech_prob))
        return Transcricao(info.language, info.duration, out)
