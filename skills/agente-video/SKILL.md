# SKILL: /agenteVideo — Screenshot o Reel educativo (video para gerencia)

## Invocación

- `/agenteVideo` — **PREGUNTA PRIMERO EL MODO** al usuario: **1) Video Screenshot**,
  **2) Cápsula Extensa** o **3) Html a video**; luego genera la(s) salida(s) de la
  fecha de **hoy**.
- `/agenteVideo DD-MM-AAAA` — igual, para esa fecha.
- Lenguaje natural: "arma el video para gerencia", "reel de la reunión", "cápsula con
  impacto de la Daily", "convierte este HTML/diagrama en un video didáctico".

> **Regla de invocación (obligatoria):** ante `/agenteVideo`, Copilot pregunta al
> usuario **1. Video Screenshot**, **2. Cápsula Extensa** o **3. Html a video** antes
> de ejecutar, y pasa el `--mode` correspondiente (`screenshot` | `capsula` | `html`).

## Política de comprensión profunda y uso responsable de modelos

Experto en análisis audiovisual: **el video completo debe ser comprendido** de punta a
punta (contexto, secuencia temporal, cambios de escena, audio, demostraciones,
artefactos, resultados, explicaciones, relaciones entre momentos) antes de tomar
decisiones editoriales; nunca asumir que un muestreo aislado representa el contenido
completo. Dos niveles: **Nivel 1** (barato, NO negociable) = cobertura sistemática de
TODO el video vía escenas/audio/transcripción/OCR/frames/artefactos/energía para
construir la representación completa; **Nivel 2** (selectivo) = razonamiento experto
SOBRE esa representación ya completa para identificar casos de uso, relacionar
explicación con demostración, detectar contradicciones, distinguir demostración real
de conceptual y construir la narrativa/selección de segmentos. No fusionar pantallas
similares que representen etapas distintas; una escena puede depender de su contexto
temporal (antes/después) para interpretarse bien. Modelo: **Auto** general; menor
capacidad para extracción/clasificación/OCR/detección de escenas/validaciones, mayor
capacidad para comprensión semántica/integración de fuentes/casos de uso/resolución de
contradicciones/storytelling. **No escalar solo porque el video sea largo**; escalar
por **complejidad semántica** (un segmento de 30s con una decisión/contradicción puede
requerir más razonamiento que un video de 60min sin ambigüedad). Toda conclusión
editorial responde: qué ocurrió / dónde en el video / qué evidencia lo prueba / qué
interpreta el agente / qué valor tiene; sin evidencia suficiente → **[Por validar]**.
Nunca sacrificar comprensión por ahorro de tokens (misma comprensión + menor
razonamiento innecesario, nunca menor comprensión + menor costo). Codificado también en
`agenteVideo.prompt.md` ("Política de comprensión profunda y uso responsable de
modelos").

## Tres modos (se elige al invocar)

| Modo | Qué produce | Salida |
|---|---|---|
| **1. Screenshot** (`--mode screenshot`, actual) | Imágenes **fijas** de los momentos clave + una **voz en off** continua. Mantiene el foco (sin movimiento). | `ReporteVideo/MM-AAAA/screenShot/` |
| **2. Reel** (`--mode reel`, educativo) | **Tramas de video** reales cortadas y unidas (**≤ 5 min**), **audio 100 % voz IA**, portada **"Reel Célula Agéntica · Realizado por Bernardo Cornejo López"**. De un video largo (**≥ 1 h**) salen **3–5 reels temáticos** que **enseñan** el framework. | `ReporteVideo/MM-AAAA/reel/` |
| **3. Html a video** (`--mode html`, didáctico) | Convierte un **HTML/diagrama** (por defecto `inbox/CicloVidaGluon/infografia.html`) en un **video a prueba de niños**: portada branded, **voz IA masculina** (Bernardo Cornejo López), el **producto como protagonista** (sin personas) y cierre co-brand. Primero hace **discovery** (qué es / qué hace / casos de uso, real vs simulado) y luego el video **paso a paso**. | `ReporteVideo/MM-AAAA/Html-a-video/` |

## Modo reel — discovery + reels educativos (para gerencia de banco)

El modo **reel** no es "prompt y prompt": son **cápsulas educativas a prueba de
principiantes** que enseñan **cómo el Framework Agéntico amplifica** a las personas.
Al invocarlo, primero hace la operación **más larga**: un **discovery** que **lee el
video completo**. En base al **contexto real**, lo **desfragmenta dinámicamente** en
**casos de uso** → **uno o más reels** (2, 4 o **más**, según lo que el video muestre;
por eso se apoya en el auto-aprendizaje: se adapta al contenido, no a una plantilla).

Cada reel enseña **una** capacidad con la **estructura de la educación** (voz IA que
explica con analogías simples; el audio original se **reemplaza por completo**):

1. **¿Qué hace?** — qué es y qué hace, sin tecnicismos.
2. **¿Para qué sirve?** — el propósito (ángulo banco).
3. **¿Cuál es el resultado?** — el beneficio concreto.

Los tres actos también se ven en pantalla como subtítulo de cada tercio del reel.

**Capacidades enseñables** (`scripts/reel_themes.py`; el discovery elige las que el
video realmente muestra por OCR; el intro va siempre primero):

| Slug (`--reels`) | Enseña |
|---|---|
| `Que-es-un-Agente` | Qué es un agente vs. IA tradicional; la IA ejecuta, las personas deciden |
| `Panel-Cascade` | Planificar antes de ejecutar; nada se corre a ciegas (transparencia) |
| `Visualizador-Agentico` | Ver el avance real sin leer código; acerca técnico y negocio |
| `Jira-HDU-Refinamiento` | Historias de usuario, refinamiento y trazabilidad en Jira |
| `MCP-Conexion` | MCP como "enchufe universal" seguro a las herramientas del banco |
| `Auto-aprendizaje-Calibracion` | Lecciones aprendidas + calibrar (lenguajes, flujo, guardrails, skills) |
| `Software-de-Terceros` | Integrar sistemas externos en un solo lugar |

**Cuántos reels = dinámico por contenido:** una capacidad genera reel si el video la
**muestra** (palabra clave detectada por OCR en ≥3 momentos). Un video rico puede dar
6–7 reels; uno acotado, 2. Cada reel: portada "Reel Célula Agéntica" → tramas reales
con subtítulo del acto → cierre "La IA ejecuta. Las personas deciden.".

**Salidas** (en `presentacion/ReporteVideo/MM-AAAA/reel/`):
- `Reel-<video>-<slug>-DD-MM-AAAA.mp4` + su rundown `.md` (por reel).
- `Discovery-<video>-DD-MM-AAAA.md` — **base educativa**: cada caso de uso con su
  ¿qué hace? / ¿para qué? / ¿resultado?.
- `discovery/<video>/` — **discovery PROFUNDO del audio** (`scripts/reel_discovery.py`,
  transcripción Whisper cacheada): `01_transcripcion_completa.md` (literal con
  timestamps), `02_discovery_video.md` (mapa temporal + **intenciones "vamos a…"** +
  **preguntas reales** + tema + pantalla), `03_casos_de_uso.md`, `04_matriz_casos_uso.md`.
  Es la **evidencia** para curar los guiones sobre lo que realmente ocurrió (`--no-transcribe`
  lo omite). Sin diarización: no etiqueta hablantes.
- `_progreso-capsula-DD-MM-AAAA.log` — **log de avance** (discovery → desfragmentación →
  render) para seguir el estado del programa en vivo.

```powershell
# Discovery + Cápsulas Extensas educativas automáticas (cantidad dinámica por contenido)
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula

# Capacidades específicas, en orden
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula `
  --reels Panel-Cascade,Visualizador-Agentico,Jira-HDU-Refinamiento
```

> El discovery **necesita OCR** (default on) para reconocer las capacidades en pantalla;
> no uses `--no-ocr`. Es la parte más lenta (lee el video denso). Un render a la vez
> (secuencial); sigue el `_progreso-reel-*.log` para ver el avance.

## Modo Html a video — discovery + video didáctico (opción 3)

Convierte un **HTML** (por defecto el diagrama del ciclo agéntico
`inbox/CicloVidaGluon/infografia.html`) en un **video a prueba de niños** para jóvenes
profesionales y gerencia. **No graba el HTML sin entenderlo**: primero hace un
**discovery** (¿qué es? ¿qué hace? ¿para quién? ¿qué problema resuelve? casos de uso,
qué es **real** vs **simulado**) y recién después arma el video, **paso a paso**.

> **Portada y apertura (fijas):** la **portada visual** dice **«Cápsula flujo agéntico»**
> y la voz **abre siempre** con **«Soy Bernardo Cornejo López y se explicará \<nombre\>»**.
> El `<nombre>` es **dinámico**: Copilot **pregunta** «¿Cuál es el nombre de la
> presentación?» y lo pasa con `--presentacion "<nombre>"` (default `el flujo agéntico`).

- **Motor:** `scripts/html_to_video.py`. Captura una **lámina por fase** con Playwright
  (Edge del sistema, `?phase=N`) y las monta con `CapsuleRenderer` (mismo estilo de
  salida que la Cápsula Extensa): portada branded → una lámina por paso con **voz IA
  masculina** (Bernardo Cornejo López) que explica *qué hace / para qué / resultado* →
  cierre «La IA ejecuta. Las personas deciden.». **Sin personas** (el producto es el
  protagonista).
- **Salidas** en `presentacion/ReporteVideo/MM-AAAA/Html-a-video/`:
  - `03_video/CapsulaExtensa-<slug>-DD-MM-AAAA.mp4` (+ rundown `.md`).
  - `01_discovery/{00_resumen_ejecutivo,01_discovery_producto,02_mapa_interacciones,`
    `03_matriz_funcionalidades,04_matriz_casos_uso}.md` — **evidencia grounded** del
    análisis (sin inventar; distingue real / simulado / mock).
  - `02_storytelling/{05_storyboard,06_guion_video}.md` — arco **PROBLEMA → SOLUCIÓN →
    AGENTE → ACCIÓN → RESULTADO → VALOR**.
  - `_shots/` (láminas PNG) y `_progreso-html-DD-MM-AAAA.log`.
- **Otro HTML** (no el diagrama): captura una lámina general y narra con `--script-file`
  (o un guion genérico honesto); igual escribe la base de discovery.

```powershell
# Diagrama del ciclo agéntico → video didáctico (voz masculina)
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode html --voice mx-m `
  --presentacion "el Framework agéntico"

# Otro HTML con guion curado
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode html `
  --html ruta\a\mi.html --script-file guion.txt
```

## Qué hace

A partir de una **grabación larga** (una demo o Daily) produce una **cápsula ejecutiva
(~1–2 min)** para **directores del banco**. Estilo **presentación con voz en off**:
portada branded, una secuencia de **imágenes fijas** de los momentos clave (el
framework agéntico en acción) y una **única voz en off en español latino** que narra
todo de corrido. Diseñado para **mantener el foco** (sin distracciones).

**Curación manual (recomendado):** la auto-selección no siempre captura los momentos
narrativos clave. Lo que mejor funciona es **elegir los momentos a mano** con `--at`
(minutos:segundos) tras revisar una **hoja de contactos** del video, y aterrizar una
**narración continua** (`--script-file`) en lo que realmente muestra la demo.

## Cómo se genera

```
python scripts/video_capsule.py --date <hoy | DD-MM-AAAA>
```

- **Entrada (track propio):** los videos "gigantes" van en **`capsula/`**, separada de
  `videos/` (del agenteDaily). Lee **solo** de `capsula/`; `--video <ruta>` para probar.
- **Salida:** `presentacion/ReporteVideo/MM-AAAA/screenShot/` (modo screenshot) o
  `.../capsula-extensa/` (modo capsula) + **rundown** `.md` con la trazabilidad al minuto.

### Pipeline interno (`scripts/video_capsule.py`)

1. **Escanear** — muestreo por escena + OCR de keyframes + `classify_artifact` +
   energía de audio → candidatos con puntaje (recorre TODO el video).
2. **Puntuar y repartir** — peso ejecutivo por artefacto (Web/Código altos, Teams
   bajo); los momentos se reparten en **INICIO / PROCESO / RESULTADO** por posición.
3. **Aterrizar la voz** — `scripts/capsule_content.py` lee el **tema** (H1) y los
   **hechos** del `Resumen_Daily` (o la transcripción) para el hook y las secciones.
4. **Narrar** — `scripts/narration.py`: `edge-tts` neural (con `truststore` por el SSL
   corporativo) y respaldo local `pyttsx3`. La voz **fluye continua** sobre las
   imágenes (desborda de la tarjeta al clip, atenuando el audio real debajo).
5. **Montar con foco** — **portada branded** ("Cápsula Célula Agéntica · Realizado por
   Bernardo Cornejo López", Santander · NTT DATA) → **imágenes fijas** de cada momento
   (con `--still`; **sin** zoom/Ken Burns) + subtítulo → **cierre** "La IA ejecuta. Las
   personas deciden.". **Una sola voz** continua a nivel parejo (`--script` + audio
   original **silenciado**). Video **libx264 + AAC** vía PyAV (sin ffmpeg del sistema).

## Opciones

| Flag | Efecto | Default |
|---|---|---|
| `--mode screenshot\|reel` | **screenshot**: imágenes fijas (actual). **reel**: tramas reales + reels educativos. **html**: Html a video (diagrama → video didáctico) | `screenshot` |
| `--html <ruta>` | (modo html) HTML a explicar (default: `inbox/CicloVidaGluon/infografia.html`) | auto |
| `--presentacion "<nombre>"` | (modo html) nombre de la presentación; la voz abre con «Soy Bernardo Cornejo López y se explicará \<nombre\>» | preguntárselo |
| `--settle-ms <n>` | (modo html) ms de espera por fase antes de capturar la lámina | `1500` |
| `--reels <slug,…>` | (modo reel) temas educativos específicos; por defecto se eligen por contenido | auto |
| `--still` | **Imagen fija** por momento (sin zoom/Ken Burns) — mantiene el foco | movimiento on |
| `--script-file <txt>` | **Narración continua** desde archivo UTF-8 (una sola voz; silencia el original) | — |
| `--script "<texto>"` | Igual, pero inline (ojo con acentos por consola) | — |
| `--at "m:ss,…"` | Momentos **manuales** (una sola cápsula) — **curación recomendada** | — |
| `--ordered` | Respeta el **orden** de `--at` (narrativo; p.ej. abrir con el Q&A) | cronológico |
| `--voice` | Voz latina: alias `mx`/`mx-m`/`co`/`co-m`/`cl`/`cl-m`/`us`… | usar **`mx-m`** (masculina) |
| `--theme "<txt>"` | Subtítulo de la portada | — |
| `--force` / `--reprocess` | Reprocesa aunque el video sea `EXACT_DUPLICATE` en memoria (sección 0) | off |
| `--clip-seconds` | Duración de cada momento (se autoajusta al guion con `--script`) | `5` |
| `--mute-original` | Silencia el audio original (implícito con `--script`) | — |
| `--out` | Ruta `.mp4` de salida | auto |
| `--min-seconds`/`--max-seconds`/`--capsules`/`--chapter-minutes` | Modo auto (sin `--at`) | `60`/`95`/`0`/`12` |

## Reglas

- **Una sola voz**: la narración en español latino cubre TODA la cápsula a nivel parejo;
  el **audio original se silencia** (`--script`/`--script-file`). No mezclar la voz con
  las voces de los presentadores (pierde foco y deja niveles dispares).
- **Sin movimiento**: usar `--still` (imagen fija por momento). El zoom/Ken Burns
  distrae → los ejecutivos pierden el foco.
- **Portada + cierre fijos**: portada "Cápsula Célula Agéntica · Realizado por Bernardo
  Cornejo López" (Santander · NTT DATA); cierre "La IA ejecuta. Las personas deciden.".
  **Sin** tarjetas de sección A·B·A+B.
- **Curación manual**: revisar una **hoja de contactos** del video y elegir los momentos
  con `--at` (framework en acción: IDE agéntico, visualizador/HDU, lenguaje natural,
  dashboards, validaciones). La auto-selección se queda corta.
- **Guion aterrizado (grounded)**: la narración describe lo que REALMENTE muestra la
  demo (sin inventar); alto nivel, sin exponer PR/commits/hosts/nombres internos.
- **Un render a la vez**: **no** correr una hoja de contactos de un video grande ni otro
  render en paralelo mientras uno está activo → la contención puede **cortar el mp4**
  (queda inválido). Lote **secuencial**; con `--still` cada cápsula tarda ~35–40s.
- **Revisión humana**: mirar la cápsula (o una hoja de contactos del resultado) antes de
  compartir. **Formato de fecha estándar**: `DD-MM-AAAA`.

## Doctrina grounded + salvaguardas (lecciones incorporadas 2026-08-28)

Flujo **probado** para cápsulas que venden el producto al banco (5 cápsulas + 1 concepto
entregadas con este método). Incorpora buenas prácticas de **ECC** (verification-loop,
delivery-gate, continuous-learning) y del curso **ai-agents-for-beginners** de Microsoft
(07-planning-design, 09-metacognition, 13-agent-memory).

### 0. Identidad del video (anti-reprocesamiento, misma doctrina del `/videoE2EUseCaseAnalyzer`)
Antes de correr el discovery completo (modo `capsula`, automático), se identifica el
video por **SHA-256** (no por nombre de archivo, que puede cambiar) contra
`videos_procesados` del registro:
```powershell
.venv\Scripts\python.exe scripts\capsule_registry.py identify --video "capsula\<archivo>.mp4"
```
- `EXACT_DUPLICATE` (mismo hash, con cápsulas ya generadas) → `video_capsule.py` **no
  reprocesa**: informa "VIDEO YA PROCESADO" (video ID, cápsulas existentes, objetivo
  cubierto) y termina. Usa `--force` para forzar el reprocesamiento igual.
- `NEW_VERSION` (misma familia de nombre — `v1`/`v2`/`final`/... —, duración distinta)
  → se procesa completo, mencionando de qué video es nueva versión.
- El chequeo se **omite** si pasas `--at` (curación manual explícita) o `--force`.
- Requiere haber corrido `record-videos` al menos una vez (persiste `video_id` +
  `duration_seconds` por video); `more-cases` también lo hace al final de cada lote.

### 1. Flujo grounded (aterrizado en el contenido real)
1. **Discovery de audio** — `reel_discovery.deep_discovery` transcribe (Whisper, cacheado)
   y escribe entregables `01`–`04` en `discovery/<slug>/`.
2. **Curar el guion** (Copilot) leyendo `02_discovery` + `03_casos_de_uso` — NO plantilla.
   Arco: Contexto → Pregunta real → Respuesta/Demostración → Persona al mando → Resultado
   → Valor. ~300–340 palabras (~2–2.5 min). Sin nombres internos ni jerga innecesaria.
3. **Marcas en ventanas SIN personas** (ver salvaguarda) alineadas al tema.
4. **Render 1 a la vez** (`--script-file` + `--at` + `--theme` + `--no-transcribe`).
5. **Verificación (gate)** antes de entregar.

### 2. Salvaguarda anti-personas (OBLIGATORIA — regla del banco)
Nunca mostrar a las personas de las reuniones (cámaras/panel de Teams).
- **Auto-saneo de marcas** (`video_capsule._sanitize_marks`, default ON): cada marca `--at`
  se muestrea; si el tramo `[m, m+10s]` tiene piel ≥ `PEOPLE_SKIN` (0.045) la marca se
  **reubica a la ventana limpia más cercana**. `--keep-marks` lo desactiva.
- **Lección raíz**: "congelar en la última pantalla buena" FALLA si el clip **entero**
  tiene overlays de Teams (no hay frame limpio). Por eso se sanea en el ORIGEN (la marca).
- **Verificación densa**: muestrear piel cada 0.25s sobre el mp4 final; 0 frames ≥ umbral.

### 3. Anti-duplicación + bucle "¿hay más casos?"
Al terminar un lote, correr SIEMPRE:
```powershell
.venv\Scripts\python.exe scripts\capsule_registry.py more-cases
```
Cruza el **registro** (`capsula-extensa/_registro_capsulas.json`, idempotencia estilo ECC
continuous-learning) con el discovery de cada video en `capsula/` y reporta **candidatos
NUEVOS no duplicados** (un tema canónico cubierto por cualquier cápsula no se repite,
aunque aparezca en otro video). `record` registra una cápsula; `list` lista; `record-videos`
persiste el **objetivo por video procesado** (incluye `video_id` SHA-256 y duración, usados
por `identify`/el chequeo anti-reprocesamiento de la sección 0); `deletable` lista los
videos sin casos nuevos; `delete-video --name <mp4> --yes` borra un mp4 procesado
(guardado, ver sección 6).

### 4. Compuerta de verificación (gate) — patrón ECC verification-loop
Fases **mecánicas** (BLOQUEA solo en hechos verificables; nunca inferencia de IA):
1. el `.mp4` existe y pesa > 0; 2. duración **≤ 300 s**; 3. **1280×720**; 4. códecs
**h264 + aac**; 5. **SIN personas** (piel densa < 0.045). Si algo falla → corregir y
re-verificar (auto-corrección), no entregar. WARN (no bloquea) en señales blandas.

### 5. Diagnóstico antes de reintentar (ECC agent-introspection)
Ante un fallo de render/verify: capturar el error, **clasificarlo** (marca sucia / clip
sin frame limpio / guion muy largo / codec) y correr **una** comprobación discriminante
antes de reintentar. Registrar la lección en `aprendizaje/LECCIONES_APRENDIDAS.md`.

### 6. Limpieza de `capsula/` — el USUARIO decide (2026-08-28)
`capsula/` es el buzón de videos "gigantes": una vez **procesados y documentados**, el mp4
crudo puede eliminarse conservando el conocimiento derivado. Regla: **el agente nunca borra
solo; pregunta y el usuario decide.** Al cerrar un lote, cuando un video queda **sin casos
nuevos** (nada más que fabricar):
1. **Guardar el objetivo (durable):** `capsule_registry.py record-videos` escribe
   `videos_procesados` en `_registro_capsulas.json` con, por video: `objetivo` (temas del
   discovery ∪ temas de sus cápsulas), `capsulas`, `casos_nuevos`, `discovery` y fechas.
   Así, aunque se borre el mp4, queda trazable **qué se procesó y para qué**.
2. **Indicar "no hay más que procesar"** y listar los aptos: `capsule_registry.py deletable`.
3. **Preguntar por cada video** *"¿desea eliminar `XXXX.mp4`?"*. Solo tras el **sí**:
   `capsule_registry.py delete-video --name "XXXX.mp4" --yes` (sin `--yes` = dry-run).

El `delete-video` **bloquea** si el video no está registrado (`record-videos` primero) o si
aún tiene `casos_nuevos` (fabricar su cápsula antes). El `discovery/` y el registro se
**conservan**; solo se borra el mp4 pesado. Matching video↔discovery robusto por nombre
compacto (`PrimerEntregable` == carpeta `Primer-Entregable`).

## Flujo rápido (curación) y recetas

**Para un video nuevo:**
1. Hoja de contactos: `python output/_contact.py "capsula/<video>.mp4" output/_sheet.png 40`
   y revisarla para ubicar los momentos de valor.
2. Escribir el guion (una voz, ~150–200 palabras) en `.devin/skills/agente-video/guiones/<x>.txt`.
3. Render:
   `python scripts/video_capsule.py --video "capsula/<video>.mp4" --at "<m:ss,…>" --still --voice mx-m --script-file .devin/skills/agente-video/guiones/<x>.txt --theme "<subtítulo>" --out output/<x>.mp4`
4. Verificar y copiar a `presentacion/ReporteVideo/MM-AAAA/Capsula-Celula-Agentica-<tema>-DD-MM-AAAA.mp4`.

**Recetas curadas (2026-08-27)** — guiones en `guiones/`, marcas listas para re-render:

| Video (capsula/) | `--at` | Extra | Guion | Tema (portada) |
|---|---|---|---|---|
| Grabación-Demo-FrontEnd-Flujo-Jira.mp4 | `1:20,2:10,3:00,3:50,4:40,5:20,7:50,9:10,10:30,12:00,12:27` | | frontend-jira.txt | FrontEnd y Jira con el Framework Agéntico |
| Grabación-Demo-ci-cd.mp4 | `1:00,1:15,1:30,0:03,0:15,0:27,0:39` | `--ordered` | ci-cd.txt | Integración continua asistida por agentes |
| Grabación-Demo-QA.mp4 | `0:44,1:44,2:44,4:43,6:42,8:12,9:12,9:41,10:11,11:11` | | qa.txt | Calidad asistida por el Framework Agéntico |
| Grabación-Demo-archivoMesadeApi.mp4 | `0:33,3:57,7:21,10:44,13:00,15:16,17:32,22:03,24:19,32:14,37:54,44:41` | | mesa-de-api.txt | La mesa de API con el Framework Agéntico |
| Grabación-Demo-FrontEnd.mp4 | `2:48,6:11,9:33,10:41,14:03,16:19,20:49,23:04,24:11,28:41,32:04,37:41` | | digital-host.txt | Desarrollo del Digital Host con el Framework Agéntico |

**Re-generar las 5 de un comando** (usa las recetas de arriba; render secuencial ~3 min):

```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; .\.devin\skills\agente-video\regenerar.ps1
```

Deja las 5 en `presentacion/ReporteVideo/08-2026/` con nombres limpios. Para editar el
mensaje de una cápsula, cambiar su `guiones/<x>.txt`; para cambiar los momentos, su fila
de `--at`.

> Voz masculina única (`--voice mx-m` = es-MX-JorgeNeural). Para una voz aún más
> expresiva (OpenAI TTS) haría falta API key + OK para procesar el texto externamente.

## Requisitos

- Deps en `scripts/requirements.txt`: `av` (PyAV con libx264+aac), `pillow`, `numpy`,
  `rapidocr-onnxruntime`, `edge-tts` + `pyttsx3` (voz) y `truststore` (SSL corporativo).
- Ejecutar con el intérprete del proyecto: `.\.venv\Scripts\python.exe`.
