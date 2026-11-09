# Núcleo: CLI, modelos de IA e servidor MCP

Desde a 0.5.0 os scripts são organizados pelo pacote `video_editores` (ADR-10 a 12 em
[adr/2026-11-08-nucleo-modelos-mcp.md](adr/2026-11-08-nucleo-modelos-mcp.md)). As skills continuam chamando os
scripts como antes; o que muda é que agora dá para usar tudo **sem o Claude Code**, trocar os modelos por
configuração e expor as operações a qualquer cliente MCP.

## CLI `video-editores`

Do checkout do repositório (ou do cache do plugin):

```bash
cd ~/code/video-editores && PYTHONPATH=. python3 -m video_editores.cli listar
```

Instalada como ferramenta (sem clonar; `uv` resolve as dependências dos modelos sob demanda):

```bash
uv tool install "video-editores @ git+https://github.com/fmnapoli/video-editores"
video-editores listar                     # operações e scripts
video-editores modelos                    # backends configurados e dependências
video-editores transcrever originais/aula.mp4 --prompt "Python, lista, dicionário"
video-editores prova saida/aula.mp4
video-editores aula-recorte-paralelo trabalho/aula01/aula.json 4 --fundo   # roda em segundo plano, imprime o id
video-editores tarefas                    # estado das tarefas em segundo plano
```

Cada operação do catálogo tem um nome estável e repassa os argumentos ao script (`video-editores listar` mostra o uso).
Scripts Python com dependências rodam com `uv run --with …` (isolado); `--direto` usa o Python atual.

| Operação | Script | Skill |
|---|---|---|
| `transcrever`, `tomadas`, `montar-trechos`, `destaques` | `scripts/transcribe.py`, `takes.py`, `render_spans.sh`, `highlights.py` | legenda, tomada, destaques |
| `lettering`, `checklist`, `texto-atras`, `prova`, `doctor` | `scripts/lettering_ass.py`, `checklist_ass.py`, `text_behind.py`, `proof.sh`, `doctor.sh` | lettering, checklist, texto-atras, prova |
| `docs-render` | `scripts/render-docs.sh` | video-docs |
| `cenas-tts`, `cenas-montar`, `cenas-folha` | `skills/video-animado/scripts/*` | video-animado |
| `aula-*` (cenas-modo, layout, remap, identidade, recorte, recorte-paralelo, render-cenas, montar, legenda, finalizar, publicar) | `skills/videoaula/scripts/*` | videoaula |

## Modelos de IA trocáveis

Três papéis, cada um com backends registrados em `video_editores/modelos/`:

| Papel | Variável | Padrão | Outros |
|---|---|---|---|
| ASR (transcrição) | `VE_ASR` | `faster-whisper` | registrar |
| Segmentação de pessoa | `VE_SEG` | `rembg` (u2net_human_seg; `--model birefnet-portrait` para bordas melhores) | registrar |
| TTS (narração) | `VE_TTS` | `edge` | registrar |
| Dispositivo | `VE_DEVICE` | `auto` (cuda se houver `nvidia-smi`, senão cpu) | `cpu`, `cuda` |
| Codificador de vídeo | `VE_ENCODER` | `libx264` | `h264_nvenc`, `hevc_nvenc`, `h264_videotoolbox`, `h264_vaapi` |

Precedência: argumento do script (`--backend`, `--device`) > variável de ambiente > `video-editores.toml` na pasta do
projeto (ou `$VE_CONFIG`) > padrão.

```toml
# video-editores.toml
[modelos]
seg = "rembg"
device = "cuda"
encoder = "h264_nvenc"
```

### GPU

Nada a instalar à mão: com `VE_DEVICE=cuda` o backend `rembg` declara `onnxruntime-gpu` em vez de `onnxruntime`, o
`faster-whisper` usa `float16`, e `VE_ENCODER=h264_nvenc` troca o libx264 no recorte e nos blocos da videoaula.
`make doctor` mostra o dispositivo efetivo e os codificadores que o ffmpeg local declara.

```bash
VE_DEVICE=cuda VE_ENCODER=h264_nvenc video-editores aula-recorte-paralelo trabalho/aula01/aula.json 4
```

Ganhos esperados (não medidos aqui, sem GPU): recorte de ~2,5 s/frame para dezenas de fps; transcrição `large-v3` em
segundos por minuto. Manim continua em CPU.

### Um backend próprio

Uma classe com o contrato de `video_editores/modelos/base.py` (`deps(device)` + o método do papel) e um registro por env:

```python
# meupacote/seg.py
class MeuSegmentador:
    nome = "meu"; descricao = "modelo interno"
    @staticmethod
    def deps(device="cpu"): return ["torch", "meupacote"]
    def __init__(self, modelo="x", device="cpu", threads=4): ...
    def mascara(self, img, pos_processar=True): ...   # PIL RGB -> PIL L
    def recortar(self, img): ...                      # PIL -> PIL RGBA
```

```bash
export VE_MODELOS_EXTRA="seg:meu=meupacote.seg:MeuSegmentador" VE_SEG=meu
video-editores modelos      # deve listar "meu"
```

## Áudio determinístico (`nucleo/audio.py`)

`medir(path)` (LUFS, dBTP, LRA), `normalizar(entrada, saida.wav, alvo, tp)`, `normalizar_video(...)` (vídeo copiado), `fades(d)` e
`quadros(d, fps)`. A normalização é ganho estático até o alvo integrado mais `alimiter` com oversampling a 192 kHz no teto de pico
real, medida depois e repetida com teto menor se o pico passar, ou com o ganho corrigido se o loudness saiu do alvo (até 4 passadas). Motivo (ADR-13): o `loudnorm` linear confia na medição da primeira
passada e, com degraus nas junções de uma montagem por blocos, entregou +9,2 dBTP; o dinâmico mexe na dinâmica da fala. Na CLI:
`video-editores normalizar-audio ENTRADA SAIDA [--alvo -14] [--tp -1.5] [--filtro ...]`. A saída de vídeo usa `audio.AAC` (256k, sem PNS: o PNS do codificador nativo gerou +4,7 dBTP a partir de um wav limitado a −2,5) e a medição reportada é a do arquivo final.

## Outros agentes (Codex, OpenCode, Kiro)

`video-editores integrar codex|opencode|kiro|todos [--projeto DIR | --usuario]` instala as skills, registra o servidor MCP
e grava as regras no formato de cada agente. Detalhes, pastas e limitações em [agentes.md](agentes.md).

## Servidor MCP

Invólucro fino sobre o mesmo catálogo (ADR-11): ferramentas `listar_operacoes`, `listar_modelos`,
`executar_operacao` (qualquer operação, argumentos como na CLI), e tipadas: `transcrever`, `recortar_pessoa`,
`lettering`, `prova`, `videoaula_montar`, `videoaula_finalizar`; tarefas: `tarefa_status`, `tarefa_esperar`,
`tarefa_cancelar`, `tarefas_listar`; `ler_texto` (arquivos de texto do projeto) e `versao`.

Operações longas voltam com `estado: "rodando"` e um `id`; o cliente acompanha com `tarefa_status`. Os processos
sobrevivem à desconexão do cliente. Todo caminho precisa estar dentro de `--raiz` (padrão: pasta atual).

### Claude Code (stdio)

```bash
claude mcp add video-editores -- uvx --from "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores" video-editores-mcp --raiz /caminho/do/projeto
```

Do checkout: `claude mcp add video-editores -- uv run --with "mcp>=2" --directory ~/code/video-editores python -m video_editores.mcp_server --raiz /caminho/do/projeto`.

### Claude Desktop ou outro cliente (JSON)

```json
{"mcpServers": {"video-editores": {"command": "uvx",
  "args": ["--from", "video-editores[mcp] @ git+https://github.com/fmnapoli/video-editores", "video-editores-mcp", "--raiz", "/dados/projetos/aulas"]}}}
```

### Máquina com GPU (HTTP)

```bash
VE_DEVICE=cuda VE_ENCODER=h264_nvenc video-editores-mcp --http 3001 --host 127.0.0.1 --raiz /dados/projetos
# cliente: http://127.0.0.1:3001/mcp
```

O servidor não autentica: em rede, coloque-o atrás de um proxy com autenticação ou acesse por túnel/VPN. Servidor e
projeto precisam ver o mesmo storage, porque o protocolo transporta caminhos, não vídeo.

## Testes

`tests/nucleo.sh` cobre registro e configuração dos modelos (env, toml, backend extra), `codec_video`, `audio.normalizar`
(estalos a fundo de escala: pico ≤ −1,5 dBTP a −14 LUFS), retry do edge-tts com o stub, catálogo (todo
script existe; comando com `uv run`, bash e python), a CLI (`prova`), tarefas em segundo plano (`--fundo`, esperar,
listar) e o servidor MCP em processo (`tests/mcp_test.py`: ferramentas, operação curta, tarefa longa, recusa de
caminho fora da raiz e de operação desconhecida). Roda no CI junto com o smoke.
