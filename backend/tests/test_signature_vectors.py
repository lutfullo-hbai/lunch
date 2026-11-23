"""Imzo uchun qat'iy namunalar. Aynan shu qiymatlar frontend/tests/signing.test.mjs da ham bor:
frontend (Web Crypto) va backend imzosi bir xil chiqishi shu orqali kafolatlanadi."""

import hashlib

from app.core.signature import build_string_to_sign, compute_signature


def test_post_with_body_query_and_non_ascii_key():
    body = b'{"items":[{"menu_item_id":1,"quantity":2}],"payment_method":"card"}'
    assert (
        hashlib.sha256(body).hexdigest()
        == "df572ebce81b9b2e4c2f5a218c97612023120d051e94bf0f7107801384d14f56"
    )
    to_sign = build_string_to_sign("POST", "/api/v1/orders?x=1", "1795400000", "abc123nonce", body)
    assert (
        compute_signature("test-signing-key-ж", to_sign)
        == "00e7eb262bc6c10c587d7c5cf231af567cf6b614677fd83311115222e8244d94"
    )


def test_get_without_body():
    to_sign = build_string_to_sign("get", "/api/v1/me", "1", "n", b"")
    assert (
        compute_signature("k", to_sign)
        == "702e92d12ca5dd8b3aa10d691718f1c8b860a3d366d02ac06cac34aed6d455d9"
    )
