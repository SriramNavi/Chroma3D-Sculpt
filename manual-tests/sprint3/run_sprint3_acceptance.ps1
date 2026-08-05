param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "run_sprint3_acceptance.py"
py $Runner --blender $Blender
exit $LASTEXITCODE
