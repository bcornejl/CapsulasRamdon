# ============================================================================
# capsule_content.py - Contexto real del video para narrar la cápsula
#
# Da "de qué trata" la reunión para que la voz en off (español latino) EXPLIQUE
# lo que se muestra, sin inventar. Prioridad de fuente:
#   1) Resumen_Daily_DD-MM-AAAA.md (resumen conciliado): tema (H1) + los tres
#      hechos del "Resumen ejecutivo" → arco Inicio / Proceso / Resultado.
#   2) Transcripción time-aligned (transcripciones/DD-MM-AAAA.md, Whisper) como
#      respaldo (más ruidosa).
# El renderer usa esto para el HOOK y las tarjetas de sección.
# ============================================================================

import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

from utils import date_tag, normalize_date

SEG_RE = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*→\s*(\d{2}):(\d{2}):(\d{2})\.\d{3}\]\s*\n(.+?)(?=\n\[|\Z)",
    re.DOTALL,
)


def clean_md(text: str) -> str:
    """Quita marcas Markdown/citas y normaliza espacios para poder narrarlo."""
    t = text
    t = re.sub(r"\[por validar\]", "", t, flags=re.I)
    t = re.sub(r"\[[^\]]*\]\([^)]*\)", "", t)      # enlaces
    t = re.sub(r"[`*_>#|]", " ", t)                # símbolos md
    t = re.sub(r"\s+([,.;:])", r"\1", t)            # espacio antes de puntuación
    t = re.sub(r"\s+", " ", t).strip(" ·-—:;,.")
    return t.strip()


def to_phrase(text: str, max_chars: int = 165) -> str:
    """Frase breve y limpia para la voz: corta en límite de oración/palabra."""
    t = clean_md(text)
    if not t:
        return ""
    if len(t) > max_chars:
        cut = t[:max_chars]
        dot = max(cut.rfind(". "), cut.rfind(", "))
        cut = cut[:dot] if dot > 60 else cut[:cut.rfind(" ")] if " " in cut else cut
        t = cut.strip(" ,;:")
    if t and t[-1] not in ".!?":
        t += "."
    return t[0].upper() + t[1:] if t else t


# ----------------------------------------------------------------------------
# Rutas
# ----------------------------------------------------------------------------

def _summary_path(root: Path, date_string: str) -> Path:
    d = datetime.strptime(normalize_date(date_string), "%Y-%m-%d")
    tag = date_tag(date_string)
    return (root / "transcripciones" / d.strftime("%m-%Y") /
            f"Daily {tag}" / f"Resumen_Daily_{tag}.md")


def _transcript_path(root: Path, date_string: str) -> Path:
    return root / "transcripciones" / f"{date_tag(date_string)}.md"


# ----------------------------------------------------------------------------
# Transcripción time-aligned
# ----------------------------------------------------------------------------

def _hms(h, m, s) -> float:
    return float(int(h) * 3600 + int(m) * 60 + int(s))


def load_transcript(root: Path, date_string: str) -> List[Tuple[float, float, str]]:
    p = _transcript_path(root, date_string)
    if not p.exists():
        return []
    segs: List[Tuple[float, float, str]] = []
    for m in SEG_RE.finditer(p.read_text(encoding="utf-8", errors="ignore")):
        a = _hms(m.group(1), m.group(2), m.group(3))
        b = _hms(m.group(4), m.group(5), m.group(6))
        txt = " ".join(m.group(7).split())
        if txt:
            segs.append((a, b, txt))
    return segs


def transcript_phrase(segs: List[Tuple[float, float, str]],
                      start: float, end: float) -> str:
    """Frase representativa (la más larga) hablada en [start, end]."""
    inside = [t for (a, b, t) in segs if a >= start - 1 and a < end]
    if not inside:
        return ""
    return to_phrase(max(inside, key=len))


# ----------------------------------------------------------------------------
# Resumen conciliado (fuente preferida)
# ----------------------------------------------------------------------------

def _section(md: str, number: int) -> str:
    """Devuelve el cuerpo de la sección '## N. …' hasta el próximo '## '."""
    m = re.search(rf"^##\s*{number}\.\s.*?$(.*?)(?=^##\s|\Z)", md,
                  flags=re.M | re.DOTALL)
    return m.group(1) if m else ""


def _enumerated_facts(block: str) -> List[str]:
    """Extrae hechos enumerados '(1)… (2)… (3)…' de un bloque de texto."""
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"\((\d)\)", block)]
    if len(marks) < 2:
        return []
    facts: List[str] = []
    for i, (pos, _) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(block)
        piece = re.sub(r"^\(\d\)\s*", "", block[pos:end])
        piece = re.sub(r"^\s*(y|e)\s+", "", piece.strip())
        piece = re.sub(r"[;,]\s*(?:y|e)?\s*$", "", piece.strip())   # cola "; y"
        facts.append(to_phrase(piece))
    return [f for f in facts if f]


class Context:
    """Contexto narrativo: tema + tres puntos (Inicio / Proceso / Resultado)."""

    def __init__(self, theme: str = "", points: Optional[List[str]] = None,
                 source: str = "generico"):
        self.theme = theme
        self.points = points or []
        self.source = source

    def point(self, i: int, fallback: str) -> str:
        return self.points[i] if i < len(self.points) and self.points[i] else fallback


def load_context(root: Path, date_string: str) -> Context:
    """Arma el contexto desde el resumen conciliado; si no hay, desde la transcripción."""
    sp = _summary_path(root, date_string)
    if sp.exists():
        md = sp.read_text(encoding="utf-8", errors="ignore")
        theme = ""
        h1 = re.search(r"^#\s+(.+)$", md, flags=re.M)
        if h1:
            title = h1.group(1)
            theme = clean_md(title.split("):", 1)[1] if "):" in title else title)
        exec_block = _section(md, 2)
        points = _enumerated_facts(exec_block)
        if not points:
            # Respaldo: primeras oraciones del resumen ejecutivo.
            sentences = re.split(r"(?<=[.])\s+", clean_md(exec_block))
            points = [to_phrase(s) for s in sentences[:3] if len(s) > 30]
        if theme or points:
            return Context(theme, points[:3], source="resumen")
    # Respaldo: transcripción (más ruidosa).
    segs = load_transcript(root, date_string)
    if segs:
        return Context("", [], source="transcripcion")
    return Context(source="generico")
