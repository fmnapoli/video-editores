---
name: referencia
description: Analisa um vídeo de referência (link ou arquivo) e extrai o "DNA" da edição — ritmo de cortes, duração dos planos, estilo de legenda, gancho, uso de música — para replicar no vídeo do usuário. Use para /referencia, "edita igual esse vídeo", "analisa esse reels".
---

# /referencia — engenharia reversa de edição

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.


## Passos
1. Obtenha o vídeo:
   - Link: `yt-dlp -f "bv*[height<=1080]+ba/b" -o "ref.%(ext)s" "URL"` (só para análise pessoal; respeite os termos da plataforma).
   - Arquivo: use direto.
2. Detecte cortes (PySceneDetect, BSD):
   ```bash
   scenedetect -i ref.mp4 detect-adaptive list-scenes -f ref_cenas.csv save-images -n 1 -o ref_frames
   ```
3. Transcreva para ler o roteiro e o gancho: `uv run --with faster-whisper python "${CLAUDE_PLUGIN_ROOT}/scripts/transcribe.py" ref.mp4`.
4. Gere `ref_contato.jpg` com `bash "${CLAUDE_PLUGIN_ROOT}/scripts/proof.sh" ref.mp4 16` e **olhe a imagem** (Read) para identificar estilo de legenda, enquadramento, cores, b-roll e texto na tela.
5. Entregue um **guia de edição** curto em markdown (`referencia.md`):
   - duração total, nº de cortes, duração média/mín/máx de plano, cortes por segundo nos primeiros 3s vs. resto;
   - gancho (texto dos 3 primeiros segundos) e estrutura (gancho → desenvolvimento → CTA);
   - estilo de legenda (palavras por bloco, posição, cor, animação);
   - música/efeitos (presença, momentos de drop);
   - lista de **parâmetros para aplicar**: margem do `/corte`, estilo do `/legenda`, sugestões de `/ganchos` e `/efeitos`.
6. Pergunte se deve aplicar o guia no vídeo do usuário.
