# ADR-15 — Geração de imagem e vídeo por IA no plugin

**Data:** 2026-11-09, revisto em 2026-11-12 · **Estado:** fase 1 em execução (0.13.0): papel `imagem` com backend ComfyUI · **Depende de:** máquina com GPU para validar a qualidade (pendência do ADR-10)

## Contexto

Depois do curso de bateria (0.7.0) veio a pergunta: o plugin cria vídeo generativo? Hoje **não**. As 21 skills
fazem edição (corte, tomadas, legenda, trilha), animação por código (Manim, ffmpeg, Blender), síntese de voz
(edge-tts) e de som (bateria por fórmula), recorte de pessoa por IA e transcrição. Nenhuma produz imagem ou vídeo
novo a partir de texto. A pergunta seguinte foi se dá para evoluir nessa direção sem trair o que o plugin é:
open source, local, determinístico onde possível, com gates humanos onde o erro é caro (ADR-01, 05, 06).

Onde a geração ajudaria de verdade, pelo que os projetos pediram:
- **fundos e ilustrações** para o `/video-animado` e para as cartelas do `/videoaula` (hoje: gradientes do Pillow e logo do cliente);
- **B-roll estático** para cobrir trechos de fala sem imagem útil (hoje: lettering sobre o próprio vídeo);
- **cenário** para o `/tela-verde` (hoje: imagem fornecida pelo usuário);
- **clipes curtos** (3–6 s) de transição ou metáfora visual, onde um vídeo gravado não existe.

Onde **não** ajuda e não entra: substituir a pessoa gravada, "deepfake" de locutor, gerar conteúdo factual (diagramas
de arquitetura, código na tela, dados) — isso continua vindo de medição e de animação por código, por precisão.

## Decisão proposta

### Dois papéis novos de modelo
Em `video_editores/modelos`, ao lado de ASR, Segmentador e TTS:
- **`imagem`**: `gerar(prompt, negativo=None, largura, altura, semente, passos) -> PNG`; variações por semente; opcional `imagem_base` (img2img) para manter a identidade de um fundo.
- **`video`**: `gerar(prompt, imagem_inicial=None, duracao_s, fps, semente) -> mp4 sem áudio`; a partir de uma imagem aprovada (image-to-video) é o caminho preferido, porque o gate acontece no quadro parado.

Backends pela mesma regra dos outros papéis (`VE_IMAGEM`, `VE_VIDEO`, `VE_DEVICE`, `video-editores.toml`), com `deps(device)` alimentando o `uv run --with`:
- **locais primeiro** (ADR-05): modelos abertos com licença permissiva ou de uso livre, executados num **servidor ComfyUI** (revisão de 2026-11-12, seção abaixo); `diffusers` em processo fica como alternativa possível, não implementada. A lista concreta de modelos (FLUX.1-schnell para imagem; LTX-Video, Wan ou CogVideoX para vídeo) é decidida **por workflow**, conferindo licença e memória na data, porque mudam a cada poucos meses;
- **API opcional** atrás da mesma interface, desligada por padrão, para quem não tem GPU; nunca obrigatória.

### Skill `/gerar`
Uma skill, não várias: "gera um fundo", "faz uma ilustração para esta cena", "um clipe de 4 s de ondas". Fluxo:
1. prompt escrito pelo Claude a partir do roteiro e da identidade (paleta, estilo, o que não pode aparecer), mostrado ao usuário;
2. **gate 1**: 4 variações em miniatura (sementes diferentes), o usuário escolhe ou pede outra rodada;
3. para vídeo, **gate 2**: quadro inicial aprovado antes de gerar movimento; folha de contato do clipe depois;
4. tudo gravado no projeto: `trabalho/<slug>/gerados/<id>.{png,mp4}` com `<id>.json` (prompt, negativo, backend, modelo, semente, passos, data), para regenerar e para o relatório de edição dizer o que foi gerado.

Integração com o que existe: imagem gerada vira `BG` de cena do `/video-animado`, fundo do `/tela-verde`, cartela do `/videoaula`; clipe gerado entra como bloco pronto (`video` na cena, mecanismo da 0.8.0) ou como B-roll no `/editar`.

### Regras
- Marcação: o relatório de edição e o `COMO-FOI-FEITO.md` listam cada peça gerada; cabe ao usuário decidir se e como declara isso na publicação.
- Pessoas: a skill não gera rostos de pessoas reais nem imita a pessoa gravada; pedidos assim são recusados na skill, não deixados para o modelo.
- Determinismo possível: semente fixa e versão do modelo gravadas; o mesmo JSON regenera a mesma imagem no mesmo backend.
- Prova: imagem gerada passa pelo mesmo olhar do `/prova` (texto ilegível, mãos, logos de terceiros).

### Backend ComfyUI (revisão de 2026-11-12)
O ComfyUI (github.com/comfy-org/ComfyUI) é o backend de referência dos papéis `imagem` e, depois, `video`.

**Por que ele e não `diffusers` em processo:**
- descarrega partes do modelo da GPU e aceita versões compactadas (fp8, GGUF): é o que leva modelos de vídeo como Wan e LTX-Video a caber em 8–12 GB, contra os 16–24 GB estimados acima. Para o papel `video`, é a diferença entre precisar de uma GPU de servidor e de uma de mesa;
- workflows dos modelos abertos novos costumam sair primeiro para ele;
- roda em outra máquina sem mudar nada no plugin: quem edita num notebook sem GPU aponta `VE_COMFYUI_URL` para a máquina que tem. Essa é a situação de quem mantém o plugin, num notebook com GPU integrada.

**Licença:** GPL-3.0. Cumpre o ADR-05 do mesmo jeito que ffmpeg e Blender: executável separado. O plugin não importa código do ComfyUI; só envia um workflow em JSON pela API HTTP (`/prompt`, `/history`, `/view`) e baixa o resultado. O backend usa só a biblioteca padrão do Python.

**Regras do backend:**
- **só nós nativos.** Nó de terceiro (custom node) é código Python arbitrário rodando no servidor, sem revisão, e já houve casos maliciosos. Workflow do plugin que precisar de um nó assim não entra;
- **workflows versionados no pacote** (`video_editores/modelos/workflows/comfyui/<nome>.json`), no formato de API, com marcadores (`"{{prompt}}"`, `"{{semente}}"`...) e uma chave `_ve` com modelo, licença, arquivo do checkpoint, onde baixar e VRAM esperada. Workflow próprio entra por `VE_COMFYUI_WORKFLOW=arquivo.json`;
- **reprodutibilidade:** o registro de cada rodada grava, além de prompt e semente, o sha256 do workflow, o checkpoint e a versão do servidor. Mesmo trio = mesma imagem;
- **erro claro antes da GPU:** `--conferir` (e o `doctor.sh`) checam o servidor e se o checkpoint do workflow está nele, e dizem onde baixar quando não está.

**Primeiro workflow:** `flux-schnell` (FLUX.1-schnell fp8 em checkpoint único, pesos Apache-2.0, 4 passos, ~12 GB). FLUX.1-dev fica fora: pesos sem uso comercial.

## Ordem

1. **Imagem**: papel `imagem`, um backend local e `/gerar` só para imagem. Validar nos três usos de fundo acima.
   - **1a, feita em 0.13.0:** papel `imagem`, backend `comfyui`, workflow `flux-schnell`, operação `gerar-imagem` (variações por semente, folha de escolha, registro por rodada), checagem no `doctor.sh`, testes contra um servidor ComfyUI falso (`tests/stub/comfyui_servidor.py`).
   - **1b, pendente de GPU:** rodar contra um ComfyUI real, medir tempo e VRAM, ajustar prompt-base e tamanho para os três usos, e só então escrever a skill `/gerar` com os gates. Sem essa validação, as instruções da skill seriam palpite.
2. **Vídeo curto** (depois): papel `video`, image-to-video a partir de imagem aprovada, 3–6 s, 24 ou 30 fps, upscale/interpolação por ffmpeg se o modelo entregar menos.
3. Fora do plano: geração de voz clonada, avatar falante, vídeo longo gerado.

## Consequências

- Mais um papel de modelo mantém a arquitetura (ADR-10) sem tocar nas skills existentes; quem não usa `/gerar` não baixa nada.
- Custo real: GPU com 12–16 GB para imagem com qualidade, 16–24 GB para vídeo; em CPU a imagem leva minutos e o vídeo é inviável. Por isso o ADR fica **proposto** até haver a máquina para validar, como já ocorre com o video matting em GPU.
- Risco de licença: cada backend declara a licença do modelo no `deps()` e no `doctor.sh`; modelos com uso comercial restrito só entram marcados como tal.
