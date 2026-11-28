---
name: cena-web
description: Cena de vídeo escrita em HTML — 3D com Three.js (câmera, luz, sombra), layout e tipografia em CSS, linha do tempo com GSAP — renderizada quadro a quadro num Chrome sem janela e juntada no ffmpeg, com fundo opaco ou transparente. Use para /cena-web, "faz uma cena 3D com as letras", "abertura em 3D", "cartela com layout de página", "anima isso com Three.js", "cena em HTML", "GSAP", "motion com CSS".
---

# /cena-web — cena em HTML (Three.js, CSS, GSAP) renderizada quadro a quadro

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh`.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py`. Modelos: `${CLAUDE_PLUGIN_ROOT}/skills/cena-web/templates/` (tabela em "Modelos").

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
3. **Gate de quadros-chave.** Antes do render inteiro, gere a folha e **olhe** (Read): enquadramento, contraste, o instante mais cheio da cena. Escolha instantes em que a cena está parada (depois de cada entrada), ou passe um inteiro para N instantes espalhados.
   ```bash
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/abertura.html --quadros 1.5,3.5,5.2 trabalho/<slug>/cenas/abertura.folha.png
   ```
   O script confere o texto da página em cada instante: `PROBLEMA: ... texto cortado pela borda` e código de saída 2 significam cena a corrigir, não a ignorar. Cena que leva legenda por cima: `--reserva-baixo 0.21` acusa texto na faixa da legenda. O que sangra de propósito ganha `data-ve-sangra` no elemento. Texto desenhado em `<canvas>` (textura do Three.js) não é visto pela conferência: aí só a folha mostra. Para olhar um instante em tamanho cheio: `--quadro T SAIDA.png`.
4. Renderize (~5 quadros por segundo em 1080p: 6 s de cena levam ~35 s; rode em segundo plano se passar de 20 s de cena):
   ```bash
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/abertura.html trabalho/<slug>/abertura.mp4
   # camada transparente para sobrepor: fundo da página transparente e, em WebGL, `alpha: true` (FUNDO = null no modelo)
   uv run --with playwright python "${CLAUDE_PLUGIN_ROOT}/scripts/cena_web.py" trabalho/<slug>/cenas/selo.html trabalho/<slug>/selo.mov --alpha
   ```
5. Para **trocar um trecho** de um vídeo pronto pelo bloco (um separador, uma cartela), corte por tempo em três partes, junte com o demuxer `concat` e confira a emenda extraindo quadros com `-ss` antes e depois: contagem de quadros e `-itsoffset` erram em vídeo montado por blocos (ver solução de problemas). Olhe a emenda **quadro a quadro** (dois quadros de cada lado): o corte original pode ser um dissolve de 2 ou 3 quadros, e o bloco novo precisa cobri-lo, senão sobra um resto do desenho antigo por um décimo de segundo. Lembre que `-ss T` entrega o primeiro quadro com tempo ≥ T: para o quadro `n`, use `T = n/fps − 0,01`. Se o trecho tinha a pessoa num círculo ou janela, recorte essa região do original com uma máscara (`crop` + `alphamerge`) e sobreponha na cena nova; faça isso em **duas etapas** (corte o trecho sem perda, depois componha sem `-ss`), porque compor na mesma chamada do salto no tempo atrasa as camadas fixas nos primeiros quadros.
6. Use o bloco: como cena pronta do `/video-animado` (`"video": "abertura.mp4"`), bloco do `/videoaula`, ou sobreposto com `overlay` (o `.mov` com alpha, como no `/animacao`). Bloco sem som: o áudio da cena vem da narração ou de um efeito do `/efeitos`.
7. `/prova` no resultado.

## Modelos
Copie o mais próximo e ajuste, ou use direto: os narrados leem o conteúdo de `veDados.dados` (o campo `"dados"` da cena no `/video-animado`, ou `--dados`), então muita cena sai sem editar HTML. Todos abrem soltos com valores de exemplo, funcionam em 16:9 e 9:16, usam as cores e a fonte da marca e deixam livres os 21% de baixo.
| Modelo | Para | `dados` |
|---|---|---|
| `cena-narrada.html` | título + três cartões que entram na palavra | editar no HTML (`data-quando`) |
| `cena-numero.html` | número grande que conta até o valor quando é falado | `numero`, `prefixo`, `sufixo`, `decimais`, `de`, `rotulo`, `quando` |
| `cena-comparacao.html` | antes e depois, A contra B | `lados[]`: `rotulo`, `quando`, `itens[]` (texto ou `{texto, quando}`) |
| `cena-linha-tempo.html` | linha do tempo ou etapas (3 a 5 marcos) | `marcos[]`: `rotulo`, `texto`, `quando` |
| `cena-citacao.html` | citação ou frase de impacto; cada palavra acende quando é falada | `texto`, `autor`, `destaque`, `quando` (trecho da fala) |
| `cena-barras.html` | barras horizontais (2 a 6); cada uma cresce e o valor conta quando é falada | `barras[]`: `rotulo`, `valor`, `quando`, `destaque`; `sufixo`, `prefixo`, `decimais`, `maximo` |
| `cena-abertura.html` | abertura, separador de capítulo e encerramento, com o logo da marca | `capitulo`, `subtitulo`, `quando`, `logo`, `fica` (não desvanece: última cena) |
| `cena-three.html` | letreiro 3D com câmera, luz e sombra (Three.js) | editar no HTML |
| `cena-gsap.html` | cartela em CSS com linha do tempo GSAP | editar no HTML |

Exemplo no spec do `/video-animado` (o caminho do modelo pode ser o do plugin; copie para `cenas/` quando for mexer no desenho):
```json
{"id": "B3", "html": "cenas/cena-numero.html", "titulo": "Acessos pelo celular",
 "narracao": "Hoje, setenta e três por cento dos acessos vêm do celular.",
 "dados": {"numero": 73, "sufixo": "%", "rotulo": "dos acessos vêm do celular", "quando": "setenta"}}
```
`quando` é sempre uma palavra **da narração** (o número é falado por extenso: "setenta", não "73"). Todo `quando` aceita `n` (ocorrência) e `padrao` (instante na prévia sem narração). Texto longo demais para o modelo aparece na folha de quadros-chave como texto cortado: encurte ou divida em duas cenas.

## Sincronia com a narração
Cena que acompanha uma fala não fixa segundos: recebe o mapa de palavras e pergunta. Dentro do `/video-animado` isso é automático (cena com `"html"` no spec, `render_web.py`); solta, passe `--palavras ARQ.json` (`[{"t", "d", "w"}]`, no tempo da cena).
```js
const tBlender = veQuando("Blender");            // início da 1ª vez que a palavra é dita
const tDeNovo  = veQuando("Blender", 2);         // 2ª ocorrência
const { ini, fim } = veTrecho("na ordem certa"); // expressão: do início da primeira ao fim da última palavra
const tPrevia  = veQuando("Blender", 1, 2.0);    // 3º argumento: instante usado quando a cena abre sem narração
```
Maiúsculas, acentos e pontuação não importam. Palavra que não está na fala **interrompe o render** e a mensagem traz a fala inteira: o roteiro mudou, a cena acompanha. `window.veDados` traz o JSON de `--dados` (no `/video-animado`: `{id, titulo, narracao, total, fala: {ini, fim}, dados}`). Modelos: `cena-narrada.html` e os outros narrados da tabela acima.

## Marca
Havendo `marca/marca.json`, a página recebe as variáveis CSS `--ve-fundo`, `--ve-fundo2`, `--ve-acento`, `--ve-secundario`, `--ve-texto`, `--ve-texto2` e `--ve-fonte`, os TTF da marca registrados com o nome da família, e `window.veMarca` (`{nome, cores, fonte, logo}`; `logo.png`/`logo.svg` são URLs prontas para `<img>`). Escreva sempre com reserva, `color: var(--ve-acento, #FFD43B)`: sem marca, vale o valor depois da vírgula. Em `<canvas>`, leia de `veMarca.cores`. `--sem-marca` desliga.

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
| `--quadros` | — | `T1,T2,...` ou um inteiro N: folha de quadros-chave em `SAIDA.png`, com conferência do texto |
| `--reserva-baixo` | 0 | com `--quadros`: fração de baixo onde texto é problema (0,21 = legenda de 2 linhas) |
| `--auditoria` | `erro` | `aviso` não derruba o comando; `nao` desliga a conferência |
| `--palavras` / `--dados` | — | mapa de palavras da narração e JSON livre para a cena |
| `--marcas ARQ.json` | — | grava o que a cena consultou ao carregar (`veQuando`/`veTrecho`): termo, ocorrência, início e fim |

## Regras
- Texto em 3D: desenhe num `<canvas>` e use como textura (o modelo faz isso), com fonte do sistema ou da marca. Não baixe fonte em tempo de render.
- Texto que precisa ser lido fica parado pelo menos 1,5 s e fora dos 15% de cima e de baixo em vertical.
- WebGL roda por software no Chrome sem janela: evite pós-processamento pesado e milhares de objetos; sombra em mapa de 2048 é o teto razoável.
- Aviso `recurso não entregue` no fim do render é erro de cena (arquivo faltando ou CDN): corrija, não ignore.
- Nenhuma cena vai para o render inteiro sem a folha de quadros-chave olhada. Defeito que apareceu numa cena vira regra no modelo do projeto (`trabalho/<slug>/cenas/`), para a próxima já nascer sem ele.
- Entrada marcada por palavra (`veQuando`), nunca por segundo copiado do `tempos.json`: o texto muda no gate e os tempos se ajustam sozinhos.
- Nunca passe filmagem por aqui: legenda e lettering sobre vídeo gravado são ASS no ffmpeg (ADR-16 mediu 18× mais lento pelo navegador).
