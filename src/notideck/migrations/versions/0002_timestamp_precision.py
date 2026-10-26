"""Use double precision for epoch times, leases, backoff and durations.

MySQL FLOAT defaults to single precision, which rounds contemporary epoch seconds
by minutes. SQLite FLOAT already has REAL (64-bit) affinity. This migration preserves
records and nullability; previously rounded MySQL values cannot regain lost precision.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = {
    "nd_users": [("created_at", False)],
    "nd_sessions": [("created_at", False), ("expires_at", False)],
    "nd_sources": [("created_at", False)],
    "nd_api_keys": [("created_at", False), ("expires_at", True)],
    "nd_channels": [("created_at", False), ("next_send_at", False)],
    "nd_recipients": [("created_at", False)],
    "nd_groups": [("created_at", False)],
    "nd_templates": [("created_at", False)],
    "nd_rules": [("created_at", False)],
    "nd_notifications": [("created_at", False), ("updated_at", False)],
    "nd_deliveries": [
        ("created_at", False),
        ("available_at", False),
        ("lease_until", True),
        ("updated_at", False),
        ("accepted_at", True),
    ],
    "nd_attempts": [("created_at", False), ("duration_ms", False)],
    "nd_audits": [("created_at", False)],
    "nd_workers": [("heartbeat", False)],
}


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        return
    for table, columns in COLUMNS.items():
        for column, nullable in columns:
            op.alter_column(
                table, column, existing_type=sa.Float(), type_=sa.Double(), existing_nullable=nullable
            )


def downgrade():
    raise RuntimeError("Lossy timestamp downgrade disabled; restore a verified backup instead.")
