# Tutorial: do bruto ao reels pronto

Exemplo completo com um vídeo falado de ~1 minuto gravado no celular (vertical). Os comandos abaixo são pedidos em linguagem natural ao Claude Code; ele escolhe o skill e roda os scripts. Também dá para chamar os skills diretamente (`/video-editores:corte`).

## 0. Prepare o projeto

```bash
mkdir -p ~/videos/dicas-k8s/{originais,trabalho,saida,legendas}
cp ~/Downloads/IMG_1234.MOV ~/videos/dicas-k8s/originais/bruto.mov
cd ~/videos/dicas-k8s && claude
```

Estrutura e regras: [convencoes.md](convencoes.md). O bruto em `originais/` nunca é alterado.

## 1. Tire as tomadas repetidas — `/tomada`

> "Usa o /tomada no originais/bruto.mov. Vocabulário: Kubernetes, kubectl, ArgoCD, GitOps."

O Claude:
1. transcreve com faster-whisper (`medium` + o vocabulário);
2. agrupa frases repetidas e mostra quais tentativas vai descartar;
3. **para e pede seu OK**;
4. gera `trabalho/bruto_tomada.mp4`.

Se ele agrupou frases que não eram repetição, peça "usa threshold 0.75". Se deixou passar repetição, "usa 0.5".

## 2. Corte seco — `/corte`

> "Agora /corte no resultado, ritmo normal."

auto-editor remove silêncios com margem de 0,15 s. O Claude informa a duração antes e depois. Mais de 45% removido é sinal de alerta: ele avisa e oferece refazer.

## 3. Gancho — `/ganchos`

> "Me dá ganchos para esse vídeo, público: devs que estão começando em Kubernetes."

Você recebe 5 ganchos com padrões diferentes, cada um com o jeito de executar:
- reaproveitar um trecho que já está gravado (ele reordena o início);
- texto na tela (vira item do `/lettering`);
- regravar (ele escreve a fala).

## 4. Textos na tela — `/lettering`

> "Coloca o gancho 2 como título com pop nos primeiros 2,5 s e um lower third com meu nome e cargo dos 4 aos 8 s."

Ele escreve `trabalho/textos.json`, gera o `.ass` e queima. Detalhes do formato: [scripts.md](scripts.md#lettering_asspy).

## 5. Legenda — `/legenda`

> "Legenda estilo reels, 3 palavras por bloco."

Ele reaproveita a transcrição, **mostra as correções** de termos técnicos (o Whisper costuma errar "kubectl", "ArgoCD") e só então queima. O `.srt` vai para `legendas/`.

## 6. Música e efeitos — `/trilha` e `/efeitos`

> "Coloca a trilha musica.mp3 com ducking, e whoosh nas trocas de plano."

A música abaixa sozinha quando você fala (sidechain). O loudness final fica em -14 LUFS, o alvo das redes. Os whooshes são sintetizados pelo ffmpeg, sem baixar nada.

## 7. Revisão — `/prova`

> "/prova no vídeo final."

Você recebe a folha de contato (12 frames), um preview leve em 480p para ver no celular e o relatório técnico. O Claude olha os frames e lista problemas: legenda sobre o rosto, texto cortado, dado sensível na tela.

## 8. Entrega

Quando aprovar, o Claude copia para `saida/dicas-k8s.mp4`. O `.srt` fica em `legendas/`, separado.

---

## Variações

### Vídeo de documentação (gravação de tela)
Use o `/video-docs`, que tem fluxo próprio com três gates (inventário → roteiros → piloto), narração sintetizada e destaques. Guia: [video-docs-LEIAME.md](video-docs-LEIAME.md).

> "Transforma as gravações em originais/ em vídeos de documentação, um por ação."

### Editar igual a uma referência
> "/referencia nesse reels: <link>. Depois aplica o estilo no meu vídeo."

Ele gera `referencia.md` com ritmo de cortes, estilo de legenda e estrutura, e usa esses parâmetros nos passos acima.

### Efeitos visuais
- Texto atrás de você: `/texto-atras` (use trechos de 1–4 s).
- Trocar o fundo: `/tela-verde`.
- Logo ou título em 3D: `/3d`.
- Diagrama animado: `/animacao`.

Esses passos vêm **antes** do `/lettering` e da `/legenda` (ordem em [convencoes.md](convencoes.md#ordem-recomendada)).
