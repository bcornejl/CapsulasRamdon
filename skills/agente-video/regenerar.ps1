# ============================================================================
# regenerar.ps1 - Re-genera las 5 capsulas ejecutivas de un comando.
#   Imagen FIJA (--still) + UNA voz masculina latina (--script-file) + portada branded.
#   Uso (desde la raiz del repo):  .\.devin\skills\agente-video\regenerar.ps1
# Marcas y guiones curados el 2026-08-27 (ver SKILL.md > Recetas).
# ============================================================================
$ErrorActionPreference = "Stop"
$py  = ".\.venv\Scripts\python.exe"
$s   = "scripts\video_capsule.py"
$g   = ".devin\skills\agente-video\guiones"
$dst = "presentacion\ReporteVideo\08-2026"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

function Get-Vid($pat) {
    $f = Get-ChildItem "capsula" -Filter $pat -File | Select-Object -First 1
    if (-not $f) { throw "No se encontro capsula\$pat" }
    return $f.FullName
}

# Cada receta: patron del video, marcas --at, guion, tema (subtitulo), salida y extras.
$recetas = @(
    @{ pat = "*FrontEnd-Flujo-Jira.mp4"; at = "1:20,2:10,3:00,3:50,4:40,5:20,7:50,9:10,10:30,12:00,12:27"; guion = "frontend-jira.txt"; theme = "FrontEnd y Jira con el Framework Agentico"; out = "Capsula-Celula-Agentica-FrontEnd-Jira-27-08-2026.mp4"; extra = @() }
    @{ pat = "*ci-cd.mp4"; at = "1:00,1:15,1:30,0:03,0:15,0:27,0:39"; guion = "ci-cd.txt"; theme = "Integracion continua asistida por agentes"; out = "Capsula-Celula-Agentica-CI-CD-27-08-2026.mp4"; extra = @("--ordered") }
    @{ pat = "*QA.mp4"; at = "0:44,1:44,2:44,4:43,6:42,8:12,9:12,9:41,10:11,11:11"; guion = "qa.txt"; theme = "Calidad asistida por el Framework Agentico"; out = "Capsula-Celula-Agentica-QA-27-08-2026.mp4"; extra = @() }
    @{ pat = "*MesadeApi.mp4"; at = "0:33,3:57,7:21,10:44,13:00,15:16,17:32,22:03,24:19,32:14,37:54,44:41"; guion = "mesa-de-api.txt"; theme = "La mesa de API con el Framework Agentico"; out = "Capsula-Celula-Agentica-Mesa-de-API-27-08-2026.mp4"; extra = @() }
    @{ pat = "*Demo-FrontEnd.mp4"; at = "2:48,6:11,9:33,10:41,14:03,16:19,20:49,23:04,24:11,28:41,32:04,37:41"; guion = "digital-host.txt"; theme = "Desarrollo del Digital Host con el Framework Agentico"; out = "Capsula-Celula-Agentica-Digital-Host-27-08-2026.mp4"; extra = @() }
)

$t0 = Get-Date
foreach ($r in $recetas) {
    $vid = Get-Vid $r.pat
    $tmp = "output\_regen.mp4"
    Write-Host ("=> " + $r.out)
    # Render de UNA capsula (secuencial: nunca en paralelo, evita cortar el mp4).
    $a = @("-u", $s, "--video", $vid, "--at", $r.at, "--still", "--voice", "mx-m",
        "--script-file", (Join-Path $g $r.guion), "--theme", $r.theme, "--out", $tmp) + $r.extra
    & $py @a *> $null
    if (-not (Test-Path $tmp)) { throw "Fallo el render de $($r.out)" }
    Copy-Item $tmp (Join-Path $dst $r.out) -Force
}
Remove-Item "output\_regen.mp4" -ErrorAction SilentlyContinue
Write-Host ("LISTO: 5 capsulas en {0} ({1:N0}s)" -f $dst, ((Get-Date) - $t0).TotalSeconds)
