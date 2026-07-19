param(
  [switch]$SkipInstall,
  [string]$PythonExecutable = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not $SkipInstall) {
  & $PythonExecutable -m pip install -r requirements-dev.txt
  if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

& $PythonExecutable -m PyInstaller --clean --noconfirm FileconverterAthome.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$executable = Join-Path $projectRoot "dist\FileconverterAthome.exe"
if (-not (Test-Path -LiteralPath $executable)) {
  throw "The expected executable was not created."
}

& $PythonExecutable scripts\smoke_executable.py $executable
if ($LASTEXITCODE -ne 0) { throw "The executable smoke test failed." }

$hash = Get-FileHash -LiteralPath $executable -Algorithm SHA256
Write-Output "Built $executable"
Write-Output "SHA256 $($hash.Hash.ToLowerInvariant())"
