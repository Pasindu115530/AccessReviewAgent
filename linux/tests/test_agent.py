import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent


class ClassifyTest(unittest.TestCase):
    def sample(self, msg, ident="sshd", cursor="cursor-001"):
        return {"MESSAGE": msg, "SYSLOG_IDENTIFIER": ident, "__CURSOR": cursor,
                "__REALTIME_TIMESTAMP": "1762300000000000"}

    def test_ssh_accepted(self):
        event = agent.classify_journal(self.sample("Accepted publickey for alice from 192.0.2.10 port 5555 ssh2"), "LINUX-01")
        self.assertEqual(event["event_id"], 1001)
        self.assertEqual(event["username"], "alice")
        self.assertEqual(event["source_ip"], "192.0.2.10")
        self.assertEqual(len(event["event_uid"]), 64)
        self.assertGreaterEqual(event["record_id"], 0)
        self.assertEqual(event["event_category"], "login_success")

    def test_invalid_ssh_user_and_failed_login(self):
        event = agent.classify_journal(self.sample("Failed password for invalid user gone from 198.51.100.42 port 22 ssh2"), "LINUX-01")
        self.assertEqual(event["event_id"], 1002)
        self.assertEqual(event["username"], "gone")

    def test_ssh_logout(self):
        event = agent.classify_journal(self.sample("pam_unix(sshd:session): session closed for user alice"), "LINUX-01")
        self.assertEqual(event["event_id"], 1003)

    def test_sudo_scrubs_command(self):
        raw = "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/secret --password=supersecret"
        event = agent.classify_journal(self.sample(raw, "sudo"), "LINUX-01")
        self.assertEqual(event["event_id"], 1101)
        self.assertEqual(event["details"]["target_user"], "root")
        self.assertNotIn("supersecret", json.dumps(event))
        self.assertNotIn("COMMAND", json.dumps(event))

    def test_account_change_and_unrelated(self):
        event = agent.classify_journal(self.sample("new user: alice", "useradd"), "LINUX-01")
        self.assertEqual(event["event_id"], 1201)
        self.assertIsNone(agent.classify_journal(self.sample("Started nightly backup", "systemd"), "LINUX-01"))

    def test_same_cursor_is_deterministic(self):
        item = self.sample("Accepted password for alice from 192.0.2.1", "sshd")
        one = agent.classify_journal(item, "LINUX-01")
        two = agent.classify_journal(item, "LINUX-01")
        three = agent.classify_journal(item, "LINUX-02")
        self.assertEqual(one["event_uid"], two["event_uid"])
        self.assertNotEqual(one["event_uid"], three["event_uid"])


class QueueTest(unittest.TestCase):
    def test_persistence_and_ack(self):
        with tempfile.TemporaryDirectory() as d:
            st = agent.QueueStore(d)
            event = {"event_uid": "x" * 64, "event_id": 1002}
            st.save_entry("cursor-2", event)
            st.save_entry("cursor-2", event)
            st.save_snapshot({"collected_at_utc": "2026-11-05T00:00:00Z", "accounts": []})
            self.assertEqual(st.pending_counts(), (1, 1))
            st.close()
            st = agent.QueueStore(d)
            self.assertEqual(st.get_meta("journal_cursor"), "cursor-2")
            self.assertEqual(st.batch_events()[0][1]["event_id"], 1002)
            st.ack_events([event["event_uid"]])
            st.ack_snapshot("2026-11-05T00:00:00Z")
            self.assertEqual(st.pending_counts(), (0, 0))
            st.close()

    def test_batch_upload_and_ack(self):
        with tempfile.TemporaryDirectory() as d:
            st = agent.QueueStore(d)
            cfg = {"server_url": "https://example.com", "device_id": "LINUX-01", "agent_token": "x"*32}
            event = agent.classify_journal({"MESSAGE":"Accepted password for bob from 192.0.2.9", "SYSLOG_IDENTIFIER":"sshd", "__CURSOR":"sample-44"}, "LINUX-01")
            st.save_entry("sample-44", event)
            st.save_snapshot({"device_id": "LINUX-01", "collected_at_utc": "2026-11-05T00:00:00Z", "accounts": [], "groups": [], "error": None})
            sent_requests = []
            def fake_post(config, endpoint, data):
                sent_requests.append((endpoint, data))
                return {"status": "ok"}
            with patch.object(agent, "api_post", side_effect=fake_post):
                sent, connected = agent.send_pending(cfg, st)
            self.assertEqual(sent, 1)
            self.assertTrue(connected)
            self.assertEqual(st.pending_counts(), (0, 0))
            self.assertEqual([r[0] for r in sent_requests], ["/api/agents/events", "/api/agents/snapshot"])
            body = sent_requests[0][1]
            self.assertEqual(body["device_id"], "LINUX-01")
            self.assertEqual(len(body["events"][0]["event_uid"]), 64)
            st.close()

    def test_first_run_seeds_cursor_without_old_uploads(self):
        with tempfile.TemporaryDirectory() as d:
            st = agent.QueueStore(d)
            with patch.object(agent, "journal_latest_cursor", return_value="tail-cursor"):
                self.assertEqual(agent.poll_journal({"device_id": "LINUX-01"}, st), 0)
            self.assertEqual(st.get_meta("journal_cursor"), "tail-cursor")
            self.assertEqual(st.pending_counts(), (0, 0))
            st.close()


class ConfigTest(unittest.TestCase):
    def test_https_required(self):
        with self.assertRaises(ValueError):
            agent.validate_config({"server_url": "http://example.com", "device_id": "LINUX-01", "agent_token": "x"*32})
        with self.assertRaises(ValueError):
            agent.validate_config({"server_url": "https://example.com/hijack", "device_id": "LINUX-01", "agent_token": "x"*32})
        ok = agent.validate_config({"server_url": "https://logs.example.com/", "device_id": "LINUX-01", "agent_token": "x"*32})
        self.assertEqual(ok["server_url"], "https://logs.example.com")

    def test_account_snapshot(self):
        accounts, groups = agent.collect_accounts()
        self.assertTrue(any(a["username"] == "root" for a in accounts))
        self.assertTrue(any(g["name"] == "root" for g in groups))
        self.assertNotIn("password", json.dumps(accounts))


if __name__ == "__main__":
    unittest.main()
