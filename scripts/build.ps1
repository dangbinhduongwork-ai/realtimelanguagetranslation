<#
.SYNOPSIS
    Builds the standalone Screen Translator Windows distribution executable using PyInstaller.

.DESCRIPTION
    Compiles Screen Translator into a standalone directory bundle (dist/ScreenTranslator),
    runs make_icon.py to create application icons, runs PyInstaller with screen_translator.spec,
    verifies the built executable with an automated --check --deep smoke test, and optionally
    archives the release as a zip file.

.PARAMETER Clean
    Removes existing build/ and dist/ directories before building.

.PARAMETER Console
    Builds with an attached debug console window (console=True) instead of a windowed app.

.PARAMETER Zip
    Archives dist/ScreenTranslator into dist/ScreenTranslator-<version>-win64.zip upon completion.

.EXAMPLE
    .\scripts\build.ps1 -Clean -Zip
    .\scripts\build.ps1 -Console
#>

[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$Console,
    [switch]$Zip
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $ProjectRoot

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "         Screen Translator - Windows Build          " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Root: $ProjectRoot"

# 1. Verify Python Environment (Python 3.10 - 3.12)
Write-Host "`n[1/6] Checking Python environment..." -ForegroundColor Yellow

$pyCmd = $null

# Check candidate paths first to avoid broken or unregistered Python launchers
$candidatePaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python310\python.exe"
)

foreach ($cand in $candidatePaths) {
    if (Test-Path $cand) {
        $pyCmd = $cand
        break
    }
}

if (-not $pyCmd) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $resolved = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null)
            if ($resolved -and (Test-Path $resolved.Trim())) {
                $pyCmd = $resolved.Trim()
            }
        } catch {}
    }
}

if (-not $pyCmd) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            $resolved = (& python -c "import sys; print(sys.executable)" 2>$null)
            if ($resolved -and (Test-Path $resolved.Trim())) {
                $pyCmd = $resolved.Trim()
            }
        } catch {}
    }
}

if (-not $pyCmd) {
    Write-Error "Python was not found. Please ensure Python (3.10-3.12) is installed."
    exit 1
}

Write-Host "Using Python executable: $pyCmd"

try {
    $pyVer = & $pyCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
} catch {
    Write-Error "Failed to execute Python ($pyCmd)."
    exit 1
}

Write-Host "Detected Python version: $pyVer"
if ($pyVer) {
    $match = [regex]::Match($pyVer.ToString().Trim(), '^(\d+)\.(\d+)')
    if ($match.Success) {
        $major = [int]$match.Groups[1].Value
        $minor = [int]$match.Groups[2].Value
        if ($major -ne 3 -or $minor -lt 10 -or $minor -gt 12) {
            Write-Warning "Python 3.10-3.12 is recommended. Running on Python $pyVer."
        }
    }
}

# 2. Clean previous build artifacts if requested
# Terminate any running ScreenTranslator processes to avoid file locks
Stop-Process -Name "ScreenTranslator" -Force -ErrorAction SilentlyContinue

if ($Clean) {
    Write-Host "`nCleaning build directories (-Clean requested)..." -ForegroundColor Yellow
    if (Test-Path "$ProjectRoot\build") {
        Remove-Item -Recurse -Force "$ProjectRoot\build"
        Write-Host "Removed build/"
    }
    if (Test-Path "$ProjectRoot\dist") {
        Remove-Item -Recurse -Force "$ProjectRoot\dist"
        Write-Host "Removed dist/"
    }
}

# 3. Install required build and runtime dependencies
Write-Host "`n[2/6] Installing dependencies..." -ForegroundColor Yellow
& $pyCmd -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install requirements.txt"
    exit 1
}

& $pyCmd -m pip install -q -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install requirements-build.txt"
    exit 1
}
Write-Host "Dependencies are up-to-date."

# 4. Generate application icon
Write-Host "`n[3/6] Generating icon (assets/app.ico)..." -ForegroundColor Yellow
& $pyCmd scripts/make_icon.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to generate application icon."
    exit 1
}

# 5. Execute PyInstaller packaging
Write-Host "`n[4/6] Running PyInstaller..." -ForegroundColor Yellow
if ($Console) {
    $env:BUILD_CONSOLE = "1"
    Write-Host "Build mode: DEBUG CONSOLE (console=True)" -ForegroundColor Magenta
} else {
    $env:BUILD_CONSOLE = "0"
    Write-Host "Build mode: WINDOWED APP (console=False)" -ForegroundColor Green
}

try {
    & $pyCmd -m PyInstaller --clean screen_translator.spec
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item env:BUILD_CONSOLE -ErrorAction SilentlyContinue
}

$exePath = "$ProjectRoot\dist\ScreenTranslator\ScreenTranslator.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Build verification failed: $exePath not found."
    exit 1
}
Write-Host "Built executable at: $exePath" -ForegroundColor Green

# 6. Automated Smoke Test: run dist\ScreenTranslator\ScreenTranslator.exe --check --deep
Write-Host "`n[5/6] Executing smoke test (--check --deep)..." -ForegroundColor Yellow
$smokeOut = "$ProjectRoot\build\smoke_stdout.log"
$smokeErr = "$ProjectRoot\build\smoke_stderr.log"
if (-not (Test-Path "$ProjectRoot\build")) {
    New-Item -ItemType Directory -Path "$ProjectRoot\build" -Force | Out-Null
}
$proc = Start-Process -FilePath $exePath -ArgumentList "--check", "--deep" -Wait -PassThru -RedirectStandardOutput $smokeOut -RedirectStandardError $smokeErr
if (Test-Path $smokeOut) {
    $outText = Get-Content $smokeOut -Raw
    if ($outText) {
        Write-Host $outText.Trim()
    }
}
if (Test-Path $smokeErr) {
    $errText = Get-Content $smokeErr -Raw
    if ($errText) {
        Write-Host $errText.Trim() -ForegroundColor Red
    }
}
if ($proc.ExitCode -ne 0) {
    Write-Error "Automated smoke test failed with exit code $($proc.ExitCode)!"
    exit $proc.ExitCode
}
Write-Host "Smoke test PASSED! Bundled OCR inference and configs verified successfully." -ForegroundColor Green

# 7. Package ZIP archive if requested
if ($Zip) {
    Write-Host "`n[6/6] Creating ZIP distribution..." -ForegroundColor Yellow
    $appVer = & $pyCmd -c "import sys; sys.path.insert(0, 'src'); import screen_translator; print(screen_translator.__version__)"
    if (-not $appVer) {
        $appVer = "1.0.0"
    }

    $zipName = "ScreenTranslator-$appVer-win64.zip"
    $zipPath = "$ProjectRoot\dist\$zipName"

    if (Test-Path $zipPath) {
        Remove-Item -Force $zipPath
    }

    $distFolder = "$ProjectRoot\dist\ScreenTranslator"
    Compress-Archive -Path $distFolder -DestinationPath $zipPath -Force
    Write-Host "Created release archive: $zipPath" -ForegroundColor Green

    $zipSize = (Get-Item $zipPath).Length
    $zipSizeMB = [math]::Round($zipSize / 1MB, 2)
    Write-Host "Archive size: $zipSizeMB MB"
}

# Calculate final dist folder size
$distFolder = "$ProjectRoot\dist\ScreenTranslator"
$totalBytes = (Get-ChildItem -Recurse $distFolder | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 2)

Write-Host "`n====================================================" -ForegroundColor Cyan
Write-Host "                  BUILD SUCCESSFUL                  " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Distribution Directory : $distFolder"
Write-Host "Total Uncompressed Size: $totalMB MB"
if ($Zip) {
    Write-Host "Distribution Archive   : $zipPath ($zipSizeMB MB)"
}
Write-Host "Launch with: dist\ScreenTranslator\ScreenTranslator.exe"
