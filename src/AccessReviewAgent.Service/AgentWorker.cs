using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using AccessReviewAgent.Shared;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace AccessReviewAgent.Service;

internal sealed class AgentWorker : BackgroundService
{
    private static readonly HttpClient Client = new() { Timeout = TimeSpan.FromSeconds(20) };
    private readonly ILogger<AgentWorker> _logger;
    private readonly QueueStore _queue = new();
    private readonly AgentStatus _status = new();
    private DateTime _nextSnapshot = DateTime.MinValue;

    public AgentWorker(ILogger<AgentWorker> logger) => _logger = logger;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try { _queue.Initialize(); }
        catch (Exception ex)
        {
            _logger.LogCritical(ex, "Cannot open the local offline queue");
            throw;
        }

        while (!stoppingToken.IsCancellationRequested)
        {
            var config = AgentConfig.Load();
            try
            {
                _status.ServiceState = config.IsValid() ? "Running" : "Awaiting valid settings";
                if (config.IsValid())
                {
                    string? collectionError = null;
                    try
                    {
                        int collected = SecurityEventCollector.Collect(_queue, config.DeviceId);
                        if (collected > 0) _status.LastEventCollectedUtc = DateTime.UtcNow.ToString("O");
                    }
                    catch (Exception ex)
                    {
                        collectionError = $"Collection: {ex.Message}";
                        _logger.LogWarning(ex, "Windows Security collection failed");
                    }
                    if (DateTime.UtcNow >= _nextSnapshot)
                    {
                        _queue.AddSnapshot(AccountSnapshotCollector.Capture(config.DeviceId));
                        _status.LastSnapshotUtc = DateTime.UtcNow.ToString("O");
                        _nextSnapshot = DateTime.UtcNow.AddMinutes(Math.Clamp(config.SnapshotMinutes, 5, 1440));
                    }
                    // Upload must still run when the queue is full, to recover from backlog.
                    await UploadEvents(config, stoppingToken);
                    await UploadSnapshot(config, stoppingToken);
                    _status.LastError = collectionError ?? "";
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception ex)
            {
                _status.LastError = $"{DateTime.UtcNow:O} {ex.GetType().Name}: {ex.Message}";
                _logger.LogWarning(ex, "Collection or upload failed; will retry");
            }

            try
            {
                var counts = _queue.QueueCounts();
                _status.PendingEvents = counts.Events;
                _status.PendingSnapshots = counts.Snapshots;
                _status.Save();
            }
            catch (Exception ex) { _logger.LogWarning(ex, "Unable to write agent status"); }

            try { await Task.Delay(TimeSpan.FromSeconds(Math.Clamp(config.PollSeconds, 2, 60)), stoppingToken); }
            catch (OperationCanceledException) { break; }
        }
        _status.ServiceState = "Stopped";
        _status.Save();
    }

    private async Task UploadEvents(AgentConfig config, CancellationToken ct)
    {
        // A bounded batch is safe to retry because the server deduplicates event_uid.
        var items = _queue.GetEvents(100);
        if (items.Count == 0) return;
        var events = items.Select(i => JsonSerializer.Deserialize<SecurityEventData>(i.Json, AgentJson.Options)!).ToArray();
        var body = new { DeviceId = config.DeviceId, Events = events };
        await Post(config, "/api/agents/events", body, ct);
        _queue.RemoveEvents(items.Select(i => i.Id));
        _status.UploadedEvents += items.Count;
        _status.LastUploadUtc = DateTime.UtcNow.ToString("O");
    }

    private async Task UploadSnapshot(AgentConfig config, CancellationToken ct)
    {
        var row = _queue.GetOldestSnapshot();
        if (row is null) return;
        var snapshot = JsonSerializer.Deserialize<AccessSnapshot>(row.Value.Json, AgentJson.Options)!;
        await Post(config, "/api/agents/snapshot", snapshot, ct);
        _queue.RemoveSnapshot(row.Value.Id);
        _status.LastUploadUtc = DateTime.UtcNow.ToString("O");
    }

    private static async Task Post<T>(AgentConfig config, string path, T payload, CancellationToken ct)
    {
        var uri = new Uri(new Uri(config.ServerUrl.TrimEnd('/') + "/"), path.TrimStart('/'));
        using var request = new HttpRequestMessage(HttpMethod.Post, uri);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", config.AgentToken);
        request.Content = JsonContent.Create(payload, options: AgentJson.Options);
        using var response = await Client.SendAsync(request, ct);
        response.EnsureSuccessStatusCode();
    }
}
