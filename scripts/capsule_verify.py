"""capsule_verify.py - Compuerta de verificacion (delivery gate) de Capsulas Extensas.

Patron "verification-loop" de ECC (MIT), adaptado al dominio de video: fases MECANICAS
que BLOQUEAN solo en hechos verificables por maquina (nunca inferencia de IA). Si algo
falla -> corregir y re-verificar (auto-correccion), no entregar.

Fases (BLOCK):
  1. Archivo existe y pesa > 0
  2. Duracion <= 300 s (<= 5 min)
  3. Resolucion 1280x720
  4. Codecs video h264 + audio aac
  5. SIN personas: muestreo denso de piel (cada ~0.25s) < PEOPLE_SKIN
WARN (no bloquea): duracion < 45 s (posible guion corto).

Uso:
    python scripts/capsule_verify.py                 # verifica toda la carpeta capsula-extensa
    python scripts/capsule_verify.py <a.mp4> <b.mp4> # verifica archivos puntuales
Exit code 2 si alguna capsula FALLA (bloquea la entrega); 0 si todas pasan.
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

import numpy as np
import av

ROOT = Path(__file__).resolve().parent.parent
# Carpeta del mes vigente (o CAPSULA_MES="MM-AAAA" para apuntar a otro mes/proyecto).
import os as _os
_MES = _os.environ.get("CAPSULA_MES") or datetime.now().strftime("%m-%Y")
CAPS_DIR = ROOT / "presentacion" / "ReporteVideo" / _MES / "capsula-extensa"
MANIFEST = CAPS_DIR / "_verificacion_manifiesto.json"

PEOPLE_SKIN = 0.045
MAX_SECONDS = 300.0
W_EXPECT, H_EXPECT = 1280, 720
PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
ICON = {PASS: "OK ", WARN: "!! ", FAIL: "XX "}


def skin_frac(rgb: np.ndarray) -> float:
    s = rgb[::12, ::12].astype(np.int16)
    r, g, b = s[..., 0], s[..., 1], s[..., 2]
    mask = ((r > 95) & (g > 40) & (b > 20) & (r > g) & (r > b) &
            (np.abs(r - g) > 15) & ((r.astype(np.int32) - b) > 15))
    return float(mask.mean())


def verify_one(p: Path) -> Tuple[str, dict, List[str]]:
    """Devuelve (veredicto, metricas, motivos_fallo) de una capsula."""
    reasons: List[str] = []
    if not p.exists() or p.stat().st_size == 0:
        return FAIL, {"archivo": p.name}, ["no existe o pesa 0"]
    c = av.open(str(p))
    v = c.streams.video[0]
    a = c.streams.audio[0] if c.streams.audio else None
    dur = float(c.duration / av.time_base) if c.duration else 0.0
    W, H = v.codec_context.width, v.codec_context.height
    vcodec = v.codec_context.name
    acodec = a.codec_context.name if a else "SIN-AUDIO"
    fps = float(v.average_rate) if v.average_rate else 24.0
    skins, over = [], 0
    for i, frame in enumerate(c.decode(v)):
        if i % 6:  # ~cada 0.25s
            continue
        sf = skin_frac(frame.to_ndarray(format="rgb24"))
        skins.append(sf)
        if sf >= PEOPLE_SKIN:
            over += 1
    c.close()
    smax = max(skins) if skins else 0.0

    if dur > MAX_SECONDS:
        reasons.append(f"duracion {dur:.0f}s > {MAX_SECONDS:.0f}s")
    if (W, H) != (W_EXPECT, H_EXPECT):
        reasons.append(f"resolucion {W}x{H} != {W_EXPECT}x{H_EXPECT}")
    if vcodec != "h264":
        reasons.append(f"video codec {vcodec} != h264")
    if acodec != "aac":
        reasons.append(f"audio codec {acodec} != aac")
    if over > 0:
        reasons.append(f"PERSONAS: {over} frames con piel>={PEOPLE_SKIN} (max {smax:.3f})")

    metrics = {"archivo": p.name, "duracion_s": round(dur, 1), "resolucion": f"{W}x{H}",
               "video": vcodec, "audio": acodec, "piel_max": round(smax, 3),
               "frames_personas": over, "muestras": len(skins)}
    verdict = FAIL if reasons else (WARN if dur < 45.0 else PASS)
    if verdict == WARN and not reasons:
        reasons.append(f"duracion {dur:.0f}s < 45s (guion corto?)")
    return verdict, metrics, reasons


def main(argv: List[str]) -> int:
    files = [Path(a) for a in argv] if argv else sorted(CAPS_DIR.glob("CapsulaExtensa-*.mp4"))
    if not files:
        print("No hay capsulas para verificar.")
        return 0
    print("=" * 68)
    print("COMPUERTA DE VERIFICACION - Capsulas Extensas (ECC verification-loop)")
    print("=" * 68)
    results = []
    worst = PASS
    for p in files:
        verdict, metrics, reasons = verify_one(p)
        results.append({"veredicto": verdict, **metrics, "motivos": reasons})
        print(f"\n{ICON[verdict]}{verdict}  {p.name}")
        print(f"    {metrics['duracion_s']}s  {metrics['resolucion']}  "
              f"{metrics['video']}+{metrics['audio']}  piel_max={metrics['piel_max']}")
        for r in reasons:
            print(f"      - {r}")
        if verdict == FAIL:
            worst = FAIL
        elif verdict == WARN and worst != FAIL:
            worst = WARN

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(
        {"generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "veredicto_global": worst, "capsulas": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("\n" + "=" * 68)
    n_fail = sum(1 for r in results if r["veredicto"] == FAIL)
    n_ok = sum(1 for r in results if r["veredicto"] == PASS)
    print(f"VEREDICTO GLOBAL: {worst}  ({n_ok} OK, {n_fail} FALLA de {len(results)})  "
          f"-> {'NO ENTREGAR (corregir)' if worst == FAIL else 'apto para entregar'}")
    print(f"Manifiesto: {MANIFEST}")
    print("=" * 68)
    return 2 if worst == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
