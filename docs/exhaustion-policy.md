# Exhaustion Policy

## 1. Purpose

Exhaustion is not an exception to governance. It is a governed state with explicit behavior.

A system MUST decide what to do when requested work exceeds currently authorized capacity.

Draft 0.1 defines three baseline decisions:

```text
BLOCK
DEGRADE
ESCALATE
```

## 2. BLOCK

The requested token-consuming work is not authorized.

Required behavior:

- do not begin the governed model call,
- do not create hidden replacement budget,
- emit a machine-readable BLOCK decision,
- preserve current accounting state.

Typical reason codes may include:

```text
INSUFFICIENT_BUDGET
BUDGET_CLOSED
BUDGET_REVOKED
BUDGET_EXPIRED
```

## 3. DEGRADE

The original request cannot be authorized as proposed, but an explicitly lower-cost execution path may be evaluated.

Examples:

- lower maximum output,
- smaller context,
- fewer agent branches,
- cheaper model,
- fewer evaluation passes.

DEGRADE is not automatic permission to execute.

The degraded plan MUST itself obtain a valid reservation before consuming tokens.

```text
original request
      |
      v
insufficient capacity
      |
      v
DEGRADE
      |
      v
new bounded plan
      |
      v
new reservation decision
```

## 4. ESCALATE

The current authority cannot approve the requested capacity and asks a higher authority for an explicit decision.

Escalation MUST NOT itself increase the budget.

A higher authority may:

- grant additional budget,
- change the scope,
- approve a different bounded plan,
- deny the request.

Until new authority exists, the original work remains unauthorized.

## 5. Default behavior

If no exhaustion policy is configured, the safe baseline is:

```text
BLOCK
```

Silently continuing is not a valid default.

## 6. Hard and soft limits

An implementation MAY distinguish:

```text
soft_limit < hard_limit
```

Crossing a soft limit may trigger DEGRADE or ESCALATE.

Crossing a hard limit MUST prevent further unauthorized consumption.

A soft limit does not create additional authority beyond the hard limit.

## 7. Nested scopes

If a child scope is exhausted, it MUST NOT automatically consume unallocated parent capacity.

The child may request additional delegation from its parent, but that is a new governance decision.

## 8. Retry storms

Exhaustion policy applies to retries.

Repeated failure MUST NOT bypass governance by repeatedly reserving small amounts without respecting the same parent budget.

Implementations SHOULD make retry attribution visible so operators can distinguish productive consumption from repeated failure.

## 9. Kill behavior

A future runtime MAY support a kill switch.

The expected semantic direction is:

```text
REVOKED budget
    ->
no new reservations
    ->
active executions instructed to stop at the next safe boundary
```

Draft 0.1 does not specify distributed termination mechanics.

## 10. Decision record

Every exhaustion decision SHOULD produce a record containing at least:

```text
decision
reason
budget_id
scope_id
requested_amount
available_before
timestamp
```

This allows later audit without making audit a substitute for preventive control.
