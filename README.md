# Token Governance Protocol

A minimal protocol for governing token consumption before, during, and after agent or model execution.

The protocol treats tokens as a governed resource rather than an unbounded implementation detail. Its core rule is:

> **No governed execution may consume an unreserved token budget.**

This repository defines the protocol surface and now includes a small deterministic Python reference implementation for reservation decisions. It is **not** a distributed production control plane: authoritative runtimes must still make reservation checks and mutations atomically.

## Why this exists

Agentic systems can fan out across models, tools, retries, planners, evaluators, and sub-agents. A single user intent can therefore create token consumption that is difficult to predict or stop once execution begins.

Token Governance Protocol (TGP) introduces explicit resource authority around that behavior:

1. define a budget,
2. reserve capacity before execution,
3. consume against the reservation,
4. settle actual usage,
5. apply a deterministic exhaustion policy when the authorized budget is no longer sufficient.

The goal is not merely cost reporting after the fact. The goal is **control before consumption**.

## Core objects

- **Budget** — an authorized maximum for a scope and time window.
- **Reservation** — a temporary claim against available budget before work begins.
- **Consumption** — measured token usage attributed to a reservation.
- **Settlement** — reconciliation of reserved versus actually consumed tokens.
- **Exhaustion policy** — the required behavior when additional consumption is not authorized.

## Core invariant

For every governed scope:

```text
settled_consumption + active_reservations <= budget_limit
```

No component may bypass this invariant by retrying, spawning a sub-agent, switching models, or creating another execution path under the same governed scope.

## Repository layout

```text
token-governance-protocol/
├── README.md
├── SPEC.md
├── docs/
│   ├── budget-model.md
│   ├── reservation-semantics.md
│   └── exhaustion-policy.md
├── src/
│   └── token_governance_protocol/
└── tests/
```

## Status

**Draft 0.1 + reference reservation implementation.**

The protocol semantics remain provider-agnostic. The Python implementation exists to prove the reservation contract and Evidence-before-Action interoperability before choosing a production persistence/concurrency architecture.

## Design principles

- Governance happens before consumption, not only after billing.
- Reservations are explicit and attributable.
- Nested agents do not create free budget.
- Retries inherit governance constraints.
- Failure must not silently erase consumed usage.
- Exhaustion behavior must be deterministic.
- Accounting and authorization are related but distinct.
- Protocol semantics should remain model-provider agnostic.

## Non-goals for this stage

This repository does not yet define:

- provider billing reconciliation,
- fiat pricing,
- tokenizer normalization across providers,
- distributed consensus,
- a policy language,
- a hosted control plane,
- model routing or optimization.

Those may be added only when evidence shows they are required.

## Specification

Start with [SPEC.md](./SPEC.md).

Supporting semantics:

- [Budget model](./docs/budget-model.md)
- [Reservation semantics](./docs/reservation-semantics.md)
- [Exhaustion policy](./docs/exhaustion-policy.md)


## Reference implementation

Install the reference package from a checkout:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The implementation exposes a pure reservation evaluator over an authoritative
`BudgetSnapshot`. A granted request emits an
`eba.integration/v0.1` `BudgetReservation` artifact with SHA-256 integrity
and bindings to the principal and execution reference.

See [EBA BudgetReservation profile](./docs/eba-budget-reservation.md).
