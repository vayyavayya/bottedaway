<#
.SYNOPSIS
  One-click installer for the RadBrain capture side on the Windows PC.

.DESCRIPTION
  Run as user Gaming in an elevated PowerShell, from the folder that contains this script:
      powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
  Remove the scheduled tasks again (the data dir is NEVER deleted):
      powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall

  Steps (idempotent, safe to re-run):
    1. Python 3.12 (winget Python.Python.3.12) and Tesseract (winget UB-Mannheim.TesseractOCR)
    2. German traineddata (tessdata_best deu.traineddata) into the Tesseract tessdata dir if missing
    3. C:\RadBrain\app  = copy of this folder (radbrain package etc.), venv in C:\RadBrain\venv,
       pip install -r requirements-win.txt (+ optional windows-capture)
    4. %LOCALAPPDATA%\RadBrain with a signers.json template (config.write_signers_template())
    5. Scheduled tasks for the user, "At log on", interactive only (screen capture and hotkeys need the
       user's desktop, never SYSTEM / session 0), restart on failure 3x every 1 min:
         \RadBrain\RadBrain Capture    pythonw -m radbrain.capture.hotkey_app
         \RadBrain\RadBrain Dashboard  pythonw -m radbrain.web --host 127.0.0.1 --port 8650
       and starts both now
    6. ollama pull bge-m3 if the local Ollama does not have it yet
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [string]$Root = "C:\RadBrain",
    [string]$TaskUser = "Gaming",
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$AppDir = Join-Path $Root "app"
$VenvDir = Join-Path $Root "venv"
$TaskPath = "\RadBrain\"
$TaskNames = @("RadBrain Capture", "RadBrain Dashboard")
$DataDir = Join-Path $env:LOCALAPPDATA "RadBrain"
$Summary = [ordered]@{}

function Step([string]$msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok([string]$k, [string]$v) { $Summary[$k] = $v; Write-Host "    $k : $v" -ForegroundColor Green }
function Warn([string]$k, [string]$v) { $Summary[$k] = "WARN - $v"; Write-Host "    $k : $v" -ForegroundColor Yellow }

# Windows PowerShell 5.1 turns redirected native stderr into terminating errors under "Stop"
function Invoke-Native([scriptblock]$Block) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Block } finally { $ErrorActionPreference = $old }
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stop-RadBrainTasks {
    foreach ($n in $TaskNames) {
        $t = Get-ScheduledTask -TaskPath $TaskPath -TaskName $n -ErrorAction SilentlyContinue
        if ($t) { Stop-ScheduledTask -TaskPath $TaskPath -TaskName $n -ErrorAction SilentlyContinue }
    }
    # pythonw children survive Stop-ScheduledTask in some cases: end only OUR interpreters
    $venvPy = (Join-Path $VenvDir "Scripts").ToLower()
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($venvPy) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Show-Summary {
    Write-Host ""
    Write-Host "================ RadBrain install summary ================" -ForegroundColor Cyan
    foreach ($k in $Summary.Keys) { "{0,-22} {1}" -f $k, $Summary[$k] | Write-Host }
    Write-Host "==========================================================" -ForegroundColor Cyan
}

# ------------------------------------------------------------------------------------------- uninstall
if ($Uninstall) {
    Step "Removing scheduled tasks (data dir $DataDir is kept)"
    Stop-RadBrainTasks
    foreach ($n in $TaskNames) {
        if (Get-ScheduledTask -TaskPath $TaskPath -TaskName $n -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $n -Confirm:$false
            Ok $n "removed"
        } else { Ok $n "not registered" }
    }
    Ok "Data dir" "$DataDir (kept)"
    Ok "App dir" "$AppDir (kept; delete by hand if wanted)"
    Show-Summary
    exit 0
}

if (-not (Test-Admin)) {
    Write-Host "Please run this script in an elevated PowerShell (Run as administrator)." -ForegroundColor Red
    exit 1
}
$SourceDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $SourceDir "radbrain\config.py"))) {
    Write-Host "radbrain\config.py not found next to install.ps1 ($SourceDir)." -ForegroundColor Red
    exit 1
}
$HasWinget = [bool](Get-Command winget.exe -ErrorAction SilentlyContinue)

function Invoke-Winget([string]$id) {
    if (-not $HasWinget) { throw "winget not available - install $id by hand" }
    Invoke-Native { & winget.exe install --id $id -e --silent --accept-package-agreements --accept-source-agreements }
    # 0 = installed; -1978335189 (0x8A15002B) = already installed / no upgrade
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { throw "winget install $id failed ($LASTEXITCODE)" }
}

# ------------------------------------------------------------------------------------------- 1. Python
function Find-Python312 {
    $cands = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe")
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $p = Invoke-Native { & py.exe -3.12 -c "import sys; print(sys.executable)" 2>$null }
        if ($LASTEXITCODE -eq 0 -and $p) { return ($p | Select-Object -First 1).Trim() }
    }
    return $null
}

Step "Python 3.12"
$Py = Find-Python312
if (-not $Py) {
    Invoke-Winget "Python.Python.3.12"
    $Py = Find-Python312
}
if (-not $Py) { throw "Python 3.12 not found after winget install" }
Ok "Python" $Py

# ------------------------------------------------------------------------------------------- 2. Tesseract
function Find-Tesseract {
    $cands = @(
        (Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Tesseract-OCR\tesseract.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR\tesseract.exe")
    )
    foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
    $cmd = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

Step "Tesseract OCR + German traineddata"
$Tess = Find-Tesseract
if (-not $Tess) {
    Invoke-Winget "UB-Mannheim.TesseractOCR"
    $Tess = Find-Tesseract
}
if (-not $Tess) { throw "tesseract.exe not found after winget install" }
Ok "Tesseract" $Tess
$TessData = Join-Path (Split-Path $Tess -Parent) "tessdata"
New-Item -ItemType Directory -Force -Path $TessData | Out-Null
$Deu = Join-Path $TessData "deu.traineddata"
if (-not (Test-Path $Deu)) {
    $url = "https://github.com/tesseract-ocr/tessdata_best/raw/main/deu.traineddata"
    Write-Host "    downloading $url"
    $tmp = Join-Path $env:TEMP "deu.traineddata.download"
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
    if ((Get-Item $tmp).Length -lt 1000000) { throw "deu.traineddata download looks truncated" }
    Move-Item -Force $tmp $Deu
    Ok "deu.traineddata" "installed (tessdata_best) -> $Deu"
} else {
    Ok "deu.traineddata" "present ($Deu)"
}

# ------------------------------------------------------------------------------------------- 3. app + venv
Step "App copy $AppDir and venv $VenvDir"
Stop-RadBrainTasks
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
& robocopy.exe $SourceDir $AppDir /MIR /NFL /NDL /NJH /NJS /NP /XD .venv venv __pycache__ .pytest_cache .git /XF *.pyc | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
$global:LASTEXITCODE = 0
Ok "App" $AppDir

$VPy = Join-Path $VenvDir "Scripts\python.exe"
$VPyw = Join-Path $VenvDir "Scripts\pythonw.exe"
if (-not (Test-Path $VPy)) {
    Invoke-Native { & $Py -m venv $VenvDir }
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
Invoke-Native { & $VPy -m pip install --disable-pip-version-check -q --upgrade pip }
Invoke-Native { & $VPy -m pip install --disable-pip-version-check -q -r (Join-Path $AppDir "requirements-win.txt") }
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements-win.txt failed" }
Invoke-Native { & $VPy -m pip install --disable-pip-version-check -q windows-capture 2>$null }
if ($LASTEXITCODE -eq 0) { Ok "windows-capture" "installed (WGC available)" } else { Warn "windows-capture" "not installed (optional)" }
$global:LASTEXITCODE = 0
# make "import radbrain" work from anywhere in this venv
$SitePk = (& $VPy -c "import sysconfig; print(sysconfig.get_paths()['purelib'])").Trim()
Set-Content -Path (Join-Path $SitePk "radbrain_app.pth") -Value $AppDir -Encoding ASCII
Ok "Venv" $VenvDir

# ------------------------------------------------------------------------------------------- 4. data dir
Step "Data dir $DataDir"
Push-Location $AppDir
try {
    $sig = & $VPy -c "from radbrain import config; print(config.write_signers_template())"
    if ($LASTEXITCODE -ne 0) { throw "signers template failed" }
} finally { Pop-Location }
Ok "signers.json" "$sig (fill in the B1/B2/B3 surnames; never committed)"
& $VPy -c "from radbrain.capture.ocr import available_backends as a; import json; print(json.dumps(a()))" |
    ForEach-Object { Ok "OCR backends" $_ }

# ------------------------------------------------------------------------------------------- 5. tasks
Step "Scheduled tasks for $TaskUser (At log on, interactive)"
$principal = New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType Interactive -RunLevel Limited
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew
$defs = @(
    @{ Name = "RadBrain Capture";   Args = "-m radbrain.capture.hotkey_app" },
    @{ Name = "RadBrain Dashboard"; Args = "-m radbrain.web --host 127.0.0.1 --port 8650" }
)
foreach ($d in $defs) {
    $action = New-ScheduledTaskAction -Execute $VPyw -Argument $d.Args -WorkingDirectory $AppDir
    Register-ScheduledTask -TaskPath $TaskPath -TaskName $d.Name -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description "RadBrain (local only, no cloud)" -Force | Out-Null
    if (-not $NoStart) {
        Start-ScheduledTask -TaskPath $TaskPath -TaskName $d.Name
        Ok $d.Name "registered + started"
    } else {
        Ok $d.Name "registered"
    }
}

# ------------------------------------------------------------------------------------------- 6. Ollama
Step "Ollama embedding model bge-m3"
$Ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
if (-not $Ollama) {
    $cand = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $cand) { $Ollama = Get-Item $cand }
}
if ($Ollama) {
    $exe = if ($Ollama.Source) { $Ollama.Source } else { $Ollama.FullName }
    $list = Invoke-Native { & $exe list 2>$null | Out-String }
    if ($LASTEXITCODE -ne 0) {
        Warn "bge-m3" "ollama list failed (is the Ollama service running?)"
    } elseif ($list -match "(?m)^bge-m3") {
        Ok "bge-m3" "already pulled"
    } else {
        Invoke-Native { & $exe pull bge-m3 }
        if ($LASTEXITCODE -eq 0) { Ok "bge-m3" "pulled" } else { Warn "bge-m3" "pull failed" }
    }
} else {
    Warn "bge-m3" "ollama.exe not found - pull bge-m3 by hand"
}
$global:LASTEXITCODE = 0

Start-Sleep -Seconds 3
foreach ($n in $TaskNames) {
    $info = Get-ScheduledTask -TaskPath $TaskPath -TaskName $n -ErrorAction SilentlyContinue
    if ($info) { Ok "$n state" $info.State }
}
Ok "Dashboard" "http://127.0.0.1:8650"
Ok "Next" "1) fill $DataDir\signers.json  2) python -m radbrain.capture.probe_citrix  3) tray > Recalibrate (pair)"
Show-Summary
