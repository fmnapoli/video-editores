# Guia de produção: spec → vídeo

Serve para quem produz (você ou um agente em paralelo). Os caminhos são relativos à
raiz do projeto, de onde o montador é chamado.

## Pastas sugeridas

- `originais/`: brutos. **Não alterar, apagar ou mover.**
- `specs/<slug>/spec.json`: a edição de cada vídeo.
- `saida/`: `<slug>.mp4` (com `"srt_dir": "legendas"` e `"roteiro_dir": "roteiros"` o `.srt` e o roteiro
  saem em pastas próprias, já no formato de entrega: o VLC dobra a legenda se achar o `.srt` ao lado do `.mp4`).
- `trabalho/<slug>/`: cache de TTS, `.ass`, frames de QA.

## Comando

    uv run --with edge-tts --with pillow python <skill>/scripts/build.py specs/<slug>/spec.json

Imprime JSON com `total`, `cues` e, por cena, `t0`, `dur`, `footage`, `tts`, `freeze`,
`speeds`, `avisos`, e grava `trabalho/<slug>/timeline.json` e `trabalho/<slug>/palavras.transcript.json`
(palavras com a grafia da legenda e o tempo da fala, entrada direta do `/legenda` estilo `reels-palavra`;
cenas com `tts` próprio ficam de fora). Render de 30–60 s por vídeo.

**Leia os `avisos`** (também vão para o stderr): caixa fora de 1280x720, destaque ou balão sobre a faixa
da legenda, `at` que começa num trecho cortado (o destaque entra atrasado) ou cai todo num corte (não aparece).

**Falha de TTS encerra o build.** O edge-tts repete 3 vezes (`VE_TTS_ESPERA` entre tentativas) e depois
sai com erro. O `.mp4` é gravado em `trabalho/` e só substitui o de `out_dir` no fim, junto com o `.srt`:
um build que falha deixa o par antigo intacto e coerente.

## Lote

Rode o lote parando no primeiro erro (`set -e` ou `&&`) e **termine sempre com o conferidor**:

    python3 <skill>/scripts/confere_saida.py specs/*/spec.json

Ele compara o texto de cada `.srt` com as legendas do spec e o horário do `.mp4` com o do spec, e sai com 1
listando o que remontar. Caso real (nov/2026): o edge-tts falhou no meio do lote, o lote seguiu, e o vídeo
com a narração antiga ("15 chaves") ficou no lugar com cara de atualizado.

Termos em inglês: escreva normal, na legenda e no `tts`. A voz padrão (Thalita
Multilingual) pronuncia inglês nativamente. Se ela errar um termo do projeto, corrija só
ele em `"glossary"` do spec (vale só para a fala). Confira o texto falado na seção
"Narração TTS" do `roteiro-<slug>.md` gerado.

O conteúdo vem do roteiro aprovado: as cenas, o texto "Narração TTS" e os blocos de
"Legenda" são **conteúdo aprovado**. Copie-os para o spec sem reescrever (`tts` = linha
numerada da seção TTS; `legend` = blocos daquela cena, preservando o `\n` interno).

## Spec (JSON)

```jsonc
{
 "slug": "...", "title": "<título curto>", "subtitle": "<produto/área>",
 "acoes": "...", "doc": "...", "revisao": ["..."],   // opcionais, vão para o roteiro gerado
 "out_dir": "saida", "work_dir": "trabalho/<slug>",
 "size": [1920, 1080],                               // opcional; padrão 1280x720
 "voice": "pt-BR-ThalitaMultilingualNeural",         // opcional (padrão)
 "glossary": {"kubectl": "cube control"},            // opcional: correção de pronúncia de termos do projeto (ou caminho de JSON)
 "sources": {"a": "originais/<arquivo>.mp4", "b": "..."},
 "scenes": [
  {"src": "a", "chip": "2–4 palavras",
   "clips": [[ini, fim, vel], ...],       // segundos do bruto; vel opcional (1.0); vel<1 = câmera lenta
   "fit": "auto",                          // auto: acelera (até 2,2×) ou desacelera (até 0,7×) para casar com a fala; "none" respeita vel
   "tts": "...",                           // opcional: sem ele a voz lê a legenda; o "glossary" é aplicado aqui
   "legend": ["...", "..."],
   "callouts": [{"at": [t0, t1], "box": [x,y,w,h], "focus": true, "balloon": "≤45 chars", "balloon_at": [x,y]}],
   "masks": [{"box": [x,y,w,h], "at": [t0, t1], "label": "opcional"}],
   "no_client": true                       // opcional: desliga a tarja fixa (chrome.client) nesta cena
  }
 ],
 "srt_dir": "legendas", "roteiro_dir": "roteiros",   // opcionais
 "chrome": {"band": 100, "logo": "marca/logo.png",   // opcional: faixa opaca sobre a barra do navegador
            "client": [x,y,w,h], "client_label": "cliente de teste"},  // tarja fixa em todas as cenas
 "chrome_src": {"b": {"band": 0, "client": null}}    // opcional: ajuste por fonte
}
```

- `at` em segundos do **bruto**; o montador converte pelos clipes. Se `at[1]` ≥ fim do
  último clipe, o destaque segue até o fim da cena (inclusive congelamento).
- **Coordenadas sempre em 1280x720**, mesmo com `"size": [1920, 1080]`.
- `focus: true` escurece tudo fora da caixa: use nos cliques-chave (campo a preencher,
  botão de confirmar, resultado), não em tudo.
- `balloon_at` opcional: sem ele o balão fica acima da caixa (ou abaixo, se não couber).
  Longe da caixa, sai uma seta automática. Nunca deixe o balão cobrir a caixa nem a faixa
  da legenda (y > 630).
- Sem `box`, dá para usar só `"balloon"` + `"balloon_at"` como aviso solto.
- `masks`: retângulo opaco por baixo dos destaques; sem `at` vale a cena inteira; na
  última cena vale até o fim do vídeo. Use em todo dado pessoal visível: e-mail, telefone,
  documento, nomes de terceiros, token/URL de autenticação, caixa de entrada, abas e
  favoritos do navegador legíveis. Na dúvida, corte o trecho em vez de tarjar.
- `chrome`: para gravações de navegador. `band` (altura em px de 1280x720, ~100 cobre abas, URL e
  favoritos) desenha uma faixa com o logo opcional, o título e o subtítulo do spec, e some com a barra do
  navegador de uma vez em todas as cenas. `client` é uma tarja fixa para o que aparece em toda tela no
  mesmo lugar (seletor de cliente/organização do portal, nome do usuário). Quando uma cena mostra outra
  tela (sem o seletor, ou com algo útil ali), ponha `"no_client": true` nela; **confira a última cena**:
  foi lá que, numa regravação, o cliente ficou à mostra porque a tela mudou de layout. `chrome_src`
  ajusta por fonte (ex.: um terminal gravado sem navegador: `{"band": 0, "client": null}`).

## Regras de corte

1. Comece cada clipe **depois** que a tela carregou: nada de spinner, página em branco,
   modal vazio, nem a gravação mostrando a si mesma. Ache os instantes com
   `ffmpeg -i bruto.mp4 -vf "select='gt(scene,0.03)',showinfo" -f null - 2>&1 | grep -o 'pts_time:[0-9.]*'`
   (0.03 pega trocas de tela; 0.004 pega até digitação).
2. Tire esperas, leituras de documentação, passagens repetidas e falas fora da ação. Se a
   espera mostra progresso útil, mantenha curta a 4–8× com balão "acelerado".
3. Prefira clipes do momento em que algo acontece (clique, digitação, resultado). A
   narração manda no ritmo: `fit: auto` ajusta a velocidade; evite congelamentos > 3 s
   (se sobrar fala, acrescente clipe).
4. Cenas = cenas do roteiro, na mesma ordem.

## Coordenadas dos destaques

- Frame com grade (em 1280x720):
  `ffmpeg -v error -y -ss <t> -i "<bruto>" -frames:v 1 -vf "scale=1280:720,drawgrid=w=100:h=100:t=1:c=red@0.6,drawgrid=w=500:h=500:t=2:c=blue@0.8" g<t>.png`
  Se a ferramenta de imagem reduzir o frame, ela informa o fator de escala: multiplique.
- Recortes finos: `-vf crop=w:h:x:y`. Confirme o instante exato de colagens, cliques e
  resultados extraindo 4–8 frames a cada 1 s e empilhando com `vstack`/`hstack`
  (`xstack` para grades) antes de fixar `at`.
- Listas e painéis rolam sozinhos: confira o frame antes de fixar a caixa.
- **Fonte em 1080p**: as coordenadas continuam em 1280x720. Extraia sempre o frame com `scale=1280:720`
  (o comando acima já faz) ou divida por 1,5 o que medir no quadro cheio. Caixa medida em 1080p sai do
  quadro (o montador avisa) ou cai no elemento errado.
- **Elemento que muda de lugar entre cenas** (barra de busca, botão que desce com a rolagem): em vez de
  estimar no olho, ache a linha pela cor dos pixels em alguns frames, por exemplo com Pillow:
  `[y for y in range(100, 630) if img.getpixel((x, y)) == cor_da_barra]` num `x` que corta o elemento.
- Área útil típica de gravação de navegador: y 104–630 (acima a barra do navegador,
  abaixo a legenda).

## Revisão pós-produção (obrigatória)

1. `ffprobe -v error -show_entries stream=codec_name,width,height,channels:format=duration -of compact saida/<slug>.mp4`
   → h264 na resolução do spec, aac 2 canais.
2. Para **cada** destaque e tarja, extraia um frame no meio do intervalo no vídeo
   **final** (tempo de saída pelo `timeline.json`) e monte uma folha de contato
   (`xstack`/`vstack`, `scale=1280:-1`). Confira: caixa no elemento certo, balão legível
   e sem cobrir o alvo, texto do balão coerente com a tela **naquele instante** (não
   dizer "colado" com o campo vazio), tarja cobrindo o dado no início e no fim da cena.
3. Extraia 2–3 frames em momentos de legenda: ela aparece e não colide com balões.
4. Corrija o spec e remonte até a folha ficar limpa. Guarde como `trabalho/<slug>/qa.png`.
5. Reporte: duração final, cenas (dur/freeze/speeds), destaques, o que corrigiu e
   qualquer dúvida de conteúdo. Não altere a narração por conta própria: se a tela
   contradiz o texto, reporte.

## Regravação de um vídeo já publicado

Quando chega uma gravação nova da mesma ação (tela mudou, ou a anterior tinha erro):

1. Faça backup do spec e do `.mp4`/`.srt` publicados (`spec.json.bak-<motivo>`). Parta do spec antigo:
   troque `sources` e refaça `clips`, mantendo título, cenas e legendas que continuam valendo.
2. **Nenhuma coordenada nem `at` do spec antigo vale**: o layout e os tempos mudaram. Remeça cada caixa e
   cada tarja na gravação nova (inventário de mudanças de tela, frame com grade, folha de contato).
3. Releia a narração contra a tela nova: a gravação nova costuma trazer mudanças de comportamento
   (limites, nomes de aba, opções). Quando a tela contradiz o material de apoio (slides, FAQ, cola), a
   correção vai para o material também, não só para a narração.
4. Publique por cima mantendo o link: no Drive, `rclone copyto novo.mp4 remoto:pasta/<nome>.mp4` substitui
   o conteúdo e mantém o ID do arquivo (upload novo gera link novo); guarde a versão anterior numa
   subpasta `bkp`. Depois rode `confere_saida.py`.

## Para agentes em paralelo

Proibido: alterar brutos; alterar narração/legenda; editar `build.py` (achou bug,
reporte); instalar coisas; publicar ou enviar algo. Nenhuma senha, token, chave ou dado
pessoal pode aparecer nos clipes.
