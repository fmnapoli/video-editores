# video-docs: harness para vídeos de documentação

Transforma gravações de tela brutas em vídeos curtos de documentação: corta o tempo
morto, troca o áudio por narração sintetizada (edge-tts), queima legenda alinhada por
palavra, desenha destaques (caixa, foco, balão, seta), tarja dados sensíveis e abre com
uma cartela de título.

Nada é editado num editor de vídeo. Cada vídeo é descrito por um `spec.json` (cortes do
bruto, narração, legenda, destaques, tarjas) e o montador gera o `.mp4` com ffmpeg. Para
mudar um vídeo, você edita o spec e monta de novo.

## Conteúdo

| Caminho | O que é |
|---|---|
| `scripts/render-docs.sh` | Confere os pré-requisitos e monta um spec: `scripts/render-docs.sh specs/<slug>/spec.json` |
| `skills/video-docs/` | Skill do Claude Code com o pipeline completo |
| `skills/video-docs/SKILL.md` | Fluxo em etapas com gates (inventário → roteiros → piloto → lote), ferramentas, pegadinhas |
| `skills/video-docs/scripts/build.py` | O montador: spec → `.mp4` + `.srt` + `roteiro-<slug>.md` |
| `skills/video-docs/references/producao.md` | **Formato completo do spec**, regras de corte, coordenadas e QA |
| `skills/video-docs/references/revisao-coerencia.md` | Como conferir a narração contra o código antes de publicar |
| `skills/video-docs/scripts/confere_saida.py` | Confere se o `.mp4` e o `.srt` de cada spec estão atualizados (rodar ao fim de todo lote) |
| `scripts/validar_marca.py` | Valida o `marca/marca.json` do projeto e gera a prancha de aprovação da identidade |
| `skills/video-docs/glossario-ingles.json` | Grafia fonética de termos em inglês, só para voz não multilíngue (ver abaixo) |
| `skills/video-docs/scripts/testar_pronuncia.py` | Ouve um texto com e sem glossário, ou o glossário inteiro |
| `exemplos/video-docs/` | Exemplo executável com bruto sintético |

## Pré-requisitos (Ubuntu/Debian)

```bash
sudo apt install ffmpeg fonts-dejavu-core       # o ffmpeg precisa ter libass (o do apt tem)
curl -LsSf https://astral.sh/uv/install.sh | sh  # o render-docs.sh baixa edge-tts e pillow sozinho
```

Precisa de internet ao montar: a narração vem do edge-tts (serviço da Microsoft, voz
padrão `pt-BR-ThalitaMultilingualNeural`, trocável com `"voice"` no spec). O áudio fica em cache
em `work_dir` e só é regerado quando o texto muda.

Para transcrever brutos (opcional): `uv tool install whisper-ctranslate2` e modelo
`medium` com `--initial_prompt` de vocabulário do domínio (detalhes no `SKILL.md`).

## Teste rápido

```bash
cd exemplos/video-docs
./gerar-bruto.sh                      # cria originais/demo.mp4 (20 s de padrão de teste)
../../scripts/render-docs.sh spec.json  # gera saida/demo.mp4 (~17 s), .srt e roteiro-demo.md
```

O spec do exemplo usa cartela, foco, balão, seta automática, tarja, mudança de velocidade e uma
cena sem `tts`, com termos em inglês (a voz lê a legenda). Faixa do navegador, tarja fixa, pastas de
saída e identidade são opcionais e estão descritos em `references/producao.md`.

## Montando um projeto seu

```
meu-projeto/
  originais/            brutos (nunca alterar)
  specs/<slug>/spec.json
  marca/marca.json      opcional: identidade do cliente (cores, fonte, logo, fundos)
  saida/                gerado (.mp4)
  legendas/ roteiros/   gerados, com "srt_dir" e "roteiro_dir" no spec
  trabalho/<slug>/      gerado (cache de TTS, .ass, timeline.json, palavras.transcript.json)
```

Rode o `render-docs.sh` **a partir da raiz do projeto**, porque os caminhos do spec são
relativos a ela:

```bash
cd meu-projeto && "${CLAUDE_PLUGIN_ROOT}/scripts/render-docs.sh" specs/<slug>/spec.json
```

Pontos que mais pegam:

- `at` de destaques e tarjas é em segundos do **bruto**; o montador converte pelos cortes.
- Coordenadas de caixa, balão e tarja são **sempre em 1280x720**, mesmo com
  `"size": [1920, 1080]`. Para achá-las, extraia um frame com grade (comando em
  `references/producao.md`).
- Se a fala for mais longa que a filmagem, o último quadro congela. Acima de 3 s,
  acrescente clipe.
- Sem `"srt_dir"`, o `.srt` sai ao lado do `.mp4`. Use `"srt_dir": "legendas"`: o VLC carrega
  a legenda externa de mesmo nome por cima da queimada e ela aparece dobrada.
- O relatório do montador traz `avisos` (caixa fora do quadro, balão sobre a legenda, `at`
  num trecho cortado). Leia antes de revisar por frames.
- Se o edge-tts não responder, o build **encerra com erro** e o vídeo anterior fica intacto.
  Num lote, pare no primeiro erro e termine com o conferidor:
  `python3 "${CLAUDE_PLUGIN_ROOT}/skills/video-docs/scripts/confere_saida.py" specs/*/spec.json`.
- Gravação de navegador: `"chrome": {"band": 100}` cobre abas, URL e favoritos com uma faixa;
  `"chrome": {"client": [x,y,w,h]}` tarja o que aparece em toda tela (seletor de cliente).

## Identidade do cliente

Cores, fonte, logo e estilo de legenda vêm de `marca/marca.json` na raiz do projeto. Sem o
arquivo, o vídeo sai com o visual padrão do plugin. Não edite nem copie o `build.py` para
trocar a identidade.

```json
{"nome": "Cliente",
 "cores": {"fundo": "#002233", "acento": "#00DBFF", "texto": "#FFFFFF"},
 "fonte": {"familia": "Cliente Sans", "arquivos": {"bold": "fontes/ClienteSans-Bold.ttf"}},
 "logo": {"png": "logo.png"},
 "fundos": {"cartela": "bg.png"},
 "legenda": {"estilo": "palavra"}}
```

Só as três cores são obrigatórias. Com logo, a cartela ganha o logo e o vídeo ganha uma tela de
encerramento de 3 s. `legenda.estilo` é `bloco` (padrão) ou `palavra` (a palavra falada na cor de
destaque). Antes de montar, valide e olhe a prancha:

```bash
uv run --with pillow --with fonttools python "${CLAUDE_PLUGIN_ROOT}/scripts/validar_marca.py" marca/marca.json
```

O validador reprova contraste insuficiente e fonte sem acentos, e propõe a cor corrigida sem
aplicar. Formato completo e regras (fonte licenciada, logo oficial) no
[ADR-17](adr/2026-11-11-identidade-visual.md).

## Pronúncia de termos em inglês

A voz padrão, `pt-BR-ThalitaMultilingualNeural`, fala português e pronuncia termos em
inglês ("deploy", "dashboard", "rollback") em inglês. Escreva tudo normalmente, sem grafia
fonética.

- Sem `tts` na cena, a voz lê a própria legenda.
- Se ela errar um termo do seu projeto, corrija só ele no spec:
  `"glossary": {"kubectl": "cube control"}` (ou o caminho de um JSON). A troca vale só
  para a fala; a legenda continua com a grafia normal.
- Para ouvir antes de montar:

  ```bash
  uv run --with edge-tts python "${CLAUDE_PLUGIN_ROOT}/skills/video-docs/scripts/testar_pronuncia.py" "Faça o deploy no cluster."
  ```

- O texto realmente falado aparece em `roteiro-<slug>.md`, seção "Narração TTS".
- Com uma voz pt-BR não multilíngue (`"voice": "pt-BR-FranciscaNeural"`), que lê inglês
  como português, o montador aplica sozinho o `skills/video-docs/glossario-ingles.json`
  (grafia fonética: "diplói", "clôster").

## Com Claude Code

O skill já vem com o plugin `video-editores` (`/video-editores:video-docs`). Sem o plugin:

```bash
cp -r skills/video-docs ~/.claude/skills/video-docs
```

Depois peça, por exemplo, "transforma as gravações em originais/ em vídeos de
documentação, um por ação". A skill conduz o fluxo e para nos gates (inventário,
roteiros, piloto) para você aprovar. Ela usa o `scripts/build.py` de dentro dela, o
mesmo que o `render-docs.sh` chama.

## Regras que valem para qualquer projeto

1. **A fala do bruto não é verdade.** Quem grava improvisa e erra. Confira cada
   afirmação da narração contra o código ou a documentação oficial
   (`references/revisao-coerencia.md`).
2. **Nenhum dado pessoal ou segredo na tela**: corte ou tarje (`masks`). Os brutos
   costumam ter, então trate-os como material interno.
3. **Revise por frames depois de montar**: um frame no meio de cada destaque e de cada
   tarja, numa folha de contato (`references/producao.md`, "Revisão pós-produção").
