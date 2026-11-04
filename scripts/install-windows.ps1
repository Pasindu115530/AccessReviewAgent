#Requires -RunAsAdministrator
# Run from the extracted GitHub Actions ZIP (containing service/ and ui/).
$ErrorActionPreference = 'Stop'

$serviceSource = Join-Path $PSScriptRoot 'service'
$uiSource = Join-Path $PSScriptRoot 'ui'
$installRoot = Join-Path $env:ProgramFiles 'AccessReviewAgent'
$serviceDest = Join-Path $installRoot 'service'
$uiDest = Join-Path $installRoot 'ui'
$dataDir = Join-Path $env:ProgramData 'AccessReviewAgent'
$serviceExe = Join-Path $serviceDest 'AccessReviewAgent.Service.exe'

if (!(Test-Path (Join-Path $serviceSource 'AccessReviewAgent.Service.exe'))) {
    throw "Missing service EXE. Download the compiled Windows package from GitHub Actions first."
}
if (!(Test-Path (Join-Path $uiSource 'AccessReviewAgent.UI.exe'))) {
    throw "Missing UI EXE. Download the compiled Windows package from GitHub Actions first."
}

$existing = Get-Service -Name 'AccessReviewAgent' -ErrorAction SilentlyContinue
if ($existing -and $existing.Status -ne 'Stopped') {
    Stop-Service -Name 'AccessReviewAgent' -Force
    (Get-Service -Name 'AccessReviewAgent').WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
}

New-Item -ItemType Directory -Path $serviceDest, $uiDest, $dataDir -Force | Out-Null
Copy-Item -Path (Join-Path $serviceSource '*') -Destination $serviceDest -Recurse -Force
Copy-Item -Path (Join-Path $uiSource '*') -Destination $uiDest -Recurse -Force

# Only LocalSystem and local Administrators can read the stored token / queue.
# Grant using well-known Windows SIDs to work on localized installations.
& icacls.exe $dataDir '/inheritance:r' '/grant:r' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict ProgramData folder ACL; aborting installation.' }

if (!$existing) {
    New-Service -Name 'AccessReviewAgent' `
        -BinaryPathName ('"' + $serviceExe + '"') `
        -DisplayName 'AccessReviewAgent Windows Collector' `
        -Description 'Collects approved access events and permission snapshots for the AccessReview prototype.' `
        -StartupType Automatic | Out-Null
}
Start-Service -Name 'AccessReviewAgent'
Write-Host 'Installed and started AccessReviewAgent Service.' -ForegroundColor Green
Write-Host 'Opening the admin setup window...'
Start-Process -FilePath (Join-Path $uiDest 'AccessReviewAgent.UI.exe') -Verb RunAs
Write-Host 'Enter your HTTPS API URL, device ID and per-device token in the UI, then Save and Test API.'
