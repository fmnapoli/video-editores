"""Tarefas em segundo plano para operações longas (recorte por IA, render, transcrição).

Cada tarefa é um processo detached (sessão própria, sobrevive ao fim do cliente) com log e um JSON de estado
em <raiz>/.video-editores/tarefas/<id>.json. Usado pelo servidor MCP e pela CLI (`--fundo`).
"""
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

PASTA = ".video-editores/tarefas"


class Tarefas:
    def __init__(self, raiz):
        self.raiz = Path(raiz).resolve()
        self.dir = self.raiz / PASTA
        self.dir.mkdir(parents=True, exist_ok=True)
        self._procs = {}

    def _arq(self, tid):
        return self.dir / f"{tid}.json"

    def _grava(self, t):
        self._arq(t["id"]).write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")

    def iniciar(self, nome, cmd, cwd=None, env=None) -> dict:
        tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        log = self.dir / f"{tid}.log"
        cwd = str(Path(cwd or self.raiz).resolve())
        rc_arq = self.dir / f"{tid}.rc"
        e = dict(os.environ)
        e.update(env or {})
        e["VE_RC"] = str(rc_arq)
        # Um bash fino grava o código de saída em .rc: assim qualquer processo (outra sessão do servidor, a CLI
        # `tarefas`) sabe se a tarefa terminou bem, não só quem a iniciou.
        envolto = ["bash", "-c", '"$@"; echo $? > "$VE_RC"', "video-editores", *cmd]
        with open(log, "wb") as lf:
            p = subprocess.Popen(envolto, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 start_new_session=True, env=e)
        t = {"id": tid, "nome": nome, "cmd": cmd, "cwd": cwd, "pid": p.pid, "inicio": time.time(),
             "estado": "rodando", "rc": None, "fim": None, "log": str(log), "rc_arq": str(rc_arq)}
        self._procs[tid] = p
        self._grava(t)
        return t

    def _vivo(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def status(self, tid, linhas_log=15) -> dict:
        arq = self._arq(tid)
        if not arq.is_file():
            raise KeyError(f"tarefa desconhecida: {tid}")
        t = json.loads(arq.read_text(encoding="utf-8"))
        if t["estado"] == "rodando":
            p = self._procs.get(tid)
            if p is not None:
                p.poll()
            rc_arq = Path(t.get("rc_arq", ""))
            if rc_arq.is_file() and rc_arq.read_text().strip():
                rc = int(rc_arq.read_text().strip())
                t.update(estado="ok" if rc == 0 else "erro", rc=rc, fim=rc_arq.stat().st_mtime)
            elif p is None and not self._vivo(t["pid"]):
                t.update(estado="terminada", fim=time.time())  # morreu sem gravar o rc (kill -9, queda)
            if t["estado"] != "rodando":
                self._grava(t)
        t["decorrido_s"] = round((t["fim"] or time.time()) - t["inicio"], 1)
        try:
            with open(t["log"], "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 8000))
                t["log_fim"] = f.read().decode("utf-8", "replace").splitlines()[-linhas_log:]
        except OSError:
            t["log_fim"] = []
        return t

    def esperar(self, tid, timeout=None, passo=1.0) -> dict:
        t0 = time.time()
        while True:
            t = self.status(tid)
            if t["estado"] != "rodando" or (timeout is not None and time.time() - t0 > timeout):
                return t
            time.sleep(passo)

    def cancelar(self, tid) -> dict:
        t = self.status(tid)
        if t["estado"] == "rodando":
            try:
                os.killpg(t["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
            t.update(estado="cancelada", fim=time.time())
            self._grava(t)
        return t

    def listar(self, n=20) -> list:
        ids = sorted((p.stem for p in self.dir.glob("*.json")), reverse=True)[:n]
        return [{k: v for k, v in self.status(i, 3).items() if k in ("id", "nome", "estado", "decorrido_s", "rc")} for i in ids]
