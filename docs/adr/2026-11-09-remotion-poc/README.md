# Prova de conceito do Remotion (ADR-16)

Projeto mínimo usado em 09/11/2026 para medir o Remotion contra o que o plugin já faz. Não é parte do plugin:
não entra no CI, não é instalado pelo `doctor.sh`. Fica aqui para a avaliação ser repetível.

```bash
npm install                      # ~40 s, 518 MB em node_modules (Remotion 4.0.542, React 19)
npx remotion browser ensure      # baixa o Chrome Headless Shell 158.0.8127.2 (~9 s nesta rede)
npm run render                   # Demo: título com spring, wipe, lower third, legenda por palavra (public/trecho.srt)
# Burn precisa de public/seg.mp4 (60 s de filmagem 1080p30) e public/seg.srt (um cue por palavra, tempos do trecho)
npm run burn
```

`public/trecho.srt` tem as 41 primeiras palavras da narração do curso de bateria (tempos do edge-tts), um cue por palavra.

## Medições (Intel 8 threads, 30 GB, sem GPU; concorrência padrão 4x)

| O quê | Resultado |
|---|---|
| `Demo` 17,6 s (530 quadros, 1080p30) | 32 s incluindo o bundle (~6 s): ~17 quadros/s |
| `Demo` 33,6 s (1007 quadros) renderizado duas vezes | 49–67 s; **md5 idêntico** nos dois mp4 (determinístico) |
| `Demo` como sequência PNG (1007 quadros) | 110 s |
| `Burn`: legenda por palavra sobre 60 s de filmagem | **318 s** (Remotion, `OffthreadVideo`) contra **17,6 s** do `ffmpeg -vf subtitles=` com o mesmo SRT e `libx264 veryfast crf 18` |

`prova.png`: seis quadros do `Demo` (0,6 s a 13,5 s).

## Pegadinhas encontradas
- `createTikTokStyleCaptions()` separa palavras pelo **espaço inicial** do `text` de cada `Caption`. `parseSrt()` de um SRT por palavra devolve textos sem esse espaço e tudo vira uma página só, sem quebra. Corrigir ao carregar (ver `Root.tsx`).
- Os pacotes `@remotion/*` e `remotion` têm de estar na **mesma versão exata** (o próprio `npx remotion versions` confere).
- `--frames=a-b` fora da duração calculada por `calculateMetadata` aborta o render.
