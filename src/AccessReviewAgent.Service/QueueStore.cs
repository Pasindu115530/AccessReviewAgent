using Microsoft.Data.Sqlite;
using AccessReviewAgent.Shared;

namespace AccessReviewAgent.Service;

internal sealed class QueueStore
{
    private readonly string _connectionString = new SqliteConnectionStringBuilder
    {
        DataSource = AgentPaths.DatabaseFile,
        Mode = SqliteOpenMode.ReadWriteCreate
    }.ToString();

    private SqliteConnection Open()
    {
        var connection = new SqliteConnection(_connectionString);
        connection.Open();
        return connection;
    }

    public void Initialize()
    {
        AgentPaths.EnsureDirectory();
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS event_queue (
                event_uid TEXT PRIMARY KEY,
                json TEXT NOT NULL,
                stored_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS snapshot_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                json TEXT NOT NULL,
                stored_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS metadata (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );";
        cmd.ExecuteNonQuery();
    }

    public long? LastRecordId()
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT value FROM metadata WHERE name='last_record_id'";
        var value = cmd.ExecuteScalar()?.ToString();
        return long.TryParse(value, out var n) ? n : null;
    }

    public void SetLastRecordId(long id)
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = @"INSERT INTO metadata(name,value) VALUES('last_record_id',$value)
                            ON CONFLICT(name) DO UPDATE SET value=excluded.value";
        cmd.Parameters.AddWithValue("$value", id.ToString());
        cmd.ExecuteNonQuery();
    }

    public bool AddEvent(SecurityEventData evt)
    {
        using var conn = Open();
        using var transaction = conn.BeginTransaction();
        using var countCmd = conn.CreateCommand();
        countCmd.Transaction = transaction;
        countCmd.CommandText = "SELECT COUNT(*) FROM event_queue";
        var count = (long)(countCmd.ExecuteScalar() ?? 0L);
        if (count >= 100_000) return false; // do NOT advance cursor if queue is full

        using var add = conn.CreateCommand();
        add.Transaction = transaction;
        add.CommandText = "INSERT OR IGNORE INTO event_queue(event_uid,json) VALUES($uid,$json)";
        add.Parameters.AddWithValue("$uid", evt.EventUid);
        add.Parameters.AddWithValue("$json", System.Text.Json.JsonSerializer.Serialize(evt, AgentJson.Options));
        add.ExecuteNonQuery();

        using var cursor = conn.CreateCommand();
        cursor.Transaction = transaction;
        cursor.CommandText = @"INSERT INTO metadata(name,value) VALUES('last_record_id',$id)
                                ON CONFLICT(name) DO UPDATE SET value=excluded.value";
        cursor.Parameters.AddWithValue("$id", evt.RecordId.ToString());
        cursor.ExecuteNonQuery();
        transaction.Commit();
        return true;
    }

    public List<(string Id, string Json)> GetEvents(int maxCount = 100)
    {
        var items = new List<(string, string)>();
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT event_uid,json FROM event_queue ORDER BY rowid LIMIT $limit";
        cmd.Parameters.AddWithValue("$limit", maxCount);
        using var reader = cmd.ExecuteReader();
        while (reader.Read()) items.Add((reader.GetString(0), reader.GetString(1)));
        return items;
    }

    public void RemoveEvents(IEnumerable<string> eventUids)
    {
        using var conn = Open();
        using var transaction = conn.BeginTransaction();
        foreach (var eventUid in eventUids)
        {
            using var cmd = conn.CreateCommand();
            cmd.Transaction = transaction;
            cmd.CommandText = "DELETE FROM event_queue WHERE event_uid=$id";
            cmd.Parameters.AddWithValue("$id", eventUid);
            cmd.ExecuteNonQuery();
        }
        transaction.Commit();
    }

    public void AddSnapshot(AccessSnapshot snapshot)
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "INSERT INTO snapshot_queue(json) VALUES($json)";
        cmd.Parameters.AddWithValue("$json", System.Text.Json.JsonSerializer.Serialize(snapshot, AgentJson.Options));
        cmd.ExecuteNonQuery();
    }

    public (long Id, string Json)? GetOldestSnapshot()
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT id,json FROM snapshot_queue ORDER BY id LIMIT 1";
        using var reader = cmd.ExecuteReader();
        return reader.Read() ? (reader.GetInt64(0), reader.GetString(1)) : null;
    }

    public void RemoveSnapshot(long id)
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM snapshot_queue WHERE id=$id";
        cmd.Parameters.AddWithValue("$id", id);
        cmd.ExecuteNonQuery();
    }

    public (long Events, long Snapshots) QueueCounts()
    {
        using var conn = Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT (SELECT COUNT(*) FROM event_queue), (SELECT COUNT(*) FROM snapshot_queue)";
        using var reader = cmd.ExecuteReader();
        return reader.Read() ? (reader.GetInt64(0), reader.GetInt64(1)) : (0, 0);
    }
}
