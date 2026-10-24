"""Token extraction for the X-NRIMS-Auth / Authorization pair (pure, no server)."""

import pytest

from app.deps import AUTH_HEADER, extract_token


def test_header_name_is_the_one_the_frontend_sends():
    assert AUTH_HEADER == "X-NRIMS-Auth"


@pytest.mark.parametrize("custom,expected", [
    ("abc.def.ghi", "abc.def.ghi"),
    ("Bearer abc.def.ghi", "abc.def.ghi"),
    ("bearer abc.def.ghi", "abc.def.ghi"),
    ("  Bearer   abc.def.ghi  ", "abc.def.ghi"),
    ("  abc.def.ghi  ", "abc.def.ghi"),
])
def test_custom_header_accepts_raw_or_bearer_value(custom, expected):
    assert extract_token(custom, None) == expected


def test_authorization_bearer_is_the_fallback_when_no_custom_header():
    assert extract_token(None, "from-authorization") == "from-authorization"


def test_custom_header_wins_over_authorization():
    assert extract_token("custom", "other") == "custom"


@pytest.mark.parametrize("blank", ["", "   ", "Bearer ", "bearer    "])
def test_blank_custom_header_means_no_token_and_never_falls_through(blank):
    assert extract_token(blank, "valid-in-authorization") is None


def test_nothing_supplied():
    assert extract_token(None, None) is None
    assert extract_token(None, "") is None
