# Pedidos prontos

Copie, cole no Claude Code e troque o que estiver entre `< >`. Cada pedido aciona o `/editar`, que monta o plano com os skills indicados e para nos pontos de aprovação.

## Reels, Shorts, TikTok (vídeo falado, 20–90 s)

| Pedido | O que acontece | Skills |
|---|---|---|
| "Corta as pausas e fica com a última tomada" | remove repetições e silêncios | tomada → corte |
| "Legenda palavra por palavra" | legenda estilo reels, 2–3 palavras por bloco | legenda |
| "Legenda com a palavra destacada, igual TikTok" | `legenda_palavra.py`: páginas de ~1,5 s, palavra falada em amarelo (`--modo preenche` para karaokê) | legenda (reels-palavra) |
| "Abre com um gancho forte na tela" | 5 opções de gancho; o escolhido vira título animado | ganchos → lettering |
| "Põe a frase forte atrás de mim" | texto entre o fundo e a pessoa | texto-atras |
| "Faz um checklist do que eu falar" | itens entram no instante em que são ditos | checklist |
| "Responde esse comentário com um cartão na tela: `<texto do comentário>`" | cartão com o comentário no topo | lettering (estilo cartao) |
| "Deixa com cara de capa de revista" | moldura, título grande, chamadas laterais | lettering (estilo capa) |
| "Divide a tela: o vídeo `<arquivo>` em cima e eu reagindo embaixo" | reação 9:16 | tela-dividida |
| "Mostra o antes e o depois na tela dividida" | bruto em cima, editado embaixo | tela-dividida |
| "Me recorta e troca o cenário por `<imagem ou vídeo>`" | fundo trocado sem pano verde | tela-verde |
| "Põe um contorno neon em mim nessa frase" | contorno colorido na silhueta | tela-verde (neon) |
| "Explica essa parte com uma animação" | motion graphic sobreposto | animacao |
| "Ilustra essa parte em 3D" | texto/objeto 3D com fundo transparente | 3d |
| "Coloca uma trilha calma e abaixa quando eu falo" | música com ducking, -14 LUFS | trilha |
| "Whoosh nas trocas de plano e pop nos textos" | efeitos sincronizados | efeitos |
| "Edita igual esse reels: `<link>`" | copia ritmo, legenda e estrutura | referencia → pipeline |
| "Disfarça os cortes com zoom e dá um punch quando eu falo 'de graça'" | troca de plano a cada corte, punch na palavra | camera |
| "Edição completa pra Reels" | tomada → corte → camera → ganchos → lettering → legenda → trilha → efeitos → prova | editar |

## Aula gravada

| Pedido | Skills |
|---|---|
| "Transforma essa aula de 2 horas num vídeo de 10 minutos pro YouTube" | destaques → corte → legenda → prova |
| "Tira dessa aula três Reels de 45 segundos" | destaques (modo reels) → lettering → legenda |
| "Corta essa aula em 90 segundos, mas com começo, meio e fim" | destaques (arco narrativo: blocos → etapas → relatório → montar) → ganchos → legenda |
| "Esse vídeo convence? O que está faltando nele?" | destaques (arco narrativo, só o relatório) |
| "Só limpa a aula: tira pausas e erros, mantém tudo" | tomada → corte |
| "Faz um checklist dos passos que eu explico" | checklist |
| "Refaz essa videoaula com cenário novo, troca o Excalidraw por diagramas animados, põe abertura e separadores, mantém o professor na tela" | videoaula (referencia → corte com remap → identidade → recorte IA → Manim → piloto → lote) |
| "Monta um curso com os vídeos do baterista: mostra a partitura do que ele toca e um exemplo tocado antes de cada clipe" | partitura (transcrição aprovada → cartões → exemplos tocados) → video-animado ou videoaula → prova |

## Vlog e vídeo longo

| Pedido | Skills |
|---|---|
| "Edita pro YouTube com os melhores momentos. Onde eu não falo, põe música" | destaques → corte → trilha (ducking) → legenda |
| "Junta as gravações da pasta `<pasta>` na ordem dos arquivos e corta os silêncios" | corte (por arquivo) → concat |
| "Coloca o nome do lugar quando eu chego em cada um" | lettering (lower third) com tempos da transcrição |

## Anúncio e criativo

| Pedido | Skills |
|---|---|
| "Faz três versões desse criativo com ganchos diferentes nos 3 primeiros segundos" | ganchos → render_spans/lettering ×3 |
| "Versão quadrada 1:1 e versão 9:16 desse vídeo" | ffmpeg crop/pad (receita em `/tela-dividida`) |
| "Legenda com destaque amarelo nas palavras de preço" | legenda com `PrimaryColour` por bloco |

## Documentação de produto (gravação de tela)

| Pedido | Skills |
|---|---|
| "Transforma as gravações em `originais/` em vídeos de documentação, um por ação" | video-docs (inventário → roteiros → piloto → lote) |
| "Transcreve e inventaria o que tem nessas gravações" | video-docs (etapa 1) |
| "Revisa a narração contra o código em `<pasta>`" | video-docs (revisão de coerência) |
| "Chegou gravação nova dessa ação: refaz o vídeo e substitui o publicado" | video-docs (regravação: backup, remedir destaques, `confere_saida.py`) |
| "Cobre a barra do navegador e o nome do cliente em todas as cenas" | video-docs (`chrome.band`, `chrome.client`) |
| "Confere se todos os vídeos do lote estão atualizados" | video-docs (`confere_saida.py`) |

## Identidade do cliente

| Pedido | Skills |
|---|---|
| "Usa as cores, a fonte e o logo da empresa nos vídeos" | marca (`marca/marca.json` + prancha para aprovar), lido por todas as skills |
| "Pega a identidade desse manual de marca" / "aplica o tema dessa apresentação" / "aqui está o pacote de marca" | marca (`extrair_marca.py` → proposta → `validar_marca.py` → prancha) |
| "Valida essa paleta e me mostra como fica" | `validar_marca.py` (contraste, fonte, logo, prancha) |
| "Legenda com a palavra falada na cor da marca" | video-docs com `legenda.estilo: "palavra"` |

## Cena em 3D e cartela com layout

| Pedido | Skills |
|---|---|
| "Abertura em 3D com as letras do título, câmera girando" / "um objeto 3D simples com sombra" | cena-web (Three.js) |
| "Cartela com quatro cartões em duas colunas, entrando um por vez" / "lista com quebra de linha automática" | cena-web (CSS, com ou sem GSAP) |
| "Um selo girando no canto, por cima do vídeo" | cena-web `--alpha` (camada `.mov`) + overlay do ffmpeg |

## Marcar o que está na imagem

| Pedido | Skills |
|---|---|
| "Põe uma etiqueta que acompanha a prancha" / "marca esse carro e segue" | rastrear |
| "Destaca o botão Salvar quando eu falar dele" / "sublinha o nome do arquivo no print" | ler-tela (o instante vem da transcrição) |
| "Onde eu apareço, põe o título onde não cubra meu rosto" | lettering (posição pela `sugestao` do `rostos.py`) |
| "Falta imagem nesse trecho, põe um vídeo de ondas" | banco (opcional: só com chave própria; antes, o próprio bruto ou animacao) |

## Revisão e entrega

| Pedido | Skills |
|---|---|
| "Me mostra como ficou" | prova |
| "Confere se algum texto ficou em cima do meu rosto" | prova (`rostos.py --conferir`, entrada e saída da etapa de texto) |
| "Confere se a narração final bate com o roteiro" | prova (`transcribe.py` no vídeo final + `conferir_fala.py`) |
| "Esconde os e-mails que aparecem na gravação" | ler-tela (`--regex`, `--estilo tarja`) e depois prova |
| "Exporta a timeline pro DaVinci em vez do vídeo" | corte `--export resolve` |
| "Gera o SRT separado pra subir no YouTube" | legenda (só SRT) |
