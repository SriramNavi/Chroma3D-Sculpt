$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
py manual-tests\sprint1\run_sprint1_acceptance.py @args
