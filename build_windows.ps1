$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $Root

Write-Host ""
Write-Host "============================================"
Write-Host " KAKAFANDODO - BUILD WINDOWS"
Write-Host "============================================"
Write-Host ""


$GodotExe = Join-Path `
    $Root `
    "build\godot\kakafandodo2d.exe"

$GodotPck = Join-Path `
    $Root `
    "build\godot\kakafandodo2d.pck"

$SpecFile = Join-Path `
    $Root `
    "launcher\kakafandodo.spec"

$Venv = Join-Path `
    $Root `
    ".buildvenv"

$Dist = Join-Path `
    $Root `
    "dist"

$Work = Join-Path `
    $Root `
    "pyinstaller-build"


Write-Host "[1/7] Verification export Godot..."

if (-not (Test-Path $GodotExe)) {
    throw "Fichier manquant : $GodotExe"
}

if (-not (Test-Path $GodotPck)) {
    throw "Fichier manquant : $GodotPck"
}

if (-not (Test-Path $SpecFile)) {
    throw "Fichier manquant : $SpecFile"
}


Write-Host "[2/7] Environnement Python..."

if (-not (Test-Path "$Venv\Scripts\python.exe")) {

    Write-Host "Creation de .buildvenv..."

    py -m venv $Venv
}


$Python = Join-Path `
    $Venv `
    "Scripts\python.exe"

$Pip = Join-Path `
    $Venv `
    "Scripts\pip.exe"

$PyInstaller = Join-Path `
    $Venv `
    "Scripts\pyinstaller.exe"


Write-Host "[3/7] Mise a jour pip..."

& $Python `
    -m pip `
    install `
    --upgrade `
    pip


Write-Host "[4/7] Installation backend..."

& $Python `
    -m pip `
    install `
    -r `
    "$Root\backend\requirements.txt"


Write-Host "[5/7] Installation PyInstaller..."

& $Python `
    -m pip `
    install `
    "pyinstaller>=6.21,<7" `
    requests


Write-Host "[6/7] Nettoyage ancien build..."

if (Test-Path $Dist) {
    Remove-Item `
        $Dist `
        -Recurse `
        -Force
}

if (Test-Path $Work) {
    Remove-Item `
        $Work `
        -Recurse `
        -Force
}


Write-Host "[7/7] Creation executable final..."

& $PyInstaller `
    --noconfirm `
    --clean `
    --distpath `
    $Dist `
    --workpath `
    $Work `
    $SpecFile


$FinalExe = Join-Path `
    $Dist `
    "kakafandodo2d-ikom.exe"


if (-not (Test-Path $FinalExe)) {
    throw "Build termine mais EXE final introuvable."
}


Write-Host ""
Write-Host "============================================"
Write-Host " BUILD TERMINE"
Write-Host "============================================"
Write-Host ""

Get-Item $FinalExe |
    Format-List `
        FullName,
        Length,
        LastWriteTime

Write-Host ""
Write-Host "SHA256 :"

Get-FileHash `
    $FinalExe `
    -Algorithm SHA256 |
    Format-List

Write-Host ""
Write-Host "Executable final :"
Write-Host $FinalExe
Write-Host ""