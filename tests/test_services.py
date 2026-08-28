"""Pure-logic tests for ingest and auth services."""

from __future__ import annotations

from seamly.modules.auth import service as auth_service
from seamly.modules.ingest import service as ingest_service


def test_normalise_name_resolves_legal_suffix_variants():
    assert ingest_service.normalise_name("Calder Engineering Ltd") == ingest_service.normalise_name(
        "Calder Engineering Limited"
    )
    assert ingest_service.normalise_name(
        "ACME Industrial Supplies"
    ) == ingest_service.normalise_name("Acme Industrial Supplies Ltd")
    assert ingest_service.normalise_name("Brightwater Foods") == ingest_service.normalise_name(
        "Brightwater Foods Ltd"
    )


def test_normalise_name_handles_punctuation_and_case():
    assert ingest_service.normalise_name("Acme & Sons, Co.") == ingest_service.normalise_name(
        "acme and sons"
    )


def test_password_roundtrip():
    stored = auth_service.hash_password("s3cret")
    assert stored.startswith("pbkdf2$")
    assert auth_service.verify_password("s3cret", stored)
    assert not auth_service.verify_password("wrong", stored)


def test_tokens_are_hashed_not_stored_raw():
    token = auth_service.new_session_token()
    assert auth_service.hash_token(token) != token
    assert auth_service.hash_token(token) == auth_service.hash_token(token)
