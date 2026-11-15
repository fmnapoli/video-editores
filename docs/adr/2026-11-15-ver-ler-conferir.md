# ADR-19 — Ver, ler e conferir (rosto, rastreamento, OCR, fala) e cena em HTML com Three.js

**Data:** 2026-11-15 · **Estado:** implementado (0.14.0)

## Contexto

Um vídeo público que explica, peça por peça, como um agente edita vídeo serviu de lista de conferência para o plugin.
A maior parte do que ele mostra o plugin já faz: transcrição com o instante de cada palavra, corte por lista de
trechos (EDL), recorte de pessoa e texto atrás dela, animação por código, 3D, ducking, loudness no padrão das
plataformas, folha de contato antes de entregar. Quatro capacidades faltavam, todas do mesmo tipo: o agente
**enxergar o próprio material** em vez de depender só do olho de quem revisa.

| No vídeo | No plugin até a 0.13.0 |
|---|---|
| sabe onde está o rosto em cada quadro; nenhum texto passa na frente dele | "confira na folha de contato se o texto cobre o rosto" (`/prova`, `/lettering`, `/checklist`) |
| acompanha o que se move: a etiqueta gruda no objeto | não havia |
| lê a tela (OCR) e põe o destaque onde o texto está | coordenada medida no olho; tarja de dado sensível à mão |
| transcreve o áudio final e compara com o roteiro, palavra por palavra | só o `.srt` contra o spec (`docs-conferir`), que não ouve o áudio |
| busca vídeo de banco por API quando falta imagem | não havia |
| cena em 3D escrita em HTML (Three.js), layout em CSS, linha do tempo com GSAP, tudo renderizado num navegador sem janela | Manim (2D) e Blender (3D); nenhum caminho para HTML/CSS/WebGL |

O vídeo usa, para isso, uma biblioteca de visão que só existe num sistema operacional, serviços pagos de voz e de
avatar e quatro motores de animação por HTML. A pergunta deste ADR não é "como copiar a pilha dele", e sim: o que
dessas ideias melhora o plugin **dentro** das promessas dele (ADR-01, 05): open source, local, determinístico onde
possível, sem serviço pago no caminho padrão. O critério de licença usado aqui é o do `CONTRIBUTING.md`: o que é
gratuito pode entrar; o que não é open source entra só como opcional, com aviso explícito.

## Decisão

### 1. Dois papéis novos de modelo: `rosto` e `ocr`
Em `video_editores/modelos`, pela mesma regra dos outros (ADR-10): contrato em `base.py`, backend por nome,
`VE_ROSTO`/`VE_OCR`, `deps(device)` alimentando o `uv run --with`.

- **`rosto` → `yunet`**: `FaceDetectorYN` do OpenCV com o modelo YuNet (MIT, 230 KB). O arquivo não vem no pacote do
  OpenCV 5: é baixado uma vez para `~/.cache/video-editores/modelos/`, conferido por sha256 fixo no código, e
  `VE_YUNET_MODELO` aponta um arquivo local em máquina sem rede. As cascatas Haar, que viriam embutidas, saíram do
  pacote na versão 5 e erram mais; não foram usadas.
- **`ocr` → `rapidocr`**: RapidOCR com modelos PP-OCR em ONNX (Apache-2.0), no mesmo `onnxruntime` do recorte de
  pessoa. Só pacote Python, sem binário de sistema nem pacote de idioma, o que o Tesseract exigiria em cada
  plataforma. Lê português com acento e devolve a caixa de cada palavra.

Quem tiver um motor melhor na própria máquina (a biblioteca de visão do sistema, um detector com GPU) registra um
backend por `VE_MODELOS_EXTRA` sem tocar no pacote, como nos outros papéis.

### 2. Rastreamento sem modelo
`rastrear.py` segue os pontos de textura da região com fluxo óptico Lucas-Kanade (ida e volta, para descartar ponto
que escorregou) e ajusta deslocamento + escala + rotação por RANSAC a cada quadro. É OpenCV puro, determinístico,
sem download. Detecta corte de cena e perda do objeto e para ali com código 2, em vez de inventar posição.

Um rastreador por rede neural (VitTrack, Apache-2.0, 700 KB) foi testado no mesmo trecho e **perdeu o objeto em
cerca de 1 s** (a caixa cresceu até o quadro inteiro); o fluxo óptico seguiu o trecho todo. Não entrou.

### 3. Tudo que se desenha continua em ASS
A etiqueta rastreada é um evento ASS por quadro; o destaque e a tarja do OCR são formas vetoriais ASS (`\p1`), com a
varredura do marca-texto por `\clip` animado. Nenhum script novo compõe pixel: quem queima é o libass, como no resto
do plugin. As peças comuns foram para `nucleo/ass.py` e a leitura de quadros por pipe do ffmpeg para
`nucleo/quadros.py`.

### 4. Conferência automática na `/prova`
- `rostos.py ANTES --conferir DEPOIS` compara a entrada e a saída da etapa que pôs texto, só dentro das caixas de
  rosto: pixel que mudou é texto em cima do rosto. Não precisa saber que texto foi nem de onde veio.
- `conferir_fala.py ROTEIRO TRANSCRICAO` alinha as duas sequências de palavras e separa o que faltou, sobrou e
  trocou, com o instante; troca por palavra quase igual é tratada como provável erro do reconhecimento e não conta.

As duas apontam **onde olhar**; não substituem o olhar. A folha de contato continua sendo o gate.

### 5. Banco de vídeo: opcional, fora do padrão
`banco_video.py` e a skill `/banco` existem, mas desligados: sem a chave do próprio usuário o script encerra
explicando, e nada no plugin depende dele. É a única operação de edição que fala com um serviço de terceiros (sai o
termo de busca, entra um vídeo). A escolha é gate (folha de miniaturas) e cada download grava autor, página, licença
e sha256, que viram os créditos. A skill manda tentar antes o próprio bruto, lettering ou animação.

### 6. Cena em HTML com renderizador próprio (`/cena-web`)
`cena_web.py` é um renderizador pequeno (~200 linhas): Playwright (Apache-2.0) dirige o Chrome já instalado, chama
`window.veQuadro(t)` para cada quadro, captura e manda ao ffmpeg. O contrato "a cena é função de `t`" é o que dá
determinismo; a página é servida por interceptação de requisição (sem porta aberta) e não acessa a internet.

- **Three.js (MIT)** é a biblioteca padrão para 3D; **GSAP** entra como opcional para linha do tempo, com o aviso
  de licença na skill e nas convenções (gratuita, "no charge", **não é open source**, revogável, com usos
  proibidos). O modelo com Three.js não depende dela.
- As duas vêm do registro do npm na versão fixada, com sha256 conferido, para `~/.cache/video-editores/web/`
  (23 MB). Não há `node_modules` nem Node no caminho: o ADR-16 mediu 518 MB para o Remotion.
- **Não substitui nada.** Manim continua o padrão para diagrama sincronizado com a fala (`/animacao`,
  `/video-animado`) e o Blender para 3D fotorrealista (`/3d`). A cena HTML cobre o que o ADR-16 reconheceu que
  faltava (layout de texto em CSS) e o 3D rápido de autoria. A regra do ADR-16 fica: **filmagem nunca passa pelo
  navegador**; a cena gera um bloco ou uma camada com alpha, e o ffmpeg compõe.
- Por que não o HyperFrames (Apache-2.0), que faz o mesmo: ele é uma ferramenta de Node (`npx`), e o plugin já
  tem `uv`, ffmpeg e o padrão de script determinístico; o contrato de uma função resolve o mesmo problema sem
  motor de terceiros e sem `node_modules`. O HyperFrames **não foi medido** aqui: a escolha é por encaixe, não
  por comparação de desempenho.

## O que foi medido

CPU de notebook, 8 threads, sem GPU.

| Operação | Material | Tempo | Resultado |
|---|---|---|---|
| `rostos` (localizar, passo 0,5 s) | 30 s, 1280×720, pessoa falando intercalada com gráficos | 1,5 s | rosto em 21 de 60 amostras, nos planos com a pessoa |
| `rostos --conferir` | o mesmo, com um título queimado sobre o rosto de 0,5 a 3,0 s (com fade) | 1,5 s | acusa 1,00–3,00 s (13% da área alterada; a amostra de 0,5 s cai no início do fade, ainda transparente); a simples recodificação em CRF 23 passa limpa |
| `rastrear` | sintético, cartão a 150 px/s sobre ruído, 120 quadros | 1,7 s com a queima | erro máximo 3,2 px em 1280×720 |
| `rastrear` | plano aéreo real, surfista de ~50×90 px sobre água em movimento, câmera aproximando, 102 quadros | 0,9 s | etiqueta no surfista do começo ao fim; confiança mínima 0,77 |
| `ler-tela` | um quadro 1280×720 de tela | 1,4 s (0,7 s de leitura) | 22 palavras; acentos corretos |
| `cena-web` | modelo 3D (6 blocos com textura, luz direcional, sombra 2048, câmera em arco), 6 s, 1920×1080 | 35 s (~5 quadros/s) | dois renders com os mesmos quadros (md5 idêntico) |
| `cena-web` | modelo CSS + GSAP (título, 4 cartões com stagger), 6 s, 1920×1080 | 33 s; 54 s em ProRes 4444 com alpha | timeline posicionada por `seek(t)` |
| `conferir-fala` | 30 s de fala real, legenda automática de outra origem como roteiro | instantâneo | 79 palavras, 1 "parecida" (nome próprio) e 3 que faltam por causa da borda do recorte |

## O que foi avaliado e não entrou

| Do vídeo | Decisão | Motivo |
|---|---|---|
| Remotion | segue o ADR-16 | cobra assento de empresa com 4 ou mais pessoas; nada mudou |
| HyperFrames (HTML → vídeo, Apache-2.0) | não entra como dependência | o renderizador próprio cobre o mesmo contrato sem Node (ver decisão 6). Não foi medido aqui |
| Voz clonada e avatar falante | fora | serviços pagos e fora do plano do ADR-15 (o plugin não imita a pessoa gravada) |
| Efeito sonoro gerado por descrição | fora | o `/efeitos` sintetiza whoosh, pop e ding pelo ffmpeg; os pesos abertos de geração de áudio são não comerciais |
| Biblioteca de visão do sistema operacional | fora do padrão | só existe em uma plataforma; o CI roda em duas. Pode entrar como backend extra de `rosto`/`ocr` |
| Texto "preso no chão" (perspectiva) | fora, por ora | pede rastreio planar (homografia) e composição com perspectiva, que o ASS não faz; `rastrear.py` declara o limite |

Também do vídeo, e que viraram orientação nas skills em vez de código: escolher a curva de easing de propósito
(`/animacao`), trilha com o tamanho de cada capítulo (`/trilha`), igualar a cor do B-roll (`/banco`) e um
[glossário](../glossario.md) dos termos que o vídeo ensina, ligado às skills.

## Limites declarados

- `rostos`: rosto de frente e de três quartos; perfil fechado, rosto muito pequeno ou coberto
  escapam. A conferência compara pixels: precisa da entrada e da saída da **mesma** etapa (mesma linha do tempo).
- `cena-web`: ~5 quadros/s em 1080p; WebGL por software (sem pós-processamento pesado); a fonte é a do sistema
  ou da marca, então a mesma cena pode diferir entre máquinas com fontes diferentes (dentro da mesma máquina o
  resultado é idêntico).
- `rastrear`: um plano por rastro; região sem textura é recusada; objeto pequeno sobre fundo que se move é o caso
  difícil e a skill manda conferir o fim do trecho. Sem perspectiva.
- `ler-tela`: a caixa vale para o quadro lido; em tela com rolagem, o destaque fica no intervalo em que a tela está
  parada. **Tarja por OCR não é garantia de privacidade**: texto pequeno ou borrado pode não ser lido; a skill
  exige revisão dos quadros depois.
- `conferir-fala`: a transcrição erra; por isso a tolerância (2%), a classe "parecida" e o arquivo de equivalentes
  para número, sigla e nome próprio.
- `banco-video`: validado contra um servidor falso com as rotas da API; **não foi exercitado contra o serviço
  real** neste ciclo (sem chave na máquina de desenvolvimento).

## O que o uso numa aula real mostrou

As operações foram aplicadas a uma videoaula de código já entregue (16 min, 1080p, montada por blocos) para
produzir uma segunda versão: 26 destaques por OCR no instante em que cada trecho de código é falado, um separador
de capítulo em 3D (`/cena-web`) e as conferências. Quatro defeitos só apareceram ali, e viraram correção e teste:

- **Contar quadros não é confiável em entrega montada por blocos.** O vídeo mudava de parâmetros aos 6,9 s (emenda
  da cartela de abertura) e o ffmpeg reinicia o grafo de filtros nesse ponto, zerando o número do quadro: a
  amostragem por índice passou a apontar quadros 7 s adiantados e a conferência de rosto acusou a aula inteira.
  `nucleo/quadros.py` agora escolhe a amostra pelo tempo do quadro. Pela mesma razão, trocar um trecho do vídeo
  por contagem de quadros (`trim=end_frame`, `select=eq(n,…)`) ou por `-itsoffset` + `overlay` saiu deslocado;
  o que funcionou foi cortar por tempo em partes e juntar, conferindo a emenda por tempo (`-ss`).
- **O destaque de um pedaço de token cobria o token inteiro** (`str(idade)` dentro de `"+str(idade)+"`): a caixa
  passou a ser recortada na proporção dos caracteres.
- **Em aula de código a tela rola logo depois de cada execução.** O modo `--lote` nasceu disso: procura o texto
  na janela em que é falado e só destaca num trecho em que ele fica parado.
- **A timeline do GSAP tem `.then()`**: tratada como Promise, travava o render para sempre.

O que a ferramenta não decide sozinha: 4 dos 26 destaques caíram, na primeira rodada, num momento de erro do
instrutor ou atrás de um pop-up do editor (o texto procurado estava lá, mas não era o momento certo). Quem resolve
é a folha de quadros conferida a olho, que a skill exige. O OCR também leu `"-"` como `"_"` num caso (resolvido
com `regex`). Tempo: ~9 min de CPU para os 26 itens.

## Consequências

- Dependência nova, só para quem usa: `opencv-python-headless` (Apache-2.0) e `rapidocr` (Apache-2.0), via
  `uv run --with`. Quem não usa não baixa nada; o resto do plugin não muda.
- 26 skills (`/cena-web`, `/rastrear`, `/ler-tela`, `/banco`); `/prova`, `/lettering`, `/tela-dividida`, `/video-animado`,
  `/video-docs`, `/animacao`, `/trilha` e `/editar` ganham passos, sem mudar o que já faziam.
- `tests/visao.sh` roda no CI nos dois sistemas com OpenCV real para o rastreamento e backends falsos para rosto e
  OCR (`tests/stub/modelos_falsos.py`), no padrão do ComfyUI falso; `VE_TESTE_MODELOS=1` acrescenta o OCR real.
- `/cena-web` pede um Chrome ou Chromium na máquina (o `doctor.sh` avisa); `tests/cena_web.sh` roda no CI e é
  pulado onde não houver navegador. WebGL roda por software: a cena 3D é para blocos curtos, não para minutos.
