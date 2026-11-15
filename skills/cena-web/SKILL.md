---
name: cena-web
description: Cena de vídeo escrita em HTML — 3D com Three.js (câmera, luz, sombra), layout e tipografia em CSS, linha do tempo com GSAP — renderizada quadro a quadro num Chrome sem janela e juntada no ffmpeg, com fundo opaco ou transparente. Use para /cena-web, "faz uma cena 3D com as letras", "abertura em 3D", "cartela com layout de página", "anima isso com Three.js", "cena em HTML", "GSAP", "motion com CSS".
---

# /cena-web — cena em HTML (Three.js, CSS, GSAP) renderizada quadro a quadro

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py`. Modelos: `${CLAUDE_PLUGIN_ROOT}/skills/cena-web/templates/` (`cena-three.html`, `cena-gsap.html`).

## Quando usar (e quando não)
| O pedido | Ferramenta |
|---|---|
| objeto ou letreiro em 3D com câmera que se move, luz e sombra, em segundos | **`/cena-web` com Three.js** |
| cartela com várias linhas, colunas, quebra automática, lista, cartões | **`/cena-web` com CSS** (com ou sem GSAP) |
| diagrama, gráfico, equação, fluxo sincronizado com a narração | `/animacao`, `/video-animado` (Manim): continua o padrão |
| 3D fotorrealista, modelo importado, materiais e iluminação de produto | `/3d` (Blender) |
| texto sobre a filmagem (título, lower third, legenda, destaque) | `/lettering`, `/legenda`, `/ler-tela` (ASS): a filmagem **nunca** passa pelo navegador |

A cena HTML gera um **bloco** (abertura, separador, cartela, objeto 3D com alpha). O que vai por cima de filmagem é composto depois pelo ffmpeg.

## Passos
1. Levante: o que aparece, a duração, o formato (`--tamanho 1920x1080` ou `1080x1920`) e se é bloco inteiro (`.mp4`) ou camada para sobrepor (`.mov` com `--alpha`). Havendo `marca/marca.json`, use as cores e a fonte dela.
2. Copie o modelo mais próximo para `trabalho/<slug>/cenas/<nome>.html` e escreva a cena. **Contrato:**
   ```js
   window.veDuracao = 6;                 // segundos (ou passe --dur)
   window.veQuadro = (t) => { /* desenha o instante t */ };
   ```
   Tudo é função de `t`. Sem `requestAnimationFrame` livre, `setTimeout`, `Date.now()`, `Math.random()` sem semente nem animação CSS solta: é isso que faz dois renders darem o mesmo arquivo. Com GSAP: `const tl = gsap.timeline({ paused: true })` e `veQuadro = (t) => tl.seek(t, false)`.
3. **Gate de quadro.** Antes do render inteiro, tire 2 ou 3 quadros em instantes diferentes e **olhe** (Read): enquadramento, texto cortado, contraste, o instante mais cheio da cena.
   ```bash
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/abertura.html --quadro 3.5 trabalho/<slug>/cenas/abertura_3.5.png
   ```
4. Renderize (~5 quadros por segundo em 1080p: 6 s de cena levam ~35 s; rode em segundo plano se passar de 20 s de cena):
   ```bash
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/abertura.html trabalho/<slug>/abertura.mp4
   # camada transparente para sobrepor: fundo da página transparente e, em WebGL, `alpha: true` (FUNDO = null no modelo)
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/selo.html trabalho/<slug>/selo.mov --alpha
   ```
5. Para **trocar um trecho** de um vídeo pronto pelo bloco (um separador, uma cartela), corte por tempo em três partes, junte com o demuxer `concat` e confira a emenda extraindo quadros com `-ss` antes e depois: contagem de quadros e `-itsoffset` erram em vídeo montado por blocos (ver solução de problemas).
6. Use o bloco: como cena pronta do `/video-animado` (`"video": "abertura.mp4"`), bloco do `/videoaula`, ou sobreposto com `overlay` (o `.mov` com alpha, como no `/animacao`). Bloco sem som: o áudio da cena vem da narração ou de um efeito do `/efeitos`.
7. `/prova` no resultado.

## Bibliotecas
A página importa por nome; o script entrega do cache local (baixa do registro do npm na primeira vez, versão fixada e sha256 conferido; `--libs` mostra). Nada vem de CDN e, por padrão, a página não acessa a internet (`--rede` libera).
```html
<script type="importmap">{"imports": {"three": "/_ve/three/build/three.module.js",
  "three/addons/": "/_ve/three/examples/jsm/", "gsap": "/_ve/gsap/index.js", "gsap/": "/_ve/gsap/"}}</script>
```
| Biblioteca | Licença | Para quê |
|---|---|---|
| Three.js | MIT | 3D: geometria, luz, sombra, câmera |
| GSAP | gratuita, licença própria ("no charge"); **não é open source** e proíbe uso em ferramenta visual de animação sem código que concorra com a dona | linha do tempo, easing, stagger |

Sem GSAP dá para fazer tudo em função de `t` (o `cena-three.html` traz as curvas de easing em três linhas). Imagens, fontes e `.js` ao lado do `.html` são servidos também (`<img src="logo.png">`).

## Parâmetros
| Parâmetro | Padrão | Efeito |
|---|---|---|
| `--dur` | `window.veDuracao` | duração em segundos |
| `--fps` | 30 | quadros por segundo (use o do vídeo em que o bloco entra) |
| `--tamanho` | 1920x1080 | `1080x1920` para vertical |
| `--escala` | 1 | 2 renderiza com o dobro de pixels (texto e borda mais finos; 4× mais lento) |
| `--alpha` | desligado | fundo transparente; pede saída `.mov` (ProRes 4444) |
| `--espera-quadro` | desligado | espera a composição do navegador a cada quadro (filtro CSS pesado, `<video>` na página) |

## Regras
- Texto em 3D: desenhe num `<canvas>` e use como textura (o modelo faz isso), com fonte do sistema ou da marca. Não baixe fonte em tempo de render.
- Texto que precisa ser lido fica parado pelo menos 1,5 s e fora dos 15% de cima e de baixo em vertical.
- WebGL roda por software no Chrome sem janela: evite pós-processamento pesado e milhares de objetos; sombra em mapa de 2048 é o teto razoável.
- Aviso `recurso não entregue` no fim do render é erro de cena (arquivo faltando ou CDN): corrija, não ignore.
- Nunca passe filmagem por aqui: legenda e lettering sobre vídeo gravado são ASS no ffmpeg (ADR-16 mediu 18× mais lento pelo navegador).
