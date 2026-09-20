param(
    [string]$Staging = "$PSScriptRoot/../../builds/distribution-preview",
    [string]$Compiler = "$env:LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe"
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$stagingPath = (Resolve-Path -LiteralPath $Staging).Path
$compilerPath = (Resolve-Path -LiteralPath $Compiler).Path
if (!(Test-Path -LiteralPath (Join-Path $stagingPath 'bundle-manifest.json'))) {
    throw 'The staging directory has no verified bundle manifest.'
}
& $compilerPath "/DStagingDir=$stagingPath" (Join-Path $projectRoot 'packaging/windows/installer.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
$installer = Join-Path $projectRoot 'packaging/windows/output/StickBalancing-Prototype-Setup.exe'
if (!(Test-Path -LiteralPath $installer)) { throw 'Inno Setup did not create the expected installer.' }
Get-FileHash -Algorithm SHA256 -LiteralPath $installer
