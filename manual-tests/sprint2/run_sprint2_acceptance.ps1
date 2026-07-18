$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
py manual-tests\sprint2\run_sprint2_acceptance.py @args
