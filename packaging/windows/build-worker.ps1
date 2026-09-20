param(
    [Parameter(Mandatory=$true)][string]$UnityEditor,
    [ValidateSet(1,2,3)][int]$Segments = 1
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$editorPath  = (Resolve-Path -LiteralPath $UnityEditor).Path

$methods = @{1='Windows'; 2='WindowsN2'; 3='WindowsN3'}
$method  = $methods[$Segments]
$suffix  = if ($Segments -eq 1) { '' } else { "N$Segments" }
$logPath = Join-Path $projectRoot "builds/unity-build${suffix}.log"

New-Item -ItemType Directory -Force (Join-Path $projectRoot 'builds') | Out-Null
$arguments = @(
    '-batchmode', '-nographics', '-quit',
    '-projectPath', ('"' + (Join-Path $projectRoot 'unity') + '"'),
    '-executeMethod', "StickBalancing.Editor.BuildPrototype.$method",
    '-logFile', ('"' + $logPath + '"')
)
$process = Start-Process -FilePath $editorPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Unity failed ($($process.ExitCode)); see $logPath" }
$workerPath = Join-Path $projectRoot "builds/windows/worker/StickBalancingWorker${suffix}.exe"
if (!(Test-Path -LiteralPath $workerPath)) { throw "Unity did not produce the N=$Segments worker executable" }
Get-FileHash -Algorithm SHA256 -LiteralPath $workerPath
