---
name: prova
description: Gera material de aprovação de um vídeo — folha de contato de frames, preview leve, info técnica e loudness — e faz o QA visual antes de entregar. Use para /prova, "me mostra como ficou", "revisa o vídeo", "QA", "folha de contato".
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
   - loudness integrado perto de -14 LUFS (redes) ou -16 (docs).
5. Entregue ao usuário: o `.proof.jpg`, o `.preview.mp4` e uma lista curta de problemas encontrados, com o comando que corrige cada um.

## Regras
- Nenhum vídeo é "pronto" sem passar pela `/prova`.
- Na entrega, `.srt` em pasta separada do `.mp4`: o VLC carrega o sidecar e a legenda aparece dobrada.
