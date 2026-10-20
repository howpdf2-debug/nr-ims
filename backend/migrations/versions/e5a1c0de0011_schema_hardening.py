"""schema hardening: server defaults for NOT NULL adds + hot-path indexes

Earlier migrations added NOT NULL columns without a server_default, which fails on
populated tables and breaks raw/ORM inserts that rely on the model's server_default.

Revision ID: e5a1c0de0011
Revises: c6195cae2b48
"""
from alembic import op

revision = "e5a1c0de0011"
down_revision = "c6195cae2b48"
branch_labels = None
depends_on = None

DEFAULTS = [
    ("devices", "is_maintenance", "false"),
    ("users", "scopes", "'[]'::jsonb"),
    ("links", "crc_errors", "0"),
    ("links", "is_admin_shutdown", "false"),
]
INDEXES = [
    ("ix_alarms_first_seen", "alarms", "first_seen"),
    ("ix_devices_status", "devices", "status"),
    ("ix_remote_actions_device_id_created_at", "remote_actions", "device_id, created_at DESC"),
    ("ix_audit_events_created_at", "audit_events", "created_at DESC"),
    ("ix_links_source_station", "links", "source_station"),
    ("ix_links_destination_station", "links", "destination_station"),
    ("ix_stations_parent_station_code", "stations", "parent_station_code"),
]


def upgrade() -> None:
    for table, col, default in DEFAULTS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT {default}")
    for name, table, cols in INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def downgrade() -> None:
    for name, _t, _c in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    for table, col, _d in DEFAULTS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
