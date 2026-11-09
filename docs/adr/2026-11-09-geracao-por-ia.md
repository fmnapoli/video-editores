# ADR-15 — Geração de imagem e vídeo por IA no plugin

**Data:** 2026-11-09 · **Estado:** proposto (não implementado) · **Alvo:** 0.9.0 ou posterior · **Depende de:** máquina com GPU (pendência do ADR-10)

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
- **locais primeiro** (ADR-05): modelos abertos com licença permissiva ou de uso livre, executados via `diffusers`; a lista concreta (por exemplo FLUX.1-schnell para imagem; LTX-Video, Wan ou CogVideoX para vídeo) é decidida **na implementação**, conferindo licença e requisitos de memória na data, porque mudam a cada poucos meses;
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

## Ordem

1. **Imagem** (0.9.0): papel `imagem`, um backend local e `/gerar` só para imagem. Validar nos três usos de fundo acima.
2. **Vídeo curto** (depois): papel `video`, image-to-video a partir de imagem aprovada, 3–6 s, 24 ou 30 fps, upscale/interpolação por ffmpeg se o modelo entregar menos.
3. Fora do plano: geração de voz clonada, avatar falante, vídeo longo gerado.

## Consequências

- Mais um papel de modelo mantém a arquitetura (ADR-10) sem tocar nas skills existentes; quem não usa `/gerar` não baixa nada.
- Custo real: GPU com 12–16 GB para imagem com qualidade, 16–24 GB para vídeo; em CPU a imagem leva minutos e o vídeo é inviável. Por isso o ADR fica **proposto** até haver a máquina para validar, como já ocorre com o video matting em GPU.
- Risco de licença: cada backend declara a licença do modelo no `deps()` e no `doctor.sh`; modelos com uso comercial restrito só entram marcados como tal.
