---
name: video-animado
description: Produz vídeo de documentação ou de apresentação 100% animado por código (Manim), sem gravação de tela — roteiro por cena, narração sintetizada que dita a duração de cada animação, legenda queimada, identidade visual da marca e transições sem tela preta. Use para /video-animado, "vídeo explicativo para a diretoria", "animação em vez de gravação", "refaz a demo como animação", "vídeo institucional didático", "explica um conceito técnico para gestores".
---

# /video-animado — vídeo inteiro em animação por código

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md` (pastas, nomes de saída, loudness, privacidade). Dependências: `${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh` (Manim é obrigatório aqui; se `uv tool install manim` falhar, veja `docs/troubleshooting.md`).

Diferença para o `/video-docs`: não há bruto. Cada cena é uma `Scene` do Manim cuja duração é **a da narração** daquela cena, mais um respiro antes e depois. Nada de tela preta: as cenas abrem e fecham sobre o mesmo fundo, e a troca de fundo é um fade entre duas imagens. Público típico: gestores, com analogias do dia a dia e zero terminal.

Scripts desta skill em `${CLAUDE_PLUGIN_ROOT}/skills/video-animado/scripts/`; modelos em `templates/`. Validado em nov/2026 num vídeo de 24 cenas e 4 min 26 s para gestores (VMs → containers → Kubernetes → operators).

## Passos

1. **Projeto e identidade.** Pastas da convenção (`originais/` fica vazia, `trabalho/<slug>/`, `saida/`, `legendas/`) mais `marca/` com o pacote oficial do cliente: fonte TTF instalada (`fc-cache -f ~/.local/share/fonts`), logo oficial em SVG (o Manim lê com `SVGMobject`), cores e grafismo. Fundos em gradiente vão para PNG (Pillow), nunca para o `Scene.background_color`; gradiente só no fundo, e fraco o bastante para o texto branco continuar legível no canto. Grafismo da marca (forma do símbolo) como contorno fino de baixa opacidade, nunca como ícone preenchido.
2. **Roteiro (GATE 1).** Um `.md` com, por cena: título na tela, narração, texto na tela e descrição da animação, mais a duração estimada (2,6 palavras/s) e as decisões abertas (duração, posição do logo, cortes possíveis). Metáfora única atravessando o vídeo (prédio, sala, síndico). Mostrar e **parar**.
3. **Narração primeiro.** `cenas/<slug>.json` com `id`, `classe`, `titulo`, `narracao` (ou `duracao` para cena muda), e o glossário de pronúncia:
   ```bash
   uv run --with edge-tts python "${CLAUDE_PLUGIN_ROOT}/skills/video-animado/scripts/tts_cenas.py" cenas/<slug>.json --glossario glossario.json
   ```
   Gera `trabalho/<slug>/tts/<id>.mp3`, `.words.json` e `tempos.json` (fala, total, lead). Antes do lote, ouça os termos do domínio: `testar_pronuncia.py` do video-docs com a frase que concentra os termos. Mesmo a voz multilíngue erra alguns ("Operator", "Orchestrator"): o glossário troca só a fala, a legenda mantém a grafia.
4. **Cenas em Manim.** Copie `templates/cena_base.py` para `trabalho/<slug>/video.py` e escreva uma classe por cena herdando de `Base`: `abre()` (título com fade e, se houver, fade do fundo anterior), `q(0.4)` (espera até 40 % da fala), `p(anim, rt=…)` (play que contabiliza o tempo), `fim()` (desvanece tudo menos fundo, grafismo e logo). Conteúdo acima da faixa da legenda (y > −2,3 em unidades do Manim, com legenda de 2 linhas em 1080p). Teste em baixa:
   ```bash
   manim -ql -r 960,540 --fps 30 video.py <Classe> -o <ID>.mp4
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/video-animado/scripts/folha_cenas.py" cenas/<slug>.json media/videos/video/540p30 --fracao 0.9
   ```
   Olhe a folha com Read: nada pode encostar na legenda; a folha a 0,5 mostra o meio da animação, a 0,9 o estado final.
5. **Piloto (GATE 2).** Renderize em 1080p só o ato mais denso, monte e passe pelo `/prova`:
   ```bash
   manim -qh -r 1920,1080 --fps 30 video.py <Classe> -o <ID>.mp4
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/video-animado/scripts/montar_cenas.py" cenas/<slug>.json media/videos/video/1080p30 --cenas B1,B2,B3 --saida saida/piloto.mp4 --fonte "<Fonte da marca>"
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/proof.sh" saida/piloto.mp4 12
   ```
   Mostre `.proof.jpg`, `.preview.mp4` e um teste de voz com os termos; **pare**.
6. **Lote.** Todas as cenas em 1080p (em segundo plano: ~30 s a 1 min por cena), `montar_cenas.py` sem `--cenas`, `/prova`, folhas a 0,55 e 0,92, mais quadros nas trocas de fundo e no último quadro (tem de terminar na vinheta, nunca em preto). Entregue `saida/<slug>.mp4`, `legendas/<slug>.srt`, `roteiros/` (design aprovado e roteiro final gerado por `--roteiro`), `README.md` do projeto com o comando de regenerar, e o resumo de 8–12 linhas para o time.

## Parâmetros

| Onde | Padrão | Quando mudar |
|---|---|---|
| `tts_cenas.py --lead/--tail` | 0,6 s / 0,8 s | mais respiro entre cenas = subir o tail (o `fim()` usa os últimos 0,45 s para o fade) |
| `montar_cenas.py --fonte` | DejaVu Sans Bold | a fonte da marca, se instalada (libass acha pelo fontconfig) |
| `--tamanho` / `--margem` | 15 / 22 (escala 288 = ~56 px e 82 px em 1080p) | legenda maior exige subir o conteúdo das cenas |
| `--loudness` | −16 LUFS | −14 para redes |
| `Base.BG_ANTES` | nenhum | cena que abre um ato com fundo diferente do anterior |
| `fim(fade=0.45)` | 0,45 s | vinheta final sobrescreve `fim()` para terminar no logo |

## Regras

- Narração antes de animar: o tempo da cena vem do áudio, nunca o contrário; `fit`/aceleração não existem aqui.
- Marque os instantes por fração da fala (`q()`), não por segundo: o texto muda no gate e os tempos se ajustam sozinhos.
- Texto na tela e legenda com a grafia normal; pronúncia só no glossário. Depois de montar, confira o `.srt`: nenhuma grafia fonética pode vazar para a legenda.
- Transição = fade do conteúdo sobre o fundo fixo. Nunca `fade=out` para preto, nunca cartela preta entre atos.
- Logo oficial sem redesenhar, posição fixa (canto superior esquerdo); centralizado só na vinheta final. Produtos de terceiros só como texto. Sem fotos, salvo pedido.
- Números na narração ("menos de 3 minutos", "15 indicadores") vêm de medição real do sistema ou do vídeo técnico anterior, com a fonte anotada no roteiro.
- `-ql` antes de `-qh`, sempre; o render em 1080p vai para segundo plano.
- Nada é "pronto" sem o `/prova`: folha de contato, preview, `.proof.txt` com −16 LUFS e 48 kHz.
