# shellcheck shell=bash
# Diferenças de plataforma dos testes (para dar `source`). No Linux e no macOS só define `caminho` e `tmpdir`.
# No Windows os testes rodam no Git Bash, com Python e ffmpeg nativos, e três coisas mudam:
#   - caminho: /tmp/x e /d/a/x só existem dentro do bash. `cygpath -m` devolve C:/..., que vale para o bash, para
#     o Python e dentro de um texto (heredoc, JSON, filtro do ffmpeg), onde o Git Bash não converte nada;
#   - fim de linha: Python e ffprobe escrevem \r\n e o $(...) só tira o \n; as funções abaixo tiram o \r;
#   - codificação: PYTHONUTF8=1, senão o Python lê e escreve em cp1252.
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) VE_WIN=1 ;; *) VE_WIN=0 ;; esac
if [ "$VE_WIN" = 1 ]; then
  export PYTHONUTF8=1
  export SEP=";"   # separador de lista de caminhos (PYTHONPATH): com C:/..., o ":" do Unix não serve
  caminho() { cygpath -m "$1"; }
  # Processo em segundo plano cujo PID interessa: chame `command python3` (ou `exec python3`), não a função.
  python3() { command python3 "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }
  ffprobe() { command ffprobe "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }
else
  export SEP=":"
  caminho() { printf '%s\n' "$1"; }
fi
tmpdir() { caminho "$(mktemp -d)"; }
# Pasta do TTF de uma fonte instalada (fontconfig, ou o registro de fontes no Windows).
pasta_da_fonte() { dirname "$(PYTHONPATH="$ROOT" python3 -m video_editores.nucleo.fontes "$@")"; }
