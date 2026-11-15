---
name: prova
description: Gera material de aprovação de um vídeo — folha de contato de frames, preview leve, info técnica e loudness — e faz o QA antes de entregar, com conferência automática de texto sobre o rosto e de fala contra o roteiro. Use para /prova, "me mostra como ficou", "revisa o vídeo", "QA", "folha de contato", "confere se o texto cobriu meu rosto", "confere se a narração bate com o roteiro".
---

# /prova — revisão antes de entregar

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/proof.sh` (sem `drawtext`, compatível com ffmpeg estático).

## Passos
1. Gere a prova:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/proof.sh" IN_final.mp4 12
   ```
   Saídas: `.proof.jpg` (grid 4×3), `.preview.mp4` (480p leve, bom para mandar no celular), `.proof.txt` (codec, resolução, fps, instantes de cada quadro do grid, loudness).
2. **Olhe o `.proof.jpg` com Read** e confira:
   - legenda visível e legível, sem cobrir rosto nem lettering;
   - textos e destaques no lugar certo;
   - nenhum dado pessoal, senha, token ou e-mail na tela (regra do `video-docs`);
   - sem frame preto, congelado ou de carregamento.
3. Para um instante específico (ex.: o meio de um lettering), extraia o frame exato:
   ```bash
   ffmpeg -ss 12.4 -i IN_final.mp4 -frames:v 1 -q:v 2 frame_12.4.jpg
   ```
4. Confira o técnico no `.proof.txt`:
   - vertical 1080x1920 para reels/shorts, 1280x720 ou 1920x1080 para docs;
   - h264 + aac;
   - loudness integrado perto de -14 LUFS (redes) ou -16 (docs);
   - pico real ≤ -1,5 dBTP. Acima de -1,0 o `proof.sh` sai com código 3 e grava `PICO ACIMA DO LIMITE` no `.proof.txt`: normalize com `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/normalizar_audio.py" IN.mp4 OUT.mp4 --alvo -14` e rode a prova de novo.
5. **Conferência automática**, quando houver com o que comparar (não substitui o olhar do passo 2: aponta o instante para você olhar):
   - **texto sobre o rosto**: compare a entrada e a saída da etapa que pôs texto (mesma linha do tempo, ex.: `_corte.mp4` e `_lettering.mp4`). Código 3 lista os intervalos em que algo cobriu o rosto.
     ```bash
     uv run --with opencv-python-headless --with numpy python "${CLAUDE_PLUGIN_ROOT}/scripts/rostos.py" IN_corte.mp4 --conferir IN_lettering.mp4
     ```
   - **fala × roteiro** (vídeo com roteiro escrito: `/video-animado`, `/video-docs`, narração por TTS): transcreva o **vídeo final** e compare com o roteiro, palavra por palavra. Código 1 lista o que faltou, sobrou ou trocou, com o instante.
     ```bash
     uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" IN_final.mp4
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/conferir_fala.py" roteiro.md trabalho/IN_final/IN_final.transcript.json --equivalentes eq.json
     ```
     Ouça cada instante apontado antes de corrigir: a transcrição também erra. Número, sigla e nome próprio que ela escreve de outro jeito vão para `eq.json` (`{"5.2": "cinco ponto dois"}`).
6. Entregue ao usuário: o `.proof.jpg`, o `.preview.mp4` e uma lista curta de problemas encontrados, com o comando que corrige cada um.

## Regras
- Nenhum vídeo é "pronto" sem passar pela `/prova`.
- Erro encontrado na conferência volta para a etapa que o causou (refaça o lettering, a cena, o corte) e a prova roda de novo; não se entrega com ressalva o que dá para consertar.
- Na entrega, `.srt` em pasta separada do `.mp4`: o VLC carrega o sidecar e a legenda aparece dobrada.
