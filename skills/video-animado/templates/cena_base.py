"""Modelo de cenas do /video-animado (Manim Community). Copie para trabalho/<slug>/video.py e adapte.

Cada cena dura exatamente o tempo da narração (tempos.json do tts_cenas.py). As animações marcam os
instantes por fração da fala (`q(0.5)` = metade), e `fim()` desvanece o conteúdo sobre o fundo fixo,
para o corte entre cenas não dar salto. Troca de fundo entre atos é um fade do fundo anterior
(`BG_ANTES`), nunca preto.

Render: manim -ql -r 960,540 --fps 30 video.py Exemplo -o EX.mp4      (conferência)
        manim -qh -r 1920,1080 --fps 30 video.py Exemplo -o EX.mp4    (final)
"""
import json

import numpy as np
from manim import (DOWN, LEFT, UL, UP, Create, FadeIn, FadeOut, Group, ImageMobject, Line, RoundedRectangle, Scene,
                   SVGMobject, Text, config)

# --- identidade (troque pelos valores da marca: fonte instalada, 1 cor de destaque, 1 secundária, texto branco)
FONT = "DejaVu Sans"                 # fonte instalada no sistema (fc-list)
DESTAQUE, SECUNDARIO, TEXTO = "#38BDF8", "#A78BFA", "#FFFFFF"
ESCURO = "#0F172A"
BG_PADRAO = "anim/bg_azul.png"       # PNG 1920x1080 com o gradiente (gradiente só no fundo)
LOGO = "anim/logo.svg"               # logo oficial, sem redesenhar; None para nenhum
TEMPOS = json.load(open("tts/tempos.json", encoding="utf-8"))

# Faixa reservada à legenda (2 linhas, FontSize 15 / MarginV 22 em 1080p): nada abaixo de y = -2,3.
LIMITE_LEGENDA = -2.3


def txt(s, size=30, cor=TEXTO, **kw):
    return Text(s, font=FONT, weight="BOLD", color=cor, font_size=size, **kw)


def cartao(titulo, sub="", w=3.0, h=2.0, cor=DESTAQUE):
    box = RoundedRectangle(corner_radius=0.2, width=w, height=h).set_stroke(cor, 3, opacity=0.8).set_fill(cor, opacity=0.07)
    t = txt(titulo, 30).move_to(box.get_center() + UP * (0.25 if sub else 0))
    if t.width > w - 0.3:
        t.width = w - 0.3
    g = Group(box, t)
    if sub:
        s = txt(sub, 20).set_opacity(0.85).next_to(t, DOWN, buff=0.12)
        g.add(s)
    return g


class Base(Scene):
    ID = None            # id da cena no spec (chave de tempos.json)
    BG = BG_PADRAO
    BG_ANTES = None      # fundo da cena anterior, quando diferente: abre com fade entre os dois
    TITULO = ""

    def setup(self):
        self.t = 0.0
        info = TEMPOS[self.ID]
        self.total, self.lead, self.fala = info["total"], info["lead"], info["fala"]
        bg = ImageMobject(self.BG)
        bg.height = config.frame_height
        self.add(bg)
        self.fixos = [bg]
        self.prev = None
        if self.BG_ANTES and self.BG_ANTES != self.BG:
            self.prev = ImageMobject(self.BG_ANTES)
            self.prev.height = config.frame_height
            self.add(self.prev)
        if LOGO:
            self.logo = SVGMobject(LOGO)
            self.logo.height = 0.42
            self.logo.to_corner(UL, buff=0.45)
            self.add(self.logo)
            self.fixos.append(self.logo)
        self.titulo = txt(self.TITULO, 40).to_edge(UP, buff=0.55)

    # --- relógio da cena, no grid de quadros. O Manim grava int(s·fps) quadros num `wait` (piso) e
    #     len(np.arange(0, rt, 1/fps)) num `play` (teto): contando por segundos, uma cena de 20 passos
    #     derivou 0,3 s e cortou o fim da narração. Aqui cada passo é arredondado ao quadro e `self.t`
    #     avança pela mesma conta do renderer, e a cena fecha em `total` com ±1 quadro.
    def p(self, *anims, rt=1.0, **kw):
        """play que contabiliza o tempo."""
        fps = config.frame_rate
        rt = max(1, round(rt * fps)) / fps
        self.play(*anims, run_time=rt, **kw)
        self.t += len(np.arange(0, rt, 1 / fps)) / fps

    def w(self, s):
        fps = config.frame_rate
        n = round(s * fps)
        if n > 0:
            self.wait(n / fps + 1e-6)
            self.t += n / fps

    def ate(self, t):
        self.w(t - self.t)

    def q(self, frac):
        """Espera até a fração `frac` da narração."""
        self.ate(self.lead + self.fala * frac)

    def abre(self, rt=0.5):
        anims = [FadeIn(self.titulo, shift=DOWN * 0.2)]
        if self.prev is not None:
            anims.append(FadeOut(self.prev))
        self.w(self.lead * 0.4)
        self.p(*anims, rt=rt)

    def fim(self, fade=0.45):
        """Espera o resto da cena e desvanece tudo menos fundo e logo."""
        resto = self.total - self.t
        if resto < fade + 0.05:
            print(f"AVISO {self.ID}: animações estouraram a narração ({resto - fade:.2f}s)")
        self.w(resto - fade)
        soltos = [m for m in self.mobjects if m not in self.fixos]
        if soltos:
            self.p(FadeOut(Group(*soltos)), rt=fade)
        else:
            self.w(fade)


class Exemplo(Base):
    """Cena de exemplo: título, três cartões que entram nas frações da fala, linha de destaque."""
    ID, TITULO = "EX", "Três ideias em uma cena"

    def construct(self):
        self.abre()
        cards = Group(cartao("Primeira", "aparece a 10 %"), cartao("Segunda", "a 40 %", cor=SECUNDARIO), cartao("Terceira", "a 70 %"))
        cards.arrange(buff=0.5).move_to([0, -0.3, 0])
        for frac, c in zip((0.1, 0.4, 0.7), cards):
            self.q(frac)
            self.p(FadeIn(c, shift=UP * 0.25), rt=0.6)
        linha = Line(LEFT * 4, LEFT * 4).set_stroke(DESTAQUE, 4).next_to(cards, DOWN, buff=0.3)
        self.q(0.85)
        self.p(Create(linha.put_start_and_end_on(cards.get_corner(DOWN + LEFT), cards.get_corner(DOWN + LEFT) + [8, 0, 0])), rt=0.5)
        self.fim()
