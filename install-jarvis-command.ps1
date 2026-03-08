$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$shimDir = Join-Path $env:USERPROFILE ".jarvis\bin"
$shimPath = Join-Path $shimDir "jarvis.cmd"

New-Item -ItemType Directory -Force -Path $shimDir | Out-Null

$shimContent = @"
@echo off
set "JARVIS_ROOT=$repoRoot"
if exist "%JARVIS_ROOT%\jarvis.py" (
    py -3 "%JARVIS_ROOT%\jarvis.py" %*
) else (
    echo Jarvis installation is broken. Could not find: %JARVIS_ROOT%\jarvis.py
    exit /b 1
)
"@

Set-Content -Path $shimPath -Value $shimContent -Encoding ASCII

$currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $currentUserPath) {
    $currentUserPath = ""
}

$pathEntries = $currentUserPath -split ";" | Where-Object { $_ -ne "" }
$alreadyPresent = $pathEntries | Where-Object { $_.TrimEnd("\\") -ieq $shimDir.TrimEnd("\\") }

if (-not $alreadyPresent) {
    $newPath = if ($currentUserPath.Trim()) { "$currentUserPath;$shimDir" } else { $shimDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added to user PATH: $shimDir"
} else {
    Write-Host "Already in user PATH: $shimDir"
}

Write-Host "Installed command: jarvis"
Write-Host "Open a new terminal and run: jarvis"
