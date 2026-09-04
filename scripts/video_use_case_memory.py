"""video_use_case_memory.py - Memoria persistente + anti-duplicacion del
Video E2E Use Case Analyzer (ver skills/video-e2e-analyzer/SKILL.md).

Es el backing store MECANICO (hashing, similitud de texto, versionado) que el
agente (Copilot, al analizar un video) consulta ANTES de generar cualquier
conclusion. El analisis semantico (que hace el video, que casos de uso hay)
lo hace el agente; este script solo garantiza que:

  1. Un video ya analizado no se vuelva a procesar desde cero (identidad por
     SHA-256 + heuristica de "version/relacionado" por nombre+duracion).
  2. Un caso de uso no se duplique: se compara contra los existentes por
     similitud de texto (nombre/objetivo/actor/flujo) y se clasifica en
     NEW / EXISTING / UPDATE / DUPLICATE / RELATED.
  3. Toda la memoria queda en un unico JSON versionado, con historial de
     cambios (nunca se sobrescribe silenciosamente).

Esquema del JSON (memory/video_use_case_memory.json):
    memory_version, videos[], actors[], systems[], functionalities[],
    business_rules[], use_cases[], relationships[], analysis_history[]

Uso (CLI):
    python scripts/video_use_case_memory.py check-video --video <ruta>
    python scripts/video_use_case_memory.py register-video --video <ruta> --title "..." \
        [--functionalities F-001,F-002] [--use-cases UC-001,UC-002] [--parent <video_id>]
    python scripts/video_use_case_memory.py match-use-case --name "..." --objective "..." \
        --actor "..." [--flow "..."] [--functionality F-002]
    python scripts/video_use_case_memory.py add-use-case --name "..." --objective "..." \
        --actor "..." [--flow "..."] [--functionality F-002] [--business-rule BR-008] \
        --video <video_id> --ts-start 00:04:21 --ts-end 00:05:10 [--confidence HIGH]
    python scripts/video_use_case_memory.py add-evidence --use-case UC-003 --video <video_id> \
        --ts-start 00:04:21 --ts-end 00:05:10
    python scripts/video_use_case_memory.py update-use-case --use-case UC-003 --reason "..." \
        [--name ...] [--objective ...] [--flow ...] [--business-rule BR-008]
    python scripts/video_use_case_memory.py list-videos
    python scripts/video_use_case_memory.py list-use-cases
    python scripts/video_use_case_memory.py history [--entity UC-003]

Todas las salidas son JSON por stdout (facil de leer para el agente/Copilot).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
MEMORY_PATH = ROOT / "memory" / "video_use_case_memory.json"

MEMORY_VERSION = "1.0"

EMPTY_MEMORY: Dict = {
    "memory_version": MEMORY_VERSION,
    "videos": [],
    "actors": [],
    "systems": [],
    "functionalities": [],
    "business_rules": [],
    "use_cases": [],
    "relationships": [],
    "analysis_history": [],
}

# Umbrales de similitud (seccion 38/49 del spec): ajustables por --threshold-*.
THRESHOLD_DUPLICATE = 0.92
THRESHOLD_EXISTING = 0.75
THRESHOLD_RELATED = 0.55

# Nombre "familia" (v1/v2/final/final_2...) para detectar NEW_VERSION/RELATED_VIDEO
# aun cuando el hash cambio por completo (seccion 35).
_VERSION_SUFFIX_RX = re.compile(
    r"[-_\s]*(v\d+|version\s*\d+|final|final[-_\s]*\d+|copy|copia|rev\d*)$", re.I)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ----------------------------------------------------------------------------
# Identidad del video (seccion 32)
# ----------------------------------------------------------------------------

def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    """SHA-256 del contenido completo del archivo -> identificador principal."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return f"sha256:{h.hexdigest()}"


def probe_duration(path: Path) -> float:
    """Duracion en segundos (0.0 si no se puede determinar; no bloquea el flujo)."""
    try:
        import av
        c = av.open(str(path))
        d = float(c.duration / av.time_base) if c.duration else 0.0
        c.close()
        return d
    except Exception:
        return 0.0


def family_name(file_name: str) -> str:
    """Nombre 'base' sin version/sufijo, para agrupar v1/v2/final (seccion 35)."""
    stem = Path(file_name).stem.lower()
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    prev = None
    while prev != stem:
        prev = stem
        stem = _VERSION_SUFFIX_RX.sub("", stem).strip("-_ ")
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")


# ----------------------------------------------------------------------------
# Persistencia
# ----------------------------------------------------------------------------

def load() -> Dict:
    if MEMORY_PATH.exists():
        try:
            mem = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            for key, default in EMPTY_MEMORY.items():
                mem.setdefault(key, default if not isinstance(default, list) else [])
            return mem
        except json.JSONDecodeError:
            pass
    return json.loads(json.dumps(EMPTY_MEMORY))  # copia profunda


def save(mem: Dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")


def _log(mem: Dict, action: str, entity: str, reason: Optional[str] = None) -> None:
    entry = {"date": _now(), "action": action, "entity": entity}
    if reason:
        entry["reason"] = reason
    mem["analysis_history"].append(entry)


def _next_id(mem: Dict, key: str, prefix: str) -> str:
    n = 0
    for item in mem[key]:
        m = re.match(rf"{prefix}-(\d+)", item.get(f"{key[:-1]}_id" if key != "use_cases" else "use_case_id", ""))
        if m:
            n = max(n, int(m.group(1)))
    return f"{prefix}-{n + 1:03d}"


# ----------------------------------------------------------------------------
# Identidad / duplicados de VIDEO (secciones 33-36)
# ----------------------------------------------------------------------------

def classify_video(mem: Dict, path: Path) -> Dict:
    """EXACT_DUPLICATE / LIKELY_DUPLICATE / NEW_VERSION / RELATED_VIDEO / NEW_VIDEO."""
    vid = file_hash(path)
    duration = probe_duration(path)
    fam = family_name(path.name)

    exact = next((v for v in mem["videos"] if v["video_id"] == vid), None)
    if exact is not None:
        return {"status": "EXACT_DUPLICATE", "video_id": vid, "duration_seconds": duration,
                "match": exact}

    same_family = [v for v in mem["videos"] if family_name(v["file_name"]) == fam and fam]
    if same_family:
        # Duracion muy parecida (<=2%) + misma familia de nombre -> probable duplicado
        # semantico aunque el hash cambie (recompresion, recorte minimo, etc.).
        close = [v for v in same_family
                if duration and v.get("duration_seconds")
                and abs(v["duration_seconds"] - duration) / max(v["duration_seconds"], 1) <= 0.02]
        if close:
            return {"status": "LIKELY_DUPLICATE", "video_id": vid, "duration_seconds": duration,
                    "match": close[0], "family": fam}
        latest = max(same_family, key=lambda v: v.get("version", 1))
        return {"status": "NEW_VERSION", "video_id": vid, "duration_seconds": duration,
                "parent_video_id": latest["video_id"], "family": fam,
                "suggested_version": latest.get("version", 1) + 1}

    return {"status": "NEW_VIDEO", "video_id": vid, "duration_seconds": duration, "family": fam}


def register_video(mem: Dict, path: Path, title: Optional[str] = None,
                   functionalities: Optional[List[str]] = None,
                   use_cases: Optional[List[str]] = None,
                   parent_video_id: Optional[str] = None,
                   version: int = 1) -> Dict:
    vid = file_hash(path)
    existing = next((v for v in mem["videos"] if v["video_id"] == vid), None)
    if existing is not None:
        return existing
    entry = {
        "video_id": vid,
        "file_name": path.name,
        "title": title or path.stem,
        "duration_seconds": probe_duration(path),
        "version": version,
        "status": "PROCESSED",
        "processed_at": _now(),
        "functionalities": functionalities or [],
        "use_cases": use_cases or [],
    }
    if parent_video_id:
        entry["parent_video_id"] = parent_video_id
        entry["status"] = "NEW_VERSION"
    mem["videos"].append(entry)
    _log(mem, "CREATED", vid, reason=f"Video registrado: {path.name}")
    return entry


# ----------------------------------------------------------------------------
# Similitud / duplicados de CASO DE USO (secciones 37-40, 48-49)
# ----------------------------------------------------------------------------

def _ratio(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def use_case_similarity(candidate: Dict, existing: Dict) -> float:
    """Similitud ponderada: nombre/objetivo pesan mas que actor/flujo (seccion 37)."""
    weights = {"name": 0.35, "objective": 0.30, "actor": 0.10, "flow": 0.15, "trigger": 0.10}
    total_w = 0.0
    score = 0.0
    for field, w in weights.items():
        cv, ev = candidate.get(field), existing.get(field)
        if not cv and not ev:
            continue
        score += w * _ratio(str(cv or ""), str(ev or ""))
        total_w += w
    # Bono: comparten al menos una funcionalidad -> mismo dominio funcional.
    shared_func = set(candidate.get("functionalities", [])) & set(existing.get("functionalities", []))
    if shared_func:
        score += 0.05
        total_w += 0.05
    return score / total_w if total_w else 0.0


def classify_use_case(mem: Dict, candidate: Dict, *,
                      threshold_dup: float = THRESHOLD_DUPLICATE,
                      threshold_existing: float = THRESHOLD_EXISTING,
                      threshold_related: float = THRESHOLD_RELATED) -> Tuple[str, Optional[Dict], float]:
    """-> (status, best_match_or_None, score). Status en NEW/EXISTING/UPDATE/DUPLICATE/RELATED.

    UPDATE se decide aparte (llamalo explicitamente via update-use-case); aqui se
    distingue solo EXISTING (evidencia adicional, sin cambios) vs DUPLICATE
    (practicamente identico) vs RELATED (aparentado, pero funcionalidad distinta)."""
    best, best_score = None, 0.0
    for uc in mem["use_cases"]:
        s = use_case_similarity(candidate, uc)
        if s > best_score:
            best, best_score = uc, s
    if best is None or best_score < threshold_related:
        return "NEW", None, best_score
    if best_score >= threshold_dup:
        return "DUPLICATE", best, best_score
    if best_score >= threshold_existing:
        return "EXISTING", best, best_score
    return "RELATED", best, best_score


def add_use_case(mem: Dict, candidate: Dict, video_id: str, ts_start: str, ts_end: str,
                 confidence: str = "MEDIUM", screenshot_ids: Optional[List[str]] = None) -> Dict:
    uc_id = _next_id(mem, "use_cases", "UC")
    entry = {
        "use_case_id": uc_id,
        "name": candidate.get("name", ""),
        "version": 1,
        "status": "ACTIVE",
        "actor": candidate.get("actor", ""),
        "objective": candidate.get("objective", ""),
        "flow": candidate.get("flow", ""),
        "trigger": candidate.get("trigger", ""),
        "functionalities": candidate.get("functionalities", []),
        "business_rules": candidate.get("business_rules", []),
        "evidence": [{"video_id": video_id, "timestamp_start": ts_start, "timestamp_end": ts_end,
                     "screenshot_ids": screenshot_ids or []}],
        "confidence": confidence,
    }
    mem["use_cases"].append(entry)
    _log(mem, "CREATED", uc_id, reason=f"Nuevo caso de uso: {entry['name']}")
    return entry


def add_evidence(mem: Dict, use_case_id: str, video_id: str, ts_start: str, ts_end: str,
                 screenshot_ids: Optional[List[str]] = None) -> Optional[Dict]:
    uc = next((u for u in mem["use_cases"] if u["use_case_id"] == use_case_id), None)
    if uc is None:
        return None
    uc.setdefault("evidence", []).append({
        "video_id": video_id, "timestamp_start": ts_start, "timestamp_end": ts_end,
        "screenshot_ids": screenshot_ids or [],
    })
    _log(mem, "EVIDENCE_ADDED", use_case_id, reason=f"Nueva evidencia: {video_id} @ {ts_start}")
    return uc


def update_use_case(mem: Dict, use_case_id: str, changes: Dict, reason: str) -> Optional[Dict]:
    uc = next((u for u in mem["use_cases"] if u["use_case_id"] == use_case_id), None)
    if uc is None:
        return None
    mem.setdefault("analysis_history", [])
    snapshot = json.loads(json.dumps(uc))
    _log(mem, "UPDATED", use_case_id, reason=reason)
    mem["analysis_history"][-1]["previous_version_snapshot"] = snapshot
    for k, v in changes.items():
        if v is None:
            continue
        if k == "business_rules" and isinstance(v, list):
            uc.setdefault("business_rules", [])
            uc["business_rules"] = sorted(set(uc["business_rules"]) | set(v))
        else:
            uc[k] = v
    uc["version"] = uc.get("version", 1) + 1
    return uc


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Memoria persistente del Video E2E Use Case Analyzer.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-video", help="Identidad + deteccion de duplicado/version de un video")
    p.add_argument("--video", required=True)

    p = sub.add_parser("register-video", help="Registra un video en memoria (si no existe)")
    p.add_argument("--video", required=True)
    p.add_argument("--title")
    p.add_argument("--functionalities", help="Coma-separado: F-001,F-002")
    p.add_argument("--use-cases", help="Coma-separado: UC-001,UC-002")
    p.add_argument("--parent-video-id")
    p.add_argument("--version", type=int, default=1)

    p = sub.add_parser("match-use-case", help="Clasifica un candidato contra la memoria (sin crear)")
    p.add_argument("--name", required=True)
    p.add_argument("--objective", default="")
    p.add_argument("--actor", default="")
    p.add_argument("--flow", default="")
    p.add_argument("--trigger", default="")
    p.add_argument("--functionality", action="append", default=[])

    p = sub.add_parser("add-use-case", help="Crea (o reusa) un caso de uso segun el match")
    p.add_argument("--name", required=True)
    p.add_argument("--objective", default="")
    p.add_argument("--actor", default="")
    p.add_argument("--flow", default="")
    p.add_argument("--trigger", default="")
    p.add_argument("--functionality", action="append", default=[])
    p.add_argument("--business-rule", action="append", default=[])
    p.add_argument("--video", required=True, help="video_id (sha256:...) de la evidencia")
    p.add_argument("--ts-start", required=True)
    p.add_argument("--ts-end", required=True)
    p.add_argument("--screenshot", action="append", default=[])
    p.add_argument("--confidence", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"])
    p.add_argument("--force-new", action="store_true", help="Crea aunque haya match EXISTING/RELATED")

    p = sub.add_parser("add-evidence", help="Agrega evidencia a un caso de uso existente")
    p.add_argument("--use-case", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--ts-start", required=True)
    p.add_argument("--ts-end", required=True)
    p.add_argument("--screenshot", action="append", default=[])

    p = sub.add_parser("update-use-case", help="Actualiza un caso de uso (mantiene historial)")
    p.add_argument("--use-case", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--name")
    p.add_argument("--objective")
    p.add_argument("--flow")
    p.add_argument("--business-rule", action="append", default=None)
    p.add_argument("--confidence", choices=["HIGH", "MEDIUM", "LOW"])

    sub.add_parser("list-videos", help="Lista los videos en memoria")
    sub.add_parser("list-use-cases", help="Lista los casos de uso en memoria")

    p = sub.add_parser("history", help="Historial de cambios (analysis_history)")
    p.add_argument("--entity", help="Filtra por ID de entidad (video_id o UC-XXX)")

    args = ap.parse_args(argv)
    mem = load()

    if args.cmd == "check-video":
        result = classify_video(mem, Path(args.video))
        _print(result)
        return 0

    if args.cmd == "register-video":
        entry = register_video(
            mem, Path(args.video), title=args.title,
            functionalities=[s.strip() for s in args.functionalities.split(",")] if args.functionalities else [],
            use_cases=[s.strip() for s in args.use_cases.split(",")] if args.use_cases else [],
            parent_video_id=args.parent_video_id, version=args.version)
        save(mem)
        _print(entry)
        return 0

    if args.cmd == "match-use-case":
        candidate = {"name": args.name, "objective": args.objective, "actor": args.actor,
                    "flow": args.flow, "trigger": args.trigger, "functionalities": args.functionality}
        status, match, score = classify_use_case(mem, candidate)
        _print({"status": status, "score": round(score, 3), "match": match})
        return 0

    if args.cmd == "add-use-case":
        candidate = {"name": args.name, "objective": args.objective, "actor": args.actor,
                    "flow": args.flow, "trigger": args.trigger, "functionalities": args.functionality,
                    "business_rules": args.business_rule}
        status, match, score = classify_use_case(mem, candidate)
        if status in ("DUPLICATE", "EXISTING") and not args.force_new:
            uc = add_evidence(mem, match["use_case_id"], args.video, args.ts_start, args.ts_end,
                              args.screenshot)
            save(mem)
            _print({"status": status, "score": round(score, 3), "action": "EVIDENCE_ADDED",
                   "use_case": uc})
            return 0
        entry = add_use_case(mem, candidate, args.video, args.ts_start, args.ts_end,
                             confidence=args.confidence, screenshot_ids=args.screenshot)
        save(mem)
        _print({"status": "NEW" if status == "NEW" else status, "score": round(score, 3),
               "action": "CREATED", "use_case": entry, "related_to": match})
        return 0

    if args.cmd == "add-evidence":
        uc = add_evidence(mem, args.use_case, args.video, args.ts_start, args.ts_end, args.screenshot)
        if uc is None:
            _print({"error": f"No existe {args.use_case}"})
            return 1
        save(mem)
        _print(uc)
        return 0

    if args.cmd == "update-use-case":
        changes = {"name": args.name, "objective": args.objective, "flow": args.flow,
                  "business_rules": args.business_rule, "confidence": args.confidence}
        uc = update_use_case(mem, args.use_case, changes, args.reason)
        if uc is None:
            _print({"error": f"No existe {args.use_case}"})
            return 1
        save(mem)
        _print(uc)
        return 0

    if args.cmd == "list-videos":
        _print(mem["videos"])
        return 0

    if args.cmd == "list-use-cases":
        _print(mem["use_cases"])
        return 0

    if args.cmd == "history":
        hist = mem["analysis_history"]
        if args.entity:
            hist = [h for h in hist if h.get("entity") == args.entity]
        _print(hist)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
