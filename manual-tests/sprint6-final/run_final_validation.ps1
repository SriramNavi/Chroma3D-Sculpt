param(
    [Parameter(Mandatory=$true)]
    [string]$Blender
)

Set-Location (Split-Path -Parent $PSScriptRoot | Split-Path -Parent)
py manual-tests\sprint6-final\run_final_validation.py --blender $Blender
