# Token Governance Protocol — Specification

**Status:** Draft 0.1  
**Scope:** Token-budget authorization and consumption control for model and agent execution.

## 1. Purpose

Token Governance Protocol (TGP) defines a provider-agnostic mechanism for deciding whether token-consuming work is authorized to begin or continue.

The protocol separates three concerns:

```text
Authorization -> Reservation -> Accounting
```

Authorization answers whether budget may be used.  
Reservation claims budget before execution.  
Accounting records what was actually consumed.

The protocol MUST NOT treat post-hoc usage reporting as equivalent to governance.

## 2. Terminology

### 2.1 Governed scope

A logical boundary to which a budget applies.

Examples include:

- one request,
- one user task,
- one agent run,
- one workflow,
- one tenant,
- one project,
- one time window.

A scope MAY have a parent scope.

### 2.2 Budget

A finite authorization to consume tokens within a governed scope.

A budget contains at minimum:

```text
budget_id
scope_id
limit
consumed
reserved
status
```

Where:

```text
available = limit - consumed - reserved
```

### 2.3 Reservation

A temporary claim on a portion of available budget made before execution.

A reservation contains at minimum:

```text
reservation_id
budget_id
amount
state
created_at
```

A reservation state is one of:

```text
ACTIVE
SETTLED
RELEASED
CANCELLED
```

### 2.4 Consumption

Actual token usage attributable to governed execution.

Consumption MUST be accounted for even if the associated execution fails.

### 2.5 Settlement

The transition that reconciles an ACTIVE reservation with actual measured consumption.

## 3. Normative requirements

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

### 3.1 Budget invariant

For every active budget:

```text
0 <= consumed
0 <= reserved
consumed + reserved <= limit
```

An implementation MUST preserve this invariant atomically for every reservation decision.

### 3.2 Reservation-before-execution

Governed execution MUST obtain a reservation before beginning token-consuming work.

If sufficient budget cannot be reserved, execution MUST follow the configured exhaustion policy.

### 3.3 No implicit budget creation

A child agent, retry, model switch, evaluator, or tool-driven model call MUST NOT create additional budget implicitly.

Any newly authorized amount MUST come from an explicit budget operation.

### 3.4 Attribution

Every governed consumption event MUST be attributable to a reservation or to an explicit exceptional accounting path.

Unattributed token use SHOULD be treated as a protocol violation.

### 3.5 Failed execution

Execution failure MUST NOT automatically release already consumed tokens.

Unused reserved capacity MAY be released after measured consumption is settled.

### 3.6 Idempotency

Reservation creation and settlement SHOULD support idempotency keys so retries of control-plane operations do not duplicate budget effects.

### 3.7 Parent-child conservation

When budgets are nested, a child budget MUST NOT authorize more capacity than its parent makes available to it.

A child allocation is therefore a delegation of existing authority, not creation of new authority.

## 4. Minimal state transitions

### 4.1 Budget

```text
OPEN
  |
  +--> EXHAUSTED
  |
  +--> CLOSED
  |
  +--> REVOKED
```

### 4.2 Reservation

```text
ACTIVE
  |-- settle --> SETTLED
  |-- release -> RELEASED
  |-- cancel --> CANCELLED
```

Only ACTIVE reservations contribute to `reserved`.

## 5. Reservation operation

A reservation request contains:

```text
scope_id
requested_amount
idempotency_key
```

The governing authority evaluates:

```text
requested_amount <= available
```

If true:

```text
reserved := reserved + requested_amount
decision := GRANT
```

Otherwise:

```text
decision := EXHAUSTION_POLICY
```

The check and mutation MUST be atomic.

## 6. Settlement operation

Given an ACTIVE reservation of `R` and measured usage `U`:

If `U <= R`:

```text
reserved := reserved - R
consumed := consumed + U
reservation.state := SETTLED
```

The unused amount `R - U` returns to available capacity.

If `U > R`, the implementation MUST NOT silently increase the budget. It MUST invoke an overrun rule defined by the exhaustion policy or a future extension of this specification.

## 7. Exhaustion

A budget is exhausted when no further requested governed work can be authorized under its remaining capacity.

Exhaustion behavior MUST be explicit. The baseline protocol supports:

```text
BLOCK
DEGRADE
ESCALATE
```

The semantics are defined in [docs/exhaustion-policy.md](./docs/exhaustion-policy.md).

## 8. Required observable decisions

A conforming implementation SHOULD expose machine-readable outcomes for governance decisions.

Minimum recommended decision vocabulary:

```text
GRANT
BLOCK
DEGRADE
ESCALATE
```

A decision record SHOULD contain:

```text
decision
budget_id
scope_id
requested_amount
available_before
reason
timestamp
```

## 9. Security and integrity properties

A conforming implementation SHOULD make it difficult for an execution component to:

- alter its own budget,
- settle another reservation,
- hide consumption,
- reuse a settled reservation,
- create unbounded child scopes,
- bypass an exhaustion decision.

Authorization to mutate governance state SHOULD be narrower than authorization to request model execution.

## 10. Conformance boundary

An implementation conforms to Draft 0.1 if it preserves the budget invariant and implements:

1. finite budgets,
2. reservation-before-execution,
3. attributable settlement,
4. deterministic exhaustion handling,
5. no implicit budget creation.

Everything else remains implementation-specific in this draft.
