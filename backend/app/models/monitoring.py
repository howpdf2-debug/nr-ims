"""Monitoring tables (Phase 3a-1). ADDITIVE ONLY: no existing table is altered.

* ``snmp_credential_profiles``  SNMPv3 users; passphrases stored as Fernet tokens (SEC-33). One default
                                profile + optional per-device override (``device_poll_state``).
* ``device_poll_state``         per-device poll bookkeeping: last success, consecutive failures, last error.
                                Feeds the dead-man switch (ARC-04) in 3a-2.
* ``device_metrics``            raw device samples (CPU / memory / temperature / uptime). 7-day raw retention
                                (ARC-09); hourly roll-ups arrive in 3a-2.
* ``interface_metrics``         raw per-interface rates, utilisation and error deltas.

Both metric tables are narrow, append-only and keyed (entity, ts): TimescaleDB-ready (hypertable on ``ts``)
without any schema change.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

AUTH_PROTOCOLS = ("SHA", "SHA256", "SHA384", "SHA512")
PRIV_PROTOCOLS = ("AES128", "AES192", "AES256")
SECURITY_LEVELS = ("authPriv", "authNoPriv")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class SnmpCredentialProfile(Base):
    __tablename__ = "snmp_credential_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    security_level: Mapped[str] = mapped_column(String(12), server_default="authPriv")
    username: Mapped[str] = mapped_column(String(64))
    auth_protocol: Mapped[str] = mapped_column(String(8))
    auth_key_enc: Mapped[str] = mapped_column(Text)  # Fernet token, never plaintext
    priv_protocol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    priv_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"security_level IN ({_in(SECURITY_LEVELS)})", name="ck_snmp_profiles_security_level"),
        CheckConstraint(f"auth_protocol IN ({_in(AUTH_PROTOCOLS)})", name="ck_snmp_profiles_auth_protocol"),
        CheckConstraint(f"priv_protocol IS NULL OR priv_protocol IN ({_in(PRIV_PROTOCOLS)})",
                        name="ck_snmp_profiles_priv_protocol"),
        # authPriv MUST carry a privacy protocol and key; authNoPriv must not.
        CheckConstraint(
            "(security_level = 'authPriv' AND priv_protocol IS NOT NULL AND priv_key_enc IS NOT NULL) OR "
            "(security_level = 'authNoPriv' AND priv_protocol IS NULL AND priv_key_enc IS NULL)",
            name="ck_snmp_profiles_priv_consistent"),
        # At most one default profile.
        Index("uq_snmp_profiles_single_default", "is_default", unique=True, postgresql_where=text("is_default")),
    )


class DevicePollState(Base):
    __tablename__ = "device_poll_state"

    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True)
    # NULL = use the default profile. SET NULL (not CASCADE) if a profile is deleted: the device keeps its row.
    credential_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("snmp_credential_profiles.id", ondelete="SET NULL"), nullable=True)
    poll_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    vendor_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, server_default="0")
    last_error_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("consecutive_failures >= 0", name="ck_device_poll_state_failures"),
        Index("ix_device_poll_state_last_success_at", "last_success_at"),
    )


class DeviceMetric(Base):
    __tablename__ = "device_metrics"

    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cpu_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_s: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("device_id", "ts", name="pk_device_metrics"),
        CheckConstraint("cpu_pct IS NULL OR (cpu_pct >= 0 AND cpu_pct <= 100)", name="ck_device_metrics_cpu"),
        CheckConstraint("mem_pct IS NULL OR (mem_pct >= 0 AND mem_pct <= 100)", name="ck_device_metrics_mem"),
        Index("ix_device_metrics_ts", "ts"),  # retention purge scans by time
    )


class InterfaceMetric(Base):
    __tablename__ = "interface_metrics"

    interface_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interfaces.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    in_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    out_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    in_util_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_util_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_errors: Mapped[int | None] = mapped_column(Integer, nullable=True)  # deltas over the interval
    out_errors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    in_discards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    out_discards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oper_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # IF-MIB ifOperStatus

    __table_args__ = (
        PrimaryKeyConstraint("interface_id", "ts", name="pk_interface_metrics"),
        CheckConstraint("in_util_pct IS NULL OR (in_util_pct >= 0 AND in_util_pct <= 100)",
                        name="ck_interface_metrics_in_util"),
        CheckConstraint("out_util_pct IS NULL OR (out_util_pct >= 0 AND out_util_pct <= 100)",
                        name="ck_interface_metrics_out_util"),
        Index("ix_interface_metrics_ts", "ts"),
    )
