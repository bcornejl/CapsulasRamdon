# ============================================================================
# reel_themes.py - Discovery + reels EDUCATIVOS del agenteVideo (modo reel)
#
# El modo reel primero hace un DISCOVERY del video completo (la operacion mas
# larga) y, en base al CONTEXTO real, lo DESFRAGMENTA dinamicamente en casos de
# uso -> uno o mas reels educativos "a prueba de ninos". No hay un numero fijo:
# pueden salir 2, 4 o mas reels segun lo que el video realmente muestre.
#
# SOLO PANTALLA: los reels muestran la PROYECCION EN PANTALLA (el producto
# agentico y el trabajo del equipo); NUNCA las camaras/personas de la reunion.
#
# Cada reel ensena UNA capacidad con la estructura tipica de la educacion, en
# detalle y con gancho de VENTA para la gerencia del banco:
#   1) ¿QUE HACE?   2) ¿PARA QUE / PROPOSITO?   3) EJEMPLO simple
#   4) ¿CUAL ES EL RESULTADO?   5) ¿POR QUE LE CONVIENE AL BANCO?
#
# Idea central que atraviesa todo:
#   La IA agentica NO es "prompt y prompt". Es una herramienta que AMPLIFICA las
#   habilidades de las personas. La IA ejecuta; las personas deciden.
# ============================================================================

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Callable


def _rx(*patterns: str) -> List[Pattern]:
    """Compila las senales (regex, sin distinguir mayusculas) de una capacidad."""
    return [re.compile(p, re.I) for p in patterns]


# Estructura educativa visible: los tres actos del reel (¿que hace/proposito/resultado).
ACT_LABELS = ["¿Qué hace?", "¿Para qué sirve?", "¿Cuál es el resultado?"]

CIERRE = ("En resumen: el Framework Agéntico no reemplaza a las personas, amplifica lo "
          "que saben hacer. La inteligencia artificial ejecuta; las personas deciden. "
          "Gracias por acompañarme en esta Cápsula Extensa de la Célula Agéntica.")


@dataclass(eq=False)
class ReelTheme:
    """Una capacidad enseñable: qué hace, para qué, con qué ejemplo, resultado y valor.

    `eq=False` la hace hashable por identidad (se usa como clave de dict).
    """
    slug: str                       # nombre de archivo (Reel-<slug>-DD-MM-AAAA.mp4)
    title: str                      # subtitulo de la portada
    caption: str                    # subtitulo corto (respaldo) sobre los clips
    hook: str                       # frase de apertura de la narracion
    que_hace: str                   # acto 1: que es / que hace (a prueba de ninos)
    proposito: str                  # acto 2: para que sirve (angulo banco)
    resultado: str                  # acto 3: cual es el resultado concreto
    ejemplo: str = ""               # ejemplo simple "a prueba de ninos"
    valor: str = ""                 # por que le conviene al banco (venta)
    pregunta: str = ""              # la pregunta que surge (Q&A reconstruido, voz IA)
    cues: List[Pattern] = field(default_factory=list)   # senales OCR de la capacidad
    artifacts: List[str] = field(default_factory=list)  # artefactos que suman
    priority: int = 5               # orden de relleno (menor = primero)

    @property
    def script(self) -> str:
        """Narracion como BERNARDO CORNEJO LOPEZ (voz IA masculina). Arco de venta:
        Contexto -> Pregunta -> Respuesta -> Demostracion -> Resultado -> Valor banco,
        explicado a prueba de ninos."""
        preg = self.pregunta or f"¿Cómo funciona {self.title.lower()} y qué gano con esto?"
        parts = [
            "Cápsula Extensa. Célula Agéntica.",
            self.hook,
            "Veamos primero el contexto.", self.que_hace,
            "La pregunta que suele surgir es esta:", preg,
            "Y la respuesta, en simple, es la siguiente.", self.proposito,
        ]
        if self.ejemplo:
            parts += ["Mirémoslo con un ejemplo bien sencillo, a prueba de niños.", self.ejemplo]
        parts += ["Entonces, ¿cuál es el resultado?", self.resultado]
        if self.valor:
            parts += ["¿Y qué significa esto para el banco?", self.valor]
        parts.append(CIERRE)
        return " ".join(p for p in parts if p)

    def act_caption(self, act: int) -> str:
        """Subtitulo del acto (0/1/2) = ¿que hace? / proposito / resultado + tema."""
        act = max(0, min(2, act))
        return f"{ACT_LABELS[act]} · {self.title}"

    def matches(self, cand) -> bool:
        """¿El momento MUESTRA esta capacidad? Requiere una senal REAL de texto (OCR)."""
        txt = getattr(cand, "ocr_text", "") or ""
        return any(p.search(txt) for p in self.cues)

    def score(self, cand) -> float:
        """Ranking de un momento para esta capacidad (cues + artefacto + value)."""
        txt = getattr(cand, "ocr_text", "") or ""
        art = getattr(cand, "artifact", "otro")
        s = 0.0
        for pat in self.cues:
            if pat.search(txt):
                s += 2.0
        if art in self.artifacts:
            s += 1.5
        s += 0.2 * float(getattr(cand, "value", 0.0))
        return s


# ----------------------------------------------------------------------------
# Catalogo de capacidades enseñables. Guiones RICOS y detallados (~3-4 min) para
# VENDER el producto agentico al banco. El discovery elige las que el video muestra.
# ----------------------------------------------------------------------------

EDUCATIONAL_REELS: List[ReelTheme] = [
    ReelTheme(
        slug="Que-es-un-Agente",
        title="¿Qué es un agente?",
        caption="¿Qué es un agente? · La IA que ejecuta",
        priority=0,
        hook=("Bienvenidos a la Célula Agéntica. Antes de ver la herramienta en acción, "
              "tomémonos un momento para entender la idea, sin ningún tecnicismo."),
        pregunta="¿Qué es exactamente un agente, y en qué se diferencia de la inteligencia artificial de siempre?",
        que_hace=(
            "Un agente de inteligencia artificial es como un colega digital que trabaja a "
            "tu lado. La inteligencia artificial tradicional, la que casi todos conocen, "
            "responde preguntas: tú preguntas, ella contesta. Un agente va mucho más allá: "
            "recibe un objetivo, arma un plan, ejecuta las tareas una por una y revisa su "
            "propio trabajo antes de entregarlo. Es la diferencia entre alguien que te da "
            "un consejo y alguien que de verdad hace la tarea contigo."
        ),
        proposito=(
            "El propósito no es reemplazar a las personas; es todo lo contrario. Se trata "
            "de quitarles de encima el trabajo repetitivo y mecánico para que dediquen su "
            "talento a lo que de verdad importa: pensar, decidir y crear. Y aquí va la idea "
            "más importante de todo este material: esto no es escribir instrucciones sin "
            "parar. El Framework Agéntico es una herramienta que amplifica las habilidades "
            "de cada persona del equipo, igual que una calculadora potencia a un contador "
            "sin quitarle el criterio."
        ),
        ejemplo=(
            "Imagina que le pides a un ayudante que prepare un informe. Un asistente común "
            "te diría cómo hacerlo. Un agente, en cambio, abre las herramientas, reúne los "
            "datos, arma el borrador, corrige los errores y te lo deja listo para revisar. "
            "Tú sigues siendo quien aprueba y decide; él hace el trabajo pesado en una "
            "fracción del tiempo."
        ),
        resultado=(
            "El resultado es un equipo que avanza más rápido, con menos errores y con las "
            "personas enfocadas en lo estratégico. En nuestro caso, así es como la Célula "
            "construye el Digital Host, el producto que activa a los nuevos clientes del "
            "banco."
        ),
        valor=(
            "Para el banco, esto significa entregar más rápido, con mayor calidad y con "
            "trazabilidad de cada paso. Es hacer más con el mismo equipo, sin sacrificar el "
            "control ni la seguridad."
        ),
        cues=_rx(r"\bagente[s]?\b", r"ag[eé]ntic", r"\bdevin\b", r"\bcopilot\b",
                 r"framework", r"c[eé]lula"),
        artifacts=[],
    ),
    ReelTheme(
        slug="Panel-Cascade",
        title="El panel Cascade",
        caption="Panel Cascade · Planificar antes de ejecutar",
        priority=1,
        hook="Ahora entremos al panel Cascade, una de las piezas más importantes del framework.",
        pregunta="¿Cómo sabemos qué va a hacer la inteligencia artificial antes de que lo haga?",
        que_hace=(
            "Cascade es el lugar donde el agente piensa en voz alta antes de actuar. En vez "
            "de lanzarse a programar de inmediato, primero escribe su plan de trabajo, paso "
            "por paso, y lo muestra en pantalla. Cada paso queda a la vista: qué va a tocar, "
            "en qué orden y por qué. Es, literalmente, el plano de la obra antes de poner el "
            "primer ladrillo."
        ),
        proposito=(
            "Sirve para que nada, absolutamente nada, se ejecute a ciegas. Una persona del "
            "equipo revisa ese plan, lo aprueba o lo corrige, y recién entonces el agente "
            "avanza. En un banco, donde un error puede costar caro, esta transparencia no "
            "es un lujo: es la base de la confianza."
        ),
        ejemplo=(
            "Piensa en un cirujano que, antes de operar, explica cada paso a su equipo y "
            "espera el visto bueno. Si algo no cuadra, se corrige antes de empezar, no a "
            "mitad de camino. Cascade hace exactamente eso con el software: primero el plan "
            "claro, luego la ejecución, sin sorpresas."
        ),
        resultado=(
            "El resultado es que una preparación que antes tomaba horas queda lista en "
            "minutos, con cada decisión registrada y explicada. Si mañana alguien pregunta "
            "por qué se hizo algo, la respuesta está escrita."
        ),
        valor=(
            "Para el banco, esto significa control total y auditoría natural: se ve qué va a "
            "hacer la inteligencia artificial antes de que lo haga, y queda evidencia de "
            "todo. Velocidad con gobierno, que es justo lo que exige un entorno regulado."
        ),
        cues=_rx(r"cascad[ae]", r"waterfall", r"\bplan(?:ificaci[oó]n|ner)?\b",
                 r"paso a paso", r"\bflujo\b", r"pipeline", r"workflow"),
        artifacts=["code", "browser"],
    ),
    ReelTheme(
        slug="Visualizador-Agentico",
        title="El visualizador agéntico",
        caption="Visualizador agéntico · Ver el avance real",
        priority=2,
        hook="Veamos ahora el visualizador agéntico, quizá lo más vistoso de todo.",
        pregunta="¿Cómo entiendo el avance de un desarrollo si no sé leer código?",
        que_hace=(
            "El visualizador toma el trabajo del agente, que normalmente vive en el mundo "
            "del código, y lo convierte en algo que cualquiera puede ver: las pantallas "
            "reales, los flujos y los resultados, actualizándose en vivo mientras el agente "
            "construye. No hay que imaginar cómo va quedando el producto; se ve tomando "
            "forma frente a tus ojos."
        ),
        proposito=(
            "Su propósito es derribar el muro que suele existir entre el equipo técnico y "
            "quienes toman las decisiones. Un gerente no tiene por qué leer código para "
            "entender el avance; con el visualizador, mira la pantalla y comprende de "
            "inmediato dónde estamos y hacia dónde vamos."
        ),
        ejemplo=(
            "Imagina que estás construyendo una casa a distancia y, en lugar de recibir un "
            "informe lleno de términos técnicos, tienes una cámara en vivo que te muestra la "
            "casa creciendo, habitación por habitación. Eso es el visualizador: la cámara en "
            "vivo del producto agéntico."
        ),
        resultado=(
            "El resultado es que todos, técnicos y no técnicos, miran lo mismo al mismo "
            "tiempo y hablan el mismo idioma. Hay menos malentendidos, decisiones más "
            "rápidas y un producto que se puede aprobar con solo verlo funcionar."
        ),
        valor=(
            "Para el banco, esto acelera las aprobaciones y reduce el riesgo: se valida "
            "sobre algo real y demostrable, no sobre promesas en una diapositiva. Ver para "
            "creer, y creer para avanzar con confianza."
        ),
        cues=_rx(r"visualizador", r"visualiza", r"preview", r"vista previa",
                 r"localhost", r"\bhost\b", r"navegaci[oó]n"),
        artifacts=["browser"],
    ),
    ReelTheme(
        slug="Jira-HDU-Refinamiento",
        title="Jira, HDU y refinamiento",
        caption="Jira e historias de usuario · Trabajo trazable",
        priority=3,
        hook="Pasemos a algo del día a día del equipo: Jira y las historias de usuario.",
        pregunta="¿Cómo logramos que una tarea quede tan clara que nadie la interprete mal?",
        que_hace=(
            "Una historia de usuario es, en palabras simples, una tarea escrita desde la "
            "necesidad real del cliente: qué necesita y para qué. Refinarla significa "
            "dejarla tan clara que cualquiera pueda tomarla y construirla sin dudas. Aquí el "
            "agente lee la historia, propone los detalles que faltan, los criterios para "
            "saber si está bien hecha, y hasta las subtareas; luego lo conecta todo con "
            "Jira, la herramienta donde el banco organiza el trabajo."
        ),
        proposito=(
            "El propósito es que nada quede a la libre interpretación, que es justo de donde "
            "nacen la mayoría de los errores y los retrabajos. El agente amplifica al "
            "analista: le prepara el terreno para que la persona ajuste, refine y apruebe "
            "con criterio."
        ),
        ejemplo=(
            "Imagina un pedido a la cocina que solo dice: algo rico. Así nacen los "
            "problemas. Ahora imagina ese mismo pedido convertido en una receta detallada, "
            "con ingredientes, cantidades y pasos. El agente convierte el vago algo rico en "
            "la receta exacta, y la deja anotada en Jira para todo el equipo."
        ),
        resultado=(
            "El resultado es una tarea lista para desarrollar, con trazabilidad completa "
            "desde la idea hasta la entrega. Jira deja de ser una lista de pendientes "
            "olvidados y se convierte en el mapa vivo del proyecto, siempre actualizado."
        ),
        valor=(
            "Para el banco, esto significa previsibilidad: se sabe qué se está construyendo, "
            "por qué y en qué estado está, en todo momento. Menos sorpresas, mejores "
            "estimaciones y trazabilidad lista para auditoría."
        ),
        cues=_rx(r"\bjira\b", r"historia[s]?\s+de\s+usuario", r"\bh\.?\s?d\.?\s?u\.?\b",
                 r"\bhu[-\s]?\d", r"backlog", r"sprint", r"[eé]pica", r"refin",
                 r"story\s*points?", r"planner"),
        artifacts=["jira_planner"],
    ),
    ReelTheme(
        slug="MCP-Conexion",
        title="MCP: conectar la IA",
        caption="MCP · Conectar la IA con las herramientas",
        priority=4,
        hook="Hablemos de MCP, que suena técnico pero es una idea muy simple e importante.",
        pregunta="¿Cómo se conecta el agente con nuestras herramientas sin abrir riesgos de seguridad?",
        que_hace=(
            "MCP significa Protocolo de Contexto de Modelo, y funciona como un enchufe "
            "universal. Es lo que permite que el agente se conecte, de forma segura y "
            "ordenada, con las herramientas que el banco ya usa todos los días: Jira, los "
            "repositorios de código, las bases de conocimiento y más. Sin MCP, el agente "
            "estaría encerrado en una habitación, hablando solo. Con MCP, tiene puertas "
            "seguras a todo el edificio."
        ),
        proposito=(
            "Su propósito es que la inteligencia artificial no trabaje aislada, sino dentro "
            "del ecosistema real de la empresa, respetando sus reglas, sus permisos y su "
            "seguridad. Y esto, en un banco, es innegociable: cada conexión pasa por la "
            "puerta correcta, con la llave correcta."
        ),
        ejemplo=(
            "Piensa en un empleado nuevo. No le entregas una copia de todo ni acceso a la "
            "fuerza; le das una credencial que abre solo las puertas que le corresponden. "
            "MCP es esa credencial para el agente: acceso justo, controlado y registrado."
        ),
        resultado=(
            "El resultado es que el agente deja de ser una herramienta suelta y se vuelve un "
            "miembro más del equipo, capaz de trabajar con todas las herramientas de la "
            "empresa sin fricción y sin saltarse las reglas."
        ),
        valor=(
            "Para el banco, esto es clave: aprovecha la inteligencia artificial sin abrir "
            "brechas de seguridad ni crear sistemas paralelos. Integración segura, "
            "gobernada y trazable, sobre lo que ya existe."
        ),
        cues=_rx(r"\bmcp\b", r"model\s+context", r"protocolo\s+de\s+contexto",
                 r"integraci[oó]n", r"conect", r"\bapi\b", r"servidor"),
        artifacts=["code", "browser"],
    ),
    ReelTheme(
        slug="Auto-aprendizaje-Calibracion",
        title="Auto-aprendizaje y calibración",
        caption="Auto-aprendizaje · Calibrar el modelo",
        priority=5,
        hook=("Ahora algo poderoso y que marca la diferencia a largo plazo: el "
              "auto-aprendizaje y la calibración."),
        pregunta="¿Cómo se adapta el modelo a nuestra forma de trabajar y a nuestras reglas?",
        que_hace=(
            "Un buen agente no se queda quieto ni comete el mismo error dos veces. Aprende "
            "de cada corrida: si algo salió mal, se registra la lección y se corrige para la "
            "próxima. Y además se puede calibrar, que significa ajustarlo a nuestra "
            "realidad: enseñarle nuevos lenguajes de programación, definir los flujos de "
            "trabajo propios del banco, poner guardarraíles de seguridad y darle skills, es "
            "decir, habilidades especializadas para tareas concretas."
        ),
        proposito=(
            "El propósito es que la herramienta mejore semana a semana y se adapte a cómo "
            "trabaja el banco, en lugar de forzar al banco a adaptarse a la herramienta. Y "
            "lo más importante: las reglas y los límites los ponen siempre las personas."
        ),
        ejemplo=(
            "Es como capacitar a un empleado nuevo. Al principio necesita guía y comete "
            "algún error; le explicas las reglas de la casa y, con el tiempo, las domina y "
            "trabaja solo con confianza. Aquí es igual, pero el aprendizaje se guarda y se "
            "comparte, así que nunca se pierde."
        ),
        resultado=(
            "El resultado es un Framework Agéntico que cada vez conoce mejor el negocio, es "
            "más productivo y más seguro, porque acumula experiencia en lugar de empezar de "
            "cero cada vez."
        ),
        valor=(
            "Para el banco, esto es una inversión que se revaloriza: el sistema se vuelve "
            "más valioso con el uso, se alinea a las normas internas y reduce riesgos con "
            "cada iteración. Mejora continua, gobernada por las personas."
        ),
        cues=_rx(r"skill", r"guardrail", r"guardarra", r"calibr", r"aprend",
                 r"lenguaje", r"guideline", r"lecci[oó]n", r"regla[s]?", r"entren"),
        artifacts=["code"],
    ),
    ReelTheme(
        slug="Software-de-Terceros",
        title="Integración con terceros",
        caption="Software de terceros · Todo en un solo lugar",
        priority=6,
        hook="Cerremos con la integración con software de terceros.",
        pregunta="¿Cómo juntamos la información de tantas herramientas distintas en un solo lugar?",
        que_hace=(
            "En un banco no todo se construye desde cero; se trabaja con muchas herramientas "
            "externas, cada una con su propio lenguaje y su propia pantalla. El agente actúa "
            "como un puente: lee y visualiza la información de esos sistemas de terceros y la "
            "trae junto al trabajo del equipo, en un solo lugar, sin que la persona tenga "
            "que andar saltando de un programa a otro."
        ),
        proposito=(
            "El propósito es eliminar el trabajo tedioso y peligroso de copiar y pegar entre "
            "sistemas, que es una fuente constante de errores, y dar una visión unificada "
            "del avance. Menos ventanas abiertas, menos confusión, más foco."
        ),
        ejemplo=(
            "Imagina tener que armar un reporte mirando cinco planillas, tres páginas web y "
            "dos programas distintos, copiando datos a mano de cada uno. Ahora imagina que "
            "alguien lo junta todo, ordenado, en una sola pantalla. Eso hace el agente con "
            "las herramientas de terceros."
        ),
        resultado=(
            "El resultado es que la persona deja de perder tiempo moviendo datos de un lado "
            "a otro y se concentra en lo que aporta valor: analizar y decidir. El agente "
            "conecta en lugar de aislar."
        ),
        valor=(
            "Para el banco, esto significa aprovechar mejor las inversiones que ya hizo en "
            "otras herramientas, con menos errores manuales y una foto única y confiable del "
            "avance. Más valor de lo que ya se tiene."
        ),
        cues=_rx(r"third[-\s]?party", r"terceros", r"external", r"externo",
                 r"excel", r"power\s?bi", r"postman", r"swagger", r"open\s?api",
                 r"spectral", r"figma", r"sonar", r"trivy", r"xray"),
        artifacts=["excel", "browser", "code"],
    ),
]

THEMES_BY_SLUG = {t.slug.lower(): t for t in EDUCATIONAL_REELS}


@dataclass
class UseCase:
    """Un caso de uso descubierto en el video = un reel educativo."""
    theme: ReelTheme
    start: float          # inicio del tramo donde aparece la capacidad (s)
    end: float            # fin del tramo (s)
    marks: List[float]    # momentos elegidos para el reel


def _spread(ts_list: List[float], n_max: int, min_gap: float) -> List[float]:
    """Toma hasta n_max marcas respetando una separacion minima (evita clusters)."""
    chosen: List[float] = []
    for ts in ts_list:
        if all(abs(ts - o) >= min_gap for o in chosen):
            chosen.append(ts)
        if len(chosen) >= n_max:
            break
    if not chosen and ts_list:
        chosen = ts_list[:n_max]
    return sorted(chosen)


# Artefactos de PANTALLA COMPARTIDA (el trabajo del equipo en pantalla). El reel
# se enfoca SOLO en la proyeccion; NUNCA en 'teams' (paneles de camara = personas).
SCREEN_ARTIFACTS = {"browser", "code", "jira_planner", "excel", "powerpoint", "word"}

# Sobre este tono de piel el frame MUESTRA personas (galeria de camaras) y se excluye,
# aunque el OCR no lo clasifique como Teams.
PEOPLE_SKIN = 0.045


def _has_people(cand) -> bool:
    """¿El momento muestra personas? (panel Teams o mucho tono de piel = camaras)."""
    return (getattr(cand, "artifact", "otro") == "teams"
            or getattr(cand, "skin", 0.0) >= PEOPLE_SKIN)


def _screen_pool(cands) -> list:
    """Momentos de PANTALLA (sin personas): prioriza artefactos de proyeccion."""
    clean = [c for c in cands if not _has_people(c)]
    strong = [c for c in clean if getattr(c, "artifact", "otro") in SCREEN_ARTIFACTS]
    return strong or clean


def _even(ts_list: List[float], n: int) -> List[float]:
    """Elige n marcas REPARTIDAS a lo largo de una lista de tiempos (cobertura pareja)."""
    ts = sorted(ts_list)
    if not ts or n <= 0:
        return []
    if len(ts) <= n:
        return ts
    step = len(ts) / float(n)
    return [ts[min(len(ts) - 1, int(i * step))] for i in range(n)]


def themes_from_slugs(slugs: List[str]) -> List[ReelTheme]:
    """Resuelve una lista de slugs a temas (ignora los desconocidos, conserva orden)."""
    out: List[ReelTheme] = []
    for s in slugs:
        t = THEMES_BY_SLUG.get(s.strip().lower())
        if t and t not in out:
            out.append(t)
    return out


# ----------------------------------------------------------------------------
# Casos de uso GROUNDED: en vez de forzar el catalogo fijo de "Framework Agentico"
# (EDUCATIONAL_REELS, pensado para el proyecto original), narran con el CONTENIDO
# REAL del audio (reel_discovery.analyze: topico + tramo + citas literales de la
# transcripcion). Es el modo por defecto para que el mismo motor sirva para
# cualquier proyecto sin inventar contenido que el video no muestra.
# ----------------------------------------------------------------------------

def _slug_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")
    return t or "Caso"


@dataclass(eq=False)
class GroundedTheme:
    """Interfaz minima que build_capsule espera de un 'reel_theme' (title/caption/
    script/act_caption), pero con contenido tomado del audio real (sin plantilla)."""
    slug: str
    title: str
    caption: str
    script: str
    que_hace: str = ""
    proposito: str = ""
    resultado: str = ""

    def act_caption(self, act: int) -> str:
        act = max(0, min(2, act))
        return f"{ACT_LABELS[act]} · {self.title}"


def _case_quotes(case: Dict, tagged: List[Dict], max_quotes: int = 3) -> List[str]:
    """Citas literales (las mas largas, sin repetir) dentro del tramo del caso."""
    inside = [t["text"] for t in tagged
             if case["start"] - 1 <= t["start"] <= case["end"] and len(t["text"].split()) >= 4]
    seen, out = set(), []
    for txt in sorted(inside, key=len, reverse=True):
        if txt in seen:
            continue
        seen.add(txt)
        out.append(txt.strip())
        if len(out) >= max_quotes:
            break
    return out


def _grounded_theme(case: Dict, quotes: List[str]) -> GroundedTheme:
    """Guion HONESTO: contexto + intencion/pregunta reales + citas literales del
    tramo. No fabrica proposito/resultado que el audio no explique."""
    topic = case["topic"]
    parts = [f"Veamos este momento de la reunión, sobre {topic.lower()}."]
    if case.get("intencion"):
        parts.append(case["intencion"].strip())
    if case.get("pregunta"):
        parts.append("En ese momento surge esta pregunta:")
        parts.append(case["pregunta"].strip())
    if quotes:
        parts.append("Así lo explica el equipo en la grabación:")
        parts.extend(quotes)
    parts.append(f"Eso es lo que el equipo mostró y conversó sobre {topic.lower()} en esta sesión.")
    script = " ".join(p for p in parts if p)
    que_hace = case.get("intencion") or (quotes[0] if quotes else f"Momento real sobre {topic.lower()}.")
    proposito = case.get("pregunta") or "(no explicito en el audio; revisar el tramo)"
    resultado = quotes[-1] if quotes else "(revisar el tramo para el detalle del resultado)"
    return GroundedTheme(slug=_slug_text(topic), title=topic,
                         caption=f"{topic} · momento real de la reunión", script=script,
                         que_hace=que_hace, proposito=proposito, resultado=resultado)


def grounded_use_cases(cases: List[Dict], tagged: List[Dict], cands, duration: float,
                       emit: Optional[Callable[[str], None]] = None, *,
                       min_menciones: int = 2, per_case: int = 10,
                       max_reels: int = 6) -> List[UseCase]:
    """Casos de uso a partir del discovery de AUDIO real (reel_discovery.analyze),
    no del catalogo fijo de capacidades. Es el modo por defecto: evita narrar un
    tema que el video no muestra (p. ej. 'Framework Agéntico' sobre un video de
    otro proyecto que no lo menciona)."""
    def say(msg: str) -> None:
        if emit is not None:
            emit(msg)

    cams = [c for c in cands if _has_people(c)]
    clean = [c for c in cands if not _has_people(c)]
    if cams:
        say(f"Excluidos {len(cams)} momentos con personas (camara): solo pantalla compartida.")
    pool = _screen_pool(clean) if clean else []

    strong = [c for c in cases if c.get("menciones", 0) >= min_menciones]
    strong.sort(key=lambda c: c["start"])

    use_cases: List[UseCase] = []
    for c in strong[:max_reels]:
        lo, hi = c["start"], c["end"]
        window = [k.ts for k in pool if lo - 5 <= k.ts <= hi + 5]
        if not window:
            window = [k.ts for k in clean if lo - 5 <= k.ts <= hi + 5]
        if not window:
            continue
        marks = _even(sorted(window), min(per_case, len(window)))
        theme = _grounded_theme(c, _case_quotes(c, tagged))
        use_cases.append(UseCase(theme=theme, start=lo, end=hi, marks=marks))
        say(f"Caso de uso GROUNDED: {theme.title} · {len(marks)} momentos · "
            f"{int(lo)}s-{int(hi)}s ({c['menciones']} menciones)")

    if use_cases:
        say(f"Casos de uso reales (del audio): {len(use_cases)}.")
    return use_cases


def discover_use_cases(cands, duration: float,
                       emit: Optional[Callable[[str], None]] = None, *,
                       only: Optional[List[ReelTheme]] = None,
                       min_moments: int = 3, per_reel: int = 14,
                       max_reels: int = 8) -> List[UseCase]:
    """DISCOVERY: en base al contenido real del video, decide DINAMICAMENTE cuantos
    reels salen (2, 4 o mas) y cuales capacidades ensena.

    - Puntua cada momento contra cada capacidad (OCR/artefacto).
    - Una capacidad "esta presente" si tiene >= `min_moments` momentos reales.
    - SOLO PANTALLA: se excluyen los momentos de camara (artifact 'teams'); el reel
      se enfoca en la proyeccion/producto agentico, NUNCA en las personas.
    - El intro ("¿Que es un agente?") va SIEMPRE primero.
    - El resto se ordena por su PRIMERA aparicion (narrativa cronologica).
    - `only` fuerza capacidades concretas (flag --reels).
    """
    def say(msg: str) -> None:
        if emit is not None:
            emit(msg)

    # Separacion adaptativa: en videos cortos, marcas mas juntas (no colapsar a 1).
    gap = max(6.0, min(20.0, duration / 60.0))
    intro = EDUCATIONAL_REELS[0]
    topical = [t for t in EDUCATIONAL_REELS if t is not intro]

    # SOLO PROYECCION EN PANTALLA: fuera camaras/personas (panel Teams o mucho tono de
    # piel = galeria de camaras, aunque el OCR no la clasifique como Teams).
    cams = [c for c in cands if _has_people(c)]
    cands = [c for c in cands if not _has_people(c)]
    if cams:
        say(f"Excluidos {len(cams)} momentos con personas (camara): solo pantalla compartida.")

    # Puntuar cada capacidad contra los momentos del video. Solo cuentan los momentos
    # que MUESTRAN la capacidad (senal real de OCR); el score afina el orden.
    per_theme = {}
    for t in topical:
        scored = [(t.score(c), c) for c in cands if t.matches(c)]
        scored.sort(key=lambda x: x[0], reverse=True)
        per_theme[t] = scored

    if only:
        chosen = [t for t in only if t is not intro]
        say(f"Reels forzados por el usuario: {len(only)}")
        present = [(t, per_theme.get(t, [])) for t in chosen]
    else:
        present = [(t, sc) for t, sc in per_theme.items() if len(sc) >= min_moments]
        present.sort(key=lambda x: min((c.ts for _, c in x[1]), default=0.0))
        nombres = ", ".join(t.title for t, _ in present) or "(ninguna clara)"
        say(f"Capacidades detectadas en el video: {len(present)} -> {nombres}")

    use_cases: List[UseCase] = []

    # B-roll de PANTALLA (sin camaras) repartido a lo largo del video: para el intro
    # y para cualquier tema forzado sin material propio.
    screen_ts = [c.ts for c in _screen_pool(cands)]

    def broll(n: int) -> List[float]:
        m = _even(screen_ts, n)
        if not m:                       # sin pantalla detectada: reparto temporal
            step = duration / (n + 1)
            m = [step * (i + 1) for i in range(n)]
        return sorted(m)

    include_intro = (not only) or (intro in only)
    if include_intro:
        intro_marks = broll(per_reel)
        use_cases.append(UseCase(intro, 0.0, duration, intro_marks))
        say(f"Caso de uso 1: {intro.title} · {len(intro_marks)} momentos · 0s-{int(duration)}s")

    for t, sc in present[:max(1, max_reels - len(use_cases))]:
        if sc:
            ts_all = [c.ts for _, c in sc]
            marks = _spread([c.ts for _, c in sc], per_reel, gap)
            start, end = min(ts_all), max(ts_all)
        else:
            marks = broll(per_reel)     # forzada sin material: B-roll de pantalla
            start, end = 0.0, duration
        # Un caso de uso real necesita >=2 momentos y cubrir un tramo (no todo pegado en
        # un mismo instante). Evita sobre-fragmentar videos cortos/clusterizados.
        if len(marks) >= 2 and (end - start) >= 15.0:
            use_cases.append(UseCase(t, start, end, marks))
            say(f"Caso de uso {len(use_cases)}: {t.title} · {len(marks)} momentos · "
                f"{int(start)}s-{int(end)}s")

    say(f"Discovery listo: {len(use_cases)} reel(s) educativo(s).")
    return use_cases
