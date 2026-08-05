param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "run_final_validation.py"
py $scriptPath --blender $Blender
exit $LASTEXITCODE
