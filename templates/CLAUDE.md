# Vault Operating Manual — for agents invoked by the Orchestrator Hub

This file is the ground truth every agent reads before touching the vault.
Update it whenever folder conventions or project priorities change.

## Folder structure

```
<vault root>/
├── CLAUDE.md              # this file
├── .orchestrator/         # hub state — agents only touch this via the hub
│   ├── tasks/             # pending task JSON files
│   ├── results/           # completed result JSON files
│   ├── errors/            # failed task reports
│   ├── logs/              # per-task stdout/stderr captures
│   └── state/             # state.json
├── Projects/              # one note per active project
├── Research/              # researcher agent writes notes here
├── Code/                  # coder agent writes scripts and source here
├── Daily/                 # Tom's daily notes — read-only for agents
├── Inbox/                 # quick captures — read-only for agents
└── Scratch/               # ephemeral scratch space agents may write to
```

## Naming conventions

- Notes use `Title Case With Spaces.md` (e.g. `Ingestion Pipeline Design.md`).
- Project notes live under `Projects/<Project Name>.md`.
- Research notes use frontmatter (`title`, `created`, `agent`, `task_id`,
  `sources`) and live under `Research/<YYYY-MM-DD> <Topic>.md`.
- Code files keep their idiomatic language naming (snake_case for Python,
  kebab-case for shell scripts).

## Folder write permissions for agents

| Folder           | Read | Write |
|------------------|:----:|:-----:|
| `Projects/`      |  Y   |   Y   |
| `Research/`      |  Y   |   Y   |
| `Code/`          |  Y   |   Y   |
| `Scratch/`       |  Y   |   Y   |
| `.orchestrator/` |  Y   |  via hub only |
| `Daily/`         |  Y   |   N   |
| `Inbox/`         |  Y   |   N   |

If a task asks an agent to touch a read-only folder, the agent should
return `status: failed` with a note rather than silently writing.

## Tom's active projects (update this list as priorities shift)

1. **Project Alpha** — _Priority: P0_ — short description here.
2. **Project Bravo** — _Priority: P1_ — short description here.
3. **Project Charlie** — _Priority: P1_ — short description here.
4. **Project Delta** — _Priority: P2_ — short description here.
5. **Project Echo** — _Priority: P2_ — short description here.

## Preferred output formats

- Research notes: markdown with the frontmatter above; cite every source.
- Code: include a brief module docstring; no comment spam; pass linters.
- Result blocks (parsed by the orchestrator): fenced ` ```result ` blocks
  with the fields described in each agent's prompt.

## Writing style

- Direct, declarative, present tense.
- No filler ("It's worth noting that…", "In conclusion…").
- Prefer bullet lists for facts; reserve prose for synthesis.
- Mark uncertainty inline (`[unverified]`, `TODO`, `assumption:`).
