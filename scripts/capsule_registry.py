"""capsule_registry.py - Registro de capsulas + bucle "¿hay mas casos?" (anti-duplicacion).

Inspirado en el patron de idempotencia/estado por proyecto de ECC
(skills/continuous-learning-v2) y en la descomposicion en subtareas verificables del
curso de Microsoft (07-planning-design). Objetivo del pedido del usuario:
"un bucle de revisar si existen mas casos cuando terminas" — SIN DUPLICAR.

Fuente de verdad:
- Registro JSON: <capsula-extensa>/_registro_capsulas.json  (que video+tema ya produjo capsula)
- Entregables de discovery: <capsula-extensa>/discovery/<slug>/03_casos_de_uso.md (temas detectados)
- Videos fuente: capsula/*.mp4

Uso:
    python scripts/capsule_registry.py more-cases      # reporta candidatos NUEVOS no duplicados
    python scripts/capsule_registry.py record --video <mp4> --topic "<tema>" --output <mp4> [--dur S --skin F]
    python scripts/capsule_registry.py list            # lista lo ya producido
"""
from __future__ import annotations
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

ROOT = Path(__file__).resolve().parent.parent
# Carpeta del mes vigente (o CAPSULA_MES="MM-AAAA" para apuntar a otro mes/proyecto).
import os as _os
_MES = _os.environ.get("CAPSULA_MES") or datetime.now().strftime("%m-%Y")
CAPS_DIR = ROOT / "presentacion" / "ReporteVideo" / _MES / "capsula-extensa"
SRC_DIR = ROOT / "capsula"
REGISTRY = CAPS_DIR / "_registro_capsulas.json"

# Temas canonicos (alineados con reel_discovery.DEMO_TOPICS + Concepto). Un tema cubierto
# por CUALQUIER capsula no se vuelve a proponer, aunque aparezca en otro video fuente.
# AJUSTAR por proyecto: estas claves/keywords describen los casos de uso del proyecto
# original; para un proyecto nuevo, edita este diccionario (y reel_discovery.DEMO_TOPICS)
# con los temas reales que ese proyecto demuestra.
CANON: Dict[str, List[str]] = {
    "CI/CD": ["cicd", "ci-cd", "ci/cd", "pipeline"],
    "QA / Pruebas": ["qa", "certificacion", "prueba", "pruebas"],
    "Jira / HDU": ["jira", "hdu", "flujo-jira", "historia"],
    "Agente / Framework (concepto)": ["concepto", "framework", "agente", "agentico", "que-es"],
    "Codigo / PR": ["codigo", "pr", "commit", "repositorio"],
    "API / Mesa": ["mesa", "api", "mesadeapi"],
    "Visualizador / Front (Digital Host)": ["visualizador", "digital-host", "digital host", "front"],
    "MCP / Integracion": ["mcp", "integracion"],
}


def canon_of(text: str) -> Optional[str]:
    """Mapea un texto (slug de archivo o nombre de tema del discovery) a un tema canonico."""
    t = text.lower()
    best = None
    for topic, kws in CANON.items():
        if any(kw in t for kw in kws):
            # Preferencia: 'digital host'/'visualizador' antes que 'front' generico ya cubre
            best = topic
            if any(kw in t for kw in kws[:2]):
                return topic
    return best


def load_registry() -> Dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"capsulas": [], "actualizado": None}


def save_registry(reg: Dict) -> None:
    reg["actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_from_outputs(reg: Dict) -> Dict:
    """Reconcilia el registro con los .mp4 realmente presentes (auto-descubrimiento)."""
    known = {c.get("output") for c in reg["capsulas"]}
    for mp4 in sorted(CAPS_DIR.glob("CapsulaExtensa-*.mp4")):
        if mp4.name in known:
            continue
        # nombre: CapsulaExtensa-<VideoSlug>-<TopicSlug>-<fecha>.mp4
        stem = mp4.stem[len("CapsulaExtensa-"):]
        stem = re.sub(r"-\d{2}-\d{2}-\d{4}$", "", stem)
        topic = canon_of(stem) or "(sin clasificar)"
        reg["capsulas"].append({
            "output": mp4.name, "tema_canonico": topic, "slug": stem,
            "origen": "auto-descubierto", "fecha": datetime.now().strftime("%Y-%m-%d"),
        })
    return reg


def covered_topics(reg: Dict) -> Dict[str, str]:
    """Temas canonicos ya cubiertos -> nombre de la capsula que los cubre."""
    out = {}
    for c in reg["capsulas"]:
        topic = c.get("tema_canonico") or canon_of(c.get("slug", ""))
        if topic and topic != "(sin clasificar)":
            out.setdefault(topic, c.get("output", "?"))
    return out


def _toks(s: str) -> set:
    """Tokens normalizados (sin 'grabacion'/'demo'/acentos) para emparejar nombres."""
    s = s.lower()
    for junk in ("grabación", "grabacion", "demo"):
        s = s.replace(junk, "")
    return set(t for t in re.split(r"[^a-z0-9]+", s) if t)


def _compact(s: str) -> str:
    """Nombre compacto alfanumerico (sin separadores) para match robusto: 'PrimerEntregable'
    y 'Primer-Entregable' colapsan a 'primerentregable'."""
    s = s.lower()
    for junk in ("grabación", "grabacion", "demo"):
        s = s.replace(junk, "")
    return re.sub(r"[^a-z0-9]+", "", s)


def _find_discovery(src_stem: str, disc_root: Path) -> Optional[Path]:
    """Empareja un video con SU carpeta de discovery por MAXIMO solape de tokens.

    Evita que 'Demo-FrontEnd-Flujo-Jira' se confunda con 'Demo-FrontEnd' (bug del
    emparejamiento por 'ultimo token'). El folder cuyos tokens son subconjunto del
    video y con mas coincidencias gana. La IGUALDAD por nombre compacto (sin
    separadores) manda: 'PrimerEntregable' == carpeta 'Primer-Entregable'."""
    vt = _toks(src_stem)
    vc = _compact(src_stem)
    best, best_score = None, 0
    for d in sorted(disc_root.glob("*/03_casos_de_uso.md")):
        dt = _toks(d.parent.name)
        if not dt:
            continue
        score = len(vt & dt)
        if dt <= vt:  # todos los tokens del folder estan en el video (match fuerte)
            score += len(dt)
        if vc and _compact(d.parent.name) == vc:  # match exacto robusto a separadores
            score += 10
        if score > best_score:
            best, best_score = d, score
    return best if best_score > 0 else None


def _span_min(tramo: str) -> float:
    """Minutos entre inicio y fin de un tramo 'HH:MM:SS-HH:MM:SS' (0 si no parsea)."""
    ts = re.findall(r"(\d{1,2}):(\d{2}):(\d{2})", tramo)
    if len(ts) < 2:
        return 0.0

    def _s(t):
        return int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2])
    return (_s(ts[-1]) - _s(ts[0])) / 60.0


def _parse_discovery(md: Path) -> List[Tuple[str, str, int]]:
    """Extrae (tema, tramo, menciones) de un 03_casos_de_uso.md."""
    if not md.exists():
        return []
    cases = []
    txt = md.read_text(encoding="utf-8")
    for m in re.finditer(r"## Caso \d+:\s*(.+)", txt):
        name = m.group(1).strip()
        tail = txt[m.end():m.end() + 400]
        tramo = re.search(r"\*\*Tramo:\*\*\s*([\d:]+)[–-]([\d:]+)", tail)
        menc = re.search(r"\*\*menciones:\*\*\s*(\d+)", tail)
        cases.append((name, tramo.group(0).replace("**Tramo:**", "").strip() if tramo else "?",
                      int(menc.group(1)) if menc else 0))
    return cases


def more_cases() -> int:
    """Bucle 'hay mas casos': reporta candidatos NUEVOS (no duplicados) por video fuente."""
    reg = _sync_from_outputs(load_registry())
    save_registry(reg)
    cov = covered_topics(reg)

    print("=" * 70)
    print("BUCLE 'HAY MAS CASOS' - candidatos NUEVOS sin duplicar")
    print("=" * 70)
    print(f"\nTemas YA CUBIERTOS ({len(cov)}):")
    for topic, out in sorted(cov.items()):
        print(f"  [x] {topic:38s} <- {out}")

    disc_root = CAPS_DIR / "discovery"
    candidates: List[Tuple[str, str, str, int]] = []  # (video, tema, tramo, menciones)
    print("\nPor video fuente:")
    for src in sorted(SRC_DIR.glob("*.mp4")):
        md = _find_discovery(src.stem, disc_root)
        print(f"\n  {src.name}")
        if md is None:
            print("    (sin discovery; corre deep_discovery para analizarlo)")
            continue
        for name, tramo, menc in _parse_discovery(md):
            topic = canon_of(name) or name
            covered = topic in cov
            span = _span_min(tramo)
            # Candidato real = suficientes menciones Y concentradas (no dispersas por
            # todo el video). Densidad <= 3 min/mencion evita falsos positivos como
            # 'Codigo/PR' = 5 menciones incidentales en 22 min (aprendido 2026-08-28).
            dens = (span / menc) if menc else 999.0
            focused = menc >= 4 and dens <= 3.0
            if covered:
                tag = "[YA CUBIERTO]"
            elif focused:
                tag = "[CANDIDATO NUEVO]"
                candidates.append((src.name, topic, tramo, menc))
            elif menc >= 4:
                tag = "[disperso: no enfocado]"
            else:
                tag = "[debil: pocas menciones]"
            print(f"    {tag:26s} {topic:34s} tramo={tramo}  menciones={menc}")

    print("\n" + "=" * 70)
    if candidates:
        # dedup por tema canonico (no proponer el mismo tema desde 2 videos)
        seen, uniq = set(), []
        for v, t, tr, mc in sorted(candidates, key=lambda x: -x[3]):
            if t in seen:
                continue
            seen.add(t)
            uniq.append((v, t, tr, mc))
        print(f"CANDIDATOS NUEVOS no duplicados: {len(uniq)}")
        for v, t, tr, mc in uniq:
            print(f"  -> {t:34s} (fuente: {v}, tramo {tr}, {mc} menciones)")
        print("\nSugerencia: valida en el 02_discovery/transcripcion que el tramo tenga demo")
        print("real en pantalla; cura guion grounded; marcas en ventana limpia; render+verify.")
    else:
        print("NO hay candidatos nuevos con suficiente contenido. La biblioteca esta completa")
        print("sin duplicar. (Los temas restantes aparecen solo como menciones dispersas.)")
    print("=" * 70)
    cleanup_report(build_video_report())
    return 0


# ---------------------------------------------------------------------------
# Limpieza de capsula/ (el USUARIO decide): registrar objetivo por video + borrado
# guardado. Un video procesado SIN casos nuevos = "no hay mas que fabricar" -> se
# PREGUNTA si eliminar el mp4; el registro conserva que se proceso y su objetivo.
# ---------------------------------------------------------------------------
def _cap_stem_tokens(output: str) -> set:
    stem = output[len("CapsulaExtensa-"):] if output.startswith("CapsulaExtensa-") else output
    return _toks(re.sub(r"-\d{2}-\d{2}-\d{4}$", "", stem))


def _caps_for_video(src_stem: str, reg: Dict, all_stems: List[str]) -> List[str]:
    """Capsulas producidas por un video: por video_fuente o por tokens (el mas especifico)."""
    vt = _toks(src_stem)
    caps: List[str] = []
    for c in reg["capsulas"]:
        out = c.get("output")
        if not out:
            continue
        vf = c.get("video_fuente")
        if vf:
            if _toks(Path(vf).stem) == vt:
                caps.append(out)
            continue
        ct = _cap_stem_tokens(out)
        if not vt or not (vt <= ct):
            continue
        # reclama la capsula solo si es el video MAS especifico cuyos tokens ⊆ la capsula
        if any((vt < _toks(o)) and (_toks(o) <= ct) for o in all_stems if o != src_stem):
            continue
        caps.append(out)
    return caps


def build_video_report() -> List[Dict]:
    """Objetivo + estado por cada video en capsula/ (para registrar y decidir limpieza)."""
    reg = _sync_from_outputs(load_registry())
    cov = covered_topics(reg)
    disc_root = CAPS_DIR / "discovery"
    stems = [s.stem for s in sorted(SRC_DIR.glob("*.mp4"))]
    report: List[Dict] = []
    for src in sorted(SRC_DIR.glob("*.mp4")):
        md = _find_discovery(src.stem, disc_root)
        temas: List[str] = []
        nuevos: List[str] = []
        if md is not None:
            for name, tramo, menc in _parse_discovery(md):
                topic = canon_of(name) or name
                span = _span_min(tramo)
                dens = (span / menc) if menc else 999.0
                temas.append(topic)
                if topic not in cov and menc >= 4 and dens <= 3.0:
                    nuevos.append(topic)
        caps = _caps_for_video(src.stem, reg, stems)
        # Objetivo = temas del discovery UNION los temas de las capsulas ya producidas
        # (un video con capsula esta procesado aunque el discovery no calce o sea parcial).
        cap_temas = [c.get("tema_canonico") for c in reg["capsulas"]
                     if c.get("output") in caps and c.get("tema_canonico")]
        temas = temas + cap_temas
        procesado = (md is not None) or bool(caps)
        report.append({
            "video": src.name,
            "discovery": md.parent.name if md else None,
            "objetivo": sorted(set(t for t in temas if t)),
            "capsulas": caps,
            "casos_nuevos": sorted(set(nuevos)),
            "procesado": procesado,
            "sin_casos_nuevos": (procesado and not nuevos),
        })
    return report


def cleanup_report(rep: List[Dict]) -> None:
    """Resumen de limpieza: que videos estan listos para que el USUARIO decida eliminarlos."""
    apt = [v for v in rep if v["sin_casos_nuevos"]]
    pend = [v for v in rep if not v["sin_casos_nuevos"]]
    if not (apt or pend):
        return
    print("\nLIMPIEZA de capsula/ (el USUARIO decide; el agente solo PREGUNTA):")
    if apt:
        print("  Sin casos nuevos -> no hay mas que fabricar (candidatos a eliminar):")
        for v in apt:
            print(f"    · {v['video']:42s} objetivo=[{', '.join(v['objetivo']) or '-'}]"
                  f"  capsulas={len(v['capsulas'])}")
        print("  Paso: 'record-videos' (guarda objetivo) -> preguntar al usuario ->")
        print("        'delete-video --name <mp4> --yes' SOLO si confirma.")
    for v in pend:
        razon = ("casos nuevos: " + ", ".join(v["casos_nuevos"])) if v["casos_nuevos"] else "sin discovery"
        print(f"  [NO borrar] {v['video']:42s} ({razon})")


def record_videos(_args) -> int:
    """Persiste el objetivo de cada video procesado (durable; sobrevive al borrado del mp4)."""
    reg = load_registry()
    rep = build_video_report()
    by_name = {v["video"]: v for v in reg.get("videos_procesados", [])}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for v in rep:
        prev = by_name.get(v["video"], {})
        entry = {**prev, **v}
        entry.setdefault("registrado", now)
        entry["actualizado"] = now
        by_name[v["video"]] = entry
    reg["videos_procesados"] = list(by_name.values())
    save_registry(reg)
    print(f"Registrados {len(rep)} video(s) con su objetivo:")
    for v in rep:
        estado = ("SIN CASOS NUEVOS" if v["sin_casos_nuevos"]
                  else ("CASOS NUEVOS: " + ", ".join(v["casos_nuevos"]) if v["casos_nuevos"]
                        else "SIN DISCOVERY (procesar primero)"))
        print(f"  - {v['video']:42s} objetivo=[{', '.join(v['objetivo']) or '-'}]  {estado}")
    return 0


def deletable_videos(_args) -> int:
    """Lista los videos aptos para eliminar (procesados y sin casos nuevos)."""
    cleanup_report(build_video_report())
    return 0


def delete_video(args) -> int:
    """Elimina un mp4 de capsula/ SOLO si esta registrado y sin casos nuevos. Conserva discovery + registro."""
    reg = load_registry()
    name = Path(args.name).name
    rec = {v["video"]: v for v in reg.get("videos_procesados", [])}
    v = rec.get(name)
    if v is None:
        print(f"[BLOQUEADO] {name} no esta registrado. Corre 'record-videos' antes de borrar "
              f"(para conservar su objetivo).")
        return 1
    if not v.get("procesado"):
        print(f"[BLOQUEADO] {name} no tiene discovery (no procesado). No se elimina.")
        return 1
    if v.get("casos_nuevos"):
        print(f"[BLOQUEADO] {name} tiene casos NUEVOS por fabricar: {', '.join(v['casos_nuevos'])}. "
              f"Fabrica su capsula antes de eliminar.")
        return 1
    p = SRC_DIR / name
    if not p.exists():
        print(f"[SKIP] {name} ya no esta en capsula/ (registro conservado).")
        return 0
    if not args.yes:
        print(f"[DRY-RUN] Eliminaria {name}. Objetivo conservado: [{', '.join(v['objetivo'])}]. "
              f"Usa --yes para confirmar.")
        return 0
    p.unlink()
    v["eliminado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reg["videos_procesados"] = [v if x["video"] == name else x for x in reg.get("videos_procesados", [])]
    save_registry(reg)
    print(f"Eliminado {name}. Registro conservado (objetivo: [{', '.join(v['objetivo'])}]; "
          f"capsulas: {len(v['capsulas'])}; discovery: {v.get('discovery')}).")
    return 0


def record(args) -> int:
    reg = load_registry()
    out_name = Path(args.output).name if args.output else None
    # upsert: no duplicar si ya existe una entrada con el mismo output
    if out_name:
        reg["capsulas"] = [c for c in reg["capsulas"] if c.get("output") != out_name]
    reg["capsulas"].append({
        "output": out_name,
        "video_fuente": Path(args.video).name if args.video else None,
        "tema_canonico": canon_of(args.topic) or args.topic,
        "tema": args.topic,
        "duracion_s": args.dur, "piel_max": args.skin,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "origen": "record",
    })
    save_registry(reg)
    print(f"Registrada: {args.topic} -> {args.output}")
    return 0


def list_caps(_args) -> int:
    reg = _sync_from_outputs(load_registry())
    save_registry(reg)
    print(f"Capsulas registradas: {len(reg['capsulas'])}")
    for c in reg["capsulas"]:
        print(f"  - {c.get('tema_canonico','?'):38s} {c.get('output','?')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Registro de capsulas y bucle 'hay mas casos'.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("more-cases", help="Reporta candidatos nuevos no duplicados")
    sub.add_parser("list", help="Lista capsulas producidas")
    sub.add_parser("record-videos", help="Registra el objetivo de cada video procesado (durable)")
    sub.add_parser("deletable", help="Lista videos aptos para eliminar (sin casos nuevos)")
    dv = sub.add_parser("delete-video", help="Elimina un mp4 procesado sin casos nuevos (conserva registro)")
    dv.add_argument("--name", type=str, required=True, help="Nombre del mp4 en capsula/")
    dv.add_argument("--yes", action="store_true", help="Confirma el borrado (sin esto, dry-run)")
    r = sub.add_parser("record", help="Registra una capsula producida")
    r.add_argument("--video", type=str, help="Video fuente")
    r.add_argument("--topic", type=str, required=True, help="Tema de la capsula")
    r.add_argument("--output", type=str, help="MP4 de salida")
    r.add_argument("--dur", type=float, default=None, help="Duracion (s)")
    r.add_argument("--skin", type=float, default=None, help="Piel maxima (verificacion)")
    args = ap.parse_args()
    if args.cmd == "more-cases":
        return more_cases()
    if args.cmd == "list":
        return list_caps(args)
    if args.cmd == "record-videos":
        return record_videos(args)
    if args.cmd == "deletable":
        return deletable_videos(args)
    if args.cmd == "delete-video":
        return delete_video(args)
    if args.cmd == "record":
        return record(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
