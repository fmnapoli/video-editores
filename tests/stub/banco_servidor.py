"""Banco de vídeo falso para os testes do banco_video.py: as rotas da API de busca que o script usa, sem rede.

Uso: python3 banco_servidor.py PORTA_ARQ   (na pasta com mini.jpg e clipe.mp4, que ele serve)
Escuta numa porta livre e grava o número em PORTA_ARQ; sai quando o processo pai morre. /v1/videos/search exige
o cabeçalho Authorization igual a "chave-teste" (senão 401) e devolve três vídeos de 2, 10 e 20 s; as consultas
recebidas vão para recebidos.json.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

RECEBIDOS = []


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
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        if u.path == "/v1/videos/search":
            if self.headers.get("Authorization") != "chave-teste":
                return self._resp(401, {"error": "Unauthorized"})
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            RECEBIDOS.append(q)
            with open("recebidos.json", "w") as f:
                json.dump(RECEBIDOS, f)
            if q.get("query") == "nada":
                return self._resp(200, {"videos": []})
            vids = [{"id": 100 + i, "width": 1920, "height": 1080, "duration": d, "url": f"https://banco.exemplo/video/{100 + i}/",
                     "image": f"{base}/mini.jpg", "user": {"name": f"Autora {i}", "url": f"https://banco.exemplo/@autora{i}"},
                     "video_files": [{"file_type": "video/mp4", "width": 640, "height": 360, "fps": 30, "link": f"{base}/clipe.mp4?h=360"},
                                     {"file_type": "video/mp4", "width": 1920, "height": 1080, "fps": 30, "link": f"{base}/clipe.mp4?h=1080"},
                                     {"file_type": "application/x-mpegURL", "width": None, "height": None, "link": f"{base}/x.m3u8"}]}
                    for i, d in enumerate((2, 10, 20), 1)]
            return self._resp(200, {"videos": vids})
        if u.path in ("/mini.jpg", "/clipe.mp4"):
            with open(u.path[1:], "rb") as f:
                return self._resp(200, f.read(), "image/jpeg" if u.path.endswith(".jpg") else "video/mp4")
        if u.path == "/erro.html":   # o banco devolve uma página no lugar do vídeo
            return self._resp(200, b"<html>pagina de erro</html>", "text/html")
        self._resp(404, {"error": "not found"})


def _vigia(pai):
    while os.getppid() == pai:
        time.sleep(0.5)
    os._exit(0)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=_vigia, args=(os.getppid(),), daemon=True).start()
    with open(sys.argv[1] + ".tmp", "w") as f:
        f.write(str(srv.server_address[1]))
    os.replace(sys.argv[1] + ".tmp", sys.argv[1])
    srv.serve_forever()
