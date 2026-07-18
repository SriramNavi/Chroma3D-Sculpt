param([string]$Blender = "")

$runner = Join-Path $PSScriptRoot "run_final_validation.py"
$arguments = @($runner)
if ($Blender) {
    $arguments += @("--blender", $Blender)
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py @arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @arguments
} else {
    Write-Error "Python launcher not found."
    exit 2
}
exit $LASTEXITCODE
