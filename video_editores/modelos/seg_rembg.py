"""Segmentação de pessoa com rembg (U²-Net human seg por padrão; birefnet-portrait para bordas melhores em GPU)."""
from .base import Backend


class Rembg(Backend):
    nome = "rembg"
    descricao = "rembg/onnxruntime: u2net_human_seg (rápido) ou birefnet-portrait (cabelo melhor, 3-5x mais lento)"

    @staticmethod
    def deps(device="cpu"):
        ort = "onnxruntime-gpu" if device == "cuda" else "onnxruntime"
        return ["rembg", ort, "pillow", "numpy"]

    def __init__(self, modelo="u2net_human_seg", device="cpu", threads=4):
        try:
            import onnxruntime as ort
            from rembg import new_session, remove
        except ImportError:
            raise SystemExit("faltam dependências: uv run --with rembg --with onnxruntime --with pillow --with numpy ...") from None
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"] if device == "cuda" else ["CPUExecutionProvider"]
        self._remove = remove
        self.sessao = new_session(modelo, sess_opts=so, providers=prov)
        self.providers = self.sessao.inner_session.get_providers() if hasattr(self.sessao, "inner_session") else prov

    def mascara(self, img, pos_processar=True):
        """PIL RGB -> PIL L (255 = pessoa)."""
        return self._remove(img, session=self.sessao, only_mask=True, post_process_mask=pos_processar)

    def recortar(self, img):
        """PIL -> PIL RGBA com alpha = pessoa."""
        return self._remove(img, session=self.sessao)
