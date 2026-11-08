---
name: animacao
description: Cria animações e motion graphics por código (Manim ou ffmpeg) — diagramas animados, contadores, gráficos, tipografia cinética, intros — e sobrepõe ou insere no vídeo. Use para /animacao, "anima esse diagrama", "faz uma intro", "motion graphic".
---

# /animacao — motion graphics por código

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

## Escolha da ferramenta
- **Manim Community (MIT)** — diagramas, fluxos, gráficos, equações, texto animado. Padrão.
- **ffmpeg puro** — zoom/punch-in, ken burns em imagem, transições (`xfade`), contadores simples.

## Manim
1. Escreva `anim.py` com uma `Scene`. Para sobrepor ao vídeo, use fundo transparente.
   ```python
   from manim import *
   class Cena(Scene):
       def construct(self):
           t = Text("TEXTO", weight=BOLD).scale(1.4)
           self.play(Write(t), run_time=0.8)
           self.play(t.animate.scale(1.2).set_color(YELLOW), run_time=0.3)
           self.wait(1)
           self.play(FadeOut(t, shift=UP), run_time=0.4)
   ```
2. Renderize. Vertical 9:16: `-r 1080,1920`. Transparente: `-t` (gera .mov com alpha).
   ```bash
   manim -qh -t -r 1080,1920 --fps 30 anim.py Cena -o anim.mov
   ```
3. Sobreponha no momento certo (T0 em segundos):
   ```bash
   ffmpeg -i IN.mp4 -itsoffset T0 -i media/videos/anim/*/anim.mov \
     -filter_complex "[0:v][1:v]overlay=0:0:eof_action=pass[v]" -map "[v]" -map 0:a -c:a copy IN_anim.mp4
   ```

## ffmpeg — receitas rápidas
- **Punch-in (zoom 1.15x num trecho)**: `-vf "scale=iw*1.15:-2,crop=iw/1.15:ih/1.15"` aplicado só ao trecho (separe com `trim` + `concat`) ou `zoompan` para zoom progressivo.
- **Ken Burns em foto (5s)**: `ffmpeg -loop 1 -i foto.jpg -vf "zoompan=z='min(zoom+0.0015,1.3)':d=150:s=1080x1920:fps=30" -pix_fmt yuv420p -t 5 kb.mp4`
- **Transição entre clipes**: `[0][1]xfade=transition=slideleft:duration=0.3:offset=N`, em que `N` é um número: a duração do primeiro clipe menos 0,3 (calcule com `ffprobe`; `xfade` não aceita expressão).

## Sincronizar com a fala (diagrama que acompanha a narração)
Use a base `"${CLAUDE_PLUGIN_ROOT}/skills/videoaula/templates/base_cenas.py"`: `Trecho` com `T0`/`DUR` (início e duração do trecho no vídeo), `att(t_abs)` espera até o instante absoluto da palavra (do `.transcript.json`, ou do `transcript_corte.txt` se o vídeo foi cortado) e `fim()` desvanece exatamente no fim do trecho. Vários diagramas independentes: escreva um por subagente (mesma base, mesma área segura) e revise só a folha dos últimos quadros; renderize em paralelo com `skills/videoaula/scripts/render_cenas.sh`.

## Regras
- Sempre teste com `-ql` (baixa qualidade) antes do `-qh`.
- Use `/prova` para mostrar frames da animação ao usuário antes de compor.
