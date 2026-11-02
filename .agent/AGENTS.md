# AGENTS.md

This repository is designed for long-running coding-agent work. The goal is not
to maximize raw code output. The goal is to leave the repo in a state where the
next session can continue without guessing.

## Startup Workflow

Before writing code:

1. Confirm the working directory with `pwd` (expect `financial-tracker` root).
2. Read `.agent/claude-progress.md` for the latest verified state and next step.
3. Read `.agent/feature_list.json` and choose the highest-priority unfinished feature.
4. Review recent commits with `git log --oneline -5`.
5. Run `./init.sh`.
6. Run the required smoke or end-to-end verification before starting new work.

If baseline verification is already failing, fix that first. Do not stack new
feature work on top of a broken starting state.

## Working Rules

- Work on one feature at a time.
- Do not mark a feature complete just because code was added.
- Keep changes within the selected feature scope unless a blocker forces a
  narrow supporting fix.
- Do not silently change verification rules during implementation.
- Prefer durable repo artifacts over chat summaries.
- **Do not merge PRs unless the human asks.**
- **Do not invent commits unless the human asks.**

## Project Facts

- Stack: FastAPI (`backend/`, **uv**) + SvelteKit (`frontend/`) + local Tesseract OCR.
- Money: integer cents, CAD. Tax jurisdiction: Ontario HST (13%) with CRA grocery rules.
- Multi-user: every receipt/query is scoped by `user_id`. Never leak across users.
- No vision LLMs / cloud OCR in v1.
- Python style: **PEP 8** via Ruff. Package manager: **uv** only.

## UI PR Contract

On **any UI change**:

1. Use **Unslop** (`.agent/skills/unslop`) plus design/taste skills
   (`.agent/skills/impeccable`, design-taste-*).
2. Facts from code — do not invent product claims.
3. `.agent/DESIGN.md` is the contract; tokens live in the global stylesheet
   (`frontend/src/app.css`). Do not invent a palette — use host tokens.
4. Bilingual (when added): keep locales in lockstep.
5. One global `Button` owns the lighting recipe (see `.agent/DESIGN.md`).
6. Bans: no CSS Popover split buttons; no oversized fields; no second-hue focus
   ring; no 24/12 card lift; no press-scale; no spinner→check; do not add
   gitleaks/knip/jscpd/osv-scanner/lefthook unless asked.

## Required Artifacts

All agent harness files live under `.agent/` (root symlinks exist for tool discovery):

- `.agent/feature_list.json`: source of truth for feature state
- `.agent/claude-progress.md`: session log and current verified status
- `init.sh`: standard startup and verification path
- `.agent/session-handoff.md`: optional compact handoff for larger sessions
- `.agent/PRODUCT.md` / `.agent/DESIGN.md`: product and design contracts
- `.agent/skills/`: UI craft skills (unslop, impeccable, …)

## Definition Of Done

A feature is done only when all of the following are true:

- the target behavior is implemented
- the required verification actually ran
- evidence is recorded in `.agent/feature_list.json` or `.agent/claude-progress.md`
- the repository remains restartable from the standard startup path

## End Of Session

Before ending a session:

1. Update `.agent/claude-progress.md`.
2. Update `.agent/feature_list.json`.
3. Record any unresolved risk or blocker.
4. Commit only if the human asked.
5. Leave the repo clean enough for the next session to run `./init.sh`
   immediately.
