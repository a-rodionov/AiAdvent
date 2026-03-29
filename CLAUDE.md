# lean-ctx — Context Engineering Layer

PREFER lean-ctx MCP tools over native equivalents for token savings:

| PREFER                      | OVER                     | Why                                                            |
| --------------------------- | ------------------------ | -------------------------------------------------------------- |
| `ctx_read(path)`            | Read / cat / head / tail | Session caching, 8 compression modes, re-reads cost ~13 tokens |
| `ctx_shell(command)`        | Bash (shell commands)    | Pattern-based compression for git, npm, cargo, docker, tsc     |
| `ctx_search(pattern, path)` | Grep / rg                | Compact context, token-efficient results                       |
| `ctx_tree(path, depth)`     | ls / find                | Compact directory maps with file counts                        |

## ctx_read Modes

| Situation                              | Mode                  |
| -------------------------------------- | --------------------- |
| File you will edit                     | `full`                |
| Code referenced by a spec, not editing | `signatures` or `map` |
| Verifying your own edit                | `diff`                |
| Large file, interested in one function | `lines:N-M`           |
| Just need dependency/API shape         | `map`                 |

Default to the narrowest mode that answers the question. Upgrade only if it proves insufficient. Do NOT read files in `full` mode "just in case".

## File Editing

Use native Edit/StrReplace when available. If Edit requires Read and Read is unavailable,
use `ctx_edit(path, old_string, new_string)` — it reads, replaces, and writes in one MCP call.
NEVER loop trying to make Edit work. If it fails, switch to ctx_edit immediately.
Write, Delete have no lean-ctx equivalent — use them normally.

# Project: LLM Agent

An LLM agent implemented as a Python library with a FastAPI web server and a Textual TUI client.

## Tech Stack

- **Language:** Python 3.11
- **Web framework:** FastAPI + Uvicorn
- **LLM integration:** any-llm-sdk (provider-agnostic)
- **TUI client:** Textual
- **Persistence:** filesystem (JSON files)
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Linting/Formatting:** ruff
- **Type checking:** mypy (strict-ish, see `pyproject.toml`)

## Architecture

See [docs/ai/ARCHITECTURE.md](docs/ai/ARCHITECTURE.md).

## Entry Points

- `server/server.py` — FastAPI server (`python server.py --config <path>`)
- `client.py` — Textual TUI client (`python client.py [--host] [--port]`)

## Commands

Use the venv — bare `python` / `python3` are not on PATH:

```bash
./run_tests.sh [-k <pattern>] [--cov]   # run tests (see docs/ai/TESTING.md)
.venv/bin/python -m mypy server/         # type-check server code
.venv/bin/python -m ruff check .         # lint
.venv/bin/python -m ruff format .        # format
```

## Testing

See [docs/ai/TESTING.md](docs/ai/TESTING.md).

## OpenSpec

- Active changes: `openspec/changes/<name>/` — contains `proposal.md`, `tasks.md`, `specs/` delta
- Current truth: `openspec/specs/`
- **Do NOT read `openspec/changes/archive/` unless explicitly asked** — it's history, not context.
- When working on a change, read only that change's folder, not others.

## Development Rules

### Code Quality

- **ruff** for linting and formatting (config in `pyproject.toml`)
- **mypy** for type checking (strict for app code, relaxed for tests)
- Line length: 120 characters
- Quote style: double quotes
- Import sorting: isort via ruff
