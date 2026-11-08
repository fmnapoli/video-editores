---
name: videoaula
description: Reedita uma videoaula gravada (locutor + quadro branco/Excalidraw + IDE) numa versão profissional com o mesmo locutor e a mesma narração — cenário novo por recorte de IA, diagramas animados no lugar do quadro, abertura, separadores de capítulo, encerramento, código reenquadrado, legenda e áudio normalizado. Use para /videoaula, "refaz essa aula com cenário novo", "troca o Excalidraw por diagramas animados", "deixa a videoaula mais profissional", "telas de introdução e separação entre assuntos", "mantém o professor na tela".
---

# /videoaula — aula gravada → aula redesenhada

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh` (ffmpeg, faster-whisper, auto-editor, scenedetect, Manim, rembg via uv). Scripts desta skill em `${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/`, modelos em `templates/`.

Validado em nov/2026 numa aula de Python de 20 min (3 modos visuais, 9 diagramas, 6 capítulos → 17,5 min).

## O que entra e o que sai
- **Entra**: uma gravação de aula com o professor em tela cheia em alguns trechos e, nos demais, uma webcam circular sobre um quadro (Excalidraw, Miro, slides) ou sobre a IDE.
- **Sai**: `saida/<slug>.mp4` 1920×1080 a −14 LUFS + `legendas/<slug>.srt`, com três layouts que compartilham o mesmo fundo:
  - **L1 locutor**: pessoa recortada por IA sobre o cenário novo, com sombra; lower third na primeira aparição.
  - **L2 diagrama**: chip do capítulo + diagrama Manim sincronizado com a fala + o círculo da webcam (recortado da própria gravação) com anel.
  - **L3 código**: a IDE recortada para o painel útil, ampliada e emoldurada à esquerda; o círculo maior à direita, com chip e call-outs.
  - Cartelas: abertura com checklist dos capítulos entrando conforme a fala, separador por capítulo (2,6 s + whoosh), encerramento com checklist marcado.

## Passos

1. **Avaliação (GATE 1 — design).** Rode o `/referencia` no arquivo (ficha técnica, loudness, silêncios com `auto-editor --export v1`) e mapeie os **modos visuais**:
   ```bash
   scenedetect -i originais/IN.mp4 -fs 3 detect-adaptive list-scenes -f trabalho/<slug>/cenas.csv save-images -n 1 -o trabalho/<slug>/frames
   uv run --with pillow --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/cenas_modo.py" trabalho/<slug>/cenas.csv trabalho/<slug>/frames trabalho/<slug>/cenas.json
   ```
   Olhe uma grade dos frames (Read) e corrija o JSON se a heurística errar. Depois meça o círculo da webcam e os **grupos de layout da IDE** (explorer aberto/fechado, janela menor):
   ```bash
   uv run --with pillow --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/detectar_layout.py" originais/IN.mp4 trabalho/<slug>/cenas.json --saida trabalho/<slug>/layout
   ```
   O círculo sai pronto para o `aula.json`; os grupos de código saem como **rascunho** com uma régua de 100 px por grupo (`layout/regua_*.jpg`): olhe cada régua e ajuste o `crop` (x onde o código começa, sem explorer; y abaixo das abas e acima da barra de status). Cenas curtas herdam o grupo da vizinha. Transcreva com `transcribe.py` (`--prompt` com o vocabulário da aula). Escreva o design (identidade, capítulos, lista de diagramas, cortes de conteúdo) e **pare** para aprovação. Pergunte: nome para o lower third, cortes de erros de gravação, dados pessoais na fala, legenda queimada ou só SRT.
2. **Corte com remap.** Silêncios (margem **0,3 s** em aula) mais os cortes manuais aprovados, um `--cut-out` por trecho:
   ```bash
   CO=(--cut-out 233.98sec,239.44sec --cut-out 937.90sec,951.65sec)
   auto-editor originais/IN.mp4 --edit audio:threshold=0.04 --margin 0.3s "${CO[@]}" --export v1 --output trabalho/<slug>/<slug>_corte.v1.json --no-open
   auto-editor originais/IN.mp4 --edit audio:threshold=0.04 --margin 0.3s "${CO[@]}" --video-codec libx264 --audio-codec aac --output trabalho/<slug>/<slug>_corte.mp4 --no-open
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/remap_tempos.py" <slug>_corte.v1.json cenas.json IN.transcript.json --out trabalho/<slug>
   ```
   Daqui em diante **tudo é no tempo do corte** (`cenas_corte.json`, `transcript_corte.txt` com `[ini-fim] frase`). Não retranscreva: o remap é exato.
3. **`aula.json` + identidade (GATE 2 — visual).** Copie `templates/aula-exemplo.json` para `trabalho/<slug>/aula.json` e preencha: capítulos com o instante (no corte) da frase que abre cada um, diagramas com os trechos de quadro, círculo, grupos de código com `crop`, abertura/encerramento com os instantes das palavras. Gere a identidade e **mockups estáticos** dos três layouts antes de qualquer render longo:
   ```bash
   uv run --with pillow --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/identidade.py" trabalho/<slug>/aula.json
   ```
   Monte os mockups com Pillow (fundo + um frame recortado do locutor + um diagrama + um frame da IDE recortado) e **pare**.
4. **Recorte do locutor (paralelo por processos).** Começa já após o gate 2, em segundo plano, porque é o passo mais longo (CPU: 1–3 s por frame):
   ```bash
   setsid nohup bash "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/matte_workers.sh" trabalho/<slug>/aula.json 2 > trabalho/<slug>/mattes.log 2>&1 &
   ```
   N trabalhadores = min(núcleos/4, RAM livre/1,5 GB). Cada trecho vira `mattes/talk_<ini>.mp4` + `_alpha.mp4` + `.done`; reexecutar só faz o que falta. Lance detached (`setsid nohup`): processos ligados à sessão morrem com ela.
5. **Diagramas e cartelas (paralelo por subagentes).** Copie `templates/base_cenas.py` → `manim/base.py`, `templates/cartelas.py` → `manim/cartelas.py`, e crie `manim/diagramas.py` com uma classe `Trecho` por diagrama. **Despache um subagente por diagrama** (ou por 3 diagramas curtos) com: `base.py`, a área segura (nada com x > 3,4 abaixo de y < −1,3; título via `titulo()`), `T0`/`DUR` do trecho, as linhas do `transcript_corte.txt` daquele trecho com os tempos por palavra, e o pedido de devolver a classe + o render `-ql` + o último quadro. Você faz só a folha de verificação (último quadro de cada cena sobre o fundo com o círculo e o chip) e os ajustes de layout. Depois, render final em paralelo:
   ```bash
   cd trabalho/<slug>/manim && bash "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/render_cenas.sh" diagramas.py qh -j 2 D1Fluxo D2Blocos ...
   bash "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/render_cenas.sh" cartelas.py qh -j 2 Abertura Encerramento Separador:1 Separador:2 ...
   ```
   Som: sintetize o whoosh com ffmpeg (`anoisesrc` + `bandpass` + `afade`) em `sfx/whoosh.wav`; nada de música sob a fala em aula.
6. **Piloto (GATE 3).** Primeiro capítulo completo:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/montar_aula.py" trabalho/<slug>/aula.json edl
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/montar_aula.py" trabalho/<slug>/aula.json render --ate <início do cap. 2> --jobs 2
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/montar_aula.py" trabalho/<slug>/aula.json concat saida/piloto.mp4 --ate <início do cap. 2>
   ```
   `/prova` + grade de quadros nos instantes das trocas de layout; **pare**.
7. **Lote e entrega (GATE 4).** `textos.json` (lower third, call-outs nos trechos de locutor, correções de conteúdo) com tempos finais via `montar_aula.py aula.json map <t_corte>`; `ajustes.json` para as frases cortadas pela metade; então:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/finalizar.sh" trabalho/<slug>/aula.json saida/<slug>.mp4 legendas/<slug>.srt --textos textos.json --ajustes ajustes.json --jobs 2
   ```
   `--limpar-audio` adiciona passa-alta 80 Hz + redução de ruído antes do loudnorm (sala com zumbido). Mostre `.proof.jpg`, `.preview.mp4`, loudness e durações de vídeo e áudio (devem ser iguais).
8. **Publicação.** Capítulos do YouTube nos tempos finais, descrição, hashtags e thumbnail com o recorte do locutor:
   ```bash
   uv run --with pillow --with numpy python "${CLAUDE_PLUGIN_ROOT}/skills/videoaula/scripts/publicar_aula.py" trabalho/<slug>/aula.json --saida saida/<slug> --thumb-t 5.5
   ```
   Entregue `saida/<slug>.mp4`, `legendas/<slug>.srt`, `saida/<slug>.youtube.md`, `saida/<slug>_thumb.jpg`, o relatório de edição e um README do projeto com os comandos de regeneração.

## Paralelismo — onde cabe e onde não
| Trabalho | Como paralelizar | Limite |
|---|---|---|
| Recorte IA dos trechos de locutor | `matte_workers.sh aula.json N` (processos, balanceados por duração); com GPU NVIDIA, `VE_DEVICE=cuda` (troca para `onnxruntime-gpu` sozinho) e `VE_ENCODER=h264_nvenc` | ~1,3 GB RAM e núcleos/N threads por trabalhador |
| Render das cenas Manim | `render_cenas.sh ... -j N` | ~1 GB por render em 1080p |
| Render dos blocos ffmpeg | `montar_aula.py render --jobs N` | núcleos/4 |
| Autoria das cenas Manim, call-outs, revisão de folhas | **subagentes**, um por cena, depois que os tempos existem | consistência: todos recebem a mesma base e área segura |
| Corte → remap → EDL → concat, e os 4 gates | sequencial (dependência de dados e aprovação) | — |

Subagentes não aceleram render: numa máquina saturada só disputam CPU. Lance a computação pesada em segundo plano (detached) logo após o gate que a libera, e use o tempo de espera para a autoria.

## Regras
- O áudio final é **uma trilha contínua** construída do corte com silêncio/whoosh nas cartelas (`montar_aula.py concat`), nunca a soma dos áudios dos blocos: blocos codificados separadamente derivam. As fronteiras dos blocos são alinhadas ao frame.
- Cada diagrama dura exatamente o trecho de quadro que substitui e termina em `fim()`; passos marcados por `att(t_abs)` com o tempo da palavra, nunca "no olho".
- O círculo do locutor vem da gravação original (`circulo` no aula.json); não há webcam separada. Nos trechos de código, o retângulo original da webcam é coberto pela tampa do painel.
- Título do diagrama abaixo do chip; nada na zona do círculo. Confira sempre a folha dos últimos quadros antes do render final.
- Em aula: margem de corte 0,3 s, sem música sob a fala, legenda em SRT separado por padrão, −14 LUFS.
- Correções de conteúdo (fala que contradiz a tela) viram call-out ou corte, decididos pelo autor no gate 1; nunca silenciosamente.
- Dados pessoais na fala ou na tela (ano de nascimento, e-mail): perguntar antes de manter.
