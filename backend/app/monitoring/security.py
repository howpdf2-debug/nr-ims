"""Monitoring settings, SNMP target allow-list and credential encryption (Phase 3a-1).

* SEC-33  SNMPv3 passphrases are stored ONLY as Fernet tokens (never plaintext, never logged).
* SEC-35  The poller may only talk to IP *literals* inside an allow-list (default: private ranges), so a
          wrong or malicious inventory row cannot turn the NMS into a scanner of arbitrary hosts.
* SEC-13/14 (groundwork)  ``NRIMS_CREDENTIAL_KEY`` may hold several comma-separated Fernet keys: the first
          encrypts, all decrypt. That is the rotation path; the full vault arrives in Phase 4a.

Key handling, in the order tried:
1. ``NRIMS_CREDENTIAL_KEY`` (production: REQUIRED).
2. Development/test only: a key derived (HKDF-SHA256) from ``NRIMS_SECRET_KEY``. Zero set-up for a dev
   stack. Consequence: changing the secret key makes stored credentials undecryptable, so production must
   use an explicit key.
"""

from __future__ import annotations

import base64
import ipaddress
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import ConfigError, Env, Settings, get_settings

# RFC1918 + loopback (loopback is what the test simulator uses). Public addresses are refused by default.
DEFAULT_ALLOWED_CIDRS: tuple[str, ...] = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")
_HKDF_INFO = b"nrims-snmp-credentials-v1"


class CredentialError(Exception):
    """A stored credential cannot be decrypted (wrong/rotated key or tampered data). No secret inside."""


class TargetNotAllowed(ValueError):  # noqa: N818  (reads better at call sites than TargetNotAllowedError)
    """The SNMP target is not an IP literal inside the configured allow-list."""


class MonitoringSettings(BaseSettings):
    """Env vars carry the NRIMS_ prefix, e.g. ``NRIMS_SNMP_TIMEOUT_S=3``."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NRIMS_", extra="ignore")

    credential_key: SecretStr | None = None
    snmp_allowed_cidrs: list[str] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_CIDRS))
    snmp_port: int = Field(161, ge=1, le=65535)
    snmp_timeout_s: float = Field(2.0, gt=0, le=30)  # per request
    snmp_retries: int = Field(1, ge=0, le=5)
    snmp_context_name: str = Field("", max_length=64)  # empty for real routers; simulators use a name
    poll_deadline_s: float = Field(20.0, gt=0, le=300)  # hard cap for ONE device poll (SEC-31)
    snmp_profiles_file: Path | None = None  # override the packaged profiles.toml

    @field_validator("snmp_allowed_cidrs")
    @classmethod
    def _valid_cidrs(cls, value: list[str]) -> list[str]:
        for item in value:
            try:
                ipaddress.ip_network(item, strict=False)
            except ValueError as exc:
                raise ValueError(f"invalid CIDR in NRIMS_SNMP_ALLOWED_CIDRS: {item!r}") from exc
        return value


@lru_cache
def get_monitoring_settings() -> MonitoringSettings:
    return MonitoringSettings()


IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def check_snmp_target(host: str, allowed_cidrs: list[str] | tuple[str, ...]) -> IPAddress:
    """Return the parsed address or raise ``TargetNotAllowed``. Hostnames are refused on purpose (no DNS)."""
    try:
        ip = ipaddress.ip_address(host.strip())
    except ValueError:
        raise TargetNotAllowed("SNMP target must be an IP address, not a hostname") from None
    if not any(ip in ipaddress.ip_network(c, strict=False) for c in allowed_cidrs):
        raise TargetNotAllowed(f"SNMP target {ip} is outside NRIMS_SNMP_ALLOWED_CIDRS")
    return ip


def _derive_dev_key(secret: str) -> bytes:
    okm = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(secret.encode())
    return base64.urlsafe_b64encode(okm)


def build_fernet(app_settings: Settings | None = None, mon: MonitoringSettings | None = None) -> MultiFernet:
    app_settings = app_settings or get_settings()
    mon = mon or get_monitoring_settings()
    if mon.credential_key is not None:
        keys = [k.strip() for k in mon.credential_key.get_secret_value().split(",") if k.strip()]
        try:
            fernets = [Fernet(k.encode()) for k in keys]
        except (ValueError, TypeError):
            fernets = []
        if not fernets:
            raise ConfigError(
                "NRIMS_CREDENTIAL_KEY is not a valid Fernet key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return MultiFernet(fernets)
    if app_settings.env is Env.PRODUCTION:
        raise ConfigError("NRIMS_CREDENTIAL_KEY must be set in production (SNMP credentials are encrypted with it)")
    return MultiFernet([Fernet(_derive_dev_key(app_settings.secret_key.get_secret_value()))])


def encrypt_secret(plaintext: str, fernet: MultiFernet | None = None) -> str:
    return (fernet or build_fernet()).encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str, fernet: MultiFernet | None = None) -> str:
    try:
        return (fernet or build_fernet()).decrypt(token.encode()).decode()
    except InvalidToken:
        raise CredentialError(
            "Stored SNMP credential cannot be decrypted: the encryption key changed or the data was altered"
        ) from None
