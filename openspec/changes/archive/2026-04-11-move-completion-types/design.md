## Context

`completion.py` currently defines three unrelated concepts in one file:
- `CompletionConfig` — LLM request configuration
- `StopReason` — why a model generation stopped (session-level concept)
- `TokensUsage` — token counts for a single completion (usage tracking concept)

Both `StopReason` and `TokensUsage` are imported by `session.py` and `usage_stats.py` respectively, creating reverse coupling: modules that own these concepts must import them from a module that is logically unrelated to them.

## Goals / Non-Goals

**Goals:**
- Move `StopReason` to `session.py` where it is used as a session-domain type
- Move `TokensUsage` to `usage_stats.py` where it belongs as a usage tracking type
- Update all import sites to reference the new locations
- Leave `CompletionConfig` in `completion.py`

**Non-Goals:**
- No behavior changes
- No renaming of types
- No changes to type definitions or fields

## Decisions

### Decision: Destination modules

`StopReason` → `session.py`: Session state tracks `stop_reason` directly. This enum describes *why a session turn ended*, which is a session-domain concept.

`TokensUsage` → `usage_stats.py`: `UsageStat` wraps a `TokensUsage` instance. All arithmetic and aggregation over token counts lives in `usage_stats.py`. The type belongs alongside its consumers.

**Alternative considered**: Create new dedicated files (e.g., `stop_reason.py`, `tokens_usage.py`). Rejected — these are small value types, not modules warranting their own files. Placing them in the module that owns their concept is cleaner.

### Decision: Import update approach

Update all import sites directly (no re-exports from `completion.py`). Re-exporting the moved types from `completion.py` for backwards compatibility would defeat the purpose of the move and leave the coupling intact.

Affected files:
- `completion.py` — remove `StopReason`, `TokensUsage` definitions
- `session.py` — add `StopReason` definition, remove import of `StopReason` from `completion.py`
- `usage_stats.py` — add `TokensUsage` definition, remove import of `TokensUsage` from `completion.py`
- `llm_port.py` — update imports: `StopReason` ← `session`, `TokensUsage` ← `usage_stats`
- `ws_protocol.py` — update imports: `StopReason` ← `session`, `TokensUsage` ← `usage_stats`
- `ws_handler.py` — update import: `StopReason` ← `session`

## Risks / Trade-offs

[Circular import risk] → Mitigation: Verify that `session.py` does not import from `usage_stats.py` or vice versa before moving. Current code shows no such cycle.

[Missing import sites] → Mitigation: Use `grep` to find all references before and after the change; confirm zero remaining imports of `StopReason`/`TokensUsage` from `completion.py`.
