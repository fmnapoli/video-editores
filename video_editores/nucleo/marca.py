"""Identidade visual do projeto: lê `marca/marca.json` (ADR-17) e converte para o que cada motor quer.

Só biblioteca padrão. Sem `marca.json`, `carregar()` devolve uma Marca com `definida = False` e os valores
padrão do plugin, e cada skill mantém o visual de sempre.

Resolução, na ordem: caminho explícito (campo "marca" do spec ou --marca) > $VE_MARCA > <base>/marca/marca.json.
Um caminho explícito que não existe é erro; os outros dois, quando ausentes, caem no padrão.
"""
import json
import os
import re

PADRAO = {
    "nome": "padrão",
    "cores": {"fundo": "#0F172A", "fundo2": "#1E3A8A", "acento": "#FF6B35", "secundario": "#A78BFA",
              "texto": "#FFFFFF", "texto2": "#E2E8F0"},
    "fonte": {"familia": "DejaVu Sans", "arquivos": {}, "substituta": None},
    "logo": {},
    "fundos": {},
    "legenda": {"estilo": "bloco", "destaque": "acento", "caixa": True},
}
OBRIGATORIAS = ("fundo", "acento", "texto")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def rgb(h):
    """'#RRGGBB' -> (r, g, b)."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ass(h, alpha=0):
    """'#RRGGBB' -> '&HAABBGGRR&' do ASS (alpha 0 = opaco, 255 = transparente)."""
    r, g, b = rgb(h)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}&"


def ass_bgr(h):
    """'#RRGGBB' -> 'BBGGRR' (para tags \\1c&H...& montadas à mão)."""
    r, g, b = rgb(h)
    return f"{b:02X}{g:02X}{r:02X}"


def ffcor(h):
    """'#RRGGBB' -> '0xRRGGBB' dos filtros do ffmpeg."""
    return "0x" + h.lstrip("#").upper()


def luminancia(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ajustar_contraste(cor, fundo, minimo):
    """Menor mudança de luminosidade em `cor` (em direção ao branco ou ao preto, o que estiver mais longe do fundo)
    que atinge o contraste mínimo contra `fundo`. Devolve a cor original se já atende."""
    if contraste(cor, fundo) >= minimo:
        return cor
    alvo = (255, 255, 255) if luminancia(fundo) < 0.5 else (0, 0, 0)
    r, g, b = rgb(cor)
    for i in range(1, 101):
        t = i / 100
        c = "#%02X%02X%02X" % tuple(round(v + (a - v) * t) for v, a in zip((r, g, b), alvo))
        if contraste(c, fundo) >= minimo:
            return c
    return "#%02X%02X%02X" % alvo


class Marca:
    def __init__(self, dados, pasta=None, definida=False):
        self.pasta, self.definida = pasta, definida
        self.dados = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PADRAO.items()}
        for k, v in (dados or {}).items():
            if isinstance(v, dict) and isinstance(self.dados.get(k), dict):
                self.dados[k].update({a: b for a, b in v.items() if b is not None or a == "substituta"})
            else:
                self.dados[k] = v
        self.nome = self.dados.get("nome", "")
        self.cores = self.dados["cores"]
        self._proprias = dict((dados or {}).get("cores", {})) if definida else dict(self.cores)
        if definida:   # papel opcional ausente deriva da própria marca, nunca do padrão do plugin
            proprias = (dados or {}).get("cores", {})
            for opc, base in (("fundo2", "fundo"), ("secundario", "acento"), ("texto2", "texto")):
                if opc not in proprias and base in proprias:
                    self.cores[opc] = proprias[base]
        self.legenda = self.dados["legenda"]

    def cor(self, papel):
        """Cor de um papel; aceita também um HEX direto (ex.: legenda.destaque = "#FACC15")."""
        return papel if _HEX.match(papel or "") else self.cores[papel]

    def caminho(self, rel):
        """Caminho de um arquivo da marca (relativo à pasta do marca.json), ou None."""
        if not rel:
            return None
        p = os.path.expanduser(rel)
        return p if os.path.isabs(p) or not self.pasta else os.path.join(self.pasta, p)

    @property
    def fonte(self):
        return self.dados["fonte"].get("familia") or PADRAO["fonte"]["familia"]

    def fonte_arquivo(self, peso="bold"):
        arqs = self.dados["fonte"].get("arquivos") or {}
        return self.caminho(arqs.get(peso) or arqs.get("bold") or arqs.get("regular"))

    def fontes_dir(self):
        """Pasta dos TTF da marca, para o `fontsdir` do libass; None quando a fonte é do sistema."""
        f = self.fonte_arquivo()
        return os.path.dirname(f) if f else None

    def logo(self, tipo="png"):
        lg = self.dados.get("logo") or {}
        return self.caminho(lg.get(tipo))

    def fundo(self, qual="cartela"):
        return self.caminho((self.dados.get("fundos") or {}).get(qual))

    def problemas(self):
        """Erros que impedem o uso: cor obrigatória ausente ou malformada, arquivo citado que não existe."""
        out = []
        for k in OBRIGATORIAS:
            if k not in self._proprias:
                out.append(f"cores.{k} é obrigatória")
        for k, v in self._proprias.items():
            if not _HEX.match(str(v)):
                out.append(f"cores.{k} = {v!r} não é #RRGGBB")
        refs = [("fonte.arquivos." + k, v) for k, v in (self.dados["fonte"].get("arquivos") or {}).items()]
        refs += [("logo." + k, v) for k, v in (self.dados.get("logo") or {}).items()]
        refs += [("fundos." + k, v) for k, v in (self.dados.get("fundos") or {}).items()]
        for nome, rel in refs:
            p = self.caminho(rel)
            if p and not os.path.exists(p):
                out.append(f"{nome}: arquivo não existe ({p})")
        d = self.legenda.get("destaque")
        if d and not _HEX.match(d) and d not in self.cores:
            out.append(f"legenda.destaque = {d!r} não é um papel de cor nem #RRGGBB")
        if self.legenda.get("estilo", "bloco") not in ("bloco", "palavra"):
            out.append("legenda.estilo deve ser 'bloco' ou 'palavra'")
        return out


def localizar(explicito=None, base="."):
    """Caminho do marca.json a usar, ou None. Caminho explícito inexistente é erro."""
    if explicito:
        p = os.path.expanduser(explicito)
        if os.path.isdir(p):
            p = os.path.join(p, "marca.json")
        if not os.path.exists(p):
            raise SystemExit(f"marca não encontrada: {p}")
        return p
    for p in (os.environ.get("VE_MARCA"), os.path.join(base, "marca", "marca.json")):
        if p and os.path.exists(os.path.expanduser(p)):
            return os.path.expanduser(p)
    return None


def carregar(explicito=None, base=".", estrito=True):
    """Marca do projeto (ou a padrão, com `definida = False`). `explicito=False` força a padrão.
    Com `estrito`, problemas no arquivo encerram com a lista; sem, ficam em `marca.problemas()`."""
    if explicito is False:
        return Marca(None)
    p = localizar(explicito, base)
    if not p:
        return Marca(None)
    try:
        dados = json.load(open(p, encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{p}: JSON inválido ({e})") from None
    m = Marca(dados, pasta=os.path.dirname(os.path.abspath(p)), definida=True)
    m.arquivo = p
    if estrito and m.problemas():
        raise SystemExit(f"{p}:\n  - " + "\n  - ".join(m.problemas()))
    return m
