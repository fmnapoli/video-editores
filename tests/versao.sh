#!/usr/bin/env bash
# Confere que a versão é uma só: pyproject.toml, video_editores/__init__.py, .claude-plugin/plugin.json,
# topo do CHANGELOG.md e tags vX.Y.Z do git.
# Uso: tests/versao.sh   (só python3 e git; sem tags no clone, a parte das tags é pulada)
set -euo pipefail
ROOT="${VE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

python3 - <<'PY'
import json, os, re, subprocess, sys

def ler(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def tupla(v):
    return tuple(int(x) for x in v.split("."))

SEMVER = r"(\d+\.\d+\.\d+)"
erros = []

fontes = {}
m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', ler("pyproject.toml"))
fontes["pyproject.toml"] = m and m.group(1)
m = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', ler("video_editores/__init__.py"))
fontes["video_editores/__init__.py"] = m and m.group(1)
fontes[".claude-plugin/plugin.json"] = json.loads(ler(".claude-plugin/plugin.json")).get("version")

entradas = re.findall(r"(?m)^## " + SEMVER + r"\b", ler("CHANGELOG.md"))
fontes["CHANGELOG.md (topo)"] = entradas[0] if entradas else None

V = fontes["pyproject.toml"]
for nome, v in fontes.items():
    if v is None:
        erros.append(f"{nome}: versão não encontrada")
    elif not re.fullmatch(SEMVER, v):
        erros.append(f"{nome}: '{v}' não é X.Y.Z")
    elif v != V:
        erros.append(f"{nome}: {v} (pyproject.toml diz {V})")
if erros:
    sys.exit("versões divergentes:\n  " + "\n  ".join(erros))

# CHANGELOG em ordem decrescente e sem repetição
for a, b in zip(entradas, entradas[1:]):
    if tupla(a) <= tupla(b):
        erros.append(f"CHANGELOG.md: {a} aparece antes de {b} (fora de ordem ou repetida)")
print(f"  \033[32m✔\033[0m versão {V} igual em pyproject, __init__, plugin.json e CHANGELOG")

def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()

rc, saida = git("tag", "-l", "v*")
tags = [t for t in saida.split() if re.fullmatch("v" + SEMVER, t)] if rc == 0 else []
if not tags:
    print("  - sem tags vX.Y.Z neste clone: checagem das tags pulada")
else:
    for t in tags:
        if t[1:] not in entradas:
            erros.append(f"tag {t} sem entrada '## {t[1:]}' no CHANGELOG.md")
    maior = max(tags, key=lambda t: tupla(t[1:]))
    if tupla(maior[1:]) > tupla(V):
        erros.append(f"tag {maior} é maior que a versão do código ({V}): versão voltou ou bump faltando")
    _, raso = git("rev-parse", "--is-shallow-repository")
    if f"v{V}" in tags and raso != "true":
        rc, _ = git("merge-base", "--is-ancestor", f"v{V}", "HEAD")
        if rc != 0:
            erros.append(f"tag v{V} não está no histórico de HEAD: aponta para um commit fora desta linha")
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/v") and ref[len("refs/tags/v"):] != V:
        erros.append(f"CI rodando na tag {ref[len('refs/tags/'):]}, mas o código diz {V}")
    if not erros:
        situacao = "já tem tag" if f"v{V}" in tags else f"ainda sem tag (última: {maior})"
        print(f"  \033[32m✔\033[0m {len(tags)} tags com entrada no CHANGELOG; {V} {situacao}")

if erros:
    sys.exit("versão inconsistente:\n  " + "\n  ".join(erros))
PY
