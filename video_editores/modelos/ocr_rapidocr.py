"""OCR com o RapidOCR (modelos PP-OCR em ONNX, Apache-2.0): lê texto de print e de quadro de vídeo, com a
caixa de cada linha e de cada palavra. Roda em CPU pelo onnxruntime, o mesmo runtime do recorte de pessoa.
Reconhece acentos do português com os modelos que vêm no pacote."""
from .base import Backend, Caixa, LinhaOCR


def _caixa(pontos, texto="", conf=1.0):
    xs = [float(p[0]) for p in pontos]
    ys = [float(p[1]) for p in pontos]
    return Caixa(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), round(float(conf), 3), texto)


class RapidOCR(Backend):
    nome = "rapidocr"
    descricao = "RapidOCR/onnxruntime com modelos PP-OCR (Apache-2.0): linhas e palavras com caixa, CPU"

    @staticmethod
    def deps(device="cpu"):
        return ["rapidocr", "onnxruntime-gpu" if device == "cuda" else "onnxruntime"]

    def __init__(self, device="cpu"):
        try:
            from rapidocr import RapidOCR as _Motor
        except ImportError:
            raise SystemExit("faltam dependências: uv run --with rapidocr --with onnxruntime ...") from None
        # o RapidOCR registra em INFO cada modelo que carrega, colorido, no stderr: só avisos e erros interessam
        self._motor = _Motor(params={"Global.log_level": "error"})

    def ler(self, imagem):
        """Imagem BGR (numpy) ou caminho -> lista de LinhaOCR, de cima para baixo, em pixels da imagem."""
        r = self._motor(imagem, return_word_box=True)
        if r is None or r.boxes is None or not r.txts:
            return []
        palavras = r.word_results or [()] * len(r.txts)
        linhas = []
        for texto, conf, pts, pals in zip(r.txts, r.scores, r.boxes, palavras):
            ws = [_caixa(p[2], p[0], p[1]) for p in pals if p and str(p[0]).strip()]
            linhas.append(LinhaOCR(str(texto), _caixa(pts, str(texto), conf), ws))
        return sorted(linhas, key=lambda ln: (ln.caixa.y, ln.caixa.x))
