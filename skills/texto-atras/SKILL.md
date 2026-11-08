---
name: texto-atras
description: Efeito "texto atrás da pessoa" — o texto aparece entre o fundo e a pessoa, que fica na frente. Usa segmentação local (rembg, MIT). Use para /texto-atras, "texto atrás de mim", "text behind subject".
---

# /texto-atras — texto entre o fundo e a pessoa

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/text_behind.py`.

## Passos
1. Levante: texto (curto, 1–3 palavras funciona melhor), intervalo (`--start`/`--end`, ideal 1–4s), fonte, cor, altura (`--y`, 0.35 = acima da cabeça/ombros).
2. Verifique dependências: `python3 -c "import rembg, PIL"`; senão `pip install "rembg[cpu]" pillow` (com GPU NVIDIA: `rembg[gpu]`).
3. Rode:
   ```bash
   uv run --with "rembg[cpu]" --with pillow python "${CLAUDE_PLUGIN_ROOT}/scripts/text_behind.py" IN.mp4 IN_texto_atras.mp4 --text "TEXTO" \
     --start 0 --end 3 --font /caminho/Montserrat-Black.ttf --size 0.22 --color "#FFFFFF" --y 0.35
   ```
4. Avise do tempo: CPU processa ~2–6 frames/s (3s a 30fps ≈ 15–45s). Na primeira execução o rembg baixa o modelo (~170 MB).
5. Gere `/prova` do trecho e mostre ao usuário. Se a borda da pessoa "tremer", sugira trecho com fundo mais limpo ou a variante abaixo.

## Qualidade
- Rascunho: padrão `--model u2net_human_seg`.
- Final: `--model birefnet-portrait` (BiRefNet, MIT) — recorte de cabelo e bordas muito melhor; use com GPU (`rembg[gpu]`) ou em trechos curtos.

## Variante de qualidade máxima (GPU)
Para recortes mais estáveis em cabelo e movimento rápido, use SAM 2 (Apache 2.0) ou RobustVideoMatting para gerar a máscara, e reaproveite a mesma composição (fundo → texto → pessoa).
