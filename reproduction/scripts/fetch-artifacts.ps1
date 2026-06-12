$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "fetch_artifacts.py"
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "python executable was not found in PATH" }
& $Python.Source $PythonScript @args
exit $LASTEXITCODE
