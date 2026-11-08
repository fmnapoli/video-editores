# Revisão de coerência da narração contra o código

Por que: em out/2026, dois dos roteiros gerados a partir das gravações diziam o oposto do
que o produto faz (Downgrade era "valor final" quando é "quantidade a retirar"; Clone
"exigia mesma release" quando não exige). O apresentador improvisou e errou; a
transcrição herdou o erro; o roteiro também. Só a leitura do código pegou.

## Quando

Depois de escrever os roteiros e **antes** de mostrar o lote. De novo se o código mudar
antes de publicar.

## Como

1. Liste cada afirmação factual dos roteiros (regra de validação, limite, efeito,
   pré-requisito, quem vê a ação, o que reinicia, nomes de campos e opções).
2. Para cada produto, identifique a fonte da verdade: modelos/CRDs e validações do
   backend, handlers e formulários, catálogos de ações/permissões, webhooks de
   validação, guias de usuário no repo, textos de tela (front, i18n, API).
3. Disparar verificadores em paralelo (um por grupo de ações), cada um devolvendo, por
   afirmação: **Veredito** (Confirmado / Parcial / Incorreto / Não encontrado),
   **Evidência** (arquivo:linha e trecho), **Como deveria ser dito**, e "Observações
   extras" (o que a gravação omite: travas, efeitos colaterais, perfis de acesso).
4. Consolidar em `revisao-coerencia.md`: tabela por vídeo (afirmações, confirmadas,
   corrigidas, o que muda na narração), detalhe por ação com as citações, ressalvas
   fora do vídeo (ações só em DEV, publicação retida), e o que não foi encontrado.
5. Reescrever narração, TTS e legenda **pelo código**. Quando a tela do bruto contradiz
   o código, narra-se o código e a divergência fica registrada.
6. Acrescentar ao cabeçalho de cada roteiro uma seção "Revisão de coerência" com o que
   mudou; o montador leva isso para o roteiro final (campo `revisao` do spec).

## Sinais de alerta no bruto

- "acho que", "provavelmente", "pelo jeito", "não vai dar certo porque…"
- Valores informados num formulário que "coincidem" com o resultado (1000 → 500).
- Afirmações sobre quem pode usar a ação (quase sempre é controle de permissão no backend).
- "Reinicia / não reinicia", "só sobe para cima", "mesma release": checar no webhook.
