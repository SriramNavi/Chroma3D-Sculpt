[CmdletBinding()]
param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe",
    [int]$TimeoutSeconds = 2400
)

$ErrorActionPreference = "Stop"
$PythonCommand = Get-Command py -ErrorAction Stop
& $PythonCommand.Source (Join-Path $PSScriptRoot "run_final_validation.py") --blender $Blender --timeout-seconds $TimeoutSeconds
exit $LASTEXITCODE
