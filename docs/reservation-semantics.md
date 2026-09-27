# Reservation Semantics

## 1. Why reservations exist

A usage counter that updates only after a model call cannot prevent overspend.

Reservations move governance ahead of execution:

```text
request work
    |
    v
reserve capacity
    |
    +-- denied --> exhaustion policy
    |
    +-- granted --> execute
                     |
                     v
                   settle
```

## 2. Reservation request

Minimum fields:

```text
reservation_request {
  budget_id
  requested_amount
  scope_id
  idempotency_key
}
```

`requested_amount` MUST be positive.

## 3. Grant condition

A reservation may be granted only when:

```text
budget.status == OPEN
AND requested_amount <= available
AND budget is temporally valid
AND caller is authorized
```

The availability check and reservation mutation MUST be atomic.

## 4. Grant effect

For granted amount `R`:

```text
reserved := reserved + R
```

The resulting reservation enters:

```text
ACTIVE
```

## 5. Settlement

Suppose:

```text
reserved amount = R
actual measured use = U
```

For `U <= R`:

```text
reserved := reserved - R
consumed := consumed + U
state := SETTLED
```

The unused remainder is:

```text
R - U
```

and becomes available again.

## 6. Release

A reservation that performed no token-consuming work MAY be released.

```text
reserved := reserved - R
state := RELEASED
```

Release MUST NOT be used to erase real consumption.

## 7. Cancellation

Cancellation is a control-plane termination of a reservation before normal settlement.

If consumption may already have occurred, cancellation alone is insufficient; measured usage must first be accounted for or the reservation must enter an implementation-defined reconciliation path.

## 8. Overrun

`U > R` is a governance event.

The implementation MUST NOT silently transform the reservation into a larger one.

Possible future strategies include:

- pre-authorized bounded overrun,
- emergency reserve,
- immediate block of continuation,
- escalation to a higher authority.

Draft 0.1 leaves the exact overrun strategy open, but requires it to be explicit and auditable.

## 9. Idempotency

The same `idempotency_key` within the same governing scope SHOULD return the same logical reservation outcome.

This prevents network retries from allocating the same budget multiple times.

Settlement SHOULD also be idempotent.

## 10. Concurrency

Two concurrent reservation requests must not both observe the same remaining capacity and both receive it.

Example:

```text
available = 100
request A = 80
request B = 80
```

A conforming system may grant A or B, but MUST NOT grant both against the same 100-token capacity.

## 11. Reservation ownership

A reservation SHOULD record enough identity to answer:

- who requested it,
- for which scope,
- for which execution,
- which budget authorized it.

A component MUST NOT be permitted to settle or release arbitrary reservations merely because it can execute model calls.

## 12. Expiry

Implementations MAY expire unused ACTIVE reservations.

Reservation expiry returns only unused reserved capacity. It does not reverse already measured consumption.
