param([string]$UnityEditor = "$PSScriptRoot/../../builds/tools/Unity/Editor/Unity.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$editorPath = (Resolve-Path -LiteralPath $UnityEditor).Path
$logPath = Join-Path $projectRoot 'builds/unity-tests.log'
$resultsPath = Join-Path $projectRoot 'builds/unity-tests.xml'
if (Test-Path -LiteralPath $resultsPath) { Remove-Item -LiteralPath $resultsPath }
$arguments = @('-batchmode', '-nographics', '-projectPath', ('"' + (Join-Path $projectRoot 'unity') + '"'), '-runTests', '-testPlatform', 'EditMode', '-testResults', ('"' + $resultsPath + '"'), '-logFile', ('"' + $logPath + '"'))
$process = Start-Process -FilePath $editorPath -ArgumentList $arguments -WindowStyle Hidden -PassThru
$process.WaitForExit()
if (!(Test-Path -LiteralPath $resultsPath)) { throw "Unity produced no test results; see $logPath" }
[xml]$report = Get-Content -LiteralPath $resultsPath
if ($process.ExitCode -ne 0 -or $report.'test-run'.result -ne 'Passed') { throw "Unity tests failed; see $resultsPath and $logPath" }
Write-Output "Unity: $($report.'test-run'.passed) tests passed."
