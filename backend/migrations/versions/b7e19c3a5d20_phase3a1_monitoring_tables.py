"""monitoring tables: snmp credential profiles, device poll state, device/interface metrics

Phase 3a-1 (gaps G-05, G-15 groundwork; SEC-33). ADDITIVE ONLY: creates four new tables and touches no
existing one, so it cannot break Phase 1/2 data or code. Downgrade drops exactly these four tables.

Revision ID: b7e19c3a5d20
Revises: e85b9a356da8
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e19c3a5d20"
down_revision = "e85b9a356da8"
branch_labels = None
depends_on = None


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.create_table(
        "snmp_credential_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("security_level", sa.String(length=12), server_default="authPriv", nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("auth_protocol", sa.String(length=8), nullable=False),
        sa.Column("auth_key_enc", sa.Text(), nullable=False),
        sa.Column("priv_protocol", sa.String(length=8), nullable=True),
        sa.Column("priv_key_enc", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint(f"security_level IN ({_in(('authPriv', 'authNoPriv'))})",
                           name="ck_snmp_profiles_security_level"),
        sa.CheckConstraint(f"auth_protocol IN ({_in(('SHA', 'SHA256', 'SHA384', 'SHA512'))})",
                           name="ck_snmp_profiles_auth_protocol"),
        sa.CheckConstraint(f"priv_protocol IS NULL OR priv_protocol IN ({_in(('AES128', 'AES192', 'AES256'))})",
                           name="ck_snmp_profiles_priv_protocol"),
        sa.CheckConstraint(
            "(security_level = 'authPriv' AND priv_protocol IS NOT NULL AND priv_key_enc IS NOT NULL) OR "
            "(security_level = 'authNoPriv' AND priv_protocol IS NULL AND priv_key_enc IS NULL)",
            name="ck_snmp_profiles_priv_consistent"),
    )
    op.create_index("uq_snmp_profiles_single_default", "snmp_credential_profiles", ["is_default"], unique=True,
                    postgresql_where=sa.text("is_default"))

    op.create_table(
        "device_poll_state",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("credential_profile_id", sa.Uuid(), nullable=True),
        sa.Column("poll_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("vendor_profile", sa.String(length=32), nullable=True),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_kind", sa.String(length=24), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_profile_id"], ["snmp_credential_profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("device_id"),
        sa.CheckConstraint("consecutive_failures >= 0", name="ck_device_poll_state_failures"),
    )
    op.create_index("ix_device_poll_state_last_success_at", "device_poll_state", ["last_success_at"])

    op.create_table(
        "device_metrics",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_pct", sa.Float(), nullable=True),
        sa.Column("mem_pct", sa.Float(), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("uptime_s", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "ts", name="pk_device_metrics"),
        sa.CheckConstraint("cpu_pct IS NULL OR (cpu_pct >= 0 AND cpu_pct <= 100)", name="ck_device_metrics_cpu"),
        sa.CheckConstraint("mem_pct IS NULL OR (mem_pct >= 0 AND mem_pct <= 100)", name="ck_device_metrics_mem"),
    )
    op.create_index("ix_device_metrics_ts", "device_metrics", ["ts"])

    op.create_table(
        "interface_metrics",
        sa.Column("interface_id", sa.Uuid(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("in_bps", sa.BigInteger(), nullable=True),
        sa.Column("out_bps", sa.BigInteger(), nullable=True),
        sa.Column("in_util_pct", sa.Float(), nullable=True),
        sa.Column("out_util_pct", sa.Float(), nullable=True),
        sa.Column("in_errors", sa.Integer(), nullable=True),
        sa.Column("out_errors", sa.Integer(), nullable=True),
        sa.Column("in_discards", sa.Integer(), nullable=True),
        sa.Column("out_discards", sa.Integer(), nullable=True),
        sa.Column("oper_status", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["interface_id"], ["interfaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("interface_id", "ts", name="pk_interface_metrics"),
        sa.CheckConstraint("in_util_pct IS NULL OR (in_util_pct >= 0 AND in_util_pct <= 100)",
                           name="ck_interface_metrics_in_util"),
        sa.CheckConstraint("out_util_pct IS NULL OR (out_util_pct >= 0 AND out_util_pct <= 100)",
                           name="ck_interface_metrics_out_util"),
    )
    op.create_index("ix_interface_metrics_ts", "interface_metrics", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_interface_metrics_ts", table_name="interface_metrics")
    op.drop_table("interface_metrics")
    op.drop_index("ix_device_metrics_ts", table_name="device_metrics")
    op.drop_table("device_metrics")
    op.drop_index("ix_device_poll_state_last_success_at", table_name="device_poll_state")
    op.drop_table("device_poll_state")
    op.drop_index("uq_snmp_profiles_single_default", table_name="snmp_credential_profiles",
                  postgresql_where=sa.text("is_default"))
    op.drop_table("snmp_credential_profiles")
