"""Quadros de vídeo como numpy, lidos do ffmpeg por pipe (sem arquivos temporários, sem OpenCV para decodificar).

A rotação de celular já vem aplicada (o ffmpeg auto-rotaciona). Com `largura`, o quadro é reduzido mantendo a
proporção, com altura par: detecção e rastreamento não precisam da resolução cheia, e as posições saem em
fração do quadro (0–1), que vale para qualquer resolução.
"""
import subprocess

from .ffmpeg import fps as _fps
from .ffmpeg import probe_dimensoes


def tamanho(path, largura=None):
    """(w, h) dos quadros que `ler` vai entregar."""
    w, h = probe_dimensoes(path)
    if largura and largura < w:
        h = max(2, int(round(h * largura / w / 2)) * 2)
        w = int(largura) - int(largura) % 2
    return w, h


def ler(path, largura=None, passo=None, inicio=0.0, fim=None, cinza=False):
    """Gera (indice, t, quadro). Sem `passo`, todos os quadros; com `passo` (segundos), uma amostra a cada passo.
    `t` é o instante real do quadro no vídeo (taxa de quadros constante): o primeiro quadro entregue é o primeiro
    com tempo >= `inicio`, e a amostra k é o quadro mais próximo de k × passo depois dele. A amostragem escolhe o
    quadro pelo TEMPO dele (filtro `select` sobre `t`, sem estado), e não:
      - pelo filtro `fps`, que arredonda o tempo e desloca o rótulo em até meio passo;
      - pelo número do quadro (`n`), que o ffmpeg zera quando o vídeo muda de parâmetros no meio (entrega montada
        por blocos com cor ou SPS diferentes): depois da emenda, toda contagem por quadro aponta o quadro errado.
    Quadro: uint8 HxWx3 (BGR) ou HxW (cinza)."""
    import math

    import numpy as np
    w, h = tamanho(path, largura)
    taxa = _fps(path)
    inicio = max(0.0, inicio)
    # Tolerância de 2 ms no início: em entrega montada por blocos os tempos podem ficar uma fração de milissegundo
    # antes da grade (673,0993 em vez de 673,1) e um -ss no instante exato pularia justamente o quadro pedido.
    folga = 0.002 if inicio > 0 else 0.0
    n0 = math.ceil((inicio - folga) * taxa - 1e-6)       # índice do primeiro quadro entregue
    busca = inicio - folga
    p_q = max(1.0, passo * taxa) if passo else 1.0       # passo em quadros
    vf = []
    if passo:
        # u = tempo desde o primeiro quadro entregue; entra o quadro em que floor((u + meio quadro) / passo) avança
        # (o 1% de quadro a mais decide o empate quando k × passo cai exatamente entre dois quadros)
        d, o = 1.0 / taxa, n0 / taxa - busca
        u = f"(t-{o - 0.01 / taxa:.6f})"
        vf.append(f"select=gt(floor(({u}+{d / 2:.6f})/{p_q * d:.6f})\\,floor(({u}-{d / 2:.6f})/{p_q * d:.6f}))")
    vf.append(f"scale={w}:{h}")
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{busca:.6f}"]
    if fim is not None:
        cmd += ["-to", f"{fim:.6f}"]
    cmd += ["-i", str(path), "-an", "-sn", "-vf", ",".join(vf), "-fps_mode", "passthrough", "-f", "rawvideo",
            "-pix_fmt", "gray" if cinza else "bgr24", "-"]
    n = w * h * (1 if cinza else 3)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        i = 0
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            q = np.frombuffer(buf, dtype=np.uint8)
            quadro = n0 + (math.ceil(i * p_q - 0.51) if passo else i)
            yield i, quadro / taxa, (q.reshape(h, w) if cinza else q.reshape(h, w, 3))
            i += 1
    finally:
        if p.poll() is None:   # quem consome parou antes do fim: encerra sem o ffmpeg reclamar de pipe fechado
            p.kill()
        p.stdout.close()
        p.wait()


def em(path, t, largura=None, cinza=False):
    """Um quadro no instante t (None se t passar do fim)."""
    for _, _, q in ler(path, largura=largura, inicio=t, fim=t + 1.0, cinza=cinza):
        return q.copy()
    return None
