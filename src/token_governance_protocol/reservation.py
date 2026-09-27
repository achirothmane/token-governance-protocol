from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "eba.integration/v0.1"
RESERVATION_KIND = "BudgetReservation"

OPEN = "OPEN"
EXHAUSTED = "EXHAUSTED"
CLOSED = "CLOSED"
REVOKED = "REVOKED"

GRANT = "GRANT"
BLOCK = "BLOCK"


class BudgetReservationError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BudgetReservationError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise BudgetReservationError("timestamps must include timezone information")
    return parsed.astimezone(timezone.utc)


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    return f"{prefix}_{_digest(value)[:24]}"


def _with_integrity(value: dict[str, Any]) -> dict[str, Any]:
    artifact = dict(value)
    artifact.pop("integrity", None)
    artifact["integrity"] = {
        "algorithm": "sha256",
        "digest": _digest(artifact),
    }
    return artifact


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    budget_id: str
    scope_id: str
    limit: int
    consumed: int
    reserved: int
    status: str = OPEN
    valid_until: str | None = None

    @property
    def available(self) -> int:
        return self.limit - self.consumed - self.reserved


@dataclass(frozen=True, slots=True)
class ReservationRequest:
    requested_amount: int
    idempotency_key: str
    execution_ref: str
    principal_id: str


@dataclass(frozen=True, slots=True)
class ReservationResult:
    decision: str
    reason: str
    budget_before: BudgetSnapshot
    budget_after: BudgetSnapshot
    reservation: dict[str, Any] | None


def _validate_budget(snapshot: BudgetSnapshot) -> None:
    if not snapshot.budget_id:
        raise BudgetReservationError("budget_id is required")
    if not snapshot.scope_id:
        raise BudgetReservationError("scope_id is required")
    if snapshot.limit < 0 or snapshot.consumed < 0 or snapshot.reserved < 0:
        raise BudgetReservationError("budget counters must be non-negative")
    if snapshot.consumed + snapshot.reserved > snapshot.limit:
        raise BudgetReservationError("BUDGET_INVARIANT_VIOLATION")
    if snapshot.status not in {OPEN, EXHAUSTED, CLOSED, REVOKED}:
        raise BudgetReservationError("invalid budget status")
    _parse_time(snapshot.valid_until)


def _validate_request(request: ReservationRequest) -> None:
    if request.requested_amount <= 0:
        raise BudgetReservationError("requested_amount must be positive")
    if not request.idempotency_key:
        raise BudgetReservationError("idempotency_key is required")
    if not request.execution_ref:
        raise BudgetReservationError("execution_ref is required")
    if not request.principal_id:
        raise BudgetReservationError("principal_id is required")


def reserve(
    snapshot: BudgetSnapshot,
    request: ReservationRequest,
    *,
    trace_id: str,
    created_at: str | None = None,
    expires_at: str | None = None,
) -> ReservationResult:
    """Evaluate one reservation against an authoritative budget snapshot.

    This reference function is pure. A production runtime MUST perform the
    corresponding availability check and state mutation atomically in its
    authoritative store.
    """
    _validate_budget(snapshot)
    _validate_request(request)
    if not trace_id:
        raise BudgetReservationError("trace_id is required")

    timestamp = created_at or _utc_now()
    now = _parse_time(timestamp)
    assert now is not None
    budget_expiry = _parse_time(snapshot.valid_until)

    reason: str | None = None
    if snapshot.status == REVOKED:
        reason = "BUDGET_REVOKED"
    elif snapshot.status == CLOSED:
        reason = "BUDGET_CLOSED"
    elif snapshot.status == EXHAUSTED:
        reason = "BUDGET_EXHAUSTED"
    elif budget_expiry is not None and now > budget_expiry:
        reason = "BUDGET_EXPIRED"
    elif request.requested_amount > snapshot.available:
        reason = "INSUFFICIENT_BUDGET"

    if reason is not None:
        return ReservationResult(
            decision=BLOCK,
            reason=reason,
            budget_before=snapshot,
            budget_after=snapshot,
            reservation=None,
        )

    after = replace(snapshot, reserved=snapshot.reserved + request.requested_amount)
    _validate_budget(after)

    artifact: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "kind": RESERVATION_KIND,
        "trace_id": trace_id,
        "producer": "token-governance-protocol",
        "created_at": timestamp,
        "budget_id": snapshot.budget_id,
        "scope_id": snapshot.scope_id,
        "principal_id": request.principal_id,
        "execution_ref": request.execution_ref,
        "idempotency_key": request.idempotency_key,
        "budget_type": "tokens",
        "requested": request.requested_amount,
        "reserved": request.requested_amount,
        "hard_limit": snapshot.limit,
        "available_before": snapshot.available,
        "available_after": after.available,
        "status": "RESERVED",
        "protocol_state": "ACTIVE",
        "expires_at": expires_at,
    }
    artifact["id"] = _stable_id("budget", artifact)
    artifact = _with_integrity(artifact)

    return ReservationResult(
        decision=GRANT,
        reason="RESERVATION_GRANTED",
        budget_before=snapshot,
        budget_after=after,
        reservation=artifact,
    )


def validate_budget_reservation(
    artifact: dict[str, Any],
    *,
    execution_ref: str | None = None,
    principal_id: str | None = None,
    now: str | None = None,
) -> None:
    if artifact.get("contract_version") != CONTRACT_VERSION:
        raise BudgetReservationError("BUDGET_CONTRACT_VERSION_INVALID")
    if artifact.get("kind") != RESERVATION_KIND:
        raise BudgetReservationError("BUDGET_KIND_INVALID")
    if artifact.get("budget_type") != "tokens":
        raise BudgetReservationError("BUDGET_TYPE_INVALID")
    if artifact.get("status") != "RESERVED" or artifact.get("protocol_state") != "ACTIVE":
        raise BudgetReservationError("BUDGET_RESERVATION_INACTIVE")

    # Integrity is checked before interpreting mutable numeric semantics.
    # A modified artifact must be classified as tampered rather than as a
    # legitimate but malformed reservation.
    integrity = artifact.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        raise BudgetReservationError("BUDGET_INTEGRITY_INVALID")
    unsigned = dict(artifact)
    unsigned.pop("integrity", None)
    if integrity.get("digest") != _digest(unsigned):
        raise BudgetReservationError("BUDGET_INTEGRITY_INVALID")

    requested = artifact.get("requested")
    reserved = artifact.get("reserved")
    hard_limit = artifact.get("hard_limit")
    available_before = artifact.get("available_before")
    available_after = artifact.get("available_after")
    if not all(type(value) is int for value in (
        requested,
        reserved,
        hard_limit,
        available_before,
        available_after,
    )):
        raise BudgetReservationError("BUDGET_NUMERIC_FIELDS_INVALID")
    if requested <= 0 or reserved != requested:
        raise BudgetReservationError("BUDGET_RESERVATION_AMOUNT_INVALID")
    if available_before - reserved != available_after:
        raise BudgetReservationError("BUDGET_RESERVATION_CONSERVATION_INVALID")
    if hard_limit < reserved:
        raise BudgetReservationError("BUDGET_RESERVATION_LIMIT_INVALID")

    if execution_ref is not None and artifact.get("execution_ref") != execution_ref:
        raise BudgetReservationError("BUDGET_EXECUTION_MISMATCH")
    if principal_id is not None and artifact.get("principal_id") != principal_id:
        raise BudgetReservationError("BUDGET_PRINCIPAL_MISMATCH")

    expires_at = _parse_time(artifact.get("expires_at"))
    if expires_at is not None:
        current = _parse_time(now or _utc_now())
        assert current is not None
        if current > expires_at:
            raise BudgetReservationError("BUDGET_RESERVATION_EXPIRED")
