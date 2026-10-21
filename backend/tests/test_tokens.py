"""JWT creation/validation contract."""

from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings
from app.security import tokens
from app.security.tokens import ALGORITHM, create_access_token, decode_access_token


def test_roundtrip_has_required_claims():
    t = create_access_token("user-1", "operator", ["BSB"])
    c = decode_access_token(t)
    assert c is not None
    assert c["sub"] == "user-1" and c["role"] == "operator" and c["scopes"] == ["BSB"]
    assert {"iat", "exp", "jti"} <= set(c)


def test_each_token_has_unique_jti():
    a = decode_access_token(create_access_token("u", "operator", []))
    b = decode_access_token(create_access_token("u", "operator", []))
    assert a and b and a["jti"] != b["jti"]


def test_tampered_token_rejected():
    t = create_access_token("u", "operator", [])
    assert decode_access_token(t[:-3] + ("AAA" if not t.endswith("AAA") else "BBB")) is None


def test_wrong_key_rejected():
    forged = jwt.encode({"sub": "u", "exp": datetime.now(UTC) + timedelta(hours=1)}, "x" * 40, algorithm=ALGORITHM)
    assert decode_access_token(forged) is None


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(tokens, "get_settings", lambda: Settings(access_token_expire_minutes=-1))
    assert decode_access_token(create_access_token("u", "operator", [])) is None


def test_missing_exp_rejected():
    key = Settings().secret_key.get_secret_value()
    assert decode_access_token(jwt.encode({"sub": "u"}, key, algorithm=ALGORITHM)) is None


def test_alg_none_rejected():
    assert decode_access_token(jwt.encode({"sub": "u", "exp": 9999999999}, key=None, algorithm="none")) is None
