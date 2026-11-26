# Glossário: os termos de edição e onde cada um mora no plugin

Para quem não edita e quer saber pedir. Cada termo com o que significa e a skill que faz.

| Termo | O que é | No plugin |
|---|---|---|
| **Quadro** (frame) | Uma das imagens paradas que, mostradas depressa (30 por segundo), viram movimento | toda saída é fechada no grid de quadros ([convenções](convencoes.md)) |
| **Quadro-chave** (keyframe) | O ponto em que você diz "aqui começa" e "aqui termina"; o computador calcula o meio | `/animacao`, `/video-animado` |
| **Easing** | O jeito de acelerar e frear entre dois quadros-chave; é o que separa movimento de robô de movimento com vida | `/animacao` (tabela de `rate_func`), `anim: pop` do `/lettering` |
| **Renderizar** | Transformar a descrição da cena (código) no arquivo de vídeo | Manim, Blender, Chrome sem janela (`/cena-web`) e ffmpeg, conforme a skill |
| **Transcrição** | O texto da fala com o instante de cada palavra; é por ela que o corte cai entre palavras | `/tomada`, `/legenda`, `/destaques` (`transcribe.py`) |
| **EDL** (lista de cortes) | A lista de trechos que ficam, com início e fim; o vídeo é montado a partir dela | `/tomada` (`.takes.json`), `/corte` (`--export`), `/videoaula` |
| **Jump cut** | O salto que aparece quando se tira um pedaço do meio de uma fala gravada no mesmo enquadramento | `/camera` troca o plano em cada corte para o salto virar mudança de enquadramento |
| **Punch-in** | Zoom curto e rápido numa palavra, para dar ênfase | `/camera` (`--punches`) |
| **Recorte** (matte) | Separar a pessoa do fundo, sem tela verde | `/texto-atras`, `/tela-verde`, `/videoaula` |
| **Rastreamento** (tracking) | Calcular, quadro a quadro, onde um objeto está, para um texto andar junto com ele | `/rastrear` |
| **OCR** | Ler o texto que está numa imagem e saber onde cada palavra fica | `/ler-tela` |
| **B-roll** | Imagem de apoio que cobre a fala quando não há o que mostrar | o próprio bruto, `/animacao`, `/lettering`; `/banco` (opcional) |
| **Ducking** | A música abaixa sozinha quando há fala e volta quando a fala para | `/trilha` |
| **Loudness** (LUFS) | O volume percebido do vídeo inteiro, medido e ajustado ao padrão da plataforma | `/prova`, `normalizar_audio.py` (−14 LUFS redes, −16 documentação) |
| **Prova** | Olhar o vídeo pronto antes de entregar: folha de quadros, medição do áudio e conferências automáticas | `/prova` |
