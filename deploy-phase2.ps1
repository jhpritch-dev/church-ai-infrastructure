<#
.SYNOPSIS
    Phase 2 Deploy: Liturgical Calendar + Lectionary Integration
.DESCRIPTION
    - Copies calendar_service.py and lectionary_service.py into bulletin-backend\modules\
    - Adds liturgical-calendar, httpx, redis to requirements.txt
    - Patches app.py with /api/lectionary/{date} and /api/calendar/{date} endpoints
    - ALL Python files are standalone (no inline generation)
.NOTES
    Place these 4 files in D:\Docker\ before running:
      deploy-phase2.ps1         (this script)
      calendar_service.py       (liturgical calendar module)
      lectionary_service.py     (RCL lectionary module)
      patch_app_phase2.py       (app.py patcher)
.EXAMPLE
    cd D:\Docker
    .\deploy-phase2.ps1 -LocalTest
#>

param(
    [switch]$LocalTest
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Phase 2 Deploy: Liturgical Calendar + Lectionary" -ForegroundColor Cyan
Write-Host "  =================================================" -ForegroundColor Cyan
Write-Host ""

# --- CONFIGURATION ---
$DockerBase   = "D:\Docker"
$BackendDir   = "$DockerBase\bulletin-backend"
$ModulesDir   = "$BackendDir\modules"
$AppPy        = "$BackendDir\app.py"
$ReqTxt       = "$BackendDir\requirements.txt"
$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- STEP 1: Verify Phase 1 exists ---
Write-Host "[1/5] Verifying Phase 1 installation..." -ForegroundColor Yellow

$requiredFiles = @(
    $AppPy,
    $ReqTxt,
    "$ModulesDir\hymn_lookup.py",
    "$ModulesDir\docx_generator.py",
    "$ModulesDir\__init__.py"
)

$missing = @()
foreach ($f in $requiredFiles) {
    if (Test-Path $f) {
        Write-Host "  [OK] $f" -ForegroundColor Green
    } else {
        Write-Host "  [!!] MISSING: $f" -ForegroundColor Red
        $missing += $f
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  ERROR: Phase 1 files missing. Run Phase 1 deploy first." -ForegroundColor Red
    exit 1
}

Write-Host ""

# --- STEP 2: Copy Python module files ---
Write-Host "[2/5] Copying Phase 2 modules..." -ForegroundColor Yellow

$sourceFiles = @{
    "$ScriptDir\calendar_service.py"   = "$ModulesDir\calendar_service.py"
    "$ScriptDir\lectionary_service.py" = "$ModulesDir\lectionary_service.py"
}

foreach ($src in $sourceFiles.Keys) {
    $dst = $sourceFiles[$src]
    if (-not (Test-Path $src)) {
        $filename = Split-Path $src -Leaf
        Write-Host "  [!!] $filename not found in $ScriptDir" -ForegroundColor Red
        Write-Host "  Download it from Claude and place next to this script." -ForegroundColor Yellow
        exit 1
    }
    Copy-Item $src $dst -Force
    Write-Host "  [OK] Copied $(Split-Path $src -Leaf)" -ForegroundColor Green
}

# Verify
if ((Test-Path "$ModulesDir\calendar_service.py") -and (Test-Path "$ModulesDir\lectionary_service.py")) {
    Write-Host "  [OK] Both modules verified on disk." -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Module files not found after copy." -ForegroundColor Red
    exit 1
}

Write-Host ""

# --- STEP 3: Update requirements.txt ---
Write-Host "[3/5] Updating requirements.txt..." -ForegroundColor Yellow

$currentReqs = Get-Content $ReqTxt -Raw
$newDeps = @("liturgical-calendar", "httpx", "redis")

foreach ($dep in $newDeps) {
    if ($currentReqs -notmatch [regex]::Escape($dep)) {
        Add-Content -Path $ReqTxt -Value $dep -Encoding UTF8
        Write-Host "  [+] Added: $dep" -ForegroundColor Green
    } else {
        Write-Host "  [=] Already present: $dep" -ForegroundColor Gray
    }
}

Write-Host ""

# --- STEP 4: Patch app.py with lectionary endpoints ---
Write-Host "[4/5] Patching app.py..." -ForegroundColor Yellow

$patcherPath = "$ScriptDir\patch_app_phase2.py"
if (-not (Test-Path $patcherPath)) {
    Write-Host "  [!!] patch_app_phase2.py not found in $ScriptDir" -ForegroundColor Red
    Write-Host "  Download it from Claude and place next to this script." -ForegroundColor Yellow
    exit 1
}

python "$patcherPath" "$AppPy"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] app.py patching failed." -ForegroundColor Red
    exit 1
}

Write-Host ""

# --- STEP 5: Test ---
Write-Host "[5/5] Running tests..." -ForegroundColor Yellow

if ($LocalTest) {
    Write-Host "  Testing module imports..." -ForegroundColor Gray

    Push-Location $BackendDir

    # Test calendar
    $calResult = python -c "import sys; sys.path.insert(0, '.'); from modules.calendar_service import get_calendar_info; info = get_calendar_info('2026-02-08'); print(f'Calendar: {info[""day_name""]} | Season: {info[""season""]} | Year: {info[""rcl_year""]}')" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $calResult" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Calendar test failed. Installing dependencies..." -ForegroundColor Yellow
        python -m pip install liturgical-calendar httpx redis 2>&1 | Out-Null

        $calResult2 = python -c "import sys; sys.path.insert(0, '.'); from modules.calendar_service import get_calendar_info; info = get_calendar_info('2026-02-08'); print(f'Calendar: {info[""day_name""]} | Season: {info[""season""]} | Year: {info[""rcl_year""]}')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] $calResult2" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $calResult2" -ForegroundColor Red
        }
    }

    # Test lectionary
    $lectResult = python -c "import sys; sys.path.insert(0, '.'); from modules.lectionary_service import LectionaryService; svc = LectionaryService(); r = svc.get_readings('2026-02-08', day_name='The Fifth Sunday after the Epiphany'); print(f'Readings source: {r[""source""]} | Gospel: {r.get(""readings"",{}).get(""gospel"",""N/A"")}')" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $lectResult" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Lectionary test: $lectResult" -ForegroundColor Yellow
    }

    Pop-Location
} else {
    Write-Host "  Skipping local tests (use -LocalTest flag to enable)." -ForegroundColor Gray
}

Write-Host ""
Write-Host "  =================================================" -ForegroundColor Cyan
Write-Host "  Phase 2 deployment complete!" -ForegroundColor Green
Write-Host "  =================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  New endpoints:" -ForegroundColor White
Write-Host "    GET /api/lectionary/{date}  - Calendar + RCL readings" -ForegroundColor Gray
Write-Host "    GET /api/calendar/{date}    - Calendar info only" -ForegroundColor Gray
Write-Host ""
Write-Host "  Test locally:" -ForegroundColor White
Write-Host "    cd $BackendDir" -ForegroundColor Gray
Write-Host "    python -m uvicorn app:app --host 0.0.0.0 --port 8001" -ForegroundColor Gray
Write-Host "    curl http://localhost:8001/api/lectionary/2026-02-08" -ForegroundColor Gray
Write-Host ""
Write-Host "  For Docker:" -ForegroundColor White
Write-Host "    cd $DockerBase" -ForegroundColor Gray
Write-Host "    docker compose build bulletin-api" -ForegroundColor Gray
Write-Host "    docker compose up -d bulletin-api" -ForegroundColor Gray
Write-Host ""
Write-Host "  Git commit:" -ForegroundColor White
Write-Host "    cd $DockerBase" -ForegroundColor Gray
Write-Host "    git add bulletin-backend/modules/calendar_service.py" -ForegroundColor Gray
Write-Host "    git add bulletin-backend/modules/lectionary_service.py" -ForegroundColor Gray
Write-Host "    git add bulletin-backend/requirements.txt bulletin-backend/app.py" -ForegroundColor Gray
Write-Host '    git commit -m "Phase 2: Liturgical calendar + RCL lectionary integration"' -ForegroundColor Gray
Write-Host "    git push" -ForegroundColor Gray
Write-Host ""
