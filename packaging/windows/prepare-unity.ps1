$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path "$PSScriptRoot/../..").Path
$packageDir = Join-Path $projectRoot 'builds/packages'
New-Item -ItemType Directory -Force $packageDir | Out-Null
$packagePath = Join-Path $packageDir 'com.unity.sentis-2.1.0.tgz'
# Unity 6000.0.60 automatically substitutes registry Sentis with a 2.2 shim.
# Use the original registry artifact required by ML-Agents release_22.
if (!(Test-Path -LiteralPath $packagePath)) {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://download.packages.unity.com/com.unity.sentis/-/com.unity.sentis-2.1.0.tgz' -OutFile $packagePath
}
$sha1 = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA1).Hash
if ($sha1 -ne 'a9353f8ec25dd7e90d4e33a86cbc3b01b00293eb') { throw 'Sentis artifact differs from the official registry checksum' }
Get-FileHash -LiteralPath $packagePath -Algorithm SHA256
