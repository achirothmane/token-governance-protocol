from __future__ import annotations

import hashlib

import pytest

from token_governance_protocol.reservation import (
    BudgetReservationError,
    canonical_json_bytes,
)


def test_shared_key_order_vector():
    body = canonical_json_bytes({"b": 2, "a": 1})
    assert body == b'{"a":1,"b":2}'
    assert hashlib.sha256(body).hexdigest() == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )


def test_ambiguous_numbers_reject():
    with pytest.raises(BudgetReservationError, match="CANONICAL_NON_INTEGER_NUMBER"):
        canonical_json_bytes({"n": 1.0})
    with pytest.raises(BudgetReservationError, match="CANONICAL_INTEGER_OUT_OF_RANGE"):
        canonical_json_bytes({"n": 9007199254740992})
