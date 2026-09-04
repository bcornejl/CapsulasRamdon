# ============================================================================
# narration.py - Voz en off (TTS) en español latino para las cápsulas ejecutivas
#
# Genera la narración que EXPLICA lo que se muestra. Preferencia:
#   1) edge-tts  → voces NEURALES en español latino (es-MX/CO/AR/CL/US). Requiere
#      red; el SSL corporativo se resuelve con truststore (almacén de Windows).
#   2) pyttsx3   → voz local SAPI5 (offline) como respaldo si no hay red.
# El audio resultante lo mezcla el renderer (PyAV) sobre los clips.
# ============================================================================

import sys
from pathlib import Path
from typing import Optional

# Voces neurales en español latino (edge-tts). Alias cortos + nombre completo.
LATIN_VOICES = {
    "mx": "es-MX-DaliaNeural",   "mx-f": "es-MX-DaliaNeural",  "mx-m": "es-MX-JorgeNeural",
    "co": "es-CO-SalomeNeural",  "co-m": "es-CO-GonzaloNeural",
    "ar": "es-AR-ElenaNeural",   "ar-m": "es-AR-TomasNeural",
    "cl": "es-CL-CatalinaNeural", "cl-m": "es-CL-LorenzoNeural",
    "us": "es-US-PalomaNeural",  "us-m": "es-US-AlonsoNeural",
}
DEFAULT_VOICE = "es-MX-DaliaNeural"


class Narrator:
    """Sintetiza texto a voz en español latino (edge-tts → pyttsx3 de respaldo)."""

    def __init__(self, logger, voice: str = DEFAULT_VOICE, rate: str = "-5%"):
        self.logger = logger
        self.voice = LATIN_VOICES.get((voice or "").lower(), voice or DEFAULT_VOICE)
        self.rate = rate            # ligeramente más lento = más claro para ejecutivos
        self.backend: Optional[str] = None
        self._edge_ok = True        # se apaga si la red falla una vez

    def synthesize(self, text: str, out_stem: Path) -> Optional[Path]:
        """Devuelve la ruta del audio generado, o None si no se pudo sintetizar."""
        out_stem.parent.mkdir(parents=True, exist_ok=True)
        if self._edge_ok:
            p = self._edge(text, out_stem.with_suffix(".mp3"))
            if p is not None:
                self.backend = "edge-tts"
                return p
            self._edge_ok = False   # evita reintentar la red en cada línea
        p = self._pyttsx3(text, out_stem.with_suffix(".wav"))
        if p is not None:
            self.backend = "pyttsx3"
            return p
        return None

    def _edge(self, text: str, out_path: Path) -> Optional[Path]:
        try:
            try:
                import truststore
                truststore.inject_into_ssl()   # SSL corporativo (almacén de Windows)
            except Exception:
                pass
            import asyncio
            import edge_tts

            async def _run():
                await edge_tts.Communicate(text, self.voice, rate=self.rate).save(str(out_path))

            asyncio.run(_run())
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
            return None
        except Exception as e:
            self.logger.warning(f"Voz neural (edge-tts) no disponible ({e}); uso voz local.")
            return None

    def _pyttsx3(self, text: str, out_path: Path) -> Optional[Path]:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                meta = f"{v.id} {getattr(v, 'name', '')} {getattr(v, 'languages', '')}".lower()
                if any(k in meta for k in ("es-", "spanish", "español", "sabina", "helena", "laura")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 165)
            engine.save_to_file(text, str(out_path))
            engine.runAndWait()
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
            return None
        except Exception as e:
            self.logger.warning(f"Voz local (pyttsx3) no disponible ({e}); cápsula sin voz.")
            return None


if __name__ == "__main__":
    # Prueba rápida: python narration.py "texto" salida_stem [voz]
    class _L:
        def warning(self, m): print("WARN:", m)
    text = sys.argv[1] if len(sys.argv) > 1 else "Prueba de voz en español latino."
    stem = Path(sys.argv[2] if len(sys.argv) > 2 else "output/_narr_test")
    voice = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_VOICE
    out = Narrator(_L(), voice=voice).synthesize(text, stem)
    print("OK" if out else "FAIL", out)
