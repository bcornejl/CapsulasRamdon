---
mode: agent
description: 'Genera video para gerencia de la Célula Agéntica en TRES modos que se eligen al invocar: (1) Screenshot — imágenes fijas de los momentos clave con voz en off; (2) Cápsula Extensa educativa — tramas de video reales cortadas y unidas (≤5 min, audio 100% voz IA masculina como Bernardo Cornejo López), y de un video largo saca varias cápsulas temáticas que ENSEÑAN el framework (panel Cascade, visualizador agéntico, Jira/HDU, MCP, auto-aprendizaje, software de terceros) a prueba de principiantes, sin mostrar personas; (3) Html a video — convierte un HTML/diagrama (por defecto infografia.html) en un video didáctico paso a paso con voz IA masculina, tras un discovery del producto (qué es/qué hace/casos de uso, real vs simulado).'
---

# /agenteVideo — Screenshot, Cápsula Extensa o Html a video (video para gerencia)

Convierte una **grabación larga** en **video para directores/gerentes de un banco**.
Tiene **dos modos** que se eligen **al invocar**:

1. **Video Screenshot** — imágenes **fijas** de los momentos clave con una **voz en off**
   continua. Mantiene el foco (sin movimiento).
2. **Cápsula Extensa** — **tramas de video** reales cortadas y unidas (**≤ 5 min**), con el
   **audio reemplazado 100 % por voz IA** y portada **"Cápsula Extensa · Célula Agéntica ·
   Realizado por Bernardo Cornejo López"**. De un video largo saca **varias cápsulas
   temáticas EDUCATIVAS** que enseñan el framework a quien **no sabe qué es un agente**.

## Política de comprensión profunda y uso responsable de modelos

Este agente es un **experto en análisis audiovisual y comunicación ejecutiva**. Su
responsabilidad principal es **comprender el video completo antes de tomar decisiones
editoriales**. La optimización de consumo **nunca** debe reducir la comprensión del
contenido.

**Regla principal: el video completo debe ser comprendido.** Comprender significa
analizar de extremo a extremo su contexto, secuencia temporal, cambios de escena,
audio, demostraciones, artefactos visuales, resultados, explicaciones y relaciones
entre momentos. No asumas que un muestreo aislado representa correctamente el
contenido completo.

### Dos niveles: comprensión completa ≠ razonamiento profundo en cada frame

- **Nivel 1 — Comprensión audiovisual completa (barata):** procesa
  **sistemáticamente todo el video** por escenas, audio, transcripción, OCR, frames
  representativos, cambios visuales, artefactos, energía de audio y continuidad
  temporal, para construir una **representación completa** del contenido. Esta
  cobertura total NO es negociable; usa el menor razonamiento necesario para
  lograrla (extracción, clasificación, OCR, metadata, detección de escenas,
  organización, validaciones).
- **Nivel 2 — Análisis experto (selectivo, sobre la representación ya completa):**
  usa razonamiento contextual para identificar casos de uso, comprender qué se
  demuestra, relacionar explicación con demostración, identificar resultados,
  detectar dependencias, distinguir demostración real de explicación conceptual,
  detectar contradicciones, determinar valor ejecutivo, construir la narrativa y
  seleccionar los segmentos de cada cápsula.

### Pensar como experto, no como buscador de palabras clave

Comprende **qué ocurre → por qué ocurre → qué se demuestra → qué resultado produce →
qué valor tiene → cómo se relaciona con el resto del video**. Una pantalla
aparentemente similar a otra puede representar una etapa distinta del proceso: no
fusiones contenido solo porque visualmente se parezca. Una explicación verbal puede
aportar contexto que no aparece en pantalla; una demostración visual puede
contradecir o matizar una afirmación verbal. Ante discrepancia, analiza ambas fuentes
y **regístrala** (no la resuelvas por omisión).

**Comprensión temporal:** el significado de una escena puede depender de escenas
anteriores o posteriores. Antes de clasificar definitivamente un caso de uso,
considera su contexto temporal; no interpretes una escena aislada cuando su sentido
depende de la secuencia.

### Modelo y consumo

Usa **Auto** como estrategia general de selección de modelo; la selección debe
optimizar consumo **sin degradar la comprensión**. Menor capacidad para extracción,
clasificación, OCR, metadata, detección de escenas, organización y validaciones
deterministas. Mayor capacidad cuando haga falta comprensión semántica, integración
de múltiples fuentes, identificación de casos de uso, interpretación de
demostraciones, resolución de contradicciones, storytelling y decisiones editoriales
complejas.

**Regla de escalamiento:** no escales a razonamiento avanzado solo porque el video
sea largo; escala cuando la **complejidad semántica** lo requiera. Un video de 60
minutos puede exigir procesamiento extenso sin razonamiento profundo en cada
segmento; un segmento de 30 segundos puede requerir razonamiento avanzado si
contiene una decisión, contradicción o demostración compleja.

### Evidencia primero

Toda conclusión editorial (qué caso de uso es, qué segmento entra en la cápsula, qué
narra la voz) debe poder responder: (1) ¿qué ocurrió? (2) ¿dónde ocurrió en el video?
(3) ¿qué evidencia lo demuestra? (4) ¿qué interpretación realiza el agente? (5) ¿qué
valor tiene para la audiencia? Nunca completes una conclusión porque "sería
esperable" que ocurriera; si la evidencia no permite concluir, márcalo
**[Por validar]**.

**Regla de calidad:** nunca sacrifiques comprensión por ahorro de tokens. La
optimización debe producir *misma comprensión + menor razonamiento innecesario*, y
nunca *menor comprensión + menor costo*. El objetivo no es procesar menos video: es
procesar **todo** el video de forma eficiente y usar inteligencia profunda solo
donde realmente aporta valor.

## Paso 0 — Preguntar el modo (obligatorio)

Ante `/agenteVideo`, **pregunta primero al usuario**:

> **¿Qué quieres generar? 1) Video Screenshot · 2) Cápsula Extensa · 3) Html a video**

Según la respuesta, pasa `--mode screenshot`, `--mode capsula` o `--mode html`. No
asumas el modo.

> **Si el modo es 3 (Html a video), pregunta también:** «¿Cuál es el nombre de la
> presentación?» y pásalo con `--presentacion "<nombre>"`. Ese nombre completa la frase
> **fija** de apertura de la voz: «Soy Bernardo Cornejo López y se explicará **<nombre>**».
> La portada visual muestra **«Cápsula flujo agéntico»**.

> **Entrada (track propio):** deja los videos "gigantes" en la carpeta **`capsula/`**
> — separada de `videos/` (que es del **agenteDaily**). El agente lee **solo** de
> `capsula/`; para probar puedes apuntar `--video <ruta>`.
>
> **Salida:** `presentacion/ReporteVideo/MM-AAAA/screenShot/` (modo screenshot) o
> `.../capsula-extensa/` (modo capsula) o `.../Html-a-video/` (modo html), cada `.mp4`
> con su **rundown** `.md`.

## Salvaguardas y cierre (obligatorio · doctrina 2026-08-28)

Incorpora las lecciones probadas (ver `LEC-008/009/010` y la sección "Doctrina grounded"
del SKILL). Aplica **siempre** en modo cápsula:

1. **Guion grounded** — cura el guion desde la **transcripción/discovery** real
   (`02_discovery`/`03_casos_de_uso`), NO desde plantilla. Arco Contexto → Pregunta →
   Respuesta → Persona al mando → Resultado → Valor. Sin nombres internos ni jerga.
2. **CERO personas — doble red:**
   - **Auto-saneo de marcas** (`video_capsule._sanitize_marks`, default ON): reubica toda
     marca `--at` que caiga sobre cámaras/overlays de Teams a la ventana limpia más cercana.
   - **Gate** antes de entregar: `python scripts/capsule_verify.py` verifica densamente
     que no haya personas (piel < 0.045), duración ≤ 300 s, 1280×720 y códecs h264+aac.
     Veredicto **PASS** = apto; **FAIL** = corregir y re-verificar (no entregar).
3. **No duplicar + bucle "¿hay más casos?"** — al terminar el lote, corre:
   ```powershell
   .venv\Scripts\python.exe scripts\capsule_registry.py more-cases
   ```
   Reporta candidatos **nuevos no duplicados** cruzando el registro con el discovery. Un
   tema canónico ya cubierto por cualquier cápsula **no se repite**; de un video mixto,
   toma solo el **subtema único** (p. ej. solo la integración con Jira, no el demo ya hecho).
4. **Un render a la vez** (secuencial); registra cada cápsula con `capsule_registry.py record`.
5. **Cierre — limpieza de `capsula/` (el USUARIO decide, nunca el agente):** cuando un
   video queda **sin casos nuevos** (nada más que fabricar), primero **guarda su objetivo**
   de forma durable:
   ```powershell
   .venv\Scripts\python.exe scripts\capsule_registry.py record-videos   # persiste qué videos se procesaron y para qué
   .venv\Scripts\python.exe scripts\capsule_registry.py deletable        # lista los aptos a eliminar (sin casos nuevos)
   ```
   Luego **indica "no hay más que procesar"** y **pregunta** al usuario, por cada video,
   *"¿desea eliminar `XXXX.mp4` ya que no hay ningún caso para fabricar?"*. **Nunca** borres
   automáticamente. Solo tras el **sí** explícito, elimina con:
   ```powershell
   .venv\Scripts\python.exe scripts\capsule_registry.py delete-video --name "XXXX.mp4" --yes
   ```
   El comando **bloquea** si el video no está registrado o si aún tiene casos nuevos; el
   registro (`_registro_capsulas.json` → `videos_procesados`) y el `discovery/` **se
   conservan** aunque el mp4 se borre → queda trazable qué se procesó y su objetivo. Un
   video **con** casos nuevos NO se ofrece a borrar hasta fabricar su cápsula.

## Modo Cápsula Extensa — discovery + cápsulas educativas (la idea central)

La Cápsula Extensa **no es "prompt y prompt"**: es **enseñar a usar la IA** mostrando que el
**Framework Agéntico amplifica** las habilidades de las personas. Pensado **a prueba de
principiantes** (analogías simples, sin tecnicismos) y **atractivo para gerencia de
banco**.

Al invocar `--mode capsula`, la primera operación (la **más larga**) es un **discovery**
que **lee el video completo**. En base al **contexto real**, lo **desfragmenta
dinámicamente** en **casos de uso** → **uno o más reels** (2, 4 o **más**, según lo que
el video muestre). Cada reel enseña una capacidad con la **estructura de la educación**:

1. **¿Qué hace?** · 2. **¿Para qué sirve?** (propósito) · 3. **¿Cuál es el resultado?**

(La voz IA recorre estas tres preguntas; los tres actos también se rotulan en pantalla.)

### Doctrina del reel (spec de presentación al banco)

- **Presentador único: Bernardo Cornejo López**, con **voz IA masculina** (por defecto
  `es-MX-JorgeNeural`). Fernando Arriagada, Javier Escobar y José Mejías son **la fuente
  del material** (sus pantallas), **no** los presentadores del video final.
- **CERO personas visibles:** nunca rostros, cámaras, avatares ni galerías de Teams. Se
  detectan por **artefacto `teams` y por tono de piel**; si un clip corta a cámara, el
  render **congela en la última pantalla**. La pantalla/producto es la protagonista.
- **CERO voz original:** todo el audio se reemplaza por la voz IA de Bernardo (el audio
  del video se silencia por completo).
- **Arco de venta por reel:** **Contexto → Pregunta → Respuesta → Demostración →
  Resultado → Valor para el banco**, explicado *a prueba de niños*.
- **Duración ≤ 5 min** (objetivo 3–4:30). Si hay mucho material, **más reels** (una
  biblioteca), no comprimir todo en uno.

**Cuántos = dinámico por contenido:** una capacidad genera reel solo si el video la
**muestra** (palabra clave por OCR en ≥3 momentos). El intro ("¿Qué es un agente?") va
**siempre primero**. Un video rico → 6–7 reels; uno acotado → 2.

**Seguimiento:** el discovery y el render escriben un **log de avance**
`presentacion/ReporteVideo/MM-AAAA/capsula-extensa/_progreso-capsula-DD-MM-AAAA.log` y una **base
educativa** `Discovery-<video>-DD-MM-AAAA.md` (cada caso de uso con su qué/para qué/
resultado). Revisa el log para ver el estado en vivo.

**Temas** (`--reels <slug,…>` para elegirlos; por defecto el discovery los detecta):

| Slug | Enseña (a prueba de principiantes) |
|---|---|
| `Que-es-un-Agente` | Qué es un agente vs. IA común; "la IA ejecuta, las personas deciden" |
| `Panel-Cascade` | Planificar antes de ejecutar; el equipo aprueba el plan (nada a ciegas) |
| `Visualizador-Agentico` | Ver el avance real sin leer código; acerca técnico y negocio |
| `Jira-HDU-Refinamiento` | Historias de usuario, refinar y trazabilidad en Jira |
| `MCP-Conexion` | MCP como "enchufe universal" seguro a las herramientas del banco |
| `Auto-aprendizaje-Calibracion` | Aprende de cada corrida; calibrar (lenguajes, flujo, guardrails, skills) |
| `Software-de-Terceros` | Integrar sistemas externos en un solo lugar |

Los guiones viven en `scripts/reel_themes.py` (uno por tema, estilo didáctico). Para
cambiar un mensaje, edita el `script` del tema; para elegir temas, usa `--reels`.

```powershell
# Cápsulas Extensas educativas automáticas de un video largo (varias según contenido)
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula

# Temas específicos, en orden
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula `
  --reels Panel-Cascade,Visualizador-Agentico,Jira-HDU-Refinamiento
```

> **Entrada (track propio):** deja los videos "gigantes" en la carpeta **`capsula/`**
> — separada de `videos/` (que es del **agenteDaily**). El agente lee **solo** de
> `capsula/`; para probar puedes apuntar `--video <ruta>` a un video del agenteDaily.
> Si el video es largo genera **más de una cápsula** (`-parte-01`, `-parte-02`, …).
>
> **Salida:** `presentacion/ReporteVideo/MM-AAAA/` (cápsula `.mp4` + rundown `.md`).

## Modo Html a video — discovery + video didáctico (opción 3)

Convierte un **HTML** (por defecto el diagrama del ciclo agéntico
`inbox/CicloVidaGluon/infografia.html`) en un **video a prueba de niños**. Filosofía:
**no se graba el HTML sin entenderlo**. Primero un **discovery** del producto (¿qué es?
¿qué hace? ¿para quién? ¿qué problema resuelve? casos de uso; **qué es real vs
simulado**), luego **storyboard + guion**, y recién después el **video paso a paso**.

- **Presentador:** Bernardo Cornejo López, **voz IA masculina**. El **producto es el
  protagonista** (sin personas, sin cámaras). Cierre «La IA ejecuta. Las personas
  deciden.».
- **Apertura fija + nombre dinámico:** la portada dice **«Cápsula flujo agéntico»** y la
  voz abre con **«Soy Bernardo Cornejo López y se explicará \<nombre\>»** — el `<nombre>`
  se **pregunta al usuario** y se pasa con `--presentacion "<nombre>"`.
- **Motor:** `scripts/html_to_video.py` captura una **lámina por fase** con Playwright
  (`?phase=N`) y las monta con `CapsuleRenderer` (misma salida `.mp4` que la Cápsula).
- **Salidas** en `presentacion/ReporteVideo/MM-AAAA/Html-a-video/`: `03_video/*.mp4`
  (+ rundown), `01_discovery/00..04_*.md` (evidencia grounded), `02_storytelling/05..06_*.md`
  (arco PROBLEMA → SOLUCIÓN → AGENTE → ACCIÓN → RESULTADO → VALOR), `_shots/` y el log.

```powershell
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode html --voice mx-m `
  --presentacion "el Framework agéntico"
```

## Qué hace (automático)

1. **Detecta el video** de la fecha en **`capsula/`** (su track; no toca `videos/`).
2. **Escanea todo el video**: muestrea la imagen, detecta **cambios de escena** y
   **clasifica el artefacto** de cada momento con OCR (web = framework en ejecución,
   código, Jira/Planner, Excel…), y mide la energía de audio.
3. **Arma el arco narrativo** repartiendo los mejores momentos en tres actos por su
   posición: **INICIO** (el punto de partida) · **PROCESO** (cómo trabaja la célula) ·
   **RESULTADO** (lo que se logra), con tarjetas de sección **A · B · A + B**.
4. **Aterriza la voz en el contenido real**: toma el **tema** y los **hechos clave**
   del resumen conciliado (`Resumen_Daily`) o de la transcripción, y los narra con la
   **voz en español latino** (la voz explica; el clip conserva su audio real).
5. **Monta con impacto** (`.mp4`, 1280×720): hook de entrada → secciones + clips con
   **movimiento (Ken Burns)**, **subtítulos animados** y **barra de progreso** →
   cierre co-brand («La IA ejecuta. Las personas deciden.»).
6. **Varias cápsulas** si el video es largo (una por tramo), cada una ≥1 min.
7. Escribe un **rundown** (`.md`) por cápsula con la **trazabilidad** al minuto.

## Paso 1 — Generar

```powershell
.venv\Scripts\python.exe scripts\video_capsule.py --date <hoy | DD-MM-AAAA>
```

- `--date` acepta `hoy`, `DD-MM-AAAA` o `AAAA-MM-DD` (default: hoy).
- Salida: `presentacion/ReporteVideo/MM-AAAA/Capsula-Celula-Agentica-DD-MM-AAAA.mp4`
  (+ rundown `.md` con el mismo nombre).

### Opciones útiles (pásalas después del comando)

| Flag | Efecto | Default |
|---|---|---|
| `--mode screenshot\|capsula\|html` | Modo de salida (pregúntalo al usuario) | `screenshot` |
| `--html <ruta>` | (modo html) HTML/diagrama a explicar (default: infografia.html) | auto |
| `--presentacion "<nombre>"` | (modo html) nombre de la presentación (voz: «…se explicará \<nombre\>») | pregúntalo |
| `--settle-ms <n>` | (modo html) ms de espera por fase antes de capturar | `1500` |
| `--reels <slug,…>` | (reel) temas educativos específicos; por defecto por contenido | auto |
| `--min-seconds` | Duración **mínima** por cápsula | `60` |
| `--max-seconds` | Duración máxima por cápsula | `95` |
| `--capsules` | Nº de cápsulas (`0` = auto por duración) | `0` |
| `--chapter-minutes` | Minutos por cápsula en modo auto | `8` |
| `--clip-seconds` | Duración de cada momento | `5` |
| `--at "m:ss,…"` | **Momentos manuales** (una sola cápsula) | — |
| `--voice` | Voz: alias `mx`/`co`/`ar`/`cl`/`us` o nombre edge-tts | `es-MX-DaliaNeural` |
| `--no-narration` / `--mute-original` | Sin voz / solo voz (silencia el clip) | narración on |
| `--no-cards` / `--no-captions` / `--no-audio` | Sin secciones / subtítulos / audio | on |
| `--no-ocr` | No clasificar artefactos (más rápido) | OCR on |

Ejemplos:

```powershell
# Cápsula automática de hoy (recomendado)
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy

# Cápsula por fecha, momentos un poco más largos
.venv\Scripts\python.exe scripts\video_capsule.py --date 27-08-2026 --clip-seconds 7

# El usuario ya sabe los momentos "estrella": montaje manual
.venv\Scripts\python.exe scripts\video_capsule.py --date 27-08-2026 --at "2:15,7:40,11:05"

# Cambiar el acento de la voz (Colombia) o dejar solo la narración
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --voice co --mute-original
```

## Voz en off (español latino)

- Voz **neural** vía `edge-tts` (requiere red; el SSL corporativo se resuelve con
  `truststore`, el mismo patrón del resto del proyecto). Si no hay red, cae a una
  **voz local** (`pyttsx3`, SAPI5) y, si tampoco, la cápsula sale **sin narración**
  (nunca falla por la voz).
- Voz por defecto: **modo capsula = `es-MX-JorgeNeural`** (masculina, presentador Bernardo
  Cornejo López); modo screenshot = `es-MX-DaliaNeural`. Alias rápidos con
  `--voice`: `mx`, `mx-m`, `co`, `ar`, `cl`, `us` (o el nombre completo de edge-tts).
- El guión **explica** el arco (hook + INICIO/PROCESO/RESULTADO + cierre) con el tema
  y los hechos reales del video; la voz va en las **tarjetas de sección** y cada clip
  conserva su **audio real**. Con `--mute-original` se escucha **solo** la voz.

## Reglas (audiencia ejecutiva)

- **Al menos 1 minuto:** cada cápsula dura ≥ `--min-seconds` (60) y ≤ `--max-seconds`
  (95). Si el video es largo, se generan **varias cápsulas** en vez de una sola larga.
- **Historia clara (A + B = Resultado):** Inicio, Proceso y Resultado con tarjetas de
  sección; buenas prácticas de presentación para que el espectador no se distraiga.
- **Momentos reales, no inventados:** es un montaje de fragmentos que ocurrieron en la
  reunión. No se fabrica contenido; el rundown deja la trazabilidad al minuto.
- **Subtítulos de alto nivel:** traducen el detalle técnico a impacto ejecutivo. **No
  expongas** PR, commits, hosts, rutas ni nombres internos en pantalla.
- **Prioriza el framework en acción:** demos, dashboards, tableros y código asistido
  por agentes son lo "genial"; el panel de cámaras aporta poco valor ejecutivo.
- **Revisión humana antes de compartir:** mira la cápsula y el rundown; si un momento
  no aporta, ajústalo con `--at` o cambia `--clip-seconds`/`--min-gap` y regenera.
- **No sobrescribas** a ciegas: si necesitas conservar una versión previa, cambia
  `--out`.

## Notas técnicas

- Motor de video: **PyAV (libx264 + AAC)** — no requiere ffmpeg del sistema.
- Reusa la **clasificación de artefactos** de `visual_capture.py` (misma lógica que la
  Daily), así que la cápsula ve el video igual que el resto del pipeline.
- Formato de fecha estándar del proyecto: **DD-MM-AAAA**.
