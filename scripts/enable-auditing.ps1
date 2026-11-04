#Requires -RunAsAdministrator
# Explicit opt-in on company-owned/authorized test PCs only.
# Audit policy changes may be overridden by Group Policy.
$ErrorActionPreference = 'Stop'
foreach ($subcategory in @('Logon','Logoff','User Account Management','Security Group Management','Special Logon')) {
    & auditpol.exe /set "/subcategory:$subcategory" /success:enable /failure:enable
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Audit policy '$subcategory' failed. Names can be localized; use 'auditpol /list /subcategory:*'."
    }
}
Write-Host 'Audit policy command sequence complete. Check with: auditpol /get /category:*'
