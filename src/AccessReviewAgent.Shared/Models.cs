using System.Text.Json;

namespace AccessReviewAgent.Shared;

public static class AgentPaths
{
    public static readonly string DataDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "AccessReviewAgent");
    public static readonly string ConfigFile = Path.Combine(DataDirectory, "config.json");
    public static readonly string StatusFile = Path.Combine(DataDirectory, "status.json");
    public static readonly string DatabaseFile = Path.Combine(DataDirectory, "queue.db");

    public static void EnsureDirectory() => Directory.CreateDirectory(DataDirectory);
}

public static class AgentJson
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false
    };
}

public sealed class AgentConfig
{
    public string DeviceId { get; set; } = Environment.MachineName.ToUpperInvariant();
    public string ServerUrl { get; set; } = "";
    public string AgentToken { get; set; } = "";
    public int PollSeconds { get; set; } = 5;
    public int SnapshotMinutes { get; set; } = 60;

    public bool IsValid() =>
        !string.IsNullOrWhiteSpace(DeviceId) &&
        !string.IsNullOrWhiteSpace(AgentToken) &&
        Uri.TryCreate(ServerUrl, UriKind.Absolute, out var url) &&
        url.Scheme == Uri.UriSchemeHttps;

    public static AgentConfig Load()
    {
        try
        {
            if (!File.Exists(AgentPaths.ConfigFile)) return new AgentConfig();
            return JsonSerializer.Deserialize<AgentConfig>(
                File.ReadAllText(AgentPaths.ConfigFile), AgentJson.Options) ?? new AgentConfig();
        }
        catch (IOException) { return new AgentConfig(); }
        catch (System.Text.Json.JsonException) { return new AgentConfig(); }
    }

    public void Save()
    {
        AgentPaths.EnsureDirectory();
        var tmp = AgentPaths.ConfigFile + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(this, AgentJson.Options));
        File.Move(tmp, AgentPaths.ConfigFile, true);
    }
}

public sealed class AgentStatus
{
    public string ServiceState { get; set; } = "Not started";
    public string LastError { get; set; } = "";
    public string? LastEventCollectedUtc { get; set; }
    public string? LastUploadUtc { get; set; }
    public string? LastSnapshotUtc { get; set; }
    public long UploadedEvents { get; set; }
    public long PendingEvents { get; set; }
    public long PendingSnapshots { get; set; }

    public static AgentStatus Load()
    {
        try
        {
            return JsonSerializer.Deserialize<AgentStatus>(
                File.ReadAllText(AgentPaths.StatusFile), AgentJson.Options) ?? new AgentStatus();
        }
        catch { return new AgentStatus(); }
    }

    public void Save()
    {
        AgentPaths.EnsureDirectory();
        var tmp = AgentPaths.StatusFile + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(this, AgentJson.Options));
        File.Move(tmp, AgentPaths.StatusFile, true);
    }
}

public sealed class SecurityEventData
{
    public string EventUid { get; set; } = "";
    public long RecordId { get; set; }
    public int EventId { get; set; }
    public string OccurredAtUtc { get; set; } = "";
    public string Computer { get; set; } = "";
    public string? Username { get; set; }
    public string? Domain { get; set; }
    public string? SourceIp { get; set; }
    public string? LogonType { get; set; }
    public string EventCategory { get; set; } = "";
    public Dictionary<string, string> Details { get; set; } = new();
}

public sealed class AccountInfo
{
    public string Name { get; set; } = "";
    public string? Sid { get; set; }
    public bool? Enabled { get; set; }
    public string? LastLogonUtc { get; set; }
}

public sealed class GroupInfo
{
    public string Name { get; set; } = "";
    public string? Sid { get; set; }
    public List<AccountInfo> Members { get; set; } = new();
    public string? Error { get; set; }
}

public sealed class AccessSnapshot
{
    public string DeviceId { get; set; } = "";
    public string CollectedAtUtc { get; set; } = DateTime.UtcNow.ToString("O");
    public List<AccountInfo> Accounts { get; set; } = new();
    public List<GroupInfo> Groups { get; set; } = new();
    public string? Error { get; set; }
}
