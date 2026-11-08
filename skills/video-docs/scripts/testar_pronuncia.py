#!/usr/bin/env python3
"""Ouvir e ajustar a pronúncia antes de montar.

  uv run --with edge-tts python testar_pronuncia.py "Faça o deploy no cluster."
      -> mostra o texto falado e grava pronuncia-cru.mp3 (sem glossário) e
         pronuncia-glossario.mp3 (com glossário), para comparar de ouvido.

  uv run --with edge-tts python testar_pronuncia.py --glossario [--secao nao_validados]
      -> grava pronuncia-glossario.mp3 lendo cada termo numa frase-moldura, na ordem do
         arquivo, e imprime a lista com os tempos (para achar o termo no áudio).

Opções: --voz <nome> (padrão pt-BR-ThalitaMultilingualNeural; o glossário padrão só entra com voz
        não multilíngue, ex.: --voz pt-BR-FranciscaNeural), --glossary <arquivo.json> (extra, vence o padrão),
        --saida <pasta> (padrão: diretório atual).
"""
import argparse, asyncio, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronuncia  # noqa: E402


async def synth(text, voice, mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, boundary="SentenceBoundary")
    sents = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "SentenceBoundary":
                sents.append((ch["offset"] / 1e7, ch["text"]))
    return sents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("texto", nargs="?")
    ap.add_argument("--glossario", action="store_true")
    ap.add_argument("--secao", choices=["validados", "nao_validados"])
    ap.add_argument("--voz", default="pt-BR-ThalitaMultilingualNeural")
    ap.add_argument("--glossary")
    ap.add_argument("--saida", default=".")
    a = ap.parse_args()
    gloss = pronuncia.load(a.glossary, voice=a.voz)
    if a.glossario and not gloss:
        gloss = pronuncia.load(True)
    os.makedirs(a.saida, exist_ok=True)

    if a.glossario:
        data = json.load(open(pronuncia.DEFAULT, encoding="utf-8"))
        secoes = [a.secao] if a.secao else [k for k in data if not k.startswith("_")]
        termos = [(k, gloss[k]) for s in secoes for k in data[s] if k in gloss]
        frases = [f"{i}. Agora o termo {v}." for i, (k, v) in enumerate(termos, 1)]
        mp3 = os.path.join(a.saida, "pronuncia-glossario.mp3")
        sents = asyncio.run(synth(" ".join(frases), a.voz, mp3))
        for i, (k, v) in enumerate(termos):
            t = sents[i][0] if i < len(sents) else float("nan")
            print(f"{int(t)//60:02d}:{t%60:05.2f}  {i+1:3d}. {k:16s} -> {v}")
        print(f"\n{mp3}")
        return

    if not a.texto:
        ap.error("informe um texto ou --glossario")
    falado = pronuncia.apply(a.texto, gloss)
    print("exibido:", a.texto)
    print("falado: ", falado)
    for nome, txt in (("cru", a.texto), ("glossario", falado)):
        mp3 = os.path.join(a.saida, f"pronuncia-{nome}.mp3")
        asyncio.run(synth(txt, a.voz, mp3))
        print(mp3)


if __name__ == "__main__":
    main()
