param(
    [string]$UnityEditor = "$PSScriptRoot/../../builds/tools/Unity/Editor/Unity.exe"
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$editorPath  = (Resolve-Path -LiteralPath $UnityEditor).Path
$logPath     = Join-Path $projectRoot 'builds/unity-build-N2.log'
New-Item -ItemType Directory -Force (Join-Path $projectRoot 'builds') | Out-Null
$arguments = @(
    '-batchmode', '-nographics', '-quit',
    '-projectPath', ('"' + (Join-Path $projectRoot 'unity') + '"'),
    '-executeMethod', 'StickBalancing.Editor.BuildPrototype.WindowsN2',
    '-logFile', ('"' + $logPath + '"')
)
$process = Start-Process -FilePath $editorPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Unity failed ($($process.ExitCode)); see $logPath" }
$workerPath = Join-Path $projectRoot 'builds/windows/worker/StickBalancingWorkerN2.exe'
if (!(Test-Path -LiteralPath $workerPath)) { throw 'Unity did not produce the N=2 worker executable' }
Get-FileHash -Algorithm SHA256 -LiteralPath $workerPath
