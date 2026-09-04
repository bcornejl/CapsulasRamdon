# ============================================================================
# reel_discovery.py - DISCOVERY PROFUNDO del audio para el modo reel (agenteVideo)
#
# El discovery visual (frames/OCR) ve QUE se muestra en pantalla, pero no QUE se
# dice. Este modulo lee el AUDIO COMPLETO (transcripcion Whisper) para entender:
#   - "¿que se va a hacer?" (intencion: "vamos a...", "el objetivo es...").
#   - las PREGUNTAS de los participantes y su tema.
#   - las DEMOSTRACIONES por tema (CI/CD, QA, Jira, agente, API...).
#
# Produce los ENTREGABLES del discovery (para curar los reels con evidencia real):
#   01_transcripcion_completa.md  - transcripcion literal con timestamps.
#   02_discovery_video.md         - mapa temporal + intenciones + preguntas + temas.
#   03_casos_de_uso.md            - casos de uso (contexto/pregunta/demo/resultado/valor).
#   04_matriz_casos_uso.md        - matriz resumen.
#
# NO reemplaza la curacion humana/Copilot: da la EVIDENCIA para que los guiones se
# aterricen en lo que realmente ocurrio (voz IA de Bernardo, cero personas).
# ============================================================================

import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Callable, Dict

# SSL corporativo (Santander): almacen de Windows, igual que transcriber.py.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

Seg = Tuple[float, float, str]   # (inicio_s, fin_s, texto)

# Intencion: "lo que se va a hacer" (arranque de una demo / accion).
INTENT_RX = re.compile(
    r"\b(vamos a|voy a|vamos\b|lo que (?:vamos|voy) a hacer|el objetivo es|la idea es|"
    r"queremos (?:demostrar|mostrar|ver|probar)|a continuaci[oó]n|lo siguiente|"
    r"ahora (?:vamos|veremos|voy|ejecut|revis|mostrar|les muestro)|"
    r"vamos a (?:probar|mostrar|revisar|ver|ejecutar|hacer|demostrar))\b", re.I)

# Pregunta: por el signo de interrogacion que Whisper emite en espanol (¿?). Es la
# senal fiable; los arranques interrogativos sin signo dan muchos falsos (que/como
# relativos), asi que NO se usan.
QUESTION_RX = re.compile(r"[?¿]")

# Temas de demostracion (alineados a las capacidades del producto agentico).
DEMO_TOPICS: List[Tuple[str, re.Pattern]] = [
    ("CI/CD", re.compile(r"\bci\b|\bcd\b|ci.?cd|pipeline|build|deploy|despliegue|jenkins|argo|gitlab|integraci[oó]n continua", re.I)),
    ("QA / Pruebas", re.compile(r"\bqa\b|prueba|\btest\b|xray|sonar|trivy|calidad|cobertura", re.I)),
    ("Jira / HDU", re.compile(r"\bjira\b|historia|backlog|sprint|[eé]pica|refin|planner|criterio", re.I)),
    ("Agente / Framework", re.compile(r"\bagente|ag[eé]ntic|framework|devin|copilot|cascade|\bprompt", re.I)),
    ("Código / PR", re.compile(r"c[oó]digo|pull request|\bpr\b|commit|repositori|\bgit\b|merge", re.I)),
    ("API / Mesa", re.compile(r"\bapi\b|open.?api|spectral|swagger|endpoint|\bmesa\b", re.I)),
    ("Visualizador / Front", re.compile(r"visualizador|front|\bhost\b|navegaci[oó]n|pantalla|dashboard", re.I)),
    ("MCP / Integración", re.compile(r"\bmcp\b|integraci[oó]n|conect|servidor|protocolo", re.I)),
]


def _hms(seconds: float) -> str:
    s = max(0.0, float(seconds))
    return f"{int(s // 3600):02d}:{int((s % 3600) // 60):02d}:{int(s % 60):02d}"


def _hmsms(seconds: float) -> str:
    s = max(0.0, float(seconds))
    return f"{int(s // 3600):02d}:{int((s % 3600) // 60):02d}:{int(s % 60):02d}.{int((s % 1) * 1000):03d}"


_SEG_RE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*→\s*(\d{2}):(\d{2}):(\d{2})\.\d{3}\]\s*\n(.+)")


def _parse_transcript_md(md_path: Path) -> List[Seg]:
    """Relee un 01_transcripcion_completa.md ya generado (cache)."""
    segs: List[Seg] = []
    for m in _SEG_RE.finditer(md_path.read_text(encoding="utf-8", errors="ignore")):
        a = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        b = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + int(m.group(6))
        txt = m.group(7).strip()
        if txt:
            segs.append((float(a), float(b), txt))
    return segs


def transcribe(video: Path, md_path: Path, logger=None,
               emit: Optional[Callable[[str], None]] = None,
               model_name: str = "base") -> List[Seg]:
    """Transcribe el AUDIO COMPLETO (faster-whisper) y escribe 01_transcripcion_completa.md.

    Cachea: si el .md ya existe, lo relee (no re-transcribe)."""
    def say(msg: str) -> None:
        if emit:
            emit(msg)
        elif logger:
            logger.info(msg)

    if md_path.exists():
        segs = _parse_transcript_md(md_path)
        if segs:
            say(f"Transcripcion en cache: {len(segs)} segmentos ({md_path.name}).")
            return segs

    from faster_whisper import WhisperModel
    say(f"Transcribiendo audio con Whisper ({model_name})... (operacion larga)")
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception:
        model = WhisperModel(model_name, device="cpu", compute_type="float32")
    segments, info = model.transcribe(str(video), language="es", vad_filter=True, beam_size=5)

    dur = float(getattr(info, "duration", 0.0) or 0.0)
    segs: List[Seg] = []
    lines: List[str] = []
    next_report = 30.0
    for s in segments:
        st, en, txt = float(s.start), float(s.end), (s.text or "").strip()
        if not txt:
            continue
        segs.append((st, en, txt))
        lines.append(f"[{_hmsms(st)} → {_hmsms(en)}]\n{txt}\n")
        if st >= next_report:
            say(f"Transcripcion {_hms(st)}/{_hms(dur)} · {len(segs)} segmentos")
            next_report += max(30.0, dur / 12.0)

    md_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"# 01 · Transcripcion completa - {video.name}",
        "",
        f"- **Video:** `{video.name}`",
        f"- **Duracion:** {_hms(dur)}",
        f"- **Modelo:** Whisper `{model_name}` (faster-whisper)",
        f"- **Generado:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "> Transcripcion LITERAL del audio (fuente de verdad). Sin diarizacion: los "
        "hablantes no estan etiquetados (requiere un paso aparte). No resumir ni inventar.",
        "",
        "---",
        "",
    ]
    md_path.write_text("\n".join(header) + "\n".join(lines), encoding="utf-8")
    say(f"Transcripcion lista: {len(segs)} segmentos -> {md_path.name}")
    return segs


def _topics_of(text: str) -> List[str]:
    return [name for name, rx in DEMO_TOPICS if rx.search(text)]


def analyze(segs: List[Seg]) -> Dict:
    """Marca cada segmento (intent/question/topics) y arma casos de uso candidatos por tema."""
    tagged = []
    intents: List[Seg] = []
    questions: List[Seg] = []
    for (st, en, txt) in segs:
        is_intent = bool(INTENT_RX.search(txt))
        is_question = bool(QUESTION_RX.search(txt)) and len(txt.split()) >= 3
        topics = _topics_of(txt)
        tagged.append({"start": st, "end": en, "text": txt,
                       "intent": is_intent, "question": is_question, "topics": topics})
        if is_intent:
            intents.append((st, en, txt))
        if is_question:
            questions.append((st, en, txt))

    # Casos de uso candidatos: por TEMA, el tramo [primera, ultima] mencion + su
    # pregunta e intencion mas cercanas (evidencia real del audio).
    cases = []
    for name, _rx in DEMO_TOPICS:
        hits = [t for t in tagged if name in t["topics"]]
        if len(hits) < 2:
            continue
        start = min(h["start"] for h in hits)
        end = max(h["end"] for h in hits)
        q = next((h["text"] for h in hits if h["question"]), "")
        intent = next((h["text"] for h in hits if h["intent"]), "")
        cases.append({"topic": name, "start": start, "end": end,
                      "menciones": len(hits), "pregunta": q, "intencion": intent})
    cases.sort(key=lambda c: c["start"])
    return {"tagged": tagged, "intents": intents, "questions": questions, "cases": cases}


def _nearest_artifact(cands, ts: float) -> str:
    """Que ARTEFACTO estaba en pantalla cerca de `ts` (liga lo dicho con lo mostrado)."""
    if not cands:
        return "-"
    best = min(cands, key=lambda c: abs(getattr(c, "ts", 0.0) - ts))
    return getattr(best, "artifact", "otro")


def write_deliverables(out_dir: Path, video: Path, date_string: str, duration: float,
                       segs: List[Seg], analysis: Dict, cands=None) -> None:
    """Escribe 02_discovery_video.md, 03_casos_de_uso.md y 04_matriz_casos_uso.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tagged = analysis["tagged"]
    intents = analysis["intents"]
    questions = analysis["questions"]
    cases = analysis["cases"]

    # --- 02_discovery_video.md : mapa temporal + intenciones + preguntas ---
    m2 = [
        f"# 02 · Discovery del video - {video.name}",
        "",
        f"- **Duracion:** {_hms(duration)} · **segmentos:** {len(segs)} · "
        f"**intenciones:** {len(intents)} · **preguntas:** {len(questions)}",
        f"- **Generado:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "## ¿Que se va a hacer? (intenciones detectadas)",
        "",
    ]
    m2 += [f"- `{_hms(st)}` {txt}" for (st, en, txt) in intents] or ["- (sin frases de intencion claras)"]
    m2 += ["", "## Preguntas detectadas", ""]
    m2 += [f"- `{_hms(st)}` {txt}" for (st, en, txt) in questions] or ["- (sin preguntas claras)"]
    m2 += ["", "## Mapa temporal (segmento · marca · tema · pantalla)", "",
           "| Inicio | Fin | Marca | Tema(s) | Pantalla | Texto |",
           "|---|---|---|---|---|---|"]
    for t in tagged:
        marca = "PREGUNTA" if t["question"] else ("INTENCION" if t["intent"] else "·")
        temas = ", ".join(t["topics"]) or "-"
        pant = _nearest_artifact(cands, t["start"])
        txt = t["text"].replace("|", "/")
        if len(txt) > 90:
            txt = txt[:87] + "…"
        m2.append(f"| {_hms(t['start'])} | {_hms(t['end'])} | {marca} | {temas} | {pant} | {txt} |")
    (out_dir / "02_discovery_video.md").write_text("\n".join(m2), encoding="utf-8")

    # --- 03_casos_de_uso.md : casos con estructura de venta ---
    m3 = [
        f"# 03 · Casos de uso - {video.name}",
        "",
        "> Casos DETECTADOS por el audio (tema + su pregunta e intencion reales). "
        "Estructura: Contexto → Pregunta → Respuesta → Demostracion → Resultado → Valor. "
        "Curar el guion final (voz IA de Bernardo, cero personas) sobre esta evidencia.",
        "",
    ]
    if not cases:
        m3 += ["_No se detectaron temas de demostracion recurrentes en el audio._", ""]
    for i, c in enumerate(cases, 1):
        m3 += [
            f"## Caso {i}: {c['topic']}",
            "",
            f"- **Tramo:** {_hms(c['start'])}–{_hms(c['end'])} · **menciones:** {c['menciones']}",
            f"- **Intencion (¿que se va a hacer?):** {c['intencion'] or '(no explicita)'}",
            f"- **Pregunta real:** {c['pregunta'] or '(no detectada)'}",
            "- **Respuesta / Demostracion:** (curar con la transcripcion del tramo)",
            "- **Resultado:** (curar) · **Valor para el banco:** (curar)",
            "",
        ]
    (out_dir / "03_casos_de_uso.md").write_text("\n".join(m3), encoding="utf-8")

    # --- 04_matriz_casos_uso.md ---
    m4 = [
        f"# 04 · Matriz de casos de uso - {video.name}",
        "",
        "| # | Tema | Tramo | Menciones | Pregunta real | Intencion |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(cases, 1):
        preg = (c["pregunta"] or "-").replace("|", "/")[:60]
        inte = (c["intencion"] or "-").replace("|", "/")[:60]
        m4.append(f"| {i} | {c['topic']} | {_hms(c['start'])}–{_hms(c['end'])} | "
                  f"{c['menciones']} | {preg} | {inte} |")
    (out_dir / "04_matriz_casos_uso.md").write_text("\n".join(m4), encoding="utf-8")


def deep_discovery(video: Path, out_dir: Path, date_string: str, duration: float,
                   cands=None, logger=None, emit: Optional[Callable[[str], None]] = None,
                   model_name: str = "base") -> Dict:
    """Orquesta el discovery profundo del audio y escribe los entregables. Devuelve el analisis."""
    def say(msg: str) -> None:
        if emit:
            emit(msg)
        elif logger:
            logger.info(msg)

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        segs = transcribe(video, out_dir / "01_transcripcion_completa.md", logger, emit, model_name)
    except Exception as e:
        say(f"No se pudo transcribir el audio ({e}); discovery solo visual.")
        return {"tagged": [], "intents": [], "questions": [], "cases": []}
    analysis = analyze(segs)
    write_deliverables(out_dir, video, date_string, duration, segs, analysis, cands)
    say(f"Discovery de audio: {len(analysis['intents'])} intenciones, "
        f"{len(analysis['questions'])} preguntas, {len(analysis['cases'])} temas -> entregables en {out_dir.name}/")
    return analysis
