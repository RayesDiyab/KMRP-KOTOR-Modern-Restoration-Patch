# KMRP agent memory

This directory provides deliberate, repository-local continuity for coding agents.
It complements Codex's generated memories; it does not replace source inspection,
Git history, issues, or subsystem documentation.

## Read routes

| Task | Read first | Then consult |
| --- | --- | --- |
| Any repository task | `AGENTS.md`, this file | `PROJECT.md` |
| Build, test, package, or release | `WORKFLOWS.md` | `CONTRIBUTING.md`, `docs/patcher-ui-build.md` |
| Executable or engine patch | `MEMORY.md` | `reverse-engineering/exe-patching.md`, `reverse-engineering/binary-inventory.md`, the subsystem reference |
| GUI, font, map, or scaling work | `MEMORY.md` | `tools/prepare_universal_resources.py`, the relevant `reverse-engineering/` reference |
| Backup, restore, install, or compatibility work | `MEMORY.md`, `WORKFLOWS.md` | `src/patcher/KmrpPatcher.cs`, `docs/patcher-ui-build.md` |
| Documentation work | `PROJECT.md` | `docs/documentation-standard.md` |
| Resume unfinished local work | `HANDOFF.md` if present | Revalidate every recorded state item |
| Machine or live-game interaction | `LOCAL.md` if present | Recheck paths, hashes, process state, and backups before acting |

Do not read all of `docs/` or `reverse-engineering/` by default. Start from their
index files and open only the subsystem relevant to the task.

## Files

- `PROJECT.md` — durable orientation, architecture, and source-of-truth map.
- `WORKFLOWS.md` — canonical commands and verification ladders.
- `MEMORY.md` — curated discoveries, constraints, and rejected approaches that
  save future agents from repeating work.
- `LOCAL.md` — ignored machine-specific paths and observations.
- `HANDOFF.md` — ignored transient task state and the next concrete action.

## Writing memory

Memory entries must be concise and falsifiable. Each entry should say:

1. what is known;
2. how it was established;
3. where the authoritative evidence lives;
4. what must be rechecked because it can change.

Do not use this directory as a session transcript, issue mirror, or second copy of
the reverse-engineering corpus. Link to the authoritative document rather than
duplicating it. Fetch live GitHub issue and release state when network access is
available; a copied backlog becomes stale immediately.

Promote a fact to `MEMORY.md` only when it is likely to matter in later tasks and
has survived direct measurement or implementation verification. Put hypotheses in
the relevant experiment document, not in durable memory.

