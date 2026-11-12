"""Servidor ComfyUI falso para os testes: as rotas que o backend `comfyui` usa, sem modelo nem GPU.

Uso: python3 comfyui_servidor.py PORTA_ARQ [--sem-checkpoint] [--falhar]
Escuta numa porta livre e grava o número em PORTA_ARQ; sai sozinho quando o processo pai morre. /prompt confere que o workflow chegou sem marcador
"{{...}}" e sem a chave "_ve"; /history responde vazio na 1ª consulta (job "rodando") e completo na 2ª;
/view devolve um PNG de cor sólida derivada da semente, no tamanho pedido. Recebidos vão para recebidos.json.
"""
import json
import os
import struct
import sys
import threading
import time
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CHECKPOINT = "flux1-schnell-fp8.safetensors"
SEM_CK = "--sem-checkpoint" in sys.argv
FALHAR = "--falhar" in sys.argv
JOBS, CONSULTAS, RECEBIDOS = {}, {}, []


def png(w, h, cor):
    linha = b"\x00" + bytes(cor) * w
    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(linha * h)) + ch(b"IEND", b""))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _resp(self, codigo, corpo, tipo="application/json"):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/system_stats":
            return self._resp(200, {"system": {"comfyui_version": "0.0.0-stub"},
                                    "devices": [{"name": "stub", "type": "cpu", "vram_total": 0}]})
        if u.path == "/object_info/CheckpointLoaderSimple":
            ops = [] if SEM_CK else [CHECKPOINT]
            return self._resp(200, {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["COMBO", {"options": ops}]}}}})
        if u.path.startswith("/history/"):
            pid = u.path.rsplit("/", 1)[1]
            CONSULTAS[pid] = CONSULTAS.get(pid, 0) + 1
            if pid not in JOBS or CONSULTAS[pid] < 2:
                return self._resp(200, {})
            if FALHAR:
                st = {"status_str": "error", "completed": False, "messages": [
                    ["execution_error", {"node_type": "KSampler", "exception_message": "CUDA out of memory (stub)"}]]}
                return self._resp(200, {pid: {"status": st, "outputs": {}}})
            nome = JOBS[pid]["prefixo"].rsplit("/", 1)[-1] + "_00001_.png"
            return self._resp(200, {pid: {"status": {"status_str": "success", "completed": True},
                                          "outputs": {"7": {"images": [{"filename": nome, "subfolder": "video-editores", "type": "output"}]}}}})
        if u.path == "/view":
            q = parse_qs(u.query)
            job = next(j for j in JOBS.values() if q["filename"][0].startswith(j["prefixo"].rsplit("/", 1)[-1] + "_"))
            s = job["semente"]
            return self._resp(200, png(job["w"], job["h"], (s * 37 % 256, s * 91 % 256, s * 13 % 256)), "image/png")
        self._resp(404, {"erro": u.path})

    def do_POST(self):
        if self.path != "/prompt":
            return self._resp(404, {})
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        wf = corpo["prompt"]
        texto = json.dumps(wf)
        if "{{" in texto or "_ve" in wf or any("class_type" not in n for n in wf.values()):
            return self._resp(400, {"error": {"type": "prompt_outputs_failed_validation"}, "node_errors": {"stub": texto[:300]}})
        RECEBIDOS.append(wf)
        with open("recebidos.json", "w") as f:
            json.dump(RECEBIDOS, f)
        pid = uuid.uuid4().hex
        lat = next(n for n in wf.values() if n["class_type"] == "EmptySD3LatentImage")["inputs"]
        ks = next(n for n in wf.values() if n["class_type"] == "KSampler")["inputs"]
        sv = next(n for n in wf.values() if n["class_type"] == "SaveImage")["inputs"]
        JOBS[pid] = {"w": lat["width"], "h": lat["height"], "semente": ks["seed"], "prefixo": sv["filename_prefix"]}
        self._resp(200, {"prompt_id": pid, "number": len(JOBS), "node_errors": {}})


def vigia(pai):
    """Encerra quando o processo que subiu o servidor morre: o teste nunca deixa servidor para trás."""
    while os.getppid() == pai:
        time.sleep(0.5)
    os._exit(0)


threading.Thread(target=vigia, args=(os.getppid(),), daemon=True).start()
srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
with open(sys.argv[1] + ".tmp", "w") as f:  # rename atômico: quem espera nunca lê o arquivo pela metade
    f.write(str(srv.server_address[1]))
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
srv.serve_forever()
