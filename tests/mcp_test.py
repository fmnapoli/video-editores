"""Testa o servidor MCP em processo (Client em memória, sem porta nem subprocesso).
Uso: uv run --with mcp python -I tests/mcp_test.py PASTA_PROJETO   (a pasta tem um in.mp4 curto)
"""
import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from mcp import Client  # noqa: E402

from video_editores.mcp_server import criar_servidor  # noqa: E402


async def main(raiz):
    os.chdir(raiz)
    srv = criar_servidor(raiz)
    async with Client(srv) as c:
        tools = {t.name for t in (await c.list_tools()).tools}
        esperadas = {"listar_operacoes", "listar_modelos", "executar_operacao", "transcrever", "recortar_pessoa",
                     "lettering", "prova", "videoaula_montar", "videoaula_finalizar", "tarefa_status",
                     "tarefa_esperar", "tarefa_cancelar", "tarefas_listar", "ler_texto", "versao"}
        assert esperadas <= tools, esperadas - tools
        ops = (await c.call_tool("listar_operacoes", {})).structured_content["result"]
        assert any(o["nome"] == "aula-recorte" and o["longa"] and o["deps"] == ["seg"] for o in ops), ops
        mod = (await c.call_tool("listar_modelos", {})).structured_content
        assert mod["tipos"]["seg"]["escolhido"] == "rembg", mod
        # operação curta síncrona: prova gera os 3 artefatos
        r = (await c.call_tool("prova", {"video": "in.mp4", "quadros": 4})).structured_content
        assert r["estado"] == "ok" and r["rc"] == 0, r
        assert os.path.exists("in.proof.jpg") and os.path.exists("in.proof.txt"), os.listdir(".")
        # operação longa em segundo plano: volta "rodando" e termina via tarefa_esperar
        r = (await c.call_tool("executar_operacao", {"operacao": "montar-trechos", "argumentos": ["in.mp4", "k.json", "t.mp4"]})).structured_content
        assert r["estado"] in ("rodando", "ok"), r
        fim = (await c.call_tool("tarefa_esperar", {"id": r["id"], "timeout_s": 120})).structured_content
        assert fim["estado"] == "ok" and os.path.exists("t.mp4"), fim
        lst = (await c.call_tool("tarefas_listar", {"n": 5})).structured_content["result"]
        assert any(t["id"] == r["id"] for t in lst), lst
        # ler_texto dentro da raiz funciona; fora, é recusado
        txt = (await c.call_tool("ler_texto", {"caminho": "in.proof.txt"})).structured_content["result"]
        assert "quadros" in txt, txt[:200]
        async def falha(nome, args):
            try:
                r = await c.call_tool(nome, args)
            except Exception:
                return True
            return bool(getattr(r, "is_error", False))
        assert await falha("ler_texto", {"caminho": "/etc/hostname"}), "leu fora da raiz"
        assert await falha("executar_operacao", {"operacao": "prova", "argumentos": ["../../in.mp4"]}), "caminho fora da raiz aceito"
        assert await falha("executar_operacao", {"operacao": "nao-existe", "argumentos": []}), "operação inexistente aceita"
        v = (await c.call_tool("versao", {})).structured_content
        print(json.dumps({"tools": len(tools), "versao": v["video_editores"], "device": v["device"]}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
