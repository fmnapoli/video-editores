"""Áudio determinístico: medição de loudness, normalização a um alvo LUFS com teto de pico real,
fades de bloco e duração alinhada ao quadro.

Por que não `loudnorm` sozinho: em modo linear ele aplica um ganho e confia na medição da primeira
passada; com degraus nas junções entre blocos a saída de um curso de 19 min foi a +9 dBTP. Em modo
dinâmico ele mexe na dinâmica da fala. Aqui o ganho é estático até o alvo integrado e um `alimiter`
com oversampling (192 kHz) segura o pico real; o resultado é medido e, se passar do limite, o teto
desce; se o loudness saiu do alvo (o limiter comeu energia), o ganho é corrigido; até 4 passadas. As
junções recebem fades curtos (`fades`) para não gerar o degrau que vira pico.
"""
import json
import os
import subprocess
import tempfile

TAXA = 48000

# Codificação AAC para entrega. O codificador nativo do ffmpeg, com PNS (substituição perceptual de ruído) ligado,
# gerou +4,7 dBTP a partir de um wav limitado a -2,5 dBTP (bateria sintetizada com bandas de ruído): o ruído
# sintético que ele injeta não respeita o pico do original. Sem PNS e a 256k a diferença cai para ~0,1 dB.
AAC = ["-c:a", "aac", "-b:a", "256k", "-aac_pns", "0"]


def _ffmpeg(args, capturar=False):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falhou: " + " ".join(args) + "\n" + r.stderr[-2000:])
    return r.stderr if capturar else None


def medir(path, filtro=None) -> dict:
    """Loudness integrado (LUFS), pico real (dBTP), LRA e threshold do áudio de `path` (wav ou vídeo).
    `filtro` é uma cadeia ffmpeg aplicada antes da medição (ex.: passa-alta + afftdn)."""
    af = (f"{filtro}," if filtro else "") + "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json"
    err = _ffmpeg(["-i", str(path), "-vn", "-af", af, "-f", "null", "-"], capturar=True)
    j = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    return {"I": float(j["input_i"]), "TP": float(j["input_tp"]), "LRA": float(j["input_lra"]),
            "thresh": float(j["input_thresh"])}


def fades(d, entrada=0.012, saida=0.018) -> str:
    """Fade de entrada e de saída curtos para um bloco de `d` segundos (evita o clique e o pico na junção)."""
    return f"afade=t=in:st=0:d={entrada},afade=t=out:st={max(0.0, d - saida):.4f}:d={saida}"


def quadros(d, fps=30) -> float:
    """Duração arredondada ao grid de quadros (vídeo e áudio do bloco com a mesma conta)."""
    return round(d * fps) / fps


_LATENCIA = None


def _alimiter_latencia() -> str:
    """`latency=1` compensa o atraso do lookahead (senão o áudio sai 5 ms atrasado e o teto é ultrapassado em ~0,7 dB);
    a opção não existe em ffmpeg antigo, então é sondada uma vez."""
    global _LATENCIA
    if _LATENCIA is None:
        h = subprocess.run(["ffmpeg", "-hide_banner", "-h", "filter=alimiter"], capture_output=True, text=True).stdout
        _LATENCIA = ":latency=1" if "latency" in h else ""
    return _LATENCIA


def cadeia(ganho_db, teto_db, taxa=TAXA) -> str:
    """Filtro: estéreo, ganho estático, limiter de pico real com oversampling e volta à taxa de saída.
    O estéreo vem antes do ganho: mono vira L+R a -3 dB por canal (matriz do ffmpeg), e assim o teto que
    o limiter aplica é o mesmo que a medição final enxerga."""
    lim = 10 ** (teto_db / 20)
    return (f"aformat=channel_layouts=stereo,volume={ganho_db:.2f}dB,aresample=192000,"
            f"alimiter=limit={lim:.4f}:attack=5:release=100:level=false{_alimiter_latencia()},aresample={taxa}")


def normalizar(entrada, saida, alvo=-14.0, tp=-1.5, filtro=None, margem=1.0, tentativas=4, taxa=TAXA) -> dict:
    """Grava `saida` (wav estéreo a `taxa`) com o áudio de `entrada` a `alvo` LUFS e pico real <= `tp` dBTP.
    Cada passada é medida: pico acima do limite baixa o teto; loudness fora de ±0,5 LU (o limiter comeu energia,
    ou o material tem transientes fortes) corrige o ganho. Devolve {"entrada", "saida", "ganho_db", "teto_db", "passadas"}."""
    m = medir(entrada, filtro)
    ganho = alvo - m["I"]
    teto = tp - margem
    r, passadas = None, 0
    for i in range(tentativas):
        af = (f"{filtro}," if filtro else "") + cadeia(ganho, teto, taxa)
        _ffmpeg(["-i", str(entrada), "-vn", "-af", af, "-ar", str(taxa), "-c:a", "pcm_s16le", str(saida)])
        r = medir(saida)
        passadas = i + 1
        if r["TP"] > tp + 0.2:
            teto -= (r["TP"] - tp) + 0.2
        elif abs(r["I"] - alvo) > 0.5 and i + 1 < tentativas:
            ganho += alvo - r["I"]
        else:
            break
    return {"entrada": m, "saida": r, "ganho_db": round(ganho, 2), "teto_db": round(teto, 2), "passadas": passadas}


def normalizar_video(entrada, saida, alvo=-14.0, tp=-1.5, filtro=None, args_video=("-c:v", "copy")) -> dict:
    """Normaliza o áudio de um vídeo e remuxa (vídeo copiado por padrão, áudio `AAC`). O dict devolvido tem em
    "saida" a medição do arquivo final (depois do AAC, que é o que o espectador ouve) e em "wav" a do wav limitado."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "norm.wav")
        res = normalizar(entrada, wav, alvo, tp, filtro)
        _ffmpeg(["-i", str(entrada), "-i", wav, "-map", "0:v:0", "-map", "1:a:0", *args_video, *AAC,
                 "-movflags", "+faststart", str(saida)])
    res["wav"] = res["saida"]
    res["saida"] = medir(saida)
    return res


def resumo(res) -> str:
    e, s = res["entrada"], res["saida"]
    extra = f", wav {res['wav']['TP']:.1f} dBTP antes do AAC" if "wav" in res else ""
    return (f"áudio: {e['I']:.1f} LUFS / {e['TP']:.1f} dBTP -> {s['I']:.1f} LUFS / {s['TP']:.1f} dBTP "
            f"(ganho {res['ganho_db']:+.1f} dB, teto {res['teto_db']:.1f} dBTP, {res['passadas']} passada(s){extra})")
