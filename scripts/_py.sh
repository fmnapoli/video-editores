# shellcheck shell=bash
# Interpretador Python dos scripts .sh do plugin (para dar `source`, não para executar).
# Define VE_PY (python3; no Windows, onde o instalador do python.org só cria `python`, cai nele) e a função
# `py`, para quando a saída é capturada em $(...): no Windows o Python termina as linhas com \r\n e o bash só
# tira o \n, então o \r ia parar dentro do filtro do ffmpeg e do nome de arquivo.
# `python3 -c ''` em vez de `command -v`: no Windows `python3` pode ser o atalho da Microsoft Store, que existe
# no PATH e não roda nada.
if python3 -c '' >/dev/null 2>&1; then
  VE_PY=python3
elif python -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
  VE_PY=python
else
  echo "erro: Python 3 não encontrado (nem python3 nem python); instale o Python 3.10+" >&2
  exit 1
fi
export VE_PY
# Windows: arquivos e saída em UTF-8 (o padrão lá é cp1252 e os acentos do roteiro saíam trocados).
export PYTHONUTF8="${PYTHONUTF8:-1}"

py() {
  "$VE_PY" "$@" | tr -d '\r'
  return "${PIPESTATUS[0]}"
}

# ffprobe com a saída capturada em $(...): mesma história do \r no Windows.
sonda() {
  ffprobe "$@" | tr -d '\r'
  return "${PIPESTATUS[0]}"
}
