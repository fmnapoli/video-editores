"""Base das cenas Manim de uma videoaula redesenhada (/videoaula). Copie para trabalho/<slug>/manim/base.py.

- Paleta e fontes num lugar só (troque pelas cores do aula.json).
- `Timed`: cena com relógio; `at(t)` espera até o instante t relativo ao início da cena.
- `Trecho`: cena ligada a um trecho do vídeo cortado (T0 absoluto); `att(t_abs)` espera até o instante absoluto,
  lido da transcrição remapeada (transcript_corte.txt / .json), palavra por palavra.
- `fim()` desvanece tudo em DUR; a cena dura exatamente o trecho de quadro que substitui.
- Área segura do layout com o círculo do locutor no canto inferior direito: nada com x > 3.4 abaixo de y < -1.3;
  título em `titulo()` já desce o bastante para não bater no chip de capítulo (topo esquerdo).

Render de conferência: manim -ql -t -r 960,540 --fps 30 diagramas.py D1Fluxo -o D1Fluxo.mov
Render final:         manim -qh -t -r 1920,1080 --fps 30 diagramas.py D1Fluxo -o D1Fluxo.mov   (ou render_cenas.sh)
"""
from manim import *

AZUL = "#4B8BBE"; AZUL_CLARO = "#7FB3DB"; AMARELO = "#FFD43B"; VERDE = "#34D399"; VERMELHO = "#F87171"
ROXO = "#A78BFA"; TXT = "#F1F5F9"; SUB = "#94A3B8"; FUNDO = "#0F172A"; PAINEL = "#1B2540"
FONTE = "Inter"; MONO = "JetBrainsMono NF"

# Área segura do layout L2: o círculo do locutor ocupa o canto inferior direito.
# Em unidades do Manim (frame 14.22 x 8): x ∈ [-6.6, 6.6], y ∈ [-4, 4]. Círculo ≈ x>3.6 e y<-1.2.
SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, SAFE_BOTTOM = -6.5, 6.4, 3.2, -3.6
CIRCLE_X, CIRCLE_Y = 3.6, -1.3   # conteúdo abaixo de y<-1.3 deve ficar com x<3.4


def texto(s, size=0.6, cor=TXT, peso=BOLD, font=FONTE):
    return Text(s, font=font, weight=peso, color=cor).scale(size)


def mono(s, size=0.6, cor=TXT):
    return Text(s, font=MONO, color=cor).scale(size)


def caixa(label, cor, w=3.0, h=1.3, size=0.55, fill=0.14, radius=0.25):
    r = RoundedRectangle(corner_radius=radius, width=w, height=h, color=cor, stroke_width=5)
    r.set_fill(cor, opacity=fill)
    t = texto(label, size).move_to(r)
    return VGroup(r, t)


def seta(a, b, cor=TXT, buff=0.15, sw=5):
    return Arrow(a, b, buff=buff, color=cor, stroke_width=sw, max_tip_length_to_length_ratio=0.18)


def titulo(s, size=0.75):
    """Título do diagrama no topo, alinhado à esquerda, abaixo do chip."""
    t = texto(s, size).to_edge(UP, buff=1.35).to_edge(LEFT, buff=0.8)
    return t


class Timed(Scene):
    """Cena com relógio: os passos são agendados em segundos relativos ao início do trecho.
    Use self.at(t) antes de uma animação para esperar até o instante t (se já passou, não espera)."""
    T0 = 0.0        # início do trecho no vídeo cortado (só para referência)
    DUR = 10.0      # duração total da cena

    def setup(self):
        self.clock = 0.0

    def at(self, t):
        if t > self.clock:
            self.wait(t - self.clock)
            self.clock = t

    def go(self, *anims, rt=0.6, **kw):
        self.play(*anims, run_time=rt, **kw)
        self.clock += rt

    def fim(self, fade=0.4):
        """Espera até DUR e desvanece tudo."""
        self.at(self.DUR - fade)
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=fade)
            self.clock += fade


class Trecho(Timed):
    """Cena ligada a um trecho do vídeo cortado: T0 = início absoluto. att(t) espera até o instante absoluto t."""
    def att(self, t_abs):
        self.at(t_abs - self.T0)

    def brick(self, label, cor, w=2.9):
        """Tijolo estilo Lego: retângulo com dois 'pinos' em cima."""
        r = RoundedRectangle(corner_radius=0.12, width=w, height=0.95, color=cor, stroke_width=4).set_fill(cor, opacity=0.18)
        studs = VGroup(*[RoundedRectangle(corner_radius=0.06, width=0.5, height=0.22, color=cor, stroke_width=3).set_fill(cor, opacity=0.35)
                         for _ in range(2)]).arrange(RIGHT, buff=0.5).next_to(r, UP, buff=0)
        t = texto(label, 0.42).move_to(r)
        return VGroup(r, studs, t)
