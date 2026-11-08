# ADR-10/11/12 — Núcleo em camadas: modelos trocáveis, CLI única e servidor MCP

**Data:** 2026-11-08 · **Estado:** aceito e implementado (0.5.0) · **Substitui parcialmente:** ADR-01

## Contexto

O plugin nasceu como skills do Claude Code mais scripts CLI (ADR-01). Em 0.4.0 ele produziu uma videoaula de 20 min
redesenhada e a documentação em vídeo das ações de um produto, a partir de gravações de tela. A partir disso surgiu a proposta de
levá-lo além do Claude Code, em três frentes:

1. **abstrair o modelo**, para trocar os motores de IA (inclusive por modelos próprios) sem reescrever os scripts;
2. **uma skill para outros agentes comerciais**, para que o mesmo know-how sirva a outras ferramentas;
3. **um servidor MCP**, para que agentes internos (por exemplo numa plataforma com GPUs) usem as capacidades sem shell local.

Restrições: manter os scripts funcionando sozinhos no terminal (é o que permite depurar e testar sem agente);
não quebrar as skills existentes nem o `uv run --with` (ADR-04); não exigir nada rodando em segundo plano para quem usa
só o Claude Code.

## O que já estava abstraído

Os scripts (corte, remap, montagem por EDL, identidade, legenda, prova, publicação) são Python padrão + ffmpeg,
dirigidos por JSON. Nenhum depende do Claude. O que dependia de um modelo específico estava espalhado em cinco
pontos: `transcribe.py` (faster-whisper), `matte.py` e `text_behind.py` (rembg/onnxruntime), `tts_cenas.py` e
`build.py` (edge-tts). A inteligência de **autoria** (ler a fala e escrever diagramas Manim, decidir cortes de
conteúdo) está nas skills e depende do modelo de linguagem; essa parte não é abstraível sem perder qualidade e
fica fora deste ADR.

## Decisão

### ADR-10 — Pacote `video_editores` com interfaces de modelo

- `video_editores/modelos/`: três papéis com contrato explícito, **ASR** (`transcrever`), **Segmentador**
  (`mascara`/`recortar`) e **TTS** (`sintetizar`), cada um com backends registrados por nome. Backends iniciais:
  `faster-whisper`, `rembg`, `edge`. Cada backend declara `deps(device)`, os pacotes para `uv run --with`, então a
  escolha de GPU muda o pacote (`onnxruntime` → `onnxruntime-gpu`) sem o usuário saber.
- Configuração em camadas: argumento explícito > variáveis `VE_ASR`, `VE_SEG`, `VE_TTS`, `VE_DEVICE`, `VE_ENCODER` >
  `video-editores.toml` > padrão. Backends externos entram por `VE_MODELOS_EXTRA="seg:meu=pacote.mod:Classe"` sem
  mexer no repositório, o caminho para um modelo próprio.
- `video_editores/nucleo/ffmpeg.py` concentra sondagem, decodificação de áudio para ASR e `codec_video()`, que
  traduz `VE_ENCODER` (libx264, h264_nvenc, hevc_nvenc, h264_videotoolbox, h264_vaapi) em argumentos equivalentes.
  `matte.py` e `montar_aula.py` passam a usá-lo; os demais scripts migram quando forem tocados.
- `video_editores/nucleo/catalogo.py` é a **única fonte** das operações (nome estável → script, uso, dependências
  por papel, se é longa). CLI, MCP e documentação leem dele.
- `video-editores <operação> …` (`cli.py`): um comando para todos os scripts, resolvendo `uv run --with` a partir do
  catálogo e do backend configurado; `--fundo` roda em segundo plano. Os scripts continuam chamáveis diretamente.
- Os scripts acham o pacote por `VE_PKG_DIR` (definido pela CLI/MCP) ou pela raiz do checkout; a roda inclui
  `scripts/` e `skills/*/scripts` em `video_editores/recursos/`, espelhando a árvore, para os caminhos relativos
  entre scripts continuarem válidos.

### ADR-11 — MCP como invólucro fino com tarefas assíncronas

- `video_editores/mcp_server.py` expõe o catálogo como ferramentas (`executar_operacao` genérica + ferramentas
  tipadas para as operações mais usadas) e não contém lógica de edição. Transporte stdio por padrão (Claude Code,
  Claude Desktop) e streamable HTTP por `--http PORTA` (máquina remota com GPU).
- Operações longas (recorte por IA, render, transcrição) voltam na hora com um id; `tarefa_status`,
  `tarefa_esperar`, `tarefa_cancelar` acompanham. Os processos nascem em sessão própria e gravam o código de saída
  num arquivo, então sobrevivem à desconexão do cliente e outro processo do servidor sabe como terminaram.
- MCP passa **caminhos**, não mídia: `--raiz` define a pasta do projeto, todo caminho fora dela é recusado, e
  servidor e arquivos precisam compartilhar o storage. Isso é intencional: vídeos de GB não cabem no protocolo.
- O conhecimento de *como* editar (gates humanos, decisões de design, convenções de pastas) continua nas skills;
  o `instructions` do servidor só resume as convenções e manda pedir aprovação antes de render longo e entrega.

### ADR-12 — Skills para outros agentes só por demanda

- O formato `SKILL.md` (frontmatter + instruções) é o que os agentes de código convergiram a ler; o porte é de
  texto, não de código, porque os scripts e a CLI já são agnósticos. Com o MCP, um agente sem shell local também
  consegue executar. Não se mantém uma segunda cópia das skills até existir um segundo agente em uso real; quando
  existir, a cópia deve apontar para `video-editores <op>` em vez de caminhos do plugin.

## Alternativas consideradas

- **Só MCP, sem CLI:** perderia a depuração no terminal e obrigaria um processo rodando para quem usa só o Claude
  Code. Rejeitada; a CLI é a base e o MCP a envolve.
- **Reescrever os scripts como módulos do pacote:** limpo, mas semanas de regressão num código recém-validado em
  produção. Rejeitada por ora; o catálogo permite migrar script a script.
- **Transferir mídia pelo MCP (base64/recursos):** inviável para vídeo; storage compartilhado é a solução de
  sempre em pipelines de mídia.
- **Config por arquivo apenas (sem env):** env é o que funciona em contêiner e em `setsid nohup`; o toml fica para
  o projeto, o env para a máquina.

## Consequências

- Trocar motor é configuração: `VE_DEVICE=cuda VE_ENCODER=h264_nvenc video-editores aula-recorte-paralelo aula.json 4`.
- Um modelo próprio de segmentação ou ASR entra como classe com três métodos e um registro por env.
- Dois pontos de entrada a manter alinhados (skills com caminhos do plugin e CLI com nomes do catálogo); o smoke
  test confere que todo script do catálogo existe.
- O MCP amplia a superfície de segurança: a restrição de raiz é obrigatória e o modo HTTP não tem autenticação
  própria; em rede, fica atrás de um proxy com autenticação (ou só em localhost/VPN).
- `build.py` do video-docs continua com edge-tts embutido (ADR-07); o backend de TTS vale para `tts_cenas.py`.

## Integração com uma plataforma de GPUs

| Ponto | Hoje (CPU, local) | Na plataforma |
|---|---|---|
| Recorte de pessoa (`seg`) | u2net_human_seg, 2,3–3,3 s/frame; ~2 h para 3 min de locutor | `VE_DEVICE=cuda`: dezenas de fps; abre BiRefNet/MatAnyone como novos backends |
| Transcrição (`asr`) | medium int8, ~1,2× tempo real | large-v3 float16 em segundos por minuto de áudio |
| Codificação | libx264 veryfast | `VE_ENCODER=h264_nvenc` nos blocos e no recorte |
| Manim | CPU (cairo); não muda | igual; paralelizar por `-j` |
| Acesso | Claude Code com shell | `video-editores-mcp --http` ao lado do storage, agentes como clientes MCP |

## Roteiro e esforço estimado

| Etapa | Estado | Esforço |
|---|---|---|
| 1. Pacote, interfaces de modelo, catálogo, CLI, testes | feito (0.5.0) | — |
| 2. Servidor MCP stdio/HTTP com tarefas, testes em processo | feito (0.5.0) | — |
| 3. Validar em GPU: `VE_DEVICE=cuda`, NVENC, medir ganho real | pendente (sem GPU aqui) | 1 dia com a máquina |
| 4. Backends novos: BiRefNet/MatAnyone (vídeo), whisper large-v3 | pendente | 2–3 dias cada, com comparação visual |
| 5. HTTP atrás de autenticação + storage compartilhado na plataforma | pendente | 2 dias, depende da infra |
| 6. Skills para outro agente (ADR-12) | sob demanda | 1 dia por agente, só texto |
| 7. Modelo próprio de segmentação/ASR | sob demanda | registro leva minutos; o modelo é outro projeto |
