## Context

Statistics are currently accumulated by a standalone free function `update_statistics()` in `session.py` operating on a raw `dict[str, UsageStatistics]`. The key is a comma-joined `"provider,model"` string — a fragile encoding with no separator escaping. `UsageStatistics` is a Pydantic model in `pricing.py` that exists solely to bundle `TokensUsage` + optional `TokensCost`; it carries a circular-import shim because `TokensUsage` lives in `completion.py`. The `Session` aggregate holds two such dicts: one for lifetime cumulative stats and one for per-request stats, both reset and accumulated via the same free function.

## Goals / Non-Goals

**Goals:**
- Encapsulate accumulation logic into a `UsageStats` value object with explicit methods
- Replace the fragile flat string key with a structured nested dict keyed by provider then model
- Remove `UsageStatistics` Pydantic model and its circular-import workaround
- Replace the no-billing zero-cost sentinel with an explicit `None`
- Remove the `update_statistics` free function; all accumulation goes through `UsageStats`

**Non-Goals:**
- Changing the `ModelPricing` engine or cost estimation logic
- Altering the `TokensCost` or `TokensUsage` value objects themselves
- Modifying the HTTP/WS wire format beyond the statistics field shape

## Decisions

### D1: `ModelStats` as NamedTuple, not Pydantic model

`ModelStats(usage: TokensUsage, cost: TokensCost | None = None)` is a `NamedTuple`. Pydantic models are immutable-by-convention but mutable in practice; accumulation already creates new instances each time (matching the existing pattern for `TokensUsage`/`TokensCost`). A `NamedTuple` is lighter, requires no `model_rebuild()` shim, and makes the immutability explicit. Alternative: a `@dataclass` — rejected because the rest of the value-objects layer uses Pydantic or NamedTuple, not dataclasses.

### D2: `UsageStats` as a plain Python class

`UsageStats` is a mutable accumulator, not a pure value object. Encoding it as a Pydantic model would require `PrivateAttr` for `_data` and a custom serializer for the nested dict. A plain class is simpler, explicit, and consistent with `Session` itself (also a plain class). `UsageStats` is never persisted directly — only its `data` property is handed to the DTO.

### D3: Internal storage is `dict[str, dict[str, ModelStats]]` (nested by provider → model)

This directly matches the DTO serialization format, eliminating any conversion step. Previous flat `"provider,model"` string keys had no escaping — a model name containing a comma would silently produce a wrong key. The nested dict is explicit, readable, and JSON-serializable with standard Pydantic.

### D4: `add_stats(provider, model, usage, cost=None)` — single method, optional cost

Explored splitting into `add_usage` / `add_cost`. A single method mirrors the natural event grouping (both usage and cost arrive from the same completion event) and eliminates the ordering dependency that two methods would introduce. `cost` is optional because not every adapter emits a `BillingEvent`.

### D5: No-billing path passes `cost=None`, not zero `TokensCost`

Previously, when no `BillingEvent` arrived, a zero-cost `TokensCost` was stored, and the test asserted `cost is not None`. This was misleading — zero cost is indistinguishable from "billing not configured". `cost=None` makes the absence of billing data explicit. Tests updated accordingly.

### D6: `zero()` replaces `_request_statistics = {}`

`Session.acompletion` reset per-request stats by assigning a new empty dict. With `UsageStats`, `zero()` clears the internal dict in place — same semantics, encapsulated.

### D7: `data` property for DTO boundary

`UsageStats.data` returns the internal `_data` directly (no copy). The DTO boundary (`to_dto` / `from_dto`) reads and writes `data` directly. A dedicated `to_dict` / `from_dict` pair was considered and rejected — they would be trivial wrappers since `_data` already has the serialization-compatible type.

## Risks / Trade-offs

- **BREAKING serialization** — `SessionDto.statistics` changes from `dict[str, UsageStatistics]` to `dict[str, dict[str, ModelStats]]`. Any persisted session files with the old format will fail to deserialize. Verified: no persisted session files exist in `models_service_data/` today.
- **`ModelStats` not Pydantic** — Pydantic v2 serializes `NamedTuple` fields correctly. If a future requirement needs custom validators on `ModelStats`, it would need to become a Pydantic model.
- **`data` property returns live reference** — callers receive the actual internal dict, not a copy. Mutation by the caller would corrupt `UsageStats` state. Acceptable because the only consumer is `to_dto`, which reads it immediately for serialization.

## Migration Plan

No running instances or persisted data to migrate. The change is self-contained within the domain layer and its tests. Deploy as a single atomic change.
