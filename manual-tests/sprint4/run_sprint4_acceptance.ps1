param(
    [string]$Blender = "D:\Softwares\Design\Blender\blender.exe",
    [int]$DatasetTimeoutSeconds = 900,
    [switch]$SkipDataset
)
$arguments = @("manual-tests\sprint4\run_sprint4_acceptance.py", "--blender", $Blender, "--dataset-timeout-seconds", $DatasetTimeoutSeconds)
if ($SkipDataset) { $arguments += "--skip-dataset" }
& py @arguments
exit $LASTEXITCODE
