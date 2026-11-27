"""Onde está o arquivo de uma fonte instalada, em Linux, macOS e Windows.

Os scripts medem texto com o Pillow e por isso precisam do TTF, não só do nome da família. No Linux e no macOS
quem responde é o fontconfig (`fc-match`); no Windows não há fontconfig, e a resposta vem do registro, que liga
"Arial Bold (TrueType)" a `arialbd.ttf`. Por último, o nome do arquivo nas pastas de fontes do sistema.

Como comando (usado pelos testes e pelo doctor):
  python -m video_editores.nucleo.fontes "DejaVu Sans" [bold]    imprime o caminho; sai com 1 se não achar
"""
import os
import re
import shutil
import subprocess
import sys


def pastas() -> list:
    """Pastas de fontes do sistema e do usuário que existem nesta máquina."""
    casa = os.path.expanduser("~")
    if os.name == "nt":
        cands = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                 os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(casa, "AppData", "Local")),
                              "Microsoft", "Windows", "Fonts")]
    elif sys.platform == "darwin":
        cands = [os.path.join(casa, "Library", "Fonts"), "/Library/Fonts", "/System/Library/Fonts",
                 "/opt/homebrew/share/fonts", "/usr/local/share/fonts"]
    else:
        cands = [os.path.join(casa, ".local", "share", "fonts"), os.path.join(casa, ".fonts"),
                 "/usr/share/fonts", "/usr/local/share/fonts"]
    return [c for c in cands if os.path.isdir(c)]


def _chave(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _fontconfig(familia, estilo):
    """(arquivo, a família confere). O fontconfig sempre devolve alguma fonte; a segunda parte diz se é a pedida."""
    if not shutil.which("fc-match"):
        return None, False
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}|%{family}", f"{familia}:{estilo}" if estilo else familia],
                             capture_output=True, text=True, check=True).stdout.strip()
        arq, fam = out.split("|", 1)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None, False
    return (arq or None), familia.lower() in fam.lower()


def _registro(familia, estilo):
    """Windows: nome da fonte -> arquivo, nas chaves da máquina e do usuário."""
    try:
        import winreg
    except ImportError:
        return None
    alvo = _chave(f"{familia} {estilo}" if estilo and estilo.lower() != "regular" else familia)
    dirs = pastas()
    for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            ch = winreg.OpenKey(raiz, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except OSError:
            continue
        with ch:
            for i in range(winreg.QueryInfoKey(ch)[1]):
                nome, valor, _ = winreg.EnumValue(ch, i)
                # "DejaVu Sans Bold (TrueType)" -> "dejavusansbold"
                if _chave(re.sub(r"\(.*?\)", "", nome)) != alvo:
                    continue
                for cand in [valor] + [os.path.join(d, valor) for d in dirs]:
                    if os.path.isabs(cand) and os.path.exists(cand):
                        return cand
    return None


def _por_nome(familia, estilo):
    """Arquivo cujo nome é a família mais o estilo (DejaVuSans-Bold.ttf), em qualquer pasta de fontes."""
    alvo = _chave(familia + (estilo if estilo and estilo.lower() != "regular" else ""))
    for d in pastas():
        for raiz, _, arqs in os.walk(d):
            for a in sorted(arqs):
                base, ext = os.path.splitext(a)
                if ext.lower() in (".ttf", ".otf", ".ttc") and _chave(base) == alvo:
                    return os.path.join(raiz, a)
    return None


def localizar(familia: str = "DejaVu Sans", estilo: str = "bold"):
    """(arquivo, exata). `exata` é False quando o que se achou foi a substituta do fontconfig, não a família pedida;
    `arquivo` é None quando não há nem isso."""
    arq, exata = _fontconfig(familia, estilo)
    if arq and exata:
        return arq, True
    achado = _registro(familia, estilo) or _por_nome(familia, estilo)
    if achado:
        return achado, True
    return arq, False


def arquivo(familia: str = "DejaVu Sans", estilo: str = "bold"):
    """Caminho do arquivo da fonte pedida, ou None se ela não está instalada."""
    arq, exata = localizar(familia, estilo)
    return arq if exata else None


if __name__ == "__main__":
    a = arquivo(*(sys.argv[1:3] or ["DejaVu Sans", "bold"]))
    if not a:
        sys.exit(1)
    print(a)
