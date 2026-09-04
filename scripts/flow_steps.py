"""flow_steps.py - Analisis PASO A PASO (end-to-end) del video para capsulas de aprendizaje.

Problema que resuelve (agenteVideo, modo capsula):
  - El montaje anterior repetia marcas con desplazamiento -> BUCLE visual (se veia
    lo mismo varias veces y con tramos solapados).
  - Solo miraba unas pocas "escenas"; se perdian pasos reales de la demo (p. ej.
    entrar al catalogo de API y aplicar filtros).
  - No sabia QUE se hace en cada pantalla ni en que orden -> sin flujo E2E.

Que hace:
  1. Escaneo DENSO del video completo (paso configurable, ~1.5 s) sin perder el foco.
  2. Agrupa frames consecutivos en PASOS: un paso = un estado de pantalla estable.
     Un cambio visual relevante (o de artefacto/pantalla) abre un paso nuevo.
  3. Clasifica cada paso: artefacto (browser/html, excel, code, jira, word, ppt),
     titulo de pantalla y ACCION observada (navegar, filtrar, escribir, desplegar...)
     deducida del texto OCR y de cuanto cambia la imagen.
  4. Detecta TIEMPO MUERTO: tramos sin cambio visual (esperas/cargas) -> se marcan
     `dead=True` para descartarlos del montaje y que la demo AVANCE.
  5. Guarda un SCREENSHOT por paso y persiste el flujo completo en JSON
     (`_flujo_e2e_<slug>.json`) + un `.md` legible: es la memoria del end-to-end.

El resultado alimenta el montaje: pasos reales, en orden, sin repetir ni solapar,
y la narracion puede describir lo que ocurre incluso cuando nadie habla.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import av
import numpy as np
from PIL import Image

from visual_capture import classify_artifact, ARTIFACT_LABEL, FrameOCR, fmt_ts

# Version de la deteccion: invalida el cache cuando cambia la logica de PASOS
# (tramos/actividad). El saneo de nombres de pantalla se re-aplica al leer el
# cache, asi que afinar ese filtro no obliga a re-escanear el video.
FLOW_VERSION = 2


# ----------------------------------------------------------------------------
# Deteccion de la ACCION de cada paso (que se hace en pantalla)
#
# La demo casi nunca dice "ahora hago X"; hay que deducirlo de lo que aparece.
# El orden importa: lo mas especifico primero (filtrar/buscar antes que navegar).
# ----------------------------------------------------------------------------

ACTION_CUES: List[Tuple[str, str, List[str]]] = [
    # (id, frase que se inserta en la narracion, patrones OCR)
    ("filtrar", "se aplican los filtros para acotar el resultado",
     [r"\bfiltr", r"\bfilter", r"\bbuscar\b", r"\bsearch\b", r"\bcriterio", r"\bordenar\b"]),
    ("catalogo", "se consulta el catálogo y se revisa el listado disponible",
     [r"\bcat[aá]logo\b", r"\bcatalog\b", r"\blistado\b", r"\bresultados?\b",
      r"\bapis?\b.*\blista", r"\bexplorar\b"]),
    ("formulario", "se completan los campos del formulario con los datos del caso",
     [r"\bformulario\b", r"\bcampo[s]?\b", r"\bnombre\b.*\bdescripci[oó]n\b",
      r"\brequerido\b", r"\bobligatorio\b", r"\bingres", r"\bcompletar\b"]),
    ("crear", "se crea el nuevo elemento desde la opción correspondiente",
     [r"\bcrear\b", r"\bnuevo\b", r"\bnueva\b", r"\bcreate\b", r"\bnew\b",
      r"\bagregar\b", r"\bañadir\b", r"\badd\b"]),
    ("desplegar", "se ejecuta el despliegue de la aplicación",
     [r"\bdeploy\b", r"\bdespliegue\b", r"\bdesplegar\b", r"\bpublicar\b",
      r"\bbuild\b", r"\bpipeline\b", r"\brelease\b"]),
    ("configurar", "se ajustan los parámetros de configuración",
     [r"\bconfigur", r"\bajuste", r"\bsettings?\b", r"\bpar[aá]metro", r"\bopciones?\b",
      r"\bseguridad\b", r"\bpolicy\b", r"\bautorizaci[oó]n\b"]),
    ("documentar", "se revisa la documentación generada",
     [r"\bdocumentaci[oó]n\b", r"\bdocs?\b", r"\bswagger\b", r"\bopen\s?api\b",
      r"\bespecificaci[oó]n\b", r"\breadme\b"]),
    ("validar", "se valida que el resultado obtenido sea el esperado",
     [r"\bvalidar\b", r"\bvalidaci[oó]n\b", r"\berror(es)?\b", r"\bok\b", r"\b[eé]xito\b",
      r"\bcorrecto\b", r"\bprueba\b", r"\btest\b", r"\bresultado\b"]),
    ("codigo", "se revisa el código del componente",
     [r"\bimport\s+\w", r"\bdef\s+\w+\s*\(", r"\bfunction\s+\w+", r"\bclass\s+\w+",
      r"</\w+>", r"\.ya?ml\b", r"\.json\b", r"\brepositorio\b", r"\bcommit\b"]),
    ("navegar", "se accede a la sección correspondiente",
     [r"\bmen[uú]\b", r"\binicio\b", r"\bhome\b", r"\bsecci[oó]n\b", r"\bpesta[ñn]a\b",
      r"\bvolver\b", r"\bsiguiente\b", r"\bnext\b"]),
]

# Encabezados/nombres de pantalla: la primera linea "titulo" util del OCR.
_NOISE_LINE = re.compile(
    r"^(archivo|inicio|insertar|ayuda|buscar|file|home|edit|view|"
    r"\d{1,2}:\d{2}|[\W_]+)$", re.I)

# Ruido de OCR que NO debe llegar a la voz (sonaria incoherente en la narracion):
# atajos, fragmentos cortados, nombres de personas pegados, palabras sueltas vacias.
_BAD_SCREEN = re.compile(
    r"ctrl?\s*\+|\(ctr|@|\.(com|cl|net)\b|"
    r"^\s*(esta|este|esto|updated?|new|nuevo|nueva|session|home|men[uú])\s*$",
    re.I)

# Palabras que delatan texto suelto de la UI, no un nombre de pantalla.
_BAD_WORD = re.compile(r"^(updated?|al|the|de|del|la|el|los|las|un|una|y|o|en)$", re.I)

# Chrome de la app de reunion / barras genericas: NO son la pantalla de la demo.
# Nombrarlas en la voz ("se da de alta el registro en Sessions") es sencillamente
# incorrecto, asi que se descartan y la frase se queda con el artefacto generico.
_UI_CHROME = {
    "chat", "chats", "sessions", "session", "about", "acerca", "notas", "resumen",
    "compartida", "compartido", "compartir", "participantes", "participante",
    "reunion", "reunión", "grabacion", "grabación", "transcripcion", "transcripción",
    "pregunta", "preguntas", "pregun", "respuesta", "respuestas", "mensaje", "mensajes",
    "teams", "meet", "zoom", "copilot", "menu", "menú", "opciones", "configuracion",
    "configuración", "ayuda", "archivo", "editar", "ver", "inicio", "home", "file",
    "edit", "view", "help", "search", "buscar", "settings", "more", "mas", "más",
    "calendario", "calendar", "actividad", "activity", "aplicaciones", "apps",
    "camara", "cámara", "microfono", "micrófono", "silenciar", "salir", "finalizar",
}


def _is_ui_chrome(s: str) -> bool:
    """¿El texto es barra/menu de la app de reunion en vez de la pantalla demostrada?"""
    palabras = [w.strip(".&/-").lower() for w in s.split()]
    if not palabras:
        return True
    # Si TODAS las palabras son chrome, no aporta nada como nombre de pantalla.
    return all(w in _UI_CHROME for w in palabras)


def _is_valid_screen(s: str) -> bool:
    """¿Es un nombre de pantalla PRESENTABLE para leer en voz alta?

    El OCR devuelve mucho ruido (atajos, nombres de personas, fragmentos). Ante la
    duda se descarta: es preferible decir "en la página web" que leer un texto
    incoherente en una presentacion al banco."""
    if not s or len(s) < 4 or len(s) > 34:
        return False
    if _BAD_SCREEN.search(s) or _is_ui_chrome(s):
        return False
    # Solo letras/numeros/espacios y unos pocos separadores: fuera simbolos raros
    # como "十", "|", barras o iconos mal reconocidos ("Es/createy").
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .&-]*", s):
        return False
    palabras = s.split()
    if not (1 <= len(palabras) <= 4):
        return False
    # Un nombre de pantalla real se escribe como etiqueta: cada palabra empieza en
    # mayuscula o es una sigla ("GLUON", "Customer Actions Hub"). Los fragmentos que
    # deja el OCR ("ndo pant", "ued opua", "e/ZLA") son minusculas sueltas -> fuera.
    for w in palabras:
        limpio = w.strip(".&/-")
        if not limpio or _BAD_WORD.match(limpio):
            return False
        if not (limpio[0].isupper() or limpio.isdigit()):
            return False
        if not (len(limpio) >= 3 or limpio.isupper()):
            return False
        # Pegote CamelCase repetido ("ArriagadaArriagada") o de 3+ trozos = ruido.
        trozos = re.findall(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+", limpio)
        if len(trozos) >= 3 or (len(trozos) >= 2 and
                                len(set(t.lower() for t in trozos)) < len(trozos)):
            return False
        # Sigla creible: hasta 6 letras. "E/ZLA" o "AAAAAAA" no lo son.
        if limpio.isupper() and not re.fullmatch(r"[A-ZÁÉÍÓÚÑ]{2,6}[0-9]{0,2}", limpio):
            return False
    return sum(c.isalpha() for c in s) >= 4


def _screen_title(ocr_text: str, max_len: int = 40) -> str:
    """Nombre de la pantalla/opcion: primera linea significativa y PRESENTABLE del OCR.

    Se descarta el ruido (atajos, nombres de personas, fragmentos): si se leyera en
    la narracion, la capsula sonaria incoherente."""
    for ln in (ocr_text or "").splitlines():
        s = " ".join(ln.split())
        if len(s) < 3 or len(s) > max_len or _NOISE_LINE.match(s):
            continue
        if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{3}", s):
            continue
        if not _is_valid_screen(s):
            continue
        return s
    return ""


def _detect_action(ocr_text: str, change: float, artifact: str,
                   activity: float = 0.0) -> Tuple[str, str]:
    """(id_accion, frase) de lo que ocurre en el paso, deducido del OCR y del cambio."""
    low = (ocr_text or "").lower()
    for aid, phrase, pats in ACTION_CUES:
        if any(re.search(p, low) for p in pats):
            return aid, phrase
    # Sin señal textual: deducir por el movimiento en pantalla.
    if change >= 25.0:
        return "cambiar", "se avanza a la siguiente pantalla del proceso"
    # Mucho movimiento pero poco cambio global = se esta ESCRIBIENDO (dato a dato).
    if activity >= 0.35 or change >= 6.0:
        return "escribir", "se ingresan los datos del ejemplo, campo por campo"
    if activity >= 0.15:
        return "interactuar", "se recorren y seleccionan las opciones"
    return "revisar", "se revisa el detalle desplegado"


# Como se nombra cada artefacto en la voz (lenguaje profesional, no tecnico).
# "otro" se deja vacio a proposito: si no sabemos que es, no se menciona el lugar
# (decir "en la pantalla" en cada frase suena repetitivo y poco profesional).
ARTIFACT_SPOKEN = {
    "browser": "la aplicación web",
    "code": "el editor de código",
    "jira_planner": "el tablero de gestión",
    "excel": "la planilla",
    "word": "el documento",
    "powerpoint": "la presentación",
    "teams": "",
    "otro": "",
}


# Variantes de redaccion por accion: si un mismo tipo de paso aparece mas de una vez,
# se alterna la formulacion para que el guion no suene repetitivo ni automatico.
ACTION_VARIANTS: Dict[str, List[str]] = {
    "filtrar": ["se aplican los filtros para acotar el resultado",
                "se ajustan los criterios de búsqueda",
                "se refina la selección con los filtros disponibles"],
    "catalogo": ["se consulta el catálogo y se revisa el listado disponible",
                 "se recorre el listado del catálogo",
                 "se ubica el elemento dentro del catálogo"],
    "formulario": ["se completan los campos del formulario con los datos del caso",
                   "se cargan los datos requeridos en el formulario",
                   "se termina de completar la información solicitada"],
    "crear": ["se crea el nuevo elemento desde la opción correspondiente",
              "se da de alta el nuevo registro",
              "se genera el elemento con los datos ya definidos"],
    "desplegar": ["se ejecuta el despliegue de la aplicación",
                  "se lanza el proceso de publicación",
                  "se pone en marcha el despliegue"],
    "configurar": ["se ajustan los parámetros de configuración",
                   "se define la configuración correspondiente",
                   "se completan las opciones necesarias"],
    "documentar": ["se revisa la documentación generada",
                   "se contrasta el resultado con la documentación",
                   "se verifica la especificación publicada"],
    "validar": ["se valida que el resultado obtenido sea el esperado",
                "se comprueba el resultado de la ejecución",
                "se confirma que la respuesta es correcta"],
    "codigo": ["se revisa el código del componente",
               "se inspecciona la implementación",
               "se recorre el detalle del código"],
    "navegar": ["se accede a la sección correspondiente",
                "se avanza hasta la siguiente sección",
                "se abre la opción indicada"],
    "escribir": ["se ingresan los datos del ejemplo, campo por campo",
                 "se escribe el detalle solicitado",
                 "se completa la información del caso"],
    "interactuar": ["se recorren y seleccionan las opciones",
                    "se marcan las opciones necesarias",
                    "se navega por las alternativas disponibles"],
    "cambiar": ["se avanza a la siguiente pantalla del proceso",
                "se pasa a la vista siguiente"],
    "revisar": ["se revisa el detalle desplegado",
                "se observa el resultado en pantalla"],
}


def action_phrase(action: str, repeticion: int = 0, fallback: str = "") -> str:
    """Frase de la accion, alternando variantes segun cuantas veces ya se uso."""
    variantes = ACTION_VARIANTS.get(action)
    if not variantes:
        return fallback
    return variantes[repeticion % len(variantes)]


@dataclass
class Step:
    """Un paso real de la demo: un estado de pantalla estable y lo que se hace en el."""
    index: int
    start: float
    end: float
    artifact: str
    screen: str = ""
    action: str = ""
    action_text: str = ""
    ocr_excerpt: str = ""
    change: float = 0.0
    activity: float = 0.0        # fraccion de muestras con movimiento (digitacion, clics)
    dead: bool = False           # tramo REALMENTE congelado = espera/carga -> se descarta
    shot: str = ""               # nombre del PNG del paso

    @property
    def dur(self) -> float:
        return max(0.0, self.end - self.start)

    def narration(self, repeticion: int = 0) -> str:
        """Clausula para la voz IA: empieza por la ACCION, de modo que cualquier
        conector ("A continuación, …") forme una oración natural y bien construida.
        `repeticion` alterna la redacción cuando la acción ya se narró antes."""
        frase = action_phrase(self.action, repeticion, self.action_text)
        donde = ARTIFACT_SPOKEN.get(self.artifact, "")
        if self.screen:
            return f"{frase} en {self.screen}"
        if donde:
            return f"{frase} en {donde}"
        return frase


def _signature(rgb: np.ndarray) -> np.ndarray:
    return np.asarray(Image.fromarray(rgb).convert("L").resize((64, 64)), dtype=np.float32)


def _skin_frac(rgb: np.ndarray) -> float:
    """Fraccion de tono de piel: alto = camaras/personas (se excluye de la capsula)."""
    s = rgb[::12, ::12].astype(np.int16)
    r, g, b = s[..., 0], s[..., 1], s[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    mask = ((r > 95) & (g > 40) & (b > 20) & ((mx - mn) > 15) &
            (np.abs(r - g) > 15) & (r > g) & (r > b))
    return float(mask.mean()) if mask.size else 0.0


def analyze_flow(video: Path, out_dir: Path, logger=None,
                 emit: Optional[Callable[[str], None]] = None, *,
                 step_seconds: float = 1.5, change_threshold: float = 3.0,
                 dead_threshold: float = 0.40, dead_min_seconds: float = 8.0,
                 typing_epsilon: float = 0.18, min_step: float = 2.5,
                 use_ocr: bool = True, people_skin: float = 0.045,
                 shots: bool = True) -> List[Step]:
    """Recorre el video COMPLETO y devuelve el flujo E2E paso a paso.

    - `step_seconds`: muestreo denso (no se salta partes del video).
    - `change_threshold`: diferencia visual que abre un paso nuevo.
    - `dead_threshold` / `dead_min_seconds`: solo se descarta lo REALMENTE congelado
      (nada se mueve durante varios segundos). La DIGITACION mueve poquisimos pixeles,
      asi que un umbral alto la confundiria con espera y se perderia el detalle.
    - `typing_epsilon`: movimiento minimo que ya cuenta como actividad (tecleo/cursor).
    - `min_step`: pasos mas cortos se fusionan con el anterior (evita parpadeos).
    """
    def say(msg: str) -> None:
        if emit:
            emit(msg)
        elif logger:
            logger.info(msg)

    out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = out_dir / "_pasos"
    if shots:
        shots_dir.mkdir(parents=True, exist_ok=True)

    # Cache: el escaneo denso es la operacion mas lenta del pipeline. Se reusa si el
    # video, los parametros y la VERSION de la deteccion no cambiaron.
    cache = out_dir / "_flujo_cache.json"
    key = {"version": FLOW_VERSION, "video": video.name,
           "size": video.stat().st_size if video.exists() else 0,
           "step_seconds": step_seconds, "change_threshold": change_threshold,
           "dead_threshold": dead_threshold, "dead_min_seconds": dead_min_seconds,
           "typing_epsilon": typing_epsilon, "min_step": min_step, "ocr": use_ocr}
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("key") == key:
                steps = [Step(**s) for s in data["pasos"]]
                for s in steps:      # re-aplica el filtro vigente de nombres de pantalla
                    if s.screen and not _is_valid_screen(s.screen):
                        s.screen = ""
                say(f"Flujo E2E en cache: {len(steps)} pasos "
                    f"({sum(1 for s in steps if not s.dead)} utiles).")
                return steps
        except Exception:
            pass

    container = av.open(str(video))
    vstream = container.streams.video[0]
    duration = float(container.duration / av.time_base) if container.duration else 0.0
    say(f"Flujo E2E: escaneo denso cada {step_seconds:.1f}s sobre {fmt_ts(duration)}.")

    ocr = FrameOCR(logger, min_score=0.4) if (use_ocr and logger is not None) else None

    steps: List[Step] = []
    last_sig = None
    cur: Optional[Step] = None
    cur_changes: List[float] = []
    cur_rgb = None
    t = 0.0
    report_every = max(30.0, duration / 12.0) if duration > 0 else 1e9
    next_report = report_every

    def close_step(end_t: float) -> None:
        """Cierra el paso en curso: decide si fue espera y guarda su captura."""
        nonlocal cur, cur_changes, cur_rgb
        if cur is None:
            return
        cur.end = end_t
        cur.change = float(max(cur_changes)) if cur_changes else 0.0
        # Actividad: proporcion de muestras con movimiento real (tecleo, clics, scroll).
        cur.activity = (sum(1 for c in cur_changes if c >= typing_epsilon) / len(cur_changes)
                        if cur_changes else 0.0)
        # Espera/carga: SOLO si estuvo practicamente congelado un buen rato. Un paso con
        # digitacion tiene `change` bajo pero `activity` alta -> NO es espera.
        cur.dead = (cur.change < dead_threshold and cur.activity < 0.15
                    and cur.dur >= dead_min_seconds)
        if cur_rgb is not None:
            if use_ocr and ocr is not None:
                tmp = shots_dir / f"_tmp_{cur.index:03d}.png"
                im = Image.fromarray(cur_rgb)
                if im.width > 1600:
                    im = im.resize((1600, int(im.height * 1600 / im.width)))
                im.save(tmp)
                text = ocr.read(tmp)
                tmp.unlink(missing_ok=True)
                cur.artifact = classify_artifact(text)[0]
                cur.screen = _screen_title(text)
                cur.ocr_excerpt = " / ".join(
                    " ".join(l.split()) for l in text.splitlines()[:6] if l.strip())[:300]
                cur.action, cur.action_text = _detect_action(text, cur.change,
                                                             cur.artifact, cur.activity)
            else:
                cur.action, cur.action_text = _detect_action("", cur.change,
                                                             cur.artifact, cur.activity)
            if shots and not cur.dead:
                shot = shots_dir / f"paso_{cur.index:03d}_{int(cur.start):05d}s.png"
                Image.fromarray(cur_rgb).save(shot)
                cur.shot = shot.name
        # Fusionar pasos demasiado cortos con el anterior (parpadeos de UI).
        if steps and cur.dur < min_step and not steps[-1].dead and not cur.dead:
            steps[-1].end = cur.end
        else:
            steps.append(cur)
        cur, cur_changes, cur_rgb = None, [], None

    while t < duration:
        try:
            container.seek(int(t * av.time_base), backward=True)
            frame = next(container.decode(vstream))
        except (StopIteration, av.AVError):
            break
        ts = float(frame.pts * vstream.time_base) if frame.pts is not None else t
        rgb = frame.to_ndarray(format="rgb24")
        sig = _signature(rgb)
        change = float(np.mean(np.abs(sig - last_sig))) if last_sig is not None else 255.0
        last_sig = sig
        people = _skin_frac(rgb) >= people_skin

        if cur is None or change >= change_threshold:
            close_step(ts)
            cur = Step(index=len(steps) + 1, start=ts, end=ts + step_seconds,
                      artifact="teams" if people else "otro")
            cur_rgb = rgb
            cur_changes = []
        else:
            cur_changes.append(change)
            if people:
                cur.artifact = "teams"
        t += step_seconds
        if t >= next_report:
            say(f"Flujo E2E {fmt_ts(min(t, duration))}/{fmt_ts(duration)} · "
                f"{len(steps)} pasos detectados")
            next_report += report_every
    close_step(min(t, duration) if duration else t)
    container.close()

    live = [s for s in steps if not s.dead]
    dead = len(steps) - len(live)
    say(f"Flujo E2E listo: {len(steps)} pasos ({len(live)} utiles, {dead} de espera descartados).")
    try:
        cache.write_text(json.dumps({"key": key, "pasos": [asdict(s) for s in steps]},
                                    ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return steps


def write_flow(steps: List[Step], out_dir: Path, video: Path, slug: str,
               date_string: str) -> Tuple[Path, Path]:
    """Persiste el flujo E2E (JSON + MD legible). Es la memoria del paso a paso."""
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / f"_flujo_e2e_{slug}.json"
    js.write_text(json.dumps({
        "video": video.name,
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha": date_string,
        "pasos_total": len(steps),
        "pasos_utiles": sum(1 for s in steps if not s.dead),
        "pasos": [asdict(s) for s in steps],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    md = out_dir / f"05_flujo_e2e_{slug}.md"
    lines = [
        f"# 05 · Flujo end-to-end paso a paso - {video.name}",
        "",
        f"- **Pasos detectados:** {len(steps)} "
        f"({sum(1 for s in steps if not s.dead)} útiles · "
        f"{sum(1 for s in steps if s.dead)} de espera descartados)",
        f"- **Generado:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "> Reconstrucción del proceso completo: cada paso es un estado real de pantalla, "
        "con su artefacto (web/HTML, planilla, código, tablero), la opción usada y la "
        "acción observada. Los tramos sin movimiento (esperas/cargas) se marcan y se "
        "descartan del montaje para que la demo avance.",
        "",
        "| # | Tramo | Pantalla/artefacto | Opción | Acción | Actividad | Captura |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in steps:
        etiqueta = ARTIFACT_LABEL.get(s.artifact, s.artifact)
        estado = "_(espera)_" if s.dead else s.action
        lines.append(
            f"| {s.index} | {fmt_ts(s.start)}–{fmt_ts(s.end)} | {etiqueta} | "
            f"{s.screen or '-'} | {estado} | {s.activity:.0%} | {s.shot or '-'} |")
    md.write_text("\n".join(lines), encoding="utf-8")
    return js, md


def steps_in_range(steps: List[Step], lo: float, hi: float,
                   min_dur: float = 0.0) -> List[Step]:
    """Pasos utiles (sin esperas ni personas) dentro de un tramo, en ORDEN cronologico."""
    return [s for s in steps
            if not s.dead and s.artifact != "teams"
            and s.end > lo and s.start < hi and s.dur >= min_dur]
