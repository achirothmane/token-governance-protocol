import copy

import pytest

from token_governance_protocol.reservation import (
    BLOCK,
    GRANT,
    BudgetReservationError,
    BudgetSnapshot,
    ReservationRequest,
    reserve,
    validate_budget_reservation,
)

NOW = "2026-09-27T17:00:00Z"


def _budget(**overrides):
    values = dict(
        budget_id="budget-1",
        scope_id="agent-run-1",
        limit=100_000,
        consumed=20_000,
        reserved=10_000,
        status="OPEN",
        valid_until="2026-09-27T18:00:00Z",
    )
    values.update(overrides)
    return BudgetSnapshot(**values)


def _request(**overrides):
    values = dict(
        requested_amount=30_000,
        idempotency_key="run-1:model-call-1",
        execution_ref="req_123",
        principal_id="research-agent",
    )
    values.update(overrides)
    return ReservationRequest(**values)


def test_grant_preserves_budget_conservation():
    result = reserve(_budget(), _request(), trace_id="tr_1", created_at=NOW)

    assert result.decision == GRANT
    assert result.budget_before.available == 70_000
    assert result.budget_after.reserved == 40_000
    assert result.budget_after.available == 40_000
    assert (
        result.budget_after.consumed
        + result.budget_after.reserved
        + result.budget_after.available
        == result.budget_after.limit
    )


def test_grant_emits_eba_budget_reservation():
    result = reserve(_budget(), _request(), trace_id="tr_1", created_at=NOW)
    artifact = result.reservation
    assert artifact is not None
    assert artifact["contract_version"] == "eba.integration/v0.1"
    assert artifact["kind"] == "BudgetReservation"
    assert artifact["status"] == "RESERVED"
    assert artifact["protocol_state"] == "ACTIVE"
    assert artifact["reserved"] == 30_000
    assert artifact["available_before"] == 70_000
    assert artifact["available_after"] == 40_000
    validate_budget_reservation(
        artifact,
        execution_ref="req_123",
        principal_id="research-agent",
        now=NOW,
    )


def test_insufficient_budget_blocks_without_mutation():
    budget = _budget()
    result = reserve(
        budget,
        _request(requested_amount=70_001),
        trace_id="tr_1",
        created_at=NOW,
    )
    assert result.decision == BLOCK
    assert result.reason == "INSUFFICIENT_BUDGET"
    assert result.reservation is None
    assert result.budget_after == budget


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("CLOSED", "BUDGET_CLOSED"),
        ("REVOKED", "BUDGET_REVOKED"),
        ("EXHAUSTED", "BUDGET_EXHAUSTED"),
    ],
)
def test_non_open_budget_blocks(status, reason):
    result = reserve(
        _budget(status=status),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
    )
    assert result.decision == BLOCK
    assert result.reason == reason
    assert result.reservation is None


def test_expired_budget_blocks():
    result = reserve(
        _budget(valid_until="2026-09-27T16:59:59Z"),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
    )
    assert result.decision == BLOCK
    assert result.reason == "BUDGET_EXPIRED"




def test_budget_exact_expiry_blocks():
    result = reserve(
        _budget(valid_until=NOW),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
    )
    assert result.decision == BLOCK
    assert result.reason == "BUDGET_EXPIRED"


def test_reservation_inherits_finite_budget_expiry():
    artifact = reserve(
        _budget(valid_until="2026-09-27T18:00:00Z"),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
    ).reservation
    assert artifact is not None
    assert artifact["expires_at"] == "2026-09-27T18:00:00Z"


def test_requested_reservation_expiry_is_capped_by_budget():
    artifact = reserve(
        _budget(valid_until="2026-09-27T18:00:00Z"),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
        expires_at="2026-09-27T19:00:00Z",
    ).reservation
    assert artifact is not None
    assert artifact["expires_at"] == "2026-09-27T18:00:00Z"


def test_unbounded_budget_requires_finite_reservation_expiry():
    with pytest.raises(BudgetReservationError, match="RESERVATION_EXPIRES_AT_MISSING"):
        reserve(
            _budget(valid_until=None),
            _request(),
            trace_id="tr_1",
            created_at=NOW,
        )


def test_reservation_exact_expiry_is_rejected():
    artifact = reserve(
        _budget(),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
        expires_at="2026-09-27T17:05:00Z",
    ).reservation
    assert artifact is not None
    with pytest.raises(BudgetReservationError, match="RESERVATION_EXPIRED"):
        validate_budget_reservation(
            artifact,
            now="2026-09-27T17:05:00Z",
        )


def test_malformed_reservation_expiry_is_rejected():
    artifact = reserve(
        _budget(),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
    ).reservation
    assert artifact is not None
    malformed = copy.deepcopy(artifact)
    malformed["expires_at"] = 123
    import hashlib, json
    unsigned = dict(malformed)
    unsigned.pop("integrity", None)
    malformed["integrity"] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(
            json.dumps(
                unsigned,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
    }
    with pytest.raises(BudgetReservationError, match="RESERVATION_EXPIRES_AT_INVALID"):
        validate_budget_reservation(malformed, now=NOW)


def test_invalid_budget_invariant_is_rejected():
    with pytest.raises(BudgetReservationError, match="INVARIANT"):
        reserve(
            _budget(limit=100, consumed=80, reserved=30),
            _request(requested_amount=1),
            trace_id="tr_1",
            created_at=NOW,
        )


def test_non_positive_request_is_rejected():
    with pytest.raises(BudgetReservationError, match="positive"):
        reserve(
            _budget(),
            _request(requested_amount=0),
            trace_id="tr_1",
            created_at=NOW,
        )


def test_tampering_breaks_integrity():
    artifact = reserve(
        _budget(), _request(), trace_id="tr_1", created_at=NOW
    ).reservation
    assert artifact is not None
    tampered = copy.deepcopy(artifact)
    tampered["reserved"] = 99_999

    with pytest.raises(BudgetReservationError, match="INTEGRITY|CONSERVATION"):
        validate_budget_reservation(tampered, now=NOW)


def test_execution_binding_is_fail_closed():
    artifact = reserve(
        _budget(), _request(), trace_id="tr_1", created_at=NOW
    ).reservation
    assert artifact is not None

    with pytest.raises(BudgetReservationError, match="EXECUTION_MISMATCH"):
        validate_budget_reservation(
            artifact,
            execution_ref="req_other",
            principal_id="research-agent",
            now=NOW,
        )


def test_principal_binding_is_fail_closed():
    artifact = reserve(
        _budget(), _request(), trace_id="tr_1", created_at=NOW
    ).reservation
    assert artifact is not None

    with pytest.raises(BudgetReservationError, match="PRINCIPAL_MISMATCH"):
        validate_budget_reservation(
            artifact,
            execution_ref="req_123",
            principal_id="other-agent",
            now=NOW,
        )


def test_expired_reservation_is_rejected_at_use_time():
    artifact = reserve(
        _budget(),
        _request(),
        trace_id="tr_1",
        created_at=NOW,
        expires_at="2026-09-27T17:05:00Z",
    ).reservation
    assert artifact is not None

    with pytest.raises(BudgetReservationError, match="RESERVATION_EXPIRED"):
        validate_budget_reservation(
            artifact,
            now="2026-09-27T17:05:01Z",
        )
