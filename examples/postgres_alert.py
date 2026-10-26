"""Send measured PostgreSQL replica lag; pip install psycopg[binary] httpx."""

import os
import time
import httpx
import psycopg

with psycopg.connect(os.environ["MONITORED_POSTGRES_URL"]) as connection:
    row = connection.execute(
        "SELECT pg_is_in_recovery(), EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))"
    ).fetchone()
if row and row[0] and row[1] is not None and float(row[1]) > 120:
    response = httpx.post(
        os.getenv("NOTIDECK_URL", "http://127.0.0.1:8000") + "/api/v1/notifications",
        headers={"Authorization": "Bearer " + os.environ["NOTIDECK_API_KEY"]},
        json={
            "environment": "production",
            "severity": "CRITICAL",
            "title": "Replica lag exceeded 120 seconds",
            "message": "Investigate replica replay and primary workload.",
            "metadata": {"lag_seconds": float(row[1])},
            "idempotency_key": f"replica-lag-{time.time_ns()}",
        },
        timeout=15,
    )
    response.raise_for_status()
# Idle primaries can make replay timestamp lag misleading; adapt monitoring to your workload.
