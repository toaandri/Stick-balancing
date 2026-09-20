param([string]$UnityEditor = "$PSScriptRoot/../../builds/tools/Unity/Editor/Unity.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$editorPath = (Resolve-Path -LiteralPath $UnityEditor).Path
$logPath = Join-Path $projectRoot 'builds/unity-desktop-build.log'
$arguments = @('-batchmode', '-nographics', '-quit', '-projectPath', ('"' + (Join-Path $projectRoot 'unity') + '"'), '-executeMethod', 'StickBalancing.Editor.BuildPrototype.Desktop', '-logFile', ('"' + $logPath + '"'))
$process = Start-Process -FilePath $editorPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Desktop build failed; see $logPath" }
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $projectRoot 'builds/windows/app/StickBalancing.exe')
