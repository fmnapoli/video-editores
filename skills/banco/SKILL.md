---
name: banco
description: OPCIONAL, fora do padrão do plugin — busca e baixa vídeo de banco de imagens (Pexels, com chave própria e gratuita) para cobrir um trecho sem imagem, com folha de escolha, registro de autor e créditos, e iguala formato e cor ao resto do vídeo. Use para /banco, "põe um B-roll de ondas aqui", "falta imagem nesse trecho", "pega um vídeo de banco", "vídeo de stock".
---

# /banco — B-roll de banco de vídeo (opcional)

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/banco_video.py` (só biblioteca padrão e ffmpeg).

**Antes de usar, diga ao usuário:** este é o único skill de edição que fala com um serviço de terceiros. O plugin é local por princípio; aqui sai da máquina o **termo de busca** (nenhum arquivo do projeto) e entra um vídeo de outra pessoa. Precisa de uma chave do próprio usuário (gratuita em https://www.pexels.com/api/), em `PEXELS_API_KEY`. Sem a chave o script encerra explicando, e nada mais no plugin depende dele. Prefira, nesta ordem: imagem do próprio bruto, `/lettering` ou `/animacao` sobre o trecho, e só então o banco.

## Passos
1. Levante: o trecho a cobrir (início e fim, do `.transcript.json`), o assunto da frase e o formato do vídeo (retrato para Reels, paisagem para YouTube).
2. Busque pelo **assunto concreto** da frase, não pela frase (termos em inglês rendem mais):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banco_video.py" buscar "ocean waves aerial" --id ondas --orientacao paisagem --min-dur 6
   ```
   Gera `banco/ondas.busca.json` e `banco/ondas.folha.jpg` (miniaturas numeradas da esquerda para a direita, de cima para baixo).
3. **Gate:** mostre a folha (Read) com a lista de autor e duração e espere a escolha. Descarte por conta própria o que tiver marca visível, rosto em primeiro plano de pessoa identificável ou texto na imagem.
4. Baixe o escolhido:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banco_video.py" baixar ondas --escolha 3 --altura 1080
   ```
   Gera `banco/ondas.mp4` e `banco/ondas.json` (autor, página, licença, termo, data, sha256).
5. Corte o trecho e iguale ao vídeo: mesmo tamanho e fps, sem o áudio do banco.
   ```bash
   ffmpeg -ss 2 -t 4.5 -i banco/ondas.mp4 -an -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30" \
     -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p trabalho/<slug>/broll_ondas.mp4
   ```
6. **Iguale a cor** para a imagem conversar com o resto. Compare um quadro do B-roll com um do vídeo lado a lado (Read) e ajuste no mesmo filtro: `eq=saturation=0.85:contrast=1.05:gamma=0.97` (banco costuma vir mais saturado que webcam) e `colortemperature=temperature=5200` para aquecer ou esfriar. Mudança pequena: o objetivo é não destoar, não "tratar".
7. Insira por cima do trecho, mantendo a fala. Exemplo com o trecho começando em 12 s e B-roll de 4,5 s:
   ```bash
   ffmpeg -i IN.mp4 -itsoffset 12 -i trabalho/<slug>/broll_ondas.mp4 -filter_complex \
     "[1:v]format=yuva420p,fade=t=in:st=12:d=0.2:alpha=1,fade=t=out:st=16.3:d=0.2:alpha=1[b];[0:v][b]overlay=eof_action=pass[v]" \
     -map "[v]" -map 0:a -c:a copy trabalho/<slug>/<slug>_broll.mp4
   ```
   O `-itsoffset` desloca também o relógio dos fades: a entrada começa em `st` = início do trecho (12) e a saída em início + duração − 0,2 (16,3). Com `st=0` o B-roll fica invisível.
8. Feche com os créditos, que vão para o relatório de edição e para a descrição do vídeo:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/banco_video.py" creditos
   ```

## Parâmetros
| Parâmetro | Padrão | Efeito |
|---|---|---|
| `--orientacao` | qualquer | `paisagem`, `retrato` ou `quadrado` |
| `--min-dur` / `--max-dur` | 4 / 60 s | descarta clipe curto demais para o trecho |
| `--n` | 8 | candidatos na folha |
| `--altura` | 1080 | menor arquivo cujo lado menor tem pelo menos essa medida: 1080 é 1080p, deitado ou em pé (evita baixar 4K sem precisar) |
| `--out` | `banco/` | pasta do projeto com os vídeos e os registros |

## Regras
- Opcional e desligado por padrão: nunca rode sem o usuário ter pedido imagem de fora e sem a chave dele.
- Nunca escolha sozinho: a folha é o gate. Nunca sobrescreva um download (o script recusa).
- Licença: a do Pexels permite uso gratuito, inclusive comercial, sem exigir crédito; **credite mesmo assim** (`creditos`). Não use clipe com pessoa identificável para sugerir endosso, nem com marca de terceiros em destaque. Confira a licença na página do vídeo se o uso for sensível.
- B-roll entra **antes** de `/lettering` e `/legenda` e não mexe no áudio: a fala continua a do bruto.
- O registro `banco/<id>.json` fica no projeto: é a prova de onde veio cada imagem.
