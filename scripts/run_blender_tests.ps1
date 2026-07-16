$ErrorActionPreference = "Stop"
$PythonCommand = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonCommand) { $PythonCommand = Get-Command python -ErrorAction SilentlyContinue }
if (-not $PythonCommand) { Write-Error "Python launcher not found. Install Python or use Blender's bundled Python."; exit 1 }
& $PythonCommand.Source (Join-Path $PSScriptRoot "run_blender_tests.py") @args
exit $LASTEXITCODE

