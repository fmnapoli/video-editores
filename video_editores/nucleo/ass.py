"""ASS/libass para os scripts que desenham sobre o vídeo: tempo, cor, cabeçalho, formas vetoriais e queima.
Texto e forma na tela são sempre ASS (nunca `drawtext`, que o ffmpeg estático não tem)."""
import os
import subprocess

from .ffmpeg import codec_video


def tempo(s: float) -> str:
    cs = max(0, int(round(s * 100)))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{sec:02}.{cs:02}"


def cor(hexrgb: str, alpha: int = 0) -> str:
    """#RRGGBB -> &HAABBGGRR& (alpha 0 = opaco, 255 = invisível)."""
    x = hexrgb.lstrip("#")
    return f"&H{alpha:02X}{x[4:6]}{x[2:4]}{x[0:2]}&".upper()


def ffesc(p: str) -> str:
    """Escapa um caminho para ser o valor de uma opção de filtro do ffmpeg, SEM aspas em volta. São dois níveis:
    o da opção (\\ : ') e o do grafo de filtros (\\ ' , ; [ ]). Dentro de aspas simples o ffmpeg não aceita
    apóstrofo escapado, então caminho com apóstrofo só funciona assim.
    No Windows o caminho sai com barra normal (`C:/Users/...`): o ffmpeg aceita, e a barra invertida de
    `C:\\Users` teria de atravessar os dois níveis de escape."""
    s = str(p)
    if os.name == "nt":
        s = s.replace("\\", "/")
    for ch in ("\\", ":", "'"):                       # nível 1: valor da opção
        s = s.replace(ch, "\\" + ch)
    for ch in ("\\", "'", ",", ";", "[", "]"):         # nível 2: descrição do grafo
        s = s.replace(ch, "\\" + ch)
    return s


def texto(s: str) -> str:
    """Texto do usuário dentro de um evento: chaves não abrem bloco de tags, quebra de linha vira \\N.
    O `\\N` digitado de propósito continua valendo."""
    return str(s).replace("{", "\\{").replace("}", "\\}").replace("\r", "").replace("\n", "\\N")


def retangulo(x0, y0, x1, y1) -> str:
    """Desenho vetorial (\\p1) de um retângulo cheio, em pixels do PlayRes."""
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    return f"m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1}"


def moldura(x0, y0, x1, y1, e) -> str:
    """Contorno de retângulo com espessura `e` (retângulo externo menos o interno, regra par-ímpar do libass)."""
    x0, y0, x1, y1, e = (int(round(v)) for v in (x0, y0, x1, y1, e))
    return (f"m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1} l {x0} {y0} "
            f"m {x0 + e} {y0 + e} l {x0 + e} {y1 - e} l {x1 - e} {y1 - e} l {x1 - e} {y0 + e} l {x0 + e} {y0 + e}")


def documento(w: int, h: int, fonte: str, eventos: list, estilos: "list | None" = None) -> str:
    """Arquivo ASS completo. `eventos`: linhas `Dialogue: ...` prontas. Estilo `Base` sempre presente."""
    base = f"Style: Base,{fonte},48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,5,10,10,10,1"
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{chr(10).join([base] + list(estilos or []))}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(eventos) + "\n"


def queimar(video, arq_ass, saida, fontsdir: str = ""):
    """Queima o ASS no vídeo, mantendo o áudio. `fontsdir` é o sufixo devolvido por marca_cli.fontsdir()."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-vf", f"ass=filename={ffesc(arq_ass)}{fontsdir}", *codec_video(crf=20),
                    "-c:a", "copy", "-movflags", "+faststart", str(saida)], check=True)
