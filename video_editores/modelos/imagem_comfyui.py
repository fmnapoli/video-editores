"""Imagem gerada por um servidor ComfyUI (github.com/comfy-org/ComfyUI), pela API HTTP. ADR-15.

O ComfyUI é GPL-3.0 e roda como processo separado (ADR-05: GPL só como executável à parte): o plugin não importa
nada dele, só envia um workflow em JSON e baixa o PNG. O servidor pode estar em outra máquina, a que tem a GPU:
`VE_COMFYUI_URL` aponta para ele (padrão http://127.0.0.1:8188).

Workflows ficam em `workflows/comfyui/<nome>.json`, no formato de API do ComfyUI, só com nós nativos (nó de
terceiro é código arbitrário rodando no servidor). Os valores variáveis são marcadores de string inteira:
"{{prompt}}", "{{negativo}}", "{{largura}}", "{{altura}}", "{{semente}}", "{{passos}}", "{{prefixo}}",
"{{checkpoint}}". A chave "_ve" descreve modelo, licença, arquivo do checkpoint e onde baixar; não vai ao servidor.

Variáveis: VE_COMFYUI_URL, VE_COMFYUI_WORKFLOW (nome ou caminho), VE_COMFYUI_CHECKPOINT (outro arquivo no lugar
do declarado), VE_COMFYUI_TIMEOUT (s, padrão 900), VE_COMFYUI_POLL (s entre consultas, padrão 1).
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .base import Backend

WORKFLOWS = Path(__file__).with_name("workflows") / "comfyui"
URL_PADRAO = "http://127.0.0.1:8188"
WORKFLOW_PADRAO = "flux-schnell"


def workflows() -> list:
    return sorted(p.stem for p in WORKFLOWS.glob("*.json"))


def _preencher(no, valores):
    if isinstance(no, dict):
        return {k: _preencher(v, valores) for k, v in no.items()}
    if isinstance(no, list):
        return [_preencher(v, valores) for v in no]
    if isinstance(no, str) and no.startswith("{{") and no.endswith("}}"):
        chave = no[2:-2]
        if chave not in valores:
            raise ValueError(f"marcador desconhecido no workflow: {no}")
        return valores[chave]
    return no


def _erro_execucao(status) -> str:
    for tipo, dados in status.get("messages", []):
        if tipo == "execution_error":
            return f"{dados.get('node_type', '?')}: {dados.get('exception_message', '').strip()}"
    return "erro sem detalhe; veja o log do servidor"


class ComfyUI(Backend):
    nome = "comfyui"
    descricao = "servidor ComfyUI (GPL-3.0, processo à parte, local ou remoto) pela API HTTP; workflow padrão FLUX.1-schnell"

    @staticmethod
    def deps(device="cpu"):
        return []  # só biblioteca padrão: o modelo e a GPU ficam no servidor

    def __init__(self, url=None, workflow=None, timeout=None):
        self.url = (url or os.environ.get("VE_COMFYUI_URL") or URL_PADRAO).rstrip("/")
        w = workflow or os.environ.get("VE_COMFYUI_WORKFLOW") or WORKFLOW_PADRAO
        arq = Path(w)
        if not arq.is_file():
            arq = WORKFLOWS / f"{w}.json"
        if not arq.is_file():
            raise ValueError(f"workflow {w!r} não encontrado; do plugin: {', '.join(workflows())}, ou um caminho .json")
        self.workflow_arq = arq
        bruto = arq.read_bytes()
        self.workflow_sha256 = hashlib.sha256(bruto).hexdigest()
        self.workflow = json.loads(bruto)
        self.meta = self.workflow.pop("_ve", {})
        self.timeout = float(timeout or os.environ.get("VE_COMFYUI_TIMEOUT", "900"))

    # --- HTTP --------------------------------------------------------------------------------------------------
    def _req(self, caminho, dados=None, timeout=30):
        corpo = None if dados is None else json.dumps(dados).encode()
        cab = {"Content-Type": "application/json"} if corpo else {}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + caminho, data=corpo, headers=cab), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", "replace")[:2000]
            raise RuntimeError(f"ComfyUI {caminho.split('?')[0]}: HTTP {e.code}: {detalhe}") from None
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(f"ComfyUI fora do ar em {self.url} ({getattr(e, 'reason', e)}); "
                               "suba o servidor ou ajuste VE_COMFYUI_URL") from None

    def _json(self, caminho, dados=None, timeout=30):
        return json.loads(self._req(caminho, dados, timeout))

    # --- servidor ----------------------------------------------------------------------------------------------
    def servidor(self, timeout=30) -> dict:
        s = self._json("/system_stats", timeout=timeout)
        return {"url": self.url, "versao": s.get("system", {}).get("comfyui_version", "?"),
                "dispositivos": [{"nome": d.get("name"), "tipo": d.get("type"),
                                  "vram_gb": round(d.get("vram_total", 0) / 2**30, 1)} for d in s.get("devices", [])]}

    def checkpoints(self) -> list:
        campo = self._json("/object_info/CheckpointLoaderSimple")["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
        opcoes = campo[0]
        if opcoes == "COMBO":  # formato novo: ["COMBO", {"options": [...]}]
            opcoes = campo[1].get("options", [])
        return list(opcoes)

    def checkpoint(self) -> str:
        return os.environ.get("VE_COMFYUI_CHECKPOINT") or self.meta.get("arquivo", "")

    def conferir(self, timeout=30) -> dict:
        """Servidor no ar e checkpoint do workflow presente nele. Devolve a info do servidor; erro diz onde baixar."""
        info = self.servidor(timeout=timeout)
        ck = self.checkpoint()
        if ck and "{{checkpoint}}" in json.dumps(self.workflow):
            disp = self.checkpoints()
            if ck not in disp:
                onde = f" Baixe de {self.meta['fonte']} para {self.meta.get('pasta', 'models/checkpoints/')}." if self.meta.get("fonte") else ""
                raise RuntimeError(f"checkpoint {ck!r} não está no servidor ({len(disp)} disponíveis: "
                                   f"{', '.join(disp[:8]) or 'nenhum'}).{onde} Outro arquivo: VE_COMFYUI_CHECKPOINT.")
        return info

    def info(self) -> dict:
        d = super().info()
        d.update(url=self.url, workflow=self.workflow_arq.stem, workflow_sha256=self.workflow_sha256,
                 modelo=self.meta.get("modelo"), licenca=self.meta.get("licenca"), checkpoint=self.checkpoint())
        return d

    # --- geração -----------------------------------------------------------------------------------------------
    def gerar(self, prompt, saida_dir, negativo="", largura=1344, altura=768, sementes=(0,), passos=None, prefixo="ve"):
        """Um job por semente; espera todos e grava <saida_dir>/<prefixo>-<semente>.png. Devolve os caminhos na
        ordem das sementes. Mesma semente, workflow e checkpoint no mesmo servidor: mesma imagem."""
        passos = int(passos or self.meta.get("passos", 4))
        cliente = uuid.uuid4().hex
        fila = {}
        for s in sementes:
            wf = _preencher(self.workflow, {
                "prompt": prompt, "negativo": negativo or "", "largura": int(largura), "altura": int(altura),
                "semente": int(s), "passos": passos, "prefixo": f"video-editores/{prefixo}-{s}", "checkpoint": self.checkpoint()})
            r = self._json("/prompt", {"prompt": wf, "client_id": cliente})
            if r.get("node_errors"):
                raise RuntimeError(f"workflow recusado pelo servidor: {json.dumps(r['node_errors'], ensure_ascii=False)[:2000]}")
            fila[r["prompt_id"]] = int(s)

        pasta = Path(saida_dir)
        pasta.mkdir(parents=True, exist_ok=True)
        feitos = {}
        limite = time.monotonic() + self.timeout
        pausa = float(os.environ.get("VE_COMFYUI_POLL", "1"))
        while True:
            for pid, s in fila.items():
                if pid in feitos:
                    continue
                h = self._json(f"/history/{pid}").get(pid)
                if not h:
                    continue  # ainda na fila ou rodando
                st = h.get("status", {})
                if st.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI falhou na semente {s}: {_erro_execucao(st)}")
                if not st.get("completed", True):
                    continue
                imgs = [i for o in h.get("outputs", {}).values() for i in o.get("images", []) if i.get("type", "output") == "output"]
                if not imgs:
                    raise RuntimeError(f"semente {s}: o workflow terminou sem imagem de saída (falta um SaveImage?)")
                q = urllib.parse.urlencode({k: imgs[0].get(k, "") for k in ("filename", "subfolder", "type")})
                destino = pasta / f"{prefixo}-{s}.png"
                destino.write_bytes(self._req(f"/view?{q}", timeout=120))
                feitos[pid] = destino
            if len(feitos) == len(fila):
                return [feitos[p] for p in fila]
            if time.monotonic() > limite:
                raise RuntimeError(f"ComfyUI não terminou em {self.timeout:.0f}s ({len(feitos)}/{len(fila)} prontas); "
                                   "aumente VE_COMFYUI_TIMEOUT se o servidor estiver só lento")
            time.sleep(pausa)
