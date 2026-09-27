# Evidence-before-Action BudgetReservation profile

Token Governance Protocol can emit a `BudgetReservation` compatible with
`eba.integration/v0.1`.

A BudgetReservation is created only after a reservation request is granted.
A blocked request produces no reservation artifact and therefore cannot
populate `Decision.basis.budget_ref`.

## Flow

```text
BudgetSnapshot + ReservationRequest
               ↓
      Token Governance Protocol
               ↓
          GRANT / BLOCK
               ↓
        BudgetReservation
               ↓
       EBA Decision budget_ref
```

## Artifact binding

The reference artifact records:

- budget id
- governed scope
- principal id
- execution reference
- requested/reserved amount
- hard limit
- available capacity before and after
- idempotency key
- expiration
- SHA-256 integrity

Consumers should validate both the reservation integrity and its binding to
the exact execution/principal before consuming governed tokens.

## Important runtime boundary

The included implementation is a deterministic reference evaluator over an
authoritative budget snapshot. It does not claim to solve distributed
atomicity.

A production control plane MUST make the availability check and reservation
mutation atomically in the authoritative budget store. Two concurrent callers
must not both spend the same remaining capacity.
