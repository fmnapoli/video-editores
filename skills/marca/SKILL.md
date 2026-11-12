---
name: marca
description: Extrai a identidade visual (cores, fonte, logo) de uma fonte externa — tema de apresentação PPTX/Google Slides, documento DOCX, manual de marca em PDF, pacote de marca (pasta ou zip) ou design tokens — e grava o marca/marca.json que todas as skills leem, com validação de contraste e prancha de aprovação. Use para /marca, "usa a identidade da empresa", "pega as cores desse manual de marca", "aplica o tema dessa apresentação nos vídeos", "configura a marca do cliente".
---

# /marca — identidade visual a partir de uma fonte externa

Siga `${CLAUDE_PLUGIN_ROOT}/docs/convencoes.md`. Contrato do `marca.json` e regras: `${CLAUDE_PLUGIN_ROOT}/docs/adr/2026-11-11-identidade-visual.md`.
Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/extrair_marca.py` (coleta) e `${CLAUDE_PLUGIN_ROOT}/scripts/validar_marca.py` (validação e prancha).

O script coleta candidatos e sugere; quem atribui os papéis é você, pela evidência, e quem aprova é a pessoa, pela prancha. **Nada é renderizado com a marca antes do OK na prancha.**

## Fontes aceitas

| Fonte | O que sai | Confiança |
|---|---|---|
| `.pptx`, `.potx`, `.docx`, `.dotx`, `.xlsx` (Google Slides/Docs: baixar como PPTX/DOCX) | paleta do tema já com papéis (`dk1`, `lt1`, `accent1`…), fonte de título e de corpo, imagens do slide mestre | alta para cores; a fonte vem só como nome |
| `.pdf` (manual de marca) | HEX e RGB citados no texto, com página e linha; fontes embutidas | alta, mas exige leitura: abra as páginas citadas |
| pasta ou `.zip` (pacote de marca) | logos SVG/PNG, fontes TTF/OTF com a família real, tokens JSON, cores dos logos | alta para logo e fonte |
| `.json` (design tokens, DTCG ou `{"value": …}`) | cores com o caminho do token | alta |

Site e Figma ainda não são lidos: peça o manual em PDF, o pacote de marca ou o tema da apresentação.

## Passos

1. **Coleta.** Na raiz do projeto de vídeos:
   ```bash
   uv run --with pillow --with fonttools --with pypdf python "${CLAUDE_PLUGIN_ROOT}/scripts/extrair_marca.py" FONTE --out marca
   ```
   Grava `marca/rascunho.json` (`cores`, `fontes`, `logos`, cada um com `evidencia`, mais `sugestao` e `avisos`). Havendo mais de uma fonte (manual + pacote), rode uma por vez com `--out` diferente e junte na proposta. `--gravar-sugestao` já escreve um primeiro `marca/marca.json` (e, de pacote, copia logo e fontes para `marca/`); nunca sobrescreve um existente.
2. **Proposta.** Leia o rascunho e escreva `marca/marca.json`. Só `cores.fundo`, `cores.acento` e `cores.texto` são obrigatórias.
   ```json
   {"nome": "Exemplo",
    "origem": [{"tipo": "pdf", "ref": "marca/manual.pdf", "data": "2026-11-11"}],
    "cores": {"fundo": "#0B2545", "acento": "#2DD4BF", "texto": "#FFFFFF"},
    "fonte": {"familia": "Exemplo Sans", "arquivos": {"regular": "fontes/ExemploSans-Regular.ttf", "bold": "fontes/ExemploSans-Bold.ttf"}},
    "logo": {"svg": "logo.svg", "png": "logo.png"}}
   ```
   - `fundo`: a cor escura institucional (cartelas, balões, faixas). `acento`: a cor viva que a marca usa para destacar. `texto`: o que se lê sobre o fundo. Em PDF, o papel está na frase ao lado do valor ("cor primária", "apoio"); cite a página ao justificar.
   - Marca de fundo claro: vídeo de tela costuma pedir fundo escuro; proponha a cor escura da paleta como `fundo` e diga isso.
   - Logo para fundo escuro em `logo.svg`/`logo.png` (versão negativa); a de fundo claro em `logo.fundo_claro`.
   - Registre em `origem` de onde cada coisa veio.
3. **Validação e prancha.**
   ```bash
   uv run --with pillow --with fonttools python "${CLAUDE_PLUGIN_ROOT}/scripts/validar_marca.py" marca/marca.json --gravar
   ```
   Erro de contraste: mostre o ajuste proposto pelo validador e pergunte; a cor oficial nunca é trocada em silêncio.
4. **GATE.** Mostre `marca/prancha.png` com um resumo de três linhas (cores e de onde vieram, fonte, logo) e pare. Com o OK, todas as skills passam a ler `marca/marca.json` sozinhas; `"marca": false` no spec ou `--marca nao` volta ao visual padrão do plugin.

## Regras

- **Fonte tipográfica.** O arquivo só entra quando vem do pacote do cliente ou tem licença que permita (ex.: OFL). Nunca baixe fonte proprietária de site. Sem o arquivo, proponha uma substituta livre de desenho parecido, grave em `fonte.substituta` e avise na prancha.
- **Logo.** Só arquivo oficial. Imagem tirada do slide mestre é candidata a conferir; nunca recorte de print, redesenho ou favicon ampliado.
- **Marca de terceiros.** Aplique a marca de quem a pessoa representa ou tem autorização para usar; não monte vídeo que se passe por comunicação oficial de outra organização.
- Cores tiradas de PNG são aproximadas: confirme com o manual ou com o SVG antes de gravar.

## Combinações
- Depois do OK: `/video-docs`, `/video-animado`, `/videoaula`, `/legenda`, `/lettering`, `/checklist` e `/partitura` usam a marca sem parâmetro extra.
- Mais de uma marca no mesmo projeto: um `marca.json` por pasta e `"marca": "<caminho>"` no spec (ou `--marca`, ou `VE_MARCA`).
