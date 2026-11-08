"""Exemplo de diagrama sincronizado com a fala (/videoaula). Uma classe por trecho de quadro; T0/DUR vêm do
aula.json (diagramas[]), os instantes de `att()` vêm da transcrição remapeada (transcript_corte.txt).
Copie para trabalho/<slug>/manim/diagramas.py e escreva uma classe por diagrama.
"""
from manim import *
from base import *


class D1Fluxo(Trecho):
    T0, DUR = 25.1, 28.2                      # início e duração do trecho no vídeo cortado

    def construct(self):
        tit = titulo("O que é um programa?")
        a = caixa("Entrada de dados", AZUL).move_to(LEFT * 4.3 + UP * 1.5)
        b = caixa("Processamento", ROXO, 3.3).move_to(LEFT * 0.9 + UP * 1.5)
        c = caixa("Saída", VERDE, 2.6).move_to(RIGHT * 2.4 + UP * 1.5)
        self.att(25.3); self.go(FadeIn(tit, shift=DOWN * 0.2), rt=0.4)         # "entrada"[25.5]
        self.att(25.5); self.go(FadeIn(a, shift=RIGHT * 0.3), rt=0.5)
        self.att(26.6); self.go(GrowArrow(seta(a.get_right(), b.get_left())), FadeIn(b, shift=RIGHT * 0.3), rt=0.6)   # "processamento"[26.8]
        self.att(27.8); self.go(GrowArrow(seta(b.get_right(), c.get_left())), FadeIn(c, shift=RIGHT * 0.3), rt=0.6)   # "saída"[28.0]
        n2 = texto("2", 1.1, AMARELO).move_to(a.get_center() + DOWN * 2.0)
        op = texto("× 2", 1.1, AMARELO).move_to(b.get_center() + DOWN * 2.0)
        n4 = texto("4", 1.1, AMARELO).move_to(c.get_center() + DOWN * 2.0)
        self.att(33.0); self.go(Write(n2), rt=0.4)
        self.att(35.5); self.go(GrowArrow(seta(n2.get_right(), op.get_left(), SUB, 0.3, 4)), FadeIn(op), rt=0.5)
        self.att(38.4); self.go(GrowArrow(seta(op.get_right(), n4.get_left(), SUB, 0.3, 4)), rt=0.3)
        self.att(38.7); self.go(Write(n4), rt=0.4)
        self.fim()                                # desvanece em T0 + DUR
