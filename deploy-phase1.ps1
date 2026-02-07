<#
.SYNOPSIS
    Episcopal Bulletin Generator - Phase 1 Deployment Script
.DESCRIPTION
    Sets up the bulletin-backend and flask-web-gui directories,
    creates required Docker volumes, and optionally builds/starts containers.
.EXAMPLE
    .\deploy-phase1.ps1
    .\deploy-phase1.ps1 -SkipBuild
    .\deploy-phase1.ps1 -LocalTest
#>

param(
    [switch]$SkipBuild,
    [switch]$SkipDeploy,
    [switch]$LocalTest
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Episcopal Bulletin Generator - Phase 1 Deploy" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

$DockerBase = "D:\Docker"

# ── Step 1: Create volume directories ────────────────────────────────────

Write-Host "[1/5] Creating Docker volume directories..." -ForegroundColor Yellow

$dirs = @(
    "$DockerBase\bulletin\assets",
    "$DockerBase\bulletin\bulletins",
    "$DockerBase\bulletin\templates",
    "$DockerBase\flask-web-gui\static",
    "$DockerBase\flask-web-gui\templates",
    "$DockerBase\datasets\BCP-Source",
    "$DockerBase\datasets\daily-office"
)

foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        Write-Host "  [+] Created: $d" -ForegroundColor Green
    } else {
        Write-Host "  [=] Exists:  $d" -ForegroundColor DarkGray
    }
}

# ── Step 2: Verify source files ──────────────────────────────────────────

Write-Host ""
Write-Host "[2/5] Verifying deployment files..." -ForegroundColor Yellow

$requiredFiles = @(
    "$DockerBase\bulletin-backend\app.py",
    "$DockerBase\bulletin-backend\Dockerfile",
    "$DockerBase\bulletin-backend\requirements.txt",
    "$DockerBase\bulletin-backend\modules\__init__.py",
    "$DockerBase\bulletin-backend\modules\hymn_lookup.py",
    "$DockerBase\bulletin-backend\modules\docx_generator.py",
    "$DockerBase\bulletin-backend\data\hymnal_1982.json",
    "$DockerBase\flask-web-gui\app.py",
    "$DockerBase\flask-web-gui\Dockerfile",
    "$DockerBase\flask-web-gui\requirements.txt",
    "$DockerBase\flask-web-gui\templates\index.html",
    "$DockerBase\docker-compose.yml"
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
    Write-Host "  ERROR: $($missing.Count) required files are missing." -ForegroundColor Red
    Write-Host "  Copy the Phase 1 deploy files to D:\Docker\ first." -ForegroundColor Red
    Write-Host "  Missing:" -ForegroundColor Red
    foreach ($m in $missing) {
        Write-Host "    - $m" -ForegroundColor Red
    }
    exit 1
}

# ── Step 3: Local test (optional) ────────────────────────────────────────

if ($LocalTest) {
    Write-Host ""
    Write-Host "[3/5] Running local API test..." -ForegroundColor Yellow

    Push-Location "$DockerBase\bulletin-backend"

    # Check Python dependencies
    Write-Host "  Checking Python dependencies..." -ForegroundColor DarkGray
    python -m pip install -q fastapi uvicorn python-docx pydantic python-multipart 2>$null

    # Test imports
    Write-Host "  Testing module imports..." -ForegroundColor DarkGray
    $importTest = python -c "
import sys; sys.path.insert(0, '.')
from modules.hymn_lookup import lookup_hymn
from modules.docx_generator import generate_bulletin
hymn = lookup_hymn('390')
print(f'Hymn 390: {hymn[""title""]}')
print('All modules OK')
" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $importTest" -ForegroundColor Green
    } else {
        Write-Host "  [!!] Import test failed: $importTest" -ForegroundColor Red
    }

    Pop-Location

    Write-Host ""
    Write-Host "  To start the local API server:" -ForegroundColor Cyan
    Write-Host "    cd $DockerBase\bulletin-backend" -ForegroundColor White
    Write-Host "    python -m uvicorn app:app --host 0.0.0.0 --port 8001" -ForegroundColor White
    Write-Host "  Then open: http://localhost:8001/docs" -ForegroundColor White
    Write-Host ""

    if (-not $SkipBuild) {
        Write-Host "  Skipping Docker build in LocalTest mode." -ForegroundColor DarkGray
    }
    exit 0
}

# ── Step 4: Docker build ─────────────────────────────────────────────────

if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[4/5] Building Docker images..." -ForegroundColor Yellow

    Push-Location $DockerBase
    docker compose build bulletin-api flask-web-gui
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [!!] Docker build failed." -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Write-Host "  [OK] Images built successfully." -ForegroundColor Green
    Pop-Location
} else {
    Write-Host ""
    Write-Host "[4/5] Skipping Docker build (--SkipBuild)" -ForegroundColor DarkGray
}

# ── Step 5: Deploy ───────────────────────────────────────────────────────

if (-not $SkipDeploy) {
    Write-Host ""
    Write-Host "[5/5] Starting services..." -ForegroundColor Yellow

    Push-Location $DockerBase
    docker compose up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [!!] Docker start failed." -ForegroundColor Red
        Pop-Location
        exit 1
    }

    Write-Host ""
    Write-Host "  Waiting for services to initialize..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 10

    docker compose ps
    Pop-Location

    Write-Host ""
    Write-Host "  ================================================" -ForegroundColor Green
    Write-Host "  Phase 1 deployment complete!" -ForegroundColor Green
    Write-Host "  ================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Flask Dashboard:  http://localhost:5000" -ForegroundColor White
    Write-Host "  Bulletin API:     http://localhost:8001/docs" -ForegroundColor White
    Write-Host "  API Form:         http://localhost:8001/form" -ForegroundColor White
    Write-Host "  Hymn Lookup:      http://localhost:8001/hymn/390" -ForegroundColor White
    Write-Host "  Paperless-NGX:    http://localhost:8080" -ForegroundColor White
    Write-Host "  Open Notebook:    http://localhost:3030" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[5/5] Skipping deployment (--SkipDeploy)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  To deploy manually:" -ForegroundColor Cyan
    Write-Host "    cd $DockerBase" -ForegroundColor White
    Write-Host "    docker compose up -d" -ForegroundColor White
}
