"""Backends falsos de `rosto` e `ocr` para os testes: mesma interface dos reais, sem modelo nem download.

Entram por VE_MODELOS_EXTRA="rosto:fixo=modelos_falsos:RostoFixo;ocr:fixo=modelos_falsos:OcrFixo" com
PYTHONPATH apontando para tests/stub. RostoFixo devolve sempre a caixa de VE_TESTE_ROSTO ("x,y,l,a" em fração do
quadro; vazio = nenhum rosto). OcrFixo devolve as linhas do JSON em VE_TESTE_OCR
([{"texto": ..., "caixa": [x, y, l, a], "palavras": [[texto, x, y, l, a], ...]}], em fração da imagem).
"""
import json
import os

from video_editores.modelos.base import Backend, Caixa, LinhaOCR


class RostoFixo(Backend):
    nome = "fixo"
    descricao = "rosto em posição fixa (testes)"

    def __init__(self, device="cpu"):
        v = os.environ.get("VE_TESTE_ROSTO", "")
        self.caixa = [float(x) for x in v.split(",")] if v else None

    def detectar(self, quadro, min_conf=0.6):
        if not self.caixa:
            return []
        h, w = quadro.shape[:2]
        x, y, lw, lh = self.caixa
        return [Caixa(x * w, y * h, lw * w, lh * h, 0.99)]


class OcrFixo(Backend):
    nome = "fixo"
    descricao = "texto em posição fixa (testes)"

    def __init__(self, device="cpu"):
        with open(os.environ["VE_TESTE_OCR"], encoding="utf-8") as f:
            self.linhas = json.load(f)

    def ler(self, imagem):
        h, w = imagem.shape[:2]
        out = []
        for ln in self.linhas:
            x, y, lw, lh = ln["caixa"]
            pals = [Caixa(p[1] * w, p[2] * h, p[3] * w, p[4] * h, 0.99, p[0]) for p in ln.get("palavras", [])]
            out.append(LinhaOCR(ln["texto"], Caixa(x * w, y * h, lw * w, lh * h, 0.99, ln["texto"]), pals))
        return out
