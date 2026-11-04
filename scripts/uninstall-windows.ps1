#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$svc = Get-Service -Name 'AccessReviewAgent' -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -ne 'Stopped') {
        Stop-Service -Name 'AccessReviewAgent' -Force
        (Get-Service -Name 'AccessReviewAgent').WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
    }
    & sc.exe delete AccessReviewAgent
    Write-Host 'Service removed.'
}
Write-Host 'For safety, stored event queue and config have been preserved in ProgramData\AccessReviewAgent.'
Write-Host 'After closing the UI and the service has fully stopped, delete Program Files\AccessReviewAgent manually if desired.'
Write-Host 'To erase local telemetry later, delete ProgramData\AccessReviewAgent as administrator.'
