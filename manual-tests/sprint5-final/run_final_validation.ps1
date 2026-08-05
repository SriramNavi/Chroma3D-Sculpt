param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe",
    [ValidateSet("initial", "final")][string]$Phase = "final",
    [switch]$SkipPerformance
)
$arguments = @("manual-tests\sprint5-final\run_final_validation.py", "--blender", $Blender, "--phase", $Phase)
if ($SkipPerformance) { $arguments += "--skip-performance" }
& py @arguments
exit $LASTEXITCODE
