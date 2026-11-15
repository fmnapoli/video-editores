"""Detecção de rosto com o YuNet (OpenCV `FaceDetectorYN`): modelo de 230 KB, CPU, dezenas de quadros por segundo.

O arquivo do modelo (licença MIT, opencv_zoo) não vem no pacote do OpenCV: é baixado uma vez para o cache
(`$VE_CACHE` ou `~/.cache/video-editores/modelos/`) e conferido por sha256. `VE_YUNET_MODELO` aponta um arquivo
já baixado (máquina sem rede).
"""
import hashlib
import os
import urllib.request
from pathlib import Path

from .base import Backend, Caixa

ARQUIVO = "face_detection_yunet_2023mar.onnx"
URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/" + ARQUIVO
SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def caminho_modelo() -> Path:
    """Arquivo do modelo, baixando para o cache na primeira vez. Encerra com instrução clara se não der."""
    fixo = os.environ.get("VE_YUNET_MODELO")
    if fixo:
        if not Path(fixo).is_file():
            raise SystemExit(f"VE_YUNET_MODELO={fixo}: arquivo não existe")
        return Path(fixo)
    cache = Path(os.environ.get("VE_CACHE") or Path.home() / ".cache" / "video-editores") / "modelos"
    alvo = cache / ARQUIVO
    if alvo.is_file() and _sha(alvo) == SHA256:
        return alvo
    cache.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_suffix(".baixando")
    try:
        with urllib.request.urlopen(URL, timeout=60) as r:
            tmp.write_bytes(r.read())
    except OSError as e:
        raise SystemExit(f"não consegui baixar o modelo de rosto ({e}).\n"
                         f"Baixe {URL}\ne aponte com VE_YUNET_MODELO=/caminho/{ARQUIVO}") from None
    if _sha(tmp) != SHA256:
        tmp.unlink()
        raise SystemExit(f"modelo de rosto baixado com sha256 diferente do esperado ({SHA256[:12]}…): download recusado")
    tmp.replace(alvo)
    return alvo


class YuNet(Backend):
    nome = "yunet"
    descricao = "YuNet via OpenCV FaceDetectorYN (modelo MIT de 230 KB, CPU); rosto de frente e de três quartos"

    @staticmethod
    def deps(device="cpu"):
        return ["opencv-python-headless", "numpy"]

    def __init__(self, device="cpu", nms=0.3):
        try:
            import cv2
        except ImportError:
            raise SystemExit("faltam dependências: uv run --with opencv-python-headless --with numpy ...") from None
        try:   # o OpenCV 5 avisa "Targets are not supported by the new graph engine" a cada criação
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        except AttributeError:
            pass
        self._det = cv2.FaceDetectorYN.create(str(caminho_modelo()), "", (320, 320), 0.3, nms, 5000)
        self._tam = None

    def detectar(self, quadro, min_conf=0.6):
        """Quadro BGR (numpy HxWx3) -> lista de Caixa em pixels do próprio quadro, da maior para a menor."""
        h, w = quadro.shape[:2]
        if self._tam != (w, h):
            self._det.setInputSize((w, h))
            self._tam = (w, h)
        _, faces = self._det.detect(quadro)
        out = []
        for f in (faces if faces is not None else []):
            x, y, fw, fh, conf = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])
            if conf < min_conf:
                continue
            x0, y0 = max(0.0, x), max(0.0, y)
            x1, y1 = min(float(w), x + fw), min(float(h), y + fh)
            if x1 - x0 > 1 and y1 - y0 > 1:
                out.append(Caixa(x0, y0, x1 - x0, y1 - y0, round(conf, 3)))
        return sorted(out, key=lambda c: -c.w * c.h)
