using System.Diagnostics.Eventing.Reader;
using System.Security.Cryptography;
using System.Text;
using System.Xml.Linq;
using AccessReviewAgent.Shared;

namespace AccessReviewAgent.Service;

internal static class SecurityEventCollector
{
    private static readonly int[] EventIds =
    [
        4624, // successful logon
        4625, // failed logon
        4634, // logoff
        4647, // user-initiated logoff
        4672, // special privileges assigned
        4720, // local/domain account created (where audited)
        4726, // account deleted
        4728, 4729, // global group membership change
        4732, 4733, // local group membership change
        4738, // account changed
        4740, // locked account
        4767, // unlocked account
        4778, 4779 // RDP session reconnect/disconnect
    ];

    private static readonly HashSet<string> AllowedDetails =
    [
        "TargetUserSid", "SubjectUserSid", "MemberSid", "TargetUserName",
        "SubjectUserName", "TargetDomainName", "SubjectDomainName",
        "GroupName", "TargetSid", "MemberName", "LogonType", "IpAddress",
        "WorkstationName", "Status", "SubStatus"
    ];

    public static long GetLatestRecordId()
    {
        var query = new EventLogQuery("Security", PathType.LogName, "*")
        {
            ReverseDirection = true
        };
        using var reader = new EventLogReader(query);
        using var evt = reader.ReadEvent();
        return evt?.RecordId ?? 0;
    }

    // Polling makes backlog resilient when the PC is offline or the service restarts.
    // First installation intentionally starts at the latest Windows event; it does not export history.
    public static int Collect(QueueStore store, string deviceId, int maxEvents = 250)
    {
        long? last = store.LastRecordId();
        if (last is null)
        {
            store.SetLastRecordId(GetLatestRecordId());
            return 0;
        }

        long newest = GetLatestRecordId();
        if (newest < last.Value)
        {
            // Windows log was cleared or recreated; reinitialize without replaying unknown history.
            store.SetLastRecordId(newest);
            return 0;
        }
        if (newest == last.Value) return 0;

        var predicates = string.Join(" or ", EventIds.Select(id => $"EventID={id}"));
        var xpath = $"*[System[((({predicates})) and (EventRecordID > {last.Value}))]]";
        var query = new EventLogQuery("Security", PathType.LogName, xpath);
        using var reader = new EventLogReader(query);
        int added = 0;
        for (int i = 0; i < maxEvents; i++)
        {
            using var evt = reader.ReadEvent();
            if (evt is null) break;
            if (evt.RecordId is not long rid) continue;
            var converted = ConvertEvent(evt, deviceId);
            if (!store.AddEvent(converted))
                throw new InvalidOperationException("Offline queue reached the 100,000-event limit; upload backlog before collection resumes.");
            added++;
        }
        return added;
    }

    private static SecurityEventData ConvertEvent(EventRecord record, string deviceId)
    {
        XNamespace ns = "http://schemas.microsoft.com/win/2004/08/events/event";
        var xml = XDocument.Parse(record.ToXml());
        var data = xml.Descendants(ns + "EventData")
            .Elements(ns + "Data")
            .Where(x => x.Attribute("Name") is not null)
            .GroupBy(x => x.Attribute("Name")!.Value)
            .ToDictionary(g => g.Key, g => g.First().Value, StringComparer.OrdinalIgnoreCase);

        string? Value(string key) => data.TryGetValue(key, out var s) && s != "-" ? s : null;
        string? user = Value("TargetUserName") ?? Value("SubjectUserName");
        string? domain = Value("TargetDomainName") ?? Value("SubjectDomainName");
        var rid = record.RecordId ?? 0;
        var uidRaw = $"{deviceId}|Security|{rid}|{record.Id}";
        var uid = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(uidRaw))).ToLowerInvariant();

        return new SecurityEventData
        {
            EventUid = uid,
            RecordId = rid,
            EventId = record.Id,
            OccurredAtUtc = (record.TimeCreated ?? DateTime.UtcNow).ToUniversalTime().ToString("O"),
            Computer = record.MachineName ?? Environment.MachineName,
            Username = user,
            Domain = domain,
            SourceIp = Value("IpAddress"),
            LogonType = Value("LogonType"),
            EventCategory = record.Id switch
            {
                4624 => "login_success",
                4625 => "login_failed",
                4634 or 4647 => "logout",
                4672 => "privileged_logon",
                4720 => "account_created",
                4726 => "account_deleted",
                4728 or 4732 => "group_member_added",
                4729 or 4733 => "group_member_removed",
                4738 => "account_modified",
                4740 => "account_locked",
                4767 => "account_unlocked",
                4778 or 4779 => "remote_session",
                _ => "other"
            },
            Details = data.Where(p => AllowedDetails.Contains(p.Key) && p.Value.Length <= 512)
                .ToDictionary(p => p.Key, p => p.Value)
        };
    }
}
