param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
py manual-tests\sprint5\run_sprint5_acceptance.py --blender $Blender
