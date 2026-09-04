# ============================================================================
# video_capsule.py - agenteVideo: cápsula ejecutiva (<=1 min) desde un video largo
#
# A partir de una grabación larga (una Daily), selecciona automáticamente los
# momentos MÁS RELEVANTES para la alta gerencia —demos del framework, dashboards,
# tableros, código generado por agentes— y los monta en una CÁPSULA de máximo un
# minuto, con carátula de entrada, subtítulos ejecutivos y cierre co-brand.
#
# La selección prioriza los "artefactos" que demuestran cómo trabaja la célula con
# el Framework Agéntico (clasificados con la misma lógica que visual_capture.py):
# navegador/web (framework en ejecución), código, Jira/Planner, Excel, etc. Los
# paneles de solo cámaras (Teams) puntúan bajo. Se distribuye a lo largo de toda
# la reunión para contar la historia de principio a fin.
#
# Motor de video: PyAV (libx264 + AAC). No requiere ffmpeg del sistema.
# ============================================================================

import os
import re
import sys
import math
import shutil
import unicodedata
import argparse
from pathlib import Path
from fractions import Fraction
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Tuple, Dict

import numpy as np
import av
from PIL import Image, ImageDraw, ImageFont

from utils import (Logger, ProjectPaths, get_video_for_date, get_latest_video,
                   normalize_date, date_tag)
from visual_capture import (classify_artifact, ARTIFACT_LABEL, DOC_ARTIFACTS,
                            FrameOCR, fmt_ts)
from narration import Narrator
import capsule_content
import reel_themes
import reel_discovery

# Windows suele mostrar cp1252 por consola; forzar UTF-8 evita romper con acentos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ----------------------------------------------------------------------------
# Paleta y textos ejecutivos
# ----------------------------------------------------------------------------

BG = (11, 16, 32)          # azul noche corporativo
RED = (236, 0, 0)          # rojo Santander
WHITE = (255, 255, 255)
MUTE = (176, 190, 214)

# Umbral de tono de piel: por encima, el frame MUESTRA personas (camara/galeria) y se
# EXCLUYE del reel. El foco es la proyeccion en pantalla, nunca las personas.
PEOPLE_SKIN = 0.045

# Presentador y marca de las cápsulas: configurables por proyecto (sin tocar código)
# via variables de entorno CAPSULA_PRESENTADOR / CAPSULA_MARCA.
PRESENTER = os.environ.get("CAPSULA_PRESENTADOR", "Bernardo Cornejo López")
BRAND = os.environ.get("CAPSULA_MARCA", "Santander · NTT DATA")


def _skin_frac(rgb: np.ndarray) -> float:
    """Fraccion de pixeles con TONO DE PIEL (subsample rapido con numpy).

    Detecta camaras/galerias de personas. Se usa por-candidato (scout) y por-frame
    (render), por eso evita PIL y solo submuestrea el arreglo (barato)."""
    if rgb is None or rgb.ndim != 3:
        return 0.0
    s = rgb[::12, ::12].astype(np.int16)
    r, g, b = s[..., 0], s[..., 1], s[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    mask = ((r > 95) & (g > 40) & (b > 20) & ((mx - mn) > 15) &
            (np.abs(r - g) > 15) & (r > g) & (r > b))
    return float(mask.mean()) if mask.size else 0.0

# Peso ejecutivo por tipo de artefacto: lo que DEMUESTRA el modelo agentico domina.
ARTIFACT_WEIGHT = {
    "browser": 8.0,        # visualizador agentico / web = lo mas importante
    "jira_planner": 8.0,   # Jira, historias de usuario (HDU), backlog
    "code": 6.0,           # software generado/asistido por agentes
    "excel": 5.0,          # datos/metricas del proceso (plantilla mesa de API)
    "powerpoint": 3.0,
    "word": 2.5,
    "teams": 0.2,          # solo camaras: sin valor ejecutivo
    "otro": 0.8,           # pantalla generica: casi sin valor
}

# Subtítulo ejecutivo (alto nivel, sin exponer PR/commits/hosts/nombres internos).
ARTIFACT_CAPTION = {
    "browser": "Framework agéntico en ejecución",
    "code": "Software generado con apoyo de agentes",
    "jira_planner": "Gestión y trazabilidad del trabajo",
    "excel": "Datos y métricas del proceso",
    "powerpoint": "Presentación de avances",
    "word": "Documentación del proceso",
    "teams": "Sesión de trabajo de la célula",
    "otro": "Trabajo de la célula agéntica",
}

# Señales de ALTO VALOR para la gerencia: el modelo agéntico EN ACCIÓN. Un frame
# que muestra Jira/HDU, el visualizador, el proceso cascade o lenguaje natural →
# salida pesa mucho más que una cámara o una pantalla cualquiera.
VALUE_CUES = [
    (re.compile(r"\bjira\b", re.I), 4.0),
    (re.compile(r"historia[s]?\s+de\s+usuario|\bh\.?\s?d\.?\s?u\.?\b|\bhu[-\s]?\d", re.I), 4.0),
    (re.compile(r"\bbacklog\b|\bsprint\b|\b[eé]pica\b|story\s*points?", re.I), 2.5),
    (re.compile(r"cascad[ae]|waterfall", re.I), 3.0),
    (re.compile(r"visualizador|visualiza", re.I), 4.0),
    (re.compile(r"lenguaje\s+natural|\bprompt\b|\bcomando\b", re.I), 3.5),
    (re.compile(r"open\s?api|spectral|swagger|endpoint", re.I), 2.5),
    (re.compile(r"\bagente[s]?\b|ag[eé]ntic|\bdevin\b|\bcopilot\b", re.I), 0.8),
    (re.compile(r"\bflujo\b|pipeline|workflow", re.I), 0.5),
]


def value_score(text: str) -> float:
    """Puntaje extra por señales del modelo agéntico (Jira/HDU/visualizador/cascade/NL)."""
    if not text:
        return 0.0
    return float(sum(w for pat, w in VALUE_CUES if pat.search(text)))

# Guión de la voz (español latino): arco narrativo Inicio (A) + Proceso (B) = Resultado.
# Puntos genéricos de respaldo cuando no hay resumen/transcripción que aterrice el relato.
GENERIC_POINTS = [
    "La célula agéntica organiza y coordina el trabajo de la reunión.",
    "El framework agéntico ejecuta el proceso con el apoyo de agentes.",
    "Se obtienen avances verificables del ciclo de desarrollo.",
]


def decode_audio_file(path: Path, rate: int = 44100) -> Optional[np.ndarray]:
    """Decodifica un audio (mp3/wav/…) a (2, n) float32 estéreo al ritmo dado."""
    try:
        container = av.open(str(path))
        astream = container.streams.audio[0] if container.streams.audio else None
        if astream is None:
            container.close()
            return None
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=rate)
        chunks: List[np.ndarray] = []
        for frame in container.decode(astream):
            out = resampler.resample(frame)
            for rf in (out if isinstance(out, list) else [out]):
                a = rf.to_ndarray()
                if a.ndim == 1:
                    a = np.stack([a, a])
                if a.shape[0] == 1:
                    a = np.repeat(a, 2, axis=0)
                chunks.append(a.astype(np.float32))
        container.close()
        return np.concatenate(chunks, axis=1) if chunks else None
    except Exception:
        return None


def item_seconds(base_seconds: float, narr: Optional[np.ndarray],
                 rate: int = 44100, pad: float = 0.6) -> float:
    """Duración de un item: al menos su base y suficiente para que quepa la voz."""
    if narr is None or narr.shape[1] == 0:
        return base_seconds
    return max(base_seconds, narr.shape[1] / rate + pad)


# ----------------------------------------------------------------------------
# Tipografía (Segoe UI en Windows; con respaldos)
# ----------------------------------------------------------------------------

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
        if bold else
        ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
    )
    roots = [Path(r"C:\Windows\Fonts"), Path("/usr/share/fonts")]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
        for root in roots:
            p = root / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    return r - l, b - t


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        probe = f"{cur} {w}".strip()
        if _text_size(draw, probe, font)[0] <= max_w or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ----------------------------------------------------------------------------
# Modelo de segmento seleccionado
# ----------------------------------------------------------------------------

@dataclass(eq=False)
class Candidate:
    ts: float
    sig: np.ndarray
    artifact: str = "otro"
    cues: List[str] = field(default_factory=list)
    ocr_len: int = 0
    ocr_text: str = ""
    audio_rms: float = 0.0
    scene_diff: float = 0.0
    skin: float = 0.0               # fraccion de tono de piel (personas en camara)
    value: float = 0.0
    score: float = 0.0


@dataclass
class Segment:
    start: float
    end: float
    artifact: str
    caption: str
    score: float

    @property
    def dur(self) -> float:
        return self.end - self.start


# ----------------------------------------------------------------------------
# Exploración: muestreo + escena + OCR/artefacto + energía de audio
# ----------------------------------------------------------------------------

class HighlightScout:
    def __init__(self, logger: Logger, step: float = 4.0, scene_threshold: float = 6.0,
                 dedup_threshold: float = 6.0, max_candidates: int = 60,
                 ocr_min_score: float = 0.4, use_ocr: bool = True,
                 discovery: bool = False):
        self.logger = logger
        self.step = step
        self.scene_threshold = scene_threshold
        self.dedup_threshold = dedup_threshold
        self.max_candidates = max_candidates
        self.use_ocr = use_ocr
        self.ocr: Optional[FrameOCR] = None
        self.ocr_min_score = ocr_min_score
        self.discovery = discovery   # True: lee el video DENSO (modo reel discovery)

    @staticmethod
    def _signature(rgb: np.ndarray) -> np.ndarray:
        img = Image.fromarray(rgb).convert("L").resize((64, 64))
        return np.asarray(img, dtype=np.float32)

    @staticmethod
    def _skin_ratio(rgb: np.ndarray) -> float:
        """Fraccion de tono de piel del frame (detecta camaras/personas)."""
        return _skin_frac(rgb)

    def _audio_rms(self, container, astream, ts: float, window: float = 0.5) -> float:
        """Energía RMS de ~0.5s de audio alrededor de ts (0 si no hay audio)."""
        if astream is None:
            return 0.0
        try:
            container.seek(int(max(0.0, ts) * av.time_base), backward=True)
            acc, n = 0.0, 0
            for frame in container.decode(astream):
                at = float(frame.pts * astream.time_base) if frame.pts is not None else ts
                if at < ts:
                    continue
                if at > ts + window:
                    break
                arr = frame.to_ndarray().astype(np.float32)
                if arr.size:
                    acc += float(np.mean(np.square(arr)))
                    n += 1
            return math.sqrt(acc / n) if n else 0.0
        except Exception:
            return 0.0

    def _is_novel(self, sig: np.ndarray, kept: List[Candidate]) -> bool:
        for c in kept:
            if float(np.mean(np.abs(sig - c.sig))) < self.dedup_threshold:
                return False
        return True

    def scan(self, video_path: Path, shots_dir: Path,
             progress: Optional[callable] = None) -> Tuple[float, List[Candidate]]:
        shots_dir.mkdir(parents=True, exist_ok=True)
        container = av.open(str(video_path))
        vstream = container.streams.video[0]
        astream = container.streams.audio[0] if container.streams.audio else None
        duration = float(container.duration / av.time_base) if container.duration else 0.0
        self.logger.info(f"Duracion del video: {fmt_ts(duration)} ({duration:.0f}s)")
        # Muestreo. En DISCOVERY (modo reel) se lee el video mas DENSO para no perder
        # capacidades; si no, pasos amplios en videos largos para no agotar el cupo.
        if self.discovery and duration > 0:
            eff_step = max(self.step, duration / max(1, self.max_candidates))
        else:
            eff_step = max(self.step, duration / 120.0) if duration > 0 else self.step
        if astream is None:
            self.logger.warning("El video no tiene pista de audio; la capsula sera silenciosa.")

        if self.use_ocr and self.ocr is None:
            self.logger.info("Cargando OCR para clasificar artefactos (demos/dashboards)...")
            self.ocr = FrameOCR(self.logger, min_score=self.ocr_min_score)

        report_every = max(30.0, duration / 12.0) if duration > 0 else 1e9
        next_report = report_every
        kept: List[Candidate] = []
        last_sig = None
        t = 0.0
        while t < duration and len(kept) < self.max_candidates:
            try:
                container.seek(int(t * av.time_base), backward=True)
                frame = next(container.decode(vstream))
            except (StopIteration, av.AVError):
                break
            ts = float(frame.pts * vstream.time_base) if frame.pts is not None else t
            rgb = frame.to_ndarray(format="rgb24")
            sig = self._signature(rgb)
            diff = float(np.mean(np.abs(sig - last_sig))) if last_sig is not None else 255.0
            is_scene = last_sig is None or diff >= self.scene_threshold
            last_sig = sig

            if is_scene and self._is_novel(sig, kept):
                cand = Candidate(ts=ts, sig=sig, scene_diff=diff)
                cand.skin = self._skin_ratio(rgb)     # personas en camara -> se excluira
                if self.use_ocr:
                    tmp = shots_dir / f"scout_{int(ts):06d}.png"
                    im = Image.fromarray(rgb)
                    if im.width > 1600:
                        r = 1600 / im.width
                        im = im.resize((1600, int(im.height * r)))
                    im.save(tmp)
                    ocr_text = self.ocr.read(tmp)
                    tmp.unlink(missing_ok=True)
                    cand.artifact, cand.cues = classify_artifact(ocr_text)
                    cand.ocr_len = len(ocr_text)
                    cand.ocr_text = ocr_text
                cand.audio_rms = self._audio_rms(container, astream, ts)
                kept.append(cand)
                if progress is None:
                    self.logger.info(
                        f"Candidato {len(kept):>2} - {fmt_ts(ts)} - "
                        f"{ARTIFACT_LABEL.get(cand.artifact, cand.artifact)}")
            t += eff_step
            if progress is not None and t >= next_report:
                progress(f"Discovery {fmt_ts(min(t, duration))}/{fmt_ts(duration)} "
                         f"· {len(kept)} escenas analizadas")
                next_report += report_every

        container.close()
        self._score(kept)
        self.logger.success(f"Candidatos detectados: {len(kept)}")
        return duration, kept

    def _score(self, cands: List[Candidate]) -> None:
        if not cands:
            return
        max_ocr = max((c.ocr_len for c in cands), default=1) or 1
        max_rms = max((c.audio_rms for c in cands), default=1e-9) or 1e-9
        max_diff = max((c.scene_diff for c in cands if c.scene_diff < 255) or [1.0])
        for c in cands:
            base = ARTIFACT_WEIGHT.get(c.artifact, 0.8)
            text_bonus = 0.8 * (c.ocr_len / max_ocr) if c.artifact in DOC_ARTIFACTS else 0.0
            audio_bonus = 0.4 * (c.audio_rms / max_rms)
            scene_bonus = 0.2 * (min(c.scene_diff, max_diff) / max_diff)
            c.value = value_score(c.ocr_text)
            c.score = base + text_bonus + audio_bonus + scene_bonus + c.value
            if c.skin >= PEOPLE_SKIN:              # frame con personas: casi se descarta
                c.score *= 0.05


# ----------------------------------------------------------------------------
# Selección: greedy por score con separación mínima, luego cronológico
# ----------------------------------------------------------------------------

class HighlightSelector:
    def __init__(self, logger: Logger, clip_seconds: float = 6.0, max_seconds: float = 60.0,
                 min_gap: float = 20.0, lead: float = 0.6,
                 card_seconds: float = 3.2, with_cards: bool = True):
        self.logger = logger
        self.clip_seconds = clip_seconds
        self.max_seconds = max_seconds
        self.min_gap = min_gap
        self.lead = lead
        self.card_seconds = card_seconds
        self.with_cards = with_cards

    def _clip_budget(self) -> Tuple[int, float]:
        cards = (2 * self.card_seconds) if self.with_cards else 0.0
        usable = max(0.0, self.max_seconds - cards)
        n = int(usable // self.clip_seconds)
        return max(1, n), usable

    def from_manual(self, marks: List[float], duration: float) -> List[Segment]:
        n_max, _ = self._clip_budget()
        segs: List[Segment] = []
        for ts in sorted(marks)[:n_max]:
            start = max(0.0, min(ts, duration - self.clip_seconds))
            segs.append(Segment(start, min(duration, start + self.clip_seconds),
                                 "otro", "Momento destacado de la reunión", 0.0))
        return segs

    def select(self, cands: List[Candidate], duration: float,
               lo: float = 0.0, hi: Optional[float] = None,
               n_target: Optional[int] = None) -> List[Segment]:
        hi = duration if hi is None else hi
        pool = [c for c in cands if lo <= c.ts < hi]
        n_max = n_target if n_target is not None else self._clip_budget()[0]
        ranked = sorted(pool, key=lambda x: x.score, reverse=True)
        chosen: List[Candidate] = []
        # Dos pasadas: primero con la separación deseada; si faltan momentos, se
        # relaja hasta un mínimo que NUNCA permite clips solapados (>= clip_seconds).
        hard_min = max(self.clip_seconds, self.min_gap * 0.4)
        for gap in (self.min_gap, hard_min):
            for c in ranked:
                if len(chosen) >= n_max:
                    break
                if c in chosen:
                    continue
                if all(abs(c.ts - o.ts) >= gap for o in chosen):
                    chosen.append(c)
            if len(chosen) >= n_max:
                break

        chosen.sort(key=lambda x: x.ts)
        segs: List[Segment] = []
        for c in chosen:
            start = max(lo, c.ts - self.lead)
            start = min(start, max(lo, hi - self.clip_seconds))
            end = min(hi, start + self.clip_seconds)
            if end - start < 1.0:
                continue
            segs.append(Segment(start, end, c.artifact,
                                ARTIFACT_CAPTION.get(c.artifact, ARTIFACT_CAPTION["otro"]),
                                c.score))
        return segs


# ----------------------------------------------------------------------------
# Render: carátulas + clips -> MP4 (libx264 + AAC)
# ----------------------------------------------------------------------------

class CapsuleRenderer:
    def __init__(self, logger: Logger, width: int = 1280, height: int = 720, fps: int = 24,
                 with_audio: bool = True, with_cards: bool = True, with_captions: bool = True,
                 card_seconds: float = 3.2, date_label: str = "", duck: float = 0.22,
                 mute_original: bool = False, narr_pad: float = 0.6, still: bool = False,
                 kenburns: bool = True):
        self.logger = logger
        self.W = width - (width % 2)
        self.H = height - (height % 2)
        self.fps = fps
        self.still = still
        self.kenburns = kenburns   # False en modo reel: reproduce la trama tal cual
        self.with_audio = with_audio
        self.with_cards = with_cards
        self.with_captions = with_captions
        self.card_seconds = card_seconds
        self.date_label = date_label
        self.rate = 44100
        self.duck = duck                 # volumen del audio original bajo la voz
        self.mute_original = mute_original
        self.narr_pad = narr_pad
        self.clip_volume = 0.9           # audio real del clip (la voz va en las tarjetas)

    # --- imágenes -----------------------------------------------------------

    def _fit_bg(self, arr: np.ndarray) -> Image.Image:
        """Ajusta el frame a WxH (letterbox); fondo para Ken Burns, sin subtítulo."""
        im = Image.fromarray(arr).convert("RGB")
        im.thumbnail((self.W, self.H), Image.BILINEAR)
        canvas = Image.new("RGB", (self.W, self.H), BG)
        canvas.paste(im, ((self.W - im.width) // 2, (self.H - im.height) // 2))
        return canvas

    @staticmethod
    def _img_skin(im: Image.Image) -> float:
        """Tono de piel de una imagen PIL (para chequeos puntuales)."""
        return _skin_frac(np.asarray(im.convert("RGB")))

    def _kenburns(self, im: Image.Image, frac: float) -> Image.Image:
        """Zoom lento (1.0→1.08) con leve paneo: da movimiento y evita estatismo."""
        z = 1.0 + 0.08 * frac
        cw, ch = int(self.W / z), int(self.H / z)
        dx = int((self.W - cw) * (0.5 + 0.18 * math.sin(frac * math.pi)))
        dy = (self.H - ch) // 2
        return im.crop((dx, dy, dx + cw, dy + ch)).resize((self.W, self.H), Image.BILINEAR)

    def _draw_caption(self, im: Image.Image, text: str, entrance: float = 1.0) -> None:
        """Subtítulo inferior con entrada animada (fade + slide). `im` es RGBA."""
        if not text or not self.with_captions or entrance <= 0:
            return
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        font = _load_font(int(self.H * 0.042), bold=True)
        pad = int(self.H * 0.024)
        _tw, th = _text_size(d, text, font)
        band = th + pad * 2
        slide = int((1 - entrance) * self.H * 0.05)
        top = self.H - band + slide
        a = int(255 * entrance)
        d.rectangle([0, top, self.W, self.H], fill=(11, 16, 32, int(205 * entrance)))
        d.rectangle([0, top, int(self.W * 0.012), self.H], fill=RED + (a,))
        d.text((pad * 2, top + pad), text, font=font, fill=(255, 255, 255, a))
        im.alpha_composite(overlay)

    def _progress(self, arr: np.ndarray, gi: int, total: int) -> None:
        """Barra de progreso: los ejecutivos ven que es corto (buena práctica)."""
        h = max(3, int(self.H * 0.008))
        arr[self.H - h:, :, :] = (30, 36, 54)
        w = int(self.W * (gi / max(1, total - 1)))
        if w > 0:
            arr[self.H - h:, :w, :] = RED

    def _card_image(self, item: Dict, entrance: float) -> Image.Image:
        """Tarjeta (hook / sección / cierre) con acento kinético y badge A·B·A+B."""
        accent = tuple(item.get("accent", RED))
        im = Image.new("RGBA", (self.W, self.H), BG + (255,))
        d = ImageDraw.Draw(im)
        badge = item.get("badge", "")
        if badge:
            bf = _load_font(int(self.H * 0.34), bold=True)
            bw, _bh = _text_size(d, badge, bf)
            d.text((self.W - bw - int(self.W * 0.07), int(self.H * 0.17)),
                   badge, font=bf, fill=accent + (48,))
        brand = item.get("brand", "")
        if brand:
            bff = _load_font(int(self.H * 0.034), bold=True)
            d.text((int(self.W * 0.09), int(self.H * 0.20)), brand.upper(),
                   font=bff, fill=accent + (255,))
        x = int(self.W * 0.09)
        y = int(self.H * 0.30)
        barw = int(self.W * 0.02) + int(self.W * 0.06 * min(1.0, entrance))
        d.rectangle([x, y, x + barw, y + int(self.H * 0.016)], fill=accent + (255,))
        y += int(self.H * 0.055)
        ta = int(255 * min(1.0, entrance * 1.4))
        ft = _load_font(int(self.H * item.get("title_size", 0.12)), bold=True)
        lines: List[str] = []
        for para in item["title"].split("\n"):
            lines += _wrap(d, para, ft, int(self.W * 0.82)) or [""]
        for line in lines:
            d.text((x, y), line, font=ft, fill=(255, 255, 255, ta))
            y += int(_text_size(d, line, ft)[1] * 1.2)
        sub = item.get("subtitle", "")
        if sub:
            y += int(self.H * 0.03)
            fs = _load_font(int(self.H * 0.05), bold=False)
            for line in _wrap(d, sub, fs, int(self.W * 0.82)):
                d.text((x, y), line, font=fs, fill=MUTE + (ta,))
                y += int(_text_size(d, line, fs)[1] * 1.3)
        foot = item.get("footer", "")
        if foot:
            ff = _load_font(int(self.H * 0.036), bold=True)
            d.text((x, int(self.H * 0.88)), foot, font=ff, fill=accent + (255,))
        return im

    # --- audio --------------------------------------------------------------

    def _clip_audio(self, path: Path, start: float, end: float, n_samples: int) -> np.ndarray:
        """Devuelve exactamente n_samples (2 x n) float32 del tramo [start,end]."""
        buf = np.zeros((2, n_samples), dtype=np.float32)
        try:
            container = av.open(str(path))
            astream = container.streams.audio[0] if container.streams.audio else None
            if astream is None:
                container.close()
                return buf
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=self.rate)
            container.seek(int(max(0.0, start) * av.time_base), backward=True)
            chunks: List[np.ndarray] = []
            for frame in container.decode(astream):
                at = float(frame.pts * astream.time_base) if frame.pts is not None else start
                if at < start:
                    continue
                if at >= end:
                    break
                out = resampler.resample(frame)
                out = out if isinstance(out, list) else [out]
                for rf in out:
                    a = rf.to_ndarray()
                    if a.ndim == 1:
                        a = np.stack([a, a])
                    if a.shape[0] == 1:
                        a = np.repeat(a, 2, axis=0)
                    chunks.append(a.astype(np.float32))
            container.close()
            if chunks:
                data = np.concatenate(chunks, axis=1)
                m = min(n_samples, data.shape[1])
                buf[:, :m] = data[:2, :m]
        except Exception as e:
            self.logger.warning(f"Audio del clip {fmt_ts(start)} omitido ({e}).")
        return buf

    # --- render principal ---------------------------------------------------

    def render_items(self, video_path: Optional[Path], items: List[Dict], out_path: Path) -> bool:
        """Monta una lista de items (tarjeta / clip / imagen) en un MP4 con voz + progreso.

        `video_path` puede ser None (modo Html a video): los items son tarjetas e
        imagenes fijas (kind 'image') y no se lee ningun video de origen.
        """
        if not items:
            self.logger.error("No hay items para montar.")
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)

        for it in items:
            base = it.get("base", self.card_seconds if it["kind"] == "card" else 5.0)
            it["nvf"] = max(1, round(base * self.fps))
        total = sum(it["nvf"] for it in items)

        has_clips = any(it["kind"] == "clip" for it in items)
        has_audio = False
        if video_path is not None and has_clips:
            probe = av.open(str(video_path))
            has_audio = bool(probe.streams.audio)
            probe.close()
        any_narr = any(it.get("narr") is not None for it in items)
        want_audio = self.with_audio and (has_audio or any_narr)

        oc = av.open(str(out_path), "w")
        vstream = oc.add_stream("libx264", rate=self.fps)
        vstream.width, vstream.height = self.W, self.H
        vstream.pix_fmt = "yuv420p"
        vstream.codec_context.time_base = Fraction(1, self.fps)
        vstream.options = {"crf": "21", "preset": "veryfast"}
        # CAPSULE_THREADS=1 fuerza libx264 a 1 hilo: evita el aborto nativo por concurrencia con archivos grandes.
        _cap_threads = os.environ.get("CAPSULE_THREADS")
        if _cap_threads:
            vstream.options["threads"] = _cap_threads
            try:
                vstream.codec_context.thread_count = int(_cap_threads)
            except Exception:
                pass
        astream = None
        if want_audio:
            astream = oc.add_stream("aac", rate=self.rate)
            astream.layout = "stereo"

        # ---- Pase de video -------------------------------------------------
        vpts = 0
        vcontainer = None
        vsrc = None
        if has_clips and video_path is not None:
            vcontainer = av.open(str(video_path))
            vsrc = vcontainer.streams.video[0]
            if _cap_threads:
                try:
                    vsrc.thread_count = int(_cap_threads)
                except Exception:
                    pass
        for it in items:
            if it["kind"] == "card":
                vpts = self._render_card(oc, vstream, it, vpts, total)
            elif it["kind"] == "image":
                vpts = self._render_image(oc, vstream, it, vpts, total)
            else:
                vpts = self._render_clip(oc, vstream, vcontainer, vsrc, it, vpts, total)
        if vcontainer is not None:
            vcontainer.close()
        for pkt in vstream.encode():
            oc.mux(pkt)

        # ---- Pase de audio: voz continua (desborda a los clips) + audio real ---
        if astream is not None:
            try:
                sizes = [round(it["nvf"] * self.rate / self.fps) for it in items]
                total_s = sum(sizes)
                audio = np.zeros((2, total_s), dtype=np.float32)
                offsets = [0]
                for n in sizes[:-1]:
                    offsets.append(offsets[-1] + n)
                # 1) audio real de cada clip en su posición
                if not self.mute_original:
                    for it, off, n in zip(items, offsets, sizes):
                        if it["kind"] == "clip":
                            orig = self._clip_audio(video_path, it["seg"].start, it["seg"].end, n)
                            audio[:, off:off + n] += self.clip_volume * orig
                # 2) voz: se coloca en cada item y puede DESBORDAR al siguiente;
                #    atenúa el audio real que quede debajo (ducking).
                for it, off in zip(items, offsets):
                    narr = it.get("narr")
                    if narr is None:
                        continue
                    m = min(narr.shape[1], total_s - off)
                    if m <= 0:
                        continue
                    audio[:, off:off + m] *= self.duck
                    audio[:, off:off + m] += narr[:, :m] * 0.97
                np.clip(audio, -1.0, 1.0, out=audio)
                apts = 0
                for i in range(0, audio.shape[1], 1024):
                    chunk = np.ascontiguousarray(audio[:, i:i + 1024])
                    af = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
                    af.sample_rate = self.rate
                    af.pts = apts
                    af.time_base = Fraction(1, self.rate)
                    apts += chunk.shape[1]
                    for pkt in astream.encode(af):
                        oc.mux(pkt)
                for pkt in astream.encode():
                    oc.mux(pkt)
            except Exception as e:
                self.logger.warning(f"No se pudo incorporar el audio ({e}); capsula sin sonido.")

        oc.close()
        return True

    def _encode_arr(self, oc, vstream, base: np.ndarray, vpts: int, total: int) -> int:
        arr = base.copy()
        self._progress(arr, vpts, total)
        vf = av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuv420p")
        vf.pts = vpts
        vf.time_base = Fraction(1, self.fps)
        for pkt in vstream.encode(vf):
            oc.mux(pkt)
        return vpts + 1

    def _render_card(self, oc, vstream, item: Dict, vpts: int, total: int) -> int:
        nvf = item["nvf"]
        ef = max(1, int(0.45 * self.fps))
        cached = None
        for k in range(nvf):
            if k < ef:
                base = np.asarray(self._card_image(item, k / ef).convert("RGB"), dtype=np.uint8)
            else:
                if cached is None:
                    cached = np.asarray(self._card_image(item, 1.0).convert("RGB"), dtype=np.uint8)
                base = cached
            vpts = self._encode_arr(oc, vstream, base, vpts, total)
        return vpts

    def _render_clip(self, oc, vstream, container, vsrc, item: Dict,
                     vpts: int, total: int) -> int:
        if self.still:
            return self._render_still(oc, vstream, container, vsrc, item, vpts, total)
        seg = item["seg"]
        nvf = item["nvf"]
        dt = 1.0 / self.fps
        capf = max(1, int(0.4 * self.fps))
        slots = [seg.start + k * dt for k in range(nvf)]
        si = 0
        last_bg = None

        def emit(bg: Image.Image, idx: int) -> np.ndarray:
            frame = self._kenburns(bg, idx / max(1, nvf - 1)) if self.kenburns else bg
            im = frame.convert("RGBA")
            self._draw_caption(im, seg.caption, min(1.0, idx / capf))
            return np.asarray(im.convert("RGB"), dtype=np.uint8)

        try:
            container.seek(int(max(0.0, seg.start) * av.time_base), backward=True)
            for frame in container.decode(vsrc):
                ts = float(frame.pts * vsrc.time_base) if frame.pts is not None else seg.start
                if ts < seg.start - dt:
                    continue
                if ts >= seg.end:
                    break
                rgb = frame.to_ndarray(format="rgb24")
                cur = self._fit_bg(rgb)
                # Reel (sin Ken Burns): si el video corta a CAMARAS/personas, se congela
                # en la ultima pantalla buena (nunca se muestran personas). Skin barato.
                if (not self.kenburns) and last_bg is not None and _skin_frac(rgb) >= PEOPLE_SKIN:
                    cur = last_bg
                while si < nvf and slots[si] <= ts:
                    bg = last_bg if last_bg is not None else cur
                    vpts = self._encode_arr(oc, vstream, emit(bg, si), vpts, total)
                    si += 1
                last_bg = cur
        except Exception as e:
            self.logger.warning(f"Clip {fmt_ts(seg.start)} con lectura parcial ({e}).")
        if last_bg is None:
            last_bg = Image.new("RGB", (self.W, self.H), BG)
        while si < nvf:
            vpts = self._encode_arr(oc, vstream, emit(last_bg, si), vpts, total)
            si += 1
        return vpts

    def _render_still(self, oc, vstream, container, vsrc, item: Dict,
                      vpts: int, total: int) -> int:
        """Modo FIJO: un frame estatico por momento (sin zoom ni paneo); mantiene el foco."""
        seg = item["seg"]
        nvf = item["nvf"]
        still: Optional[Image.Image] = None
        try:
            container.seek(int(max(0.0, seg.start) * av.time_base), backward=True)
            for frame in container.decode(vsrc):
                ts = float(frame.pts * vsrc.time_base) if frame.pts is not None else seg.start
                if ts < seg.start:
                    continue
                still = self._fit_bg(frame.to_ndarray(format="rgb24"))
                break
        except Exception as e:
            self.logger.warning(f"Clip {fmt_ts(seg.start)} sin frame fijo ({e}).")
        if still is None:
            still = Image.new("RGB", (self.W, self.H), BG)
        base = still.convert("RGBA")
        self._draw_caption(base, seg.caption, 1.0)
        arr = np.asarray(base.convert("RGB"), dtype=np.uint8)
        for _ in range(nvf):
            vpts = self._encode_arr(oc, vstream, arr, vpts, total)
        return vpts

    def _render_image(self, oc, vstream, item: Dict, vpts: int, total: int) -> int:
        """Modo Html a video: una imagen fija (letterbox a WxH) por paso, con subtitulo."""
        src = item["image"]
        im = src if isinstance(src, Image.Image) else Image.open(src)
        bg = self._fit_bg(np.asarray(im.convert("RGB")))
        base = bg.convert("RGBA")
        self._draw_caption(base, item.get("caption", ""), 1.0)
        arr = np.asarray(base.convert("RGB"), dtype=np.uint8)
        for _ in range(item["nvf"]):
            vpts = self._encode_arr(oc, vstream, arr, vpts, total)
        return vpts


# ----------------------------------------------------------------------------
# Rundown (trazabilidad de los momentos elegidos hacia el video de origen)
# ----------------------------------------------------------------------------

def write_rundown(path: Path, video: Path, date_string: str, duration: float,
                  segments: List[Segment], total_seconds: float,
                  with_cards: bool = True, voice: Optional[str] = None,
                  theme: Optional[str] = None) -> None:
    tag = date_tag(date_string)
    head = f"# Capsula Extensa educativa - Celula Agentica ({theme}) {tag}" if theme else \
           f"# Capsula ejecutiva - Celula Agentica {tag}"
    lines = [
        head,
        "",
        f"- **Video de origen:** `{video.name}`",
        f"- **Duracion original:** {fmt_ts(duration)}",
        f"- **Duracion capsula:** ~{total_seconds:.0f}s ({len(segments)} momentos"
        f"{' + caratulas' if with_cards else ''})",
        f"- **Voz en off:** {voice}" if voice else "- **Voz en off:** (sin narracion)",
        f"- **Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Momentos incluidos (trazabilidad al minuto del video)",
        "",
        "| # | Origen (video) | Duracion | Foco ejecutivo |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(segments, 1):
        lines.append(f"| {i} | {fmt_ts(s.start)}–{fmt_ts(s.end)} | {s.dur:.0f}s | {s.caption} |")
    lines += [
        "",
        "> Montaje automatico de momentos REALES del video (no se inventa contenido).",
        "> Subtitulos de alto nivel para audiencia ejecutiva; el detalle tecnico no se expone.",
        "> La voz en off (espanol latino) explica lo que se muestra en cada momento.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------
# Progreso (modo reel): log de avance en archivo + consola para el discovery
# ----------------------------------------------------------------------------

class ReelProgress:
    """Log de AVANCE del modo reel (archivo + consola) para seguir el discovery."""

    def __init__(self, path: Path, logger: Logger):
        self.path = path
        self.logger = logger
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            f"# agenteVideo · modo reel · progreso\n"
            f"# inicio: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n", encoding="utf-8")

    def log(self, msg: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.logger.info(msg)

    def phase(self, name: str) -> None:
        self.log(f"===== {name} =====")


def write_discovery_report(path: Path, video: Path, date_string: str, duration: float,
                           use_cases: List) -> None:
    """Base educativa: los casos de uso descubiertos y su explicación (qué/para qué/resultado)."""
    tag = date_tag(date_string)
    lines = [
        f"# Discovery educativo - Celula Agentica {tag}",
        "",
        f"- **Video de origen:** `{video.name}`",
        f"- **Duracion:** {fmt_ts(duration)}",
        f"- **Capsulas Extensas educativas:** {len(use_cases)} (division dinamica por contenido)",
        f"- **Generado:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "> La Capsula Extensa lee el video completo (discovery) y lo desfragmenta en casos de "
        "uso educativos a prueba de principiantes. Cada capsula explica una capacidad con la "
        "estructura de la educacion: que hace, para que sirve y cual es el resultado.",
        "",
    ]
    for i, uc in enumerate(use_cases, 1):
        t = uc.theme
        lines += [
            f"## {i}. {t.title}",
            "",
            f"- **Tramo en el video:** {fmt_ts(uc.start)}–{fmt_ts(uc.end)} · "
            f"{len(uc.marks)} momentos",
            f"- **Archivo:** `CapsulaExtensa-…-{t.slug}-{tag}.mp4`",
            "",
            f"**¿Qué hace?** {t.que_hace}",
            "",
            f"**¿Para qué sirve?** {t.proposito}",
            "",
            f"**¿Cuál es el resultado?** {t.resultado}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _parse_marks(raw: Optional[str]) -> List[float]:
    if not raw:
        return []
    marks: List[float] = []
    for tok in re.split(r"[,\s]+", raw.strip()):
        if not tok:
            continue
        parts = tok.split(":")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            continue
        sec = 0.0
        for n in nums:
            sec = sec * 60 + n
        marks.append(sec)
    return marks


def _window_skin_max(container, vstream, tb, t0: float,
                     window: float = 10.0, samples: int = 5) -> float:
    """Maxima fraccion de piel muestreando `samples` frames en [t0, t0+window].

    Sirve para decidir si un tramo muestra PERSONAS (overlays de camara/Teams)."""
    try:
        container.seek(int(max(0.0, t0) / tb), stream=vstream)
    except av.AVError:
        return 0.0
    targets = [t0 + window * k / max(1, samples - 1) for k in range(samples)]
    ti, mx = 0, 0.0
    for frame in container.decode(vstream):
        if frame.pts is None:
            continue
        t = float(frame.pts * tb)
        if t < t0 - 0.5:
            continue
        while ti < len(targets) and t >= targets[ti]:
            mx = max(mx, _skin_frac(frame.to_ndarray(format="rgb24")))
            ti += 1
        if ti >= len(targets):
            break
    return mx


def _sanitize_marks(video: Path, marks: List[float], logger: Logger,
                    window: float = 10.0, search: float = 120.0,
                    step: float = 3.0) -> List[float]:
    """Corre a la ventana LIMPIA mas cercana cualquier marca que caiga sobre personas.

    Aprendido en esta sesion: una marca manual puede caer en un tramo con overlays de
    Teams (camaras) presentes TODO el clip; ahi 'congelar en la ultima pantalla buena'
    no tiene frame limpio y se filtran personas. Este saneo lo evita en el origen.
    Regla del banco: NUNCA mostrar personas de las reuniones."""
    container = av.open(str(video))
    v = container.streams.video[0]
    tb = v.time_base
    dur = float(container.duration / av.time_base) if container.duration else 0.0
    lim = max(0.0, dur - window)
    out, moved = [], 0
    for m in marks:
        base = max(0.0, min(m, lim))
        if _window_skin_max(container, v, tb, base, window) < PEOPLE_SKIN:
            out.append(m)
            continue
        found = None
        d = step
        while d <= search and found is None:
            for cand in (base + d, base - d):
                if 0.0 <= cand <= lim and _window_skin_max(container, v, tb, cand, window) < PEOPLE_SKIN:
                    found = cand
                    break
            d += step
        if found is not None:
            moved += 1
            logger.info(f"Marca {fmt_ts(m)} tenia personas -> movida a {fmt_ts(found)} (ventana limpia).")
            out.append(found)
        else:
            logger.warning(f"Marca {fmt_ts(m)} tiene personas y no hay ventana limpia a <={int(search)}s; se mantiene.")
            out.append(m)
    container.close()
    if moved:
        logger.info(f"Saneo de marcas: {moved}/{len(marks)} reubicadas para no mostrar personas.")
    return out


def _synth(narrator: Narrator, text: str, stem: Path) -> Optional[np.ndarray]:
    """Sintetiza `text` a voz y lo decodifica a (2, n) para poder mezclarlo."""
    p = narrator.synthesize(text, stem)
    return decode_audio_file(p) if p else None


def _slug(text: str) -> str:
    """Nombre de archivo seguro a partir de una etiqueta (sin acentos ni espacios)."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")
    return t or "Capsula"


def _chapters(duration: float, k: int) -> List[Tuple[float, float]]:
    """Divide [0, duration] en k tramos: videos extensos -> varias cápsulas."""
    k = max(1, k)
    step = duration / k
    return [(i * step, (i + 1) * step if i < k - 1 else duration) for i in range(k)]


def build_capsule(logger: Logger, renderer: "CapsuleRenderer", selector: HighlightSelector,
                  narrator: Optional[Narrator], video: Path, ctx, date_string: str,
                  lo: float, hi: float, cands: Optional[List[Candidate]],
                  marks: Optional[List[float]], part: int, total_parts: int,
                  out_path: Path, args, reel_theme=None) -> Optional[Dict]:
    """Arma UNA cápsula: portada branded + clips reales con voz latina continua.

    Si `reel_theme` viene dado (modo reel educativo), la voz es el guion DIDACTICO del
    tema, el subtitulo de los clips y de la portada son los del tema, y el audio
    original se reemplaza por completo con la voz IA.
    """
    tag = date_tag(date_string)

    # Guion de la voz aterrizado en la memoria/objetivo del proyecto (sin inventar).
    theme_clean = re.sub(r"^\s*c[eé]lula\s+ag[eé]ntica\s*[·:\-–—]\s*", "",
                         ctx.theme or "", flags=re.I).strip()
    hook_text = (f"Célula Agéntica. {theme_clean}."
                 if theme_clean else
                 "Célula Agéntica. Así trabajamos con el Framework Agéntico.")
    pts = ctx.points or []

    def pt(i: int) -> str:
        return pts[i] if i < len(pts) and pts[i] else GENERIC_POINTS[i]

    sec_text = [pt(0), pt(1), pt(2)]
    outro_text = "La inteligencia artificial ejecuta. Las personas deciden."

    def synth(text: str, name: str) -> Optional[np.ndarray]:
        if args.no_narration or narrator is None or not text:
            return None
        return _synth(narrator, text, args._narr_dir / f"{name}_{part}")

    # Modo "una sola voz": si se pasa --script, la narracion continua cubre toda la
    # capsula a nivel PAREJO y se silencia el audio original (sin voces mezcladas).
    # El modo REEL siempre reemplaza el audio por completo con voz IA: si hay tema
    # educativo se usa su guion didactico; si no, se sintetiza el contexto del reel.
    is_reel = getattr(args, "mode", "screenshot") == "capsula"
    voice_only = bool(getattr(args, "script", None)) or is_reel
    if voice_only:
        renderer.mute_original = True
        script_text = getattr(args, "script", None)
        if not script_text and reel_theme is not None:
            script_text = reel_theme.script
        if not script_text:
            script_text = " ".join(p for p in (hook_text, pt(0), pt(1), pt(2), outro_text) if p)
        full_narr = synth(script_text, "script")
        if full_narr is not None:
            pk = float(np.max(np.abs(full_narr))) or 1.0
            full_narr = (full_narr * (0.95 / pk)).astype(np.float32)
        hook_narr = None
        sec_narr = [None, None, None]
        outro_narr = None
    else:
        full_narr = None
        hook_narr = synth(hook_text, "hook")
        sec_narr = [synth(sec_text[i], f"sec{i}") for i in range(3)]
        outro_narr = synth(outro_text, "outro")

    # Presupuesto: las tarjetas son CORTAS (la voz desborda a los clips), así que
    # su duracion de video es fija; los clips llenan hasta >= min_seconds.
    hook_base, outro_base = 4.5, 4.0
    card_time = hook_base + outro_base
    target = (args.min_seconds + args.max_seconds) / 2.0
    budget = max(args.min_seconds - card_time,
                 min(args.max_seconds - card_time, target - card_time))
    clips_target = max(6, int(round(budget / max(1.0, args.clip_seconds))))

    # Seleccionar momentos del tramo [lo, hi].
    # En modo una-sola-voz (reel) la DURACION la manda la NARRACION (rica, ~3-5 min):
    # se muestran MUCHOS momentos de pantalla y, si el tema tiene pocos, se AVANZA
    # dentro del screen-share (no se congela ni se repite igual) para cubrir la voz.
    ordered = bool(getattr(args, "ordered", False)) and marks is not None
    if marks is not None:
        base_marks = list(marks if ordered else sorted(marks))
        if voice_only and full_narr is not None and base_marks:
            narr_s = full_narr.shape[1] / renderer.rate
            total_clip_time = max(narr_s + 1.0 - card_time, len(base_marks) * 4.0)
            n_slots = min(60, max(len(base_marks), int(round(total_clip_time / 12.0))))
            clip_len = max(6.0, min(18.0, total_clip_time / n_slots))
            marks_seq = [base_marks[i % len(base_marks)] + (i // len(base_marks)) * clip_len
                         for i in range(n_slots)]
        else:
            clip_len = args.clip_seconds
            marks_seq = base_marks
        segs: List[Segment] = []
        for m in marks_seq:
            st = max(lo, min(m, hi - clip_len))
            segs.append(Segment(st, min(hi, st + clip_len), "otro",
                                ARTIFACT_CAPTION["otro"], 0.0))
    else:
        segs = selector.select(cands or [], hi, lo=lo, hi=hi, n_target=clips_target)
        # PRIORIZA VALOR: NO rellenar con momentos sin valor. Si faltan segundos,
        # ALARGA los clips de valor (muestra mas de cada momento). Solo si NO hay
        # nada util se usa un relleno minimo equiespaciado (ultimo recurso).
        need_s = max(0.0, args.min_seconds - card_time)
        have_s = sum(s.dur for s in segs)
        if segs and have_s < need_s:
            per = min(14.0, args.clip_seconds + (need_s - have_s) / len(segs))
            segs = [Segment(s.start, min(hi, s.start + per), s.artifact, s.caption, s.score)
                    for s in segs]
        elif not segs:
            step = (hi - lo) / 13.0
            for j in range(1, 13):
                st = max(lo, min(lo + j * step, hi - args.clip_seconds))
                segs.append(Segment(st, min(hi, st + args.clip_seconds),
                                    "otro", ARTIFACT_CAPTION["otro"], 0.0))
    if not segs:
        return None

    # En un reel educativo el subtitulo de cada clip refuerza el tema (didactico).
    if reel_theme is not None:
        for s in segs:
            s.caption = reel_theme.caption

    # Repartir en tres actos. En un reel educativo (o con --ordered) se reparte por el
    # ORDEN del reel: 1er tercio = ¿qué hace?, 2do = propósito, 3ro = resultado; así el
    # subtítulo del acto acompaña a la narración. Si no, por posición temporal.
    groups: List[List[Segment]] = [[], [], []]
    if ordered or reel_theme is not None:
        third = max(1, len(segs) // 3)
        groups = [segs[:third], segs[third:2 * third], segs[2 * third:]]
    else:
        segs.sort(key=lambda s: s.start)
        span = max(1e-6, hi - lo)
        for s in segs:
            rel = (s.start - lo) / span
            groups[0 if rel < 1 / 3 else (1 if rel < 2 / 3 else 2)].append(s)
        if len(segs) >= 3 and sum(1 for g in groups if g) < 3:
            third = max(1, len(segs) // 3)
            groups = [segs[:third], segs[third:2 * third], segs[2 * third:]]

    # Construir el timeline de items.
    # Los reels educativos son temas DISTINTOS (no partes de uno solo): sin "Parte x/y".
    part_tag = "" if reel_theme is not None else (
        f" · Parte {part}/{total_parts}" if total_parts > 1 else "")
    cards = not args.no_cards
    items: List[Dict] = []
    if cards:
        cover_sub = (reel_theme.title if reel_theme is not None
                     else (theme_clean or getattr(args, "_label", "")
                           or "Framework Agéntico")) + part_tag
        cover_title = "Cápsula Extensa\nCélula Agéntica" if is_reel else "Cápsula\nCélula Agéntica"
        items.append({"kind": "card", "title": cover_title,
                      "subtitle": cover_sub,
                      "footer": f"Realizado por {PRESENTER}",
                      "badge": "", "accent": RED, "brand": BRAND,
                      "title_size": 0.13, "base": hook_base,
                      "narr": full_narr if voice_only else hook_narr})
    # Sin tarjetas de sección (A·B·A+B): la voz (Inicio/Proceso/Resultado) va SOBRE
    # los clips reales, mostrando el framework agéntico en acción.
    for gi in range(3):
        if not groups[gi]:
            continue
        for j, s in enumerate(groups[gi]):
            if reel_theme is not None:
                s.caption = reel_theme.act_caption(gi)   # ¿qué hace?/propósito/resultado
            items.append({"kind": "clip", "seg": s,
                          "narr": sec_narr[gi] if (j == 0 and cards) else None,
                          "base": s.dur})
    if cards:
        items.append({"kind": "card", "title": "La IA ejecuta.\nLas personas deciden.",
                      "subtitle": "Célula Agéntica · Framework Agéntico",
                      "footer": BRAND, "badge": "", "accent": RED,
                      "title_size": 0.10, "base": outro_base, "narr": outro_narr})

    if not renderer.render_items(video, items, out_path):
        return None
    total = sum(it["nvf"] for it in items) / renderer.fps
    voice = f"{narrator.voice} ({narrator.backend})" if (narrator and narrator.backend) else None
    return {"segs": segs, "total": total, "voice": voice,
            "theme": reel_theme.title if reel_theme is not None else None}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="agenteVideo: Capsula Extensa educativa (<=5 min, varias por video) con "
                    "voz masculina IA (Bernardo Cornejo Lopez), solo pantalla, sin personas.")
    ap.add_argument("--video", type=str, help="Ruta del video (auto por fecha si se omite)")
    ap.add_argument("--date", type=str, help="Fecha 'hoy'/DD-MM-AAAA/AAAA-MM-DD (default: hoy)")
    ap.add_argument("--mode", choices=["screenshot", "capsula", "reel", "html"], default="screenshot",
                    help="screenshot: imagenes fijas de momentos clave; "
                         "capsula: Capsula Extensa (tramas de video cortadas y unidas, <=5 min, "
                         "audio 100%% voz IA, portada 'Capsula Extensa'). 'reel' = alias de capsula. "
                         "html: 'Html a video' (renderiza un HTML/diagrama a un video didactico).")
    ap.add_argument("--html", type=str,
                    help="(modo html) ruta del HTML a explicar (default: el diagrama del "
                         "ciclo agentico inbox/CicloVidaGluon/infografia.html)")
    ap.add_argument("--settle-ms", type=int, default=1500,
                    help="(modo html) ms de espera por fase antes de capturar (default 1500)")
    ap.add_argument("--presentacion", type=str,
                    help="(modo html) nombre de la presentacion; va en la narracion: "
                         "'Soy Bernardo Cornejo Lopez y se explicara <nombre>'")
    ap.add_argument("--reels", type=str,
                    help="(modo capsula) temas educativos por slug, separados por coma "
                         "(Que-es-un-Agente, Panel-Cascade, Visualizador-Agentico, "
                         "Jira-HDU-Refinamiento, MCP-Conexion, Auto-aprendizaje-Calibracion, "
                         "Software-de-Terceros). Por defecto se eligen automaticamente.")
    ap.add_argument("--no-transcribe", action="store_true",
                    help="(modo capsula) NO transcribir el audio (omite el discovery profundo "
                         "y los entregables 01-04); mas rapido, solo discovery visual")
    ap.add_argument("--out", type=str, help="Ruta .mp4 (solo si sale 1 capsula; auto si se omite)")
    ap.add_argument("--label", type=str, help="Etiqueta del video (nombre de salida + subtitulo; auto del nombre del archivo)")
    ap.add_argument("--theme", type=str, help="Tema del hook, aterrizado en la memoria/objetivo del proyecto")
    ap.add_argument("--points", type=str,
                    help="Tres frases Inicio|Proceso|Resultado separadas por | (aterrizadas en memoria)")
    ap.add_argument("--min-seconds", type=float, default=60.0, help="Duracion MINIMA por capsula (default 60)")
    ap.add_argument("--max-seconds", type=float, default=95.0, help="Duracion maxima por capsula")
    ap.add_argument("--clip-seconds", type=float, default=5.0, help="Duracion de cada momento")
    ap.add_argument("--min-gap", type=float, default=8.0, help="Separacion minima entre momentos")
    ap.add_argument("--capsules", type=int, default=0, help="N de capsulas (0 = auto por duracion)")
    ap.add_argument("--chapter-minutes", type=float, default=12.0, help="Minutos por capsula en modo auto")
    ap.add_argument("--fps", type=int, default=24, help="Cuadros por segundo")
    ap.add_argument("--height", type=int, default=720, help="Alto (16:9)")
    ap.add_argument("--step", type=float, default=4.0, help="Muestreo de analisis (s)")
    ap.add_argument("--at", type=str, help="Marcas manuales 'm:ss,...' (una sola capsula)")
    ap.add_argument("--ordered", action="store_true",
                    help="Respeta el ORDEN de --at (narrativo, no cronologico)")
    ap.add_argument("--keep-marks", action="store_true",
                    help="No sanear marcas --at (por defecto se reubican las que muestran personas)")
    ap.add_argument("--no-audio", action="store_true", help="Capsula silenciosa")
    ap.add_argument("--no-cards", action="store_true", help="Sin tarjetas/secciones")
    ap.add_argument("--no-captions", action="store_true", help="Sin subtitulos en los clips")
    ap.add_argument("--no-ocr", action="store_true", help="No clasificar artefactos (mas rapido)")
    ap.add_argument("--no-narration", action="store_true", help="Sin voz en off (TTS)")
    ap.add_argument("--voice", type=str, default="es-MX-DaliaNeural",
                    help="Voz en espanol latino: alias mx/co/ar/cl/us o nombre edge-tts completo")
    ap.add_argument("--mute-original", action="store_true",
                    help="Silencia el audio original del clip (deja solo la voz en off)")
    ap.add_argument("--script", type=str,
                    help="Narracion continua: UNA sola voz latina cubre toda la capsula y "
                         "silencia el audio original (evita mezclar voces con niveles dispares)")
    ap.add_argument("--still", action="store_true",
                    help="Imagen FIJA por momento (sin zoom ni paneo Ken Burns): mantiene el foco")
    ap.add_argument("--script-file", type=str,
                    help="Archivo UTF-8 con la narracion continua (evita problemas de acentos por consola)")
    args = ap.parse_args()

    paths = ProjectPaths()
    logger = Logger(paths.log_file)
    date_string = normalize_date(args.date)
    tag = date_tag(date_string)

    # Modo 3 (Html a video): rama propia. Renderiza un HTML (por defecto el diagrama
    # del ciclo agentico) a un video estilo Capsula Extensa, con voz IA masculina y
    # sin video de origen. Salida en la carpeta 'Html-a-video/'.
    if args.mode == "html":
        import html_to_video
        return html_to_video.run(args, paths, logger, date_string)

    if args.mode == "reel":            # alias historico de 'capsula'
        args.mode = "capsula"
    is_reel = (args.mode == "capsula")
    logger.section(f"agenteVideo - {'Capsula Extensa' if is_reel else 'Screenshot'} {tag}")
    if getattr(args, "script_file", None):
        try:
            args.script = Path(args.script_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"No se pudo leer --script-file ({e}).")

    # Los dos modos del agenteVideo:
    #  - screenshot (actual): imagenes FIJAS de los momentos clave (mantiene el foco).
    #  - reel: reproduce las TRAMAS de video cortadas y unidas, con el audio original
    #    reemplazado por completo con voz IA y tope duro de 5 minutos.
    if is_reel:
        args.still = False
        args.mute_original = True
        if args.max_seconds > 300:
            args.max_seconds = 300.0
        # Voz MASCULINA por defecto (presentador Bernardo Cornejo Lopez), salvo override.
        if args.voice == "es-MX-DaliaNeural":
            args.voice = "es-MX-JorgeNeural"
    else:
        args.still = True

    # Track PROPIO del agenteVideo: SOLO la carpeta 'capsula/' (videos/ es de agenteDaily).
    # Para pruebas se puede apuntar --video a un video del agenteDaily, pero nada mas.
    capsula_dir = paths.root / "capsula"
    if args.video:
        video = Path(args.video)
    else:
        video = (get_video_for_date(capsula_dir, date_string)
                 or get_latest_video(capsula_dir))
    if not video or not video.exists():
        logger.error(f"No hay video en la carpeta 'capsula/' para {tag}. Deja el video "
                     f"largo en {capsula_dir} (o pasa --video <ruta> solo para probar).")
        return 1
    logger.info(f"Video: {video.name}")

    month = datetime.strptime(date_string, "%Y-%m-%d").strftime("%m-%Y")
    out_dir = paths.presentacion / "ReporteVideo" / month / ("capsula-extensa" if is_reel else "screenShot")
    width = int(round(args.height * 16 / 9))
    args._narr_dir = paths.root / "output" / "_narration"

    renderer = CapsuleRenderer(logger, width=width, height=args.height, fps=args.fps,
                               with_audio=not args.no_audio, with_cards=not args.no_cards,
                               with_captions=not args.no_captions, date_label=tag,
                               mute_original=args.mute_original, still=args.still,
                               kenburns=not is_reel)
    selector = HighlightSelector(logger, clip_seconds=args.clip_seconds,
                                 max_seconds=args.max_seconds, min_gap=args.min_gap)
    narrator = None if args.no_narration else Narrator(logger, voice=args.voice)

    # Contexto real del video para narrar "como en el video" (sin inventar).
    # Etiqueta para distinguir varios videos del mismo dia (nombre de salida + subtitulo).
    if args.label:
        label = args.label
    elif args.video:
        raw = re.sub(r"(?i)grabaci[oó]n", "", Path(args.video).stem)
        label = re.sub(r"[-_.\s]+", " ", raw).strip()
    else:
        label = ""
    args._label = label
    slug = _slug(label) if label else "Celula-Agentica"

    # Modo reel: log de AVANCE por VIDEO (el slug evita que se pisen en un lote).
    progress = ReelProgress(out_dir / f"_progreso-capsula-{slug}-{tag}.log", logger) if is_reel else None
    if progress:
        progress.phase("DISCOVERY - lectura completa del video")
        progress.log(f"Video: {video.name}")
    # Contexto narrativo: aterrizado en la MEMORIA/OBJETIVO (si se pasa --theme/--points),
    # o en el Resumen_Daily del dia, o generico para un video suelto sin contexto.
    if args.theme or args.points:
        pts = [p.strip() for p in (args.points or "").split("|") if p.strip()]
        ctx = capsule_content.Context(theme=(args.theme or "").strip(), points=pts, source="memoria")
        logger.info(f"Contexto (memoria/objetivo): {ctx.theme or '(sin tema)'}")
    elif label:
        ctx = capsule_content.Context(source="video")
        logger.info(f"Video suelto: {label} (voz generica; subtitulos por artefacto)")
    else:
        ctx = capsule_content.load_context(paths.root, date_string)
        logger.info(f"Contexto narrativo: {ctx.source}"
                    + (f" · {ctx.theme}" if ctx.theme else ""))

    marks = _parse_marks(args.at)
    if marks:
        probe = av.open(str(video))
        duration = float(probe.duration / av.time_base) if probe.duration else 0.0
        probe.close()
        cands = None
        chapters = [(0.0, duration)]
        logger.info(f"Marcas manuales: {len(marks)} momentos (una capsula)")
        # Saneo anti-personas: reubica marcas que caigan sobre camaras/overlays de Teams.
        if not getattr(args, "keep_marks", False):
            marks = _sanitize_marks(video, marks, logger)
    else:
        if is_reel:
            # DISCOVERY PROFUNDO: leer el video COMPLETO y denso, con umbrales bajos de
            # escena/dedup para capturar MAS momentos (dialogos, preguntas/respuestas,
            # cambios sutiles), no solo unas pocas escenas. Es la operacion mas larga.
            scout = HighlightScout(logger, step=2.5, scene_threshold=3.5,
                                   dedup_threshold=4.0, max_candidates=900,
                                   use_ocr=not args.no_ocr, discovery=True)
            duration, cands = scout.scan(video, paths.root / "output" / "shots",
                                         progress=progress.log if progress else None)
        else:
            scout = HighlightScout(logger, step=args.step, max_candidates=180,
                                   use_ocr=not args.no_ocr)
            duration, cands = scout.scan(video, paths.root / "output" / "shots")
        if not cands:
            logger.error("No se detectaron escenas utiles en el video.")
            return 1
        k = (args.capsules if args.capsules > 0
             else max(1, int(duration / (args.chapter_minutes * 60) + 0.5)))
        chapters = _chapters(duration, max(1, min(k, 6)))

    # Construir la lista de TRABAJOS a renderizar.
    #  - Reel educativo (modo reel sin --at/--theme/--script, o con --reels): tras el
    #    DISCOVERY del video, se DESFRAGMENTA dinamicamente en casos de uso -> uno o
    #    mas reels educativos (2, 4 o mas segun el contenido) con estructura
    #    ¿que hace? / proposito / resultado.
    #  - Resto: una salida por capitulo/tramo (comportamiento clasico).
    reel_educational = is_reel and (
        bool(getattr(args, "reels", None)) or
        (not marks and not getattr(args, "script", None)
         and not args.theme and not args.points))

    jobs: List[Dict] = []
    if reel_educational:
        if progress:
            progress.phase("DESFRAGMENTACION - casos de uso educativos")
        only = None
        if getattr(args, "reels", None):
            only = reel_themes.themes_from_slugs(args.reels.split(","))
            if not only:
                logger.warning("Ningun slug de --reels es valido; uso seleccion automatica.")
        emit = progress.log if progress else logger.info
        # DISCOVERY PROFUNDO DEL AUDIO (transcripcion + intenciones + preguntas reales):
        # produce los entregables 01-04 como EVIDENCIA para curar los reels. Cacheado.
        if not getattr(args, "no_transcribe", False):
            if progress:
                progress.phase("DISCOVERY DE AUDIO - transcripcion, intenciones y preguntas")
            reel_discovery.deep_discovery(video, out_dir / "discovery" / slug, date_string,
                                          duration, cands=cands, emit=emit)
        use_cases = reel_themes.discover_use_cases(cands or [], duration, emit, only=only)
        # Base educativa: reporte de discovery con la explicacion de cada caso de uso.
        write_discovery_report(out_dir / f"Discovery-{slug}-{tag}.md",
                               video, date_string, duration, use_cases)
        # Si se procesan varios videos, el slug del video evita que el reel del intro
        # (mismo tema) de dos demos distintos se sobrescriba.
        vid_slug = f"{slug}-" if label else ""
        for uc in use_cases:
            jobs.append({"lo": 0.0, "hi": duration, "marks": uc.marks,
                         "theme": uc.theme,
                         "out": out_dir / f"CapsulaExtensa-{vid_slug}{uc.theme.slug}-{tag}.mp4",
                         "label": uc.theme.title})
    if not jobs:
        prefix = "CapsulaExtensa" if is_reel else "Capsula"
        n_ch = len(chapters)
        for idx, (lo, hi) in enumerate(chapters, start=1):
            if n_ch > 1:
                out_i = out_dir / f"{prefix}-{slug}-{tag}-parte-{idx:02d}.mp4"
            elif args.out:
                out_i = Path(args.out)
            else:
                out_i = out_dir / f"{prefix}-{slug}-{tag}.mp4"
            jobs.append({"lo": lo, "hi": hi, "marks": (marks if marks else None),
                         "theme": None, "out": out_i,
                         "label": f"{fmt_ts(lo)}-{fmt_ts(hi)}"})

    total_parts = len(jobs)
    logger.info(f"Se generaran {total_parts} salida(s) (video de {fmt_ts(duration)}).")
    if progress:
        progress.phase(f"RENDER - {total_parts} capsula(s) extensa(s)")

    results: List[Path] = []
    for idx, job in enumerate(jobs, start=1):
        out_i = job["out"]
        if progress:
            progress.log(f"Render {idx}/{total_parts}: {job['label']} -> {out_i.name}")
        else:
            logger.info(f"[{idx}/{total_parts}] {job['label']} -> {out_i.name}")
        res = build_capsule(logger, renderer, selector, narrator, video, ctx, date_string,
                            job["lo"], job["hi"], cands, job["marks"], idx, total_parts,
                            out_i, args, reel_theme=job["theme"])
        if not res:
            logger.warning(f"[{idx}] sin momentos utiles; se omite.")
            continue
        rundown = out_i.with_suffix(".md")
        write_rundown(rundown, video, date_string, duration, res["segs"], res["total"],
                      not args.no_cards, res["voice"], theme=res.get("theme"))
        if progress:
            progress.log(f"OK {idx}/{total_parts}: {out_i.name} (~{res['total']:.0f}s)")
        logger.success(f"[{idx}] listo (~{res['total']:.0f}s): {out_i}")
        results.append(out_i)

    shutil.rmtree(args._narr_dir, ignore_errors=True)
    if not results:
        logger.error("No se genero ninguna capsula.")
        return 1
    if progress:
        progress.phase(f"LISTO - {len(results)} capsula(s) en {out_dir.name}/")
    logger.success(f"Listo: {len(results)} capsula(s) en {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
