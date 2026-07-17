param(
    [string]$Blender
)

$ErrorActionPreference = "Stop"
$runner = Join-Path $PSScriptRoot "run_final_validation.py"
$launcher = Get-Command py -ErrorAction SilentlyContinue
if (-not $launcher) {
    $launcher = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $launcher) {
    Write-Error "Neither py nor python is available."
    exit 2
}

$arguments = @($runner)
if ($Blender) {
    $arguments += @("--blender", $Blender)
}
& $launcher.Source @arguments
exit $LASTEXITCODE
