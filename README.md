# Orchestrator Hub

A file-queue-based orchestrator that spawns specialized Claude Code agents
(coders, researchers, planners) as headless subprocesses, runs them in
parallel inside Tom's Obsidian vault, and collects their outputs without any
manual copy-paste between terminals.

## How it works

```
        ┌───────────────┐    writes JSON    ┌───────────────────────┐
Tom ──► │   cli / hub   │ ────────────────► │ vault/.orchestrator/  │
        └───────┬───────┘                   │   tasks/  results/    │
                │ spawns                    │   errors/ logs/ state │
                ▼                           └───────────────────────┘
        ┌───────────────┐                            ▲
        │  claude --print --dangerously-skip-permissions   │
        │   (one subprocess per task, up to N in parallel) │
        └────────────────────────────────────┬─────────────┘
                                             │ stdout → Result JSON
                                             ▼
                                       hub aggregates,
                                       reports to Tom
```

- Each task is a self-contained pasteable written to `tasks/<task_id>.json`.
- The hub spawns one `claude --print` subprocess per task and pipes the
  prompt (system prompt + task context + instructions) over stdin.
- Stdout is captured to `results/<task_id>.json`; stderr and the full
  prompt go to `logs/<task_id>.log`.
- Failures land in `errors/`; `state/state.json` records every run so an
  interrupted hub can resume.

## Install

```bash
pip install -e ".[dev]"
```

You also need [Claude Code](https://claude.com/claude-code) on `PATH`.

## Quick start

```bash
# 1. Scaffold .orchestrator/ and drop a CLAUDE.md template into your vault.
scripts/setup_vault.sh ~/vault
# (or: python -m orchestrator.cli init ~/vault)

# 2. Edit ~/vault/CLAUDE.md with your folder layout and active projects.

# 3. Dispatch a single task.
python -m orchestrator.cli run ~/vault \
    --agent coder \
    --instructions "Add a foo() helper to Code/utils.py and unit-test it."

# 4. Or batch from a JSON file (an array of pasteables).
python -m orchestrator.cli run ~/vault --batch batch.json --workers 4

# 5. Or let the planner agent decompose a goal for you.
python -m orchestrator.cli plan ~/vault \
    --goal "Audit Projects/Alpha.md and produce a status report in Research/."

# 6. Inspect.
python -m orchestrator.cli status ~/vault
```

A `batch.json` file looks like:

```json
[
  {
    "agent_type": "coder",
    "instructions": "Refactor Code/ingest.py — extract the FTP loop into ingest_ftp().",
    "context": {"file": "Code/ingest.py"}
  },
  {
    "agent_type": "researcher",
    "instructions": "Summarize the Modal vs. Lambda tradeoff into Research/2026-05-12 Modal vs Lambda.md.",
    "expected_output_format": "markdown"
  }
]
```

## Repo layout

```
orchestrator/
├── schema.py           Task / Result / Enums
├── queue.py            atomic file queue (tasks/results/errors/logs)
├── agent.py            subprocess runner around `claude --print`
├── hub.py              parallel dispatcher + planner output parser
├── state.py            thread-safe state.json persistence
├── logging_setup.py    console + per-run file logging
├── cli.py              `python -m orchestrator.cli`
└── prompts/
    ├── coder.md
    ├── researcher.md
    └── planner.md
templates/CLAUDE.md     drop-in vault operating manual for agents
scripts/setup_vault.sh  one-shot scaffolder
tests/                  pytest suite (uses a stub `claude` binary)
```

## Design principles

1. **Self-contained pasteables** — every task carries vault paths, file
   references, expected output format. Agents never ask clarifying
   questions; the planner / Tom is responsible for completeness.
2. **Idempotent operations** — tasks are keyed by `task_id`; writing a
   result removes the task file atomically. Re-running is safe.
3. **Structured outputs** — agent prompts require a fenced ` ```result `
   block (or JSON for the planner) so the hub can parse outputs.
4. **Error isolation** — failures write `errors/<task_id>.json` rather
   than crashing the run. The hub returns a summary including failures.
5. **State persistence** — `.orchestrator/state/state.json` records every
   run and task status; interrupted runs can be inspected and resumed.
6. **Logging** — every dispatched task gets a per-task log file plus a
   per-run orchestrator log under `logs/`.

## Tests

```bash
python -m pytest
```

The hub tests use a stub bash script in place of `claude --print`, so the
suite exercises the full subprocess path without needing a Claude Code
install or network access.

## Roadmap

- [x] file-based queue + atomic writes
- [x] parallel subprocess dispatch
- [x] state persistence
- [x] coder + researcher + planner prompts
- [x] CLI
- [ ] simple TUI (textual) for live task / result monitoring
- [ ] dashboard UI — the original Orchestrator Hub vision
