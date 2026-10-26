"""NOTIDECK_API_KEY=... python examples/python_client.py"""

import os
import uuid
import httpx

response = httpx.post(
    os.getenv("NOTIDECK_URL", "http://127.0.0.1:8000") + "/api/v1/notifications",
    headers={"Authorization": "Bearer " + os.environ["NOTIDECK_API_KEY"]},
    json={
        "environment": "production",
        "severity": "ERROR",
        "title": "Example event",
        "message": "Submitted by the Python client.",
        "idempotency_key": str(uuid.uuid4()),
    },
    timeout=15,
)
response.raise_for_status()
print(response.json())
