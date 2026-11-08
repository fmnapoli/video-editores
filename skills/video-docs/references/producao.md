# Guia de produção: spec → vídeo

Serve para quem produz (você ou um agente em paralelo). Os caminhos são relativos à
raiz do projeto, de onde o montador é chamado.

## Pastas sugeridas

- `originais/`: brutos. **Não alterar, apagar ou mover.**
- `specs/<slug>/spec.json`: a edição de cada vídeo.
- `saida/`: `<slug>.mp4`, `<slug>.srt`, `roteiro-<slug>.md` (o montador regrava o roteiro a partir do spec).
- `trabalho/<slug>/`: cache de TTS, `.ass`, frames de QA.

## Comando

    uv run --with edge-tts --with pillow python <skill>/scripts/build.py specs/<slug>/spec.json

Imprime JSON com `total`, `cues` e, por cena, `t0`, `dur`, `footage`, `tts`, `freeze`,
`speeds`, e grava `trabalho/<slug>/timeline.json`. Render de 30–60 s por vídeo.

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
   "masks": [{"box": [x,y,w,h], "at": [t0, t1], "label": "opcional"}]
  }
 ]
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

## Para agentes em paralelo

Proibido: alterar brutos; alterar narração/legenda; editar `build.py` (achou bug,
reporte); instalar coisas; publicar ou enviar algo. Nenhuma senha, token, chave ou dado
pessoal pode aparecer nos clipes.
