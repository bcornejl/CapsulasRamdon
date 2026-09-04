# ============================================================================
# html_to_video.py - agenteVideo modo 3: "Html a video"
#
# Convierte un HTML (por defecto el diagrama del ciclo de vida agentico Gluon,
# inbox/CicloVidaGluon/infografia.html) en un VIDEO DIDACTICO estilo Capsula
# Extensa: portada branded, voz IA MASCULINA (Bernardo Cornejo Lopez), el PRODUCTO
# como protagonista (sin personas) y cierre "La IA ejecuta. Las personas deciden.".
#
# Filosofia (prompt maestro): NO se graba el HTML sin entenderlo. Primero un
# DISCOVERY (que es, que hace, para quien, que problema resuelve, flujo, casos de
# uso, que es real vs simulado), luego STORYTELLING (storyboard + guion) y recien
# despues el VIDEO. El discovery se deja como evidencia en 01_discovery/ y
# 02_storytelling/; el video en 03_video/. Todo aterrizado (grounded), sin inventar.
#
# Render: reutiliza CapsuleRenderer de video_capsule (PyAV libx264+aac, sin ffmpeg
# del sistema) con items de imagen fija (una por paso) + tarjetas. Captura de las
# laminas: Playwright con el Edge del sistema (msedge), igual que capture_daily.py.
# ============================================================================

from __future__ import annotations

import re
import sys
import shutil
import unicodedata
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict

import numpy as np
from PIL import Image

from utils import Logger, ProjectPaths, normalize_date, date_tag
from narration import Narrator
from video_capsule import (CapsuleRenderer, decode_audio_file, item_seconds,
                           ReelProgress, RED, PRESENTER, BRAND)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_HTML = "inbox/CicloVidaGluon/infografia.html"

# Marca visual y frase de apertura FIJAS del modo 3 (el nombre va dinámico).
COVER_TITLE = "Cápsula flujo agéntico"
INTRO_FIJA = f"Soy {PRESENTER} y se explicará"
DEFAULT_PRESENTACION = "el flujo agéntico"


# ----------------------------------------------------------------------------
# Modelo del discovery (grounded): lo que se descubre del HTML antes de grabar.
# ----------------------------------------------------------------------------

@dataclass
class Step:
    """Un paso del recorrido = una lamina + su narracion a prueba de ninos."""
    phase: int
    label: str
    arc: str
    caption: str
    narr: str
    que_hace: str
    para_que: str
    resultado: str
    settle_ms: int = 1500


@dataclass
class HtmlProduct:
    """Discovery de un HTML: qué es, qué hace y cómo se cuenta en video."""
    slug: str
    nombre: str
    objetivo: str
    problema: str
    usuario: str
    proceso: str
    tecnologia: str
    ia_agentes: str
    logica: str
    integraciones: str
    flujo: str
    valor: str
    limitaciones: str
    real: List[str]
    simulado: List[str]
    funcionalidades: List[Dict]      # {nombre, evidencia_codigo, evidencia_visual, accion, resultado, valor}
    interacciones: List[Dict]        # {accion, elemento, resultado, funcion}
    casos_uso: List[Dict]            # {id, problema, solucion, ia, demo, resultado, valor, prioridad}
    steps: List[Step]
    intro_narr: str
    valor_narr: str
    subtitulo: str


# ----------------------------------------------------------------------------
# Discovery curado del diagrama del ciclo agentico (grounded: leido del HTML).
# ----------------------------------------------------------------------------

def _infografia_product(nombre: str) -> HtmlProduct:
    steps = [
        Step(0, "Onboarding y Definition of Ready", "PUNTO DE PARTIDA",
             "Paso 1 de 8 · Preparación (Definition of Ready)",
             "Primer paso: preparación. Antes de escribir una sola línea de código, el "
             "framework revisa que exista una historia de usuario clara, con su proyecto, "
             "su objetivo y su diseño. Toma lo que haya —un ticket, un correo, un documento, "
             "una captura o un enlace de Figma— y lo ordena. Si algo falta, lo marca como "
             "pregunta abierta en lugar de inventarlo. El resultado es una historia lista para "
             "trabajar; en el framework la llamamos Definition of Ready.",
             "Comprueba que exista una historia de usuario clara, con proyecto, objetivo y "
             "diseño, a partir de entradas heterogéneas (Jira, texto, Figma, capturas).",
             "No arrancar a ciegas: lo que falta se registra como pregunta abierta, no se inventa.",
             "Una HDU trazable y una Definition of Ready verificable."),
        Step(1, "Handoff, rules, MCP y presupuesto", "GOBIERNO",
             "Paso 2 de 8 · El orquestador toma el control",
             "Segundo paso: el orquestador toma el control. Es como un director de orquesta: "
             "carga la memoria de lo ya decidido, aplica las reglas obligatorias del banco y se "
             "conecta a las herramientas por un enchufe universal y seguro, que llamamos M C P. "
             "Además fija un presupuesto de trabajo. Así, todo lo que viene respeta las normas, "
             "no se sale del alcance y no gasta de más.",
             "El orquestador coordina a los especialistas con memoria, reglas, herramientas "
             "(MCP) y un presupuesto de trabajo.",
             "Que todo el proceso respete las normas del banco y mantenga el control del alcance.",
             "Un flujo gobernado, con memoria durable y límites explícitos."),
        Step(2, "Diseño, plan y contrato de evaluación", "PLAN",
             "Paso 3 de 8 · Pensar antes de construir",
             "Tercer paso: pensar antes de construir. Tres especialistas trabajan en fila. El "
             "analista aclara la historia; el arquitecto decide cómo resolverla; y el "
             "planificador la parte en cambios pequeños, archivo por archivo, con sus riesgos y "
             "sus pruebas. El resultado es un plan claro y editable, que una persona podrá "
             "aprobar, ajustar o rechazar.",
             "Analista, Arquitecto y Planificador convierten la historia en un diseño y un plan "
             "por archivo, pequeño y evaluable.",
             "Diseñar y planificar antes de escribir código; cada paso pequeño y revisable.",
             "Un plan editable y particionable, listo para aprobación humana."),
        Step(3, "Aprobación humana del plan", "DECISIÓN HUMANA",
             "Paso 4 de 8 · Primera puerta humana: aprobar el plan",
             "Cuarto paso, y es clave: aquí se detiene la máquina. Ninguna línea se construye "
             "todavía. El equipo revisa el plan y decide, punto por punto: aprobar, ajustar o "
             "rechazar. Esta es la primera gran puerta humana. Las personas mandan sobre el "
             "alcance y las prioridades; recién con su visto bueno se avanza.",
             "El equipo aprueba, modifica o rechaza cada ítem del plan; esa decisión queda como "
             "fuente de verdad.",
             "Que las personas conserven la soberanía sobre alcance y prioridades.",
             "El conjunto exacto de ítems autorizados para construir."),
        Step(4, "Desarrollo local gobernado, QA y seguridad", "CONSTRUCCIÓN",
             "Paso 5 de 8 · Construcción con calidad y seguridad",
             "Quinto paso: recién ahora se escribe el código, y solo dentro de lo aprobado. En "
             "paralelo, se prueba el comportamiento real —eso es Q A— y se revisa la seguridad "
             "contra los controles del banco. Calidad y seguridad desde el primer momento, no al "
             "final. Si una prueba falla, el trabajo no se declara terminado.",
             "El Desarrollador implementa dentro del alcance; QA prueba el comportamiento y "
             "Security evalúa los controles S-SDLC, en paralelo.",
             "Construir con calidad y seguridad desde el inicio, no al final.",
             "Código pequeño, probado y revisado; si una prueba falla, no hay PASS."),
        Step(5, "PR gate, revisión, DoD y evidencia", "REVISIÓN",
             "Paso 6 de 8 · Una segunda mirada independiente",
             "Sexto paso: una segunda mirada. Un revisor independiente, distinto de quien "
             "construyó, examina el cambio con ojos frescos, y se arma la propuesta con toda su "
             "evidencia: qué se probó, qué riesgos hay, qué queda pendiente. Nadie aprueba su "
             "propio trabajo; así se atrapan los errores silenciosos antes de que crezcan.",
             "Un Revisor independiente valida alcance y calidad; se arma el Pull Request con "
             "evidencia y Definition of Done.",
             "Que nadie apruebe su propio trabajo; una mirada fresca atrapa errores silenciosos.",
             "Una propuesta revisable, con pruebas y evidencia, lista para autorización."),
        Step(6, "Autorización humana de producción", "DECISIÓN HUMANA",
             "Paso 7 de 8 · Segunda puerta humana: autorizar producción",
             "Séptimo paso: la segunda gran puerta humana. Llevar algo a producción nunca es "
             "automático. El proceso se detiene hasta que la persona responsable autoriza de "
             "forma explícita. La decisión de mayor impacto siempre queda en manos de una "
             "persona, y queda registrada para poder auditarla.",
             "El pipeline se detiene hasta la autorización explícita del rol humano "
             "correspondiente para promover a producción.",
             "Que la promoción de mayor impacto nunca sea autónoma.",
             "Una decisión auditable de promover o no promover."),
        Step(7, "Despliegue, SLO y aprendizaje", "ENTREGA Y APRENDIZAJE",
             "Paso 8 de 8 · Entrega controlada y aprendizaje",
             "Octavo y último paso: la entrega y el aprendizaje. Se despliega el mismo "
             "artefacto, de forma controlada, verificando que todo opere bien, y con la "
             "posibilidad de revertir si algo se degrada. Y el ciclo se cierra aprendiendo: se "
             "miden señales reales y se proponen mejoras para la próxima vuelta. Entregamos con "
             "seguridad y mejoramos en cada iteración.",
             "Deploy controlado del mismo artefacto, observabilidad (SLO, métricas) y un learning "
             "loop que propone mejoras.",
             "Entregar con seguridad y mejorar en cada vuelta del ciclo.",
             "La versión en operación, con rollback disponible y lecciones para la próxima.",
             settle_ms=3200),
    ]
    return HtmlProduct(
        slug="Ciclo-Agentico-Gluon",
        nombre="Ciclo de vida agéntico (Gluon) — workflow ejecutivo de la Célula Agéntica",
        objetivo="Explicar, de principio a fin y sin tecnicismos, cómo la Célula Agéntica "
                 "desarrolla software con agentes de IA, con el gobierno del banco incorporado y "
                 "decisiones humanas en los puntos críticos.",
        problema="En un banco, desarrollar rápido choca con la trazabilidad, la seguridad y el "
                 "control; y suele malentenderse que 'usar IA' es solo escribir prompts. Falta un "
                 "relato claro de cómo se hace bien.",
        usuario="Jóvenes profesionales y nuevos integrantes de la célula (inducción), y audiencia "
                "ejecutiva del banco que necesita entender el modelo sin entrar al detalle técnico.",
        proceso="HDU → Onboarding/DoR → Orquestación gobernada → Diseño/Plan → Aprobación humana "
                "→ Desarrollo/QA/Seguridad → Revisión/PR → Autorización humana → Despliegue/"
                "Observabilidad/Aprendizaje.",
        tecnologia="HTML5 + CSS (custom properties, grid, animaciones), SVG (aristas y 'paquetes' "
                   "animados con getPointAtLength), JavaScript vanilla (bucle requestAnimationFrame "
                   "con máquina de estados phaseAt/applyPhase/updateStates/updatePackets) y Three.js "
                   "(partículas WebGL de fondo, con fallback 'no-webgl'). Sin frameworks.",
        ia_agentes="El diagrama representa un modelo AGÉNTICO real: un master agent (Orquestador) "
                   "coordina agentes especialistas (Analista, Arquitecto, Planificador, "
                   "Desarrollador, QA, Security, Revisor, Entrega, Observabilidad) con memoria, "
                   "reglas, herramientas (MCP) y dos puertas de decisión humana. No es un chatbot: "
                   "hay percepción, análisis, decisión, planificación, ejecución y validación.",
        logica="Máquina de estados por fases (8 fases con duración) que resalta nodos y aristas, "
               "mueve 'paquetes' por las conexiones y actualiza el % del ciclo. Los detalles de "
               "cada nodo (recibe/hace/entrega/control) están en el objeto estático nodeNotes.",
        integraciones="Ninguna en vivo: no hay llamadas fetch, WebSocket ni APIs reales en el "
                       "HTML. Los sistemas que menciona (Jira, Figma, repositorios, MCP, Gluon) son "
                       "el CONTEXTO que el framework describe, no integraciones activas de esta página.",
        flujo="Entrada heterogénea → historia lista (DoR) → orquestación con reglas y presupuesto "
              "→ diseño y plan por archivo → aprobación humana → construcción + QA + seguridad → "
              "revisión independiente + PR con evidencia → autorización humana → despliegue "
              "controlado + observabilidad + aprendizaje.",
        valor="Material de inducción y alineamiento: comunica el gobierno (S-SDLC, gates humanos, "
              "evidencia por etapa) a perfiles técnicos y de negocio, y deja explícito que 'la IA "
              "ejecuta y las personas deciden'. Para el banco: velocidad con gobierno.",
        limitaciones="Es una VISUALIZACIÓN educativa, no una aplicación operativa: no hay datos en "
                      "vivo ni ejecuta el ciclo; el fondo 3D requiere WebGL (con fallback). El % del "
                      "ciclo es una animación temporal, no el avance real de un proyecto.",
        real=["La visualización interactiva de las 8 fases y sus nodos.",
              "El detalle real del framework en cada nodo (recibe / hace / entrega / control).",
              "Las dos puertas de decisión humana (aprobación de plan y de producción).",
              "El estado de gobierno Gluon declarado: 17/78 controles (22%), 3 de 7 pilares."],
        simulado=["El 'flujo' animado (paquetes, líneas punteadas) ilustra el proceso, no ejecuta "
                  "software.",
                  "Las partículas y anillos 3D son decorativos.",
                  "El porcentaje 'CICLO HDU' avanza por tiempo (animación), no por progreso real.",
                  "Los sistemas externos (Jira, Figma, repos) se mencionan como contexto; no hay "
                  "integración activa en la página."],
        funcionalidades=[
            {"nombre": "Recorrido por fases", "evidencia_codigo": "phases[], phaseAt(), applyPhase(), tick() (rAF)",
             "evidencia_visual": "barra superior 'CICLO HDU %', etiqueta 'AGENTE EN EJECUCIÓN'",
             "accion": "Reproducir / ?phase=N", "resultado": "Resalta la fase activa y completa las previas",
             "valor": "Se entiende el proceso de principio a fin"},
            {"nombre": "Detalle de cada nodo (modal)", "evidencia_codigo": "openNodeModal(), nodeNotes{}",
             "evidencia_visual": "modal con Kicker/Recibe/Hace/Entrega/Control",
             "accion": "Click en un nodo", "resultado": "Abre el detalle y pausa la animación",
             "valor": "Profundiza sin perder el mapa general"},
            {"nombre": "Controles de reproducción", "evidencia_codigo": "setPaused(), jump(delta)",
             "evidencia_visual": "botones play/pausa y anterior/siguiente",
             "accion": "Play/Pausa/Prev/Next", "resultado": "Controla o salta de fase",
             "valor": "Permite explicar a ritmo propio"},
            {"nombre": "Resalte de nodos y aristas", "evidencia_codigo": "updateStates(), setNodeState()",
             "evidencia_visual": "nodos activos (azul) y completados (verde)",
             "accion": "Avance de fase", "resultado": "Marca activo/completo y anima las conexiones",
             "valor": "Muestra dependencias y avance"},
            {"nombre": "Fondo agéntico 3D", "evidencia_codigo": "initThree() (Three.js, fallback no-webgl)",
             "evidencia_visual": "partículas y anillos de fondo",
             "accion": "Automático", "resultado": "Ambiente visual (decorativo)",
             "valor": "Estética ejecutiva; no aporta lógica"},
        ],
        interacciones=[
            {"accion": "Click", "elemento": "Nodo del flujo", "resultado": "Abre modal de detalle y pausa", "funcion": "Profundizar"},
            {"accion": "Click", "elemento": "Play / Pausa", "resultado": "Reanuda o congela la animación", "funcion": "Control"},
            {"accion": "Click", "elemento": "Anterior / Siguiente", "resultado": "Salta a otra fase", "funcion": "Navegación"},
            {"accion": "Parámetro URL", "elemento": "?phase=N / ?paused", "resultado": "Inicia en una fase / pausado", "funcion": "Presentación"},
            {"accion": "Hover / foco", "elemento": "Nodo", "resultado": "Resalta el nodo", "funcion": "Orientación"},
            {"accion": "Automático", "elemento": "Barra de progreso", "resultado": "Muestra el % del ciclo", "funcion": "Avance"},
        ],
        casos_uso=[
            {"id": "CU-01", "problema": "Arrancar sin una historia clara", "solucion": "Onboarding + Definition of Ready",
             "ia": "El framework normaliza la HDU y detecta vacíos", "demo": "Fase 1 (entrada → DoR)",
             "resultado": "HDU trazable y lista", "valor": "Menos retrabajo", "prioridad": "A"},
            {"id": "CU-02", "problema": "Perder el control al usar agentes", "solucion": "Orquestación gobernada",
             "ia": "Orquestador con memoria, reglas, MCP y presupuesto", "demo": "Fase 2",
             "resultado": "Flujo con límites explícitos", "valor": "Gobierno incorporado", "prioridad": "A"},
            {"id": "CU-03", "problema": "Construir sin pensar", "solucion": "Diseño y plan por archivo",
             "ia": "Analista + Arquitecto + Planificador", "demo": "Fase 3",
             "resultado": "Plan pequeño y evaluable", "valor": "Cambios revisables", "prioridad": "A"},
            {"id": "CU-04", "problema": "Que la IA decida sola", "solucion": "Puerta humana de aprobación",
             "ia": "La máquina se detiene y espera decisión", "demo": "Fase 4",
             "resultado": "Ítems autorizados por personas", "valor": "Soberanía humana", "prioridad": "A"},
            {"id": "CU-05", "problema": "Calidad y seguridad tardías", "solucion": "Desarrollo local + QA + Security",
             "ia": "Construcción acotada, pruebas y controles S-SDLC", "demo": "Fase 5",
             "resultado": "Código probado y seguro", "valor": "Calidad desde el inicio", "prioridad": "A"},
            {"id": "CU-06", "problema": "Auto-aprobar el trabajo", "solucion": "Revisión independiente + PR",
             "ia": "Revisor distinto + evidencia y DoD", "demo": "Fase 6",
             "resultado": "Propuesta revisable con evidencia", "valor": "Menos errores silenciosos", "prioridad": "A"},
            {"id": "CU-07", "problema": "Despliegue autónomo a producción", "solucion": "Autorización humana",
             "ia": "El pipeline se detiene hasta autorizar", "demo": "Fase 7",
             "resultado": "Decisión auditable", "valor": "Control del mayor riesgo", "prioridad": "A"},
            {"id": "CU-08", "problema": "Entregar y olvidar", "solucion": "Despliegue + observabilidad + aprendizaje",
             "ia": "Deploy controlado, SLO y learning loop", "demo": "Fase 8",
             "resultado": "Operación con rollback y lecciones", "valor": "Mejora continua", "prioridad": "A"},
            {"id": "CU-09", "problema": "El detalle se pierde en el mapa", "solucion": "Modal por nodo (recibe/hace/entrega/control)",
             "ia": "Detalle real del framework por agente", "demo": "Click en cualquier nodo",
             "resultado": "Explicación a demanda", "valor": "Profundizar sin perder contexto", "prioridad": "B"},
            {"id": "CU-10", "problema": "No saber cuánto se ha avanzado en gobierno", "solucion": "Estado Gluon 17/78",
             "ia": "Controles automáticos/manuales/externos, sin confundir hechos con proyecciones", "demo": "Nodo Gobierno Gluon",
             "resultado": "Corte 17 cumplidos / 19 en proceso / 42 pendientes", "valor": "Transparencia del avance", "prioridad": "B"},
        ],
        steps=steps,
        intro_narr=(
            f"{INTRO_FIJA} {nombre}. Vamos a verlo paso a paso y sin tecnicismos, de principio a "
            "fin y con el gobierno del banco incorporado. Partamos de algo simple: en un banco "
            "hay que ir rápido, pero también ser trazables, seguros y controlados; y muchas veces "
            "se cree que usar inteligencia artificial es solo escribir prompt y prompt. Este ciclo "
            "demuestra lo contrario. La inteligencia artificial ejecuta; las personas deciden. "
            "Acompáñame en el recorrido completo."),
        valor_narr=(
            "Ese es el recorrido completo. La Célula Agéntica convierte una idea en software en "
            "operación —pasando por diseño, plan, construcción, calidad, seguridad y despliegue— "
            "sin perder nunca el control. Cada etapa deja evidencia, dos puertas humanas "
            "garantizan que nada avanza sin aprobación, y en cada vuelta el sistema aprende. Para "
            "el banco, esto significa velocidad con gobierno: más rápido, más trazable y más "
            "seguro. Recuérdalo siempre: la inteligencia artificial ejecuta; las personas deciden."),
        subtitulo=nombre,
    )


# ----------------------------------------------------------------------------
# Captura de las láminas con Playwright (Edge del sistema, sin descargar nada).
# ----------------------------------------------------------------------------

def _launch(pw):
    try:
        return pw.chromium.launch(channel="msedge", headless=True)
    except Exception:
        return pw.chromium.launch(headless=True)


def capture_phases(html_path: Path, shots: Path, steps: List[Step],
                   settle_ms: int, dsf: int, logger,
                   progress: Optional[ReelProgress] = None) -> Dict[int, Path]:
    """Captura una lámina por fase del diagrama (?phase=N). Devuelve {phase: png}."""
    from playwright.sync_api import sync_playwright
    shots.mkdir(parents=True, exist_ok=True)
    base = html_path.resolve().as_uri()
    out: Dict[int, Path] = {}
    with sync_playwright() as pw:
        browser = _launch(pw)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  device_scale_factor=dsf,
                                  reduced_motion="no-preference")
        pg = ctx.new_page()
        for st in steps:
            pg.goto(f"{base}?phase={st.phase}", wait_until="load")
            pg.wait_for_timeout(max(settle_ms, st.settle_ms))
            png = shots / f"fase_{st.phase}.png"
            pg.locator(".canvas").first.screenshot(path=str(png))
            out[st.phase] = png
            msg = f"Lámina fase {st.phase} capturada: {st.label}"
            progress.log(msg) if progress else logger.info(msg)
        browser.close()
    return out


def capture_single(html_path: Path, shots: Path, dsf: int, logger) -> Path:
    """Captura genérica de un HTML cualquiera: mejor selector visible o página completa."""
    from playwright.sync_api import sync_playwright
    shots.mkdir(parents=True, exist_ok=True)
    url = html_path.resolve().as_uri()
    png = shots / "pagina.png"
    with sync_playwright() as pw:
        browser = _launch(pw)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900},
                                  device_scale_factor=dsf,
                                  reduced_motion="no-preference")
        pg = ctx.new_page()
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(1200)
        shot = False
        for sel in (".canvas", ".deck", ".slide", "main", "body"):
            loc = pg.locator(sel).first
            try:
                if loc.count() and loc.is_visible():
                    loc.screenshot(path=str(png))
                    shot = True
                    break
            except Exception:
                continue
        if not shot:
            pg.screenshot(path=str(png), full_page=True)
        browser.close()
    logger.info(f"Captura genérica: {png.name}")
    return png


# ----------------------------------------------------------------------------
# Entregables de discovery + storytelling (grounded, sin inventar).
# ----------------------------------------------------------------------------

def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_discovery(disc: Path, story: Path, p: HtmlProduct, html_path: Path,
                    tag: str, video_name: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    src = f"`{html_path.as_posix()}`"

    _w(disc / "00_resumen_ejecutivo.md", f"""
# 00 · Resumen ejecutivo — {p.nombre}

- **Fuente:** {src} · **Generado:** {stamp}

**¿QUÉ ES?** {p.nombre}. Una visualización educativa e interactiva del ciclo de vida
del software desarrollado con agentes de IA (el "workflow ejecutivo" de la Célula Agéntica).

**¿PARA QUIÉN?** {p.usuario}

**¿QUÉ PROBLEMA RESUELVE?** {p.problema}

**¿CÓMO FUNCIONA?** {p.flujo}

**¿QUÉ HACE EL AGENTE?** {p.ia_agentes}

**¿CUÁLES SON LOS CASOS DE USO?** {len(p.casos_uso)} casos demostrables (ver 04): las 8
fases del ciclo, el detalle por nodo y el estado de gobierno Gluon.

**¿CUÁL ES EL VALOR?** {p.valor}

**¿QUÉ PARTE ES REAL?** {' '.join('· ' + r for r in p.real)}

**¿QUÉ PARTE ES SIMULADA?** {' '.join('· ' + s for s in p.simulado)}
""")

    _w(disc / "01_discovery_producto.md", f"""
# 01 · Discovery del producto

- **Fuente:** {src} · **Generado:** {stamp}

## Nombre
{p.nombre}

## Objetivo
{p.objetivo}

## Problema
{p.problema}

## Usuario objetivo
{p.usuario}

## Proceso
{p.proceso}

## Tecnología detectada
{p.tecnologia}

## IA / Agentes
{p.ia_agentes}

## Lógica (de presentación)
{p.logica}

## Integraciones
{p.integraciones}

## Flujo End-to-End
{p.flujo}

## Valor para el banco
{p.valor}

## Limitaciones
{p.limitaciones}

## Qué es REAL (del propio HTML)
{chr(10).join('- ' + r for r in p.real)}

## Qué es SIMULADO / decorativo
{chr(10).join('- ' + s for s in p.simulado)}
""")

    rows = "\n".join(f"| {i['accion']} | {i['elemento']} | {i['resultado']} | {i['funcion']} |"
                     for i in p.interacciones)
    _w(disc / "02_mapa_interacciones.md", f"""
# 02 · Mapa de interacciones

- **Fuente:** {src} · **Generado:** {stamp}

| Acción | Elemento | Resultado | Función |
|---|---|---|---|
{rows}

> El HTML no realiza llamadas a APIs reales (sin `fetch`/WebSocket): las interacciones
> operan sobre estado y datos estáticos del propio archivo.
""")

    frows = "\n".join(
        f"| {f['nombre']} | {f['evidencia_codigo']} | {f['evidencia_visual']} | "
        f"{f['accion']} | {f['resultado']} | {f['valor']} |" for f in p.funcionalidades)
    _w(disc / "03_matriz_funcionalidades.md", f"""
# 03 · Matriz de funcionalidades

- **Fuente:** {src} · **Generado:** {stamp}

| Funcionalidad | Evidencia en código | Evidencia visual | Acción usuario | Resultado | Valor |
|---|---|---|---|---|---|
{frows}
""")

    crows = "\n".join(
        f"| {c['id']} | {c['problema']} | {c['solucion']} | {c['ia']} | {c['demo']} | "
        f"{c['resultado']} | {c['valor']} | {c['prioridad']} |" for c in p.casos_uso)
    _w(disc / "04_matriz_casos_uso.md", f"""
# 04 · Matriz de casos de uso

- **Fuente:** {src} · **Generado:** {stamp}

| Caso | Problema | Solución | IA / Agente | Demo visual | Resultado | Valor | Prioridad |
|---|---|---|---|---|---|---|---|
{crows}

> Prioridad: **A** muy alto valor · **B** alto valor · **C** complementario · **D** bajo valor.
""")

    sb = ["# 05 · Storyboard", "", f"- **Fuente:** {src} · **Generado:** {stamp}", "",
          "Arco: **PROBLEMA → SOLUCIÓN → AGENTE → ACCIÓN → RESULTADO → VALOR** "
          "(el producto es el protagonista; sin personas).", "",
          "| Bloque | Contenido | Lámina |", "|---|---|---|",
          "| Portada + intro | Presentador Bernardo Cornejo López · problema y objetivo | Tarjeta branded |"]
    for st in p.steps:
        sb.append(f"| {st.arc} | {st.label} | Fase {st.phase} (`?phase={st.phase}`) |")
    sb += ["| RESULTADO / VALOR | El ciclo completo y su impacto para el banco | Fase 8 (cierre) |",
           "| Cierre | «La IA ejecuta. Las personas deciden.» | Tarjeta co-brand |", ""]
    _w(story / "05_storyboard.md", "\n".join(sb))

    gv = [f"# 06 · Guion del video — {p.nombre}", "",
          f"- **Fuente:** {src} · **Generado:** {stamp}",
          "- **Presentador:** Bernardo Cornejo López · **Voz:** IA masculina (es-MX-JorgeNeural)",
          f"- **Salida:** `{video_name}`", "",
          "## Portada (intro)", "", f"> {p.intro_narr}", ""]
    for st in p.steps:
        gv += [f"## {st.caption}", "",
               f"**¿Qué hace?** {st.que_hace}", "",
               f"**¿Para qué sirve?** {st.para_que}", "",
               f"**¿Cuál es el resultado?** {st.resultado}", "",
               "Narración:", "", f"> {st.narr}", ""]
    gv += ["## Cierre (resultado y valor)", "", f"> {p.valor_narr}", "",
           "> Tarjeta final: «La IA ejecuta. Las personas deciden.»", ""]
    _w(story / "06_guion_video.md", "\n".join(gv))


# ----------------------------------------------------------------------------
# Montaje del video (reutiliza CapsuleRenderer: portada + láminas + cierre).
# ----------------------------------------------------------------------------

def _slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-") or "Html"


def build_video(renderer: CapsuleRenderer, narrator: Optional[Narrator],
                p: HtmlProduct, frames: Dict[int, Path], out_path: Path,
                narr_dir: Path, logger) -> Optional[Dict]:
    """Portada branded → una lámina por paso (voz por paso) → cierre co-brand."""
    def synth(text: str, name: str) -> Optional[np.ndarray]:
        if narrator is None or not text:
            return None
        wav = narrator.synthesize(text, narr_dir / name)
        arr = decode_audio_file(wav) if wav else None
        if arr is not None:
            pk = float(np.max(np.abs(arr))) or 1.0
            arr = (arr * (0.95 / pk)).astype(np.float32)
        return arr

    items: List[Dict] = []

    intro = synth(p.intro_narr, "intro")
    items.append({"kind": "card", "title": COVER_TITLE,
                  "subtitle": p.subtitulo, "footer": f"Realizado por {PRESENTER}",
                  "badge": "", "accent": RED, "brand": BRAND,
                  "title_size": 0.13, "base": item_seconds(5.0, intro), "narr": intro})

    for st in p.steps:
        png = frames.get(st.phase)
        if png is None:
            continue
        narr = synth(st.narr, f"fase_{st.phase}")
        items.append({"kind": "image", "image": png, "caption": st.caption,
                      "base": item_seconds(4.0, narr), "narr": narr})

    # Cierre: última lámina (ciclo completo) con el mensaje de valor.
    last = p.steps[-1].phase
    if last in frames:
        valor = synth(p.valor_narr, "valor")
        items.append({"kind": "image", "image": frames[last],
                      "caption": "Ciclo completo · La IA ejecuta, las personas deciden",
                      "base": item_seconds(4.0, valor), "narr": valor})

    items.append({"kind": "card", "title": "La IA ejecuta.\nLas personas deciden.",
                  "subtitle": f"{p.subtitulo} · Resultado real de la sesión",
                  "footer": BRAND, "badge": "", "accent": RED,
                  "title_size": 0.10, "base": 4.0, "narr": None})

    if not renderer.render_items(None, items, out_path):
        return None
    total = sum(it["nvf"] for it in items) / renderer.fps
    voice = f"{narrator.voice} ({narrator.backend})" if (narrator and narrator.backend) else None
    return {"total": total, "voice": voice, "steps": len(p.steps)}


def write_rundown(path: Path, p: HtmlProduct, html_path: Path, tag: str,
                  total: float, voice: Optional[str]) -> None:
    lines = [
        f"# Html a video — {p.nombre} ({tag})", "",
        f"- **HTML de origen:** `{html_path.as_posix()}`",
        f"- **Duración:** ~{total:.0f}s ({len(p.steps)} pasos + portada + cierre)",
        f"- **Voz en off:** {voice or '(sin narración)'}",
        f"- **Presentador:** Bernardo Cornejo López (voz IA masculina)",
        f"- **Generado:** {datetime.now():%Y-%m-%d %H:%M:%S}", "",
        "## Recorrido (paso a paso del diagrama)", "",
        "| Paso | Lámina (fase) | Foco |", "|---|---|---|",
    ]
    for st in p.steps:
        lines.append(f"| {st.arc} | {st.label} | {st.para_que} |")
    lines += ["", "> Video didáctico (a prueba de principiantes) del diagrama; el producto es el "
              "protagonista, sin personas. La voz explica cada paso: qué hace, para qué sirve y "
              "cuál es el resultado. Grounded en el HTML, sin inventar.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------
# Entrada: /agenteVideo --mode html
# ----------------------------------------------------------------------------

def run(args, paths: ProjectPaths, logger: Logger, date_string: str) -> int:
    tag = date_tag(date_string)
    logger.section(f"agenteVideo - Html a video {tag}")

    html_path = Path(args.html) if getattr(args, "html", None) else (paths.root / DEFAULT_HTML)
    if not html_path.is_absolute():
        html_path = (paths.root / html_path).resolve()
    if not html_path.exists():
        logger.error(f"No existe el HTML: {html_path}")
        return 1
    logger.info(f"HTML: {html_path}")

    month = datetime.strptime(date_string, "%Y-%m-%d").strftime("%m-%Y")
    out_root = paths.presentacion / "ReporteVideo" / month / "Html-a-video"
    disc_dir = out_root / "01_discovery"
    story_dir = out_root / "02_storytelling"
    video_dir = out_root / "03_video"
    shots = out_root / "_shots"
    narr_dir = paths.root / "output" / "_narration_html"

    fps = getattr(args, "fps", 24)
    height = getattr(args, "height", 720)
    width = int(round(height * 16 / 9))
    voice = getattr(args, "voice", None) or "es-MX-JorgeNeural"
    if voice == "es-MX-DaliaNeural":            # default femenino de screenshot → masculino
        voice = "es-MX-JorgeNeural"
    no_narration = bool(getattr(args, "no_narration", False))
    dsf = 2
    settle_ms = int(getattr(args, "settle_ms", 1500) or 1500)
    nombre = (getattr(args, "presentacion", None) or "").strip() or DEFAULT_PRESENTACION
    logger.info(f"Presentación: {nombre}")

    # ¿Es el diagrama del ciclo (fases) u otro HTML cualquiera?
    try:
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        html_text = ""
    is_infografia = ("phaseNodes" in html_text) or ("infografia" in html_path.name.lower())

    renderer = CapsuleRenderer(logger, width=width, height=height, fps=fps,
                               with_audio=True, with_cards=True, with_captions=True,
                               date_label=tag, mute_original=True, still=True, kenburns=False)
    narrator = None if no_narration else Narrator(logger, voice=voice)

    progress = ReelProgress(out_root / f"_progreso-html-{tag}.log", logger)
    progress.phase("DISCOVERY - análisis del HTML")

    if is_infografia:
        product = _infografia_product(nombre)
        vid_name = f"Capsula-{product.slug}-{tag}.mp4"
        out_video = video_dir / vid_name
        write_discovery(disc_dir, story_dir, product, html_path, tag, vid_name)
        progress.log(f"Discovery + storytelling escritos ({len(product.casos_uso)} casos de uso).")

        progress.phase("CAPTURA - una lámina por fase")
        frames = capture_phases(html_path, shots, product.steps, settle_ms, dsf, logger, progress)

        progress.phase("RENDER - portada + 8 pasos + cierre")
        res = build_video(renderer, narrator, product, frames, out_video, narr_dir, logger)
        if not res:
            logger.error("No se pudo generar el video.")
            return 1
        write_rundown(out_video.with_suffix(".md"), product, html_path, tag,
                      res["total"], res["voice"])
        shutil.rmtree(narr_dir, ignore_errors=True)
        progress.phase(f"LISTO - {out_video.name} (~{res['total']:.0f}s)")
        logger.success(f"Html a video listo (~{res['total']:.0f}s): {out_video}")
        logger.info(f"Discovery: {disc_dir}  ·  Storytelling: {story_dir}")
        return 0

    # HTML genérico: una lámina + guion (curado con --script-file o genérico honesto).
    progress.phase("CAPTURA - página genérica")
    png = capture_single(html_path, shots, dsf, logger)
    script = None
    if getattr(args, "script_file", None):
        try:
            script = Path(args.script_file).read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"No se pudo leer --script-file ({e}).")
    if not script:
        script = (f"{INTRO_FIJA} {nombre}. Veremos qué muestra esta interfaz, para qué sirve y "
                  "qué valor entrega. El producto es el protagonista; la inteligencia artificial "
                  "ejecuta y las personas deciden.")
    narr = None
    if narrator is not None:
        wav = narrator.synthesize(script, narr_dir / "guion")
        narr = decode_audio_file(wav) if wav else None
    slug = _slug(html_path.stem)
    out_video = video_dir / f"Capsula-{slug}-{tag}.mp4"
    items = [
        {"kind": "card", "title": COVER_TITLE,
         "subtitle": nombre, "footer": f"Realizado por {PRESENTER}",
         "badge": "", "accent": RED, "brand": BRAND,
         "title_size": 0.13, "base": 4.5, "narr": None},
        {"kind": "image", "image": png, "caption": html_path.stem,
         "base": item_seconds(6.0, narr), "narr": narr},
        {"kind": "card", "title": "La IA ejecuta.\nLas personas deciden.",
         "subtitle": f"{nombre} · Resultado real de la sesión",
         "footer": BRAND, "badge": "", "accent": RED,
         "title_size": 0.10, "base": 4.0, "narr": None},
    ]
    progress.phase("RENDER - página genérica")
    if not renderer.render_items(None, items, out_video):
        logger.error("No se pudo generar el video.")
        return 1
    shutil.rmtree(narr_dir, ignore_errors=True)
    progress.phase(f"LISTO - {out_video.name}")
    logger.success(f"Html a video listo: {out_video}")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="agenteVideo modo 3: Html a video (renderiza un HTML/diagrama a un "
                    "video didáctico con voz IA masculina, el producto como protagonista).")
    ap.add_argument("--html", type=str, help=f"Ruta del HTML (default: {DEFAULT_HTML})")
    ap.add_argument("--date", type=str, help="Fecha 'hoy'/DD-MM-AAAA/AAAA-MM-DD (default: hoy)")
    ap.add_argument("--presentacion", type=str,
                    help="Nombre de la presentación (va en la narración: 'Soy Bernardo Cornejo "
                         "López y se explicará <nombre>')")
    ap.add_argument("--voice", type=str, default="es-MX-JorgeNeural",
                    help="Voz IA (default masculina es-MX-JorgeNeural)")
    ap.add_argument("--settle-ms", type=int, default=1500, help="ms de espera por fase")
    ap.add_argument("--no-narration", action="store_true", help="Sin voz en off")
    ap.add_argument("--script-file", type=str, help="(HTML genérico) narración desde archivo UTF-8")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()
    paths = ProjectPaths()
    logger = Logger(paths.log_file)
    return run(args, paths, logger, normalize_date(args.date))


if __name__ == "__main__":
    sys.exit(main())
