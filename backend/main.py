"""Authenticated HTTPS ingestion for the AccessReview Windows & Linux endpoints.

Supports unlimited dynamic device generation with employee mapping and DB token storage.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DATABASE_URL = os.getenv("DATABASE_URL", "")


def parse_env_tokens() -> dict[str, str]:
    try:
        raw = os.getenv("AGENT_TOKENS_JSON", "{}").strip()
        if not raw:
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        pass
    return {}


ENV_TOKENS = parse_env_tokens()


SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_devices (
    device_id TEXT PRIMARY KEY,
    employee_name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'windows',
    token TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_utc TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_devices_employee ON agent_devices(employee_name);

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
    with psycopg.connect(DATABASE_URL) as conn:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                conn.execute(statement)
        # Migrate any static ENV_TOKENS into agent_devices if they don't exist yet
        for dev_id, tok in ENV_TOKENS.items():
            conn.execute(
                """INSERT INTO agent_devices (device_id, employee_name, platform, token)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (device_id) DO NOTHING""",
                (dev_id, "System Pre-configured", "windows", tok),
            )
    yield


app = FastAPI(title="AccessReviewAgent Ingest API", version="0.2.0", lifespan=lifespan)


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


class DeviceCreate(BaseModel):
    employee_name: str = Field(min_length=1, max_length=128)
    platform: str = Field(default="windows", pattern="^(windows|linux)$")
    custom_device_id: str | None = Field(default=None, max_length=128)


def verify_admin(x_admin_token: str | None) -> None:
    required = os.getenv("ADMIN_API_TOKEN", "")
    if not required or not x_admin_token or not hmac.compare_digest(required, x_admin_token):
        raise HTTPException(status_code=401, detail="Unauthorized admin token")


def authenticate_device(device_id: str, authorization: str | None) -> None:
    provided = ""
    if authorization and authorization.startswith("Bearer "):
        provided = authorization[7:].strip()
    if not provided:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    # Check fallback in env tokens first
    if device_id in ENV_TOKENS and hmac.compare_digest(ENV_TOKENS[device_id], provided):
        return

    # Check PostgreSQL agent_devices
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT token, status FROM agent_devices WHERE device_id = %s",
                (device_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Unrecognized device ID")
            token_db, status = row
            if status != "active":
                raise HTTPException(status_code=403, detail="Device token has been revoked")
            if not hmac.compare_digest(token_db, provided):
                raise HTTPException(status_code=401, detail="Invalid device token")
            # Update last_seen_utc
            cur.execute(
                "UPDATE agent_devices SET last_seen_utc = NOW() WHERE device_id = %s",
                (device_id,),
            )


@app.get("/health")
def health():
    return {"status": "running", "service": "accessreview-ingest", "version": "0.2.0"}


# -------------------------------------------------------------
# Agent Ingest Endpoints
# -------------------------------------------------------------
@app.post("/api/agents/ping")
def ping(request: Ping, authorization: str | None = Header(default=None)):
    authenticate_device(request.device_id, authorization)
    return {"status": "authenticated", "device_id": request.device_id}


@app.post("/api/agents/events")
def ingest_events(batch: EventBatch, authorization: str | None = Header(default=None)):
    authenticate_device(batch.device_id, authorization)
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
    authenticate_device(snapshot.device_id, authorization)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute(
            """INSERT INTO agent_snapshots (device_id,collected_at_utc,payload)
               VALUES (%s,%s,%s)
               ON CONFLICT (device_id,collected_at_utc) DO NOTHING""",
            (snapshot.device_id, snapshot.collected_at_utc,
             Jsonb(snapshot.model_dump(mode="json"))),
        )
    return {"status": "ok"}


# -------------------------------------------------------------
# Admin Management Endpoints
# -------------------------------------------------------------
@app.get("/api/admin/summary")
def admin_summary(x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Query devices with event counts and join with agent_devices table for metadata
            cur.execute("""
                SELECT 
                    d.device_id,
                    d.employee_name,
                    d.platform,
                    d.status,
                    d.created_at_utc,
                    COALESCE(e.event_count, 0) as event_count,
                    e.last_event_utc
                FROM agent_devices d
                LEFT JOIN (
                    SELECT device_id, COUNT(*) as event_count, MAX(occurred_at_utc) as last_event_utc
                    FROM agent_events
                    GROUP BY device_id
                ) e ON d.device_id = e.device_id
                ORDER BY d.created_at_utc DESC
            """)
            registered_devices = [
                {
                    "device_id": row[0],
                    "employee_name": row[1],
                    "platform": row[2],
                    "status": row[3],
                    "created_at_utc": row[4].isoformat() if row[4] else None,
                    "event_count": row[5],
                    "last_event_utc": row[6].isoformat() if row[6] else None,
                }
                for row in cur.fetchall()
            ]

            # Also include any device in events that might not be in agent_devices (e.g. legacy events)
            cur.execute("""
                SELECT 
                    e.device_id, 
                    COUNT(*) as event_count, 
                    MAX(e.occurred_at_utc) as last_event_utc
                FROM agent_events e
                LEFT JOIN agent_devices d ON e.device_id = d.device_id
                WHERE d.device_id IS NULL
                GROUP BY e.device_id
            """)
            for row in cur.fetchall():
                registered_devices.append({
                    "device_id": row[0],
                    "employee_name": "Unregistered / Legacy",
                    "platform": "unknown",
                    "status": "active",
                    "created_at_utc": None,
                    "event_count": row[1],
                    "last_event_utc": row[2].isoformat() if row[2] else None,
                })

            cur.execute("SELECT COUNT(*) FROM agent_snapshots")
            snapshots = cur.fetchone()[0]

    return {
        "devices": registered_devices,
        "snapshots": snapshots,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/admin/devices")
def list_devices(x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT device_id, employee_name, platform, status, created_at_utc, last_seen_utc
                FROM agent_devices
                ORDER BY created_at_utc DESC
            """)
            devices = [
                {
                    "device_id": r[0],
                    "employee_name": r[1],
                    "platform": r[2],
                    "status": r[3],
                    "created_at_utc": r[4].isoformat() if r[4] else None,
                    "last_seen_utc": r[5].isoformat() if r[5] else None,
                }
                for r in cur.fetchall()
            ]
    return {"devices": devices}


@app.post("/api/admin/devices")
def create_device(payload: DeviceCreate, x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)

    # Generate device ID if not specified
    if payload.custom_device_id and payload.custom_device_id.strip():
        dev_id = payload.custom_device_id.strip().upper()
    else:
        prefix = "WIN" if payload.platform == "windows" else "LNX"
        # Sanitize employee name for device id prefix
        clean_name = "".join(c for c in payload.employee_name if c.isalnum()).upper()[:8]
        random_suffix = secrets.token_hex(2).upper()
        dev_id = f"{prefix}-{clean_name or 'EMP'}-{random_suffix}"

    # Generate 32-byte secure random hexadecimal token
    token = secrets.token_hex(32)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Check collision
            cur.execute("SELECT 1 FROM agent_devices WHERE device_id = %s", (dev_id,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail=f"Device ID '{dev_id}' already exists")

            cur.execute(
                """INSERT INTO agent_devices (device_id, employee_name, platform, token, status)
                   VALUES (%s, %s, %s, %s, 'active')""",
                (dev_id, payload.employee_name.strip(), payload.platform, token),
            )

    return {
        "status": "created",
        "device_id": dev_id,
        "employee_name": payload.employee_name.strip(),
        "platform": payload.platform,
        "token": token,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.delete("/api/admin/devices/{device_id}")
def delete_device(device_id: str, x_admin_token: str | None = Header(default=None)):
    verify_admin(x_admin_token)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agent_devices WHERE device_id = %s", (device_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "deleted", "device_id": device_id}
