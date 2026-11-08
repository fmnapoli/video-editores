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

O spec do exemplo usa todos os recursos: cartela, foco, balão, seta automática, tarja,
mudança de velocidade e uma cena sem `tts`, com termos em inglês (a voz lê a legenda).

## Montando um projeto seu

```
meu-projeto/
  originais/            brutos (nunca alterar)
  specs/<slug>/spec.json
  saida/                gerado
  trabalho/<slug>/      gerado (cache de TTS, .ass, timeline.json)
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
- O `.srt` sai ao lado do `.mp4`. Na entrega, separe os dois em pastas diferentes: o
  VLC carrega a legenda externa de mesmo nome por cima da queimada e ela aparece dobrada.

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
