# Budget Model

## 1. Objective

The budget model represents token authority as a finite, auditable resource.

It is deliberately independent of provider price, currency, and model family.

## 2. Minimal budget record

```text
Budget {
  budget_id
  scope_id
  parent_budget_id?
  limit
  consumed
  reserved
  status
  created_at
  valid_until?
}
```

Derived value:

```text
available = limit - consumed - reserved
```

## 3. Units

Draft 0.1 assumes one abstract token unit.

An implementation MAY keep separate counters for input, output, cached, reasoning, or provider-specific token classes, but those distinctions MUST NOT weaken the conservation invariant.

## 4. Scope hierarchy

Budgets MAY be nested.

Example:

```text
Tenant budget: 1,000,000
  |
  +-- Workflow A: 300,000
  |     |
  |     +-- Agent A1: 80,000
  |     +-- Agent A2: 120,000
  |
  +-- Workflow B: 200,000
```

Child budgets are delegations.

Creating a child budget MUST reserve or otherwise encumber equivalent authority in the parent. Destroying or closing a child budget MAY return only its unused authority.

## 5. Conservation

For a simple budget:

```text
consumed + reserved + available = limit
```

For a parent with delegated child capacity, an implementation MUST also account for delegated-but-not-yet-consumed authority so that the same tokens cannot be authorized twice.

The exact storage model is implementation-specific; double allocation is prohibited.

## 6. Status

Baseline states:

```text
OPEN
EXHAUSTED
CLOSED
REVOKED
```

### OPEN

New reservations may be evaluated.

### EXHAUSTED

The budget cannot satisfy the requested governed work under current policy.

### CLOSED

No new reservations are allowed. Existing reservations must be settled or explicitly resolved.

### REVOKED

Further use is forbidden even if numerical capacity remains.

## 7. Time

A budget MAY define `valid_until`.

Expired budget authority MUST NOT be used for new reservations.

Expiration does not erase historical consumption or unresolved reservations.

## 8. Retry behavior

Retries are not free.

A retry MUST either:

- consume from an existing valid reservation whose semantics permit reuse, or
- obtain a new reservation from remaining budget.

A retry MUST NOT reset consumed usage.

## 9. Model switching

Changing provider or model does not reset the budget.

If a cheaper or smaller model is selected under a DEGRADE policy, it still consumes governed capacity.

## 10. Future extensions

Not specified in Draft 0.1:

- price-denominated budgets,
- multi-resource budgets,
- weighted token classes,
- borrowing,
- refill schedules,
- organizational quota markets,
- probabilistic reservations.

These should be introduced only when concrete use cases require them.
