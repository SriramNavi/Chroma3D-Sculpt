param(
    [Parameter(Position = 0)]
    [string]$Blender
)

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "Neither 'py' nor 'python' is available on PATH."
    exit 2
}

$runner = Join-Path $PSScriptRoot "run_acceptance_gates.py"
$arguments = @($runner)
if ($Blender) {
    $arguments += @("--blender", $Blender)
}

& $python.Source @arguments
exit $LASTEXITCODE
