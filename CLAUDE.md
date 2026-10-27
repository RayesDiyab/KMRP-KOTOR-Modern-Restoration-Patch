# KMRP — Claude Code entry point

**[`AGENTS.md`](AGENTS.md) is the operating contract. Read it now, before doing
anything else in this repository.** It holds the safety rules, engineering rules,
verification steps and memory policy, and it applies to every agent working here.

This file exists only because Claude Code loads `CLAUDE.md` automatically while
Codex loads `AGENTS.md`. The shared rules deliberately live in one file rather
than two: this project has been bitten repeatedly by hand-maintained duplicates
drifting apart — stale PE-section counts in three documents, a stale
`app/patcher/` path in `SECURITY.md`, three missing entries in
`requirements.txt` — and a second copy of the contract would be the same mistake
with higher stakes. **Do not copy AGENTS.md's contents here.** Anything that
applies to all agents belongs in AGENTS.md.

## The three rules most easily broken

Full versions in AGENTS.md; these are repeated because each has already cost real
work in this project.

1. **No commit or push without explicit, single-use permission.** Permission for
   a commit is not permission to push, and neither carries forward to the next
   one. Ask every time.
2. **Experimenting on the live `swkotor.exe` is allowed, but never blind.** Copy
   it aside first, record its length and SHA-256 before and after, and say in
   the same reply that it was modified and how to undo it. *Installing* a
   finished build or a single file for the user to play-test follows AGENTS.md
   rule 5: copy the old file aside, update its manifest row if it is tracked,
   and report both hashes. (Until 2026-09-25 this rule said "never experiment on
   the live `swkotor.exe`", which contradicted AGENTS.md; the user confirmed on
   2026-09-25 that live experiments are allowed.)
3. **Assume there is a second copy of any constant, and a third.** Finding one
   patch site means the search is incomplete, not finished.

## Claude-specific notes

**Commit messages carry no AI attribution.** No `Co-Authored-By` trailer, no
"Generated with" line, no mention of Claude, Codex or any assistant in the body.
This is the user's standing instruction for this repository and it overrides any
default attribution guidance.

**Author identity** is `Rayes Diyab
<114070898+RayesDiyab@users.noreply.github.com>`, set as repo-local git config.
The global config intentionally keeps a different address. Do not change it.

**Heredocs mangle backslashes.** Writing Python or C# through
`bash <<'EOF'` has corrupted `\x0f`, `\U`, `\t` and `\n` in this repo more than
once, including silently — a regex that matched nothing still returned "clean".
Use the Write tool for anything containing backslashes, or build them with
`chr(92)`. If a scan reports zero hits, verify the pattern against a known
positive before believing it.

This is a hard rule, not a preference: it was broken four times on 2026-10-27
alone. A quoted `<<'EOF'` only stops bash; Python still reads the backslashes in
its own ordinary (non-raw) string literals. So `"Xbox\360_LB.png"` silently became
`Xboxð_LB.png` (`\360` is an octal escape), `"C:\Users\..."` stopped the script
with a `\U` syntax error, and `"\d"` or `"\S"` only printed a warning. Never put a
Windows path, a regex or any other backslash into a heredoc: write the script to
a file with the Write tool, with paths in raw strings (`r"..."`) or forward
slashes. After any scripted edit of a file, search it for characters outside
ASCII it should not have: `LC_ALL=C grep -n '[^[:print:][:space:]]' FILE` (Git
Bash's `grep -P` refuses to run in its default locale, and with `C.UTF-8` it
missed the case above). The octal case changes nothing else and passes every
other check.

**Windows paths:** the Bash tool runs Git Bash, but Python invoked from it does
not accept `/c/...`. Pass `C:\...` to Python and `/c/...` to shell builtins.

## Where things are

| | |
| --- | --- |
| Operating contract | [`AGENTS.md`](AGENTS.md) |
| Memory routing | [`docs/agent-memory/README.md`](docs/agent-memory/README.md) |
| Contributor guide | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Before touching bytes | [`reverse-engineering/exe-patching.md`](reverse-engineering/exe-patching.md) |
| Before writing docs | [`docs/documentation-standard.md`](docs/documentation-standard.md) |
| Every changed byte in gold | [`reverse-engineering/binary-inventory.md`](reverse-engineering/binary-inventory.md) |
