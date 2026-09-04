# ============================================================================
# visual_capture.py - Captura visual del video + OCR + fusión con el audio
# Extrae frames por cambio de escena, los documenta en texto (OCR), CLASIFICA el
# artefacto mostrado (Excel/Word/PowerPoint/Jira/Web/Código) y produce una
# transcripción enriquecida (audio + visual) alineada por tiempo. En cada frame
# con un artefacto importante inyecta una directiva OBLIGATORIA para que Copilot
# transcriba TODO lo mostrado (campos, estructura y contenido), sin resumir.
# ============================================================================

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict

import numpy as np
import av
from PIL import Image

from utils import Logger, ProjectPaths, date_tag, normalize_date


# ----------------------------------------------------------------------------
# Utilidades de tiempo
# ----------------------------------------------------------------------------

def fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_compact(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}{m:02d}{s:02d}"


# ----------------------------------------------------------------------------
# Extracción de frames por cambio de escena
# ----------------------------------------------------------------------------

class FrameExtractor:
    """Extrae frames representativos del video detectando cambios de escena."""

    def __init__(self, logger: Logger, step: int = 4, threshold: float = 9.0,
                 max_frames: int = 80, max_width: int = 1920):
        self.logger = logger
        self.step = step               # muestreo en segundos
        self.threshold = threshold     # umbral de diferencia (0-255) para escena nueva
        self.max_frames = max_frames
        self.max_width = max_width

    @staticmethod
    def _signature(rgb: np.ndarray) -> np.ndarray:
        """Firma reducida en escala de grises (64x64) para comparar escenas."""
        img = Image.fromarray(rgb).convert("L").resize((64, 64))
        return np.asarray(img, dtype=np.float32)

    def extract(self, video_path: Path, out_dir: Path,
                date_string: str) -> List[Dict]:
        out_dir.mkdir(parents=True, exist_ok=True)
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        duration = float(container.duration / av.time_base) if container.duration else 0.0
        self.logger.info(f"Duración del video: {fmt_ts(duration)} ({duration:.0f}s)")

        kept: List[Dict] = []
        last_sig = None
        seen_ts = set()

        t = 0
        while t < duration and len(kept) < self.max_frames:
            try:
                container.seek(int(t * av.time_base), backward=True)
                frame = next(container.decode(video=0))
            except (StopIteration, av.AVError):
                break

            ts = float(frame.pts * stream.time_base) if frame.pts is not None else float(t)
            ts_key = int(ts)
            if ts_key in seen_ts:
                t += self.step
                continue
            seen_ts.add(ts_key)

            rgb = frame.to_ndarray(format="rgb24")
            sig = self._signature(rgb)

            is_scene = last_sig is None or float(np.mean(np.abs(sig - last_sig))) >= self.threshold
            if is_scene:
                last_sig = sig
                img = Image.fromarray(rgb)
                if img.width > self.max_width:
                    ratio = self.max_width / img.width
                    img = img.resize((self.max_width, int(img.height * ratio)))
                name = f"frame_{fmt_compact(ts)}.png"
                img.save(out_dir / name)
                kept.append({"ts": ts, "ts_str": fmt_ts(ts), "file": name})
                self.logger.info(f"Escena {len(kept):>2} · {fmt_ts(ts)} → {name}")

            t += self.step

        container.close()
        self.logger.success(f"Frames de escena guardados: {len(kept)}")
        return kept


# ----------------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------------

class FrameOCR:
    """OCR de los frames con RapidOCR (modelos ONNX incluidos, sin binarios)."""

    def __init__(self, logger: Logger, min_score: float = 0.35):
        from rapidocr_onnxruntime import RapidOCR
        self.logger = logger
        self.min_score = min_score
        self.engine = RapidOCR()

    def read(self, image_path: Path) -> str:
        result, _ = self.engine(str(image_path))
        if not result:
            return ""
        # result: [[box, text, score], ...] — ordenar por posición vertical
        lines = []
        for box, text, score in result:
            if score is None or float(score) < self.min_score:
                continue
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            lines.append((min(ys), min(xs), text.strip()))
        lines.sort(key=lambda r: (round(r[0] / 12), r[1]))
        return "\n".join(t for _, _, t in lines if t)


# ----------------------------------------------------------------------------
# Clasificación del artefacto en pantalla + directivas de análisis exhaustivo
#
# El OCR es solo un apoyo (puede fallar). La transcripción profunda —reconstruir
# la planilla, volcar el documento, describir la lámina— la completa Copilot al
# analizar la imagen. Aquí se CLASIFICA cada frame y se inyecta una directiva
# OBLIGATORIA por tipo para que NO se resuma: hay que VOLCAR todo lo mostrado.
# ----------------------------------------------------------------------------

ARTIFACT_LABEL = {
    "excel": "Planilla de cálculo (Excel / CSV)",
    "word": "Documento de texto (Word)",
    "powerpoint": "Presentación (PowerPoint)",
    "jira_planner": "Tablero de gestión (Jira / Planner)",
    "browser": "Navegador / aplicación web (HTML)",
    "code": "Código / IDE",
    "teams": "Panel de reunión (Teams)",
    "otro": "Imagen / diagrama / captura general",
}

# Tipos que exigen transcripción exhaustiva (documentos/datos, no solo la reunión)
DOC_ARTIFACTS = {"excel", "word", "powerpoint", "jira_planner", "browser", "code"}

# Señales por tipo (regex sobre el OCR en minúsculas). Orden = más específico primero.
_SIGNALS: List[Tuple[str, List[str]]] = [
    ("excel", [
        r"\.xls[xmb]?\b", r"\bexcel\b", r"\bhoja\s?\d", r"\blibro\d*\b",
        r"\bsheet\d*\b", r"\btabla\s+din[aá]mica\b", r"\bpromedio\b", r"\bsuma\b",
        r"\bceldas?\b", r"\bf[oó]rmulas?\b", r"\bautosuma\b", r"\bfila[s]?\b.*\bcolumna",
    ]),
    ("word", [
        r"\.docx?\b", r"\bword\b", r"\binterlineado\b", r"\bp[aá]rrafo\b",
        r"\bencabezado\b", r"\bcontrol\s+de\s+cambios\b", r"\bnota\s+al\s+pie\b",
    ]),
    ("powerpoint", [
        r"\.pptx?\b", r"\bpowerpoint\b", r"\bdiapositiva", r"\bpresentaci[oó]n\b",
        r"\bpatr[oó]n\s+de\s+diapositiva", r"\bslide\s?\d",
    ]),
    ("jira_planner", [
        r"\bjira\b", r"\bsprint\b", r"\bbacklog\b", r"\bplanner\b", r"\bkanban\b",
        r"\btablero\b", r"\bhistoria\s+de\s+usuario\b", r"\bstory\s+points?\b",
        r"\bepic\b", r"\bto\s?do\b", r"\bin\s+progress\b", r"\bbloqueo[s]?\b",
    ]),
    ("browser", [
        r"https?://", r"\bwww\.", r"\blocalhost\b", r"127\.0\.0\.1",
        r"\.com\b", r"\.cl\b", r"\bhtml\b", r"\bnavegador\b", r"\blocalhost:\d",
    ]),
    ("code", [
        r"\bimport\s+\w", r"\bdef\s+\w+\s*\(", r"\bfunction\s+\w+\s*\(",
        r"\bclass\s+\w+", r"</\w+>", r"\bvisual\s+studio\s+code\b", r"\bconsole\b",
        r"\.py\b", r"\.ts\b", r"\.js\b", r"\.java\b", r"\.json\b", r"\.ya?ml\b",
    ]),
    ("teams", [
        r"\bmicrosoft\s+teams\b", r"\bsilenciar\b", r"\blevantar\s+la\s+mano\b",
        r"\bparticipantes?\b", r"\breacci[oó]n", r"\bcompartir\s+contenido\b",
    ]),
]


def _numeric_grid_score(text: str) -> int:
    """Cuenta líneas con pinta tabular (números, %, moneda, fechas) — señal de planilla."""
    hits = 0
    for ln in text.splitlines():
        s = ln.strip()
        if s and re.fullmatch(r"[\$\-\+\(\)\d\.,%\s/:]+", s) and re.search(r"\d", s):
            hits += 1
    return hits


def classify_artifact(ocr_text: str) -> Tuple[str, List[str]]:
    """Deduce el tipo de artefacto mostrado y las señales (evidencia) que lo respaldan."""
    text = ocr_text or ""
    low = text.lower()
    grid = _numeric_grid_score(text)
    best_type, best_cues, best_score = "otro", [], 0
    for kind, patterns in _SIGNALS:
        matched: List[str] = []
        for p in patterns:
            m = re.search(p, low)
            if m:
                token = m.group(0).strip()
                if token and token not in matched:
                    matched.append(token)
        score = len(matched)
        if kind == "excel" and grid >= 4:
            matched = matched + [f"grilla numérica (~{grid} líneas)"]
            score += min(grid // 3, 4)
        if score > best_score:
            best_type, best_cues, best_score = kind, matched, score
    if best_score == 0:
        return "otro", []
    return best_type, best_cues[:8]


def analysis_directive(artifact_type: str) -> List[str]:
    """Instrucción OBLIGATORIA de transcripción exhaustiva según el tipo de artefacto."""
    head = "**Análisis exhaustivo OBLIGATORIO (abrir la imagen; no resumir — VOLCAR todo):**"
    guides = {
        "excel": [
            "Reconstruye la PLANILLA COMPLETA como tabla Markdown:",
            "- Nombre del libro y de la pestaña/hoja activa.",
            "- TODOS los encabezados de columna, en orden.",
            "- TODAS las filas visibles con el valor de CADA celda (no omitas ninguna).",
            "- Fórmulas de la barra (fx), totales, subtotales y celdas calculadas.",
            "- Filtros, formato condicional, colores/semáforos y su significado.",
            "- Si un valor es ilegible, escribe `[ilegible]` pero conserva la celda.",
        ],
        "word": [
            "Transcribe el DOCUMENTO COMPLETO respetando la jerarquía:",
            "- Título, subtítulos y todos los párrafos (verbatim).",
            "- Listas con viñetas o numeradas, tablas y notas al pie.",
            "- Encabezados/pies de página y control de cambios si se ve.",
            "- Describe objetos/imágenes incrustados y su propósito.",
        ],
        "powerpoint": [
            "Transcribe TODA la diapositiva y su mensaje:",
            "- Título, subtítulo y número de diapositiva.",
            "- Todas las viñetas, tablas y textos (verbatim).",
            "- Diagramas: describe cajas, flechas y relaciones (qué conecta con qué).",
            "- Notas del orador si son visibles y la idea que comunica la lámina.",
        ],
        "jira_planner": [
            "Vuelca el TABLERO completo:",
            "- Cada tarjeta/incidencia: ID, título, columna/estado, responsable.",
            "- Etiquetas, story points, prioridad y fechas.",
            "- Estructura de columnas y flujo (To Do → Doing → Done, etc.).",
        ],
        "browser": [
            "Transcribe la PÁGINA/APLICACIÓN web:",
            "- URL visible, título de la página y de qué app/sistema se trata.",
            "- Encabezados, textos, tablas, menús y botones.",
            "- Campos de formulario con sus valores y el estado de la pantalla.",
        ],
        "code": [
            "Transcribe el CÓDIGO y su contexto:",
            "- Nombre de archivo y lenguaje.",
            "- El código visible verbatim, respetando la indentación.",
            "- Explica brevemente qué hace y los identificadores relevantes.",
            "- Salida de consola/errores si aparecen.",
        ],
        "teams": [
            "Describe el panel de reunión:",
            "- Participantes visibles y quién comparte o habla.",
            "- Indicadores (silencio, mano levantada) y contenido compartido.",
        ],
        "otro": [
            "Describe la escena con detalle:",
            "- Qué se muestra, disposición y personas.",
            "- Todo el texto legible y su relevancia para la reunión.",
        ],
    }
    return [head, ""] + guides.get(artifact_type, guides["otro"])


# ----------------------------------------------------------------------------
# Parseo de la transcripción de audio
# ----------------------------------------------------------------------------

SEG_RE = re.compile(
    r"\[(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*→\s*(\d{2}):(\d{2}):(\d{2})\.\d{3}\]\s*\n(.+?)(?=\n\[|\Z)",
    re.DOTALL,
)

# Formato del importer (Teams/TXT/VTT): '[m:ss] **Hablante**: texto' (partes opcionales)
IMPORT_LINE_RE = re.compile(
    r"^(?:\[(?P<t>\d{1,2}:\d{2}(?::\d{2})?)\]\s*)?"
    r"(?:\*\*(?P<sp>[^*]{1,60})\*\*:\s*)?"
    r"(?P<txt>.+?)\s*$"
)


def _clock_to_seconds(clock: str) -> float:
    parts = [int(p) for p in clock.split(":")]
    if len(parts) == 2:      # M:SS
        return float(parts[0] * 60 + parts[1])
    if len(parts) == 3:      # H:MM:SS
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return 0.0


def parse_imported_transcript(text: str) -> List[Dict]:
    """Parsea la transcripción importada (Teams/TXT/VTT) escrita por importer.py.

    Reconoce '[t] **Hablante**: texto' (todas las partes opcionales) y conserva el
    hablante para mostrarlo en el enriquecido. Si no hay marcas de tiempo, ordena
    por aparición (las capturas visuales, con segundos reales, se intercalan igual).
    """
    body = text
    for anchor in ("## Transcripción", "## Transcripcion", "## Transcripción\n"):
        if anchor in text:
            body = text.split(anchor, 1)[1]
            break
    segs: List[Dict] = []
    idx = 0
    for raw in body.splitlines():
        line = raw.strip()
        if (not line or line.startswith("#") or line.startswith("---")
                or line.startswith("**Estado**") or line.startswith("*Generado")):
            continue
        # Salta viñetas de metadatos del encabezado ("- **Fecha**: ...").
        if re.match(r"^-\s+\*\*[^*]+\*\*\s*:", line):
            continue
        m = IMPORT_LINE_RE.match(line)
        if not m:
            continue
        txt = (m.group("txt") or "").strip()
        if not txt:
            continue
        clock = m.group("t")
        start = _clock_to_seconds(clock) if clock else float(idx)
        idx += 1
        seg = {"start": start, "end": start, "text": " ".join(txt.split())}
        if m.group("sp"):
            seg["speaker"] = m.group("sp").strip()
        segs.append(seg)
    return segs


def parse_audio(md_path: Path) -> List[Dict]:
    if not md_path.exists():
        return []
    text = md_path.read_text(encoding="utf-8")
    segs = []
    for m in SEG_RE.finditer(text):
        h1, m1, s1, h2, m2, s2, body = m.groups()
        start = int(h1) * 3600 + int(m1) * 60 + int(s1)
        end = int(h2) * 3600 + int(m2) * 60 + int(s2)
        segs.append({"start": float(start), "end": float(end),
                     "text": " ".join(body.split())})
    if segs:
        return segs
    # Respaldo: transcripción importada (Teams/TXT/VTT), no formato Whisper.
    return parse_imported_transcript(text)


# ----------------------------------------------------------------------------
# Escritura de salidas
# ----------------------------------------------------------------------------

def write_visual_log(path: Path, date_string: str, video_name: str,
                     frames: List[Dict], frames_rel: str):
    docs = [f for f in frames if f.get("artifact") in DOC_ARTIFACTS]
    lines = [
        f"# Registro visual — {date_string}",
        "",
        f"- **Video**: {video_name}",
        f"- **Frames de escena**: {len(frames)}",
        f"- **Artefactos importantes detectados**: {len(docs)} "
        "(Excel/Word/PowerPoint/Jira/Web/Código)",
        f"- **Carpeta de imágenes**: {frames_rel}",
        "- **Origen**: Captura de escena + OCR (RapidOCR) + clasificación de artefacto",
        "",
        "> ⚠️ **Regla de detalle:** en cada escena marcada como ARTEFACTO IMPORTANTE hay",
        "> que **abrir la imagen y transcribir TODO** lo mostrado (campos, estructura y",
        "> contenido). El OCR es solo un apoyo con posibles errores; la reconstrucción",
        "> fiel (planilla, documento, lámina) la completa Copilot analizando el frame.",
        "",
        "---",
        "",
    ]
    for i, f in enumerate(frames, 1):
        atype = f.get("artifact", "otro")
        label = ARTIFACT_LABEL.get(atype, ARTIFACT_LABEL["otro"])
        flag = " · ⚠️ ARTEFACTO IMPORTANTE" if atype in DOC_ARTIFACTS else ""
        lines.append(f"## Escena {i} · [{f['ts_str']}] · {label}{flag}")
        lines.append(f"![{f['ts_str']}]({frames_rel}/{f['file']})")
        lines.append("")
        cues = f.get("artifact_cues") or []
        if cues:
            lines.append(f"- **Señales:** {', '.join(cues)}")
            lines.append("")
        ocr = f.get("ocr", "").strip()
        if ocr:
            lines.append("**Texto en pantalla (OCR, apoyo — puede tener errores):**")
            lines.append("")
            lines.append("```text")
            lines.append(ocr)
            lines.append("```")
            lines.append("")
        else:
            lines.append("_Sin texto detectado en pantalla._")
            lines.append("")
        lines.extend(analysis_directive(atype))
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_enriched(path: Path, date_string: str, video_name: str,
                   audio: List[Dict], frames: List[Dict], frames_rel: str):
    events = []
    for seg in audio:
        events.append((seg["start"], "audio", seg))
    for f in frames:
        events.append((f["ts"], "visual", f))
    events.sort(key=lambda e: e[0])

    lines = [
        f"# Transcripción enriquecida (audio + visual) — {date_string}",
        "",
        f"- **Video**: {video_name}",
        f"- **Segmentos de audio**: {len(audio)}",
        f"- **Capturas visuales**: {len(frames)}",
        "- **Origen**: Transcripción (Whisper o Teams importado) + captura de escena/OCR (visual)",
        "",
        "> Las marcas 🖼️ son capturas de pantalla del video con el texto detectado en",
        "> pantalla (OCR). Complementan el audio para entender qué se estaba mostrando.",
        "",
        "---",
        "",
    ]
    for ts, kind, data in events:
        if kind == "audio":
            speaker = data.get("speaker")
            if speaker:
                lines.append(f"**[{fmt_ts(data['start'])}]** **{speaker}:** {data['text']}")
            else:
                lines.append(f"**[{fmt_ts(data['start'])}]** {data['text']}")
            lines.append("")
        else:
            atype = data.get("artifact", "otro")
            label = ARTIFACT_LABEL.get(atype, ARTIFACT_LABEL["otro"])
            flag = " — ⚠️ ARTEFACTO IMPORTANTE" if atype in DOC_ARTIFACTS else ""
            lines.append(f"### 🖼️ [{data['ts_str']}] — {label}{flag}")
            lines.append(f"![{data['ts_str']}]({frames_rel}/{data['file']})")
            ocr = data.get("ocr", "").strip()
            if ocr:
                lines.append("")
                lines.append("**En pantalla (OCR):**")
                lines.append("```text")
                lines.append(ocr)
                lines.append("```")
            if atype in DOC_ARTIFACTS:
                lines.append("")
                lines.extend(analysis_directive(atype))
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Captura visual + OCR + fusión con audio")
    parser.add_argument("--video", type=str, required=True, help="Ruta del video")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--step", type=int, default=4, help="Muestreo en segundos")
    parser.add_argument("--threshold", type=float, default=9.0, help="Umbral de cambio de escena")
    parser.add_argument("--max-frames", type=int, default=80)
    parser.add_argument("--no-ocr", action="store_true", help="Omitir OCR")
    parser.add_argument("--no-merge", action="store_true",
                        help="Solo frames + OCR; no fusiona con el audio")
    parser.add_argument("--merge-only", action="store_true",
                        help="Solo fusiona (usa el visual_<date>.json existente)")
    args = parser.parse_args()

    paths = ProjectPaths()
    logger = Logger(paths.log_file)
    logger.section("CAPTURA VISUAL DEL VIDEO (frames + OCR)")

    video_path = Path(args.video)
    if not video_path.exists():
        logger.error(f"Video no encontrado: {video_path}")
        sys.exit(1)

    # Carpeta mensual: transcripciones/MM-AAAA/Daily DD-MM-AAAA/
    args.date = normalize_date(args.date)
    d = datetime.strptime(args.date, "%Y-%m-%d")
    month_folder = d.strftime("%m-%Y")
    day_dash = d.strftime("%d-%m-%Y")  # token de fecha estándar DD-MM-AAAA
    daily_dir = paths.transcripciones / month_folder / f"Daily {day_dash}"
    daily_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = paths.videos / "frames" / day_dash
    # daily_dir está 3 niveles bajo la raíz (transcripciones/MM-AAAA/Daily DD-MM-AAAA)
    frames_rel = f"../../../videos/frames/{day_dash}"

    # Modo fusión: usa el OCR ya calculado (permite correr tras el audio, en paralelo)
    if args.merge_only:
        vjson = daily_dir / f"visual_{day_dash}.json"
        if not vjson.exists():
            logger.error(f"No existe {vjson}; ejecuta primero la captura visual.")
            sys.exit(1)
        frames = json.loads(vjson.read_text(encoding="utf-8"))
        audio = parse_audio(paths.transcripciones / f"{date_tag(args.date)}.md")
        if audio:
            enriched = daily_dir / f"transcripcion_enriquecida_{day_dash}.md"
            write_enriched(enriched, day_dash, video_path.name, audio, frames, frames_rel)
            logger.success(f"Transcripción enriquecida: {enriched}")
        else:
            logger.warning("No hay transcripción de audio; nada que fusionar.")
        return

    # 1) Extraer frames por cambio de escena
    extractor = FrameExtractor(logger, step=args.step, threshold=args.threshold,
                               max_frames=args.max_frames)
    frames = extractor.extract(video_path, frames_dir, day_dash)

    # 2) OCR de cada frame + clasificación del artefacto mostrado
    if not args.no_ocr and frames:
        logger.section("OCR de los frames + clasificación de artefacto")
        ocr = FrameOCR(logger)
        for i, f in enumerate(frames, 1):
            f["ocr"] = ocr.read(frames_dir / f["file"])
            f["artifact"], f["artifact_cues"] = classify_artifact(f["ocr"])
            n = len(f["ocr"].splitlines()) if f["ocr"] else 0
            tag = ARTIFACT_LABEL.get(f["artifact"], f["artifact"])
            logger.info(f"OCR {i:>2}/{len(frames)} · {f['ts_str']} · {n} líneas · {tag}")
        docs = [f for f in frames if f.get("artifact") in DOC_ARTIFACTS]
        if docs:
            logger.success(f"Artefactos importantes detectados: {len(docs)} "
                           "(requieren transcripción exhaustiva por Copilot).")

    # 3) Registro visual
    visual_log = daily_dir / f"visual_{day_dash}.md"
    write_visual_log(visual_log, day_dash, video_path.name, frames, frames_rel)
    logger.success(f"Registro visual: {visual_log}")

    # 4) Fusión con la transcripción de audio (si existe y no se pidió omitir)
    if not args.no_merge:
        audio_md = paths.transcripciones / f"{date_tag(args.date)}.md"
        audio = parse_audio(audio_md)
        if audio:
            enriched = daily_dir / f"transcripcion_enriquecida_{day_dash}.md"
            write_enriched(enriched, day_dash, video_path.name, audio, frames, frames_rel)
            logger.success(f"Transcripción enriquecida: {enriched}")
        else:
            logger.warning(f"No se encontró transcripción de audio en {audio_md}; solo registro visual.")

    # 5) Índice JSON (para automatización posterior)
    (daily_dir / f"visual_{day_dash}.json").write_text(
        json.dumps(frames, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.success("Captura visual completada.")


if __name__ == "__main__":
    main()
