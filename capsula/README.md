# Carpeta `capsula/` — entrada del **agenteVideo**

Aquí van los videos "gigantes" (grabaciones largas: demos, dailies, reuniones) a partir
de los cuales se generan las **cápsulas / Cápsulas Extensas ejecutivas**. El agenteVideo
lee **solo** de esta carpeta (o de la ruta que le pases con `--video`).

## Cómo se usa

```powershell
# Deja tu video largo en esta carpeta y ejecuta (elige el modo):
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode screenshot
.venv\Scripts\python.exe scripts\video_capsule.py --date hoy --mode capsula
```

- **Dos modos:** `screenshot` (imágenes fijas + voz en off) o `capsula` = **Cápsula
  Extensa** (tramas reales cortadas y unidas, ≤5 min, audio 100 % voz IA masculina). De
  un video largo, el modo `capsula` saca **varias Cápsulas Extensas educativas** que
  enseñan el framework a la gerencia, **sin mostrar personas**.
- Detecta el video por la **fecha** (en el nombre del archivo o por su fecha de
  modificación). Formatos: `.mp4`, `.mkv`, `.mov`, `.avi`, `.m4v`, `.webm`.
- El nombre puede traer la fecha en varios formatos
  (`Grabación 2026-08-27 094738.mp4`, `reunion_27082026.mp4`, etc.).

## Salida (output)

- **`presentacion/ReporteVideo/MM-AAAA/screenShot/`** — modo screenshot:
  `Capsula-Celula-Agentica-DD-MM-AAAA.mp4` (+ rundown `.md`).
- **`presentacion/ReporteVideo/MM-AAAA/capsula-extensa/`** — modo capsula: un
  `CapsulaExtensa-<tema>-DD-MM-AAAA.mp4` por cada Cápsula Extensa educativa (+ rundown
  `.md` con la trazabilidad al minuto).

Esta carpeta (`capsula/`) es **solo de entrada**; el resultado se escribe en
`presentacion/ReporteVideo/`.
