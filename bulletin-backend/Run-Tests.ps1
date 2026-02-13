<#
.SYNOPSIS
    Episcopal Bulletin Generator - Test Pipeline
    Run smoke, unit, and integration tests across all phases.

.EXAMPLE
    .\Run-Tests.ps1                    # All tests
    .\Run-Tests.ps1 -Smoke             # Quick smoke tests only
    .\Run-Tests.ps1 -Unit              # Unit tests (no server needed)
    .\Run-Tests.ps1 -Integration       # API tests (server must be running)
    .\Run-Tests.ps1 -Phase 3           # Only Phase 3 tests
    .\Run-Tests.ps1 -Coverage          # With coverage report
#>

param(
    [switch]$Smoke,
    [switch]$Unit,
    [switch]$Integration,
    [int]$Phase = 0,
    [switch]$Coverage,
    [string]$Port = "8002",
    [switch]$StartServer
)

$ErrorActionPreference = "Continue"
$BackendDir = "D:\Docker\bulletin-backend"

Write-Host ""
Write-Host "=== Episcopal Bulletin Generator - Test Pipeline ===" -ForegroundColor Cyan
Write-Host "    $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# ── Ensure we're in the right directory ──────────────────────────────────
if (-not (Test-Path "$BackendDir\app.py")) {
    Write-Host "[!!] Cannot find $BackendDir\app.py" -ForegroundColor Red
    Write-Host "     Run this script from the project root or adjust BackendDir." -ForegroundColor Red
    exit 1
}

Push-Location $BackendDir

# ── Install test dependencies ────────────────────────────────────────────
Write-Host "[1/5] Checking test dependencies..." -ForegroundColor Yellow
$deps = @("pytest", "httpx")
foreach ($dep in $deps) {
    $check = python -c "import $dep" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing $dep..." -ForegroundColor DarkGray
        python -m pip install $dep -q 2>$null
    }
}
if ($Coverage) {
    python -m pip install pytest-cov -q 2>$null
}
Write-Host "  [OK] Dependencies ready" -ForegroundColor Green

# ── Copy test file if needed ─────────────────────────────────────────────
Write-Host "[2/5] Setting up test file..." -ForegroundColor Yellow
$testFile = "$BackendDir\test_bulletin_api.py"
if (-not (Test-Path $testFile)) {
    Write-Host "  [!!] test_bulletin_api.py not found in $BackendDir" -ForegroundColor Red
    Write-Host "  Copy it from the deployment package first." -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  [OK] Test file found" -ForegroundColor Green

# ── Optionally start server ──────────────────────────────────────────────
$serverProcess = $null
if ($StartServer) {
    Write-Host "[3/5] Starting API server on port $Port..." -ForegroundColor Yellow
    $env:BULLETIN_API_URL = "http://localhost:$Port"
    $serverProcess = Start-Process python -ArgumentList "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", $Port -PassThru -NoNewWindow
    Start-Sleep -Seconds 3

    # Verify it started
    try {
        $health = Invoke-RestMethod "http://localhost:$Port/health" -TimeoutSec 5
        Write-Host "  [OK] Server running: $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "  [!!] Server failed to start" -ForegroundColor Red
        if ($serverProcess) { Stop-Process $serverProcess -Force -ErrorAction SilentlyContinue }
        Pop-Location
        exit 1
    }
} else {
    Write-Host "[3/5] Server management: manual (use -StartServer to auto-start)" -ForegroundColor DarkGray
    $env:BULLETIN_API_URL = "http://localhost:$Port"
}

# ── Build pytest command ─────────────────────────────────────────────────
Write-Host "[4/5] Running tests..." -ForegroundColor Yellow
Write-Host ""

$pytestArgs = @("test_bulletin_api.py", "-v", "--tb=short")

# Filter by test type
if ($Smoke) {
    $pytestArgs += "-k", "TestSmoke"
    Write-Host "  Mode: SMOKE tests only" -ForegroundColor DarkGray
}
elseif ($Unit) {
    $pytestArgs += "-k", "not api_live and not TestAPIEndpoints"
    Write-Host "  Mode: UNIT tests (no server needed)" -ForegroundColor DarkGray
}
elseif ($Integration) {
    $pytestArgs += "-k", "TestAPIEndpoints"
    Write-Host "  Mode: INTEGRATION tests (requires server)" -ForegroundColor DarkGray
}

# Filter by phase
if ($Phase -gt 0) {
    $phaseMap = @{
        1 = "TestHymn or TestDocx or TestSmoke"
        2 = "TestCalendar or TestLectionary"
        3 = "TestMusic"
        4 = "TestAsset"
    }
    if ($phaseMap.ContainsKey($Phase)) {
        $pytestArgs += "-k", $phaseMap[$Phase]
        Write-Host "  Phase: $Phase" -ForegroundColor DarkGray
    }
}

# Coverage
if ($Coverage) {
    $pytestArgs += "--cov=modules", "--cov-report=term-missing", "--cov-report=html:htmlcov"
}

Write-Host ""

# Run pytest
python -m pytest @pytestArgs
$testResult = $LASTEXITCODE

Write-Host ""

# ── Results ──────────────────────────────────────────────────────────────
Write-Host "[5/5] Results" -ForegroundColor Yellow
if ($testResult -eq 0) {
    Write-Host "  [OK] ALL TESTS PASSED" -ForegroundColor Green
} elseif ($testResult -eq 5) {
    Write-Host "  [--] No tests collected (check -k filter)" -ForegroundColor Yellow
} else {
    Write-Host "  [!!] SOME TESTS FAILED (exit code: $testResult)" -ForegroundColor Red
}

if ($Coverage) {
    Write-Host ""
    Write-Host "  Coverage report: $BackendDir\htmlcov\index.html" -ForegroundColor Cyan
}

# ── Cleanup ──────────────────────────────────────────────────────────────
if ($serverProcess) {
    Write-Host ""
    Write-Host "  Stopping test server..." -ForegroundColor DarkGray
    Stop-Process $serverProcess -Force -ErrorAction SilentlyContinue
}

Pop-Location
Write-Host ""
exit $testResult
