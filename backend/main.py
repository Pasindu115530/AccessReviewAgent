"""Authenticated HTTPS ingestion for the AccessReview Windows endpoints.

Run behind Coolify's HTTPS reverse proxy. Never publish PostgreSQL directly.
"""
from __future__ import annotations

import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DATABASE_URL = os.getenv("DATABASE_URL", "")


def allowed_tokens() -> dict[str, str]:
    try:
        parsed = json.loads(os.getenv("AGENT_TOKENS_JSON", "{}"))
        if not isinstance(parsed, dict):
            raise ValueError("AGENT_TOKENS_JSON must be a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid AGENT_TOKENS_JSON") from exc


TOKENS = allowed_tokens()


SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_events (
    event_uid TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    record_id BIGINT NOT NULL,
    occurred_at_utc TIMESTAMPTZ NOT NULL,
    username TEXT,
    domain TEXT,
    source_ip TEXT,
    event_category TEXT NOT NULL,
    payload JSONB NOT NULL,
    received_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_events_device_time
    ON agent_events(device_id, occurred_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_agent_events_category_time
    ON agent_events(event_category, occurred_at_utc DESC);
CREATE TABLE IF NOT EXISTS agent_snapshots (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    collected_at_utc TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    received_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_agent_snapshot UNIQUE(device_id, collected_at_utc)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_device_time
    ON agent_snapshots(device_id, collected_at_utc DESC);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if not TOKENS:
        raise RuntimeError("AGENT_TOKENS_JSON must contain at least one device token")
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                conn.execute(statement)
    yield


app = FastAPI(title="AccessReviewAgent Ingest API", version="0.1.0", lifespan=lifespan)


class Ping(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)


class Event(BaseModel):
    event_uid: str = Field(min_length=32, max_length=128)
    record_id: int = Field(ge=0)
    event_id: int
    occurred_at_utc: datetime
    computer: str = Field(max_length=256)
    username: str | None = None
    domain: str | None = None
    source_ip: str | None = None
    logon_type: str | None = None
    event_category: str
    details: dict[str, str] = Field(default_factory=dict)


class EventBatch(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    events: list[Event] = Field(min_length=1, max_length=250)


class Snapshot(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    collected_at_utc: datetime
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


def authenticate(device_id: str, authorization: str | None) -> None:
    provided = ""
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[7:].strip()
    expected = TOKENS.get(device_id)
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid device credentials")


@app.get("/health")
def health():
    return {"status": "running", "service": "accessreview-ingest"}


@app.post("/api/agents/ping")
def ping(request: Ping, authorization: str | None = Header(default=None)):
    authenticate(request.device_id, authorization)
    return {"status": "authenticated", "device_id": request.device_id}


@app.post("/api/agents/events")
def ingest_events(batch: EventBatch, authorization: str | None = Header(default=None)):
    authenticate(batch.device_id, authorization)
    rows = [
        (
            event.event_uid, batch.device_id, event.event_id, event.record_id,
            event.occurred_at_utc, event.username, event.domain, event.source_ip,
            event.event_category, Jsonb(event.model_dump(mode="json")),
        )
        for event in batch.events
    ]
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO agent_events
                   (event_uid,device_id,event_id,record_id,occurred_at_utc,username,
                    domain,source_ip,event_category,payload)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (event_uid) DO NOTHING""",
                rows,
            )
    return {"status": "ok", "received": len(batch.events)}


@app.post("/api/agents/snapshot")
def ingest_snapshot(snapshot: Snapshot, authorization: str | None = Header(default=None)):
    authenticate(snapshot.device_id, authorization)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """INSERT INTO agent_snapshots (device_id,collected_at_utc,payload)
               VALUES (%s,%s,%s)
               ON CONFLICT (device_id,collected_at_utc) DO NOTHING""",
            (snapshot.device_id, snapshot.collected_at_utc,
             Jsonb(snapshot.model_dump(mode="json"))),
        )
    return {"status": "ok"}


@app.get("/api/admin/summary")
def admin_summary(x_admin_token: str | None = Header(default=None)):
    required = os.getenv("ADMIN_API_TOKEN", "")
    if not required or not x_admin_token or not hmac.compare_digest(required, x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT device_id,COUNT(*),MAX(occurred_at_utc)
                           FROM agent_events GROUP BY device_id ORDER BY device_id""")
            devices = [
                {"device_id": device, "event_count": count,
                 "last_event_utc": timestamp.isoformat() if timestamp else None}
                for device, count, timestamp in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) FROM agent_snapshots")
            snapshots = cur.fetchone()[0]
    return {"devices": devices, "snapshots": snapshots,
            "generated_at_utc": datetime.now(timezone.utc).isoformat()}
