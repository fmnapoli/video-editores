"""Cartelas da videoaula: separadores de capítulo (CAP=N no ambiente), overlay da abertura (título + checklist que entra
conforme a fala) e overlay do encerramento (checklist marcado + próxima aula). Tudo com fundo transparente (-t); o
montador compõe sobre o fundo. Lê `aula.json` (capitulos, titulo, kicker, abertura.itens_t, encerramento.proxima).

Render: CAP=1 manim -qh -t -r 1920,1080 --fps 30 cartelas.py Separador -o Separador1.mov
        manim -qh -t -r 1920,1080 --fps 30 cartelas.py Abertura -o Abertura.mov
"""
import json, os
from manim import *
from base import *

AULA = json.load(open(os.environ.get("AULA_JSON", "../aula.json"), encoding="utf-8"))
CAPITULOS = [c["titulo"] for c in AULA["capitulos"]]


class Separador(Scene):
    """Cartela de 2,6 s: número grande + título, barra que cresce. Render opaco sobre FUNDO (o fundo PNG entra na composição)."""
    N = int(os.environ.get("CAP") or 1)

    def construct(self):
        n = self.N; nome = CAPITULOS[n - 1]
        num = texto(f"{n:02d}", 2.6, AMARELO, font=FONTE).move_to(LEFT * 3.2 + UP * 0.3)
        barra = Line(LEFT * 1.3, LEFT * 1.3 + DOWN * 2.2, color=AZUL, stroke_width=8).move_to(LEFT * 1.3 + UP * 0.3)
        cap = texto("CAPÍTULO", 0.42, SUB).next_to(barra, RIGHT, buff=0.6).align_to(barra, UP).shift(DOWN * 0.25)
        tit = texto(nome, 0.95, TXT).next_to(cap, DOWN, buff=0.35).align_to(cap, LEFT)
        grupo = VGroup(num, barra, cap, tit).move_to(ORIGIN)
        self.play(FadeIn(num, shift=RIGHT * 0.6), run_time=0.45)
        self.play(GrowFromEdge(barra, UP), FadeIn(cap, shift=UP * 0.2), run_time=0.4)
        self.play(FadeIn(tit, shift=UP * 0.3), run_time=0.45)
        self.wait(1.0)
        self.play(FadeOut(grupo, shift=UP * 0.4), run_time=0.35)


class Abertura(Timed):
    """Overlay da abertura: título à esquerda e checklist que entra conforme a fala. Tempos em tempos.json."""
    def construct(self):
        t = AULA["abertura"]            # {"dur": fim do overlay, "titulo_t": instante do título, "itens_t": [t por capítulo]}
        self.DUR = t["dur"]
        kicker = texto(AULA.get("kicker", "AULA"), 0.42, AMARELO).move_to(LEFT * 4.9 + UP * 3.0, aligned_edge=LEFT)
        linhas = AULA["titulo"].split("\n") if "\n" in AULA["titulo"] else AULA["titulo"].rsplit(" ", 1)
        l1 = texto(linhas[0], 1.25, TXT).next_to(kicker, DOWN, buff=0.25, aligned_edge=LEFT)
        l2 = texto(linhas[1] if len(linhas) > 1 else "", 1.25, AZUL).next_to(l1, DOWN, buff=0.1, aligned_edge=LEFT)
        self.at(t.get("titulo_t", 0.4))
        self.go(FadeIn(kicker, shift=UP * 0.2), rt=0.3)
        self.go(FadeIn(l1, shift=UP * 0.3), rt=0.5)
        self.go(FadeIn(l2, shift=UP * 0.3), rt=0.5)
        itens = VGroup()
        y0 = l2.get_bottom()[1] - 0.75
        for i, nome in enumerate(CAPITULOS):
            box = RoundedRectangle(corner_radius=0.08, width=0.42, height=0.42, color=AZUL, stroke_width=3)
            lab = texto(nome, 0.46, TXT, peso=SEMIBOLD)
            row = VGroup(box, lab).arrange(RIGHT, buff=0.35).move_to(LEFT * 4.9 + UP * (y0 - i * 0.68), aligned_edge=LEFT)
            itens.add(row)
        for i, row in enumerate(itens):
            self.at(t["itens_t"][i])
            self.go(FadeIn(row, shift=RIGHT * 0.3), rt=0.35)
        self.fim(0.5)


class Encerramento(Timed):
    """Overlay do encerramento: checklist completo marcado + 'Próxima aula'."""
    def construct(self):
        t = AULA["encerramento"]      # {"dur": duração do trecho final, "inicio_t": entrada do checklist, "proxima_t": "próxima aula", "proxima": texto}
        self.DUR = t["dur"]
        kicker = texto("NESTA AULA", 0.42, AMARELO).move_to(LEFT * 4.9 + UP * 3.0, aligned_edge=LEFT)
        itens = VGroup()
        for i, nome in enumerate(CAPITULOS):
            box = RoundedRectangle(corner_radius=0.08, width=0.42, height=0.42, color=AZUL, stroke_width=3)
            box.set_fill(AZUL, opacity=0.25)
            check = VMobject(color=VERDE, stroke_width=5).set_points_as_corners([LEFT * 0.1 + DOWN * 0.0, LEFT * 0.02 + DOWN * 0.1, RIGHT * 0.13 + UP * 0.1]).move_to(box)
            lab = texto(nome, 0.46, TXT)
            row = VGroup(VGroup(box, check), lab).arrange(RIGHT, buff=0.35).move_to(LEFT * 4.9 + UP * (2.2 - i * 0.68), aligned_edge=LEFT)
            itens.add(row)
        prox = texto(t.get("proxima", "Até a próxima aula"), 0.5, SUB).move_to(LEFT * 4.9 + DOWN * 2.6, aligned_edge=LEFT)
        self.at(t.get("inicio_t", 0.3))
        self.go(FadeIn(kicker, shift=UP * 0.2), rt=0.3)
        for row in itens:
            self.go(FadeIn(row, shift=RIGHT * 0.3), rt=0.22)
        self.at(t.get("proxima_t", self.DUR - 2.0))
        self.go(FadeIn(prox, shift=UP * 0.2), rt=0.4)
        self.at(self.DUR)
