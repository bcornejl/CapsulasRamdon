# CapsulasRamdon

Motor **standalone** del *agenteVideo* (extraído de [`ReporteCelulaAgentica`](../ReporteCelulaAgentica)):
convierte grabaciones largas (demos, dailies, reuniones) en **cápsulas de video para
gerencia** — sin mostrar personas, con voz IA y trazabilidad al minuto.

## Qué hace

A partir de un video largo en `capsula/`, produce automáticamente:

1. **Screenshot** — imágenes fijas de los momentos clave + voz en off continua.
2. **Cápsula Extensa** — tramas de video reales cortadas y unidas (≤ 5 min), audio
   100 % voz IA, sin personas. De un video largo puede salir **más de una** cápsula
   temática (discovery automático de casos de uso).
3. **Html a video** — convierte un HTML/diagrama en un video didáctico paso a paso.

Pipeline interno (ver [`skills/agente-video/SKILL.md`](skills/agente-video/SKILL.md) y
[`.github/prompts/agenteVideo.prompt.md`](.github/prompts/agenteVideo.prompt.md) para el
detalle completo):

```
video → escaneo (escenas + OCR + audio) → selección de momentos
      → guion narrado (voz IA es-LatAm) → montaje (PyAV, libx264+AAC)
      → verificación (sin personas, duración, resolución, códecs)
      → registro (anti-duplicación / "¿hay más casos?")
```

## Estructura

```
capsula/            # ENTRADA: deja aquí los videos largos del proyecto
presentacion/        # SALIDA: ReporteVideo/MM-AAAA/{screenShot,capsula-extensa,Html-a-video}/
scripts/
  video_capsule.py    # motor principal (CLI: modos screenshot | capsula | html)
  html_to_video.py     # modo "Html a video"
  visual_capture.py    # OCR + clasificación de artefactos en pantalla
  reel_discovery.py    # discovery profundo del audio (Whisper) para el modo cápsula
  reel_themes.py        # guiones educativos por capacidad/tema
  capsule_content.py    # contexto narrativo (tema + hechos) desde un resumen/transcripción
  capsule_registry.py   # registro + bucle "¿hay más casos?" (anti-duplicación)
  capsule_verify.py     # compuerta de verificación (duración, resolución, códecs, sin personas)
  narration.py          # voz en off (edge-tts, con respaldo local pyttsx3)
  utils.py              # rutas del proyecto, logging, utilidades de fecha
skills/agente-video/    # SKILL + guiones de ejemplo del proyecto original
.github/prompts/agenteVideo.prompt.md  # prompt de Copilot para invocar /agenteVideo
```

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\pip.exe install -r scripts\requirements.txt
```

Requiere Python 3.9+. El motor de video es **PyAV (libx264 + AAC)**: no necesita
`ffmpeg` instalado en el sistema. El OCR usa modelos ONNX incluidos (`rapidocr-onnxruntime`).
La voz usa `edge-tts` (requiere red) con respaldo local `pyttsx3` (offline).

## Uso rápido

```powershell
# Deja el video largo en capsula/, luego:
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode screenshot
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula

# Verificar antes de entregar (sin personas, duración, códecs)
.venv\Scripts\python.exe scripts\capsule_verify.py

# Bucle "¿hay más casos?" tras un lote (anti-duplicación)
.venv\Scripts\python.exe scripts\capsule_registry.py more-cases
```

Ver todas las opciones (`--voice`, `--at`, `--reels`, `--script-file`, etc.) en
[`skills/agente-video/SKILL.md`](skills/agente-video/SKILL.md).

## Adaptar a un nuevo proyecto

Este motor nació dentro de un proyecto específico (Célula Agéntica / Santander) y se
dejó **configurable** para reutilizarlo en otro proyecto:

- **Presentador y marca de las cápsulas** — variables de entorno (sin tocar código):
  ```powershell
  $env:CAPSULA_PRESENTADOR = "Nombre Apellido"
  $env:CAPSULA_MARCA = "Empresa · Cliente"
  ```
  (por defecto: `Bernardo Cornejo López` / `Santander · NTT DATA`, los valores del
  proyecto original).
- **Carpeta de salida por mes** — `CAPSULA_MES=MM-AAAA` para que `capsule_registry.py`
  y `capsule_verify.py` apunten a un mes/proyecto distinto del actual.
- **Temas/casos de uso del discovery** — edita `CANON` en `scripts/capsule_registry.py`
  y `DEMO_TOPICS` en `scripts/reel_discovery.py` con las capacidades reales que el
  nuevo proyecto demuestra (por defecto traen los del proyecto original: CI/CD, QA,
  Jira, API, etc.).
- **Guiones educativos** — `scripts/reel_themes.py` trae temas genéricos del framework
  agéntico; agrega/edita temas según lo que el nuevo proyecto quiera enseñar.
- **Contexto narrativo real** — `capsule_content.py` intenta leer, si existen,
  `transcripciones/<fecha>.md` o `transcripciones/MM-AAAA/Daily DD-MM-AAAA/Resumen_Daily_*.md`
  para narrar con hechos reales; si no existen, usa un guion genérico (no falla).

## Origen

Extraído del subsistema `capsula/` + `scripts/video_capsule.py` (y módulos asociados)
de `ReporteCelulaAgentica`, donde convivía con el resto del pipeline de la Célula
Agéntica (transcripción, minutas, estado del proyecto). Aquí queda **aislado** para
poder generar cápsulas de cualquier otro proyecto sin arrastrar ese contexto.
