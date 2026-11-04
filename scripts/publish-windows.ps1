# Run on a Windows PC with .NET 8 SDK installed. Alternatively use GitHub Actions.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$out = Join-Path $root 'output'
$serviceOut = Join-Path $out 'service'
$uiOut = Join-Path $out 'ui'
New-Item -ItemType Directory -Path $serviceOut, $uiOut -Force | Out-Null

dotnet publish (Join-Path $root 'src\AccessReviewAgent.Service\AccessReviewAgent.Service.csproj') `
    -c Release -r win-x64 --self-contained true -o $serviceOut `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:PublishTrimmed=false
if ($LASTEXITCODE -ne 0) { throw 'Service publish failed' }

dotnet publish (Join-Path $root 'src\AccessReviewAgent.UI\AccessReviewAgent.UI.csproj') `
    -c Release -r win-x64 --self-contained true -o $uiOut `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:PublishTrimmed=false
if ($LASTEXITCODE -ne 0) { throw 'UI publish failed' }

Copy-Item (Join-Path $PSScriptRoot 'install-windows.ps1') $out
Copy-Item (Join-Path $PSScriptRoot 'uninstall-windows.ps1') $out
Copy-Item (Join-Path $PSScriptRoot 'enable-auditing.ps1') $out
$zip = Join-Path $root 'AccessReviewAgent-Windows-win-x64.zip'
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip
Write-Host "Windows install ZIP created at: $zip" -ForegroundColor Green
