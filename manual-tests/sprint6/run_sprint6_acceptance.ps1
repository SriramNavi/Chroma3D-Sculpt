param(
    [Parameter(Mandatory=$true)]
    [string]$Blender
)

Set-Location (Split-Path -Parent $PSScriptRoot | Split-Path -Parent)
py manual-tests\sprint6\run_sprint6_acceptance.py --blender $Blender
