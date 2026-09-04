# ============================================================================
# utils.py - Funciones auxiliares
# ============================================================================

import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from colorama import Fore, Style

# Extensiones de grabación admitidas (Teams/Zoom exportan distintos formatos)
VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm")
# Extensiones de transcripción externa (Teams "copiar transcripción", TXT, VTT)
TRANSCRIPT_EXTS = (".txt", ".vtt")

class Logger:
    """Logger con colores para consola y archivo"""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        
    def _write(self, level: str, message: str, color: str = ""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        # Consola con color
        print(f"{color}{log_message}{Style.RESET_ALL}")
        
        # Archivo sin color
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    def info(self, message: str):
        self._write("INFO", message, Fore.CYAN)
    
    def success(self, message: str):
        self._write("✓", message, Fore.GREEN)
    
    def warning(self, message: str):
        self._write("⚠", message, Fore.YELLOW)
    
    def error(self, message: str):
        self._write("✗", message, Fore.RED)
    
    def section(self, title: str):
        border = "═" * 60
        print(f"\n{Fore.BLUE}{border}")
        print(f"║ {title:<57} ║")
        print(f"{border}{Style.RESET_ALL}\n")


class ProjectPaths:
    """Gestión de rutas del proyecto"""
    
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            # Detectar raíz del proyecto
            current_file = Path(__file__)
            self.root = current_file.parent.parent
        else:
            self.root = Path(project_root)
        
        self.videos = self.root / "videos"
        self.transcripciones = self.root / "transcripciones"
        self.reuniones = self.root / "reuniones"
        self.estado = self.root / "estado"
        self.presentacion = self.root / "presentacion"
        self.scripts = self.root / "scripts"
        self.github = self.root / ".github"
        self.log_file = self.root / "scheduler.log"
    
    def ensure_dirs(self):
        """Crea directorios si no existen"""
        for path in [self.videos, self.transcripciones, self.reuniones, 
                     self.estado, self.presentacion]:
            path.mkdir(parents=True, exist_ok=True)
    
    def __repr__(self):
        return f"ProjectPaths(root={self.root})"


def format_duration(seconds: float) -> str:
    """Convierte segundos a formato HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def get_latest_video(videos_dir: Path) -> Optional[Path]:
    """Obtiene el video más reciente del directorio (cualquier formato admitido)."""
    videos = [p for ext in VIDEO_EXTS for p in videos_dir.glob(f"*{ext}")]
    if videos:
        return sorted(videos, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    return None


def normalize_date(value: Optional[str]) -> str:
    """Normaliza una fecha al formato interno YYYY-MM-DD.

    Acepta: None o 'hoy'/'today'/'now'/'ahora' (fecha actual), 'DD-MM-AAAA',
    'DD/MM/AAAA', 'AAAA-MM-DD' y 'AAAA/MM/DD'. Lanza ValueError si no es válida.
    """
    if value is None:
        return datetime.now().strftime("%Y-%m-%d")

    raw = value.strip().lower()
    if raw in ("hoy", "today", "now", "ahora"):
        return datetime.now().strftime("%Y-%m-%d")

    normalized = raw.replace("/", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(normalized, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(
        f"Fecha no válida: '{value}'. Usa 'hoy' o un formato como "
        f"'24-08-2026' (DD-MM-AAAA) o '2026-08-24' (AAAA-MM-DD)."
    )


def date_tag(value: str) -> str:
    """Token de fecha ESTÁNDAR para nombres de archivo y carpeta: DD-MM-AAAA.

    Acepta cualquier entrada admitida por normalize_date (hoy, DD-MM-AAAA,
    AAAA-MM-DD, DD/MM/AAAA) y devuelve siempre 'DD-MM-AAAA'.
    """
    return datetime.strptime(normalize_date(value), "%Y-%m-%d").strftime("%d-%m-%Y")


def _date_pattern(date_string: str) -> Optional[re.Pattern]:
    """Regex que reconoce la fecha en el nombre de un archivo, en varios formatos.

    Cubre AAAA-MM-DD y DD-MM-AAAA con separadores `-`, `_`, `.`, espacio o sin
    separador (p. ej. 'Grabación 2026-08-26 100002', 'reunion_26082026', '20260826').
    """
    try:
        d = datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        return None
    Y, M, D = d.strftime("%Y"), d.strftime("%m"), d.strftime("%d")
    sep = r"[-_.\s]?"
    iso = rf"{Y}{sep}{M}{sep}{D}"
    dmy = rf"{D}{sep}{M}{sep}{Y}"
    return re.compile(rf"(?:{iso}|{dmy})")


def get_video_for_date(videos_dir: Path, date_string: str) -> Optional[Path]:
    """Busca la grabación asociada a una fecha (YYYY-MM-DD).

    1) Por el nombre del archivo que contenga la fecha (varios formatos y
       separadores, p. ej. 'Grabación 2026-08-26 100002.mp4').
    2) Como respaldo, por la fecha de modificación del archivo (misma jornada).
    Devuelve None si no hay coincidencia.
    """
    pat = _date_pattern(date_string)
    videos = sorted(p for ext in VIDEO_EXTS for p in videos_dir.glob(f"*{ext}"))
    if pat is not None:
        for video in videos:
            if pat.search(video.stem):
                return video
    try:
        target = datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return None
    same_day = [v for v in videos
                if datetime.fromtimestamp(v.stat().st_mtime).date() == target]
    if same_day:
        return sorted(same_day, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    return None


def get_transcript_source_for_date(root: Path, date_string: str) -> Optional[Path]:
    """Busca una transcripción externa (Teams/TXT/VTT) para la fecha, por su nombre.

    Explora `videos/`, `transcripciones/` (raíz, carpeta mensual y carpeta del día)
    e `inbox/`, tomando el primer `.txt`/`.vtt` cuyo nombre contenga la fecha. No
    considera el `.md` ya generado del día (distinta extensión). Devuelve None si
    no hay coincidencia.
    """
    pat = _date_pattern(date_string)
    if pat is None:
        return None
    d = datetime.strptime(date_string, "%Y-%m-%d")
    tag = d.strftime("%d-%m-%Y")
    search_dirs = [
        root / "videos",
        root / "transcripciones",
        root / "transcripciones" / d.strftime("%m-%Y"),
        root / "transcripciones" / d.strftime("%m-%Y") / f"Daily {tag}",
        root / "inbox",
    ]
    for base in search_dirs:
        if not base.exists():
            continue
        candidates = sorted(p for ext in TRANSCRIPT_EXTS for p in base.glob(f"*{ext}"))
        for f in candidates:
            if pat.search(f.stem):
                return f
    return None



def get_transcription_file(transcriptions_dir: Path, date_string: str) -> Path:
    """Obtiene ruta del archivo de transcripción"""
    return transcriptions_dir / f"{date_tag(date_string)}.md"


def write_markdown_file(file_path: Path, title: str, content: str, header: Optional[dict] = None):
    """Escribe archivo Markdown con encabezado opcional"""
    lines = []
    
    if header:
        lines.append(f"# {title}\n")
        lines.append("## Información")
        for key, value in header.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
    else:
        lines.append(f"# {title}\n")
    
    lines.append(content)
    lines.append("\n---")
    lines.append(f"*Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
    
    file_path.write_text("\n".join(lines), encoding="utf-8")


def read_copilot_instructions(github_dir: Path) -> str:
    """Lee las instrucciones de Copilot"""
    instructions_file = github_dir / "copilot-instructions.md"
    if instructions_file.exists():
        return instructions_file.read_text(encoding="utf-8")
    return ""
