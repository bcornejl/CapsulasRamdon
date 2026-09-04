# SKILL: /videoE2EUseCaseAnalyzer — Video E2E Use Case Analyzer

## Invocación

- `/videoE2EUseCaseAnalyzer <ruta-del-video>` — analiza un video END TO END y produce
  el reporte completo (secciones 1-24 del prompt): identificación, resumen ejecutivo,
  actores, sistemas, transcripción, timeline, screenshots, funcionalidades, reglas de
  negocio, casos de uso, matriz de trazabilidad, información no determinada, hallazgos
  y conclusión.
- Lenguaje natural: "analiza el video completo", "busca casos de uso", "¿qué hace este
  sistema?", "muéstrame la evidencia", "¿ya analizamos este video?", "actualiza los
  casos de uso", "reprocesa el video".

Ver el prompt completo en
[`.github/prompts/videoE2EUseCaseAnalyzer.prompt.md`](../../.github/prompts/videoE2EUseCaseAnalyzer.prompt.md)
(persona + reglas + memoria persistente, secciones 1-52).

## Qué hace

A diferencia del `/agenteVideo` (que **produce** cápsulas de video para gerencia), este
agente **consume** un video y produce **documentación funcional trazable**: actores,
sistemas, funcionalidades, reglas de negocio y casos de uso, cada uno con evidencia
(timestamp + cita de transcripción + screenshot). Nunca inventa: etiqueta cada dato
como OBSERVADO / EXPLICADO / INFERIDO / DESCONOCIDO.

## Memoria persistente (obligatoria antes de analizar)

`scripts/video_use_case_memory.py` es la memoria mecánica (JSON) que evita:
1. Reprocesar un video ya analizado (identidad por SHA-256 del archivo).
2. Duplicar casos de uso (similitud de texto sobre nombre/objetivo/actor/flujo).

Archivo: `memory/video_use_case_memory.json` (se crea solo; no editar a mano).
Esquema: `memory_version, videos[], actors[], systems[], functionalities[],
business_rules[], use_cases[], relationships[], analysis_history[]`.

### Flujo obligatorio

```powershell
# 1) Identidad + duplicado/version (SIEMPRE primero)
.venv\Scripts\python.exe scripts\video_use_case_memory.py check-video --video "capsula\demo.mp4"
#   -> EXACT_DUPLICATE | LIKELY_DUPLICATE | NEW_VERSION | RELATED_VIDEO | NEW_VIDEO

# 2) Si se procede, registrar el video (usa el video_id en toda la evidencia)
.venv\Scripts\python.exe scripts\video_use_case_memory.py register-video --video "capsula\demo.mp4" `
  --title "Gestión de Solicitudes Bancarias" [--parent-video-id "sha256:..."]

# 3) Por cada caso de uso candidato: clasifica y crea/reusa automáticamente
.venv\Scripts\python.exe scripts\video_use_case_memory.py add-use-case `
  --name "Consultar Cliente" --objective "Consultar información de un cliente" `
  --actor "Ejecutivo" --flow "Ingresar RUT -> Buscar -> Mostrar cliente" `
  --functionality F-002 --business-rule BR-008 `
  --video "sha256:..." --ts-start 00:04:21 --ts-end 00:05:10 --confidence HIGH
#   -> NEW (crea UC-XXX) | EXISTING/DUPLICATE (agrega evidencia al UC existente, no duplica)

# 4) Actualizar un caso existente (mantiene historial de la version anterior)
.venv\Scripts\python.exe scripts\video_use_case_memory.py update-use-case --use-case UC-003 `
  --reason "Nueva regla de negocio detectada" --business-rule BR-008

# 5) Consultas
.venv\Scripts\python.exe scripts\video_use_case_memory.py list-videos
.venv\Scripts\python.exe scripts\video_use_case_memory.py list-use-cases
.venv\Scripts\python.exe scripts\video_use_case_memory.py history --entity UC-003
```

Todas las salidas son JSON por stdout.

### Clasificación de video (`check-video`)

| Status | Significa | Acción |
|---|---|---|
| `EXACT_DUPLICATE` | Mismo hash SHA-256 exacto | NO reprocesar; informar "VIDEO YA PROCESADO" |
| `LIKELY_DUPLICATE` | Misma "familia" de nombre (`v1`/`v2`/`final`/...) + duración casi idéntica (≤2%) | Confirmar con el contenido antes de decidir |
| `NEW_VERSION` | Misma familia de nombre, duración distinta | Analizar como nueva versión del `parent_video_id` |
| `NEW_VIDEO` | Sin relación con videos previos | Analizar completo |

### Clasificación de caso de uso (`add-use-case` / `match-use-case`)

Similitud ponderada (nombre 35%, objetivo 30%, flujo 15%, actor 10%, trigger 10%, +5%
si comparten funcionalidad) vía `difflib.SequenceMatcher`. Umbrales por defecto:

| Score | Status | Efecto |
|---|---|---|
| ≥ 0.92 | `DUPLICATE` | Se agrega evidencia al UC existente; NO se crea otro |
| ≥ 0.75 | `EXISTING` | Igual: se agrega evidencia, no se duplica |
| ≥ 0.55 | `RELATED` | Se crea un UC nuevo (funcionalidad distinta, pero emparentada) |
| < 0.55 | `NEW` | Se crea un UC nuevo |

`--force-new` fuerza la creación aunque haya match (úsalo solo si lo justificas).

### Versionado y no-destrucción

- `update-use-case` nunca sobrescribe en silencio: guarda un snapshot de la versión
  anterior dentro de `analysis_history` y sube `use_case.version`.
- `analysis_history` registra toda acción (`CREATED`, `EVIDENCE_ADDED`, `UPDATED`) con
  fecha y motivo — es el historial de auditoría (secciones 44/46 del prompt).

## Relación con `/agenteVideo`

Ambos agentes analizan video, pero con objetivos distintos:

| | `/agenteVideo` | `/videoE2EUseCaseAnalyzer` |
|---|---|---|
| Entrada | Video largo en `capsula/` | Cualquier video de demo/proceso |
| Salida | Cápsulas `.mp4` para gerencia | Documento funcional (actores, UC, reglas) |
| Memoria | `capsule_registry.py` (anti-duplicación de **cápsulas**) | `video_use_case_memory.py` (anti-duplicación de **casos de uso**) |
| Usa Whisper/OCR | Sí (`reel_discovery.py`, `visual_capture.py`) | Sí, conceptualmente (transcripción + screenshots); este agente no impone un motor concreto |

Pueden compartir evidencia: el `01_transcripcion_completa.md` y los frames que ya
genera `/agenteVideo` (`discovery/<video>/`) son una fuente válida de evidencia para
este analizador si el mismo video ya pasó por ese pipeline.
