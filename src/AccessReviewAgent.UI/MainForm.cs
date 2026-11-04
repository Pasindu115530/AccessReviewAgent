using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.ServiceProcess;
using AccessReviewAgent.Shared;

namespace AccessReviewAgent.UI;

public sealed class MainForm : Form
{
    private readonly TextBox _server = Input();
    private readonly TextBox _device = Input();
    private readonly TextBox _token = Input();
    private readonly Label _service = ValueLabel();
    private readonly Label _pending = ValueLabel();
    private readonly Label _sent = ValueLabel();
    private readonly Label _lastSync = ValueLabel();
    private readonly Label _lastSnapshot = ValueLabel();
    private readonly Label _lastError = ValueLabel();
    private readonly Label _feedback = ValueLabel();
    private readonly System.Windows.Forms.Timer _refreshTimer = new() { Interval = 5000 };

    private static Color Back = Color.FromArgb(14, 21, 34);
    private static Color PanelColor = Color.FromArgb(27, 38, 56);
    private static Color Fore = Color.FromArgb(228, 238, 248);
    private static Color Muted = Color.FromArgb(155, 178, 200);
    private static Color Accent = Color.FromArgb(38, 141, 224);

    public MainForm()
    {
        Text = "AccessReview Agent — Windows Endpoint";
        ClientSize = new Size(750, 590);
        MinimumSize = new Size(700, 580);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 10);
        BackColor = Back;
        ForeColor = Fore;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildLayout();
        LoadSettings();
        RefreshStatus();
        _refreshTimer.Tick += (_, _) => RefreshStatus();
        _refreshTimer.Start();
    }

    private static TextBox Input() => new()
    {
        Dock = DockStyle.Fill,
        Font = new Font("Segoe UI", 10),
        BackColor = Color.FromArgb(17, 28, 43),
        ForeColor = Fore,
        BorderStyle = BorderStyle.FixedSingle,
        Margin = new Padding(0, 5, 0, 5)
    };

    private static Label ValueLabel() => new()
    {
        Text = "—", Dock = DockStyle.Fill,
        AutoEllipsis = true, ForeColor = Fore, TextAlign = ContentAlignment.MiddleLeft,
        Margin = new Padding(0, 2, 0, 2)
    };

    private static Label Caption(string text) => new()
    {
        Text = text, Dock = DockStyle.Fill, ForeColor = Muted,
        TextAlign = ContentAlignment.MiddleLeft, AutoSize = false
    };

    private static Button ActionButton(string text, Color background) => new()
    {
        Text = text,
        Height = 37,
        Width = 126,
        BackColor = background,
        ForeColor = Color.White,
        FlatStyle = FlatStyle.Flat,
        Margin = new Padding(0, 2, 10, 2),
        Cursor = Cursors.Hand
    };

    private void BuildLayout()
    {
        var page = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 6,
            Padding = new Padding(25, 22, 25, 17),
            BackColor = Back
        };
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 70));
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 177));
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 195));
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 27));
        page.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        Controls.Add(page);

        var title = new Label
        {
            Text = "🛡  AccessReview Agent",
            Font = new Font("Segoe UI", 20, FontStyle.Bold),
            Dock = DockStyle.Top,
            Height = 44,
            ForeColor = Fore
        };
        var subtitle = new Label
        {
            Text = "Windows access telemetry • authorized enterprise endpoints only",
            ForeColor = Muted, Dock = DockStyle.Bottom, Height = 23
        };
        var heading = new Panel { Dock = DockStyle.Fill };
        heading.Controls.Add(subtitle);
        heading.Controls.Add(title);
        page.Controls.Add(heading, 0, 0);

        var settings = new TableLayoutPanel
        {
            BackColor = PanelColor,
            Dock = DockStyle.Fill,
            Padding = new Padding(17, 13, 17, 12),
            ColumnCount = 2, RowCount = 4
        };
        settings.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 145));
        settings.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (var i = 0; i < 4; i++) settings.RowStyles.Add(new RowStyle(SizeType.Percent, 25));
        settings.Controls.Add(Caption("Server HTTPS URL"), 0, 0);
        settings.Controls.Add(_server, 1, 0);
        settings.Controls.Add(Caption("Device ID"), 0, 1);
        settings.Controls.Add(_device, 1, 1);
        settings.Controls.Add(Caption("Agent Token"), 0, 2);
        _token.UseSystemPasswordChar = true;
        settings.Controls.Add(_token, 1, 2);
        settings.Controls.Add(Caption("Telemetry Scope"), 0, 3);
        settings.Controls.Add(Caption("Security login events + local users & groups"), 1, 3);
        page.Controls.Add(settings, 0, 1);

        var actions = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false, Padding = new Padding(0, 5, 0, 0)
        };
        var save = ActionButton("Save Settings", Accent);
        var test = ActionButton("Test API", Color.FromArgb(37, 111, 88));
        var start = ActionButton("Start Service", Color.FromArgb(48, 79, 117));
        var stop = ActionButton("Stop Service", Color.FromArgb(123, 59, 65));
        var refresh = ActionButton("Refresh", Color.FromArgb(74, 82, 97));
        save.Click += (_, _) => SaveSettings();
        test.Click += async (_, _) => await TestApi();
        start.Click += async (_, _) => await ChangeService(true);
        stop.Click += async (_, _) => await ChangeService(false);
        refresh.Click += (_, _) => RefreshStatus();
        actions.Controls.AddRange([save, test, start, stop, refresh]);
        page.Controls.Add(actions, 0, 2);

        var summary = new TableLayoutPanel
        {
            BackColor = PanelColor,
            Dock = DockStyle.Fill,
            Padding = new Padding(17, 12, 17, 12),
            ColumnCount = 2, RowCount = 6
        };
        summary.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 175));
        summary.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        for (var i = 0; i < 6; i++) summary.RowStyles.Add(new RowStyle(SizeType.Percent, 100f / 6f));
        var metrics = new (string, Label)[]
        {
            ("Service status", _service),
            ("Queued events", _pending),
            ("Uploaded events", _sent),
            ("Last successful upload", _lastSync),
            ("Last account snapshot", _lastSnapshot),
            ("Latest error", _lastError)
        };
        for (var i = 0; i < metrics.Length; i++)
        {
            summary.Controls.Add(Caption(metrics[i].Item1), 0, i);
            summary.Controls.Add(metrics[i].Item2, 1, i);
        }
        page.Controls.Add(summary, 0, 3);
        _feedback.ForeColor = Muted;
        _feedback.Text = "The background service keeps collecting when you close this window.";
        page.Controls.Add(_feedback, 0, 4);
        page.Controls.Add(Caption("No screenshots, keystrokes, browser history or file content are collected."), 0, 5);
    }

    private void LoadSettings()
    {
        var cfg = AgentConfig.Load();
        _server.Text = cfg.ServerUrl;
        _device.Text = cfg.DeviceId;
        _token.Text = cfg.AgentToken;
    }

    private AgentConfig CurrentConfig() => new()
    {
        ServerUrl = _server.Text.Trim(),
        DeviceId = _device.Text.Trim(),
        AgentToken = _token.Text.Trim()
    };

    private void SaveSettings()
    {
        var cfg = CurrentConfig();
        if (!cfg.IsValid())
        {
            MessageBox.Show("Enter a valid HTTPS server URL, device ID and agent token.",
                "Invalid settings", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }
        try
        {
            cfg.Save();
            _feedback.Text = "Settings saved. The service reads them on its next cycle.";
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Save failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async Task TestApi()
    {
        var cfg = CurrentConfig();
        if (!cfg.IsValid()) { _feedback.Text = "Enter valid HTTPS settings first."; return; }
        _feedback.Text = "Testing authenticated connection...";
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            using var request = new HttpRequestMessage(
                HttpMethod.Post,
                new Uri(new Uri(cfg.ServerUrl.TrimEnd('/') + "/"), "api/agents/ping"));
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", cfg.AgentToken);
            request.Content = JsonContent.Create(new { DeviceId = cfg.DeviceId }, options: AgentJson.Options);
            using var response = await client.SendAsync(request);
            _feedback.Text = response.IsSuccessStatusCode
                ? "✓ Authenticated API connection successful. Save Settings if changed."
                : $"API rejected request: {(int)response.StatusCode} {response.ReasonPhrase}";
        }
        catch (Exception ex) { _feedback.Text = $"Connection failed: {ex.Message}"; }
    }

    private async Task ChangeService(bool start)
    {
        try
        {
            await Task.Run(() =>
            {
                using var service = new ServiceController("AccessReviewAgent");
                if (start && service.Status == ServiceControllerStatus.Stopped)
                {
                    service.Start();
                    service.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(15));
                }
                if (!start && service.Status == ServiceControllerStatus.Running)
                {
                    service.Stop();
                    service.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(15));
                }
            });
            _feedback.Text = start ? "Service start requested." : "Service stop requested.";
            RefreshStatus();
        }
        catch (Exception ex) { _feedback.Text = $"Service operation failed: {ex.Message}"; }
    }

    private void RefreshStatus()
    {
        try
        {
            using var service = new ServiceController("AccessReviewAgent");
            _service.Text = service.Status.ToString();
        }
        catch { _service.Text = "Not installed"; }
        var status = AgentStatus.Load();
        if (_service.Text != "Not installed")
            _service.Text = $"{_service.Text} / {status.ServiceState}";
        _pending.Text = $"{status.PendingEvents:N0} event(s), {status.PendingSnapshots:N0} snapshot(s)";
        _sent.Text = $"{status.UploadedEvents:N0} (since service started)";
        _lastSync.Text = FormatTime(status.LastUploadUtc);
        _lastSnapshot.Text = FormatTime(status.LastSnapshotUtc);
        _lastError.Text = string.IsNullOrEmpty(status.LastError) ? "None" : status.LastError;
    }

    private static string FormatTime(string? s) =>
        DateTimeOffset.TryParse(s, out var time) ? time.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss") : "—";
}
