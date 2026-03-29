---
name: OPSX: Apply
description: Implement tasks from an OpenSpec change with optional delegation to python-developer subagent (Experimental)
category: Workflow
tags:
  - workflow
  - artifacts
  - experimental
  - subagents
---

Implement tasks from an OpenSpec change. Supports batching related tasks and delegating them to the `python-developer` subagent to keep the main context clean.

**Input**: Optionally specify a change name (e.g., `/opsx:apply add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: " and how to override (e.g., `/opsx:apply <other>`).

2. **Check status to understand the schema**

   ```
   openspec status --change "<name>" --json
   ```

   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

3. **Get apply instructions**

   ```
   openspec instructions apply --change "<name>" --json
   ```

   This returns:
   - Context file paths (varies by schema)
   - Progress (total, complete, remaining)
   - Task list with status
   - Dynamic instruction based on current state

   **Handle states:**
   - If `state: "blocked"` (missing artifacts): show message, suggest using `/opsx:continue`
   - If `state: "all_done"`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Read context files**

   Read the files listed in `contextFiles` from the apply instructions output using `ctx_read` with `map` mode where possible. Only use `full` mode for `tasks.md` and `proposal.md`. Specs go in `map` or `signatures` mode unless a task requires editing them.

5. **Plan batches**

   Before implementing, scan `tasks.md` and group pending tasks into **batches**. A batch is a unit of work that will be executed together — either by you or by a delegated subagent.

   **Batching rules:**
   - Group by section heading (`## N.` in tasks.md) when all tasks in the section are pending and touch a coherent set of files.
   - Split a section if tasks target unrelated subsystems.
   - A single task becomes its own batch only if it is structurally large (refactor, new module).
   - Trivial tasks (single import removal, one-line rename, doc touch-up) stay solo in the main agent — do NOT delegate them.

   **Delegation rules:**
   - **Delegate to `python-developer` subagent** when a batch has 3+ tasks sharing a file set, OR when the combined context required (files to read) exceeds ~1.5k lines.
   - **Execute in main agent** when the batch is ≤2 tasks, OR when tasks depend on decisions you just made in the current session that would be expensive to re-explain.
   - If unsure, prefer delegation for batches under secions numbered ≥4 (later sections usually build on earlier ones and benefit from a fresh context).

   Announce the plan:

   ```
   ## Batch plan

   Batch 1 (delegate): Section 2 — ModelBilling Refactoring (2 tasks)
   Batch 2 (self):     Section 3 — SessionUsageStats (1 task)
   Batch 3 (delegate): Section 6 — Session Refactoring (6 tasks)
   Batch 4 (self):     Section 9 — Cleanup (3 tasks, mostly tool runs)
   ```

6. **Show current progress**

   Display:
   - Schema being used
   - Progress: "N/M tasks complete"
   - Batch plan from step 5
   - Dynamic instruction from CLI

7. **Execute batches (loop until done or blocked)**

   For each batch in order:

   **If batch is marked `self`:**
   - Show which task is being worked on
   - Make the code changes required
   - Keep changes minimal and focused
   - Mark task complete in the tasks file: `- [ ]` → `- [x]`
   - Continue to next task in batch

   **If batch is marked `delegate`:**
   - Invoke the `python-developer` subagent with this payload:

     ```
     Change: <change-name>
     Batch: Section <N> — <section title>
     Tasks (verbatim from tasks.md):
     <paste the section's task list>

     Relevant context:
     - proposal.md (full, short)
     - openspec/changes/<name>/specs/<capability>/spec.md (the delta for this section)
     - <any specific code files the tasks reference by path>

     Deliverable:
     - Implement every task in this batch
     - Mark each task `- [x]` in openspec/changes/<name>/tasks.md
     - Run `./run_tests.sh -k <relevant pattern>` at the end
     - Return a compact summary (see python-developer.md)
     ```

   - Wait for the subagent's summary. Do NOT re-read the files it changed unless the summary indicates a problem.
   - If the summary reports failures or pauses, surface it to the user and decide: retry, take over in main agent, or pause the whole apply.

   **Pause if:**
   - Task is unclear → ask for clarification
   - Implementation reveals a design issue → suggest updating artifacts
   - Error or blocker encountered → report and wait for guidance
   - User interrupts

8. **On completion or pause, show status**

   Display:
   - Tasks completed this session (from tasks.md, re-read)
   - Overall progress: "N/M tasks complete"
   - If all done: suggest `/opsx:archive`
   - If paused: explain why and wait for guidance

**Output During Implementation**

```
## Implementing: <change-name> (schema: <schema-name>)

Batch 2/4 (self): Section 3 — SessionUsageStats
Working on task 3.1: <description>
[...implementation...]
✓ Task 3.1 complete

Batch 3/4 (delegate): Section 6 — Session Refactoring
→ Dispatched to python-developer subagent
← Summary: 6/6 tasks done, 14 files changed, tests green (48 passed in 2.1s)
✓ Batch 3 complete
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 30/30 tasks complete ✓

### Batches this session
- Batch 1 (self):     Section 1 — 3/3 ✓
- Batch 2 (delegate): Section 2 — 2/2 ✓
- Batch 3 (delegate): Section 6 — 6/6 ✓
- Batch 4 (self):     Section 9 — 4/4 ✓

All tasks complete! You can archive this change with `/opsx:archive`.
Consider running `spec-check` subagent first to verify the delta is consistent.
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Progress:** 12/30 tasks complete
**Last batch:** Batch 3 (delegate) — Section 6

### Issue Encountered
python-developer reported: <short summary from subagent>

**Options:**
1. Retry the batch with additional guidance
2. Take over in main agent for this batch
3. Pause apply and update artifacts

What would you like to do?
```

**Guardrails**

- Keep going through batches until done or blocked
- Always read context files before starting (from the apply instructions output)
- Always plan batches before executing (step 5) — do not delegate ad hoc
- If a task is ambiguous, pause and ask before implementing or delegating
- If implementation reveals issues, pause and suggest artifact updates
- Keep code changes minimal and scoped to each task
- Update task checkbox immediately after completing each task (or verify subagent did it)
- After a delegated batch, trust the summary — do NOT re-read all changed files "just in case"
- Pause on errors, blockers, or unclear requirements — don't guess
- Use contextFiles from CLI output, don't assume specific file names

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts — not phase-locked, work fluidly
- **Delegation is optional**: If the user prefers to see every step, they can ask `/opsx:apply <name> --no-delegate` and batches will all run as `self`.
