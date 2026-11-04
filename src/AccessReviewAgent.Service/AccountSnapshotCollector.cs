using System.DirectoryServices.AccountManagement;
using AccessReviewAgent.Shared;

namespace AccessReviewAgent.Service;

internal static class AccountSnapshotCollector
{
    public static AccessSnapshot Capture(string deviceId)
    {
        var result = new AccessSnapshot { DeviceId = deviceId };
        try
        {
            using var machine = new PrincipalContext(ContextType.Machine);
            using var userExample = new UserPrincipal(machine);
            using var users = new PrincipalSearcher(userExample);
            foreach (var p in users.FindAll())
            {
                if (p is not UserPrincipal user) continue;
                try
                {
                    result.Accounts.Add(new AccountInfo
                    {
                        Name = user.SamAccountName ?? user.Name ?? "unknown",
                        Sid = user.Sid?.Value,
                        Enabled = user.Enabled,
                        LastLogonUtc = user.LastLogon?.ToUniversalTime().ToString("O")
                    });
                }
                catch { /* broken local principal is skipped; next snapshot may recover */ }
            }

            using var groupExample = new GroupPrincipal(machine);
            using var groups = new PrincipalSearcher(groupExample);
            foreach (var p in groups.FindAll())
            {
                if (p is not GroupPrincipal group) continue;
                var info = new GroupInfo
                {
                    Name = group.SamAccountName ?? group.Name ?? "unknown",
                    Sid = group.Sid?.Value
                };
                try
                {
                    foreach (var member in group.GetMembers())
                    {
                        try
                        {
                            info.Members.Add(new AccountInfo
                            {
                                Name = member.SamAccountName ?? member.Name ?? "unknown",
                                Sid = member.Sid?.Value
                            });
                        }
                        catch { /* unresolved membership can occur on disconnected domain PCs */ }
                    }
                }
                catch (Exception ex)
                {
                    info.Error = $"Membership lookup unavailable: {ex.GetType().Name}";
                }
                result.Groups.Add(info);
            }
        }
        catch (Exception ex)
        {
            result.Error = $"Account snapshot failed: {ex.GetType().Name}: {ex.Message}";
        }
        return result;
    }
}
