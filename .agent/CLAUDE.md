# CLAUDE.md

You are working in a repository designed for long-running implementation work.
Prioritize reliable completion, continuity across sessions, and explicit
verification over speed.

## Operating Loop

At the start of every session:

1. Run `pwd` and confirm you are in the expected repository root.
2. Read `.agent/claude-progress.md`.
3. Read `.agent/feature_list.json`.
4. Review recent commits with `git log --oneline -5`.
5. Run `./init.sh` (or `docker compose up --build` for the full stack).
6. Check whether the baseline smoke or end-to-end path is already broken.

Then select exactly one unfinished feature and work only on that feature until
you either verify it or document why it is blocked.

## Rules

- One active feature at a time.
- Do not claim completion without runnable evidence.
- Do not rewrite the feature list to hide unfinished work.
- Do not remove or weaken tests just to make the task look complete.
- Use repository artifacts as the system of record.
- Follow `.agent/AGENTS.md` UI PR contract for any frontend work.
- Do not merge unless asked. Do not invent a palette.

## Required Files

Harness files live under `.agent/` (root symlinks for discovery):

- `.agent/feature_list.json`
- `.agent/claude-progress.md`
- `init.sh`
- `.agent/session-handoff.md` when a compact handoff is useful
- `.agent/PRODUCT.md`, `.agent/DESIGN.md`
- `.agent/skills/`

## Completion Gate

A feature can move to `passing` only after the required verification succeeds
and the result is recorded.

## Before You Stop

1. Update the progress log.
2. Update the feature state.
3. Record what is still broken or unverified.
4. Commit only if the human asked.
5. Leave a clean restart path for the next session.
