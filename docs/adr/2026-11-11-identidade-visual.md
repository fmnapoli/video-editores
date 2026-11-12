# ADR-17 — Identidade visual como contrato único (`marca.json`) e extração a partir de fonte externa

**Data:** 2026-11-11 · **Estado:** proposto (não implementado) · **Alvo:** 0.11.0 (contrato) e 0.12.0 (extração)

## Contexto

Cada skill guarda a identidade de um jeito:

| Skill | Onde a identidade mora hoje |
|---|---|
| `/video-docs` | constantes no `build.py` (`ACCENT`, `INK`, `FONT`, gradiente da cartela) |
| `/videoaula` | `cores`, `fonte`, `fonte_dir` no `aula.json`, lidos pelo `identidade.py` |
| `/video-animado` | constantes no `cena_base.py` copiado para o projeto, mais uma pasta `marca/` montada à mão |
| `/partitura`, `/lettering`, `/legenda`, `/checklist` | parâmetros próprios (`--font`, `--destaque`, `--fundo`) |

O custo apareceu no curso de produto (nov/2026): para usar fonte, cores, logo e encerramento do cliente no
`/video-docs`, o projeto copiou o `build.py` e editou as constantes. A cópia divergiu em dias: ganhou faixa do
navegador e tarja fixa que o plugin não tinha (trazidas de volta na 0.10.0) e ficou sem o glossário de pronúncia
que o plugin ganhou. O mesmo projeto ainda repetiu a paleta no `cena_base.py` do `/video-animado` e nos
parâmetros do `/legenda`.

Junto veio o pedido: aplicar uma identidade **a partir de uma fonte externa** (manual de marca, site, tema de
apresentação). Sem um contrato comum, a extração não teria onde gravar o resultado.

## Decisão proposta

### 1. `marca/marca.json`: um contrato, lido por todas as skills

```jsonc
{
 "nome": "Cliente",
 "origem": [{"tipo": "pdf", "ref": "marca/manual-de-marca.pdf", "data": "2026-11-11"}],
 "cores": {                       // papéis, não nomes de cor; HEX
  "fundo": "#002233",             // base de cartelas, balões, faixas
  "fundo2": "#0B1220",            // segunda cor do gradiente (opcional; sem ela, fundo chapado)
  "acento": "#00DBFF",            // caixas de destaque, barras, palavra destacada da legenda
  "secundario": "#A78BFA",        // segunda série em diagramas (opcional)
  "texto": "#FFFFFF",
  "texto2": "#94A3B8"
 },
 "fonte": {"familia": "Cliente Sans", "arquivos": {"regular": "fontes/ClienteSans-Regular.ttf", "bold": "fontes/ClienteSans-Bold.ttf"},
           "substituta": null},   // preenchida quando a oficial não pôde ser obtida (ver "Fonte")
 "logo": {"svg": "logo.svg", "png": "logo.png", "fundo_claro": "logo-escuro.svg"},
 "fundos": {"cartela": "bg_azul.png", "encerramento": "bg_azul.png"},   // opcionais; sem eles, gradiente das cores
 "legenda": {"destaque": "acento", "caixa": true},
 "contraste": {"texto_fundo": 15.9, "acento_fundo": 9.8, "ajustes": []}  // gravado pelo validador
}
```

Caminhos relativos à pasta do `marca.json`. Só `cores.fundo`, `cores.acento` e `cores.texto` são obrigatórios;
o resto cai no padrão atual de cada skill.

**Resolução**, na ordem: `"marca": "<caminho>"` no spec da skill (ou `--marca`), `VE_MARCA`, `marca/marca.json`
na raiz do projeto, e por fim o padrão embutido (o visual de hoje). Sem `marca.json`, nada muda: é o critério
de compatibilidade e o teste de regressão.

**Leitura** por um módulo do núcleo, `video_editores/nucleo/marca.py`: carrega, valida, resolve caminhos,
converte para o que cada motor quer (ASS `&HBBGGRR&`, tupla RGB do Pillow, HEX do Manim, `FontName` do libass
com a fonte registrada por `fontsdir`) e devolve o padrão quando não há arquivo. Nenhuma skill reimplementa
conversão de cor.

**Consumo**, por skill:
- `/video-docs`: `ACCENT`, `INK`, fonte da legenda e dos balões, fundo da cartela, logo da faixa (`chrome.logo`
  passa a vir da marca), e uma tela de encerramento com o logo (hoje só existe na cópia do projeto).
- `/video-animado`: o `cena_base.py` lê a marca em vez de constantes editadas à mão; `fundos.cartela` vira o `BG_PADRAO`.
- `/videoaula`: `identidade.py` aceita a marca como padrão de `cores`/`fonte_dir`; o `aula.json` continua
  podendo sobrescrever (papéis `destaque`, `fundo_centro`, `fundo_borda` mapeados).
- `/legenda`, `/lettering`, `/checklist`, `/partitura`: os parâmetros de fonte e cor passam a ter a marca como padrão.

### 2. `/marca`: extrair de uma fonte externa (com gate)

Skill nova com um script por tipo de fonte e um validador comum. Sempre produz um **rascunho** e para.

| Fonte | Como lê | Confiabilidade |
|---|---|---|
| Tema de PPTX/DOCX/Google Slides | `theme1.xml` (`a:clrScheme`, `a:fontScheme`), logo no slide mestre | alta: a paleta já vem com papéis |
| Manual de marca em PDF | texto (HEX/RGB/CMYK perto de nomes de cor, nome da tipografia), imagens das páginas de logo | alta, mas exige leitura: o agente interpreta, o script só coleta candidatos |
| Pacote de marca (pasta/zip) | inventário de SVG/PNG/TTF/ASE, cores dominantes dos logos | alta para logo e fonte |
| Site | variáveis CSS, cor computada de botão/link/cabeçalho, `font-family`, `<link rel=icon>`, logo do cabeçalho (via navegador headless já usado pelo usuário) | média: dezenas de cores; papel decidido por uso (frequência e área), sempre confirmado |
| Figma / tokens JSON | tokens exportados | alta, quando há acesso |

Fluxo:
1. **Coleta** (`extrair_marca.py <fonte>`): grava `marca/rascunho.json` com candidatos e a evidência de cada um
   (página do PDF, seletor CSS, slot do tema).
2. **Proposta**: o agente atribui os papéis, justificando pela evidência, e escreve o `marca.json`.
3. **Validação** (`validar_marca.py`): contraste WCAG de texto sobre fundo (≥ 7), acento sobre fundo (≥ 3) e
   acento sobre gravação de tela clara; fonte instalável e com os glifos de pt-BR; logo vetorial ou PNG com
   altura ≥ 400 px. Quando um contraste falha, propõe o ajuste mínimo de luminosidade e registra em
   `contraste.ajustes`; a cor oficial nunca é trocada em silêncio.
4. **GATE**: prancha `marca/prancha.png` com cartela, balão com destaque, legenda sobre um quadro claro e um
   escuro, faixa do navegador, lower third e encerramento. Nada é renderizado em lote antes do OK.

### Regras

- **Fonte tipográfica.** O nome se extrai; o arquivo só entra quando vem do pacote do cliente ou de fonte com
  licença que permita (ex.: Google Fonts). Fonte proprietária servida por um site não é baixada. Sem o arquivo,
  o validador propõe uma substituta livre de métrica parecida, grava em `fonte.substituta` e a prancha mostra o aviso.
- **Logo.** Só arquivo oficial fornecido ou publicado como pacote de imprensa/marca. Nunca recorte de print,
  nunca redesenho, nunca favicon ampliado.
- **Marcas de terceiros.** A skill aplica a marca de quem o usuário representa ou tem autorização para usar;
  não monta vídeo que se passe por comunicação oficial de outra organização.
- **Proveniência.** `origem` registra de onde cada marca veio e quando; o relatório de edição cita o `marca.json` usado.

## Alternativas consideradas

- **Só documentar "copie o `build.py` e troque as constantes"**: é o que existe, e gerou o fork divergente.
- **Tema por skill, sem contrato comum**: resolve o `/video-docs` e mantém a paleta repetida em quatro lugares.
- **Adotar um formato de design tokens (W3C DTCG)**: mais geral do que o plugin precisa (não há espaçamento,
  raio, estados); o extrator pode **ler** tokens DTCG, mas o contrato interno fica com seis papéis de cor.
- **Extração totalmente automática de site, sem gate**: erra o papel das cores com frequência e não resolve fonte nem logo.

## Consequências

- O montador copiado daquele projeto deixa de ser necessário: `marca/marca.json` com a identidade do cliente + o
  `build.py` do plugin. É o primeiro caso real e o critério de aceite da fase 1 (mesmo vídeo, quadro a quadro
  equivalente ao da cópia).
- Um ponto a mais de validação (contraste, glifos) que hoje é feito de olho.
- Custo: tocar em seis skills. Mitigado pela regra "sem `marca.json`, saída idêntica à de hoje", coberta por teste.

## Fases

1. **0.11.0 — contrato.** `nucleo/marca.py`, `validar_marca.py` e prancha; `/video-docs` e `/video-animado`
   lendo a marca (inclui tela de encerramento no `/video-docs`); identidade do cliente convertida à mão como caso de teste.
2. **0.11.x — demais skills.** `/videoaula`, `/legenda`, `/lettering`, `/checklist`, `/partitura`.
3. **0.12.0 — extração.** Skill `/marca` com tema de PPTX/Slides, PDF e pacote de marca. Site e Figma só
   quando um projeto pedir.

## Em aberto

- Variante clara/escura da mesma marca (dois `marca.json` ou um com `modos`)? Proposta: dois arquivos, até aparecer o caso.
- Trilha/vinheta sonora da marca entra no contrato? Proposta: não agora; `/trilha` e `/efeitos` seguem com parâmetros próprios.
